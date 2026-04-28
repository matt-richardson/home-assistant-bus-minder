from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def decode_polyline_last_point(encoded: str) -> Optional[tuple[float, float]]:
    """Decode a Google encoded polyline, return the last (lat, lng) point."""
    if not encoded:
        return None
    index, lat, lng, last = 0, 0, 0, None
    while index < len(encoded):
        for is_lng in (False, True):
            result, shift = 0, 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if is_lng:
                lng += delta
                last = (lat / 1e5, lng / 1e5)
            else:
                lat += delta
    return last


@dataclass
class Stop:
    id: int
    name: str
    lat: float
    lng: float
    sequence: int
    scheduled_time: Optional[str] = None

    @classmethod
    def from_metadata(cls, data: dict) -> "Stop":
        pos = decode_polyline_last_point(data["position"])
        lat, lng = pos if pos else (0.0, 0.0)
        return cls(
            id=data["id"],
            name=data["name"],
            lat=lat,
            lng=lng,
            sequence=data.get("num", 0),
            scheduled_time=data.get("dt"),
        )


@dataclass
class Route:
    trip_id: int
    name: str
    route_number: str
    colour: str
    uuid: str = ""
    stops: list[Stop] = field(default_factory=list)

    @classmethod
    def from_metadata(cls, data: dict, uuid: str = "") -> "Route":
        name = data.get("name", "")
        # Route names use either " : " or " - " as the separator before the description
        # e.g. "3427 : Billanook 3 | ..." or "3427 - Billanook 3 | ..."
        for sep in (" : ", " - "):
            if sep in name:
                route_number = name.split(sep)[0].strip()
                break
        else:
            route_number = name
        stops = [Stop.from_metadata(s) for s in data.get("stops", [])]
        return cls(
            trip_id=data["id"],
            name=name,
            route_number=route_number,
            colour=data.get("colour", "#000000"),
            uuid=uuid,
            stops=stops,
        )


@dataclass
class RouteGroup:
    uuid: str
    name: str
    routes: list[Route] = field(default_factory=list)

    def all_stops(self) -> list[Stop]:
        """Return deduplicated stops across all routes, ordered by name."""
        seen: dict[int, Stop] = {}
        for route in self.routes:
            for stop in route.stops:
                seen[stop.id] = stop
        return sorted(seen.values(), key=lambda s: s.name)


@dataclass
class BusPosition:
    trip_id: int
    bus_id: int
    bus_reg: str
    lat: float
    lng: float
    last_stop_id: Optional[int]
    last_stop_time: Optional[datetime]
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def from_gps_args(cls, raw: str) -> "BusPosition":
        """Parse from the JSON string inside a SignalR 'gps' message's A[0]."""
        data = json.loads(raw)
        point = decode_polyline_last_point(data.get("Route", ""))
        lat, lng = point if point else (0.0, 0.0)
        lsdt = data.get("LSDT")
        last_stop_time = datetime.fromtimestamp(lsdt / 1000, tz=timezone.utc) if lsdt else None
        return cls(
            trip_id=data["TripId"],
            bus_id=data["BusId"],
            bus_reg=str(data.get("Reg", "")),
            lat=lat,
            lng=lng,
            last_stop_id=data.get("LSID"),
            last_stop_time=last_stop_time,
        )
