# Keep safe authority through redundant estimator handover

A backup estimator can continue a mission when the preferred estimator jumps or restarts. Before switching, check that the incoming estimator is independently registered to the flight frame and agrees with physical motion. If neither estimator qualifies, use the remaining inertial authority to brake. Keep the earlier commands and single-estimator behavior.

Use the same `stream --spec` command. The optional `supervisor` configuration contains the following fields.

| Field | Meaning |
| --- | --- |
| `sources` | Nonempty array of distinct source names in preference order |
| `qualification_samples` | Positive count of consecutive qualified reports required to select a source |
| `switch_delay_ticks` | Nonnegative time from the most recent switch before an available lower-priority incumbent may yield |
| `max_position_innovation_m`, `max_velocity_innovation_mps` | Positive Euclidean discrepancy limits against the common physical prediction |
| `min_ned`, `max_ned` | Three-element permitted position bounds of the test volume |

In this mode, `reports` replaces `local`. It maps a source name to null or to `{"epoch":nonnegative_integer,"healthy":boolean,"local":record_or_null}`. A local record uses the earlier decoded fields and optional independent anchor. Keep independent reset ledgers and capture ordering for each source. A higher boot epoch discards that source's prior frame and qualification. Ignore an older epoch. Each source needs a complete valid three-axis anchor at least once in its current epoch. A reset gap in one axis group still needs an independent anchor for that group.

## Qualification, authority and motion

At each observation, predict the common physical position and velocity from the previous authoritative state using the independently timestamped IMU interval and the earlier inertial equations. Use that prediction only when the interval is matched and a further interval lies within `max_inertial_ticks`. When this prediction is unavailable, a source needs a full simultaneous anchor on each qualifying report until authoritative tracking resumes.

A fresh, healthy, fully reconstructed and anchored report qualifies when its position and velocity are within both innovation limits against the available prediction. When no prediction is available, the full simultaneous anchor supplies the reference and no velocity comparison is made. A report must meet the existing capture age and chronology rules. An absent, stale, unhealthy, unresolved, or inconsistent report clears that source's consecutive qualification count. Apply the same check to nonselected sources continuously.

Select the highest-preference qualified source when there is no qualified incumbent. If the incumbent is still qualified, keep it until the switch delay has elapsed and a higher-preference qualified source is available. Loss of incumbent authority permits immediate selection of another qualified source. The first selection starts the delay clock. Track waypoints from the selected source, retaining prior dwell when the agreeing source changes. An output adds `source`, the selected name when using its estimate, or null when stopped or braking.

If no source is qualified, keep the existing `dead_reckon` state and position output for any remaining supported inertial interval. In this mode do not advance toward a waypoint. Command acceleration toward zero velocity on each axis, with magnitude `min(max_accel, abs(predicted_velocity) / dt)`. Stop at zero acceleration with null estimate when the inertial chain expires. Remain within the declared test volume. When tracking near its boundaries, choose speed and acceleration so that a later loss of authority leaves room to brake. Use the earlier neutral terminal-abort rules. The same physically bounded point-mass test plant is used. No flight hardware is involved.
