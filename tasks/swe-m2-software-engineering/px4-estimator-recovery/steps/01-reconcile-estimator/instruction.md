# Reconcile PX4-style estimator frame resets

Build an offline tool that reconstructs a stationary North-East-Down (NED) frame from an exported estimator topic. The raw local position can jump when the estimator changes its frame. We need the physical trajectory through those jumps.

Put a modular Python package under `/app/px4_recovery`.

```bash
python3 -m px4_recovery replay --input CAPTURE.ndjson --output REPORT.json
```

Each line is an authored, decoded-ULog-style `vehicle_local_position` record. No binary ULog parser is needed. Fields are integer microsecond clocks `timestamp` (publication) and `timestamp_sample` (capture), three-element finite decimal arrays `position` and `velocity` in NED metres and m/s, `xy_valid` and `z_valid` booleans, 8-bit unsigned `xy_reset_counter` and `z_reset_counter`, `delta_xy` pair and `delta_z` scalar. The optional `anchor` is a simultaneous independent NED position, with null entries for unavailable axes. Publication times are nondecreasing, and capture times cannot exceed publication.

Process the inputs in publication order. The first sample establishes the initial frame and counter values. A sample with a timestamp at or below the last accepted capture is stale and has no effect. For each independent XY and Z group, a counter advance of exactly one modulo 256 reports a jump by the stated delta. Subtract the accumulated jump from measured positions. A larger advance leaves that group unresolved. Repeated counters do not reapply the previous delta. Invalid groups have no reported position, but their reset information still applies. A valid group with a complete anchor sets that group's frame offset and can clear its unresolved state. Both X and Y are required to anchor XY. Do not change velocity units or signs.

Write `{"rows":[{"timestamp_sample":integer,"position":[x_or_null,y_or_null,z_or_null]}],"stale":integer,"unresolved":integer}`. Emit one row per accepted sample. Count samples with at least one unresolved counter group in `unresolved`. Reject malformed input with a nonzero exit and preserve any existing report.
