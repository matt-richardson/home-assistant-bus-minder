import asyncio
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
from custom_components.busminder.coordinator import BusMinderCoordinator
from custom_components.busminder.models import BusPosition


async def test_coordinator_dispatches_position(hass: HomeAssistant, mock_config_entry):
    """GPS events from SignalR should update coordinator.data."""
    mock_config_entry.add_to_hass(hass)

    async def fake_stream():
        pos = BusPosition(
            trip_id=10001, bus_id=11528, bus_reg="1528",
            lat=-37.820, lng=145.340,
            last_stop_id=10001, last_stop_time=None,
            received_at=datetime.now(timezone.utc),
        )
        yield pos
        await asyncio.sleep(9999)  # hold open

    with patch(
        "custom_components.busminder.coordinator.SignalRClient"
    ) as MockClient:
        MockClient.return_value.stream = fake_stream
        coordinator = BusMinderCoordinator(hass, mock_config_entry)
        await coordinator.async_start()
        await asyncio.sleep(0.1)  # let event loop tick

    assert 10001 in coordinator.data
    assert coordinator.data[10001].bus_reg == "1528"


async def test_coordinator_filters_unmonitored_routes(hass: HomeAssistant, mock_config_entry):
    """GPS events for trip IDs not in config should be ignored."""

    async def fake_stream():
        pos = BusPosition(
            trip_id=99999,  # not in config
            bus_id=1, bus_reg="XXXX",
            lat=-37.800, lng=145.300,
            last_stop_id=None, last_stop_time=None,
            received_at=datetime.now(timezone.utc),
        )
        yield pos
        await asyncio.sleep(9999)

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient:
        MockClient.return_value.stream = fake_stream
        coordinator = BusMinderCoordinator(hass, mock_config_entry)
        await coordinator.async_start()
        await asyncio.sleep(0.1)

    assert coordinator.data is None or 99999 not in coordinator.data
