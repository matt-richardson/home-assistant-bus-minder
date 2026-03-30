# BusMinder — Developer Guide

## Architecture

```
custom_components/busminder/
├── __init__.py         Entry point: async_setup_entry, async_unload_entry, async_reload_entry
├── const.py            DOMAIN, config key constants, API URL constants
├── exceptions.py       BusMinderError hierarchy (BusMinderConnectionError, BusMinderParseError)
├── models.py           Stop, Route, RouteGroup, BusPosition dataclasses + polyline decoder
├── scraper.py          Fetch operator page → extract UUID → fetch route group metadata
├── signalr.py          Async SignalR 2.x SSE client (negotiate → connect → start → subscribe)
├── eta.py              Haversine distance, ETA estimation, SpeedTracker
├── coordinator.py      Push-based DataUpdateCoordinator; repair issue management
├── entity.py           BusMinderEntity base class with shared device_info
├── config_flow.py      3-step config flow + BusMinderOptionsFlow (full reconfiguration)
├── sensor.py           BusEtaSensor — ETA in minutes
├── device_tracker.py   BusTrackerEntity — GPS coordinates
├── diagnostics.py      HA diagnostics platform
├── icons.json          Entity icon definitions
├── strings.json        UI strings (en source)
└── translations/en.json  English translations (mirrors strings.json)
```

## Development Workflow

```bash
# First time
./setup-venv.sh

# Daily
source venv/bin/activate
./dev.sh test          # run all tests
./dev.sh test-cov      # run with coverage (must stay ≥95%)
./dev.sh lint          # black/isort/flake8/pylint/mypy
./dev.sh format        # auto-format
./dev.sh validate      # format + lint + test-cov
```

## Commit Format (Conventional Commits)

```
feat: add options flow for reconfiguration
fix: mark sensor unavailable when SSE connection fails
chore: add pre-commit hooks
docs: update README installation steps
test: add diagnostics coverage
```

Types: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `ci`

## Testing Strategy

- All tests use `pytest-homeassistant-custom-component` for HA fixtures
- `conftest.py` provides `mock_config_entry` with fictional "Springfield High" scenario
- HTTP calls are mocked with `aioresponses`
- SignalR client is mocked with `unittest.mock.patch`
- TDD: write the failing test first, then implement

Key fixtures:
- `hass` — Home Assistant instance (from pytest-homeassistant-custom-component)
- `mock_config_entry` — pre-configured MockConfigEntry
- Route group UUID: `aaaaaaaa-0000-4000-8000-000000000001`
- Trip IDs: 10001 (route 1001), 10002 (route 1002)
- Monitored stop: 10001 "Springfield High - Main Gate" (-37.7877, 145.33912)

## Entity Naming

- Sensor entity ID: `sensor.busminder_{route_number}_eta` (e.g., `sensor.busminder_1001_eta`)
- Device tracker entity ID: `device_tracker.busminder_{route_number}` (e.g., `device_tracker.busminder_1001`)
- Device name: route name from BusMinder (e.g., "1001 : Springfield 1 | Springfield High to City - PM")

## Silver Tier Checklist

Reference: https://developers.home-assistant.io/docs/core/integration-quality-scale/checklist
