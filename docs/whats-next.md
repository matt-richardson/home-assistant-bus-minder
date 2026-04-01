# What's Next

Ideas and deferred work for future iterations.

---

## Deferred from Silver Tier

- **Multiple config entries** — already supported by design but no integration tests covering it. Add a test with two config entries to confirm they don't interfere.
- **GTFS schedule integration** — compare live bus position against the scheduled timetable to surface "running X minutes behind" as a sensor attribute.
- **Custom HA services** — e.g. `busminder.refresh` to force an immediate SSE reconnect without restarting the integration.

## Quality / Certification

- **HACS submission** — submit to the HACS default repository once a release tag is cut.
- **Gold tier** — review the [Gold tier checklist](https://developers.home-assistant.io/docs/core/integration-quality-scale/checklist) and identify gaps.

## Features

- **Arrival notifications** — HA automation-friendly: fire an event or expose a binary sensor when the bus is N minutes away.
- **Multi-stop monitoring** — currently one monitored stop per config entry; allow selecting multiple stops.
- **Historical ETA accuracy** — track predicted vs actual arrival times over time (could be a Recorder-friendly sensor).

## Ops / Release

- **Cut 0.2.0 tag** — trigger release-please by pushing a tag, or manually create the GitHub release.
- **Codecov badge** — add `CODECOV_TOKEN` secret to GitHub repo settings so the coverage badge in README resolves.
