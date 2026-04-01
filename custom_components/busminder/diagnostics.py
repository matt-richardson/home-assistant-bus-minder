"""BusMinder diagnostics platform."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_OPERATOR_URL
from .coordinator import BusMinderCoordinator

TO_REDACT = {CONF_OPERATOR_URL}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: BusMinderCoordinator = entry.runtime_data

    positions: dict[int, dict[str, Any]] = {}
    for trip_id, pos in (coordinator.data or {}).items():
        positions[trip_id] = {
            "lat": pos.lat,
            "lng": pos.lng,
            "bus_reg": pos.bus_reg,
        }

    return {
        "config": async_redact_data(entry.data, TO_REDACT),
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "connection_failed": coordinator.connection_failed,
            "monitored_routes": list(coordinator.monitored_trip_ids),
            "positions": positions,
        },
    }
