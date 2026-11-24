# Fly with asynchronous inertial and vision evidence

A multicopter has commissioned inertial sensors and delayed external vision. Fly the simulated waypoints while the instrumentation is sound. A short loss of horizontal aiding permits braking and reacquisition. A longer loss requires a controlled touchdown inside the specified landing area. Keep the earlier entry points and behaviors.

Implement `python -m px4_recovery fly --spec SPEC.json --calibration CALIBRATION.json`. The calibration file is the successful output of your own `commission` command for this instrument set. Read one JSON object per line and flush exactly one JSON reply per observation. Use finite SI values. The simulator consumes only commands actually returned by your process.

## Frames and configuration

The navigation frame is north, east, down (NED). Body axes are forward, right, down (FRD). A unit Hamilton quaternion is stored as `[w,x,y,z]` and rotates vectors from the named child frame into its parent. Either quaternion sign represents the same rotation. Angular rates and accelerations are in radians per second and metres per second squared. Use `[0,0,9.81]` for gravity in navigation coordinates and remember that the calibrated accelerometer measures specific force.

| Spec field | Meaning |
| --- | --- |
| `initial` | `{timestamp_us,position_m,velocity_mps,q_wxyz}`, a commissioned initial NED pose and velocity |
| `imu` | One of the commissioned devices, with `device`, `clock_origin_us`, `body_from_imu_wxyz` and `lever_arm_m` (body origin to IMU in body axes) |
| `camera` | `{body_from_camera_wxyz,lever_arm_m}`, the full camera mounting and body-origin-to-camera vector |
| `waypoints` | Ordered list of `{position_m,yaw_rad}` goals in NED with wrapped heading |
| `history_us` | Capture-time window for accepting delayed observations |
| `track_age_us`, `brake_age_us` | Boundaries on horizontal position age in microseconds |
| `innovation` | Norm limits `position_m`, `velocity_mps`, `attitude_rad` at the capture instant |
| `position_tolerance_m`, `speed_tolerance_mps`, `yaw_tolerance_rad`, `dwell_ticks` | Required consecutive qualifying observations at each waypoint |
| `hover_collective`, `max_body_rate_rad_s` | Approximate level hover feedforward and per-axis rate bound |
| `min_ned`, `max_ned` | Physical bounds for the airframe |
| `landing_area` | `{min_ne_m,max_ne_m}`, a horizontal zone for contingency touchdown |
| `deadline_us` | End of the episode in navigation-clock microseconds |

## Input observations

Each observation includes `tick`, `now_us` in the navigation clock, `height_m` from an independent vertical range instrument, a boolean `contact`, and lists `imu`, `vision`, and `frame_links`. A control observation summarizes all packets delivered since the previous tick. IMU capture intervals are shorter than control ticks and can straddle them. On the control boundary, a short prediction using the most recent corrected inertial rates may be needed. The simulator supplies enough IMU coverage for all test missions.

- An IMU item is `{sequence,stamp_us,interval_us,temp_c,clipped,delta_angle,delta_velocity}`. Both intervals end at `stamp_us` in the device clock and the increments are in the instrument axes. Ignore clipped items and repeated accepted sequence numbers. Use the commissioned affine time map and gain, bias and temperature corrections. Rotate the rates into FRD. An IMU away from the body origin senses tangential and centripetal acceleration in addition to translational motion. Use the known lever arm and body rates to recover translational acceleration. The first observation may have no IMU items.
- A frame link is `{epoch,start_us,translation_m,ned_from_vision_wxyz}`. Its pose maps the named vision epoch into NED starting at the stated capture time. The camera may publish from a new epoch before its link arrives. Process available links before that packet's vision items. Validate a report against the interval from its link start to the start of the next observed link.
- A vision item is `{id,capture_us,epoch,position_m,velocity_mps,q_wxyz,omega_body_rad_s}`. It measures the camera origin and orientation in its vision frame. Any of the position, velocity or quaternion fields can be null. Use `omega_body_rad_s` and the lever arm to transfer linear velocity from the camera origin to the body origin. When a quaternion is absent, use the predicted capture-time attitude to compensate the lever arm. Vision may contribute position and velocity without an attitude update, or attitude without any translation.

Process the delivered vision items by `(capture_us,id)`. A previously seen ID has status `duplicate`. A capture from the future or outside the retained window has status `time`. An unknown epoch or incompatible link interval has status `frame`. Otherwise compare each available field to the state predicted at that capture time. Compare orientation by the shortest rotation angle. If any present innovation exceeds the configured bound, report `innovation` and use none of the row. Otherwise report `accepted`. Accepted updates correct only their observed components. Apply them at capture time and carry them forward through later inertial and aiding evidence. Late position-only and attitude-only observations can arrive in opposite order. An accepted older capture must not move the newest aiding timestamp backward. Initial calibrated position counts at its start time until the first accepted position update.

## Direction and fallback

Compute horizontal aiding age as present navigation time minus the newest accepted position capture. Track waypoints while age is at most `track_age_us`. A waypoint needs a consecutive pose, yaw and speed dwell while tracking. Continue commanding safe motion when giving the first `complete` reply. When track age expires, stop advancing the mission and brake using the remaining inertial estimate. If horizontal aiding returns before the braking limit, resume the same waypoint. If age exceeds `brake_age_us`, commit to landing. Continue to use supported attitude and range measurements, descend under control and disarm only after stable measured ground contact. The simulated aircraft must stay inside its enclosure throughout, including before and after aiding loss. Landing is checked at physical contact, with pre-contact vertical speed below 0.43 m/s and horizontal speed below 0.24 m/s. A forced landing must follow observable motion and braking.

The reply has the following fields.

| Reply field | Meaning |
| --- | --- |
| `mode` | `track`, `brake`, `land`, `complete`, or `disarmed` |
| `waypoint` | Zero-based next waypoint index, or number of waypoints on completion |
| `estimate` | Current `{position_m,velocity_mps,q_wxyz}` in NED at `now_us` |
| `accepted_position_us` | Capture time of the most recent accepted position measurement |
| `aiding` | Ordered array of `{id,status}` for this observation's vision items |
| `body_rates_rad_s` | Three requested FRD angular rates, each within the specified limit |
| `collective` | Thrust request in `[0,1]`. Both commands are zero on disarm. |

The verifier checks current position, velocity and attitude against independent truth, within 0.040 m, 0.066 m/s and 0.055 rad while flying. During the landing fallback, the respective position and velocity limits are 0.12 m and 0.17 m/s. The native point of application for thrust is the body. A bounded inner angular-rate loop and actuator lag mean that lateral translation must come from appropriate tilt. A flight passes only when estimator decisions, the physical envelope and the expected mission or landing outcome all pass. This is a software simulation with authored sensors and ground contact.
