from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from custom_components.busminder.const import CONF_ROUTES, DOMAIN


async def test_async_reload_entry(hass: HomeAssistant, mock_config_entry):
    """async_reload_entry unloads then reloads the config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.entry_id in hass.data[DOMAIN]

    from custom_components.busminder import async_reload_entry

    await async_reload_entry(hass, mock_config_entry)
    await hass.async_block_till_done()

    # Entry should still be loaded after reload
    assert mock_config_entry.entry_id in hass.data[DOMAIN]


async def test_parallel_updates_is_set(hass: HomeAssistant):
    """PARALLEL_UPDATES constant is defined."""
    from custom_components.busminder import PARALLEL_UPDATES

    assert PARALLEL_UPDATES == 1


async def test_update_listener_triggers_reload(hass: HomeAssistant, mock_config_entry):
    """Updating entry options triggers an entry reload."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    reload_calls = []

    async def mock_reload(entry_id):
        reload_calls.append(entry_id)

    with patch.object(hass.config_entries, "async_reload", side_effect=mock_reload):
        hass.config_entries.async_update_entry(mock_config_entry, options={"_ts": "1"})
        await hass.async_block_till_done()

    assert len(reload_calls) == 1


async def test_remove_config_entry_device(hass: HomeAssistant, mock_config_entry):
    """Removing a device strips its route from config and returns True."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Find the device for trip_id 10001
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(identifiers={(DOMAIN, f"{mock_config_entry.entry_id}_10001")})
    assert device is not None

    from custom_components.busminder import async_remove_config_entry_device

    result = await async_remove_config_entry_device(hass, mock_config_entry, device)

    assert result is True
    remaining = [r["trip_id"] for r in mock_config_entry.data[CONF_ROUTES]]
    assert 10001 not in remaining
    assert 10002 in remaining
    # Drain the reload triggered by async_update_entry so it runs while patches
    # are still active (prevents real aiohttp.ClientSession during hass teardown).
    await hass.async_block_till_done()


async def test_remove_config_entry_device_also_clears_options(hass: HomeAssistant, mock_config_entry):
    """Removing a device clears the route from entry.options too, so it won't reappear in the options flow."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Simulate a previous options flow run that stored routes in entry.options
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            CONF_ROUTES: [
                {"trip_id": 10001, "name": "Route 1001", "route_number": "1001"},
                {"trip_id": 10002, "name": "Route 1002", "route_number": "1002"},
            ]
        },
    )
    await hass.async_block_till_done()

    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(identifiers={(DOMAIN, f"{mock_config_entry.entry_id}_10001")})
    assert device is not None

    from custom_components.busminder import async_remove_config_entry_device

    await async_remove_config_entry_device(hass, mock_config_entry, device)

    # Route must be gone from both data and options
    assert 10001 not in [r["trip_id"] for r in mock_config_entry.data.get(CONF_ROUTES, [])]
    assert 10001 not in [r["trip_id"] for r in mock_config_entry.options.get(CONF_ROUTES, [])]
    assert 10002 in [r["trip_id"] for r in mock_config_entry.options[CONF_ROUTES]]
    await hass.async_block_till_done()
