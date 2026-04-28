from __future__ import annotations

from datetime import datetime, time, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.busminder.history import MAX_OBSERVATIONS, MIN_OBSERVATIONS, HistoryStore


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.async_load = AsyncMock(return_value=None)
    store.async_save = AsyncMock()
    return store


@pytest.fixture
def history(hass, mock_store):
    with patch("custom_components.busminder.history.Store", return_value=mock_store):
        return HistoryStore(hass, "test_entry_id")


async def test_load_empty_starts_blank(history):
    await history.async_load()
    assert history.observation_count("any:key:0") == 0


async def test_load_restores_persisted_data(hass, mock_store):
    mock_store.async_load = AsyncMock(return_value={"10001:10001:0": ["08:25", "08:26"]})
    with patch("custom_components.busminder.history.Store", return_value=mock_store):
        store = HistoryStore(hass, "test_entry_id")
    await store.async_load()
    assert store.observation_count("10001:10001:0") == 2


async def test_record_arrival_creates_entry_for_weekday(history):
    # Monday 2026-04-27 08:25 UTC — treat UTC as local via mock
    arrival = datetime(2026, 4, 27, 8, 25, 0, tzinfo=timezone.utc)
    with patch("custom_components.busminder.history.dt_util.as_local", side_effect=lambda dt: dt):
        await history.record_arrival(10001, 10001, arrival)
    assert history.observation_count("10001:10001:0") == 1  # weekday 0 = Monday


async def test_record_arrival_caps_at_max_observations(history):
    arrival = datetime(2026, 4, 27, 8, 25, 0, tzinfo=timezone.utc)
    with patch("custom_components.busminder.history.dt_util.as_local", side_effect=lambda dt: dt):
        for _ in range(MAX_OBSERVATIONS + 5):
            await history.record_arrival(10001, 10001, arrival)
    assert history.observation_count("10001:10001:0") == MAX_OBSERVATIONS


async def test_get_median_arrival_returns_none_below_min(history):
    arrival = datetime(2026, 4, 27, 8, 25, 0, tzinfo=timezone.utc)
    with patch("custom_components.busminder.history.dt_util.as_local", side_effect=lambda dt: dt):
        for _ in range(MIN_OBSERVATIONS - 1):
            await history.record_arrival(10001, 10001, arrival)
    assert history.get_median_arrival(10001, 10001, 0) is None


async def test_get_median_arrival_returns_median_time(history):
    # Record 08:20, 08:25, 08:30 all on Monday (weekday 0)
    with patch("custom_components.busminder.history.dt_util.as_local", side_effect=lambda dt: dt):
        for minute in (20, 25, 30):
            t = datetime(2026, 4, 27, 8, minute, 0, tzinfo=timezone.utc)
            await history.record_arrival(10001, 10001, t)
    result = history.get_median_arrival(10001, 10001, 0)
    assert result == time(8, 25)


async def test_record_segment_and_get_median(history):
    for seconds in (60.0, 70.0, 80.0):
        await history.record_segment(10001, 1001, 1002, seconds)
    assert history.get_median_segment(10001, 1001, 1002) == 70.0


async def test_get_median_segment_returns_none_below_min(history):
    for _ in range(MIN_OBSERVATIONS - 1):
        await history.record_segment(10001, 1001, 1002, 60.0)
    assert history.get_median_segment(10001, 1001, 1002) is None


async def test_record_segment_caps_at_max_observations(history):
    for i in range(MAX_OBSERVATIONS + 5):
        await history.record_segment(10001, 1001, 1002, float(i))
    assert history.observation_count("10001:1001:1002") == MAX_OBSERVATIONS


async def test_saves_after_each_record(history, mock_store):
    await history.record_segment(10001, 1001, 1002, 60.0)
    mock_store.async_save.assert_called_once()
