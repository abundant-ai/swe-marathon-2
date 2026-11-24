# Fuse the commissioned sensors on a separate run

The operators want to replay a new survey without tuning its calibration to that recording. Extend `smooth` to accept optional `calibration` (a successful calibration report in the previous format) and `anchors` (surveyed 2D positions by ID). Keep the earlier commands and linear factor formats.

Three additional event types supply independent measurements:

- `op: "wheel"` has `device_tick`, `value`, and `covariance`. Correct the acquisition tick by adding `calibration.offset_ticks`. With the calibrated `A = wheel_scale * rotation(wheel_yaw_rad)`, form an adjacent delta factor with vector `A * value` and covariance `A * covariance * A^T`.
- `op: "imu"` has `tick`, `value`, and `covariance`. These are externally integrated, projected displacements already in the lab frame. Treat the measurement as an adjacent delta factor. The workbench does not infer displacement by integrating raw accelerometer samples.
- `op: "range_pair"` has `tick`, distinct anchor IDs `anchor_a` and `anchor_b`, nonnegative `range_a_m` and `range_b_m`, and positive `variance_m4`. Subtract the calibrated bias from each reported distance to obtain `r_a` and `r_b`. If either corrected distance is negative report the outcome `invalid` and add no factor. Otherwise with surveyed positions `a,b`, form a projection with axis `b-a` and value `(r_a^2 - r_b^2 - ||a||^2 + ||b||^2) / 2`. Use `variance_m4` for this derived scalar. The anchors must have different positions.

Calibrated wheel and range factors require a successful supplied calibration. Range factors also require positions and bias entries for both anchors. The corrected tick determines whether a wheel measurement is active, expired or future. Support a negative corrected tick as expired. For ranges, classify valid temporal support as before and report `invalid` for a supported pair with a negative corrected distance. Keep the calibration frozen and keep malformed input handling atomic.
