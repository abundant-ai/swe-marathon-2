# Recover stereo-to-IMU timing and mount

The visual and inertial pose exporters have separate origins and clocks. Estimate the fixed left camera mount on the IMU body and its integer clock offset. The pose tracks are already computed by the estimators. Keep stereo triangulation working.

    python3 -m visqual calibrate --spec SPEC.json --output REPORT.json

The spec contains sessions, a nonempty array of independent captures with body and left pose tracks. Each track row has a nonnegative integer tick, translation_m and a quaternion_xyzw in the same format as before. Rows may arrive out of order but ticks must be unique within each track. Body poses map body to their navigation world and left poses map left camera to their visual world. World origins can differ by session and by track. offset_candidates is a nonempty list of distinct integer offsets. The camera tick equals the body tick plus the offset.

For each offset, iterate over body samples at t. Use a relative body motion A from t to t+lag_ticks and a relative left-camera motion B from t+offset to t+offset+lag_ticks. All requested sample ticks must exist exactly in their respective tracks. lag_ticks is a positive integer. Fit a single fixed transform X, body_from_left, which satisfies A*X=X*B. Use min_pairs of at least three across the sessions. Fit physically rigid proper rotations and finite translations. An eligible capture must provide motion around at least two independent body axes. Across each candidate's matched pairs, require the second singular value of the matrix of principal body rotation vectors in radians to be at least 0.001.

Compare the two transforms A*X and X*B using Euclidean translation difference and shortest rotation angle. The candidate score is sqrt(translation_rmse_m^2 + rotation_rmse_rad^2). Select the lowest eligible score. If the second score lies within nonnegative ambiguity_cost of the best, report ambiguous. Use insufficient_overlap when no candidate has min_pairs and insufficient_motion if enough matches exist but every such candidate fails rotational excitation.

Write status ok, ambiguous, insufficient_overlap, or insufficient_motion. In an ok report include offset_ticks, body_from_left, pair_count, translation_rmse_m and rotation_rmse_rad. For other statuses keep the last five fields present, with the largest available pair_count and null for the other four. Keep atomic malformed-input handling.
