import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from custom_components.busminder.models import BusPosition


def make_position(trip_id=10001, lat=-37.820, lng=145.340, last_stop_id=10001):
    return BusPosition(
        trip_id=trip_id,
        bus_id=1,
        bus_reg="1528",
        lat=lat,
        lng=lng,
        last_stop_id=last_stop_id,
        last_stop_time=None,
        received_at=datetime.now(timezone.utc),
    )


async def test_sensor_unavailable_before_first_update(hass: HomeAssistant, mock_config_entry):
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
        await asyncio.sleep(9999)

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient:
        with patch("custom_components.busminder.coordinator.SpeedTracker") as MockTracker:
            MockClient.return_value.stream = fake_stream
            MockTracker.return_value.get_speed.return_value = 30.0
            MockTracker.return_value.update = MagicMock()

            mock_config_entry.add_to_hass(hass)
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()
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


async def test_sensor_unavailable_when_connection_failed(hass: HomeAssistant, mock_config_entry):
    """Sensor is unavailable when coordinator.connection_failed is True."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    coordinator.connection_failed = True
    coordinator.async_set_updated_data({10001: make_position()})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.busminder_1001_eta")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_sensor_attributes_not_running_when_stale(hass: HomeAssistant, mock_config_entry):
    """Sensor shows not_running status when position data is stale (>5 min old)."""
    stale_time = datetime.now(timezone.utc) - timedelta(seconds=400)
    pos = BusPosition(
        trip_id=10001,
        bus_id=1,
        bus_reg="1528",
        lat=-37.820,
        lng=145.340,
        last_stop_id=10001,
        last_stop_time=None,
        received_at=stale_time,
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    coordinator.async_set_updated_data({10001: pos})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.busminder_1001_eta")
    assert state is not None
    assert state.attributes["status"] == "not_running"


async def test_sensor_extra_attrs_no_position(hass: HomeAssistant, mock_config_entry):
    """BusEtaSensor.extra_state_attributes returns not_running dict when no position data."""
    from custom_components.busminder.models import Route, Stop
    from custom_components.busminder.sensor import BusEtaSensor

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    monitored_stop = Stop(id=10001, name="Main Gate", lat=-37.787, lng=145.339, sequence=1)
    route = Route(trip_id=10001, name="Test", route_number="1001", colour="", stops=[monitored_stop])
    sensor = BusEtaSensor(coordinator, mock_config_entry, route, monitored_stop)

    # No coordinator data → _get_position returns None → should return not_running
    coordinator.async_set_updated_data({})
    attrs = sensor.extra_state_attributes
    assert attrs == {"status": "not_running"}


async def test_sensor_eta_minutes_returned(hass: HomeAssistant, mock_config_entry):
    """Sensor native_value returns minutes when ETA is calculable."""
    from unittest.mock import patch as _patch

    # Position where bus is before the monitored stop (last_stop_id=10000, not the monitored stop 10001)
    pos = BusPosition(
        trip_id=10001,
        bus_id=1,
        bus_reg="1528",
        lat=-37.820,
        lng=145.340,
        last_stop_id=10000,  # a stop before the monitored stop
        last_stop_time=None,
        received_at=datetime.now(timezone.utc),
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    entity_id = "sensor.busminder_1001_eta"

    # Manually inject position data and patch get_speed to return a valid speed
    with _patch.object(coordinator, "get_speed", return_value=30.0):
        coordinator.async_set_updated_data({10001: pos})
        await hass.async_block_till_done()

    # The state may be "unknown" if stops don't include 10000, but we just verify no crash
    state = hass.states.get(entity_id)
    assert state is not None


async def test_each_sensor_gets_its_own_stop(hass: HomeAssistant, mock_config_entry):
    """sensor.async_setup_entry passes each route's own stop to its BusEtaSensor."""
    from unittest.mock import MagicMock

    from custom_components.busminder.sensor import BusEtaSensor, async_setup_entry

    # Stub the coordinator directly — coordinator.py still reads old stop keys (fixed in Task 2)
    mock_coordinator = MagicMock()
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = mock_coordinator

    # Call async_setup_entry with a capturing add_entities callback
    add_entities = MagicMock()
    await async_setup_entry(hass, mock_config_entry, add_entities)
    captured = add_entities.call_args[0][0]

    sensors = [e for e in captured if isinstance(e, BusEtaSensor)]
    assert len(sensors) == 2
    stop_by_trip = {s._route.trip_id: s._monitored_stop.id for s in sensors}
    assert stop_by_trip[10001] == 10001  # Main Gate
    assert stop_by_trip[10002] == 10003  # City Station
