import asyncio
from datetime import datetime, timezone
from unittest.mock import patch

from homeassistant.components.device_tracker import SourceType
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from custom_components.busminder.models import BusPosition


def make_position(trip_id=10001, lat=-37.820, lng=145.340):
    return BusPosition(
        trip_id=trip_id,
        bus_id=1,
        bus_reg="0042",
        lat=lat,
        lng=lng,
        last_stop_id=10001,
        last_stop_time=None,
        received_at=datetime.now(timezone.utc),
    )


async def test_device_tracker_registered(hass: HomeAssistant, mock_config_entry):
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.busminder_1001") is not None
    assert hass.states.get("device_tracker.busminder_1002") is not None
    assert hass.states.get("device_tracker.busminder_1001").state == STATE_UNAVAILABLE
    assert hass.states.get("device_tracker.busminder_1002").state == STATE_UNAVAILABLE


async def test_device_tracker_source_type(hass: HomeAssistant, mock_config_entry):
    async def fake_stream(on_connected=None):
        if on_connected is not None:
            on_connected()
        yield make_position()
        await asyncio.sleep(9999)

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient:
        MockClient.return_value.stream = fake_stream
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)
        await hass.async_block_till_done()

    state = hass.states.get("device_tracker.busminder_1001")
    assert state is not None
    assert state.attributes.get("source_type") == SourceType.GPS


async def test_device_tracker_unavailable_when_connection_failed(hass: HomeAssistant, mock_config_entry):
    """Device tracker is unavailable when coordinator.connection_failed is True."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    coordinator.connection_failed = True
    coordinator.async_set_updated_data({10001: make_position()})
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.busminder_1001")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
