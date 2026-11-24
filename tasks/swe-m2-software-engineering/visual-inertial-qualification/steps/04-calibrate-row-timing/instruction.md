# Calibrate cameras from row-timed fiducial observations

Our calibration rig supplies an independently timed body trajectory and raw image points from two camera sensors. Each sensor can read its rows in either direction and uses its own clock. Recover the timing and rigid camera mount from the fit captures, then qualify the frozen calibration on disjoint validation captures. Refuse an unobservable calibration even if its held-out residual is small.

Keep the previous commands and add the following operation.

```bash
python3 -m visqual calibrate-row-timing --spec SPEC.json --output REPORT.json
```

## Calibration input and model

The top-level JSON object has an integer `clock_reference_ns`, positive integer `max_gap_ns`, and fields `body`, `cameras`, `targets`, `fit` and `validation`.

- `body` contains at least two poses in strictly increasing integer `timestamp_ns` order, on the body clock. Each row also has `translation_m` and a unit `quaternion_xyzw`. The pose maps body coordinates into the surveyed world. Use linear interpolation of position and shortest-arc quaternion SLERP. A time equal to a recorded knot is supported. Other times need two bracketing knots no farther apart than `max_gap_ns`. Do not extrapolate.
- `cameras` maps camera IDs to positive integer `width_px` and `height_px` of at least two, pinhole `intrinsics` as `[fx,fy,cx,cy]` with positive focal lengths, and `nominal_body_from_camera` with `translation_m` and unit `quaternion_xyzw`. The nominal mount is a starting value. The unknown rigid transform maps optical coordinates into the body, and the optical axis is positive z. No lens distortion is present. Each entry also has inclusive `offset_ns_bounds`, `readout_ns_bounds` and `skew_ppm_bounds`, with strictly increasing finite endpoints.
- `targets` maps a fiducial ID to its surveyed three-coordinate point in metres. Each `fit` or `validation` observation has `camera`, `target`, integer `timestamp_ns` on its camera clock, zero-indexed integer sensor `row`, and two-number `pixel`. Row 0 is the top and row `height_px-1` is the bottom. Use the supplied original row for exposure timing. The measured vertical pixel coordinate is a separate residual.
- Recover each camera's signed center-row offset in ns, signed top-to-bottom readout in ns, affine clock skew in ppm and six-degree-of-freedom mount. Let `x = timestamp_ns - clock_reference_ns` in ns and `u = row/(height_px-1)-0.5`. The corner occurs at the body-clock time relative to the same origin of `x*(1+skew_ppm*1e-6)+offset_ns+u*readout_ns`. Subtract the integer origin before converting to floating point. A negative readout means the lower rows were exposed earlier. Center-row offset and skew are defined at the provided clock origin. All numeric fields are finite.
- For fitting, keep only corners whose entire admissible timestamp interval, computed from the three timing bounds, lies in one continuous supported part of the body trajectory. At least 24 supported corners at eight or more distinct frame timestamps are required. Fit each camera independently using its raw training reprojection residuals and honor its timing bounds. No solved camera poses or true timing parameters are supplied. Validation observations cannot influence the fitted parameters or observability decision.

## Observability and validation

At the fitted solution, examine the two-dimensional fit residual Jacobian for each camera. Use six local rigid-mount perturbations and three timing perturbations scaled to 10 ms of offset, 10 ms of readout, and 1,000 ppm of skew. Project the timing columns onto the orthogonal complement of the mount columns and divide by the square root of the number of fit corners. Report the three descending singular values as `timing_spectrum` in pixels. A calibration is degenerate if the mount lacks full rank or the smallest projected timing singular value is below `max(0.025, 1e-5*s_max)`. A rigid mount change can explain the same pixels as a clock shift under some motions.

Publish `{"cameras":{...}}`, keyed by the requested camera IDs. Each row contains `status` of `ok`, `insufficient_support` or `degenerate`, and these fields.

| Field | Value |
| --- | --- |
| `fit_count` | Fit corners with complete time support across all admissible parameters |
| `offset_ns`, `readout_ns`, `skew_ppm` | Finite fitted numbers within the supplied bounds, or null for an unavailable fit |
| `body_from_camera` | Fitted `translation_m` and unit `quaternion_xyzw`, or null for an unavailable fit |
| `timing_spectrum` | The three descending values when a Jacobian is available, or null for insufficient support |
| `validation_count`, `validation_matched` | All validation corners for this camera, then the subset with supported exposure times and positive camera depth greater than 0.02 m under the frozen fit |
| `validation_rmse_px` | Square root of mean squared two-dimensional reprojection distance over matched corners, or null when none are matched |

Unavailable fits report zero validation matches and null RMSE. Invalid inputs exit nonzero and preserve any existing output report.

## Qualification

Supported cameras must recover the offset within 0.9 ms, readout within 1.5 ms, skew within 200 ppm, mount position within 7 mm, and mount rotation within 0.007 rad on our surveyed captures. Held-out reprojection RMS must be at most 0.55 px on supported corners. An independently altered held-out stream must leave the fitted parameters and observability unchanged while updating its error and coverage. A moving but unobservable camera must abstain when another camera in the rig is observable. The final score uses 20% of the retained third checkpoint and 80% from three equally weighted raw-calibration missions.
