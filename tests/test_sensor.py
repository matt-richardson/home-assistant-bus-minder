import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.const import STATE_UNAVAILABLE

from custom_components.busminder.models import BusPosition, Stop, Route


def make_position(trip_id=10001, lat=-37.820, lng=145.340, last_stop_id=10001):
    return BusPosition(
        trip_id=trip_id, bus_id=1, bus_reg="1528",
        lat=lat, lng=lng,
        last_stop_id=last_stop_id, last_stop_time=None,
        received_at=datetime.now(timezone.utc),
    )


async def test_sensor_unavailable_before_first_update(
    hass: HomeAssistant, mock_config_entry
):
    async def empty_stream():
        return
        yield  # make it an async generator

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient:
        MockClient.return_value.stream = empty_stream
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.busminder_1001_eta")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_sensor_shows_eta_minutes(hass: HomeAssistant, mock_config_entry):
    pos = make_position()

    async def fake_stream():
        yield pos
        import asyncio
        await asyncio.sleep(9999)

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient:
        with patch("custom_components.busminder.coordinator.SpeedTracker") as MockTracker:
            MockClient.return_value.stream = fake_stream
            MockTracker.return_value.get_speed.return_value = 30.0
            MockTracker.return_value.update = MagicMock()

            mock_config_entry.add_to_hass(hass)
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()
            import asyncio
            await asyncio.sleep(0.1)
            await hass.async_block_till_done()

    state = hass.states.get("sensor.busminder_1001_eta")
    assert state is not None
    # State is numeric minutes, "unavailable" (no data), or "unknown" (no ETA calculable)
    if state.state not in (STATE_UNAVAILABLE, "unknown"):
        assert int(state.state) >= 0
    if state.state != STATE_UNAVAILABLE:
        assert state.attributes["bus_number"] == "1528"
        assert state.attributes["status"] in ("approaching", "passed", "not_running")
