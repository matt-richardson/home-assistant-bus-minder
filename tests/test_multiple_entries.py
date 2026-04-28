"""Tests confirming two config entries don't interfere with each other."""

from datetime import datetime, timezone

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.busminder.const import (
    CONF_OPERATOR_URL,
    CONF_ROUTE_GROUP_NAME,
    CONF_ROUTE_GROUP_UUID,
    CONF_ROUTES,
    DOMAIN,
)
from custom_components.busminder.models import BusPosition


def make_entry(entry_id_suffix: str, trip_id: int, route_number: str, stop_id: int) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"aaaaaaaa-0000-4000-8000-00000000000{entry_id_suffix}",
        data={
            CONF_OPERATOR_URL: f"https://operator-{entry_id_suffix}.example.com/tracking/",
            CONF_ROUTE_GROUP_UUID: f"aaaaaaaa-0000-4000-8000-00000000000{entry_id_suffix}",
            CONF_ROUTE_GROUP_NAME: f"School {entry_id_suffix}",
            CONF_ROUTES: [
                {
                    "trip_id": trip_id,
                    "name": f"{route_number} : Route {route_number}",
                    "route_number": route_number,
                    "uuid": f"aaaaaaaa-0000-4000-8000-00000000000{entry_id_suffix}",
                    "stop_id": stop_id,
                    "stop_name": f"Stop {stop_id}",
                    "stop_lat": -37.800,
                    "stop_lng": 145.300,
                }
            ],
        },
    )


def make_position(trip_id: int) -> BusPosition:
    return BusPosition(
        trip_id=trip_id,
        bus_id=1,
        bus_reg="0042",
        lat=-37.820,
        lng=145.340,
        last_stop_id=None,
        last_stop_time=None,
        received_at=datetime.now(timezone.utc),
    )


async def setup_two_entries(hass: HomeAssistant):
    """Add and set up two independent config entries, returning (entry_a, entry_b)."""
    entry_a = make_entry("2", trip_id=20001, route_number="2001", stop_id=20001)
    entry_b = make_entry("3", trip_id=30001, route_number="3001", stop_id=30001)
    # Add and set up sequentially — adding both before either is set up causes HA to
    # auto-setup the second entry when the integration is first loaded for the first.
    entry_a.add_to_hass(hass)
    await hass.config_entries.async_setup(entry_a.entry_id)
    await hass.async_block_till_done()
    entry_b.add_to_hass(hass)
    await hass.config_entries.async_setup(entry_b.entry_id)
    await hass.async_block_till_done()
    return entry_a, entry_b


async def test_two_entries_register_separate_entities(hass: HomeAssistant):
    """Each config entry registers its own sensors and device trackers independently."""
    entry_a, entry_b = await setup_two_entries(hass)

    # Entry A entities exist
    assert hass.states.get("sensor.busminder_2001_eta") is not None
    assert hass.states.get("device_tracker.busminder_2001") is not None

    # Entry B entities exist
    assert hass.states.get("sensor.busminder_3001_eta") is not None
    assert hass.states.get("device_tracker.busminder_3001") is not None


async def test_two_entries_data_does_not_bleed_across(hass: HomeAssistant):
    """A position update for entry A does not affect entry B's sensors."""
    entry_a, entry_b = await setup_two_entries(hass)

    # Push a position update only to entry A's coordinator
    coordinator_a = entry_a.runtime_data
    coordinator_a.async_set_updated_data({20001: make_position(20001)})
    await hass.async_block_till_done()

    # Entry A's device tracker is now available (has position data)
    assert hass.states.get("device_tracker.busminder_2001").state != STATE_UNAVAILABLE

    # Entry B's device tracker remains unavailable (no data pushed to it)
    assert hass.states.get("device_tracker.busminder_3001").state == STATE_UNAVAILABLE


async def test_two_entries_unload_independently(hass: HomeAssistant):
    """Unloading entry A does not affect entry B's entities."""
    entry_a, entry_b = await setup_two_entries(hass)

    await hass.config_entries.async_unload(entry_a.entry_id)
    await hass.async_block_till_done()

    # Entry A's entities are gone / unavailable after unload
    state_a = hass.states.get("sensor.busminder_2001_eta")
    assert state_a is None or state_a.state == STATE_UNAVAILABLE

    # Entry B's entities are still present and intact
    assert hass.states.get("sensor.busminder_3001_eta") is not None
    assert hass.states.get("device_tracker.busminder_3001") is not None


async def test_two_entries_connection_failed_is_independent(hass: HomeAssistant):
    """connection_failed on entry A does not affect entry B's availability."""
    entry_a, entry_b = await setup_two_entries(hass)

    # Give entry B a position so its sensor is available
    coordinator_b = entry_b.runtime_data
    coordinator_b.async_set_updated_data({30001: make_position(30001)})
    await hass.async_block_till_done()

    # Mark entry A as connection-failed
    coordinator_a = entry_a.runtime_data
    coordinator_a.connection_failed = True
    coordinator_a.async_set_updated_data({20001: make_position(20001)})
    await hass.async_block_till_done()

    # Entry A's sensor is unavailable
    assert hass.states.get("device_tracker.busminder_2001").state == STATE_UNAVAILABLE

    # Entry B's sensor is still available
    assert hass.states.get("device_tracker.busminder_3001").state != STATE_UNAVAILABLE
