from datetime import timedelta

import pytest

from custom_components.busminder.eta import SpeedTracker, estimate_eta, haversine_km, route_distance_km
from custom_components.busminder.models import BusPosition, Route, Stop


def make_stop(id, lat, lng, seq):
    return Stop(id=id, name=f"Stop {id}", lat=lat, lng=lng, sequence=seq)


def make_bus(trip_id, lat, lng, last_stop_id):
    from datetime import datetime, timezone

    return BusPosition(
        trip_id=trip_id,
        bus_id=1,
        bus_reg="0042",
        lat=lat,
        lng=lng,
        last_stop_id=last_stop_id,
        last_stop_time=None,
        received_at=datetime.now(timezone.utc),
    )


def make_route(trip_id, stops):
    return Route(trip_id=trip_id, name="Test Route", route_number="1001", colour="#000", stops=stops)


def test_haversine_known_distance():
    # Melbourne CBD to ~1km north: should be ~1km
    dist = haversine_km(-37.8136, 144.9631, -37.8046, 144.9631)
    assert 0.9 < dist < 1.1


def test_haversine_same_point():
    assert haversine_km(-37.789, 145.340, -37.789, 145.340) == pytest.approx(0.0)


def test_estimate_eta_approaching():
    stops = [
        make_stop(1, -37.780, 145.340, 1),  # first stop (bus passed this)
        make_stop(2, -37.785, 145.340, 2),  # monitored stop
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
    from datetime import datetime, timedelta, timezone

    tracker = SpeedTracker()
    t0 = datetime(2026, 3, 30, 15, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=60)
    # ~0.556 km apart → ~33 km/h over 60 seconds
    tracker.update(10001, -37.780, 145.340, t0)
    tracker.update(10001, -37.785, 145.340, t1)
    speed = tracker.get_speed(10001)
    assert speed is not None
    assert 25 < speed < 40


def test_estimate_eta_monitored_stop_not_in_route():
    """Returns None when the monitored stop is not part of the route."""
    stops = [
        make_stop(1, -37.780, 145.340, 1),
        make_stop(2, -37.785, 145.340, 2),
    ]
    route = make_route(10001, stops)
    bus = make_bus(10001, -37.782, 145.340, last_stop_id=1)
    # monitored stop with id=999 is not in the route
    monitored = make_stop(999, -37.790, 145.340, 3)
    result = estimate_eta(bus, route, monitored, speed_kmh=30.0)
    assert result is None


def test_estimate_eta_last_stop_id_none():
    """Returns None when bus.last_stop_id is None."""
    stops = [
        make_stop(1, -37.780, 145.340, 1),
        make_stop(2, -37.785, 145.340, 2),
    ]
    route = make_route(10001, stops)
    bus = make_bus(10001, -37.782, 145.340, last_stop_id=None)
    result = estimate_eta(bus, route, stops[1], speed_kmh=30.0)
    assert result is None


def test_route_distance_km_sums_stop_segments():
    """route_distance_km sums haversine distances between stops along the route."""
    stops = [
        make_stop(1, -37.780, 145.340, 1),
        make_stop(2, -37.785, 145.340, 2),
        make_stop(3, -37.790, 145.340, 3),  # monitored
    ]
    route = make_route(10001, stops)
    bus = make_bus(10001, -37.781, 145.340, last_stop_id=1)
    monitored = stops[2]

    result = route_distance_km(bus, route, monitored)

    assert result is not None
    # bus → stop2 + stop2 → stop3, all heading south ~0.55km each segment
    assert 0.5 < result < 2.0


def test_route_distance_km_returns_none_when_passed():
    """route_distance_km returns None when bus has passed the monitored stop."""
    stops = [
        make_stop(1, -37.780, 145.340, 1),
        make_stop(2, -37.785, 145.340, 2),  # monitored
        make_stop(3, -37.790, 145.340, 3),
    ]
    route = make_route(10001, stops)
    bus = make_bus(10001, -37.788, 145.340, last_stop_id=3)
    result = route_distance_km(bus, route, stops[1])
    assert result is None


def test_route_distance_km_returns_none_when_last_stop_unknown():
    """route_distance_km returns None when bus.last_stop_id is not in the route."""
    stops = [make_stop(1, -37.780, 145.340, 1), make_stop(2, -37.785, 145.340, 2)]
    route = make_route(10001, stops)
    bus = make_bus(10001, -37.782, 145.340, last_stop_id=999)
    result = route_distance_km(bus, route, stops[1])
    assert result is None


def test_route_distance_km_returns_none_when_last_stop_id_none():
    """route_distance_km returns None when bus.last_stop_id is None."""
    stops = [make_stop(1, -37.780, 145.340, 1), make_stop(2, -37.785, 145.340, 2)]
    route = make_route(10001, stops)
    bus = make_bus(10001, -37.782, 145.340, last_stop_id=None)
    result = route_distance_km(bus, route, stops[1])
    assert result is None


def test_route_distance_km_greater_than_straight_line_for_winding_route():
    """Along-route distance is >= straight-line haversine for non-trivial routes."""
    stops = [
        make_stop(1, -37.780, 145.340, 1),
        make_stop(2, -37.780, 145.360, 2),  # east
        make_stop(3, -37.790, 145.360, 3),  # then south — L-shape
    ]
    route = make_route(10001, stops)
    bus = make_bus(10001, -37.781, 145.340, last_stop_id=1)
    monitored = stops[2]

    along_route = route_distance_km(bus, route, monitored)
    straight_line = haversine_km(bus.lat, bus.lng, monitored.lat, monitored.lng)

    assert along_route is not None
    assert along_route > straight_line


def test_speed_tracker_returns_none_when_all_samples_too_close_in_time():
    """Returns None when all consecutive samples are < 1 second apart."""
    from datetime import datetime, timedelta, timezone

    tracker = SpeedTracker()
    t0 = datetime(2026, 3, 30, 15, 0, 0, tzinfo=timezone.utc)
    # Add two samples less than 1 second apart
    tracker.update(10001, -37.780, 145.340, t0)
    tracker.update(10001, -37.785, 145.340, t0 + timedelta(milliseconds=500))
    result = tracker.get_speed(10001)
    assert result is None
