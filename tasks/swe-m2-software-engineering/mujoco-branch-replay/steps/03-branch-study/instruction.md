# Run a branch study across process restarts

A researcher wants to compare recovery controllers by forking from earlier
states in the same rollout. Add a durable job store in `/app/simbranch`.
It should support independent branches, replaying a completed request, and
submitting later jobs after the original worker exits. Keep the other
commands available.

```bash
python3 -m simbranch study --spec SPEC.json --state STATE --output REPORT.json
```

The spec has `model` in the same format as before and `runs`, an array of
requests. Each has a nonempty path-independent string `id`, integer
`end`, `updates`, `sample_ticks`, `checkpoint_ticks`, and `parent`.
Use `parent: null` to start from reset. For a branch, use
`{"id": parent_id, "tick": checkpoint_tick}`. The parent must have saved
that checkpoint. Parents may appear later in the same request or in an
earlier completed request. A child uses the parent's saved state before
the boundary's updates, so its inputs at the fork can differ from inputs
the parent applied at that tick. Fields and tick rules are otherwise the
same as for `resume`.

The state path starts absent and belongs to one compiled model. Persist
completed runs by ID and compare the full requested run contents on retry.
An exact retry returns the original report. Reject a changed request using
a saved ID, an unknown parent or checkpoint, cycles, or a different model.
Reject duplicate IDs within one request. A request with any invalid run
leaves the original state and output files intact. Commit the whole study
before publishing the output so a lost response can be retried. Concurrent
processes using the same state path must behave as if run serially. Use
distinct state and output paths.

Return `{"model_id": string, "runs": {id: resume_report}}` for just the
requested IDs. Each branch must restore its own state and retain the native
time, controls, and warm-start data at its fork. Running siblings in a
different order must give the same reports.
