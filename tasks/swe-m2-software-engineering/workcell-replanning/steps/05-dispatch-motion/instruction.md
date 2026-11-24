# Dispatch one command against the current forecast

Our machine controller needs one authorized primitive at a time. It can restart
after writing a command, retransmit a request whose reply was lost, or cancel an
issued transfer when a new fixture forecast arrives. Add a supervisor that
keeps enough durable state to handle those cases. Keep the existing commands
and use the same geometry, dynamics and time window for planning.

```bash
python3 -m workcell dispatch --spec SPEC.json --state STATE.json --output REPORT.json
```

## Requests from the machine controller

Each request has a nonempty string `mission_id`, a positive integer `sequence`,
a nonnegative integer `revision` for the authority forecast, a `window` in
the `plan-window` input format, and a `previous` field. The first request for
each mission has sequence 1 and `previous: null`. Each accepted new request
increments the sequence by one. Use a single state file for multiple missions.

- If the last reply issued a command, `previous` identifies it with
  `{"command_id":string,"outcome":"completed"}` when it finished.
  The supplied measurement must be at that command's end tick and
  end pose, at rest. Compare pose coordinates to within `1e-8`.
- With a newer forecast revision, the controller can instead send
  `{"command_id":string,"outcome":"cancelled"}`. The measurement tick must
  be within the issued interval, including its start and excluding its end.
  Use this measurement and the current forecast for the replacement. It may
  include nonzero joint velocity.
- If the last reply had no command, the next request uses `previous: null`.
- Revisions cannot go backwards. With the same revision, the window stays
  the same except for `measured`, `start_node` and `brake_ticks`. With a
  newer revision use the newly supplied window.

## Decisions and restart

Write a JSON object containing `mission_id`, `sequence`, `revision`, `status`,
`command` and `command_id`. Echo the mission, sequence and revision from
the request. For an accepted request, use the planning status and issue only
the first command in the plan, if there is one. `command_id` is an opaque
nonempty string, distinct from earlier command IDs for this mission. Use null
for both command fields if the plan is empty.

A retransmission of the most recently accepted request for that mission must
return the identical decision and command ID. Compare JSON contents, ignoring
object key order. An older sequence, a skipped sequence, changed contents at
the latest accepted sequence, a stale revision or invalid acknowledgement
returns status `rejected` with both command fields null. A rejection does not
advance the state.

The state file will initially be absent. Accepting a decision must persist it
before returning the reply so a process restart or lost output can be recovered
with a retransmission. A failed reply write returns a nonzero exit code and
leaves the accepted decision available for a retry. Concurrent invocations
sharing a state file must behave
as though processed in some serial order. Keep other missions intact and reject
malformed input with a nonzero exit and both existing files unchanged. The
controller executes a command ID at most once and supplies its next measured
state in a new request. The supervisor writes commands for the controller to
execute.
