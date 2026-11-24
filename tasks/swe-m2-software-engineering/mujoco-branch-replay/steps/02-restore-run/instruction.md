# Resume from a simulation checkpoint

A pose trace is useful for debugging, but resuming from joint position and
velocity alone can change contact behavior. Extend the tool so a researcher
can hand a complete simulation checkpoint to a different process. Keep
`trace` working.

```bash
python3 -m simbranch resume --spec SPEC.json --output REPORT.json
```

Accept the trace fields `model`, `end`, `updates`, and `sample_ticks`.
Add an optional `checkpoint` with `model_id`, `tick`, and `integration`.
The integration array uses MuJoCo's native integration-state order. It
includes actuator dynamics, inputs retained by the simulator, and the
solver's warm-start state. Without a checkpoint begin at tick zero using
a fresh data object. With a checkpoint use the declared tick as the start.
The checkpoint must match the compiled model fingerprint and the native
integration-state size. Its time must agree with `tick * timestep` within
`1e-9` seconds. Require all samples and updates to be within the resumed
window.

Add `checkpoint_ticks` using the same boundary and ordering rules as
`sample_ticks`. The output adds a `checkpoints` list of complete checkpoint
records sorted by tick. A new continuation from a saved boundary must
produce the same samples and checkpoints as the equivalent uninterrupted
run. Preserve the malformed-input and atomic-output rules.
