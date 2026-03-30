from __future__ import annotations

import math
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Optional

from .models import BusPosition, Route, Stop


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Straight-line distance between two lat/lng points in kilometres."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def estimate_eta(
    bus: BusPosition,
    route: Route,
    monitored_stop: Stop,
    speed_kmh: Optional[float],
) -> Optional[timedelta]:
    """
    Estimate time until `bus` reaches `monitored_stop` on `route`.

    Returns None if:
    - The bus has already passed the monitored stop
    - The bus's last stop is not found in the route (can't determine position in sequence)
    - speed_kmh is None or zero
    """
    stop_ids = [s.id for s in route.stops]

    try:
        monitored_idx = stop_ids.index(monitored_stop.id)
    except ValueError:
        return None  # monitored stop not in this route

    if bus.last_stop_id is None:
        return None

    try:
        last_stop_idx = stop_ids.index(bus.last_stop_id)
    except ValueError:
        return None  # bus's last stop not in this route — can't determine sequence position

    if last_stop_idx >= monitored_idx:
        return None  # bus has passed or is at the monitored stop

    if not speed_kmh or speed_kmh <= 0:
        return None

    distance = haversine_km(bus.lat, bus.lng, monitored_stop.lat, monitored_stop.lng)
    hours = distance / speed_kmh
    return timedelta(hours=hours)


class SpeedTracker:
    """
    Estimates speed per trip from consecutive GPS positions.
    Keeps the last 3 position samples per trip for a rolling estimate.
    """

    def __init__(self) -> None:
        # trip_id → deque of (datetime, lat, lng)
        self._history: dict[int, deque[tuple[datetime, float, float]]] = {}

    def update(self, trip_id: int, lat: float, lng: float, received_at: datetime) -> None:
        if trip_id not in self._history:
            self._history[trip_id] = deque(maxlen=3)
        self._history[trip_id].append((received_at, lat, lng))

    def get_speed(self, trip_id: int) -> Optional[float]:
        """Return estimated speed in km/h, or None if insufficient data."""
        history = self._history.get(trip_id)
        if not history or len(history) < 2:
            return None

        speeds = []
        items = list(history)
        for i in range(1, len(items)):
            t0, lat0, lng0 = items[i - 1]
            t1, lat1, lng1 = items[i]
            dt_s = (t1 - t0).total_seconds()
            if dt_s < 1:
                continue
            dist_km = haversine_km(lat0, lng0, lat1, lng1)
            speeds.append((dist_km / dt_s) * 3600)

        return sum(speeds) / len(speeds) if speeds else None
