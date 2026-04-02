from __future__ import annotations

import asyncio
import logging
from typing import Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.issue_registry import IssueSeverity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_OPERATOR_URL, CONF_ROUTE_GROUP_UUID, CONF_ROUTES, DOMAIN
from .eta import SpeedTracker
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
        self.connection_failed: bool = False

        effective = {**entry.data, **entry.options}
        route_data = effective.get(CONF_ROUTES, [])
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
        for task in self._sse_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

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
                async for position in client.stream():
                    self._on_position(position)
                # Stream ended cleanly — treat as a transient failure to reconnect
                raise RuntimeError("SSE stream ended unexpectedly")
            except asyncio.CancelledError:  # pylint: disable=try-except-raise
                raise
            except Exception as exc:  # pylint: disable=broad-exception-caught
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

    def _on_position(self, pos: BusPosition) -> None:
        if pos.trip_id not in self._monitored_trip_ids:
            return

        # Reset failure tracking on successful data
        if self.connection_failed:
            self.connection_failed = False
            self._failure_count = 0
            self.async_update_listeners()
            ir.async_delete_issue(self.hass, DOMAIN, "connection_failed")

        self._speed_tracker.update(pos.trip_id, pos.lat, pos.lng, pos.received_at)

        new_data = dict(self.data or {})
        new_data[pos.trip_id] = pos
        self.async_set_updated_data(new_data)

    @property
    def monitored_trip_ids(self) -> set[int]:
        return self._monitored_trip_ids

    def get_speed(self, trip_id: int) -> Optional[float]:
        return self._speed_tracker.get_speed(trip_id)

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
