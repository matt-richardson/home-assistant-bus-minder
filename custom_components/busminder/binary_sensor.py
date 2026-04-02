from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ROUTES
from .coordinator import BusMinderCoordinator
from .entity import BusMinderEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,  # pylint: disable=unused-argument
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: BusMinderCoordinator = entry.runtime_data
    effective = {**entry.data, **entry.options}
    entities = [
        BusConnectedSensor(coordinator, entry, r["trip_id"], r["route_number"], r.get("custom_route_name") or r["name"])
        for r in effective.get(CONF_ROUTES, [])
    ]
    async_add_entities(entities)


class BusConnectedSensor(BusMinderEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "connected"

    def __init__(
        self,
        coordinator: BusMinderCoordinator,
        entry: ConfigEntry,
        trip_id: int,
        route_number: str,
        route_name: str,
    ) -> None:
        super().__init__(coordinator, entry, trip_id, route_number, route_name)
        self._attr_unique_id = f"{entry.entry_id}_{trip_id}_connected"
        self.entity_id = f"binary_sensor.busminder_{route_number.lower()}_connected"

    @property
    def is_on(self) -> bool:
        return not self.coordinator.connection_failed

    @property
    def available(self) -> bool:
        return True
