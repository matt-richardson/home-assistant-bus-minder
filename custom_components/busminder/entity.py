"""Base entity for BusMinder."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_OPERATOR_URL, DOMAIN
from .coordinator import BusMinderCoordinator


class BusMinderEntity(CoordinatorEntity[BusMinderCoordinator]):
    """Base entity providing shared device_info for all BusMinder entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BusMinderCoordinator,
        entry: ConfigEntry,
        trip_id: int,
        _route_number: str,
        route_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._trip_id = trip_id
        effective = {**entry.data, **entry.options}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{trip_id}")},
            name=route_name,
            manufacturer="BusMinder",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=effective.get(CONF_OPERATOR_URL),
        )
