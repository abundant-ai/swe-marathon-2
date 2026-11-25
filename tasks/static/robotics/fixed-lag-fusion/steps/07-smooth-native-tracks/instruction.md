# Preserve visual tracks through a sliding localization window

The range estimator can stay online during radio faults. Our mobile scanner
also has calibrated landmarks and two commissioned camera mounts. Bring its
delayed pixel tracks into the live estimator while retiring old poses.
A camera may change mounts while a prior frame from the former mount is
still in flight. The map process can also revise or retract a track before
its frame leaves the smoothing window.

Keep the earlier commands available. Add a streaming command.

```bash
python3 -m lagfusion smooth-tracks --manifest MANIFEST.json
```

Read one JSON object per line from standard input and flush one JSON output
line before reading the next input. The manifest defines the pose, camera
and noise conventions. Positions are in metres. A pose is an object with
`translation` as three numbers and `quaternion_wxyz` as a unit quaternion.
Poses transform local coordinates into their parent frame. A relative
odometry pose maps the current body into the previous body frame. An
extrinsic maps optical camera coordinates into the body. The optical axis is
positive z and image coordinates have their origin at the upper left.
GTSAM 4.3.0 is installed and can be used for the native factor graph.

## Manifest

The manifest has these fields.

| Field | Value |
| --- | --- |
| `lag_frames` | Number of prior pose frames retained in addition to the newest, from 2 to 64 |
| `initial_pose`, `initial_sigmas` | Surveyed body prior and six standard deviations |
| `odometry_sigmas` | Six standard deviations for every relative pose |
| `calibrations` | Object mapping each camera mount name to a pose and `intrinsics` |
| `landmarks` | Object mapping track IDs to approximate `point` and isotropic `sigma` |

The intrinsics vector is `[fx, fy, skew, cx, cy]`. The camera mount pose
field is `body_from_camera`. All six-vectors and tangent-space matrices use
right-local GTSAM Pose3 order `[rx, ry, rz, tx, ty, tz]`. Landmark points
are in the world frame. Their priors are Gaussian, including weak seed
points supplied to start tracks. Treat these as uncertain variables.

## Live requests

Each packet has a strictly increasing integer `request_id`. An exact
retry of the most recent request returns the same reply with no state change. An invalid packet exits
nonzero without writing a reply. Supported operations follow.

- `frame` adds the next consecutive integer `frame` index. Frame zero has
  no odometry. Each later packet has `odometry` from its predecessor.
  Advance the lag window and retire expired pose variables. Keep the
  information they contributed to track and body variables.
- `tracks` has an array of `updates`. Each update names an `id`, integer
  `version` starting at 1, and `action` of `put` or `retract`. A first
  `put` also has the acquisition `frame`, `landmark`, `camera`, measured
  `pixel` as two numbers, and isotropic `sigma_px`. A newer `put` repeats those fields with the next version. Correct
  the pixel or uncertainty and keep the same frame, landmark and camera. A `retract` includes the ID, frame and next version and removes its
  current contribution. A later `put` can restore it. Ignore missing or
  outdated evidence for a retired frame. In that case report `expired`
  for its ID. Apply all accepted updates in the packet before solving. A landmark stays active
  until the newest frame is more than `lag_frames` after the last frame
  at which a `put` for it was accepted. A retraction changes the factor
  but does not advance that landmark's retirement time.
- `estimate` queries the current solution without changing the graph.

All replies are objects with `request_id`, `frame`, `state` and `updates`.
`frame` is the newest accepted frame. `state` contains `pose`,
`covariance` as a 6-by-6 array in the declared tangent frame, `frames`
as the sorted active frame numbers, and `landmarks` as sorted active
track IDs. `updates` maps each submitted evidence ID to `applied` or
`expired`, and is empty for the other packet types.

## Qualification

Resolve delayed pixels using the calibration that produced each observation.
Tracks can cross several position retirements. Preserve their information
across the boundary and apply corrections only once. The verifier compares
the reported trajectory against surveyed motion and compares pose uncertainty
against an independent full-graph fit on a small replay. It also tests live
retractions, exact acknowledgements, and focal changes during camera
handover. The final reward keeps 20% of checkpoint six and assigns 80% to
these native vision missions.

The three native missions share equal weight. A passing mission needs
physical tracking, the full pose covariance, and correct revision and
retry behavior for its stream.
