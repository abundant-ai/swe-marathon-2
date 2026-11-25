# Calibrate wheel motion and range offsets

We want to fix sensor calibration before using new runs to assess localization quality. The wheel logger has a constant timestamp offset relative to the survey clock, and a fixed residual rotation and scale in the plane. The range receivers also have per-anchor additive bias. Add this command and retain the batch smoother.

```bash
python3 -m lagfusion calibrate --spec SPEC.json --output REPORT.json
```

The spec contains `wheel` and `survey` arrays of `{"tick":integer,"delta":[x,y]}`, each with unique nonnegative ticks. A wheel observation at tick `t` matches a survey observation at `t + offset_ticks`. Wheel deltas have been approximately rotated into the lab plane. The calibration applies a single positive scale and proper 2D rotation from wheel to survey displacements. Survey and wheel rows may be out of order.

`offset_candidates` is a nonempty array of distinct integer offsets. For each offset, require at least `min_pairs` (integer ≥3) exact timestamp pairs and at least that many pairs whose wheel magnitude exceeds positive `motion_floor_m`. Estimate the rotation and scale robustly against isolated bad pairs. Compare eligible offsets by the median Euclidean residual in metres over their excited pairs. If the two best residuals are within `ambiguity_m` (finite nonnegative), report ambiguity. If no offset has sufficient excited pairs report insufficient support.

The spec also supplies `anchors`, mapping nonempty IDs to their surveyed 2D positions, and `ranges`, an array of `{"anchor":id,"position":[x,y],"distance_m":nonnegative_number}`. Recover a bias per anchor as the median measured distance minus surveyed distance. The sign is measured minus true. Require at least `min_pairs` range samples for every supplied anchor. These calibration ranges have an independently measured cart position.

Write `status` of `ok`, `insufficient_support`, or `ambiguous`. An `ok` report also contains `offset_ticks`, `wheel_scale`, `wheel_yaw_rad` in `[-pi,pi]`, `wheel_pairs` counting excited observations used to compare the chosen offset, `wheel_median_m`, and `range_bias_m` mapping each anchor to its bias. In a non-ok report those six values are null. Reject malformed input atomically as before.
