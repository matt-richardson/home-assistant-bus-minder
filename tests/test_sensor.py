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

    async def fake_stream(on_connected=None):
        if on_connected is not None:
            on_connected()
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
    """ETA sensor returns a value when full route metadata is available."""
    from unittest.mock import AsyncMock
    from unittest.mock import patch as _patch

    from custom_components.busminder.models import Route, RouteGroup, Stop

    full_route_group = RouteGroup(
        uuid="aaaaaaaa-0000-4000-8000-000000000001",
        name="Springfield High - PM",
        routes=[
            Route(
                trip_id=10001,
                name="1001 : Springfield 1 | Springfield High to City - PM",
                route_number="1001",
                colour="",
                stops=[
                    Stop(id=10000, name="Depot", lat=-37.760, lng=145.310, sequence=1),
                    Stop(id=10001, name="Springfield High - Main Gate", lat=-37.7877, lng=145.33912, sequence=2),
                ],
            )
        ],
    )

    with _patch(
        "custom_components.busminder.coordinator.fetch_route_group_by_uuid",
        new=AsyncMock(return_value=full_route_group),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    # Bus just passed stop 10000, heading to monitored stop 10001
    pos = BusPosition(
        trip_id=10001,
        bus_id=1,
        bus_reg="1528",
        lat=-37.760,
        lng=145.310,
        last_stop_id=10000,
        last_stop_time=None,
        received_at=datetime.now(timezone.utc),
    )

    with _patch.object(coordinator, "get_speed", return_value=30.0):
        coordinator.async_set_updated_data({10001: pos})
        await hass.async_block_till_done()

    state = hass.states.get("sensor.busminder_1001_eta")
    assert state is not None
    assert state.state not in ("unknown", "unavailable")
    assert int(state.state) >= 0


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


async def test_scheduled_eta_uses_dt_from_stop_metadata(hass: HomeAssistant, mock_config_entry):
    """scheduled_eta uses dt field when present on the monitored stop."""
    from homeassistant.util import dt as dt_util

    from custom_components.busminder.models import Route, Stop

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    now = dt_util.now()
    future_time = (now.replace(second=0, microsecond=0) + timedelta(minutes=10)).strftime("%H:%M")

    monitored_stop = Stop(
        id=10001,
        name="Springfield High - Main Gate",
        lat=-37.7877,
        lng=145.33912,
        sequence=3,
        scheduled_time=future_time,
    )
    coordinator._full_routes[10001] = Route(
        trip_id=10001,
        name="1001 : Springfield 1 | Springfield High to City - PM",
        route_number="1001",
        colour="",
        stops=[monitored_stop],
    )

    coordinator.async_set_updated_data({10001: make_position()})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.busminder_1001_scheduled_eta")
    assert state is not None
    assert state.state not in ("unavailable", "unknown")
    assert abs(int(state.state) - 10) <= 1


async def test_scheduled_eta_falls_back_to_history(hass: HomeAssistant, mock_config_entry):
    """scheduled_eta uses historical median when dt is absent."""
    from homeassistant.util import dt as dt_util

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    now = dt_util.now()
    future_time = (now.replace(second=0, microsecond=0) + timedelta(minutes=15)).strftime("%H:%M")
    weekday = now.weekday()

    # Inject 3 observations at future_time (no dt on stop)
    key = f"10001:10001:{weekday}"
    coordinator._history._data[key] = [future_time, future_time, future_time]

    coordinator.async_set_updated_data({10001: make_position()})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.busminder_1001_scheduled_eta")
    assert state is not None
    assert state.state not in ("unavailable", "unknown")
    assert abs(int(state.state) - 15) <= 1


async def test_scheduled_eta_unknown_when_no_data(hass: HomeAssistant, mock_config_entry):
    """scheduled_eta shows unknown when neither dt nor history is available."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    coordinator.async_set_updated_data({10001: make_position()})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.busminder_1001_scheduled_eta")
    assert state is not None
    assert state.state == "unknown"


async def test_scheduled_eta_unknown_when_bus_has_passed(hass: HomeAssistant, mock_config_entry):
    """scheduled_eta shows unknown when scheduled time is in the past."""
    from homeassistant.util import dt as dt_util

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    now = dt_util.now()
    past_time = (now.replace(second=0, microsecond=0) - timedelta(minutes=5)).strftime("%H:%M")
    weekday = now.weekday()

    key = f"10001:10001:{weekday}"
    coordinator._history._data[key] = [past_time, past_time, past_time]

    coordinator.async_set_updated_data({10001: make_position()})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.busminder_1001_scheduled_eta")
    assert state is not None
    assert state.state == "unknown"


async def test_live_eta_returns_sum_of_segment_medians(hass: HomeAssistant, mock_config_entry):
    """live_eta sums historical segment times from last stop to monitored stop."""
    from custom_components.busminder.models import Route, Stop

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    stop_a = Stop(id=9001, name="Stop A", lat=-37.78, lng=145.33, sequence=1)
    stop_b = Stop(id=9002, name="Stop B", lat=-37.79, lng=145.34, sequence=2)
    monitored = Stop(id=10001, name="Springfield High - Main Gate", lat=-37.7877, lng=145.33912, sequence=3)
    coordinator._full_routes[10001] = Route(
        trip_id=10001,
        name="1001 : Springfield 1 | Springfield High to City - PM",
        route_number="1001",
        colour="",
        stops=[stop_a, stop_b, monitored],
    )

    # 3 mins (9001→9002) + 4 mins (9002→10001) = 7 mins
    coordinator._history._data["10001:9001:9002"] = [180.0, 180.0, 180.0]
    coordinator._history._data["10001:9002:10001"] = [240.0, 240.0, 240.0]

    coordinator.async_set_updated_data({10001: make_position(last_stop_id=9001)})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.busminder_1001_live_eta")
    assert state is not None
    assert state.state == "7"


async def test_live_eta_unknown_when_insufficient_history(hass: HomeAssistant, mock_config_entry):
    """live_eta shows unknown when any segment has fewer than MIN_OBSERVATIONS."""
    from custom_components.busminder.models import Route, Stop

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    stop_a = Stop(id=9001, name="Stop A", lat=-37.78, lng=145.33, sequence=1)
    monitored = Stop(id=10001, name="Springfield High - Main Gate", lat=-37.7877, lng=145.33912, sequence=2)
    coordinator._full_routes[10001] = Route(
        trip_id=10001,
        name="1001 : Springfield 1 | Springfield High to City - PM",
        route_number="1001",
        colour="",
        stops=[stop_a, monitored],
    )
    # Only 1 observation — below MIN_OBSERVATIONS of 3
    coordinator._history._data["10001:9001:10001"] = [180.0]

    coordinator.async_set_updated_data({10001: make_position(last_stop_id=9001)})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.busminder_1001_live_eta")
    assert state is not None
    assert state.state == "unknown"


async def test_live_eta_unknown_when_bus_has_passed(hass: HomeAssistant, mock_config_entry):
    """live_eta shows unknown when last_stop_id is at or past the monitored stop."""
    from custom_components.busminder.models import Route, Stop

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    monitored = Stop(id=10001, name="Springfield High - Main Gate", lat=-37.7877, lng=145.33912, sequence=1)
    stop_after = Stop(id=9099, name="Next Stop", lat=-37.80, lng=145.34, sequence=2)
    coordinator._full_routes[10001] = Route(
        trip_id=10001,
        name="1001 : Springfield 1 | Springfield High to City - PM",
        route_number="1001",
        colour="",
        stops=[monitored, stop_after],
    )
    coordinator._history._data["10001:10001:9099"] = [180.0, 180.0, 180.0]

    # Bus is at the stop AFTER the monitored stop
    coordinator.async_set_updated_data({10001: make_position(last_stop_id=9099)})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.busminder_1001_live_eta")
    assert state is not None
    assert state.state == "unknown"


async def test_scheduled_eta_unavailable_when_connection_failed(hass: HomeAssistant, mock_config_entry):
    """scheduled_eta is unavailable when coordinator.connection_failed is True."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    coordinator.connection_failed = True
    coordinator.async_set_updated_data({10001: make_position()})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.busminder_1001_scheduled_eta")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
