# Recalibrate a camera while the map stays live

A camera mount can move after the sensor is serviced or replaced. Keep the current map available while images and delayed survey receipts establish the new mount. Estimate the camera-to-body transform with the trajectory and landmarks. Preserve its effect on localization uncertainty as old poses leave the repair window. Keep the earlier commands available.

```bash
python3 -m lagfusion recalibrate-tracks --manifest MANIFEST.json --state CHECKPOINT
```

## Camera estimates and observations

Keep the preceding checkpoint's packet sequence, active and repair windows, bounded state, cold retry and atomic edit rules. The manifest adds `uncertain_cameras`, a map from one to three IDs in `calibrations` to six positive prior standard deviations. For each listed camera, use its `body_from_camera` as the mean of a Gaussian pose prior in the right-local `[rx,ry,rz,tx,ty,tz]` convention. Other calibrations still describe fixed mounts. A replacement can have a different camera ID and its own prior. An image always uses the calibration ID named in its pixel record, including during replay. Intrinsics stay fixed.

Let `X_i` map the body at frame `i` into the map and `C_camera` map the named camera into the body. A pixel projects the uncertain landmark through `(X_i C_camera)⁻¹` using the named intrinsics. Its isotropic pixel noise stays as before. Estimate each `C_camera` jointly with the poses and landmarks.

An edit can also have kind `mount_survey`. Its `i` and `j` name the same capture frame. A `put` supplies the uncertain `camera` ID, `measurement` as the independently surveyed `world_from_camera` pose, and `sigmas` as six positive standard deviations. Compare the measured pose to `X_i C_camera` with the Pose3 prior residual convention. The camera ID and capture frame stay fixed across edits. A `retract` uses the usual edit envelope and may omit `camera`. At most one survey ID per uncertain camera starts at a frame. Honor delayed surveys, corrections and withdrawals while their frames are in the repair window.

When a capture seals, preserve its pose, landmark and mount information together in the boundary prior. Old raw pixels and surveys can then be discarded. A later edit to a sealed capture has no effect, including when the affected camera is still in use. A camera's estimate remains queryable after its last image retires. Retain the same 128 KiB limit on the committed checkpoint and each reply and the same three-second request limit.

## Replies and accuracy

Keep the existing reply fields. Add `mount_poses` mapping each uncertain camera ID to its current `body_from_camera` estimate. Any request can include `query_mount` naming one uncertain camera. The default is the first uncertain ID in lexicographic order. Add `joint_mount_camera` naming that camera and `joint_mount_covariance` for the distinct pose keys in `joint_frame_ids` followed by that camera's mount. This is a 12-by-12 covariance for the initial pose and mount, and 18-by-18 when there are two distinct pose endpoints. Use the right-local tangent for each pose and mount. Include the pose–mount cross blocks. The leading pose block equals `joint_covariance`.

On short calibration runs, keep the latest pose within 0.04 m and 0.018 rad of the Gaussian full-history fit. Keep the queried mount within 0.025 m and 0.022 rad. The full joint mount covariance must agree within 0.14 relative Frobenius error. For its pose–mount cross block, the Frobenius error must be at most 0.20 times the greater of the full-history cross-block norm and `2e-5`. An edit to a sealed capture may change the latest pose and each mount by at most 0.001 m and 0.001 rad, and the joint mount covariance by at most `3e-5` in Frobenius norm. On long replays, keep post-compaction position error at most 0.30 m. Separate factor models, bounded estimation and stream persistence.
