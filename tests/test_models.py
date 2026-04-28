from custom_components.busminder.models import BusPosition, Route, Stop, decode_polyline_last_point


def test_decode_polyline_last_point_single():
    # "blseFopavZ" decodes to approx (-37.7877, 145.33912) — Springfield High Main Gate
    result = decode_polyline_last_point("blseFopavZ")
    assert result is not None
    lat, lng = result
    assert abs(lat - (-37.7877)) < 0.001
    assert abs(lng - 145.33912) < 0.001


def test_decode_polyline_last_point_multi():
    # Multi-point polyline: last point should differ from first
    encoded = "psseFywavZDIDGDEFGFGFGHG"
    result = decode_polyline_last_point(encoded)
    assert result is not None
    lat, lng = result
    # Last point should be further south than first
    first = decode_polyline_last_point("psseFywavZ")
    assert first is not None
    first_lat, _ = first
    assert lat < first_lat  # moving south (more negative)


def test_decode_polyline_last_point_empty():
    assert decode_polyline_last_point("") is None


def test_stop_from_metadata():
    stop = Stop.from_metadata({"id": 10001, "position": "blseFopavZ", "name": "Springfield High - Main Gate", "num": 4})
    assert stop.id == 10001
    assert stop.name == "Springfield High - Main Gate"
    assert stop.sequence == 4
    assert abs(stop.lat - (-37.7877)) < 0.001


def test_route_from_metadata():
    route = Route.from_metadata(
        {
            "id": 10001,
            "name": "1001 : Springfield 1 | Springfield High to City - PM",
            "colour": "#08b8f0",
            "stops": [{"id": 10001, "position": "blseFopavZ", "name": "Springfield High - Main Gate", "num": 1}],
        }
    )
    assert route.trip_id == 10001
    assert route.route_number == "1001"
    assert len(route.stops) == 1
    assert route.stops[0].id == 10001


def test_route_number_extraction():
    route = Route.from_metadata(
        {
            "id": 10002,
            "name": "1002 : Springfield 2 | Springfield High to City Station - PM",
            "colour": "#20e30f",
            "stops": [],
        }
    )
    assert route.route_number == "1002"


def test_bus_position_from_gps():
    import json

    raw = json.dumps(
        {
            "TripId": 10001,
            "BusId": 11528,
            "Route": "nuseFuyavZHAJ?H@L?HBJ@J@",
            "Reg": "1528",
            "Poll": 0,
            "LSID": 906802,
            "LSDT": 1774845511180,
        }
    )
    pos = BusPosition.from_gps_args(raw)
    assert pos.trip_id == 10001
    assert pos.bus_reg == "1528"
    assert pos.last_stop_id == 906802
    assert pos.lat is not None
    assert pos.lng is not None


def test_stop_captures_scheduled_time():
    stop = Stop.from_metadata(
        {
            "id": 10001,
            "position": "blseFopavZ",
            "name": "Springfield High - Main Gate",
            "num": 1,
            "dt": "08:25",
        }
    )
    assert stop.scheduled_time == "08:25"


def test_stop_scheduled_time_none_when_absent():
    stop = Stop.from_metadata(
        {
            "id": 10001,
            "position": "blseFopavZ",
            "name": "Springfield High - Main Gate",
            "num": 1,
        }
    )
    assert stop.scheduled_time is None
