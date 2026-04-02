# Changelog

## 1.0.0 (2026-04-02)

First stable release. Covers everything from the initial proof-of-concept through Silver IQS compliance and a full set of proximity sensors.

### Sensors & entities

- **ETA sensor** — minutes until the bus arrives at your monitored stop, with `approaching`, `passed`, and `not_running` status attributes
- **Next stop sensor** — name of the stop the bus is currently heading to
- **Stops away sensor** — number of stops between the bus and your monitored stop
- **Distance sensor** — along-route distance in km from the bus to your stop (falls back to straight-line when route metadata is unavailable)
- **Device tracker** — live GPS position shown on the Home Assistant map
- Each monitored route appears as a named **device** in Settings → Devices & Services, with a direct link back to the BusMinder live tracking page

### Configuration

- 3-step setup: operator URL → route selection → stop selection per route
- Operators with separate AM and PM route groups are handled automatically
- Custom route and stop names can be set during setup and updated via reconfigure
- Full **reconfiguration** via the Configure button — change URL, routes, or stops without reinstalling
- Individual route devices can be removed from the HA UI without removing the whole integration

### Reliability

- **Repair notification** raised in the HA UI when the live feed fails persistently; dismissed automatically on reconnect
- All entities go **unavailable** when the connection is persistently failing, rather than showing stale data
- **`busminder.reconnect` service** — force an immediate reconnect from Developer Tools or an automation without reloading the integration

### Quality & CI

- Silver IQS compliance: `quality_scale: silver` in `manifest.json`
- 98%+ test coverage (115 tests), enforced at ≥ 95% in CI
- Full CI pipeline: black, isort, flake8, pylint, mypy, pytest, hassfest, HACS validation, Codecov
- Downloadable **diagnostics** from the HA device page (operator URL is redacted)

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
