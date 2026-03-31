# BusMinder for Home Assistant

[![HACS][hacs-badge]][hacs-url]
[![CI][ci-badge]][ci-url]
[![codecov][codecov-badge]][codecov-url]

Track live school bus arrival times and GPS positions from [BusMinder](https://busminder.com.au/) in Home Assistant.

[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[hacs-url]: https://hacs.xyz
[ci-badge]: https://github.com/matt-richardson/home-assistant-bus-minder/actions/workflows/validate.yaml/badge.svg
[ci-url]: https://github.com/matt-richardson/home-assistant-bus-minder/actions/workflows/validate.yaml
[codecov-badge]: https://codecov.io/gh/matt-richardson/home-assistant-bus-minder/branch/main/graph/badge.svg
[codecov-url]: https://codecov.io/gh/matt-richardson/home-assistant-bus-minder

## Features

- **ETA sensor** — minutes until the bus arrives at your stop
- **Device tracker** — live GPS position on the Home Assistant map
- **Device grouping** — one device per route in Settings → Devices & Services
- **Options flow** — reconfigure operator URL, routes, and stop at any time
- **Repair issues** — notified in HA UI when the live feed is persistently unavailable
- **Diagnostics** — downloadable diagnostics from the HA UI

## Requirements

- Home Assistant 2024.1+
- A school or operator using [BusMinder](https://busminder.com.au/)

## Installation

### Via HACS (recommended)

1. Open HACS → Integrations → ⋮ → Custom repositories
2. Add `https://github.com/matt-richardson/home-assistant-bus-minder` as an **Integration**
3. Search for **BusMinder** and install
4. Restart Home Assistant

### Manual

1. Copy `custom_components/busminder/` into your HA `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **BusMinder**
3. Enter your operator's live tracking URL (e.g. `https://your-operator.com.au/live-tracking/your-school/`)
4. Select the routes you want to monitor
5. Select your stop

### Reconfiguration

To change the URL, routes, or stop after setup:

1. Go to **Settings → Devices & Services**
2. Find BusMinder and click **Configure**
3. Complete the 3-step sequence again with your new selections

## Entities

Each monitored route creates a **device** in Home Assistant with two entities:

| Entity | Type | Description |
|--------|------|-------------|
| `sensor.busminder_{route}_eta` | Sensor | Minutes until bus arrives at your stop |
| `device_tracker.busminder_{route}` | Device Tracker | Live GPS position |

### ETA Sensor Attributes

| Attribute | Description |
|-----------|-------------|
| `bus_number` | Bus registration number |
| `status` | `approaching`, `passed`, or `not_running` |
| `latitude` | Current bus latitude |
| `longitude` | Current bus longitude |
| `last_updated` | ISO timestamp of last GPS update |

## Troubleshooting

### Diagnostics

1. Go to **Settings → Devices & Services**
2. Find BusMinder and click the device
3. Click **Download Diagnostics**

The diagnostics file shows coordinator state and current positions. The operator URL is redacted.

### Repair Issues

If the live feed fails for several consecutive attempts, a **repair notification** appears in the HA UI. Check:

- The operator tracking URL is still valid
- The BusMinder service is reachable from your HA instance
- The HA instance has internet access

The notification dismisses automatically when the connection is restored.

### Common Issues

**No data / sensor unavailable** — the SSE connection may still be establishing. Wait 30 seconds and reload. If the issue persists, check the repair notification.

**Wrong stop** — use the Configure button to reconfigure and select a different stop.

## Development

### Setup

```bash
git clone https://github.com/matt-richardson/home-assistant-bus-minder
cd home-assistant-bus-minder
./setup-venv.sh
source venv/bin/activate
```

### Daily workflow

```bash
./dev.sh test          # run all tests
./dev.sh test-cov      # run with coverage (must stay ≥95%)
./dev.sh lint          # black/isort/flake8/pylint/mypy
./dev.sh format        # auto-format
./dev.sh validate      # format + lint + test-cov
```

### Contributing

This project uses [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add something new
fix: fix a bug
chore: tooling, deps, CI changes
docs: documentation only
test: add or update tests
```

Open a pull request against `main`. CI must pass before merge.
