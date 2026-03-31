from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONF_ROUTES, DOMAIN
from .coordinator import BusMinderCoordinator

PLATFORMS = ["sensor", "device_tracker"]
PARALLEL_UPDATES = 1


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = BusMinderCoordinator(hass, entry)
    await coordinator.async_start()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: BusMinderCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry — called by the options flow update listener."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device: dr.DeviceEntry
) -> bool:
    """Allow removing a route device from the UI; strip it from config so it won't return."""
    # Device identifier format: (DOMAIN, "{entry_id}_{trip_id}")
    trip_id: int | None = None
    for domain, identifier in device.identifiers:
        if domain == DOMAIN:
            try:
                trip_id = int(identifier.rsplit("_", 1)[1])
            except (IndexError, ValueError):
                pass

    if trip_id is None:
        return False

    # Remove the route from the config entry so it isn't recreated on reload
    current_routes = list(entry.data.get(CONF_ROUTES, []))
    updated_routes = [r for r in current_routes if r["trip_id"] != trip_id]
    if len(updated_routes) != len(current_routes):
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_ROUTES: updated_routes}
        )

    return True
