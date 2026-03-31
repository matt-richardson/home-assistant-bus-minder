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

_IFRAME_RE = re.compile(
    r'<iframe[^>]+src=["\']https://maps\.busminder\.com\.au/route/live/([A-Fa-f0-9\-]{36})["\']',
    re.IGNORECASE,
)
_ROUTEMAP_RE = re.compile(
    r"var liveMap\s*=\s*new routemap\s*\(\s*['\"][^'\"]*['\"]\s*,\s*(\{.*?\})\s*\)\s*;",
    re.DOTALL,
)


def _clean_title(title: str) -> str:
    """Remove duplicate leading prefix from BusMinder page titles.

    e.g. "Springfield High - Springfield High - PM" → "Springfield High - PM"
    """
    parts = title.split(" - ")
    if len(parts) >= 2 and parts[0].strip() == parts[1].strip():
        parts = parts[1:]
    return " - ".join(parts).strip()


async def _fetch_route_group(
    session: aiohttp.ClientSession, uuid: str
) -> RouteGroup:
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


async def fetch_route_group_from_operator_url(
    session: aiohttp.ClientSession, operator_url: str
) -> RouteGroup:
    """
    Fetch the operator's tracking page, extract all BusMinder UUIDs from
    embedded iframes, fetch each route group, and return them merged.
    """
    # Step 1: fetch operator page
    try:
        async with session.get(operator_url, headers=SIGNALR_HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()
            html = await resp.text()
    except aiohttp.ClientError as exc:
        raise BusMinderConnectionError(f"Cannot connect to {operator_url}: {exc}") from exc

    # Step 2: extract all UUIDs (operators may embed AM and PM groups as separate iframes)
    uuids = [u.lower() for u in _IFRAME_RE.findall(html)]
    if not uuids:
        raise BusMinderConnectionError(f"No BusMinder iframe found on {operator_url}")

    # Step 3: fetch all route groups and merge
    groups = [await _fetch_route_group(session, uuid) for uuid in uuids]
    all_routes = [route for group in groups for route in group.routes]

    # Derive a combined name: strip trailing " - AM" / " - PM" suffixes and deduplicate
    import re as _re
    base_names = [_re.sub(r"\s*-\s*(AM|PM)\s*$", "", g.name, flags=_re.IGNORECASE).strip() for g in groups]
    combined_name = base_names[0] if len(set(base_names)) == 1 else groups[0].name

    return RouteGroup(uuid=groups[0].uuid, name=combined_name, routes=all_routes)
