# Land inside a surveyed pad after losing position aiding

Implement `python -m px4_recovery land-assured --spec SPEC.json --calibration CALIBRATION.json`. Consume one observation per line and flush one JSON reply. Use your own successful `commission` output and retain all earlier commands.

The multicopter starts with commissioned inertial and delayed vision measurements. Once horizontal position is stale, it must actively brake, reach a surveyed emergency pad and land. A separate down-facing optical-flow and range instrument can support this maneuver. The target plants vary in mass, thrust response, torque response and later thrust availability. They apply actual submitted body-rate and collective commands. The simulator does not supply unobservable position or a direct height channel during degraded flight.

## Inputs and frames

The flight configuration and packet use the earlier `fly` interface, with `ground_aid` replacing `height_m`. Ground observations are separate timestamped reports. The `waypoints` entry supplies the active pre-fault position and heading target.

| Additional spec field | Meaning |
| --- | --- |
| `period_s`, `cruise_mps` | Control period and maximum nominal horizontal cruise request |
| `ground_support_age_us` | Freshness limit for the newest accepted optical and range capture |
| `pads` | List of unique `{id,center_ne_m,half_extent_ne_m}` objects defining certified ground rectangles |
| `ground_sensor` | `{body_from_flow_wxyz,lever_arm_m,floor_z_m,min_quality,min_range_m,max_range_m,range_innovation_m,velocity_innovation_mps}` |

For the flow sensor, the fixed mount maps sensor axes into body FRD. Its lever arm points from the body origin to the sensor origin in body axes. The listed floor coordinate is the surveyed NED down coordinate for the beam geometry. Rotation uses the same quaternion convention as the earlier checkpoint.

Each ground item has `{id,capture_us,interval_us,integrated_flow_rad,integrated_gyro_rad,slant_range_m,omega_body_rad_s,quality}`. The two integrated angular vectors correspond to sensor x and y axes. Remove the angular contribution `integrated_gyro_rad` from `integrated_flow_rad`. Forward translation increases the corrected y flow component. Rightward translation decreases the corrected x flow component. Multiply the resulting angular rate by the slant distance for the two observable sensor-origin velocity components. The third component is not measured by optical flow. Use independent vertical motion information and the capture-time attitude to complete the velocity transform. Subtract the rotational velocity of the displaced sensor before using the resulting body-origin velocity.

The range is along the sensor's down axis. Obtain vertical distance using the capture-time rotation, and correct the height for the vertical component of the sensor lever arm. Capture-time range changes can constrain vertical velocity across a sustained outage. Apply accepted estimates at their capture time and propagate to the current time using calibrated inertial evidence.

## Integrity and fallback

Process each `ground_aid` batch by `(capture_us,id)` and report exactly one status per item.

| Status | Condition |
| --- | --- |
| `duplicate` | The ID has already been observed |
| `time` | The capture is in the future or outside the retained history |
| `quality` | Quality falls below `min_quality` |
| `range` | Slant distance is outside the declared bounds, predicted beam down projection is at most 0.45, or the slant-range residual exceeds `range_innovation_m` |
| `innovation` | The corrected horizontal velocity residual exceeds `velocity_innovation_mps` |
| `accepted` | Ground velocity and range observations pass those checks |

Apply the checks in that order. Invalid or superseded measurements do not refresh ground support. Use capture time for freshness. Valid ground velocity does not reset the age of the last absolute horizontal position capture. Continue to process vision and report its decisions even when a pad is already committed.

1. Report `track` while absolute horizontal position is recent. When its age first exceeds `track_age_us`, select a surveyed pad and report `brake`. Keep the same pad for the remainder of the landing, including when primary vision returns.
2. Physically brake, using calibrated inertial and current valid ground sensing. Report `approach` when moving to the pad. If ground aiding is stale during the approach or descent, report `hold`, keep safe altitude or recover clearance, and reacquire supporting ground evidence.
3. Report `descend` only with fresh ground aiding after braking. Below 0.44 m above the surveyed plane, the body origin must remain within the committed pad. Physical first touchdown must have vertical speed below 0.37 m/s and horizontal speed below 0.19 m/s. Command zero rates and collective and return `disarmed` after at least three observed ground-contact ticks. Every route must move under its own thrust before the induced loss, brake, and complete an actual pad touchdown within its deadline.

## Output

Return `{mode,pad,aiding,ground_aiding,last_ground_us,accepted_position_us,estimate,body_rates_rad_s,collective}`. Use null for `pad` while tracking and for `last_ground_us` before a valid ground capture. The two aiding arrays contain ordered per-report `{id,status}` records. Keep the previous current-time pose schema `estimate:{position_m,velocity_mps,q_wxyz}` and normalized attitude. The verifier checks position and velocity errors below 0.105 m and 0.127 m/s and attitude error below 0.065 rad. Candidate trajectories may differ while satisfying the actual flight and contact constraints.

The environment is an authored native MuJoCo rigid-body simulation. Ground sensors are derived from simulated motion and ray geometry. The cases represent a software-only deployment interface.
