"""Tests for the BusMinder connectivity binary sensor."""

from datetime import datetime, timezone

from homeassistant.core import HomeAssistant

from custom_components.busminder.models import BusPosition


def make_position(trip_id=10001):
    return BusPosition(
        trip_id=trip_id,
        bus_id=1,
        bus_reg="1528",
        lat=-37.820,
        lng=145.340,
        last_stop_id=None,
        last_stop_time=None,
        received_at=datetime.now(timezone.utc),
    )


async def test_connected_sensor_registered(hass: HomeAssistant, mock_config_entry):
    """A connected sensor is registered for each monitored route."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.busminder_1001_connected") is not None
    assert hass.states.get("binary_sensor.busminder_1002_connected") is not None


async def test_connected_sensor_on_by_default(hass: HomeAssistant, mock_config_entry):
    """Connected sensor starts as 'on' — the connectivity check passed to reach setup."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.busminder_1001_connected").state == "on"


async def test_connected_sensor_off_when_connection_failed(hass: HomeAssistant, mock_config_entry):
    """Connected sensor goes 'off' when coordinator.connection_failed is True."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    coordinator.connection_failed = True
    coordinator.async_set_updated_data({10001: make_position()})
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.busminder_1001_connected").state == "off"


async def test_connected_sensor_recovers(hass: HomeAssistant, mock_config_entry):
    """Connected sensor returns to 'on' when connection_failed is cleared."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    coordinator.connection_failed = True
    coordinator.async_set_updated_data({10001: make_position()})
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.busminder_1001_connected").state == "off"

    coordinator.connection_failed = False
    coordinator.async_set_updated_data({10001: make_position()})
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.busminder_1001_connected").state == "on"


async def test_connected_sensor_never_unavailable(hass: HomeAssistant, mock_config_entry):
    """Connected sensor is never unavailable — it always reports a state."""
    from homeassistant.const import STATE_UNAVAILABLE

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Even with connection_failed and no position data, it should report a state
    coordinator = mock_config_entry.runtime_data
    coordinator.connection_failed = True
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.busminder_1001_connected").state != STATE_UNAVAILABLE
