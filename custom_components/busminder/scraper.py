from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import aiohttp

from .const import MAPS_BASE_URL, SIGNALR_HEADERS
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


class ScraperError(Exception):
    pass


def _clean_title(title: str) -> str:
    """Remove duplicate leading prefix from BusMinder page titles.

    e.g. "Springfield High - Springfield High - PM" → "Springfield High - PM"
    """
    parts = title.split(" - ")
    if len(parts) >= 2 and parts[0].strip() == parts[1].strip():
        parts = parts[1:]
    return " - ".join(parts).strip()


async def fetch_route_group_from_operator_url(
    session: aiohttp.ClientSession, operator_url: str
) -> RouteGroup:
    """
    Fetch the operator's tracking page, extract the BusMinder UUID from the
    embedded iframe, then fetch the route group metadata from maps.busminder.com.au.
    """
    # Step 1: fetch operator page
    try:
        async with session.get(operator_url, headers=SIGNALR_HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()
            html = await resp.text()
    except aiohttp.ClientError as exc:
        raise ScraperError(f"Cannot connect to {operator_url}: {exc}") from exc

    # Step 2: extract UUID
    match = _IFRAME_RE.search(html)
    if not match:
        raise ScraperError(f"No BusMinder iframe found on {operator_url}")
    uuid = match.group(1).lower()

    # Step 3: fetch route group page
    maps_url = f"{MAPS_BASE_URL}/route/live/{uuid.upper()}"
    try:
        async with session.get(maps_url, headers=SIGNALR_HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()
            maps_html = await resp.text()
    except aiohttp.ClientError as exc:
        raise ScraperError(f"Cannot fetch route group page {maps_url}: {exc}") from exc

    # Step 4: parse routemap JSON from inline script
    match = _ROUTEMAP_RE.search(maps_html)
    if not match:
        raise ScraperError("Could not find routemap data on BusMinder page")

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ScraperError(f"Invalid routemap JSON: {exc}") from exc

    # Step 5: extract title for group name
    title_match = re.search(r"<title>([^<]+)</title>", maps_html)
    raw_title = title_match.group(1).strip() if title_match else uuid
    group_name = _clean_title(raw_title)

    routes = [Route.from_metadata(r) for r in data.get("routes", [])]
    return RouteGroup(uuid=uuid, name=group_name, routes=routes)
