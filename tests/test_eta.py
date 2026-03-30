import pytest
from datetime import timedelta
from custom_components.busminder.models import BusPosition, Stop, Route
from custom_components.busminder.eta import (
    haversine_km,
    estimate_eta,
    SpeedTracker,
)


def make_stop(id, lat, lng, seq):
    return Stop(id=id, name=f"Stop {id}", lat=lat, lng=lng, sequence=seq)


def make_bus(trip_id, lat, lng, last_stop_id):
    from datetime import datetime, timezone
    return BusPosition(
        trip_id=trip_id, bus_id=1, bus_reg="1528",
        lat=lat, lng=lng,
        last_stop_id=last_stop_id, last_stop_time=None,
        received_at=datetime.now(timezone.utc),
    )


def make_route(trip_id, stops):
    return Route(trip_id=trip_id, name="Test Route", route_number="1001",
                 colour="#000", stops=stops)


def test_haversine_known_distance():
    # Melbourne CBD to ~1km north: should be ~1km
    dist = haversine_km(-37.8136, 144.9631, -37.8046, 144.9631)
    assert 0.9 < dist < 1.1


def test_haversine_same_point():
    assert haversine_km(-37.789, 145.340, -37.789, 145.340) == pytest.approx(0.0)


def test_estimate_eta_approaching():
    stops = [
        make_stop(1, -37.780, 145.340, 1),   # first stop (bus passed this)
        make_stop(2, -37.785, 145.340, 2),   # monitored stop
    ]
    route = make_route(10001, stops)
    bus = make_bus(10001, -37.782, 145.340, last_stop_id=1)
    monitored_stop = stops[1]

    result = estimate_eta(bus, route, monitored_stop, speed_kmh=30.0)

    assert result is not None
    assert isinstance(result, timedelta)
    assert 0 < result.total_seconds() < 120  # should be a few minutes


def test_estimate_eta_bus_passed():
    stops = [
        make_stop(1, -37.780, 145.340, 1),
        make_stop(2, -37.785, 145.340, 2),  # monitored stop (already passed)
        make_stop(3, -37.790, 145.340, 3),
    ]
    route = make_route(10001, stops)
    bus = make_bus(10001, -37.788, 145.340, last_stop_id=3)  # past monitored
    monitored_stop = stops[1]

    result = estimate_eta(bus, route, monitored_stop, speed_kmh=30.0)
    assert result is None  # passed


def test_estimate_eta_no_speed():
    stops = [make_stop(1, -37.780, 145.340, 1), make_stop(2, -37.785, 145.340, 2)]
    route = make_route(10001, stops)
    bus = make_bus(10001, -37.782, 145.340, last_stop_id=1)
    result = estimate_eta(bus, route, stops[1], speed_kmh=None)
    assert result is None


def test_estimate_eta_unknown_last_stop():
    stops = [make_stop(1, -37.780, 145.340, 1), make_stop(2, -37.785, 145.340, 2)]
    route = make_route(10001, stops)
    bus = make_bus(10001, -37.782, 145.340, last_stop_id=999)  # not in route
    result = estimate_eta(bus, route, stops[1], speed_kmh=30.0)
    assert result is None


def test_speed_tracker_returns_none_with_one_point():
    from datetime import datetime, timezone
    tracker = SpeedTracker()
    tracker.update(10001, -37.780, 145.340, datetime.now(timezone.utc))
    assert tracker.get_speed(10001) is None


def test_speed_tracker_computes_speed():
    from datetime import datetime, timezone, timedelta
    tracker = SpeedTracker()
    t0 = datetime(2026, 3, 30, 15, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=60)
    # ~0.556 km apart → ~33 km/h over 60 seconds
    tracker.update(10001, -37.780, 145.340, t0)
    tracker.update(10001, -37.785, 145.340, t1)
    speed = tracker.get_speed(10001)
    assert speed is not None
    assert 25 < speed < 40
