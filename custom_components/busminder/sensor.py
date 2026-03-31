from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import (
    DOMAIN,
    CONF_ROUTES,
    CONF_MONITORED_STOP_ID,
    CONF_MONITORED_STOP_NAME,
    CONF_MONITORED_STOP_LAT,
    CONF_MONITORED_STOP_LNG,
)
from .coordinator import BusMinderCoordinator
from .entity import BusMinderEntity
from .eta import estimate_eta
from .models import BusPosition, Route, Stop

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

NOT_RUNNING_THRESHOLD_S = 300  # 5 minutes without update → "not_running"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: BusMinderCoordinator = hass.data[DOMAIN][entry.entry_id]

    effective = {**entry.data, **entry.options}

    monitored_stop = Stop(
        id=effective[CONF_MONITORED_STOP_ID],
        name=effective[CONF_MONITORED_STOP_NAME],
        lat=effective[CONF_MONITORED_STOP_LAT],
        lng=effective[CONF_MONITORED_STOP_LNG],
        sequence=0,
    )

    entities = []
    for route_data in effective.get(CONF_ROUTES, []):
        route = Route(
            trip_id=route_data["trip_id"],
            name=route_data["name"],
            route_number=route_data["route_number"],
            colour="",
            stops=[monitored_stop],  # enough for ETA calculation
        )
        entities.append(BusEtaSensor(coordinator, entry, route, monitored_stop))

    async_add_entities(entities)


class BusEtaSensor(BusMinderEntity, SensorEntity):
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "eta"

    def __init__(
        self,
        coordinator: BusMinderCoordinator,
        entry: ConfigEntry,
        route: Route,
        monitored_stop: Stop,
    ) -> None:
        super().__init__(coordinator, entry, route.trip_id, route.route_number, route.name)
        self._route = route
        self._monitored_stop = monitored_stop
        self._attr_unique_id = f"{entry.entry_id}_{route.trip_id}_eta"
        self.entity_id = f"sensor.busminder_{route.route_number.lower()}_eta"

    @property
    def native_value(self) -> Optional[int]:
        pos = self._get_position()
        if pos is None:
            return None
        speed = self.coordinator.get_speed(self._route.trip_id)
        eta = estimate_eta(pos, self._route, self._monitored_stop, speed)
        if eta is None:
            return None
        return max(0, round(eta.total_seconds() / 60))

    @property
    def available(self) -> bool:
        if self.coordinator.connection_failed:
            return False
        return self.coordinator.last_update_success and self._get_position() is not None

    @property
    def extra_state_attributes(self) -> dict:
        pos = self._get_position()
        if pos is None:
            return {"status": "not_running"}

        age_s = (datetime.now(timezone.utc) - pos.received_at).total_seconds()
        if age_s > NOT_RUNNING_THRESHOLD_S:
            status = "not_running"
        else:
            speed = self.coordinator.get_speed(self._route.trip_id)
            eta = estimate_eta(pos, self._route, self._monitored_stop, speed)
            status = "approaching" if eta is not None else "passed"

        return {
            "bus_number": pos.bus_reg,
            "latitude": pos.lat,
            "longitude": pos.lng,
            "last_updated": pos.received_at.isoformat(),
            "status": status,
        }

    def _get_position(self) -> Optional[BusPosition]:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._route.trip_id)
