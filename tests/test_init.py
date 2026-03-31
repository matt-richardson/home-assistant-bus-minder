import pytest
from unittest.mock import patch

from homeassistant.core import HomeAssistant

from custom_components.busminder.const import DOMAIN


async def test_async_reload_entry(hass: HomeAssistant, mock_config_entry):
    """async_reload_entry unloads then reloads the config entry."""
    async def empty_stream():
        return
        yield

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient:
        MockClient.return_value.stream = empty_stream
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.entry_id in hass.data[DOMAIN]

    from custom_components.busminder import async_reload_entry

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient2:
        MockClient2.return_value.stream = empty_stream
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
    async def empty_stream():
        return
        yield

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient:
        MockClient.return_value.stream = empty_stream
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
