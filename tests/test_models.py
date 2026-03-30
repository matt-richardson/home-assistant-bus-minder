import pytest
from custom_components.busminder.models import (
    Stop, Route, RouteGroup, BusPosition, decode_polyline_last_point
)

def test_decode_polyline_last_point_single():
    # "blseFopavZ" decodes to approx (-37.7877, 145.33912) — Springfield High
    lat, lng = decode_polyline_last_point("blseFopavZ")
    assert abs(lat - (-37.7877)) < 0.001
    assert abs(lng - 145.33912) < 0.001

def test_decode_polyline_last_point_multi():
    # Multi-point polyline: last point should differ from first
    encoded = "psseFywavZDIDGDEFGFGFGHG"
    lat, lng = decode_polyline_last_point(encoded)
    # Last point should be further south than first
    first_lat, _ = decode_polyline_last_point("psseFywavZ")
    assert lat < first_lat  # moving south (more negative)

def test_decode_polyline_last_point_empty():
    assert decode_polyline_last_point("") is None

def test_stop_from_metadata():
    stop = Stop.from_metadata(
        {"id": 905346, "position": "blseFopavZ", "name": "Springfield High - Bottom Area", "num": 4}
    )
    assert stop.id == 905346
    assert stop.name == "Springfield High - Bottom Area"
    assert stop.sequence == 4
    assert abs(stop.lat - (-37.7877)) < 0.001

def test_route_from_metadata():
    route = Route.from_metadata({
        "id": 62869,
        "name": "3428 : Springfield High 3 | Springfield High to Dawson St/Burwood Hwy - PM",
        "colour": "#08b8f0",
        "stops": [
            {"id": 905346, "position": "blseFopavZ", "name": "Springfield High - Bottom Area", "num": 1}
        ],
    })
    assert route.trip_id == 62869
    assert route.route_number == "3428"
    assert len(route.stops) == 1
    assert route.stops[0].id == 905346

def test_route_number_extraction():
    route = Route.from_metadata({
        "id": 62867,
        "name": "3430 : Springfield High 2 | Springfield High to Boronia Station - PM",
        "colour": "#20e30f",
        "stops": [],
    })
    assert route.route_number == "3430"

def test_bus_position_from_gps():
    import json
    from datetime import timezone
    raw = json.dumps({
        "TripId": 62869,
        "BusId": 11528,
        "Route": "nuseFuyavZHAJ?H@L?HBJ@J@",
        "Reg": "1528",
        "Poll": 0,
        "LSID": 906802,
        "LSDT": 1774845511180,
    })
    pos = BusPosition.from_gps_args(raw)
    assert pos.trip_id == 62869
    assert pos.bus_reg == "1528"
    assert pos.last_stop_id == 906802
    assert pos.lat is not None
    assert pos.lng is not None
