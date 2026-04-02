"""Tests for the busminder.reconnect service."""

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant


async def test_reconnect_service_registered(hass: HomeAssistant, mock_config_entry):
    """busminder.reconnect service is registered after setup."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service("busminder", "reconnect")


async def test_reconnect_service_calls_coordinator(hass: HomeAssistant, mock_config_entry):
    """Calling busminder.reconnect triggers async_reconnect on every loaded coordinator."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    coordinator.async_reconnect = AsyncMock()

    await hass.services.async_call("busminder", "reconnect", blocking=True)

    coordinator.async_reconnect.assert_awaited_once()


async def test_reconnect_service_registered_only_once(hass: HomeAssistant, mock_config_entry):
    """Service is not registered twice when multiple entries are set up."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.busminder.const import (
        CONF_OPERATOR_URL,
        CONF_ROUTE_GROUP_NAME,
        CONF_ROUTE_GROUP_UUID,
        CONF_ROUTES,
        DOMAIN,
    )

    entry_b = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aaaaaaaa-0000-4000-8000-000000000099",
        data={
            CONF_OPERATOR_URL: "https://other.example.com/tracking/",
            CONF_ROUTE_GROUP_UUID: "aaaaaaaa-0000-4000-8000-000000000099",
            CONF_ROUTE_GROUP_NAME: "Other School",
            CONF_ROUTES: [
                {
                    "trip_id": 99001,
                    "name": "9001 : Other Route",
                    "route_number": "9001",
                    "uuid": "aaaaaaaa-0000-4000-8000-000000000099",
                    "stop_id": 99001,
                    "stop_name": "Other Stop",
                    "stop_lat": -37.800,
                    "stop_lng": 145.300,
                }
            ],
        },
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entry_b.add_to_hass(hass)
    await hass.config_entries.async_setup(entry_b.entry_id)
    await hass.async_block_till_done()

    # Only one registration should exist (HA raises if you register twice)
    assert hass.services.has_service("busminder", "reconnect")


async def test_reconnect_resets_connection_failed(hass: HomeAssistant, mock_config_entry):
    """async_reconnect resets connection_failed and restarts SSE tasks."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    coordinator.connection_failed = True
    coordinator._failure_count = 5

    with patch.object(coordinator, "_cancel_sse_tasks", new=AsyncMock()) as mock_cancel:
        await coordinator.async_reconnect()

    mock_cancel.assert_awaited_once()
    assert coordinator.connection_failed is False
    assert coordinator._failure_count == 0
