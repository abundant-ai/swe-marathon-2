# Resume after a workcell update

When a fixture moves during execution, we need to decide whether the remaining path still works and, if necessary, find a replacement. Add recovery from the robot's measured state. Keep the scene and motion-checking commands working.

```bash
python3 -m workcell recover --spec SPEC.json --output REPORT.json
```

The spec contains `robot`, `initial_scene`, `events`, and `margin_m` with the same meanings as before. The initial scene already includes any load held at the time the original plan was made. Apply its events before making the recovery decision.

- `planned_revision` is the integer revision the old path was issued against. It must equal `initial_scene.revision`.
- `remaining` is the unexecuted trajectory the controller supplied, in the waypoint format from the motion checker. Its first joint position can differ from the current measurement.
- `measured_q` is the current joint reading. `goal_q` is the required final joint position, also the last configuration of `remaining`.

Write `{"revision":integer,"status":string,"trajectory":array_or_null}` for the reconciled scene revision.

- `unchanged` returns `remaining` exactly when it starts at `measured_q` and passes the motion check against the reconciled scene. A new revision alone does not require a different trajectory.
- `replanned` returns a newly timed trajectory from the measured position to the goal. It must pass the same continuous motion check under the new scene and preserve its attachment.
- `stopped` returns null if the measured pose or goal is invalid in the new scene, or if bounded planning cannot find a path. Make a substantive attempt to find a feasible route on obstructed but reachable workcells. Returning a reason is optional.

Use a CPU-only planner. The input is static within its final scene revision. Recovery plans are for offline review before execution. Inputs include clear direct paths, scenes that require detours, and cases where motion cannot begin safely. Preserve the preceding malformed-input and atomic-output rules.
