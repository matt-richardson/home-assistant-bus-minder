# Changelog

## [0.2.0] - 2026-03-31

### Features

- Device registry: each monitored route appears as a named device in Settings → Devices & Services
- Options flow: full reconfiguration of operator URL, routes, and stop without removing the integration
- Repair issues: persistent SSE connection failures raise a repair notification in HA UI
- Diagnostics: downloadable diagnostics from HA UI (operator URL is redacted)
- Entity unavailable state: sensor and device tracker go unavailable when connection is persistently failing
- `icons.json`: `mdi:bus-clock` for ETA sensor, `mdi:bus` for device tracker

### Quality

- 95%+ test coverage enforced in CI
- Full CI pipeline: black, isort, flake8, pylint, mypy, pytest, hassfest, HACS validation
- Pre-commit hooks: black, isort, flake8, mypy, markdownlint, yamlfmt
- Release automation via release-please + Conventional Commits
- `dev.sh` helper script for local development
- `CLAUDE.md` architecture and workflow documentation
- `manifest.json`: version 0.2.0, `integration_type: service`, `quality_scale: silver`

### Bug Fixes

- Device tracker entities no longer report available when the SSE stream has failed

## [0.1.0] - Initial release

- Config flow: 3-step setup (operator URL → route selection → stop selection)
- ETA sensor: minutes to arrival per route
- Device tracker: live GPS position per route
- SignalR 2.x SSE client (negotiate → connect → start → subscribe)
- Push-based coordinator (no polling)
- 35 tests
