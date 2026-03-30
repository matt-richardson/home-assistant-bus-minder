from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    CONF_ROUTE_GROUP_UUID,
    CONF_ROUTES,
    CONF_MONITORED_STOP_ID,
    CONF_MONITORED_STOP_LAT,
    CONF_MONITORED_STOP_LNG,
    CONF_MONITORED_STOP_NAME,
)
from .eta import SpeedTracker, estimate_eta
from .models import BusPosition, Route, Stop
from .signalr import SignalRClient

_LOGGER = logging.getLogger(__name__)


class BusMinderCoordinator(DataUpdateCoordinator[dict[int, BusPosition]]):
    """
    Push-based coordinator for BusMinder live bus positions.

    Does not poll. Calls async_set_updated_data() whenever a GPS event arrives
    from the SignalR SSE stream.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self._entry = entry
        self._sse_task: Optional[asyncio.Task] = None
        self._speed_tracker = SpeedTracker()

        route_data = entry.data.get(CONF_ROUTES, [])
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

        self._monitored_stop = Stop(
            id=entry.data[CONF_MONITORED_STOP_ID],
            name=entry.data[CONF_MONITORED_STOP_NAME],
            lat=entry.data[CONF_MONITORED_STOP_LAT],
            lng=entry.data[CONF_MONITORED_STOP_LNG],
            sequence=0,
        )

        self.etas: dict[int, Optional[float]] = {}  # trip_id → minutes or None

    async def async_start(self) -> None:
        """Start the background SSE task."""
        self._sse_task = self.hass.async_create_background_task(
            self._run_sse(), "busminder_sse"
        )

    async def async_shutdown(self) -> None:
        """Cancel the SSE task on unload."""
        if self._sse_task and not self._sse_task.done():
            self._sse_task.cancel()
            try:
                await self._sse_task
            except asyncio.CancelledError:
                pass

    async def _run_sse(self) -> None:
        """Maintain the SSE connection, reconnecting on error."""
        uuid = self._entry.data[CONF_ROUTE_GROUP_UUID]
        backoff = 5
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    client = SignalRClient(session, uuid)
                    _LOGGER.info("BusMinder: connecting to route group %s", uuid)
                    async for position in client.stream():
                        self._on_position(position)
                    backoff = 5
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _LOGGER.warning("BusMinder SSE error (reconnecting in %ds): %s", backoff, exc)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    def _on_position(self, pos: BusPosition) -> None:
        if pos.trip_id not in self._monitored_trip_ids:
            return

        self._speed_tracker.update(pos.trip_id, pos.lat, pos.lng, pos.received_at)

        new_data = dict(self.data or {})
        new_data[pos.trip_id] = pos
        self.async_set_updated_data(new_data)

    def get_speed(self, trip_id: int) -> Optional[float]:
        return self._speed_tracker.get_speed(trip_id)
