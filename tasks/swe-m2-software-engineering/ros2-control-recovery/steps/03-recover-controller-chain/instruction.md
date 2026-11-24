# Recover through a failed switch or a supervisor restart

Run the same planner behind a small durable controller supervisor.
The supervisor must tolerate a lost reply and a device returning with a
new hardware generation. Continue serving independent controller chains
and keep the `inspect` and `plan` commands available.

```bash
python3 -m control_recovery recover --spec SPEC.json --state STATE --output REPORT.json
```

The request adds `run_id` (nonempty string), `sequence` (positive integer),
and `previous` to the prior input. A new run starts with sequence 1 and
`previous: null`. Each subsequent accepted request increments the sequence
by one. The hardware and controller definitions stay fixed for a run.
The service groups may change. Device generations cannot decrease.

If a prior reply issued a primitive, use
`previous: {"id": command_id, "outcome": outcome}`. The remainder of the
request contains the current hardware and controller readback.

- `applied` confirms a start or stop only if the named controller is
  respectively active or inactive. For a mode switch, the device must
  be ready in the requested mode and at the issued generation.
- `failed` applies only to a mode command where the generation is current
  and readback has a different mode. Treat the failed device-and-mode
  combination as unavailable until that device advances to a new
  generation. Recompute service coverage and use a viable fallback.
- `obsolete` applies only to a mode command whose device now reports a
  greater generation. Discard the old authority and plan from the new
  reading.

When there was no issued primitive, the next request has `previous: null`.
Reject a stale or skipped sequence, modified duplicate, stale generation,
wrong command ID, or inconsistent readback. An exact retransmission of the
latest accepted request returns its original decision.

Add `run_id`, `sequence`, `status`, and `command_id` to the plan reply.
For `issued`, use a nonempty command ID distinct within the run. For
`settled`, use null command and command ID. For `rejected`, use an empty
`selected` object and null command and command ID. Rejections do not
advance the journal.

The state path starts absent and serves multiple runs. Persist accepted
decisions before publishing a reply. A failed reply write returns a
nonzero exit, and a retry can recover the decision. Concurrent
invocations on one state path must behave as if serialized. Malformed
requests leave both existing files intact. Use distinct state and output
paths.
