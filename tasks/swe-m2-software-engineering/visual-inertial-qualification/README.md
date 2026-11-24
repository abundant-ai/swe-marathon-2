# Visual-inertial qualification

A visual-inertial researcher needs to determine whether a new stereo and inertial recording has useful geometry, a recoverable clock and rigid mounting relationship, and adequate holdout coverage. This task starts at the recorded feature match and pose-track interfaces. It covers calibrated stereo geometry, relative-motion clock and mount calibration, and independently surveyed pose and landmark qualification.

The fixtures use an 80-pose excerpt from TUM VI room1. Camera observations, clock and mount errors, dropped records, and survey perturbations are authored and are explicitly identified as controls. The data and its CC BY 4.0 attribution are in `environment/resources/README.md`. The excerpt SHA-256 is `b0506184051e1873d4e7f7dfca4285ebe6ef587f2163f05642e6d9c2d0f72eb3`. A published ORB-SLAM3 calibration report describes these practical questions. The tool does not run ORB-SLAM3 or estimate pose trajectories directly from pixels or raw IMU. [TUM VI dataset and license](https://cvg.cit.tum.de/data/datasets/visual-inertial-dataset#license) · [ORB-SLAM3 calibration report](https://github.com/UZ-SLAMLab/ORB_SLAM3/issues/894)

| Dimension | Evidence and scope |
| --- | --- |
| Novelty | Reconstructs calibrated stereo points and rig pose, then reports held-out pose and landmark error and timestamp support. Fixed-Lag Fusion addresses a different estimator boundary. |
| Verifiability | Private fixtures project points with independent camera matrices and generate sensor clocks and mount transforms from known values. Survey offsets yield independently known nonzero error in all three holdout metrics. |
| Realism | Measured motion-capture poses retain the geometry of a lab recording. Controlled frame, timing, and survey perturbations provide reproducible fault and uncertainty labels. |
| Difficulty | Qualifying a recording requires finite-angle 3D geometry, a signed clock search, observability and ambiguity tests, independent world origins, and correct use of the frozen fit under held-out data loss. |
| Feasibility | The complete tool runs on CPU with NumPy, JSON and a small pose excerpt. The candidate contract begins at precomputed pose tracks and stereo matches. |

## Verification

The verifier scores named checks cumulatively across three checkpoints. Geometry must match independently projected 3D points and classify bad matches. Calibration uses noncommuting motions, different independent world origins, an opposite signed clock offset, a near-half-turn, exact tick overlap, single-axis excitation, and a periodic ambiguous trajectory. Holdout checks use TUM VI excerpts and two surveyed world tracks, assess both coverage and physical error, and verify that the fitted calibration is actually used. Given poses and survey truths cannot predict which independent sensor observations are supplied. An unchanged export or a tool that always abstains cannot qualify the supported cases.

## Development log

### 2026-11-24

Implemented and verified the cumulative CLI and the separate geometry, calibration and physical holdout checks.

The packaged reference scored 1.0 and the no-op scored 0.0 at each checkpoint. The final verifier passed all 10 named checks. The maintained pytest suite passed and Oddish preflight found no issues. Hosted execution remains unverified.

## Raw rolling-shutter calibration

### 2026-11-24

The fourth checkpoint starts at raw row-indexed fiducial observations,
before the camera-pose estimation boundary of the earlier task. A mobile
calibration rig provides an independently timed body trajectory and a
surveyed target map. Each camera has an unknown clock offset and skew,
signed row readout and six-degree-of-freedom mounting transform. Fitting
uses the raw image residual at each exposure time. Validation reprojects
disjoint observations with the fitted parameters frozen. The approach is
grounded in rolling-shutter calibration tools and continuous-time
camera–IMU calibration. The task supplies a fixed reference body trajectory,
so it does not estimate IMU biases or the underlying continuous-time
trajectory. [Kalibr rolling-shutter camera calibration](https://github.com/ethz-asl/kalibr/wiki/Rolling-Shutter-Camera-calibration) ·
[Huai et al. continuous-time spatiotemporal calibration](https://arxiv.org/abs/2108.07200)

| Dimension | Evidence and limits |
| --- | --- |
| Novelty | The problem goes from relative calibration between solved pose tracks to jointly identifying camera timing and extrinsics from raw image rows. The Fixed-Lag Fusion task estimates and revises live poses, whereas this task treats a separately supplied pose trajectory as the calibration reference. Comparisons with external benchmark collections remain unverified. |
| Verifiability | A private fixture projects surveyed 3D points with its own quaternion model and recovers a physically consistent integer exposure row per corner. The verifier independently recomputes coverage and held-out projection from the returned calibration, checks the planted physical values, and mutates only held-out pixels to detect leakage into the fit. |
| Realism | The task models opposite readout directions, independent camera clocks, and gaps in the reference trajectory. A constant screw velocity creates a clock-to-mount gauge. The verifier constructs an 18 ms shifted clock and alternate mount that yield the same predictions over 595 fit and holdout spots. |
| Difficulty | Pose interpolation, skew and signed rolling-shutter timing interact inside one residual. A well-fitted camera can still be unobservable, while a second camera sampled through other motion qualifies. The task excludes feature detection, unknown target geometry and hardware noise beyond the modeled observations. Hosted model difficulty and the five-day workload target remain unmeasured. |
| Initial feasibility | The reference uses NumPy-only damped robust nonlinear least squares and projects the timing Jacobian out of the mounting tangent space. It ran locally on raw synthetic fiducials over two different body motions and a mixed observability case. |

The first supported mission uses the existing CC BY 4.0 TUM VI room1
pose excerpt as body motion. It resamples the decimated excerpt to a 200 Hz
body reference and authors the target, camera and corner records. The second
uses authored 6-DOF motion and a gap in the supplied reference. The third
uses an authored constant screw followed by a richer segment and different
capture times for the two cameras. No new measured raw camera capture or
IMU dataset is distributed. [TUM VI attribution](environment/resources/README.md)

Local reference, predecessor and no-op scores were 1.0, 0.20 and 0.0.
Reference held-out reprojection was 0.187–0.198 px on observable cameras.
Worst absolute offset, readout and skew errors were 0.117 ms, 0.136 ms
and 27.4 ppm, with worst mount translation error 0.315 mm. The authored
trajectory's body gap excluded 105 validation corners per camera. Altering
only the held-out horizontal pixel coordinate retained the exact fit and
increased validation RMS to 2.90–2.92 px.

Constraining readout to zero increased the two TUM-derived held-out
errors to 4.21–4.38 px. Constraining only the center-row clock offset to
zero yielded 11.70–21.09 px even with skew, readout and mount free. The
same fixed-offset ablation reached 0.201 px in the degenerate screw camera,
where the calibrated timing-plus-mount combination is ambiguous. The
independent alternate solution changed the predicted pixels by at most
2.3 × 10⁻¹³ px. The reference abstained for that camera while
qualifying the other camera at 0.198 px. The maintained package regression
passed. Qualification used the local Python/NumPy runtime.

## Hosted rolling-shutter evaluation

Oddish accepted v2 with one fresh GPT‑6.2 Sol xhigh attempt. The hosted
reference and no-op scored 1.0 and 0.0. Local Oddish preflight passed.
[Rolling-shutter evaluation](https://www.oddish.app/experiments/9abc4012)

Fresh GPT‑6.2 Sol xhigh scored 1.0 across all four checkpoints. The
native report confirms subpixel held-out reprojection on the observable
cameras, an unchanged fit after the holdout was altered, and abstention
under the constant-screw ambiguity.

## Joint inertial motion and rolling-shutter calibration

### 2026-11-24

Checkpoint five replaces the dense body-pose input with timed raw gyro
and specific-force samples and a handful of externally surveyed anchors.
It recovers the body motion jointly with two instrument bias epochs, two
independently reset camera clocks, and each camera's rolling readout,
skew and rigid mount. A separate continuation starts from a single
metric anchor and propagates the frozen calibration through an optical
blackout. Subsequent raw pixels score the continuation without updating
its motion. Kalibr uses batch calibration from image and IMU samples.
Ctrl-VIO uses a continuous-time trajectory and calibrates rolling readout.
This benchmark uses a bounded inertial shooting model rather than their
full spline estimators. [Kalibr camera–IMU calibration](https://github.com/ethz-asl/kalibr/wiki/camera-imu-calibration) ·
[Ctrl-VIO](https://arxiv.org/abs/2208.12008)

| Dimension | Evidence and scope |
| --- | --- |
| Novelty | The raw inertial history is an unknown dynamical trajectory in the calibration. The previous checkpoint took body poses as given. The Fixed-Lag Fusion task examines loop-factor retention and covariance. This task examines joint motion/clock/bias recovery and physical continuation with no optical corrections. External benchmark comparisons remain unverified. |
| Verifiability | An analytically differentiated 6-DOF physical trajectory generates noisy raw specific force, gyro samples and row-timed fiducial pixels. The verifier uses private physical poses to assess clock and mount estimates separately, then independently steps the published inertial model using the returned frozen biases and reprojects the validation pixels. It also alters only those pixels and checks the fit and continuation remain identical. |
| Realism | The camera timestamp counter can reset independently of the IMU bias transition. The body reference is sparse and noisy on the fit interval. Continued motion must use frozen biases and the known gravity vector. The scenarios use authored sensor data at bench-calibration noise levels. Intrinsics, gyro and accelerometer scale and world target geometry are provided. The task does not certify hardware capture or estimate bias changepoints. |
| Difficulty | A valid result must distinguish two bias epochs and two camera offsets from shared skew, readout and mounting geometry while reconstructing physically plausible motion through the capture. A wrong fit can lower residuals by moving extrinsics or clock parameters while producing substantial inertial drift after optical information is withheld. Hosted model difficulty and the five-day workload target remain unmeasured. |
| Initial feasibility | A NumPy-only damped joint fit integrates each candidate bias correction into the camera reprojection objective. Two independent motions use 200 Hz inertial samples and disjoint continuation windows. The local solver has no dense pose or camera reference supplied as an input. |

The first prototype fit reached 0.81 mm body-position RMS, with its
separate 2.73 s continuation at 9.86 mm RMS and 21.3 mm terminal error.
The other motion reached 0.55 mm fit RMS, 10.42 mm continuation RMS and
23.0 mm terminal error. Forcing one fitted bias across each capture's two
instrument states increased continuation RMS to 1.403 m and 0.966 m. It
also changed camera parameters and produced major optical residuals, even
with both clock epochs, readout and mounts still free. This is an ablation
of the same dynamics and measurements.

The verifier gives 20% of checkpoint-five reward to preserved checkpoint
four and 80% to two equally weighted raw-inertial missions. The earlier
four packaged steps retain their original inputs and scoring. The frozen
continuation begins at an exact supplied initial pose and velocity and
cannot use validation pixels to update state.

On the exact cumulative package, the local reference scored 1.0, the
checkpoint-four reference scored 0.20, and the no-op scored 0.0. The
independent holdout grader measured 0.248–0.468 px using the fitted camera
parameters against surveyed motion and 3.47–4.14 px using raw inertial
continuation. Perturbing only continuation pixels left every fitted bias,
camera parameter and reported motion pose unchanged and raised optical
RMS to 14.78–15.64 px in the perturbed drive. The maintained packaging
regression and Oddish preflight passed. Oddish accepted v3 with one
GPT‑6.2 Sol xhigh attempt and both controls.
[Raw-inertial calibration evaluation](https://www.oddish.app/experiments/64c9c219)
