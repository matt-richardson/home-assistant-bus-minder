import pytest
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType


async def test_sensor_has_device_info(hass: HomeAssistant, mock_config_entry):
    async def empty_stream():
        return
        yield

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient:
        MockClient.return_value.stream = empty_stream
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    from homeassistant.helpers import device_registry as dr
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(
        identifiers={("busminder", f"{mock_config_entry.entry_id}_10001")}
    )
    assert device is not None
    assert device.manufacturer == "BusMinder"
    assert device.entry_type == DeviceEntryType.SERVICE


async def test_device_tracker_has_same_device(hass: HomeAssistant, mock_config_entry):
    async def empty_stream():
        return
        yield

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient:
        MockClient.return_value.stream = empty_stream
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er
    ent_reg = er.async_get(hass)
    entity = ent_reg.async_get("device_tracker.busminder_1001")
    assert entity is not None
    assert entity.device_id is not None

    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(
        identifiers={("busminder", f"{mock_config_entry.entry_id}_10001")}
    )
    assert device is not None
    assert entity.device_id == device.id
