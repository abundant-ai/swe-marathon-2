# Repair the live map after late place recognition

Our place-recognition worker sometimes finishes after its input keyframes have left the live visual estimator. A match can also be withdrawn or corrected after another worker checks it. Add a restartable repair stream that can revise those measurements over a bounded history and preserve their effects after the history closes.

Keep the earlier commands and add this CLI.

```bash
python3 -m lagfusion reopen-tracks --manifest MANIFEST.json --state CHECKPOINT
```

## Model and time bounds

Use the SE(3) transform and optical conventions from `smooth-tracks`. A pose is `{"translation":[tx,ty,tz],"quaternion_wxyz":[w,x,y,z]}`. A pose maps local coordinates to parent coordinates. For an odometry or relative match from frame `i` to frame `j`, the observation approximates `X_i⁻¹ X_j`. All six-vectors and covariance blocks use the right-local `[rx,ry,rz,tx,ty,tz]` tangent in radians and metres. Use the declared Gaussian weights. Relative-pose errors follow GTSAM's Pose3 prior and between residual conventions. Landmark priors are independent isotropic Gaussian points in the map frame. Pixel residuals use the production camera's declared optical transform and pinhole intrinsics, in pixels, with isotropic noise. Keep landmark uncertainty and its correlations with the poses.

The manifest has `initial_pose`, six positive `initial_sigmas`, six positive `odometry_sigmas`, `calibrations`, `landmarks`, `lag_frames` and `rewind_frames`. `calibrations` maps a camera ID to `body_from_camera` and `intrinsics` in order `[fx,fy,skew,cx,cy]`. `landmarks` maps an ID to a three-number `point` and positive `sigma`. There are at most 16 landmarks and four camera mounts. The frame horizons satisfy `2 <= lag_frames < rewind_frames <= 64`. The stream uses at most four pixel IDs per frame and two loop IDs starting at any given frame, with each loop spanning at most nine frame intervals.

At newest frame `n`, the serving window is the inclusive interval `[max(0,n-lag_frames), n]`. Repairs may use either endpoint anywhere in the inclusive interval `[max(0,n-rewind_frames), n]`. Poses between the two cuts are still eligible for reconstruction. A frame below the repair cut is permanently sealed. Absorb its factors and preserve their joint information when throwing away its raw measurements. Keep the estimated history bounded by `rewind_frames + 1` pose states. You can hold the already sealed part as a linearized prior. Retain the live nonlinear terms needed to revise tentative matches. A frozen estimated old pose used as a new independent pose prior loses uncertainty and cross-correlations.

## Live requests

Read one object per NDJSON line and flush one response before the next request. `request_id` starts at 1 and increases by exactly one for each new request. Collapse an exact retry of the most recent request, including after a process kill. Persist the state and receipt together before responding. Use one writer and one regular checkpoint file of at most 128 KiB. The checkpoint's parent directory already exists. After each response, the checkpoint must be the only entry in that directory. Temporary files for atomic replacement may exist while processing a request. The caller can restart the process between any two requests using only the same manifest and file. There is no raw history service. An invalid request exits nonzero and leaves the committed file unchanged.

- `{"operation":"frame","frame":n}` appends the next consecutive frame, starting at zero. For every frame after zero include `odometry` as the relative pose from the preceding frame. No future measurements are sent.
- `{"operation":"edit","updates":[...]}` applies a single packet of distinct measurement updates atomically. Each row has `id`, positive consecutive `version` starting at 1, `action` of `put` or `retract`, `kind` of `loop` or `pixel`, and the immutable frame endpoints `i`, `j`. A `loop` has `i<j` and a `put` includes a pose `measurement` and six positive `sigmas`. A `pixel` has `i=j` and a `put` includes a `camera`, `landmark`, two-number `pixel` and positive `sigma_px`. The producing camera and landmark cannot change across versions. A `retract` removes that measurement's contribution. A new `put` can restore it with corrected values. A row with `i < max(0,n-rewind_frames)` is `sealed` and has no effect even when the other endpoint is live. Other valid rows are `applied`. A late initial match within the repair cut is allowed. IDs are never reused for another measurement.
- `{"operation":"estimate"}` returns the current state and adds no factor.

Every reply contains `request_id`, the latest `frame`, `pose` of the latest frame, sorted `active_frames`, `archive_start` equal to the inclusive repair cut, `archived_frames` equal to `n-archive_start+1`, and `updates` mapping the submitted IDs to `applied` or `sealed`. Other replies use an empty `updates` object. With two distinct marginal endpoints, return `joint_frame_ids` as `[first_live,n]` and `joint_covariance` as the corresponding full 12-by-12 joint marginal, including its off-diagonal blocks. For the initial singleton, either `[0]` or `[0,0]` names the same frame and uses a six-by-six marginal. Return finite means and positive definite symmetric covariance.

The request stream supplies only the manifest and live observations. The reference trajectories, hypothetical future matches, sealed raw packets, ground-truth archived poses, and batch-estimator outputs are unavailable. After restart the state path is the sole durable handoff. Replies remain under 128 KiB and arrive within three seconds per request.

## Qualification

The short replays compare each selected pose to a separate full-history nonlinear fit with 0.04 m translation and 0.018 rad rotation tolerances. Relative Frobenius error limits are 0.12 for the full joint marginal and 0.18 for its cross block. Sealed edits may move the estimate by at most 0.001 m and change the full covariance by at most `3e-5` in Frobenius norm. On the two designed late closures per short replay the latest position error must improve by at least 0.20 m. A longer run checks state size, support bounds and cold continuation with post-compaction position error at most 0.30 m. The final reward is 20% for the retained seventh checkpoint and 80% for the new missions, each equally weighted.
