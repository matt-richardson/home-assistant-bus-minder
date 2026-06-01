from pathlib import Path

import aiohttp
import pytest
from aioresponses import aioresponses as aioresponses_ctx

from custom_components.busminder.exceptions import BusMinderConnectionError
from custom_components.busminder.scraper import (
    extract_uuids,
    fetch_route_group_from_operator_url,
    fetch_route_groups_by_uuids,
)

OPERATOR_HTML = (Path(__file__).parent / "fixtures" / "operator_page.html").read_text()
ROUTE_GROUP_HTML = (Path(__file__).parent / "fixtures" / "route_group.html").read_text()

OPERATOR_URL = "https://example-buslines.com.au/live-tracking/springfield-high/"
MAPS_URL = "https://maps.busminder.com.au/route/live/AAAAAAAA-0000-4000-8000-000000000001"


@pytest.fixture
def mock_aiohttp():
    with aioresponses_ctx() as m:
        yield m


async def test_fetch_route_group_success(mock_aiohttp):
    mock_aiohttp.get(OPERATOR_URL, body=OPERATOR_HTML, content_type="text/html")
    mock_aiohttp.get(MAPS_URL, body=ROUTE_GROUP_HTML, content_type="text/html")

    async with aiohttp.ClientSession() as session:
        group = await fetch_route_group_from_operator_url(session, OPERATOR_URL)

    assert group.uuid == "aaaaaaaa-0000-4000-8000-000000000001"
    assert group.name == "Springfield High"
    assert len(group.routes) == 2
    assert group.routes[0].route_number == "1001"
    assert group.routes[1].route_number == "1002"


async def test_fetch_route_group_stops(mock_aiohttp):
    mock_aiohttp.get(OPERATOR_URL, body=OPERATOR_HTML, content_type="text/html")
    mock_aiohttp.get(MAPS_URL, body=ROUTE_GROUP_HTML, content_type="text/html")

    async with aiohttp.ClientSession() as session:
        group = await fetch_route_group_from_operator_url(session, OPERATOR_URL)

    all_stops = group.all_stops()
    stop_names = [s.name for s in all_stops]
    assert "Springfield High - Main Gate" in stop_names
    assert "City Station" in stop_names


async def test_fetch_route_group_stop_position(mock_aiohttp):
    mock_aiohttp.get(OPERATOR_URL, body=OPERATOR_HTML, content_type="text/html")
    mock_aiohttp.get(MAPS_URL, body=ROUTE_GROUP_HTML, content_type="text/html")

    async with aiohttp.ClientSession() as session:
        group = await fetch_route_group_from_operator_url(session, OPERATOR_URL)

    main_gate_stop = next(s for s in group.all_stops() if "Main Gate" in s.name)
    # "blseFopavZ" decodes to approx (-37.7877, 145.33912)
    assert abs(main_gate_stop.lat - (-37.7877)) < 0.001
    assert abs(main_gate_stop.lng - 145.33912) < 0.001


async def test_fetch_route_group_no_iframe(mock_aiohttp):
    mock_aiohttp.get(OPERATOR_URL, body="<html><body>No iframe here</body></html>", content_type="text/html")

    async with aiohttp.ClientSession() as session:
        with pytest.raises(BusMinderConnectionError, match="No BusMinder iframe"):
            await fetch_route_group_from_operator_url(session, OPERATOR_URL)


async def test_fetch_route_group_connection_error(mock_aiohttp):
    mock_aiohttp.get(OPERATOR_URL, exception=aiohttp.ClientConnectionError("timeout"))

    async with aiohttp.ClientSession() as session:
        with pytest.raises(BusMinderConnectionError, match="Cannot connect"):
            await fetch_route_group_from_operator_url(session, OPERATOR_URL)


async def test_fetch_route_group_maps_connection_error(mock_aiohttp):
    """Raises BusMinderConnectionError when maps.busminder.com.au is unreachable."""
    mock_aiohttp.get(OPERATOR_URL, body=OPERATOR_HTML, content_type="text/html")
    mock_aiohttp.get(MAPS_URL, exception=aiohttp.ClientConnectionError("timeout"))

    async with aiohttp.ClientSession() as session:
        with pytest.raises(BusMinderConnectionError, match="Cannot fetch route group page"):
            await fetch_route_group_from_operator_url(session, OPERATOR_URL)


async def test_fetch_route_group_no_routemap_data(mock_aiohttp):
    """Raises BusMinderConnectionError when routemap data is not found on BusMinder page."""
    mock_aiohttp.get(OPERATOR_URL, body=OPERATOR_HTML, content_type="text/html")
    mock_aiohttp.get(
        MAPS_URL,
        body="<html><body><title>Test</title>No routemap here</body></html>",
        content_type="text/html",
    )

    async with aiohttp.ClientSession() as session:
        with pytest.raises(BusMinderConnectionError, match="Could not find routemap data"):
            await fetch_route_group_from_operator_url(session, OPERATOR_URL)


async def test_fetch_route_group_invalid_json(mock_aiohttp):
    """Raises BusMinderConnectionError when routemap JSON is invalid."""
    # Build a page that has the routemap script but with invalid JSON
    bad_json_html = (
        "<html><body><title>Test</title>"
        "<script>var liveMap = new routemap('', {invalid: json:});</script>"
        "</body></html>"
    )
    mock_aiohttp.get(OPERATOR_URL, body=OPERATOR_HTML, content_type="text/html")
    mock_aiohttp.get(MAPS_URL, body=bad_json_html, content_type="text/html")

    async with aiohttp.ClientSession() as session:
        with pytest.raises(BusMinderConnectionError, match="Invalid routemap JSON"):
            await fetch_route_group_from_operator_url(session, OPERATOR_URL)


UUID_1 = "bf7ce605-0fac-4c51-a2f3-be3faed3c0ba"
UUID_2 = "ba62fb89-d818-481c-8a95-08f48e331aa1"


def test_extract_uuids_full_maps_url():
    text = f"https://maps.busminder.com.au/route/live/{UUID_1.upper()}"
    assert extract_uuids(text) == [UUID_1]


def test_extract_uuids_iframe_snippet():
    text = f'<iframe src="https://maps.busminder.com.au/route/live/{UUID_1.upper()}"></iframe>'
    assert extract_uuids(text) == [UUID_1]


def test_extract_uuids_bare_uuid_fallback():
    assert extract_uuids(UUID_1) == [UUID_1]


def test_extract_uuids_multiline_dedupe_and_order():
    text = (
        f"https://maps.busminder.com.au/route/live/{UUID_1.upper()}\n"
        f"https://maps.busminder.com.au/route/live/{UUID_2.upper()}\n"
        f"https://maps.busminder.com.au/route/live/{UUID_1}\n"  # duplicate, lowercase
    )
    assert extract_uuids(text) == [UUID_1, UUID_2]


def test_extract_uuids_prefers_maps_urls_over_stray_uuids():
    # A stray non-BusMinder UUID must be ignored when a maps URL is present.
    text = (
        "<meta name=tracking content=00000000-0000-4000-8000-000000000000>"
        f'<iframe src="https://maps.busminder.com.au/route/live/{UUID_1.upper()}"></iframe>'
    )
    assert extract_uuids(text) == [UUID_1]


def test_extract_uuids_none():
    assert extract_uuids("nothing to see here") == []
    assert extract_uuids("") == []


MAPS_URL_1 = f"https://maps.busminder.com.au/route/live/{UUID_1.upper()}"
MAPS_URL_2 = f"https://maps.busminder.com.au/route/live/{UUID_2.upper()}"


async def test_fetch_route_groups_by_uuids_merges(mock_aiohttp):
    mock_aiohttp.get(MAPS_URL_1, body=ROUTE_GROUP_HTML, content_type="text/html")
    mock_aiohttp.get(MAPS_URL_2, body=ROUTE_GROUP_HTML, content_type="text/html")

    async with aiohttp.ClientSession() as session:
        group = await fetch_route_groups_by_uuids(session, [UUID_1, UUID_2])

    # Two routes per group → four merged; uuid is the first.
    assert len(group.routes) == 4
    assert group.uuid == UUID_1


async def test_fetch_route_groups_by_uuids_raises_on_bad_uuid(mock_aiohttp):
    mock_aiohttp.get(MAPS_URL_1, body=ROUTE_GROUP_HTML, content_type="text/html")
    mock_aiohttp.get(
        MAPS_URL_2,
        body="<html><title>x</title>no routemap</html>",
        content_type="text/html",
    )

    async with aiohttp.ClientSession() as session:
        with pytest.raises(BusMinderConnectionError, match="Could not find routemap data"):
            await fetch_route_groups_by_uuids(session, [UUID_1, UUID_2])
