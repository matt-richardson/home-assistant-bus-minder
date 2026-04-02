# Changelog

## 1.0.0 (2026-04-02)


### Features

* 3-step config flow (URL → routes → stop) ([4024bbb](https://github.com/matt-richardson/home-assistant-bus-minder/commit/4024bbb6994fd4c12f6de4c8384c4857ffdc4caf))
* add busminder.reconnect service ([b90dcee](https://github.com/matt-richardson/home-assistant-bus-minder/commit/b90dcee75bef18200e8f5c486a68bb575bd87653))
* add BusMinderEntity base class with device_info; refactor sensor and device_tracker ([cc61150](https://github.com/matt-richardson/home-assistant-bus-minder/commit/cc611505408cf97144c264f5a849c5eff0df99c0))
* add BusMinderOptionsFlow for full reconfiguration ([92b52a8](https://github.com/matt-richardson/home-assistant-bus-minder/commit/92b52a8256a74bf88f5ff69b5a4e428eca861937))
* add connection_failed flag and repair issue management to coordinator ([0abfc62](https://github.com/matt-richardson/home-assistant-bus-minder/commit/0abfc62f5652dd3e28b6c7201dc3e232dc828076))
* add diagnostics platform with operator_url redaction ([844e68f](https://github.com/matt-richardson/home-assistant-bus-minder/commit/844e68f513b260d07b8142a3d1536c80afb44623))
* add integration brand icons and whats-next doc ([6ac5ca0](https://github.com/matt-richardson/home-assistant-bus-minder/commit/6ac5ca094c15ba6fcd80a4ad344154c0c8ccaebf))
* add next stop sensor ([f0b9e3d](https://github.com/matt-richardson/home-assistant-bus-minder/commit/f0b9e3d225327a5e76e8b98251e3939bf64b0a17))
* add options flow and repair issue strings to strings.json and translations ([df25787](https://github.com/matt-richardson/home-assistant-bus-minder/commit/df2578716280ca2e852b50f2c8f188834ce188e2))
* add PARALLEL_UPDATES, async_reload_entry, update listener to __init__.py ([e424868](https://github.com/matt-richardson/home-assistant-bus-minder/commit/e424868374211a0eef7a13909ecb96b80e709dcf))
* add stops-to-stop and distance sensors ([7e60172](https://github.com/matt-richardson/home-assistant-bus-minder/commit/7e60172886fbcaaa56365df2c3097f0360c6bbae))
* add Visit link to device page via configuration_url ([89dbe26](https://github.com/matt-richardson/home-assistant-bus-minder/commit/89dbe26015cfcc37b29acd615c1494be90f9dfa3))
* allow custom names for routes and stops ([e941640](https://github.com/matt-richardson/home-assistant-bus-minder/commit/e941640a8def066eaceb6cae39406f239c5bd10e))
* allow removing individual route devices from HA UI ([0d2926b](https://github.com/matt-richardson/home-assistant-bus-minder/commit/0d2926b3a2f0b0e14f4932f0e98d8a3b0768a3f7))
* async SignalR SSE client ([908e8c6](https://github.com/matt-richardson/home-assistant-bus-minder/commit/908e8c680c18fee594709518dd1adbe8505808fb))
* calculate distance along route stop sequence ([0708181](https://github.com/matt-richardson/home-assistant-bus-minder/commit/0708181b9071d5669262263e9cf1cd6fb92c3f0c))
* data models and polyline decoder ([cbea20c](https://github.com/matt-richardson/home-assistant-bus-minder/commit/cbea20c164d05be65638daf5e3408894e0ddc3e4))
* discover all route groups (AM and PM) from operator page ([e61365c](https://github.com/matt-richardson/home-assistant-bus-minder/commit/e61365cb1cbe036ff791356ea9bc27ab54aa05ba))
* ETA calculator with haversine distance and speed tracking ([2144540](https://github.com/matt-richardson/home-assistant-bus-minder/commit/2144540126a5e86319070f14dcb843c6efa0b8c8))
* ETA sensor and device tracker entities, wire up integration ([5f717be](https://github.com/matt-richardson/home-assistant-bus-minder/commit/5f717bedfc8b91fd71560b2638dc80a8df85b3db))
* implement Silver IQS compliance improvements ([c8888e5](https://github.com/matt-richardson/home-assistant-bus-minder/commit/c8888e563a32c38a7662490e8f34474ce326a637))
* mark sensor and device_tracker unavailable when coordinator.connection_failed ([e55f08c](https://github.com/matt-richardson/home-assistant-bus-minder/commit/e55f08c50710609b4096996a819a7293e10991e3))
* push-based coordinator with SSE reconnect ([5b3e25e](https://github.com/matt-richardson/home-assistant-bus-minder/commit/5b3e25ef9268b7b66fb9da5546aabe81cb4d9853))
* scraper to extract route group from operator URL ([32e6413](https://github.com/matt-richardson/home-assistant-bus-minder/commit/32e6413eb179f3325f47dba1884fe030f5492886))
* sequential per-route stop picking in config and options flows ([06bd76f](https://github.com/matt-richardson/home-assistant-bus-minder/commit/06bd76fee5b05aca49aa396c3b4f483c0cbbbc5c))
* update manifest.json to Silver tier; add icons.json ([ed2503f](https://github.com/matt-richardson/home-assistant-bus-minder/commit/ed2503fe616a4f6b4508334e88fb4695a8219d04))


### Bug Fixes

* annotate sensor entities list to satisfy mypy ([1105fde](https://github.com/matt-richardson/home-assistant-bus-minder/commit/1105fde9f1fe71bfc82fc14107397820aafe4482))
* correct route number extraction and service title ([96f739c](https://github.com/matt-richardson/home-assistant-bus-minder/commit/96f739c02fd56f100786506786bec8e1c35c319f))
* device tracker unavailable when no GPS position data ([f9d74c4](https://github.com/matt-richardson/home-assistant-bus-minder/commit/f9d74c4a819851734f0d2511e0f0655e892a0816))
* move pylint disable comment to hass argument line in diagnostics ([941f6ae](https://github.com/matt-richardson/home-assistant-bus-minder/commit/941f6ae8a902682f83933bbc32bc2b80b803fd02))
* notify entity listeners on connection_failed change; add PARALLEL_UPDATES to platform modules; use translation key for sensor name; fix device_tracker availability check ([27eb91e](https://github.com/matt-richardson/home-assistant-bus-minder/commit/27eb91e44c4286928352165e5e419086f99407f4))
* options flow defaults each route's stop picker to its own saved stop ([f5ec887](https://github.com/matt-richardson/home-assistant-bus-minder/commit/f5ec887a65d779ad6dd30e334fe0f570816b4fc2))
* prevent test hangs and scraper failures by patching SignalRClient in autouse fixture ([b04810b](https://github.com/matt-richardson/home-assistant-bus-minder/commit/b04810bf2a6a6c3375d95e5b46634ebfc69fb54d))
* resolve hassfest/HACS/black/flake8/mypy CI failures ([c9fe450](https://github.com/matt-richardson/home-assistant-bus-minder/commit/c9fe4507fc0b5363ee1d0ad93c3583b4cefa9e7c))
* resolve remaining hassfest and pylint CI failures ([d6beacc](https://github.com/matt-richardson/home-assistant-bus-minder/commit/d6beacc1d8cb335cebe8cdb36026677f5cf57b5b))
* sort routes by route number in config and options flow ([84a9f83](https://github.com/matt-richardson/home-assistant-bus-minder/commit/84a9f838eb7db64becaf28bcf826eb4b6d9869d7))
* strip deleted route from entry.options as well as entry.data ([7f8f447](https://github.com/matt-richardson/home-assistant-bus-minder/commit/7f8f4474b0014ffb1fca5e5ed1573dbbbee3f933))
* suppress pylint unused-argument for hass in HA platform callbacks ([2385cbf](https://github.com/matt-richardson/home-assistant-bus-minder/commit/2385cbf747c6c0a8017b670d011111f89584ed46))
* use HA-managed session in config flow to prevent lingering aiohttp threads ([8cdb536](https://github.com/matt-richardson/home-assistant-bus-minder/commit/8cdb5369083fb70b7864b7d492fcee6075cd2814))

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
