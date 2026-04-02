from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.busminder.const import (
    CONF_OPERATOR_URL,
    CONF_ROUTE_GROUP_NAME,
    CONF_ROUTE_GROUP_UUID,
    CONF_ROUTES,
    DOMAIN,
)


async def test_sensor_has_device_info(hass: HomeAssistant, mock_config_entry):
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    from homeassistant.helpers import device_registry as dr

    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(identifiers={("busminder", f"{mock_config_entry.entry_id}_10001")})
    assert device is not None
    assert device.manufacturer == "BusMinder"
    assert device.entry_type == DeviceEntryType.SERVICE


async def test_device_tracker_has_same_device(hass: HomeAssistant, mock_config_entry):
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
    device = dev_reg.async_get_device(identifiers={("busminder", f"{mock_config_entry.entry_id}_10001")})
    assert device is not None
    assert entity.device_id == device.id


async def test_custom_route_name_becomes_device_name(hass: HomeAssistant):
    """When custom_route_name is set, it is used as the HA device name."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_OPERATOR_URL: "https://example.com/tracking/",
            CONF_ROUTE_GROUP_UUID: "aaaaaaaa-0000-4000-8000-000000000002",
            CONF_ROUTE_GROUP_NAME: "Springfield High - PM",
            CONF_ROUTES: [
                {
                    "trip_id": 10001,
                    "name": "1001 : Springfield 1 | Springfield High to City - PM",
                    "route_number": "1001",
                    "uuid": "aaaaaaaa-0000-4000-8000-000000000002",
                    "stop_id": 10001,
                    "stop_name": "Springfield High - Main Gate",
                    "stop_lat": -37.7877,
                    "stop_lng": 145.33912,
                    "custom_route_name": "My Bus",
                    "custom_stop_name": "Front Gate",
                }
            ],
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    from homeassistant.helpers import device_registry as dr

    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(identifiers={("busminder", f"{entry.entry_id}_10001")})
    assert device is not None
    assert device.name == "My Bus"
