from __future__ import annotations

from typing import TypeAlias

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr

from .const import CONF_ROUTES, DOMAIN
from .coordinator import BusMinderCoordinator

BusMinderConfigEntry: TypeAlias = ConfigEntry[BusMinderCoordinator]

PLATFORMS = ["binary_sensor", "sensor", "device_tracker"]
PARALLEL_UPDATES = 1


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:  # pylint: disable=unused-argument
    """Migrate old config entry formats to current version."""
    if entry.version == 1:
        # v1 stored a single monitored stop at the top level; v2 stores stop info per-route.
        stop_id = entry.data.get("monitored_stop_id")
        stop_name = entry.data.get("monitored_stop_name", "")
        stop_lat = entry.data.get("monitored_stop_lat", 0.0)
        stop_lng = entry.data.get("monitored_stop_lng", 0.0)
        new_routes = [
            {**r, "stop_id": stop_id, "stop_name": stop_name, "stop_lat": stop_lat, "stop_lng": stop_lng}
            for r in entry.data.get(CONF_ROUTES, [])
        ]
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_ROUTES: new_routes},
            version=2,
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: BusMinderConfigEntry) -> bool:
    coordinator = BusMinderCoordinator(hass, entry)
    await coordinator.async_start()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    if not hass.services.has_service(DOMAIN, "reconnect"):

        async def _handle_reconnect(_call: ServiceCall) -> None:
            for loaded_entry in hass.config_entries.async_entries(DOMAIN):
                if loaded_entry.runtime_data:
                    await loaded_entry.runtime_data.async_reconnect()

        hass.services.async_register(DOMAIN, "reconnect", _handle_reconnect)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BusMinderConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_shutdown()
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: BusMinderConfigEntry) -> None:
    """Reload entry — called by the options flow update listener."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: BusMinderConfigEntry, device: dr.DeviceEntry
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

    # Remove the route from both data and options so it isn't recreated on reload.
    # The coordinator and options flow both use {**entry.data, **entry.options},
    # so a stale CONF_ROUTES in options would override a cleaned-up entry.data.
    new_data = {**entry.data, CONF_ROUTES: [r for r in entry.data.get(CONF_ROUTES, []) if r["trip_id"] != trip_id]}
    new_options = (
        {**entry.options, CONF_ROUTES: [r for r in entry.options.get(CONF_ROUTES, []) if r["trip_id"] != trip_id]}
        if CONF_ROUTES in entry.options
        else entry.options
    )
    hass.config_entries.async_update_entry(entry, data=new_data, options=new_options)

    return True
