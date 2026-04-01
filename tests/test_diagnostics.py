from datetime import datetime, timezone

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from custom_components.busminder.diagnostics import async_get_config_entry_diagnostics
from custom_components.busminder.models import BusPosition


def make_position(trip_id=10001):
    return BusPosition(
        trip_id=trip_id,
        bus_id=1,
        bus_reg="1528",
        lat=-37.820,
        lng=145.340,
        last_stop_id=10001,
        last_stop_time=None,
        received_at=datetime.now(timezone.utc),
    )


async def test_diagnostics_redacts_operator_url(hass: HomeAssistant, mock_config_entry):
    """operator_url is redacted in diagnostics output."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert result["config"]["operator_url"] == REDACTED


async def test_diagnostics_includes_coordinator_state(hass: HomeAssistant, mock_config_entry):
    """Diagnostics includes coordinator state."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert "coordinator" in result
    assert "last_update_success" in result["coordinator"]
    assert "monitored_routes" in result["coordinator"]
    assert "positions" in result["coordinator"]


async def test_diagnostics_includes_position_data(hass: HomeAssistant, mock_config_entry):
    """Diagnostics includes current bus positions."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data["busminder"][mock_config_entry.entry_id]
    coordinator.async_set_updated_data({10001: make_position(10001)})
    await hass.async_block_till_done()

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert 10001 in result["coordinator"]["positions"]
    pos = result["coordinator"]["positions"][10001]
    assert "lat" in pos
    assert "lng" in pos
    assert "bus_reg" in pos


async def test_diagnostics_non_sensitive_fields_present(hass: HomeAssistant, mock_config_entry):
    """Non-sensitive config fields are not redacted."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    # Route group UUID and name are useful for diagnostics, not sensitive
    assert result["config"]["route_group_uuid"] == "aaaaaaaa-0000-4000-8000-000000000001"
