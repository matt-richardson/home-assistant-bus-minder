from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ROUTES
from .coordinator import BusMinderCoordinator
from .entity import BusMinderEntity
from .eta import estimate_eta, haversine_km
from .models import BusPosition, Route, Stop

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

NOT_RUNNING_THRESHOLD_S = 300  # 5 minutes without update → "not_running"


async def async_setup_entry(
    hass: HomeAssistant,  # pylint: disable=unused-argument
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: BusMinderCoordinator = entry.runtime_data

    effective = {**entry.data, **entry.options}

    entities: list[SensorEntity] = []
    for route_data in effective.get(CONF_ROUTES, []):
        stop = Stop(
            id=route_data["stop_id"],
            name=route_data.get("custom_stop_name") or route_data["stop_name"],
            lat=route_data["stop_lat"],
            lng=route_data["stop_lng"],
            sequence=0,
        )
        route = Route(
            trip_id=route_data["trip_id"],
            name=route_data.get("custom_route_name") or route_data["name"],
            route_number=route_data["route_number"],
            colour="",
            stops=[stop],
        )
        entities.append(BusEtaSensor(coordinator, entry, route, stop))
        entities.append(BusNextStopSensor(coordinator, entry, route))
        entities.append(BusStopsToStopSensor(coordinator, entry, route, stop))
        entities.append(BusDistanceSensor(coordinator, entry, route, stop))

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
        # Use the full route (with all stops) if available — needed so estimate_eta
        # can locate the bus's last_stop_id in the stop sequence.
        route = self.coordinator.get_full_route(self._route.trip_id) or self._route
        eta = estimate_eta(pos, route, self._monitored_stop, speed)
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
            route = self.coordinator.get_full_route(self._route.trip_id) or self._route
            eta = estimate_eta(pos, route, self._monitored_stop, speed)
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


class BusNextStopSensor(BusMinderEntity, SensorEntity):
    _attr_translation_key = "next_stop"

    def __init__(
        self,
        coordinator: BusMinderCoordinator,
        entry: ConfigEntry,
        route: Route,
    ) -> None:
        super().__init__(coordinator, entry, route.trip_id, route.route_number, route.name)
        self._route = route
        self._attr_unique_id = f"{entry.entry_id}_{route.trip_id}_next_stop"
        self.entity_id = f"sensor.busminder_{route.route_number.lower()}_next_stop"

    @property
    def native_value(self) -> Optional[str]:
        pos = self._get_position()
        if pos is None or pos.last_stop_id is None:
            return None
        next_stop = self.coordinator.get_next_stop(self._route.trip_id, pos.last_stop_id)
        return next_stop.name if next_stop else None

    @property
    def available(self) -> bool:
        if self.coordinator.connection_failed:
            return False
        return self.coordinator.last_update_success and self._get_position() is not None

    def _get_position(self) -> Optional[BusPosition]:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._route.trip_id)


class BusStopsToStopSensor(BusMinderEntity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "stops_away"

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
        self._attr_unique_id = f"{entry.entry_id}_{route.trip_id}_stops_away"
        self.entity_id = f"sensor.busminder_{route.route_number.lower()}_stops_away"

    @property
    def native_value(self) -> Optional[int]:
        pos = self._get_position()
        if pos is None or pos.last_stop_id is None:
            return None
        return self.coordinator.get_stops_until(self._route.trip_id, pos.last_stop_id, self._monitored_stop.id)

    @property
    def available(self) -> bool:
        if self.coordinator.connection_failed:
            return False
        return self.coordinator.last_update_success and self._get_position() is not None

    def _get_position(self) -> Optional[BusPosition]:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._route.trip_id)


class BusDistanceSensor(BusMinderEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1
    _attr_translation_key = "distance"

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
        self._attr_unique_id = f"{entry.entry_id}_{route.trip_id}_distance"
        self.entity_id = f"sensor.busminder_{route.route_number.lower()}_distance"

    @property
    def native_value(self) -> Optional[float]:
        pos = self._get_position()
        if pos is None:
            return None
        distance = self.coordinator.get_route_distance_km(self._route.trip_id, pos, self._monitored_stop)
        if distance is None:
            # Fall back to straight-line distance when route metadata is unavailable
            distance = haversine_km(pos.lat, pos.lng, self._monitored_stop.lat, self._monitored_stop.lng)
        return round(distance, 2)

    @property
    def available(self) -> bool:
        if self.coordinator.connection_failed:
            return False
        return self.coordinator.last_update_success and self._get_position() is not None

    def _get_position(self) -> Optional[BusPosition]:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._route.trip_id)
