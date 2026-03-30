import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock

from homeassistant.core import HomeAssistant
from homeassistant.components.device_tracker import SourceType

from custom_components.busminder.models import BusPosition


def make_position(trip_id=10001, lat=-37.820, lng=145.340):
    return BusPosition(
        trip_id=trip_id, bus_id=1, bus_reg="1528",
        lat=lat, lng=lng,
        last_stop_id=10001, last_stop_time=None,
        received_at=datetime.now(timezone.utc),
    )


async def test_device_tracker_registered(hass: HomeAssistant, mock_config_entry):
    async def empty_stream():
        return
        yield

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient:
        MockClient.return_value.stream = empty_stream
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("device_tracker.busminder_1001") is not None
    assert hass.states.get("device_tracker.busminder_1002") is not None


async def test_device_tracker_source_type(hass: HomeAssistant, mock_config_entry):
    async def fake_stream():
        yield make_position()
        import asyncio
        await asyncio.sleep(9999)

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient:
        MockClient.return_value.stream = fake_stream
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        import asyncio
        await asyncio.sleep(0.1)
        await hass.async_block_till_done()

    state = hass.states.get("device_tracker.busminder_1001")
    assert state is not None
    assert state.attributes.get("source_type") == SourceType.GPS
