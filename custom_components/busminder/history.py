from __future__ import annotations

import statistics
from datetime import datetime, time
from typing import Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

STORAGE_VERSION = 1
MIN_OBSERVATIONS = 3
MAX_OBSERVATIONS = 20


class HistoryStore:
    """Persists bus arrival and inter-stop segment observations across HA restarts."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store = Store(hass, STORAGE_VERSION, f"busminder_history_{entry_id}")
        self._data: dict[str, list] = {}

    async def async_load(self) -> None:
        stored = await self._store.async_load()
        self._data = stored or {}

    async def record_arrival(self, trip_id: int, stop_id: int, arrival_dt: datetime) -> None:
        """Record a bus arrival at stop_id. Stores local time-of-day keyed by weekday."""
        local_dt = dt_util.as_local(arrival_dt)
        key = f"{trip_id}:{stop_id}:{local_dt.weekday()}"
        time_str = local_dt.strftime("%H:%M")
        observations = list(self._data.get(key, []))
        observations.append(time_str)
        self._data[key] = observations[-MAX_OBSERVATIONS:]
        await self._store.async_save(self._data)

    async def record_segment(self, trip_id: int, from_stop_id: int, to_stop_id: int, elapsed_seconds: float) -> None:
        """Record travel time in seconds between two consecutive stops."""
        key = f"{trip_id}:{from_stop_id}:{to_stop_id}"
        observations = list(self._data.get(key, []))
        observations.append(elapsed_seconds)
        self._data[key] = observations[-MAX_OBSERVATIONS:]
        await self._store.async_save(self._data)

    def get_median_arrival(self, trip_id: int, stop_id: int, weekday: int) -> Optional[time]:
        """Return median historical arrival time for given weekday, or None if < MIN_OBSERVATIONS."""
        key = f"{trip_id}:{stop_id}:{weekday}"
        observations = self._data.get(key, [])
        if len(observations) < MIN_OBSERVATIONS:
            return None
        minutes = [int(t[:2]) * 60 + int(t[3:5]) for t in observations]
        median_mins = int(statistics.median(minutes))
        return time(hour=median_mins // 60, minute=median_mins % 60)

    def get_median_segment(self, trip_id: int, from_stop_id: int, to_stop_id: int) -> Optional[float]:
        """Return median segment travel time in seconds, or None if < MIN_OBSERVATIONS."""
        key = f"{trip_id}:{from_stop_id}:{to_stop_id}"
        observations = self._data.get(key, [])
        if len(observations) < MIN_OBSERVATIONS:
            return None
        return statistics.median(observations)

    def observation_count(self, key: str) -> int:
        return len(self._data.get(key, []))
