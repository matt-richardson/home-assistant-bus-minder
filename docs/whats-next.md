# What's Next

Ideas and deferred work for future iterations.

---

## Quality / Certification

- **HACS submission** — submitted ([hacs/default#6691](https://github.com/hacs/default/pull/6691)), pending review.
- **Gold tier** — review the [Gold tier checklist](https://developers.home-assistant.io/docs/core/integration-quality-scale/checklist) and identify gaps.

## Features

- **Historical stop-time ETA** — record actual arrival times at each stop over time, then use that history as the ETA source instead of the current haversine/speed estimate, which is unreliable. The current method doesn't account for route shape, traffic patterns, or scheduled dwell times.
- stop buses appearing outside of their scheduled times

## Deferred

- **Arrival notifications** — HA automation-friendly: fire an event or expose a binary sensor when the bus is N minutes away.
- **Multi-stop monitoring** — currently one monitored stop per config entry; allow selecting multiple stops.
- **GTFS schedule integration** — compare live bus position against the scheduled timetable to surface "running X minutes behind" as a sensor attribute.
