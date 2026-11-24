# Dispatch two shared freight lifts after an interrupted shift

Parcels can now cross floors on two lifts. A flexible fleet can reach
either lift, while a fixed-route robot may reach only one. Plan the lift
trips jointly and release only trips that can start now. When a reply is
lost, an existing grant continues to hold the car until a matching
physical report resolves it. Keep the earlier coordinator available.

```bash
python3 -m fleet_recovery elevators --request REQUEST.json --state STATE.json --output REPORT.json
```

## Calendar and requests

Each complete request contains a nonempty `event_id`, a nonnegative
integer `tick`, `lifts`, and `jobs`. Each lift ID maps to:

- `travel` and `dwell`, positive integers for ticks per floor and ticks
  for each loading or unloading visit.
- `windows`, nonoverlapping open intervals `[begin,end]`. Empty means
  the lift cannot move. An entire trip, including empty positioning
  and both dwells, must fit inside one window. It may finish at the end.
- `report`, with nonnegative integer `sequence`, integer `floor` or
  null, and `settled` null or `{"id": grant_id, "outcome": "delivered"|"returned"}`.

Floors are integers from 0 to 20. The lift IDs, travel durations and
dwells stay fixed across a shift. Availability windows may change.
A job has `id`, `robot`, distinct `origin` and `destination` floors,
`ready`, `deadline`, and a nonempty list `lifts` of usable lift IDs.
At most eight jobs and two lifts are supplied. A robot has at most
one job in the request. `ready` and `deadline` are nonnegative ticks
with `ready <= deadline`. Jobs keep their original fields under a given ID. A job may disappear from a later request,
but withdrawing it cannot revoke an issued grant.

## Plan and release

A trip records `job`, `robot`, `lift`, `depart`, `pickup`, and `settle`.
Starting from the car's current floor and earliest availability, depart
within a permitted window. If the parcel is unavailable on arrival,
the car may wait at the pickup floor. The pickup tick is no earlier
than empty travel completion and job readiness. After pickup there is
one dwell, loaded travel to the destination and one dwell. Record
the end as `settle`, no later than the job's deadline. Further planned
trips on that car start from the preceding destination.

Return `{"plan": [...], "grants": [...], "completed": [...]}`. Plan trips
in chronological order, maximizing the number of feasible outstanding
jobs, then minimizing the last settlement tick. Any equal optimum
is accepted. A car held by an issued grant or with an unknown floor
is unavailable for planning. Skip already completed or granted jobs
and jobs for a robot whose grant is pending. `grants` are exactly the
planned trips departing at the request tick, with an additional unique
nonempty `id` each. Future plan entries are estimates. Include all
confirmed job IDs in `completed`, sorted.

## Recovery

Persist the issued grant, its last observed sequence, the start and
destination floors, the disposition of jobs, and the response for
every accepted event before writing the reply. A retransmission with
the same event ID and JSON contents returns its original response.
Reject changed contents under an existing event ID or a new event
with a tick earlier than the last accepted tick. Ignore stale lift
reports at or below the last accepted sequence.

Only a fresh matching settlement can release a held lift. For
`"delivered"`, require the destination floor and a tick at least
`settle`, then complete the parcel. A matching `"returned"` requires
the original car floor and frees the lift without completing the job.
Missing, stale, prematurely delivered, foreign and contradictory evidence leaves a grant held. A fresh delayed settlement can still resolve it.
A later calendar update never frees an occupied car. Keep unrelated
cars available. Apply the new request atomically. Malformed input
leaves any previous state and reply unchanged. The state initially
does not exist. Keep the supervisor and scheduling code modular.
