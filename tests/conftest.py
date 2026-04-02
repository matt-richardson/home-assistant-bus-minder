import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.busminder.const import (
    CONF_OPERATOR_URL,
    CONF_ROUTE_GROUP_NAME,
    CONF_ROUTE_GROUP_UUID,
    CONF_ROUTES,
    DOMAIN,
)

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def mock_coordinator_signalr():
    """Prevent real SignalR connections and lingering threads in every test.

    Patches coordinator.aiohttp (prevents real ClientSession creation — on
    Python 3.12+ a real session spawns a _run_safe_shutdown_loop daemon thread
    that HA's verify_cleanup fixture treats as a failure) and SignalRClient.

    The default stream holds open indefinitely so the coordinator stays in its
    'async for' loop and never hits the retry/backoff path (which would cause
    tests to hang waiting for asyncio.sleep(5+) between retries).

    Also mocks async_get_clientsession so coordinator.async_start()'s connection
    test always succeeds without making real HTTP requests.

    Tests that need specific stream or session behaviour can override the
    relevant patches inside their own context.
    """

    async def _hold_open(on_connected=None):
        if on_connected is not None:
            on_connected()
        await asyncio.sleep(999999)
        yield  # never reached — makes this an async generator

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)
    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_resp)

    with patch(
        "custom_components.busminder.coordinator.async_get_clientsession",
        return_value=mock_session,
    ), patch("custom_components.busminder.coordinator.SignalRClient") as mock_client:
        mock_client.return_value.stream = _hold_open
        yield mock_client


@pytest.fixture
def config_entry_data():
    return {
        CONF_OPERATOR_URL: "https://example-buslines.com.au/live-tracking/springfield-high/",
        CONF_ROUTE_GROUP_UUID: "aaaaaaaa-0000-4000-8000-000000000001",
        CONF_ROUTE_GROUP_NAME: "Springfield High - PM",
        CONF_ROUTES: [
            {
                "trip_id": 10001,
                "name": "1001 : Springfield 1 | Springfield High to City - PM",
                "route_number": "1001",
                "uuid": "aaaaaaaa-0000-4000-8000-000000000001",
                "stop_id": 10001,
                "stop_name": "Springfield High - Main Gate",
                "stop_lat": -37.7877,
                "stop_lng": 145.33912,
            },
            {
                "trip_id": 10002,
                "name": "1002 : Springfield 2 | Springfield High to City Station - PM",
                "route_number": "1002",
                "uuid": "aaaaaaaa-0000-4000-8000-000000000001",
                "stop_id": 10003,
                "stop_name": "City Station",
                "stop_lat": -37.860,
                "stop_lng": 145.295,
            },
        ],
    }


@pytest.fixture
def mock_config_entry(config_entry_data):
    return MockConfigEntry(domain=DOMAIN, data=config_entry_data)
