import asyncio
from datetime import datetime, timezone
from unittest.mock import patch

from homeassistant.core import HomeAssistant

from custom_components.busminder.coordinator import BusMinderCoordinator
from custom_components.busminder.models import BusPosition


async def test_coordinator_dispatches_position(hass: HomeAssistant, mock_config_entry):
    """GPS events from SignalR should update coordinator.data."""
    mock_config_entry.add_to_hass(hass)

    async def fake_stream():
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

    async def fake_stream():
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

    call_count = 0

    async def failing_stream():
        nonlocal call_count
        call_count += 1
        raise Exception("SSE connection lost")
        yield  # make it an async generator

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient:
        with patch("custom_components.busminder.coordinator.asyncio.sleep"):
            MockClient.return_value.stream = failing_stream
            mock_config_entry.add_to_hass(hass)
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            # Let several reconnect cycles run
            for _ in range(10):
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
        with patch("custom_components.busminder.coordinator.asyncio.sleep"):
            MockClient.return_value.stream = failing_stream
            mock_config_entry.add_to_hass(hass)
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            for _ in range(10):
                await hass.async_block_till_done()

    coordinator = hass.data["busminder"][mock_config_entry.entry_id]
    assert coordinator.connection_failed is True


async def test_connection_failed_clears_on_position(hass: HomeAssistant, mock_config_entry):
    """connection_failed clears when a valid position arrives."""
    from datetime import datetime, timezone

    from homeassistant.helpers import issue_registry as ir

    from custom_components.busminder.models import BusPosition

    async def empty_stream():
        return
        yield

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient:
        MockClient.return_value.stream = empty_stream
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = hass.data["busminder"][mock_config_entry.entry_id]
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
