from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import aiohttp

from .const import MAPS_BASE_URL, SIGNALR_HEADERS
from .exceptions import BusMinderConnectionError
from .models import Route, RouteGroup

if TYPE_CHECKING:
    pass

_MAPS_UUID_RE = re.compile(
    r"maps\.busminder\.com\.au/route/live/([0-9a-fA-F-]{36})",
    re.IGNORECASE,
)
_BARE_UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_ROUTEMAP_RE = re.compile(
    r"var liveMap\s*=\s*new routemap\s*\(\s*['\"][^'\"]*['\"]\s*,\s*(\{.*?\})\s*\)\s*;",
    re.DOTALL,
)


def extract_uuids(text: str) -> list[str]:
    """Pull BusMinder route group UUIDs out of arbitrary text.

    Prefers maps.busminder.com.au/route/live/{uuid} matches (so operator-page
    HTML and pasted links only yield BusMinder UUIDs); falls back to bare UUIDs
    when no such URL is present. Lowercased, deduplicated, order preserved.
    """
    text = text or ""
    matches = _MAPS_UUID_RE.findall(text) or _BARE_UUID_RE.findall(text)
    out: list[str] = []
    for match in matches:
        uuid = match.lower()
        if uuid not in out:
            out.append(uuid)
    return out


def _clean_title(title: str) -> str:
    """Remove duplicate leading prefix from BusMinder page titles.

    e.g. "Springfield High - Springfield High - PM" → "Springfield High - PM"
    """
    parts = title.split(" - ")
    if len(parts) >= 2 and parts[0].strip() == parts[1].strip():
        parts = parts[1:]
    return " - ".join(parts).strip()


async def fetch_route_group_by_uuid(session: aiohttp.ClientSession, uuid: str) -> RouteGroup:
    """Fetch a single route group from maps.busminder.com.au by UUID."""
    maps_url = f"{MAPS_BASE_URL}/route/live/{uuid.upper()}"
    try:
        async with session.get(maps_url, headers=SIGNALR_HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()
            maps_html = await resp.text()
    except aiohttp.ClientError as exc:
        raise BusMinderConnectionError(f"Cannot fetch route group page {maps_url}: {exc}") from exc

    match = _ROUTEMAP_RE.search(maps_html)
    if not match:
        raise BusMinderConnectionError("Could not find routemap data on BusMinder page")

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise BusMinderConnectionError(f"Invalid routemap JSON: {exc}") from exc

    title_match = re.search(r"<title>([^<]+)</title>", maps_html)
    raw_title = title_match.group(1).strip() if title_match else uuid
    group_name = _clean_title(raw_title)

    routes = [Route.from_metadata(r, uuid=uuid) for r in data.get("routes", [])]
    return RouteGroup(uuid=uuid, name=group_name, routes=routes)


async def fetch_route_groups_by_uuids(session: aiohttp.ClientSession, uuids: list[str]) -> RouteGroup:
    """Fetch each UUID and merge into one RouteGroup.

    Raises BusMinderConnectionError on the first UUID that fails — config-time
    input should surface a bad entry rather than silently importing a subset.
    """
    groups = [await fetch_route_group_by_uuid(session, uuid) for uuid in uuids]
    all_routes = [route for group in groups for route in group.routes]

    # Derive a combined name: strip trailing " - AM" / " - PM" and deduplicate.
    base_names = [re.sub(r"\s*-\s*(AM|PM)\s*$", "", g.name, flags=re.IGNORECASE).strip() for g in groups]
    combined_name = base_names[0] if len(set(base_names)) == 1 else groups[0].name

    return RouteGroup(uuid=groups[0].uuid, name=combined_name, routes=all_routes)


async def fetch_route_group_from_operator_url(session: aiohttp.ClientSession, operator_url: str) -> RouteGroup:
    """Fetch the operator page, extract BusMinder UUIDs, and merge their route groups."""
    try:
        async with session.get(operator_url, headers=SIGNALR_HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()
            html = await resp.text()
    except aiohttp.ClientError as exc:
        raise BusMinderConnectionError(f"Cannot connect to {operator_url}: {exc}") from exc

    uuids = extract_uuids(html)
    if not uuids:
        raise BusMinderConnectionError(f"No BusMinder iframe found on {operator_url}")

    return await fetch_route_groups_by_uuids(session, uuids)
