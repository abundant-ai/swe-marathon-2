# PX4 estimator reset and recovery

Maintain safe software-only NED flight through estimator resets, asynchronous sensors and loss of horizontal estimates. The early checkpoints reconstruct PX4-shaped estimator streams and run waypoint missions in a point-mass plant. The final checkpoints commission two inertial instruments from bench captures and fly a native MuJoCo rigid body using the calibrated increments and delayed visual aiding.

## Design dimensions

| Dimension | Evidence and limits |
| --- | --- |
| Novelty | Localization Replay compares estimator outputs on recorded streams. Here the reconstructed frame drives commanded acceleration and changes the physical trajectory. Fixed Lag Fusion estimates pose across late measurements. This task reconciles estimator-provided reset metadata and explicitly governs the data authority used for flight feedback. Comparisons to other SWE benchmarks remain unverified. |
| Verifiability | The private verifier knows true position, injected offsets, axis validity, counter wrap, and time. It applies the actual submitted acceleration to its own constant-acceleration plant and compares the output estimate to that physical state. A real dwell at the waypoint is required. |
| Realism | PX4 publishes separate capture and publication timestamps, local-frame validity flags and reset counters. A public report describes repeated altitude resets with range-only height. PX4 also supports parallel EKF instances for isolating inconsistent sensor inputs. The task models estimator-output supervision with authored offsets, capture faults and a point-mass plant. [PX4 local position](https://docs.px4.io/main/en/msg_docs/VehicleLocalPosition.html) · [Altitude reset report](https://github.com/PX4/PX4-Autopilot/issues/28263) · [Multiple EKF instances](https://docs.px4.io/main/en/advanced_config/tuning_the_ecl_ekf#running-multiple-ekf-instances) |
| Difficulty | The controller must track reset continuity per epoch and axis group, check innovations against an independent inertial interval, qualify standby sources, retain dwell across a sound handover and bound physical motion during outages. The revision has no hosted model or five-day workload measurement yet. |
| Initial feasibility | The early reference combines per-source calibration ledgers, a bounded physical predictor and damped feedback with a stopping-distance limit. The newer reference fits affine device time and temperature-dependent intrinsics, uses a bounded capture-time replay history and controls orientation and thrust through the native plant. |

## Verification

The first checkpoint independently checks replay chronology, exact retained positions, wraparound, stale publications and atomic malformed-input behavior. The second and third checkpoints execute healthy and faulted NED missions, measure actual position error and completion tick, and check neutral hold and abort in unrecoverable routes. Those checkpoints retain their cumulative diagnostic scores.

The fourth checkpoint reruns seven earlier checks and adds nine redundant-estimator missions. They exercise independently reset backup sources, healthy-flagged position and velocity faults, boot epoch regression, repeated capture times, unregistered backup frames, broken inertial intervals, multiple overlapping faults and high-speed loss of authority. The verifier observes actual handovers, physical waypoint dwell, braking and the continuous-time extremum of each commanded movement within the enclosure. Its checkpoint reward is 20% legacy pass rate plus 80% redundant-supervisor pass rate.

The fifth checkpoint fits two asynchronously sampled IMUs on multiaxis motion and independently varied temperatures. It evaluates corrected rates on a separate holdout motion and checks rank-deficient calibration and atomic failures. The sixth checkpoint executes seven separate native MuJoCo 3.3.7 missions with a bounded body-rate loop, lagged thrust, gravity, floor contacts, attitude and yaw. The candidate calibrates its instruments before the flights. The verifier checks causal replay of partial visual aids, rejected capture and frame epochs, current-time pose and velocity, physical waypoint dwell, measured braking and pre-impact touchdown. Two otherwise distinct landing routes require a physical controlled descent. One restores valid horizontal aiding after the irreversible landing decision. Both must land and disarm.

The sixth checkpoint determines the task reward as 20% of the fourth checkpoint's combined diagnostics, 15% independent commissioning checks and 65% full native-flight missions. A native mission earns credit when it satisfies both estimator checks and the measured physical outcome.

All captures and motion fixtures are authored. The software interfaces reference PX4's integrated FRD IMU message, external odometry, delayed fusion and body-rate offboard requests. The task uses an authored point mass and a headless rigid body with a simplified rotor response. It requires neither PX4 firmware nor binary ULog playback. [ULog specification](https://docs.px4.io/main/en/dev_log/ulog_file_format) · [VehicleImu](https://docs.px4.io/main/en/msg_docs/VehicleImu) · [VehicleOdometry](https://docs.px4.io/main/en/msg_docs/VehicleOdometry) · [EKF2 delayed fusion](https://docs.px4.io/main/en/advanced_config/tuning_the_ecl_ekf) · [PX4 Offboard](https://docs.px4.io/main/en/flight_modes/offboard)

## Hackability assessment

A fixed script could fit deterministic fixture timings if it learned the private cases. Opaque source identifiers, different handover sequences, the motion-triggered blackout and a separately integrated plant constrain this shortcut. The simulator uses deterministic source fault models and exact physical acceleration feedback. The verifier runs the submitted code separately as a low-privilege user and keeps the evidence directory root-only.

## Development log

### 2026-11-24

The original hosted pilot scored 0.9048 overall for GPT-6.2 Sol xhigh, with 0.7143 at the last checkpoint. It missed the case requiring both an inertial bridge and a frame reset, and left the flight envelope during a permanent estimate loss. The revision retains both cases and separately tests source handover, bounded braking and abort while already moving. [Original Oddish experiment](https://www.oddish.app/experiments/57208689)

The revised package passes local reference and no-op controls at 1.0 and 0.0. The original reference passed the legacy checks and scored 0.20 on the revised final checkpoint. Build with `python3 -B scripts/package_task.py` and run `python3 -m pytest checks/test_px4_recovery_package.py` for the maintained package regression.

The hosted redundant-estimator revision scored 0.9714 for GPT-6.2 Sol xhigh. It passed all nine new supervisor cases and again left the flight envelope in the older permanent-loss case. The native revision tests physical braking and landing under two moving losses with different headings and an explicit check that late valid aiding cannot cancel an irreversible landing.

Locally, the native reference passes all 30 checks and the no-op scores 0.0. Moving otherwise-valid vision corrections to packet arrival instead of capture caused all seven native flights to fail. Omitting commissioned thermal corrections in live estimation passed two native flights. A controller that reported landing while maintaining altitude passed five native flights and missed both required touchdowns. The reference landed and disarmed at measured pre-impact speeds of 0.136 m/s and 0.125 m/s. Native-flight results use the pinned headless Python MuJoCo runtime.

The archived GPT implementation scored 0.142857 on the revised verifier. The
fresh GPT‑6.2 Sol xhigh trial scored 0.971429. All nine redundant-source
missions passed, including the new moving blackout. The original permanent
loss still drove the simulated vehicle outside its flight envelope.
[Version 2 results](https://www.oddish.app/experiments/9a2d8a0f)

Oddish accepted the native package with one GPT‑6.2 Sol xhigh attempt,
one reference, and one no-op. [Version 3 trial](https://www.oddish.app/experiments/3d3f9dc5)

Fresh GPT‑6.2 Sol xhigh scored 0.660635 on version 3. It passed all seven
inertial commissioning checks and five of seven native flights. Both
irrecoverable-loss missions moved to landing while horizontal speed was
still above the declared transition limit. In the exact local replay,
the candidate committed at 0.264 and 0.243 m/s. Two independent
counterfactuals completed both native landings. One reserved more braking
authority in the approach, and one removed an excessive damping term
during braking. Eight retained redundant-source cases also failed.
The candidate reached normal completion but omitted the selected estimator
from its final response. The hosted reference and no-op scored 1.0 and
0.0. [Version 3 results](https://www.oddish.app/experiments/3d3f9dc5)

Oddish's trajectory review found that the candidate changed contact
handling after its last flight stress test. The exact replay isolated the
earlier speed and braking decisions that prevented both landings.

#### Pad landing with degraded aiding

Checkpoint seven uses capture-time optical flow and oblique range alongside
the commissioned IMUs. After losing absolute position, the candidate has to
brake, correct the sensor's lever-arm motion, screen invalid aiding, and
physically approach a declared pad before descending. The four MuJoCo
cases vary aircraft mass, thrust availability, wind and actuator response.
[PX4 optical flow](https://docs.px4.io/main/en/sensor/optical_flow) ·
[PX4 range obstruction detection](https://docs.px4.io/main/en/advanced_config/tuning_the_ecl_ekf#range-finder-obstruction-detection)

The frozen reference passed 34 of 34 checks, the no-op scored 0.0, and the
exact version 3 GPT submission scored 0.132127. All four reference flights
touched down at 0.093–0.109 m/s down, with at most 0.027 m/s horizontal
speed. Applying corrections at arrival or skipping pad positioning each
failed all four. Disabling optical velocity or range-derived vertical rate
each left one passing landing. The blocked-range mission rejected nine
returns, held for thirteen ticks and resumed to touchdown.

Fresh GPT‑6.2 Sol xhigh passed all four pad-landing missions and scored
0.951841. The last checkpoint retained losses from one earlier
permanent-loss native flight and eight redundant-source checks. The hosted
reference and no-op scored 1.0 and 0.0. [Pad landing experiment](https://www.oddish.app/experiments/16ebd21c)

## Moving-cart precision touchdown

Checkpoint 8 adds a moving landing surface while preserving the earlier software-only PX4 workflows. The PX4 moving-target estimator keeps target motion separate from vehicle state, handles out-of-order observations against capture-time state, and supports a bounded landing setpoint lookahead. Its published deep dive includes moving-target SITL and real flight examples. This checkpoint applies the same measurement and control problem in a small authored flight enclosure with a laboratory interlock during stale target evidence. [PX4 precision landing](https://docs.px4.io/main/en/advanced_features/precland) · [PX4 Vision Target Estimator deep dive](https://docs.px4.io/main/en/advanced_features/vision_target_estimator_advanced#moving-target-mode-experimental)

The pinned MuJoCo 3.3.7 plant integrates an aircraft free body with finite rate torque and collective response. A cart moves on prescribed planar and yaw joints with explicit velocities for native contact. The worker receives independent vehicle pose and velocity samples and timestamped camera-relative marker detections with a nonidentity mount and optical lever arm. Cart motion is private to the camera generator and verifier. The verifier computes freshness from delivered source acquisitions, inspects the entire stale interval, and measures physical touchdown against the local surface velocity including cart rotation.

The three new enclosure sessions require uninterrupted capture-time prediction, recovery from a transient vision blackout after descent begins, and a latched abort on permanent loss. The response's declared phase is checked alongside physical clearance. A proof ablation removed the stale-target gate and still landed after the short blackout. It violated all stale ticks and reached about 0.36 m above the deck while evidence was stale, compared with 0.55 m for the qualified worker. A separate no-prediction ablation retained the earlier PX4 behavior and failed to reach the moving deck by 14 seconds, with target error around 0.116 m RMS compared with 0.009–0.010 m for the packaged reference.

The reference landed eastbound at 7.332 seconds with 0.015 m center error and 0.049 m/s relative slip. After a westbound blackout it held for all 25 stale ticks, then landed at 9.960 seconds with 0.018 m center error, 0.033 m/s relative slip, and at least 0.554 m clearance while stale. On permanent loss it maintained at least 0.562 m clearance over 219 stale ticks, latched abort, and made no unintended contact. First contact is measured on a spherical contact body. Stable post-touchdown retention, rendered vision, and actual PX4 firmware or hardware remain outside this plant. Geometry and sensor data are authored locally. No upstream flight assets are redistributed.

The final reward preserves 20% of the prior cumulative landing result and assigns 80% to the equally weighted moving-cart missions. Native moving-cart credit requires at least one qualified moving touchdown. The prior reference and the no-prediction control retained 0.20. The full reference scored 1.0 and the no-op scored 0.0, both locally and on Oddish. Oddish preflight, the maintained packaging test, and the public streaming example passed locally.

To exercise the public capture stream in the candidate image, run:

```sh
cd /app
python3 -m px4_recovery land-moving --spec /app/example/moving-cart-spec.json \
    < /app/example/moving-cart-observations.jsonl
```

Oddish accepted v5 with one fresh GPT‑6.2 Sol xhigh attempt and both
controls. [Moving-cart landing evaluation](https://www.oddish.app/experiments/1faffdf4)

Fresh GPT‑6.2 Sol xhigh scored 0.879771. It passed both moving-cart
landings and the permanent-loss abort. Deck contact was within 19.4
and 10.5 mm of the target, with relative slip below 0.021 m/s.
The earlier fixed-pad checkpoint scored 0.398857. Three descents began
before the measured horizontal braking requirement was met.
The hosted reference and no-op scored 1.0 and 0.0.

## Relative landing using raw onboard aids

Stage 9 preserves the earlier moving-cart command and removes its supplied ownship navigation state from a new sensor-only command. The worker receives raw angular rate and specific force, integrated ground optical flow with slant range, normalized image-plane target bearing, and separately timed beacon range. The camera, floor sensor and range origins have independent calibrations. Absolute positions, cart trajectory and cart height stay inside the native plant and grader. Vertical cart motion means a fixed deck-height projection cannot replace the marker range stream. [PX4 target-state separation and capture-time fusion](https://docs.px4.io/main/en/advanced_features/vision_target_estimator_advanced#filter-observability) · [PX4 optical-flow conventions](https://docs.px4.io/main/en/sensor/optical_flow) · [Tzoumanikas et al. moving-target visual–inertial flight](https://doi.org/10.1002/rob.21821)

The native plant generates delayed, reordered observations and a few poor-quality measurements. It checks current three-dimensional relative position and velocity, horizontal velocity before each descent, independent floor-referenced braking, and first contact with the moving deck. A permanent bearing blackout retains beacon range, so the task requires the pilot to recognize that range alone cannot support descent. A temporary flow blackout removes ground velocity evidence while bearing and beacon range stay available. The worker must hold safely and recover for each recoverable fault.

The packaged native reference touched the nominal cart at 8.048 s with 0.063 m center error and 0.029 m/s relative slip. It held through 25 stale-bearing intervals at no less than 0.651 m clearance, reacquired, and touched down at 11.644 s with 0.069 m center error and 0.034 m/s slip. On permanent bearing loss, it latched abort through 281 stale-bearing intervals while target range continued. Late ground speed remained below 0.038 m/s. The independent floor-flow blackout held for 17 affected intervals with at least 0.691 m deck clearance, and recovered to first contact at 10.816 s with a 0.064 m center miss. At each actual authority change into descent, relative horizontal speed was at or below 0.114 m/s.

In direct flight comparisons, attaching delayed rays and ranges to the arrival-time vehicle frame raised nominal relative position RMSE from 0.019 m to 0.377 m and prevented touchdown. The controller that propagated inertial horizontal velocity without ground-velocity correction left the flight enclosure and reached 0.763 m/s on the permanent-loss hold. Both effects remain detectable when the earlier static and moving-pad commands are available.

The MuJoCo 3.3.7 fixture uses authored inertials, mount calibrations, synthetic sensor observations, a driven cart, and an airborne rigid body with a simple contact shoe. Floor flow observes stationary surrounding texture under the modeled commissioning setup. The witness stops at first native deck contact. Post-touchdown retention, PX4 firmware, camera image processing, and field qualification are outside the scope of this simulation. The final reward retains 20% of the earlier moving-cart checkpoint result and requires a valid native touchdown for credit across the four new relative missions.

The frozen cumulative reference scored 1.0 and passed all four raw-sensor missions. The no-op scored 0.0. The exact earlier Stage 8 reference and the otherwise-identical control that omits the optical ground-velocity correction each scored 0.20 with no new missions passing. The maintained package test passed.

Oddish preflight passed. The hosted reference and no-op scored 1.0 and
0.0. One fresh GPT‑6.2 Sol xhigh attempt is underway.
[Relative-aiding evaluation](https://www.oddish.app/experiments/dd17ac79)
