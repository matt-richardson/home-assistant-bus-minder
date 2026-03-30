# BusMinder — Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Live school bus tracking for Home Assistant, powered by [BusMinder](https://busminder.com.au).

## Features

- **ETA sensor** — minutes until the bus reaches your stop
- **Map tracker** — live bus position on the HA map card
- Works with any BusMinder-based operator (Ventura Bus Lines, etc.)

## Installation

1. In HACS → Integrations → ⋮ → Custom repositories
2. Add `https://github.com/YOUR_GITHUB_USERNAME/hass-busminder` as an Integration
3. Install "BusMinder"
4. Restart Home Assistant
5. Settings → Devices & Services → Add Integration → BusMinder

## Setup

1. Find your school's live tracking URL from the bus operator's website
   (e.g. `https://your-operator.com.au/live-tracking/your-school/`)
2. Paste it into the integration setup
3. Select the routes to monitor
4. Select your stop

## Entities

| Entity | Description |
|--------|-------------|
| `sensor.busminder_3428_eta` | Minutes until route 3428 arrives at your stop |
| `device_tracker.busminder_3428` | Live GPS position of route 3428 |

The ETA sensor has attributes: `bus_number`, `latitude`, `longitude`, `last_updated`, `status`.

`status` values: `approaching` (en route), `passed` (bus has passed your stop), `not_running` (no GPS update in 5 minutes).
