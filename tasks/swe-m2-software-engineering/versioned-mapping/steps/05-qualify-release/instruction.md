# Qualify a map release with live canary routes

Before we activate a map, run a few surveyed routes against that version.
A physical guard can stop the robot before a newly blocked cell, and a
separate survey stream grades localization. Add route planning, promotion,
and rollback to `/app/versioned_mapping`. Keep the earlier mapping and
release commands available.

```bash
python3 -m versioned_mapping route --store STORE --version VERSION --request REQUEST.json --output PLAN.json
python3 -m versioned_mapping review --store STORE --request REQUEST.json --output DECISION.json
```

## Route planning

The request contains integer cells `start` and `goal` in `[x,y]` order, and
a list of blocked cells from the physical guard. Use the exact pinned
snapshot. Use cells marked "free" in the map format from the first step. Traverse free cells by their four
grid neighbors. Avoid supplied blocked cells even when the map marks them
free. Return `{"version": id, "path": [[x,y], ...]}` with a shortest legal
route, including both endpoints, or `"path": null` if none exists.

## Release review

The request has `action` (`"promote"` or `"rollback"`), `candidate`,
`expected_active`, `fallback` (three stored version IDs), and nonempty
`routes`. For a rollback, the expected active version is the candidate.
Every route has a unique `id`, `start`, `goal`, positive integer
`max_moves`, nonnegative `max_error_m`, and `observations` in dispatch order.

An observation has `sequence` starting from 1, `version` of the pinned map,
`from`, `requested`, `measured`, `result`, and finite nonnegative
`error_m` from the independent survey. The requested cell must be a free
neighbor of the measured starting cell. For `"arrived"` the measured
cell is the requested cell. For `"guarded"` the robot stayed at `from`.
Treat the requested cell as blocked for the rest of that route. For
`"collision"` the measured cell is the requested cell and the route
fails. Never credit repeated requests into a guarded cell.

A complete route starts at its commissioned start, stays pinned to the
candidate, finishes at its goal within `max_moves` attempts, including guarded attempts, and keeps survey error
at or below its limit. A collision, incomplete route, invalid movement,
or exceeding an error limit fails the route. Observations after a
route reaches its goal also fail it.

Return `{"status": ...,"active_version": id, "routes": {id: bool}}`.
Promote only when every route passes. Roll back to `fallback` when any
route fails with the candidate active. Use the existing atomic
compare-and-swap contract. The status is `"promoted"`, `"rolled_back"`,
`"held"` when the report calls for no pointer change, or `"stale"` if
the expected active version changed. Pinned reads still return their
original snapshot after a review.

Write the plan and decision files outside the map store. Reject malformed requests and unknown top-level stored versions with a nonzero
exit and preserve the old report and snapshots. Well-formed observations
that fail qualification produce a decision. Keep path search, review
and publication logic modular.
