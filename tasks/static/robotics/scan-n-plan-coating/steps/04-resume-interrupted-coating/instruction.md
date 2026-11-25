# Resume coating after a stopped pass

Add a supervisor to `/app/coating` that can finish a part after the cell interrupts a coating pass. It must decide which material was actually delivered, wait for the old command to stop, and continue from the measured arm and positioner state. An operator can supply a new registered part pose if the fixture is re-indexed while spraying is disabled. Keep the three earlier commands working.

```bash
/app/coating supervise --job JOB.json --registration REGISTRATION.json --state STATE_DIR
```

Use a fresh state directory for each mission and preserve it when restarting that mission. The initial job, recipe, and registration use the existing format. The mission clock starts at zero and its deadline is `motion.max_duration_ns`. The job's `motion.state_max_age_ns` is the inclusive age limit for a controller observation that grants motion. `motion.stop_velocity_rad_s` is the inclusive absolute speed tolerance for each stopped axis. A normal completion still needs the declared coverage, off-target requirement, final angle, and stopped state.

## Live input

Read one JSON input line per request. Each request has a consecutive integer `seq` starting at zero, nondecreasing integer `now_ns`, boolean `spray_permitted`, and these fields.

| Field | Meaning |
| --- | --- |
| `controller` | Object with `measured_ns`, `q_rad`, `qd_rad_s`, `mode` (`idle`, `running`, `stopping`, or `stopped`), `command_id` (the current or last stopped motion ID, or null before the first motion), and `trace_through_ns`. The last field is the end of the measured process record currently promised by the controller for that motion, or null before motion. |
| `scene` | Null if unchanged, or an update with a higher `scene_revision`, replacement `world_collision`, and `registration`. Its registration is null for an obstacle update and otherwise a complete registration report from the new capture epoch. A part re-index occurs with spray disabled after the controller has stopped. |
| `receipts` | Array of measured process intervals. Every interval contains a nonempty `receipt_id`, the issued motion `command_id`, its `scene_revision`, and at least two `samples`. Each sample has absolute `t_ns`, seven `q_rad` and `qd_rad_s` values, and the actual `flow_ml_s`. |

Samples inside a receipt are ordered at the control period. Use the same Hermite and held-flow conventions as the plan to interpret each measured interval. A receipt covers the half-open interval from its first to its last sample. Receipts for a motion can appear out of order and repeat verbatim. Distinct intervals can touch at endpoints and have disjoint interiors. The process history starts when the controller accepts the motion at the issue time and ends at its final stopped sample. `trace_through_ns` advances for that motion as new samples are produced. Delayed receipt delivery can leave gaps even after the robot is stopped.

## Motion and recovery

Issue a motion only from a fresh controller reading at rest, with current registration and permission to spray. A fresh reading has `0 <= now_ns - measured_ns <= state_max_age_ns`. A reading at rest is in `idle` or `stopped` mode with every speed within the stopped tolerance. Each motion has one scene revision and starts at the measured positions and velocities at its issue time on the mission clock. It uses the Stage 3 trajectory format with times relative to issue and finishes within the remaining mission time. Include all earlier measured coating in the plan's coverage and overspray budget. Treat the measured trace and its actual flow as the record of work completed. Attribute each interval to the part registration used for that issued motion so a later registration preserves the locations of material in the part frame.

When permission drops, a scene change takes effect, or controller evidence becomes stale during motion, request a stop for that motion. The controller disables spray and executes its configured braking profile before reporting `stopped`. Live revocation cases leave the configured braking envelope clear. Wait for the old command to stop, a fresh controller reading, and all intervals through its final `trace_through_ns` before issuing a replacement. Maintain the current hold while evidence is missing or a new registration is under review. Mark the job blocked if the current evidence establishes that a qualifying finish cannot be made within the remaining deadline. Mark the job complete only after a fresh stopped measurement and reconciled material history qualify.

## Replies and restart

Write and flush one JSON reply per input line. A normal reply has `{seq,status,command}`. Use `ready` while issuing or following an executable motion, `waiting` while stopping or holding for evidence, and `blocked` or `complete` for the outcomes defined above. With no new command, set `command` to null. A stop command is `{kind:"stop",command_id,motion_id}`. An execution command is `{kind:"execute",command_id,scene_revision,trajectory}`. Every newly issued command has a unique nonempty string ID. The caller deduplicates the same ID.

Commit accepted state, receipts, issued command identity, and the exact reply to `STATE_DIR` before publishing the reply. An exact retry of the latest committed request returns its original reply. A conflicting receipt with an existing ID, an altered retry, a skipped or earlier sequence, or a malformed packet returns `{seq,status:"rejected",command:null}` and leaves the committed session untouched. Use a null `seq` when the packet has no valid integer sequence. A process restart uses the same directory and keeps the in-progress material record and motion authority.

Keep the live controller adapter separate from geometry, process accounting, and durable storage. Include an interruption and restart in your development record, with enough saved inputs and outputs to replay what finished on the part.
