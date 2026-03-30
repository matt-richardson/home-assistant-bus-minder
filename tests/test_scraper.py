import pytest
from pathlib import Path
from aioresponses import aioresponses as aioresponses_ctx
import aiohttp

from custom_components.busminder.scraper import (
    fetch_route_group_from_operator_url,
    ScraperError,
)

OPERATOR_HTML = (Path(__file__).parent / "fixtures" / "operator_page.html").read_text()
ROUTE_GROUP_HTML = (Path(__file__).parent / "fixtures" / "route_group.html").read_text()

OPERATOR_URL = "https://your-operator.com.au/live-tracking/your-school/"
MAPS_URL = "https://maps.busminder.com.au/route/live/BA62FB89-D818-481C-8A95-08F48E331AA1"


@pytest.fixture
def mock_aiohttp():
    with aioresponses_ctx() as m:
        yield m


async def test_fetch_route_group_success(mock_aiohttp):
    mock_aiohttp.get(OPERATOR_URL, body=OPERATOR_HTML, content_type="text/html")
    mock_aiohttp.get(MAPS_URL, body=ROUTE_GROUP_HTML, content_type="text/html")

    async with aiohttp.ClientSession() as session:
        group = await fetch_route_group_from_operator_url(session, OPERATOR_URL)

    assert group.uuid == "ba62fb89-d818-481c-8a95-08f48e331aa1"
    assert group.name == "Springfield High - PM"
    assert len(group.routes) == 2
    assert group.routes[0].route_number == "3428"
    assert group.routes[1].route_number == "3430"


async def test_fetch_route_group_stops(mock_aiohttp):
    mock_aiohttp.get(OPERATOR_URL, body=OPERATOR_HTML, content_type="text/html")
    mock_aiohttp.get(MAPS_URL, body=ROUTE_GROUP_HTML, content_type="text/html")

    async with aiohttp.ClientSession() as session:
        group = await fetch_route_group_from_operator_url(session, OPERATOR_URL)

    all_stops = group.all_stops()
    stop_names = [s.name for s in all_stops]
    assert "Springfield High - Bottom Area" in stop_names
    assert "Boronia Station" in stop_names


async def test_fetch_route_group_stop_position(mock_aiohttp):
    mock_aiohttp.get(OPERATOR_URL, body=OPERATOR_HTML, content_type="text/html")
    mock_aiohttp.get(MAPS_URL, body=ROUTE_GROUP_HTML, content_type="text/html")

    async with aiohttp.ClientSession() as session:
        group = await fetch_route_group_from_operator_url(session, OPERATOR_URL)

    main_gate_stop = next(s for s in group.all_stops() if "Bottom Area" in s.name)
    # "blseFopavZ" decodes to approx (-37.7877, 145.33912)
    assert abs(main_gate_stop.lat - (-37.7877)) < 0.001
    assert abs(main_gate_stop.lng - 145.33912) < 0.001


async def test_fetch_route_group_no_iframe(mock_aiohttp):
    mock_aiohttp.get(OPERATOR_URL, body="<html><body>No iframe here</body></html>", content_type="text/html")

    async with aiohttp.ClientSession() as session:
        with pytest.raises(ScraperError, match="No BusMinder iframe"):
            await fetch_route_group_from_operator_url(session, OPERATOR_URL)


async def test_fetch_route_group_connection_error(mock_aiohttp):
    mock_aiohttp.get(OPERATOR_URL, exception=aiohttp.ClientConnectionError("timeout"))

    async with aiohttp.ClientSession() as session:
        with pytest.raises(ScraperError, match="Cannot connect"):
            await fetch_route_group_from_operator_url(session, OPERATOR_URL)
