# What's Next

Ideas and deferred work for future iterations.

---

## Deferred from Silver Tier

- **GTFS schedule integration** — compare live bus position against the scheduled timetable to surface "running X minutes behind" as a sensor attribute.

## Quality / Certification

- **HACS submission** — submit to the HACS default repository once a release tag is cut.
- **Gold tier** — review the [Gold tier checklist](https://developers.home-assistant.io/docs/core/integration-quality-scale/checklist) and identify gaps.

## Features

- **Arrival notifications** — HA automation-friendly: fire an event or expose a binary sensor when the bus is N minutes away.
- **Multi-stop monitoring** — currently one monitored stop per config entry; allow selecting multiple stops.
- **Historical ETA accuracy** — track predicted vs actual arrival times over time (could be a Recorder-friendly sensor).

## Ops / Release

- **Cut 0.2.0 tag** — trigger release-please by pushing a tag, or manually create the GitHub release.
