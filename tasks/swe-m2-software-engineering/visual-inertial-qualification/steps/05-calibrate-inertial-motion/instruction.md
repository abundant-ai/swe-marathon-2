# Calibrate rolling cameras against raw inertial motion

The calibration lab no longer supplies a dense body trajectory. It supplies
raw gyroscope and accelerometer samples, sparse independent metric anchors,
and the row-timed fiducial observations. Jointly recover the body motion,
inertial bias for each instrument epoch, and clock and mount parameters for
the rolling-shutter cameras. Then use the frozen fit to continue the
trajectory through a separate capture without pose or optical updates.

Keep the earlier commands and add this operation.

```bash
python3 -m visqual calibrate-inertial --spec SPEC.json --output REPORT.json
```

## Inputs and model

The JSON object contains `bias_epochs`, `cameras`, `targets`, `fit` and
`continuation`. `bias_epochs` is a list of distinct instrument-state IDs.
Each has its own unknown constant three-axis gyro bias and three-axis
specific-force bias, in rad/s and m/s² respectively. IDs are known from the
instrument log. Their bias values are not given. The input sensor axes and
scale are already calibrated. Gravity in the surveyed world is
`[0,0,-9.80665]` m/s².

Both windows have integer `reference_ns`, ordered `imu`, sparse `anchors`,
`pixels` and `pose_query_ticks_ns`. IMU samples have integer `timestamp_ns`
on the body clock, `gyro_rad_s` and `specific_force_mps2` in the body
frame, and a `bias_epoch` ID. Subtract the estimated bias before using a sample.
Specific force is body-frame world acceleration with gravity removed. The
reported unit quaternion `quaternion_xyzw` maps body coordinates into the
surveyed world. Position and velocity are expressed in that surveyed frame.

An anchor has `timestamp_ns`, `position_m`, a unit `quaternion_xyzw`,
positive `position_sigma_m` and `rotation_sigma_rad`, and optionally
`velocity_mps` with positive `velocity_sigma_mps`. There is an anchor at
the first IMU sample in each window and it includes velocity. Fit anchors
are soft independent metric priors. All query and anchor times are within
their respective IMU window. The continuation has only its initial anchor.
It starts after the fit ends.

`targets` maps each ID to its surveyed world position in metres. Each
camera entry has `intrinsics` as `[fx,fy,cx,cy]`, `width_px`, `height_px`,
and `nominal_mount` with `translation_m` and unit `quaternion_xyzw`.
The unknown mount maps optical coordinates into the body. Optical z points
forward. There is no lens distortion. The nominal mount is an initial
estimate. Each camera has a `clocks` dictionary keyed by camera-clock
epoch. A clock epoch has integer `sensor_reference_ns` and a coarse integer
`imu_reference_ns`. A camera counter can reset to a much smaller value.

Each pixel has `camera`, `clock_epoch`, `target`, raw camera
`timestamp_ns` in that epoch, integer original `row`, and two-number
`pixel`. Recover one offset per camera-clock epoch, one signed full-frame
readout per camera, one shared skew per camera and one mount per camera.
For `x = timestamp_ns-sensor_reference_ns` and
`u = row/(height_px-1)-0.5`, the exposure on the IMU clock is

```
imu_reference_ns + x*(1 + skew_ppm*1e-6) + offset_ns[clock_epoch] + u*readout_ns
```

Subtract integer origins before floating-point operations. Search within
±60 ms for each offset, ±45 ms for readout and ±1,600 ppm for skew.
Negative readout means lower rows expose first. Use `row` for exposure
time and both measured pixel coordinates for the optical residual.

Estimate fit motion and calibration together from the first window's
anchors, raw inertial data and raw pixels. We supply bounded windows with
monotonic IMU stamps and enough fit measurements in each declared bias
epoch. No solved camera poses or dense body poses are supplied. Continuation
pixels and hidden surveyed poses cannot influence either the fitted camera
and bias parameters or any body pose.

## Continuation and output

For the continuation, seed pose and velocity from its exact supplied
initial anchor. Integrate only its timestamped IMU and the frozen fitted
biases. On each interval of duration `h`, propagate orientation with
the exponential of `h` times the average of the two debiased endpoint
gyroscopes. Rotate each debiased endpoint specific force into the world
and add gravity. Interpolate world acceleration linearly along the
interval and integrate it for velocity and position. For intermediate
exposure and query times use that segment's cubic position and
shortest-arc quaternion SLERP. Do not extrapolate. Measurements in an
undeclared or unfitted epoch are invalid.

Write a JSON object with these fields.

- `bias` maps each instrument epoch to the six-number vector
  `[bgx,bgy,bgz,bax,bay,baz]`.
- `cameras` maps each camera ID to fitted `quaternion_xyzw`,
  `translation_m`, `readout_ns`, `skew_ppm`, a dictionary
  `offset_ns` keyed by that camera's clock epochs, and
  `validation_matched` and `validation_rmse_px`. Validate only pixels in
  `continuation` with the frozen mount, timing and propagated trajectory.
  Count those with a supported exposure time and positive optical depth
  over 0.1 m. RMS is the root mean squared two-dimensional pixel distance.
- `fit` and `continuation` each contain `trajectory`, in the requested
  `pose_query_ticks_ns` order. Every row contains `timestamp_ns`,
  `position_m`, `quaternion_xyzw` and `velocity_mps`.

An invalid input exits nonzero and preserves an existing output.

## Qualification

The verifier checks the fit and continuation against independent surveyed
body motion and reprojects raw continuation pixels using an independent
integrator. The fit position and rotation RMS limits are 0.028 m and
0.018 rad. Continuation position RMS must be below 0.045 m, terminal
position error below 0.08 m and rotation RMS below 0.018 rad. On the
surveyed continuation, calibrated camera reprojection RMS must be at most
0.55 px. Inertial-only reprojection RMS must be at most 8 px after the
optical blackout. Timing must be within 1 ms of epoch offsets, 1.5 ms of
readout and 210 ppm of skew. Mount translation and rotation limits are
0.012 m and 0.012 rad. Changing only the continuation pixels must preserve
the calibration and motion while updating the validation report. The final
reward gives 20% to checkpoint four and 80% to two equally weighted
inertial missions.
