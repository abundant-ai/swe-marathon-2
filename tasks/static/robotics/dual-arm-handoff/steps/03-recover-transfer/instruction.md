# Recover a transfer after a fixture forecast changes

A forecast can change while an authorized move is in progress.
Preserve who owns the load, replan from the actual measured velocity,
and issue one primitive against current authority. Keep the certifier
and planner working. Persist the decision before publishing its reply.

```bash
python3 -m dual_arm dispatch --spec SPEC.json --state STATE.json --output REPORT.json
```

The spec has `mission` (nonempty string), `sequence` (positive integer),
`revision` (nonnegative integer), `window` (the complete planning input)
and `previous`. The initial sequence is 1 with `previous: null`.
Subsequent accepted sequences increment by one. Revisions and measurement ticks never decrease on accepted new requests. Within a revision, only `measured`, `start_node` and
`brake_ticks` may change. A newer revision can replace fixture
forecasts and commissioned poses.

When a command was issued, `previous` is
`{"id": command_id, "outcome": "completed"|"withdrawn"}`. A completed
command requires the planned end tick, expected end pose and owner,
and zero measured velocities. A withdrawn command must have been a
move, the revision must be newer, and the measurement tick must be
at or after its start and before its end. The reported owner must be
the owner at move issuance. Start the replacement from the measured
state. A handoff can only be confirmed at its successful end. If the
previous reply issued no command, use `previous: null`.

For an accepted request, run the planner against the updated window.
Echo `mission`, `sequence` and `revision` and return status
`"issued"`, `"ready"` for an already completed mission, or `"blocked"`.
Include `command` and `command_id`. An issued decision contains just
the first command of the feasible plan and a distinct nonempty ID.
Use null for both fields when no command is issued.

A retry with identical JSON contents at the last accepted sequence
returns exactly its saved decision. Reject stale or skipped sequences,
changed duplicate requests, invalid acknowledgements and inconsistent
readback with status `"rejected"` and null command fields. A rejection
does not advance authority. Malformed input fails with a nonzero exit
and preserves the state and reply files. Serialize concurrent updates
to the same state file. Use distinct state and output paths.
