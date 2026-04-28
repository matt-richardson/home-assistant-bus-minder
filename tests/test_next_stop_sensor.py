from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from custom_components.busminder.models import BusPosition, Route, RouteGroup, Stop


def _route_group_with_stops() -> RouteGroup:
    """Route group where route 10001 has two ordered stops."""
    return RouteGroup(
        uuid="aaaaaaaa-0000-4000-8000-000000000001",
        name="Springfield High",
        routes=[
            Route(
                trip_id=10001,
                name="1001 : Springfield 1 | Springfield High to City - PM",
                route_number="1001",
                colour="",
                stops=[
                    Stop(id=10001, name="Springfield High - Main Gate", lat=-37.7877, lng=145.33912, sequence=1),
                    Stop(id=10002, name="Shelbyville Ave", lat=-37.800, lng=145.350, sequence=2),
                ],
            ),
            Route(
                trip_id=10002,
                name="1002 : Springfield 2 | Springfield High to City Station - PM",
                route_number="1002",
                colour="",
                stops=[
                    Stop(id=10001, name="Springfield High - Main Gate", lat=-37.7877, lng=145.33912, sequence=1),
                    Stop(id=10003, name="City Station", lat=-37.860, lng=145.295, sequence=2),
                ],
            ),
        ],
    )


def make_position(trip_id=10001, last_stop_id=10001):
    return BusPosition(
        trip_id=trip_id,
        bus_id=1,
        bus_reg="0042",
        lat=-37.820,
        lng=145.340,
        last_stop_id=last_stop_id,
        last_stop_time=None,
        received_at=datetime.now(timezone.utc),
    )


async def test_next_stop_sensor_registered(hass: HomeAssistant, mock_config_entry):
    """A next_stop sensor is registered for each monitored route."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.busminder_1001_next_stop") is not None
    assert hass.states.get("sensor.busminder_1002_next_stop") is not None


async def test_next_stop_sensor_unavailable_before_first_update(hass: HomeAssistant, mock_config_entry):
    """Next stop sensor is unavailable before any position data arrives."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.busminder_1001_next_stop")
    assert state.state == STATE_UNAVAILABLE


async def test_next_stop_sensor_shows_stop_name(hass: HomeAssistant, mock_config_entry):
    """Next stop sensor shows the name of the stop after the bus's last stop."""
    with patch(
        "custom_components.busminder.coordinator.fetch_route_group_by_uuid",
        new=AsyncMock(return_value=_route_group_with_stops()),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    # Bus just passed stop 10001 (Main Gate, seq=1) → next is 10002 (Shelbyville Ave, seq=2)
    coordinator.async_set_updated_data({10001: make_position(trip_id=10001, last_stop_id=10001)})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.busminder_1001_next_stop")
    assert state is not None
    assert state.state == "Shelbyville Ave"


async def test_next_stop_sensor_unknown_at_last_stop(hass: HomeAssistant, mock_config_entry):
    """Next stop sensor returns unknown when bus is at the last stop in the route."""
    with patch(
        "custom_components.busminder.coordinator.fetch_route_group_by_uuid",
        new=AsyncMock(return_value=_route_group_with_stops()),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    # Bus just passed stop 10002 (last stop) → no next stop
    coordinator.async_set_updated_data({10001: make_position(trip_id=10001, last_stop_id=10002)})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.busminder_1001_next_stop")
    assert state is not None
    assert state.state == "unknown"


async def test_next_stop_sensor_unavailable_when_connection_failed(hass: HomeAssistant, mock_config_entry):
    """Next stop sensor is unavailable when coordinator.connection_failed is True."""
    with patch(
        "custom_components.busminder.coordinator.fetch_route_group_by_uuid",
        new=AsyncMock(return_value=_route_group_with_stops()),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    coordinator.connection_failed = True
    coordinator.async_set_updated_data({10001: make_position()})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.busminder_1001_next_stop")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_next_stop_unknown_when_no_route_metadata(hass: HomeAssistant, mock_config_entry):
    """Next stop sensor returns unknown when route metadata could not be fetched."""
    # No patch — fetch_route_group_by_uuid will fail gracefully, _full_routes stays empty
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    coordinator.async_set_updated_data({10001: make_position()})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.busminder_1001_next_stop")
    assert state is not None
    assert state.state == "unknown"
