# BusMinder Silver Tier Uplift — Design Spec

**Date:** 2026-03-30
**Goal:** Bring the BusMinder integration to HA Silver tier quality, matching the sibling projects (home-assistant-firefly-cloud, home-assistant-qustodio).

---

## Background

The BusMinder integration was built with working core logic (35 tests, SignalR SSE client, config flow, ETA sensor, device tracker) but lacks the quality infrastructure and HA-specific features required for Silver tier certification.

Reference: [HA Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/checklist)

---

## Scope

### In scope
- All Bronze and Silver tier checklist items
- Device registry (grouping entities per route under a named device)
- Full options flow (reconfigure operator URL, routes, and stop after setup)
- 95%+ test coverage enforced in CI
- Release automation (release-please + Conventional Commits)
- Full CI/CD tooling (linting, formatting, type checking, multi-Python)
- Pre-commit hooks (including markdownlint and yamlfmt)
- Dev helper scripts
- Diagnostics platform
- Repair issues notifications
- CLAUDE.md
- README depth uplift

### Out of scope
- Reauthentication flow (BusMinder has no credentials — the options flow covers URL changes)
- Multiple config entries per HA instance (already supported by design, not tested)
- GTFS schedule integration ("running behind" vs schedule)
- Custom HA services

---

## File Structure Changes

### New files

```
custom_components/busminder/
├── entity.py              Base class with device_info, shared by sensor + device_tracker
├── exceptions.py          BusMinderError hierarchy
├── diagnostics.py         Diagnostics platform
└── icons.json             Entity icon definitions

tests/
└── test_diagnostics.py

# Root tooling
.pre-commit-config.yaml
CLAUDE.md
CHANGELOG.md               Bootstrapped at 0.2.0
release-please-config.json
dev.sh
setup-venv.sh

.github/workflows/
└── release-please.yml
```

### Modified files

```
custom_components/busminder/
├── __init__.py            Add PARALLEL_UPDATES, async_reload_entry
├── coordinator.py         Add repair issues, connection error flag
├── sensor.py              Inherit from BusMinderEntity, improve unavailable state
├── device_tracker.py      Inherit from BusMinderEntity, add unavailable state
├── config_flow.py         Add BusMinderOptionsFlow (full reconfiguration)
├── manifest.json          Add integration_type, quality_scale, requirements, bump to 0.2.0
├── strings.json           Add options flow strings, repair issue strings, more error keys
└── translations/en.json   Mirror strings.json

# Root
.github/workflows/validate.yaml   Replace stub with full CI pipeline
pyproject.toml                     Add tool config (black, isort, mypy)
requirements-dev.txt               Add coverage, linting deps
README.md                          Full depth uplift
```

---

## Section 1: Tooling & CI

### GitHub Actions — `validate.yaml`

Triggers on push and pull_request. Steps per Python version (3.12, 3.13):

1. Checkout + setup Python
2. Install `requirements-dev.txt`
3. `black --check .`
4. `isort --check-only .`
5. `flake8 .`
6. `pylint custom_components/busminder`
7. `mypy custom_components/busminder`
8. `pytest --cov=custom_components.busminder --cov-fail-under=95`
9. Upload coverage to codecov.io (requires `CODECOV_TOKEN` secret in GitHub repo settings)
10. hassfest (`home-assistant/actions/hassfest@master`)
11. HACS validation (`hacs/action@main`)

### GitHub Actions — `release-please.yml`

Triggers on push to `main`. Uses `google-github-actions/release-please-action`. Bumps `CHANGELOG.md` and `manifest.json` version from Conventional Commit messages.

### Pre-commit hooks (`.pre-commit-config.yaml`)

- **black** — code formatting
- **isort** — import ordering (profile: black)
- **flake8** — style/lint
- **mypy** — type checking
- **markdownlint** — markdown consistency
- **yamlfmt** — YAML formatting

### Tool configuration (`pyproject.toml`)

```toml
[tool.black]
line-length = 120

[tool.isort]
profile = "black"
line_length = 120

[tool.mypy]
python_version = "3.12"
check_untyped_defs = true
ignore_missing_imports = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["."]
```

### Dev scripts

**`dev.sh`** commands: `test`, `test-cov`, `test-single`, `lint`, `format`, `validate`, `install`, `help`

**`setup-venv.sh`** — creates venv, installs `requirements-dev.txt`, runs pre-commit install.

---

## Section 2: Bronze Tier Gaps

### `manifest.json`

Add:
- `"integration_type": "service"`
- `"quality_scale": "silver"`
- `"requirements": ["aiohttp>=3.9"]`
- `"version": "0.2.0"`

### `icons.json`

```json
{
  "entity": {
    "sensor": {
      "eta": { "default": "mdi:bus-clock" }
    },
    "device_tracker": {
      "_": { "default": "mdi:bus" }
    }
  }
}
```

Note: the `"eta"` key requires `_attr_translation_key = "eta"` set on `BusEtaSensor`. Add this when implementing `entity.py`.

### `entity.py` — Base entity class

```python
class BusMinderEntity(CoordinatorEntity[BusMinderCoordinator]):
    """Base entity for BusMinder, providing shared device_info."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, trip_id, route_number, route_name):
        super().__init__(coordinator)
        self._trip_id = trip_id
        self._route_number = route_number
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{trip_id}")},
            name=route_name,
            manufacturer="BusMinder",
            entry_type=DeviceEntryType.SERVICE,
        )
```

Both `BusEtaSensor` and `BusTrackerEntity` inherit from `BusMinderEntity`.

### `exceptions.py`

```python
class BusMinderError(Exception): pass
class BusMinderConnectionError(BusMinderError): pass
class BusMinderParseError(BusMinderError): pass
```

Used in `scraper.py` (replaces `ScraperError` — rename throughout including existing tests) and `coordinator.py`. Config flow catches `BusMinderConnectionError` → `cannot_connect` error key.

### `__init__.py`

Add:
- `PARALLEL_UPDATES = 1`
- `async_reload_entry()` — calls unload then setup
- `async_update_options()` — calls reload on options change

### `CLAUDE.md`

Documents:
- Architecture overview (component responsibilities)
- Development workflow (`source venv/bin/activate && ./dev.sh test`)
- Commit format (Conventional Commits: `feat:`, `fix:`, `chore:`, `docs:`)
- Testing strategy (TDD, mocking patterns)
- Entity naming conventions (`sensor.busminder_{route_number}_eta`)
- Silver tier checklist reference

---

## Section 3: Silver Tier Features

### Options flow (`config_flow.py`)

`BusMinderOptionsFlow` class registered via `async_get_options_flow()`. Re-runs the same 3-step sequence as the config flow (URL → routes → stop), pre-populated with current config entry values. On completion, calls `async_reload_entry` to apply changes immediately.

Steps:
- `async_step_init` → redirects to `async_step_user` (pre-fills current URL)
- `async_step_pick_routes` (pre-selects current routes)
- `async_step_pick_stop` (pre-selects current stop)

### Repair issues (`coordinator.py`)

```python
RECONNECT_THRESHOLD = 3  # failures before raising a repair issue

# On persistent failure:
ir.async_create_issue(
    hass, DOMAIN, "connection_failed",
    is_fixable=False,
    severity=IssueSeverity.WARNING,
    translation_key="connection_failed",
    translation_placeholders={"operator_url": entry.data[CONF_OPERATOR_URL]},
)

# On recovery:
ir.async_delete_issue(hass, DOMAIN, "connection_failed")
```

### Diagnostics (`diagnostics.py`)

```python
TO_REDACT = {CONF_OPERATOR_URL}  # fully redacted in diagnostics output

async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    return {
        "config": async_redact_data(entry.data, TO_REDACT),
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "monitored_routes": list(coordinator._monitored_trip_ids),
            "positions": {
                trip_id: {"lat": pos.lat, "lng": pos.lng, "bus_reg": pos.bus_reg}
                for trip_id, pos in (coordinator.data or {}).items()
            },
        },
    }
```

### Entity unavailable states

- `BusEtaSensor.available`: `False` when no position data OR coordinator has persistent connection error
- `BusTrackerEntity.available`: same — currently always `True` regardless of data

Add `coordinator.connection_failed: bool` flag, set by the repair issue logic.

### Translations (`strings.json`) additions

- Options flow step strings (mirrors config flow)
- `issues.connection_failed.title` / `.description`
- Error keys: `operator_url_changed`, `parse_error`

### 95% coverage

New/expanded tests needed:
- `test_diagnostics.py` — diagnostics output, redaction
- `test_config_flow.py` — options flow (all steps, pre-population, error paths)
- `test_coordinator.py` — repair issue creation after 3 failures, auto-dismissal on recovery, `connection_failed` flag
- `test_sensor.py` — unavailable when `connection_failed` is True
- `test_device_tracker.py` — unavailable state
- `test_init.py` — `async_reload_entry`, `async_update_options`

---

## Section 4: Documentation

### `README.md`

Sections:
- Badges (HACS, CI, codecov)
- Features
- Installation (HACS primary, manual fallback)
- Configuration (step-by-step, options flow)
- Entities table + attributes
- Development setup (`setup-venv.sh`, `./dev.sh help`, pre-commit install)
- Contributing (Conventional Commits, PR process)
- Troubleshooting (diagnostics, common issues)

### `CHANGELOG.md`

Bootstrapped at `0.2.0` listing all features delivered in the initial build. Future releases automated by release-please.

### `release-please-config.json`

```json
{
  "release-type": "simple",
  "extra-files": ["custom_components/busminder/manifest.json"]
}
```

---

## Implementation Sequence

Work through in order:

1. **Tooling** — CI, pre-commit, pyproject.toml, dev.sh, setup-venv.sh, requirements-dev.txt, CLAUDE.md
2. **Bronze gaps** — manifest.json, icons.json, exceptions.py, entity.py, __init__.py updates
3. **Silver features** — options flow, repair issues, diagnostics, entity unavailable states, translations
4. **Coverage uplift** — new tests to reach 95%+
5. **Documentation** — README, CHANGELOG, release-please

---

## Success Criteria

- [ ] `./dev.sh test-cov` passes at 95%+
- [ ] `./dev.sh lint` passes with no errors
- [ ] All GitHub Actions pass on push to main
- [ ] Settings → Devices & Services shows one device per monitored route
- [ ] Options flow allows full reconfiguration
- [ ] Diagnostics downloadable from HA UI
- [ ] Repair issue appears after 3 consecutive SSE failures
- [ ] CHANGELOG.md present and release-please configured
- [ ] README matches sibling depth
