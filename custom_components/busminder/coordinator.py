from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time
from typing import Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.issue_registry import IssueSeverity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_OPERATOR_URL, CONF_ROUTE_GROUP_UUID, CONF_ROUTES, DOMAIN
from .eta import SpeedTracker, route_distance_km
from .history import HistoryStore
from .models import BusPosition, Route, Stop
from .scraper import fetch_route_group_by_uuid
from .signalr import SignalRClient

_LOGGER = logging.getLogger(__name__)

RECONNECT_THRESHOLD = 3


class BusMinderCoordinator(DataUpdateCoordinator[dict[int, BusPosition]]):
    """
    Push-based coordinator for BusMinder live bus positions.

    Does not poll. Calls async_set_updated_data() whenever a GPS event arrives
    from the SignalR SSE stream.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self._entry = entry
        self._sse_tasks: list[asyncio.Task] = []
        self._speed_tracker = SpeedTracker()
        self._failure_count: int = 0
        self.is_connected: bool = True
        self.connection_failed: bool = False

        self._history = HistoryStore(hass, entry.entry_id)
        self._prev_last_stop: dict[int, Optional[int]] = {}
        self._prev_last_stop_time: dict[int, Optional[datetime]] = {}
        self._monitored_stops: dict[int, int] = {}

        effective = {**entry.data, **entry.options}
        route_data = effective.get(CONF_ROUTES, [])
        fallback_uuid = effective.get(CONF_ROUTE_GROUP_UUID, "")
        self._monitored_routes: dict[int, Route] = {
            r["trip_id"]: Route(
                trip_id=r["trip_id"],
                name=r["name"],
                route_number=r["route_number"],
                colour="",
                stops=[],
            )
            for r in route_data
        }
        self._monitored_trip_ids: set[int] = set(self._monitored_routes.keys())
        self._full_routes: dict[int, Route] = {}
        self._uuid_to_trip_ids: dict[str, set[int]] = {}
        for r in route_data:
            uuid = r.get("uuid") or fallback_uuid
            if uuid:
                self._uuid_to_trip_ids.setdefault(uuid, set()).add(r["trip_id"])

        self.etas: dict[int, Optional[float]] = {}  # trip_id → minutes or None

    async def async_start(self) -> None:
        """Test connectivity then start one background SSE task per unique route group UUID."""
        effective = {**self._entry.data, **self._entry.options}
        operator_url = effective.get(CONF_OPERATOR_URL, "")
        session = async_get_clientsession(self.hass)
        try:
            async with asyncio.timeout(10):
                async with session.get(operator_url) as resp:
                    resp.raise_for_status()
        except Exception as exc:
            raise ConfigEntryNotReady(f"Cannot reach {operator_url}: {exc}") from exc

        await self._history.async_load()

        fallback_uuid = effective.get(CONF_ROUTE_GROUP_UUID, "")
        uuids = {
            r.get("uuid") or fallback_uuid for r in effective.get(CONF_ROUTES, []) if r.get("uuid") or fallback_uuid
        }
        for uuid in uuids:
            task = self.hass.async_create_background_task(self._run_sse(uuid), f"busminder_sse_{uuid}")
            self._sse_tasks.append(task)

        for uuid in uuids:
            try:
                group = await fetch_route_group_by_uuid(session, uuid)
                for route in group.routes:
                    self._full_routes[route.trip_id] = route
            except Exception:  # pylint: disable=broad-exception-caught
                _LOGGER.debug("BusMinder: could not fetch stop metadata for route group %s", uuid)

    async def async_shutdown(self) -> None:
        """Cancel all SSE tasks on unload."""
        await self._cancel_sse_tasks()

    async def async_reconnect(self) -> None:
        """Force-reconnect: cancel current SSE tasks and restart them."""
        await self._cancel_sse_tasks()

        self.is_connected = False
        self.connection_failed = False
        self._failure_count = 0
        self.async_update_listeners()
        ir.async_delete_issue(self.hass, DOMAIN, "connection_failed")

        effective = {**self._entry.data, **self._entry.options}
        fallback_uuid = effective.get(CONF_ROUTE_GROUP_UUID, "")
        uuids = {
            r.get("uuid") or fallback_uuid for r in effective.get(CONF_ROUTES, []) if r.get("uuid") or fallback_uuid
        }
        for uuid in uuids:
            task = self.hass.async_create_background_task(self._run_sse(uuid), f"busminder_sse_{uuid}")
            self._sse_tasks.append(task)

        _LOGGER.info("BusMinder: reconnect triggered, %d SSE task(s) restarted", len(self._sse_tasks))

    async def _cancel_sse_tasks(self) -> None:
        for task in self._sse_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._sse_tasks.clear()

    async def _run_sse(self, uuid: str) -> None:
        """Maintain the SSE connection for one route group UUID, reconnecting on error."""
        effective = {**self._entry.data, **self._entry.options}
        operator_url = effective.get(CONF_OPERATOR_URL, uuid)
        session = async_get_clientsession(self.hass)
        backoff = 5
        while True:
            try:
                client = SignalRClient(session, uuid)
                _LOGGER.info("BusMinder: connecting to route group %s", uuid)
                async for position in client.stream(
                    on_connected=lambda: self._on_sse_connected(uuid),
                    on_heartbeat=self._on_sse_heartbeat,
                ):
                    self._on_position(position)
                raise RuntimeError("SSE stream ended unexpectedly")
            except asyncio.CancelledError:  # pylint: disable=try-except-raise
                raise
            except Exception as exc:  # pylint: disable=broad-exception-caught
                if self.is_connected:
                    self.is_connected = False
                    self.async_update_listeners()
                self._failure_count += 1
                _LOGGER.warning(
                    "BusMinder SSE error (attempt %d, reconnecting in %ds): %s",
                    self._failure_count,
                    backoff,
                    exc,
                )
                if self._failure_count >= RECONNECT_THRESHOLD and not self.connection_failed:
                    self.connection_failed = True
                    self.async_update_listeners()
                    _LOGGER.warning(
                        "BusMinder: lost connection to %s after %d attempts, entities now unavailable",
                        operator_url,
                        self._failure_count,
                    )
                    ir.async_create_issue(
                        self.hass,
                        DOMAIN,
                        "connection_failed",
                        is_fixable=False,
                        severity=IssueSeverity.WARNING,
                        translation_key="connection_failed",
                        translation_placeholders={"operator_url": operator_url},
                    )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    def _on_sse_connected(self, uuid: str) -> None:
        """Called by SignalRClient when the SSE stream initializes successfully."""
        if not self.is_connected:
            self.is_connected = True
            self.async_update_listeners()
        trip_ids = self._uuid_to_trip_ids.get(uuid, set())
        if any(tid not in self._full_routes for tid in trip_ids):
            _LOGGER.debug("BusMinder: SSE connected for %s — route metadata missing, fetching now", uuid)
            self.hass.async_create_background_task(self._fetch_route_metadata(uuid), f"busminder_metadata_{uuid}")
        else:
            _LOGGER.debug("BusMinder: SSE connected for %s — route metadata already loaded", uuid)

    def _on_sse_heartbeat(self) -> None:
        """Called for every SSE data line received after init. Confirms the stream is alive."""
        if self.connection_failed:
            self.connection_failed = False
            self.async_update_listeners()
            ir.async_delete_issue(self.hass, DOMAIN, "connection_failed")
        self._failure_count = 0

    async def _fetch_route_metadata(self, uuid: str) -> None:
        """Fetch full route stop metadata for a route group; retried on each SSE reconnect."""
        session = async_get_clientsession(self.hass)
        try:
            group = await fetch_route_group_by_uuid(session, uuid)
            for route in group.routes:
                self._full_routes[route.trip_id] = route
            _LOGGER.debug("BusMinder: fetched stop metadata for route group %s", uuid)
        except Exception:  # pylint: disable=broad-exception-caught
            _LOGGER.debug("BusMinder: could not fetch stop metadata for route group %s", uuid)

    def _on_position(self, pos: BusPosition) -> None:
        if pos.trip_id not in self._monitored_trip_ids:
            return

        if self.connection_failed:
            self.connection_failed = False
            self._failure_count = 0
            self.async_update_listeners()
            ir.async_delete_issue(self.hass, DOMAIN, "connection_failed")

        self._speed_tracker.update(pos.trip_id, pos.lat, pos.lng, pos.received_at)

        prev_stop = self._prev_last_stop.get(pos.trip_id)
        prev_time = self._prev_last_stop_time.get(pos.trip_id)

        if pos.last_stop_id is not None and pos.last_stop_id != prev_stop:
            _LOGGER.debug(
                "BusMinder: trip %d stop transition %s→%s (last_stop_time=%s, full_route_loaded=%s)",
                pos.trip_id,
                prev_stop,
                pos.last_stop_id,
                pos.last_stop_time,
                pos.trip_id in self._full_routes,
            )
            if pos.last_stop_time is None:
                _LOGGER.debug("BusMinder: trip %d skipping record — last_stop_time is None", pos.trip_id)
            elif prev_stop is None or prev_time is None:
                _LOGGER.debug("BusMinder: trip %d skipping record — no previous stop data yet", pos.trip_id)
            elif pos.trip_id not in self._full_routes:
                _LOGGER.debug("BusMinder: trip %d skipping record — full route not loaded yet", pos.trip_id)
            elif not self._are_consecutive(pos.trip_id, prev_stop, pos.last_stop_id):
                _LOGGER.debug(
                    "BusMinder: trip %d skipping record — stops %d→%d are not consecutive in route",
                    pos.trip_id,
                    prev_stop,
                    pos.last_stop_id,
                )
            else:
                elapsed_s = (pos.last_stop_time - prev_time).total_seconds()
                if elapsed_s > 0:
                    _LOGGER.debug(
                        "BusMinder: trip %d recording segment %d→%d (%.0fs)",
                        pos.trip_id,
                        prev_stop,
                        pos.last_stop_id,
                        elapsed_s,
                    )
                    self.hass.async_create_task(
                        self._history.record_segment(pos.trip_id, prev_stop, pos.last_stop_id, elapsed_s)
                    )
                monitored = self._monitored_stops.get(pos.trip_id)
                if monitored is not None and pos.last_stop_id == monitored:
                    _LOGGER.debug(
                        "BusMinder: trip %d recording arrival at monitored stop %d",
                        pos.trip_id,
                        monitored,
                    )
                    self.hass.async_create_task(
                        self._history.record_arrival(pos.trip_id, pos.last_stop_id, pos.last_stop_time)
                    )

        if pos.last_stop_id is not None and pos.last_stop_time is not None:
            self._prev_last_stop[pos.trip_id] = pos.last_stop_id
            self._prev_last_stop_time[pos.trip_id] = pos.last_stop_time

        new_data = dict(self.data or {})
        new_data[pos.trip_id] = pos
        self.async_set_updated_data(new_data)

    def _are_consecutive(self, trip_id: int, from_stop_id: int, to_stop_id: int) -> bool:
        route = self._full_routes.get(trip_id)
        if not route:
            return False
        stops = sorted(route.stops, key=lambda s: s.sequence)
        stop_ids = [s.id for s in stops]
        try:
            from_idx = stop_ids.index(from_stop_id)
            to_idx = stop_ids.index(to_stop_id)
            return to_idx == from_idx + 1
        except ValueError:
            return False

    @property
    def monitored_trip_ids(self) -> set[int]:
        return self._monitored_trip_ids

    def register_monitored_stop(self, trip_id: int, stop_id: int) -> None:
        self._monitored_stops[trip_id] = stop_id

    def get_scheduled_arrival(self, trip_id: int, stop_id: int, weekday: int) -> Optional[time]:
        return self._history.get_median_arrival(trip_id, stop_id, weekday)

    def get_live_eta_seconds(self, trip_id: int, last_stop_id: int, monitored_stop_id: int) -> Optional[float]:
        route = self._full_routes.get(trip_id)
        if not route:
            return None
        stops = sorted(route.stops, key=lambda s: s.sequence)
        stop_ids = [s.id for s in stops]
        try:
            last_idx = stop_ids.index(last_stop_id)
            monitored_idx = stop_ids.index(monitored_stop_id)
        except ValueError:
            return None
        if last_idx >= monitored_idx:
            return None
        total = 0.0
        for i in range(last_idx, monitored_idx):
            segment = self._history.get_median_segment(trip_id, stop_ids[i], stop_ids[i + 1])
            if segment is None:
                return None
            total += segment
        return total

    def get_full_route(self, trip_id: int) -> Optional[Route]:
        """Return the full route (with all stops) fetched at startup, or None if unavailable."""
        return self._full_routes.get(trip_id)

    def get_route_distance_km(self, trip_id: int, bus: BusPosition, monitored_stop: Stop) -> Optional[float]:
        """Return along-route distance from bus to monitored stop, or None if route data unavailable."""
        route = self._full_routes.get(trip_id)
        if not route:
            return None
        return route_distance_km(bus, route, monitored_stop)

    def get_speed(self, trip_id: int) -> Optional[float]:
        return self._speed_tracker.get_speed(trip_id)

    def get_stops_until(self, trip_id: int, last_stop_id: int, monitored_stop_id: int) -> Optional[int]:
        """Return the number of stops remaining until the monitored stop (inclusive), or None."""
        route = self._full_routes.get(trip_id)
        if not route:
            return None
        stops = sorted(route.stops, key=lambda s: s.sequence)
        stop_ids = [s.id for s in stops]
        try:
            last_idx = stop_ids.index(last_stop_id)
            monitored_idx = stop_ids.index(monitored_stop_id)
        except ValueError:
            return None
        if last_idx >= monitored_idx:
            return None
        return monitored_idx - last_idx

    def get_next_stop(self, trip_id: int, last_stop_id: int) -> Optional[Stop]:
        """Return the stop immediately after last_stop_id in the route sequence, or None."""
        route = self._full_routes.get(trip_id)
        if not route:
            return None
        stops = sorted(route.stops, key=lambda s: s.sequence)
        stop_ids = [s.id for s in stops]
        try:
            idx = stop_ids.index(last_stop_id)
        except ValueError:
            return None
        if idx + 1 >= len(stops):
            return None
        return stops[idx + 1]
