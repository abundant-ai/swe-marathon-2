# Qualify held-out visual–inertial recording segments

We need to tell which held-out frames have calibrated time support and enough stereo geometry to compare with a survey. Apply the existing calibration as supplied. Leave calibration and stereo commands available.

    python3 -m visqual qualify --spec SPEC.json --output REPORT.json

The spec contains rig, an ok calibration report, a body pose track in the lab survey world, and an ordered array of segments. Each segment has a unique id and a frames array. A frame has id, left_tick, right_tick, reference_world_from_left, and matches in the earlier stereo format. A match also has reference_world_point_m, an independently surveyed XYZ coordinate for that track. The reference pose and point use the survey world. Frame IDs are distinct within a segment and match IDs within a frame. Clock ticks are nonnegative integers.

Apply the left camera clock offset from calibration, so a left-camera tick t queries body time t-offset_ticks. Use an exact body sample if available. Otherwise interpolate only if both adjacent samples lie within max_body_gap_ticks of the query. Interpolate translation linearly and use shortest-arc quaternion interpolation. Never extrapolate. Compose world_from_body with body_from_left.

Frame status uses the first applicable condition in this order:
- stereo_skew if the absolute left/right tick difference exceeds max_stereo_skew_ticks.
- missing_body if the corrected body time is unsupported.
- poor_stereo if fewer than min_matches tracks pass the stereo geometry checks.
- usable otherwise.

Both gap bounds are nonnegative integers. min_matches is a positive integer and min_coverage is a number between zero and one inclusive. For a usable frame report the independently reconstructed world pose and triangulated world points. Do not substitute surveyed information for the reconstructed result.

Write {"segments":[...]} in input order. A segment has id, status, requested_frames, usable_frames, coverage, frames, translation_rmse_m, rotation_rmse_rad, and landmark_rmse_m. Coverage is usable divided by requested, or zero when no frames were requested. It is ok only if at least one frame is usable and coverage reaches min_coverage. Otherwise its status is insufficient_coverage and its three metrics are null. Translation and rotation RMSE compare the returned camera poses with the independent reference poses. Landmark RMSE uses the Euclidean errors of all accepted world points across usable frames.

Each frame row has id, status, world_from_left, and points. Each point entry has id and position_m in match order. An unusable frame returns world_from_left null and points empty. Preserve the existing atomic malformed-input handling.
