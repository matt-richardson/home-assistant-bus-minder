# Changelog

## [1.3.0](https://github.com/matt-richardson/home-assistant-bus-minder/compare/v1.2.0...v1.3.0) (2026-04-30)


### Features

* use '&lt;route&gt; - <stop>' as device name, honouring custom names ([6f3e4db](https://github.com/matt-richardson/home-assistant-bus-minder/commit/6f3e4dbb755b8ecd2ad1ef3222328012101d285a))


### Bug Fixes

* add sock_read timeout to SSE connection to recover after laptop sleep ([ce8c3d8](https://github.com/matt-richardson/home-assistant-bus-minder/commit/ce8c3d88c96ed79eef17e8174c4ce9b33f4e3967))
* derive SSE read timeout from negotiated KeepAliveTimeout ([cdaf631](https://github.com/matt-richardson/home-assistant-bus-minder/commit/cdaf631b86c4b86c6491bb46433c2fce64e2d8fe))
* retry route metadata fetch on SSE reconnect ([fee13ea](https://github.com/matt-richardson/home-assistant-bus-minder/commit/fee13ea4b1e38c27c3bb1e23a37734ae96764f1c))

## [1.2.0](https://github.com/matt-richardson/home-assistant-bus-minder/compare/v1.1.0...v1.2.0) (2026-04-28)


### Features

* add BusLiveEtaSensor using historical inter-stop segment times ([fb8dd27](https://github.com/matt-richardson/home-assistant-bus-minder/commit/fb8dd2774b82e2e6fe4847ae80387f9b58fea6c1))
* add BusScheduledEtaSensor using dt field with historical median fallback ([f456daf](https://github.com/matt-richardson/home-assistant-bus-minder/commit/f456daf89a0ad87a32f0f88c0f7b81dbec23bd82))
* add HistoryStore for persistent bus arrival and segment observations ([eca400b](https://github.com/matt-richardson/home-assistant-bus-minder/commit/eca400bf074ca9ab64de9b530cba4b6845370abb))
* capture scheduled_time (dt) field on Stop model ([9663e92](https://github.com/matt-richardson/home-assistant-bus-minder/commit/9663e92c01db0df921417c23c228151f42a2ecc5))
* coordinator records stop arrivals and segment times via HistoryStore ([0181132](https://github.com/matt-richardson/home-assistant-bus-minder/commit/018113280f30625a90035188b6daad604a783da2))
* migrate config entry v1→v2 promoting shared stop into per-route data ([9a6f7f8](https://github.com/matt-richardson/home-assistant-bus-minder/commit/9a6f7f87b20541ce1a443613be0d1c945d9fccb3))

## [1.1.0](https://github.com/matt-richardson/home-assistant-bus-minder/compare/v1.0.0...v1.1.0) (2026-04-02)

### New entities

- **Connected sensor** (`binary_sensor.busminder_{route}_connected`) — diagnostic binary sensor that is `on` when the SSE stream is healthy and `off` the moment a connection error occurs. Recovers as soon as the stream re-initialises, independent of whether any buses are currently running.

### Bug fixes

- **ETA sensor was always showing unknown** — the ETA calculation requires the full route stop list to locate the bus in the stop sequence, but only the single monitored stop was being passed to it. It now uses the complete stop list fetched at startup. ([4e9d602](https://github.com/matt-richardson/home-assistant-bus-minder/commit/4e9d6023538631254de6d5df6d9cb73aa76b9a93))

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
