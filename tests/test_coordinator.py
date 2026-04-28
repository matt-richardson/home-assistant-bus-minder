import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.busminder.coordinator import BusMinderCoordinator
from custom_components.busminder.models import BusPosition


async def test_coordinator_dispatches_position(hass: HomeAssistant, mock_config_entry):
    """GPS events from SignalR should update coordinator.data."""
    mock_config_entry.add_to_hass(hass)

    async def fake_stream(on_connected=None):
        if on_connected is not None:
            on_connected()
        pos = BusPosition(
            trip_id=10001,
            bus_id=11528,
            bus_reg="1528",
            lat=-37.820,
            lng=145.340,
            last_stop_id=10001,
            last_stop_time=None,
            received_at=datetime.now(timezone.utc),
        )
        yield pos
        await asyncio.sleep(9999)  # hold open

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient:
        MockClient.return_value.stream = fake_stream
        coordinator = BusMinderCoordinator(hass, mock_config_entry)
        await coordinator.async_start()
        await asyncio.sleep(0.1)  # let event loop tick

    assert 10001 in coordinator.data
    assert coordinator.data[10001].bus_reg == "1528"


async def test_coordinator_filters_unmonitored_routes(hass: HomeAssistant, mock_config_entry):
    """GPS events for trip IDs not in config should be ignored."""

    async def fake_stream(on_connected=None):
        if on_connected is not None:
            on_connected()
        pos = BusPosition(
            trip_id=99999,  # not in config
            bus_id=1,
            bus_reg="XXXX",
            lat=-37.800,
            lng=145.300,
            last_stop_id=None,
            last_stop_time=None,
            received_at=datetime.now(timezone.utc),
        )
        yield pos
        await asyncio.sleep(9999)

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient:
        MockClient.return_value.stream = fake_stream
        coordinator = BusMinderCoordinator(hass, mock_config_entry)
        await coordinator.async_start()
        await asyncio.sleep(0.1)

    assert coordinator.data is None or 99999 not in coordinator.data


async def test_repair_issue_raised_after_three_failures(hass: HomeAssistant, mock_config_entry):
    """Repair issue is created after RECONNECT_THRESHOLD consecutive SSE failures."""
    from homeassistant.helpers import issue_registry as ir

    async def failing_stream(on_connected=None):
        raise Exception("SSE connection lost")
        yield  # make it an async generator

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient:
        MockClient.return_value.stream = failing_stream
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        # Drive several reconnect cycles by advancing virtual time past each backoff sleep
        for _ in range(5):
            async_fire_time_changed(hass, utcnow() + timedelta(hours=1), fire_all=True)
            await hass.async_block_till_done()

    issue_reg = ir.async_get(hass)
    issue = issue_reg.async_get_issue("busminder", "connection_failed")
    assert issue is not None


async def test_connection_failed_flag_set_after_three_failures(hass: HomeAssistant, mock_config_entry):
    """coordinator.connection_failed is True after RECONNECT_THRESHOLD failures."""

    async def failing_stream():
        raise Exception("SSE connection lost")
        yield

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient:
        MockClient.return_value.stream = failing_stream
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        for _ in range(5):
            async_fire_time_changed(hass, utcnow() + timedelta(hours=1), fire_all=True)
            await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert coordinator.connection_failed is True


async def test_connection_failed_clears_on_position(hass: HomeAssistant, mock_config_entry):
    """connection_failed clears when a valid position arrives."""
    from homeassistant.helpers import issue_registry as ir

    from custom_components.busminder.models import BusPosition

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    # Manually set the failed state
    coordinator.connection_failed = True
    coordinator._failure_count = 3
    ir.async_create_issue(
        hass,
        "busminder",
        "connection_failed",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="connection_failed",
        translation_placeholders={"operator_url": "https://example.com/"},
    )

    pos = BusPosition(
        trip_id=10001,
        bus_id=1,
        bus_reg="1528",
        lat=-37.820,
        lng=145.340,
        last_stop_id=10001,
        last_stop_time=None,
        received_at=datetime.now(timezone.utc),
    )
    coordinator._on_position(pos)
    await hass.async_block_till_done()

    assert coordinator.connection_failed is False
    assert coordinator._failure_count == 0
    issue_reg = ir.async_get(hass)
    assert issue_reg.async_get_issue("busminder", "connection_failed") is None


async def test_config_entry_not_ready_when_unreachable(hass: HomeAssistant, mock_config_entry):
    """ConfigEntryNotReady is raised when the operator URL is unreachable at setup."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = aiohttp.ClientConnectionError("Cannot connect")
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)
    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_resp)

    with patch(
        "custom_components.busminder.coordinator.async_get_clientsession",
        return_value=mock_session,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_coordinator_records_segment_on_stop_transition(hass, mock_config_entry):
    """Coordinator records inter-stop segment time when last_stop_id changes consecutively."""
    from datetime import datetime, timezone

    from custom_components.busminder.models import BusPosition, Route, Stop

    mock_config_entry.add_to_hass(hass)

    async def fake_stream(on_connected=None):
        if on_connected is not None:
            on_connected()
        await asyncio.sleep(9999)
        yield

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient:
        MockClient.return_value.stream = fake_stream
        coordinator = BusMinderCoordinator(hass, mock_config_entry)
        await coordinator.async_start()

    # Inject a two-stop route so stops are consecutive
    stop_a = Stop(id=9001, name="Stop A", lat=-37.78, lng=145.33, sequence=1)
    stop_b = Stop(id=9002, name="Stop B", lat=-37.79, lng=145.34, sequence=2)
    coordinator._full_routes[10001] = Route(
        trip_id=10001,
        name="1001 : test",
        route_number="1001",
        colour="",
        stops=[stop_a, stop_b],
    )

    t1 = datetime(2026, 4, 27, 8, 20, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 4, 27, 8, 21, 10, tzinfo=timezone.utc)  # 70s later

    pos1 = BusPosition(
        trip_id=10001,
        bus_id=1,
        bus_reg="X",
        lat=-37.78,
        lng=145.33,
        last_stop_id=9001,
        last_stop_time=t1,
        received_at=t1,
    )
    pos2 = BusPosition(
        trip_id=10001,
        bus_id=1,
        bus_reg="X",
        lat=-37.79,
        lng=145.34,
        last_stop_id=9002,
        last_stop_time=t2,
        received_at=t2,
    )

    coordinator._on_position(pos1)
    coordinator._on_position(pos2)
    await hass.async_block_till_done()

    assert coordinator._history.get_median_segment(10001, 9001, 9002) is None  # only 1 obs, need 3
    assert coordinator._history.observation_count("10001:9001:9002") == 1


async def test_coordinator_records_arrival_at_monitored_stop(hass, mock_config_entry):
    """Coordinator records arrival time when bus reaches the registered monitored stop."""
    from datetime import datetime, timezone

    from custom_components.busminder.models import BusPosition, Route, Stop

    mock_config_entry.add_to_hass(hass)

    async def fake_stream(on_connected=None):
        if on_connected is not None:
            on_connected()
        await asyncio.sleep(9999)
        yield

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient:
        MockClient.return_value.stream = fake_stream
        coordinator = BusMinderCoordinator(hass, mock_config_entry)
        await coordinator.async_start()

    stop_a = Stop(id=9001, name="Stop A", lat=-37.78, lng=145.33, sequence=1)
    stop_b = Stop(id=9002, name="Stop B", lat=-37.79, lng=145.34, sequence=2)
    coordinator._full_routes[10001] = Route(
        trip_id=10001,
        name="1001 : test",
        route_number="1001",
        colour="",
        stops=[stop_a, stop_b],
    )
    coordinator.register_monitored_stop(10001, 9002)

    t1 = datetime(2026, 4, 27, 8, 20, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 4, 27, 8, 21, 10, tzinfo=timezone.utc)

    pos1 = BusPosition(
        trip_id=10001,
        bus_id=1,
        bus_reg="X",
        lat=-37.78,
        lng=145.33,
        last_stop_id=9001,
        last_stop_time=t1,
        received_at=t1,
    )
    pos2 = BusPosition(
        trip_id=10001,
        bus_id=1,
        bus_reg="X",
        lat=-37.79,
        lng=145.34,
        last_stop_id=9002,
        last_stop_time=t2,
        received_at=t2,
    )

    coordinator._on_position(pos1)
    coordinator._on_position(pos2)
    await hass.async_block_till_done()

    assert coordinator._history.observation_count("10001:9002:0") == 1  # weekday 0 = Monday


async def test_coordinator_skips_segment_for_non_consecutive_stops(hass, mock_config_entry):
    """Coordinator does not record a segment when stops are not adjacent in the route."""
    from datetime import datetime, timezone

    from custom_components.busminder.models import BusPosition, Route, Stop

    mock_config_entry.add_to_hass(hass)

    async def fake_stream(on_connected=None):
        if on_connected is not None:
            on_connected()
        await asyncio.sleep(9999)
        yield

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient:
        MockClient.return_value.stream = fake_stream
        coordinator = BusMinderCoordinator(hass, mock_config_entry)
        await coordinator.async_start()

    stop_a = Stop(id=9001, name="A", lat=-37.78, lng=145.33, sequence=1)
    stop_b = Stop(id=9002, name="B", lat=-37.79, lng=145.34, sequence=2)
    stop_c = Stop(id=9003, name="C", lat=-37.80, lng=145.35, sequence=3)
    coordinator._full_routes[10001] = Route(
        trip_id=10001,
        name="1001 : test",
        route_number="1001",
        colour="",
        stops=[stop_a, stop_b, stop_c],
    )

    t1 = datetime(2026, 4, 27, 8, 20, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 4, 27, 8, 22, 0, tzinfo=timezone.utc)

    pos1 = BusPosition(
        trip_id=10001,
        bus_id=1,
        bus_reg="X",
        lat=-37.78,
        lng=145.33,
        last_stop_id=9001,
        last_stop_time=t1,
        received_at=t1,
    )
    # Skip stop B — jump directly to C (skipped stop scenario)
    pos2 = BusPosition(
        trip_id=10001,
        bus_id=1,
        bus_reg="X",
        lat=-37.80,
        lng=145.35,
        last_stop_id=9003,
        last_stop_time=t2,
        received_at=t2,
    )

    coordinator._on_position(pos1)
    coordinator._on_position(pos2)
    await hass.async_block_till_done()

    assert coordinator._history.observation_count("10001:9001:9003") == 0


async def test_get_live_eta_seconds_sums_segments(hass, mock_config_entry):
    """get_live_eta_seconds returns sum of median segment times."""
    from custom_components.busminder.models import Route, Stop

    mock_config_entry.add_to_hass(hass)

    async def fake_stream(on_connected=None):
        if on_connected is not None:
            on_connected()
        await asyncio.sleep(9999)
        yield

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient:
        MockClient.return_value.stream = fake_stream
        coordinator = BusMinderCoordinator(hass, mock_config_entry)
        await coordinator.async_start()

    stops = [
        Stop(id=9001, name="A", lat=-37.78, lng=145.33, sequence=1),
        Stop(id=9002, name="B", lat=-37.79, lng=145.34, sequence=2),
        Stop(id=9003, name="C", lat=-37.80, lng=145.35, sequence=3),
    ]
    coordinator._full_routes[10001] = Route(
        trip_id=10001,
        name="1001 : test",
        route_number="1001",
        colour="",
        stops=stops,
    )

    # Inject median segment data directly (bypass the 3-observation minimum for this test)
    coordinator._history._data["10001:9001:9002"] = [60.0, 60.0, 60.0]  # median = 60s
    coordinator._history._data["10001:9002:9003"] = [90.0, 90.0, 90.0]  # median = 90s

    result = coordinator.get_live_eta_seconds(10001, 9001, 9003)
    assert result == 150.0  # 60 + 90


async def test_get_live_eta_seconds_returns_none_when_segment_missing(hass, mock_config_entry):
    """get_live_eta_seconds returns None when any segment has insufficient history."""
    from custom_components.busminder.models import Route, Stop

    mock_config_entry.add_to_hass(hass)

    async def fake_stream(on_connected=None):
        if on_connected is not None:
            on_connected()
        await asyncio.sleep(9999)
        yield

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient:
        MockClient.return_value.stream = fake_stream
        coordinator = BusMinderCoordinator(hass, mock_config_entry)
        await coordinator.async_start()

    stops = [
        Stop(id=9001, name="A", lat=-37.78, lng=145.33, sequence=1),
        Stop(id=9002, name="B", lat=-37.79, lng=145.34, sequence=2),
        Stop(id=9003, name="C", lat=-37.80, lng=145.35, sequence=3),
    ]
    coordinator._full_routes[10001] = Route(
        trip_id=10001,
        name="1001 : test",
        route_number="1001",
        colour="",
        stops=stops,
    )
    coordinator._history._data["10001:9001:9002"] = [60.0, 60.0, 60.0]
    # 10001:9002:9003 has no data

    result = coordinator.get_live_eta_seconds(10001, 9001, 9003)
    assert result is None
