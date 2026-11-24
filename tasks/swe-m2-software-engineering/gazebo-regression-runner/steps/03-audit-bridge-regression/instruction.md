# Diagnose a downstream simulator bridge regression

Keep both earlier commands. A trace recorded downstream may contain empty streams, dropped scheduled publications, wrong frame transforms, or lost reset epochs. Audit the observed evidence against the world and the declared run, even when the original simulator is unavailable.

```bash
python3 -m sim_regression audit --world WORLD.sdf --spec RUN.json --input TRACE.json --output REPORT.json
```

Read the trace from the prior interface. For each absolute step from zero to `steps-1`, compare the epoch-local clock to the declared reset schedule. Check that the expected set of topic names was delivered at their epoch-local cadence with each scheduled topic present once. Record a QoS mismatch when a known message's profile differs from `spec.qos`. Check each known message's frame ID and world pose against its configured static sensor extrinsic composed with the observed base pose. Use an absolute tolerance of 1e-7 on x/y/z and wrapped yaw. Trace pose and sensor values are observations, and the observed base does not have to match any precomputed trajectory.

Return `{"status":"ok"|"fault","first":{"clock":step_or_null,"topic":step_or_null,"qos":step_or_null,"transform":step_or_null}}`. Report each first fault independently. A missing step is both a clock and a topic fault. QoS and transform faults require a present message of a known topic. A still-present malformed transform field is a transform fault. Treat an entirely empty steps array as a missing stream, and reject duplicate step IDs, invalid absolute step ranges, or malformed structural inputs atomically.
