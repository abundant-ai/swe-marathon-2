# Land on a moving platform using delayed onboard observations

Extend `/app/px4_recovery` with a relative landing controller for the commissioning simulator. It starts level and stationary and must approach a moving landing marker, match the platform's motion and make controlled first contact. The camera can temporarily lose the marker while its range stream continues. Pause the descent safely, resume only after reacquiring the marker and matching the platform again, and abort if the loss persists.

Keep the previous commands working. Separate protocol handling, vehicle and target estimation, and landing control in focused modules. The simulator provides onboard measurements and the sensor calibration. Use those records to estimate the platform relative to the aircraft. The flight interface does not supply a world position, ground velocity, platform trajectory or absolute yaw.

## Command and clock

Run `python3 -m px4_recovery land-relative --spec SPEC.json`. Read one JSON object per line from standard input and emit one response object per line on standard output, in order. Each process handles one flight. Continue updating the estimate and actuator setpoints across lines. The command at each tick remains in effect until the next tick.

The specification contains positive integer `imu_period_us` and `period_us` for IMU and control cadence, an absolute mission `deadline_us`, and maximum capture ages `bearing_max_age_us`, `range_max_age_us`, `flow_max_age_us` and `abort_age_us`. It also provides `hover_collective` and `max_body_rate_rad_s`. The `camera` and `flow` objects each contain `lever_arm_m` and `body_from_sensor_wxyz`. The `range` object contains `lever_arm_m` for its separate origin. Lever arms are three-vector offsets from the reference body origin, expressed in body axes. The unit quaternions rotate sensor-frame vectors into the body frame and are ordered `[w,x,y,z]`.

The body axes are forward, right and down. Use a right-handed local frame with down aligned to gravity and the initial body heading as its horizontal reference. The absolute yaw is arbitrary. Position and velocity at initialization may be taken as zero at the body origin. Gyro samples are body angular velocity, and accelerometer samples are body-frame specific force.

## Input records

Each line includes integer `now_us`, an `imu` array and a `detections` array. Individual capture times use the same monotonic mission clock as `now_us`. The observation arrays can be empty. Supply the IMU samples in increasing acquisition order on the commissioned grid, through the current control tick. An IMU sample has `capture_us` and three-vectors `gyro_rad_s` and `specific_force_mps2`.

Each detection has `stream`, integer `capture_us`, and a numeric `quality`. Its remaining fields depend on its stream.

- `flow` has two-vectors `integrated_flow_rad` and `integrated_gyro_rad`, positive `interval_s`, and positive `slant_m` measured along the flow sensor's positive z-axis to the stationary ground. The angular motion of the sensor is included in the optical integration. With the gyro integration subtracted, an angular residual `[rx,ry]` corresponds to sensor-frame transverse velocity `[ry,-rx] * slant_m / interval_s` at the flow sensor origin.
- `bearing` has `bearing_xy`, a two-vector `[x/z,y/z]` for the direction to the platform marker in the camera frame. The forward ray is proportional to `[x/z,y/z,1]` from the camera origin.
- `range` has positive `range_m`, the straight-line distance from the calibrated range origin to the same marker. The range observation has its own capture time. It is distinct from the flow sensor's distance to the ground.

Accept flow quality of at least 75 and bearing or range quality of at least 70. Handle delayed and reordered captures without applying them in the arrival-time body frame. Repeated records from the same stream and capture time provide one observation. Use only observations already delivered, and do not grant freshness on a future capture, a duplicate delivery or a low-quality record.

## Responses and landing behavior

Return `{phase,body_rates_rad_s,collective,relative}`. The phase is one of `hold`, `approach`, `descend` or `abort`. Body rates are three finite commanded rates in body axes, bounded per component by `max_body_rate_rad_s`. Collective is finite from 0 to 1 inclusive. The relative estimate is `null` before it is available or an object with the three-vectors `position_m` and `velocity_mps`. They are the current marker position and velocity minus the current body-origin position and velocity, in the initialized local frame at `now_us`.

Allow up to 0.8 s to initialize. Afterwards provide a current estimate on at least 75% of the ticks for which all three streams are fresh. Across those estimates, keep the root mean square of the relative position error at or below 0.075 m and of the relative velocity error at or below 0.23 m/s.

Enter descent, and re-enter it after an interruption, only after the aircraft is within 0.14 m of the marker horizontally and its horizontal velocity relative to the platform is at most 0.21 m/s. For a recoverable approach, reach first deck contact by the deadline with horizontal center error at most 0.096 m, horizontal slip relative to the local deck surface at most 0.15 m/s, and downward closing speed from 0 to 0.30 m/s. First contact must occur with fresh bearing, range and flow while in `descend`.

Hold out of descent whenever any one of the bearing, range or flow streams exceeds its specified capture-age limit. Use `hold` or `abort` when marker bearings go stale, including when target range remains fresh. During a bearing or ground-flow outage in approach keep at least 0.43 m vertical clearance above the platform. When the bearing returns, verify alignment and relative horizontal speed again before renewing descent. After any prior descent, latch `abort` when the age of the last usable target bearing or target range exceeds `abort_age_us` (1.45 s in the commissioning specification). In a sustained bearing loss, settle horizontal ground speed to at most 0.22 m/s by 1.02 s from the loss, keep above the deck, and avoid contact. The mission ends at first contact or the flight deadline.

The simulator uses calibrated onboard measurements and an authored moving platform. The related PX4 documentation describes target fusion and optical-flow conventions. [PX4 Vision Target Estimator](https://docs.px4.io/main/en/advanced_features/vision_target_estimator) · [PX4 optical flow](https://docs.px4.io/main/en/sensor/optical_flow)
