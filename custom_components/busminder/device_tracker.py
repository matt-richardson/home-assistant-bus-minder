from __future__ import annotations

import logging
from typing import Optional

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_ROUTES
from .coordinator import BusMinderCoordinator
from .models import BusPosition

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: BusMinderCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        BusTrackerEntity(coordinator, entry, r["trip_id"], r["route_number"])
        for r in entry.data.get(CONF_ROUTES, [])
    ]
    async_add_entities(entities)


class BusTrackerEntity(CoordinatorEntity[BusMinderCoordinator], TrackerEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BusMinderCoordinator,
        entry: ConfigEntry,
        trip_id: int,
        route_number: str,
    ) -> None:
        super().__init__(coordinator)
        self._trip_id = trip_id
        self._route_number = route_number
        self._attr_unique_id = f"{entry.entry_id}_{trip_id}_tracker"
        self._attr_name = f"BusMinder {route_number}"
        self.entity_id = f"device_tracker.busminder_{route_number.lower()}"

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def latitude(self) -> Optional[float]:
        pos = self._get_position()
        return pos.lat if pos else None

    @property
    def longitude(self) -> Optional[float]:
        pos = self._get_position()
        return pos.lng if pos else None

    @property
    def battery_level(self) -> None:
        return None

    @property
    def location_accuracy(self) -> int:
        return 50  # metres (estimated GPS accuracy for a moving bus)

    @property
    def extra_state_attributes(self) -> dict:
        pos = self._get_position()
        if pos is None:
            return {}
        return {
            "bus_number": pos.bus_reg,
            "last_stop_id": pos.last_stop_id,
        }

    def _get_position(self) -> Optional[BusPosition]:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._trip_id)
