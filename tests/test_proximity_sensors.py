from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from custom_components.busminder.models import BusPosition, Route, RouteGroup, Stop


def _route_group_with_stops() -> RouteGroup:
    """Route group where route 10001 has three ordered stops."""
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
                    Stop(id=10000, name="Depot", lat=-37.760, lng=145.310, sequence=1),
                    Stop(id=10001, name="Springfield High - Main Gate", lat=-37.7877, lng=145.33912, sequence=2),
                    Stop(id=10002, name="Shelbyville Ave", lat=-37.800, lng=145.350, sequence=3),
                ],
            ),
        ],
    )


def make_position(trip_id=10001, lat=-37.770, lng=145.320, last_stop_id=10000):
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


# --- stops_away sensor ---


async def test_stops_away_sensor_registered(hass: HomeAssistant, mock_config_entry):
    """A stops_away sensor is registered for each monitored route."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.busminder_1001_stops_away") is not None
    assert hass.states.get("sensor.busminder_1002_stops_away") is not None


async def test_stops_away_unavailable_before_first_update(hass: HomeAssistant, mock_config_entry):
    """stops_away sensor is unavailable before any position data arrives."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.busminder_1001_stops_away").state == STATE_UNAVAILABLE


async def test_stops_away_shows_count(hass: HomeAssistant, mock_config_entry):
    """stops_away returns the number of stops between bus and monitored stop (inclusive)."""
    with patch(
        "custom_components.busminder.coordinator.fetch_route_group_by_uuid",
        new=AsyncMock(return_value=_route_group_with_stops()),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    # Bus just passed stop 10000 (Depot, seq=1); monitored stop is 10001 (Main Gate, seq=2)
    coordinator.async_set_updated_data({10001: make_position(last_stop_id=10000)})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.busminder_1001_stops_away")
    assert state is not None
    assert state.state == "1"


async def test_stops_away_unknown_when_bus_passed(hass: HomeAssistant, mock_config_entry):
    """stops_away returns unknown once the bus has passed the monitored stop."""
    with patch(
        "custom_components.busminder.coordinator.fetch_route_group_by_uuid",
        new=AsyncMock(return_value=_route_group_with_stops()),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    # Bus just passed the monitored stop 10001 → already passed
    coordinator.async_set_updated_data({10001: make_position(last_stop_id=10001)})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.busminder_1001_stops_away")
    assert state is not None
    assert state.state == "unknown"


async def test_stops_away_unavailable_when_connection_failed(hass: HomeAssistant, mock_config_entry):
    """stops_away sensor is unavailable when coordinator.connection_failed is True."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    coordinator.connection_failed = True
    coordinator.async_set_updated_data({10001: make_position()})
    await hass.async_block_till_done()

    assert hass.states.get("sensor.busminder_1001_stops_away").state == STATE_UNAVAILABLE


# --- distance sensor ---


async def test_distance_sensor_registered(hass: HomeAssistant, mock_config_entry):
    """A distance sensor is registered for each monitored route."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.busminder_1001_distance") is not None
    assert hass.states.get("sensor.busminder_1002_distance") is not None


async def test_distance_sensor_unavailable_before_first_update(hass: HomeAssistant, mock_config_entry):
    """Distance sensor is unavailable before any position data arrives."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.busminder_1001_distance").state == STATE_UNAVAILABLE


async def test_distance_sensor_shows_km(hass: HomeAssistant, mock_config_entry):
    """Distance sensor shows straight-line km from bus to monitored stop."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    # Bus at (-37.820, 145.340); monitored stop for route 10001 is (-37.7877, 145.33912)
    coordinator.async_set_updated_data({10001: make_position(lat=-37.820, lng=145.340)})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.busminder_1001_distance")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert float(state.state) > 0


async def test_distance_sensor_unavailable_when_connection_failed(hass: HomeAssistant, mock_config_entry):
    """Distance sensor is unavailable when coordinator.connection_failed is True."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    coordinator.connection_failed = True
    coordinator.async_set_updated_data({10001: make_position()})
    await hass.async_block_till_done()

    assert hass.states.get("sensor.busminder_1001_distance").state == STATE_UNAVAILABLE
