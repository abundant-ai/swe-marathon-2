# Frozen policy sim-to-sim bridge

An exported controller depends on the sensor and actuator conventions used at deployment. The bridge reconstructs observations, runs the frozen actor on the commissioned clock, finds divergence between exports, and compensates measured drive dynamics before sending bounded commands to the target simulator.

## Design dimensions

| Dimension | Evidence and limitations |
| --- | --- |
| Novelty | Unitree documents training a locomotion policy in Isaac Lab and validating the trained strategy in MuJoCo. The public Isaac Lab issue describes a model that immediately fell after a transfer despite custom joint order being present during training. This task turns those interface failures into a software qualification workflow. Localization Replay in this collection compares estimator outputs. MuJoCo Branch Replay reproduces a single native integration or its branches. Here independently named backend exports must produce the same policy decisions and actual articulated motion. Comparisons across SWE-Marathon v1 and the other coding suites remain unverified. [Unitree training and deployment](https://github.com/unitreerobotics/unitree_rl_lab/blob/main/README.md) · [Isaac Lab issue #4383](https://github.com/isaac-sim/IsaacLab/issues/4383) |
| Verifiability | The grader generates physically named poses and angular velocities, independently encodes each sensor export, and predicts the frozen dense actor with NumPy matrices. Equivalent actuator targets drive a native MuJoCo shadow model alongside an independent canonical controller. The verifier compares observed commands and actual position trajectories. |
| Realism | Training and target layouts vary separately for sensor and actuator identity, sign, position zero, pose reference, orientation layout and angular velocity frame. Actor history is distinct from physics cadence. A watchdog protects actuator authority from stale streams, and trace qualification compares physical decision time across two rates. The initial checkpoints use native MuJoCo, authored actors and training-style exports. The final checkpoint adds a released Go2 actor and physical terrain. |
| Difficulty | Initially correct records can become wrong after a held tick, normalization mismatch, negative quaternion, replayed frame or rearm. The solver must maintain independent clocks and history, compare exact stages of inference, and preserve hardware-facing state after restart. It is a compact pilot with no measured five-day workload or GPT difficulty claim. |
| Initial feasibility | Standard-library validation, SE(3) vector rotation, a dense tensor interpreter, and atomic snapshots suffice on the candidate side. The independent verifier uses NumPy and invokes MuJoCo 3.3.7 for the native mission. Local calibrated endpoints and package checks establish feasibility. Hosted reference and no-op controls qualified the first six checkpoints. [MuJoCo Python runtime](https://mujoco.readthedocs.io/en/3.3.7/python.html) |

The first six checkpoints include an authored fixed-deck 8-joint articulated model and authored frozen controllers. The seventh uses an openly released velocity actor from Go2 RL Lab and its 12-joint free-base Go2 deployment model. This public model retains the source joint ranges, masses and collision shapes. The exercise uses simulated support and motion, with license notices in the public fixture. [Public deployment assets and notices](environment/example/locomotion/README.md) · [MuJoCo license](https://github.com/google-deepmind/mujoco/blob/main/LICENSE)

## Checkpoints and reward

1. Recover the normalized training observation from rotated multi-axis sensor exports and reject malformed mappings atomically.
2. Satisfy phase, frame-history, actuator identity and clipping requirements with a fixed multi-layer actor and observed commands.
3. Isolate unhealthy and stale sensor streams, rearm at a new policy phase, and preserve prior action, history and exact replay over process restart.
4. Locate exact earliest divergence for paired heterogeneous-rate streams and actuate a native articulated shadow plant with both exported layouts.
5. Commission missing encoder and actuator bindings from native excitation captures, identify the affine clock correction, distinguish ambiguous fits from held-out failure, and use the accepted map to run the same actor on a different native plant.
6. Identify delayed coupled actuators from native torque logs. Run the frozen actor with causal compensation and quantify tracking, stability and restart recovery on held-out asymmetric plants.
7. Supervise the published locomotion actor under live foot contact telemetry, a motion lease and unclean restart against physical free-base rollout. Keep exact 450-value term-wise history and emit targets on an independently permuted bus.

Checkpoints 1–4 retain their cumulative diagnostic scores. Checkpoint 5 scores 0.20 times the fraction of the 13 retained missions that pass plus 0.80 times the fraction of its nine commissioning and deployment missions that pass. Each component requires evidence of a correct positive operation. Rejection-only behavior earns zero. A fitted map validated as unusable can still earn a calibration mission by reporting the correct map and held-out error. Each deadline and tolerance follows the published numerical contract. The original native missions measure parity against an independently actuated shadow. Checkpoint 6 scores 0.20 times the retained checkpoint 5 reward, plus 0.15 times the fraction of seven drive identification and safe-start missions, plus 0.65 times the fraction of five complete physical rollout missions. The identification component requires at least one positive fitted model. A fit without deployable physical recovery can reach 0.35. Each final rollout requires the unchanged actor, commissioned output limits, physical tracking and recovery, and cloud-process-compatible restart behavior.

Checkpoint 7 determines the task reward from 20% of the retained checkpoint 6 score and 80% of three free-base missions. Each mission combines actor parity, support and command authority, physically safe course progress and a measured stop. One mission induces loaded slip with a push on split terrain. One drops contact telemetry while the robot is moving and kills the controller between a committed reply and its retry. One expires a motion lease before reissuing it for a changed heading. The native verifier integrates the candidate's exact targets against body forces and actual foot contacts. The published ONNX weights, model and sample stream permit local reproduction of the deployment interface. [RoboGauge primary paper](https://www.roboticsproceedings.org/rss22/p156.html)

The packaged checkpoint 7 reference passed 37 of 37 checks locally. The no-op scored 0.0 and the complete checkpoint 6 reference scored 0.20. The free-base reference missions traveled 2.48–2.63 m and stopped below 0.015 m/s. The blackout began at 0.416 m/s and horizontal speed fell to 0.017 m/s before reacquisition. The push produced 0.614 m/s measured foot slip and tracking returned 0.40 s after push onset. Wrong history layout, index-based motor binding and ignoring loaded slip passed none of the three new missions. Removing durable state passed the two uninterrupted missions and failed the interrupted retry. Local verification used CPU ONNX Runtime 1.23.2 and native headless MuJoCo 3.3.7.

Generate the runtime with `python3 -B scripts/package_task.py`. Environment files expose only the example manifest and sample. The reference and private Python fixtures live in separate harness paths. Run Oddish preflight on the generated directory.

## Hackability assessment

| Finding | Evidence | Remaining risk |
| --- | --- | --- |
| 🟡 YELLOW / MEDIUM | Fixture-only recognition could bypass a lookup. The verifier varies joint count, metadata, seed, clocks, input traces, frozen networks and protocol incidents. It checks native physical dynamics after applying submitted commands. | More held-out MJCF shapes and direct fault-injection variants would help measure transfer beyond the authored plant. |
| 🟡 YELLOW / UNASSESSED | The separate verifier copies only regular declared candidate files and runs the package with less privilege. No private model files or reward path are passed to candidate calls. | Verify actual hosted artifact placement and container rules during hosted controls. Local process checks do not establish cloud isolation. |
| 🟢 GREEN / LOW | The score does not use a model judge or trust a reported success label. It compares ground-truth causes and the physical numerical outputs and replays actual restart responses. | Numeric checks cover only the published compact actor runtime and sample conditions. |

The highest supported concern is medium. No credentials or live robot controls are part of the scenario.

## Coupled-drive commissioning and physical qualification

Both hosted version 2 GPT‑6.2 Sol xhigh attempts scored 1.0, with matching 1.0 oracle and 0.0 no-op controls. The recorded trajectories took about 215 and 250 seconds. The parity check could be solved by running the same correctly mapped actor on both copies of each target. The new checkpoint grades the physical behavior of the compensated plant against the frozen actor's changing canonical goals. [Full batch](https://www.oddish.app/experiments/57208689) · [Six-task batch](https://www.oddish.app/experiments/afbb773d)

The source interface is an authored Isaac-style export. The target is the pinned MuJoCo 3.3.7 native fixed-deck articulated rig. The actual MuJoCo actuator forces and measured joint states supply the identification captures. A bounded delay queue models the target command bus, a coupled gain decodes commands into native servo effort, and native springs, damping and asymmetric inertias act on the links. The verifier uses separate native captures, recorded measured effort, and known gains and latencies to check the identified equations without fitting the candidate solution. It also generates a repeated-excitation case whose two delay hypotheses are observationally identical. The external step torques and initial states are held out. The plants have authored geometry with no vendor assets. Logical simulation runs at 5 ms per physics tick, with 365 ticks per physical test and actor updates every third tick. [Isaac Lab delayed actuators](https://isaac-sim.github.io/IsaacLab/v2.0.0/source/api/lab/isaaclab.actuators.html) · [MuJoCo actuation](https://mujoco.readthedocs.io/en/3.3.7/computation/index.html)

The reference fits each delay hypothesis with normalized least squares, freezes the measured model, and applies a causal inverse drive map with command lead and bounded integral load rejection. The verifier actuates each held-out target using only the submitted bus and independently compares decoded goals with measured positions. Its metrics also include peak speed and elapsed ticks to sustained recovery after disturbance or re-arm. An uncompensated native side run provides a diagnostic baseline. An uninterrupted duplicate session on identical observed input tests continuation across actual restart. The contract supports different causal controllers. This is a fixed-deck actuator experiment with no free-base balance, hardware testing, or Isaac runtime execution.

## Development log

### 2026-11-24

Implemented four cumulative checkpoints and varied named missions. Built a frozen-actor bridge and an independent NumPy verifier with a closed-loop native MuJoCo plant. Packaged reference missions passed 3/3, 5/5, 7/7, and 13/13. No-op scored zero at every checkpoint. The native mission used eight articulated joints and 19 policy updates over 55 physics steps. Its final articulated displacement was 0.542 rad in L2 norm, and the peak position difference from the independent shadow was under 7e-16 rad. Oddish preflight found no issues, and the package test passed. Hosted execution, difficulty, and model-based quality ratings are pending.

The hardened packaged reference and no-op scored 1.0 and 0.0 locally at the final checkpoint. Oddish accepted version 1 into the six-task batch with both controls and one GPT‑6.2 Sol xhigh attempt. Bundle SHA-256 is `179f8ef8b9e204af59e5a8904c6489ed31f35e3bf69b00c2a8c76848e4333d9e`. [Oddish experiment](https://www.oddish.app/experiments/439b651d)


Hosted version 1 received 1.0 at all four checkpoints from one GPT-6.2 Sol xhigh trial. Oddish classified the solution as legitimate and recorded reference 1.0 and no-op 0.0. The problem then supplied exact simulator conventions and tested actuator mapping on a single native plant. Version 2 retains those cases and adds independent sensor and actuator identification, bounded affine clock alignment, and qualification against a separate perturbation capture. Duplicate encoder or actuator evidence gives an ambiguous report, and absent overlap is distinguished from held-out errors. Native deployment cases use different mass and damping settings from commissioning, with an output-loss/restart and active watchdog branch. All additional assets and capture controls are authored. [Version 1 Oddish experiment](https://www.oddish.app/experiments/439b651d)

A feasible implementation uses time-grid interpolation, offset-removed residuals, a two-best bipartite assignment for each clock hypothesis, and an independent second assignment for the motor bus. Exact tie checks require keeping alternative hypotheses across clock cells and within a single map. Validation compares against the plant's known permutations, signed offsets, clock and perturbations and does not reuse the author optimizer. The discrete clock grid and commissioned bounded channel widths model a controlled bring-up capture. Live free-base locomotion and commissioning noisy hardware beyond the fixture assumptions remain outside the pilot.

The revised bundle passed local reference and no-op controls at 1.0 and 0.0. Oddish preflight reported no findings. The hosted version 2 batch contains one GPT‑6.2 Sol xhigh trial and both controls. Bundle SHA-256 is `9ccc028855db225ed6a9f37ba5153474350681dfc0bf27a65a3e211b87eda1ca`. [Version 2 batch](https://www.oddish.app/experiments/afbb773d)

Added the sixth checkpoint with native delayed-drive commissioning and closed-loop load rejection. The packaged reference scored 1.0 at all six checkpoints and passed 34 of 34 final checks. The no-op scored 0.0. The complete version 2 reference replayed against the new final checkpoint scored 0.20. A full drive identifier and static inverse with correct clipping and unchanged actor scored 0.35, passing all identification checks and failing all five physical missions. The native reference recorded joint tracking RMS of 0.081–0.103 rad, compared with 0.234–0.283 rad for uncompensated native runs. Final sustained-load RMS was 0.049–0.088 rad. Sustained recovery began in 0–23 ticks after the transient and in 20–103 ticks after re-arm. Each tick is 5 ms. The final reference took 38.92 seconds wall time and 18.09 seconds user CPU when run alongside the other controls. The package pytest suite passed and Oddish preflight returned no findings. Version 3 hosted execution and model difficulty remain unmeasured.

The archived GPT implementation from the original 16-task run also scored
0.20 against the exact new verifier. Fresh GPT‑6.2 Sol xhigh scored 1.0 at all
six checkpoints and passed all 34 final checks. The five native load and
recovery missions recorded joint tracking RMS of 0.049–0.066 rad. The hosted
reference and no-op scored 1.0 and 0.0. Oddish classified the solver run as a
legitimate success. [Version 3 follow-up](https://www.oddish.app/experiments/20ade25d)

The checkpoint 7 bundle passed Oddish preflight and was submitted with one
fresh GPT‑6.2 Sol xhigh attempt, the reference and the no-op.
[Free-base deployment experiment](https://www.oddish.app/experiments/ba541e83)

Fresh GPT‑6.2 Sol xhigh scored 1.0 on all seven checkpoints and passed all 37
final checks. It covered 2.48–2.63 m across the three free-base missions and
finished each with horizontal speed below 0.015 m/s. During the contact
blackout it slowed to 0.0174 m/s and replayed the unread response after
restart. The hosted reference and no-op scored 1.0 and 0.0.
[Free-base results](https://www.oddish.app/experiments/ba541e83)

## Live course routing

Checkpoint eight gives the bridge ownership of the motion request. It
receives delayed localization and versioned obstacle rectangles, chooses
a detour for the frozen Go2 actor, and holds when the map lease expires.
Two mirrored surveys close a passage while the simulated robot is moving.
The third loses map updates, kills the live worker after a committed
reply, and resumes under the new map.

| Dimension | Evidence |
| --- | --- |
| Novelty | The previous checkpoint provides twist requests and tests execution. The new one makes route choice, stopping authority, and recovery part of the same deployable bridge. |
| Verifiability | Independent integration checks actor parity, native contacts, footprint clearance, valid map revisions, physical stopping, and arrival dwell. The manifest declares the mission deadline. |
| Realism | A laboratory inspection robot can receive delayed localization or discover a blocked aisle after setting off. The authored course uses a projected planar footprint and a scripted obstruction. It leaves sensor perception, moving-person prediction, and hardware qualification for later experiments. |
| Difficulty | The bridge has to join geometric planning to measured walking dynamics and durably fence stale maps. Reusing initial geometry either led into the obstruction or dropped below the required native clearance. |
| Initial feasibility | The frozen reference uses footprint-aware graph search, body-frame tracking, and an atomic state snapshot for map and actor. Three native mission witnesses and a runnable public initial stream passed. |

The final score retains 20% of checkpoint seven and assigns 80% across the
three complete course missions. The local reference passed all 40 checks
and the no-op scored 0.0. The reference reached its goals within
0.094–0.102 m, maintained 0.503–0.510 m minimum site clearance against
the 0.46 m radius, and made zero barrier contacts. It slowed from
0.398 m/s before map loss to 0.012 m/s while holding, replayed the accepted
reply after the worker died, and completed the inspection. A fixed-map
ablation failed both mirrored courses. Ignoring lease expiry failed the
blackout case.

The exact previous GPT artifact passed the retained checkpoint and scored
0.20 on the new final verifier.

Oddish accepted v5 with one fresh GPT‑6.2 Sol xhigh attempt. The hosted
reference and no-op scored 1.0 and 0.0. [Live course evaluation](https://www.oddish.app/experiments/8bb6b62a)

Fresh GPT‑6.2 Sol xhigh scored 1.0 and passed all 40 checks. The three
course missions maintained 0.485–0.513 m minimum clearance and stopped
within 0.081–0.112 m of the goal. Each finished below 0.020 m/s. The
map-loss mission also replayed its committed response after worker death.

## Native range-scan navigation and epoch recovery

### 2026-11-24

The ninth checkpoint feeds the frozen Go2 bridge scanner returns and
relative odometry rather than surveyed live poses and a map snapshot.
A prior teaching run supplies an anchored set of raw observations.
During inspection the shelf moves, closing one lane and reopening the
other. In the recovery mission a service intervention relocates the
stationary robot without supplying its new surveyed pose. The controller
must stop on missing evidence, retire old epoch scans, reestablish its
map pose from the new scans, and reuse the frozen actor. This follows the
recorded scan and odometry workflow in SLAM Toolbox and the distinction
between local continuous odometry and surveyed map pose in REP 105.
[SLAM Toolbox](https://github.com/SteveMacenski/slam_toolbox/blob/ros2/README.md) ·
[ROS REP 105](https://www.ros.org/reps/rep-0105.html)

| Dimension | Evidence and scope |
| --- | --- |
| Novelty | The previous course consumed a finished map and surveyed localization. This checkpoint requires generating and repairing spatial evidence, relating independent sensor and odometry frames, and planning with that evidence in a real native walking loop. The two mirror courses share the same goal. External benchmark comparisons remain unverified. |
| Verifiability | MuJoCo rays intersect the same physical walls, rotated divider and movable shelf used by the collision checker. Native base pose and contact measurements are private. The evaluator checks the submitted actor outputs against independent ONNX execution, observes physical clearance and lane use, and independently verifies accepted scan times, odometry epochs, and the restored pose after SIGKILL. |
| Realism | Range capture and packet delivery have separate times. The scanner has a rigid offset and angular mount, and odometry supplies body-frame increments with authored drift. The IMU yaw gauge can reset independently of surveyed yaw. Models use 2D gravity-leveled scans and an authored service relocation. They do not require a live ROS graph, a hardware scanner driver, or a full 3D terrain mapper. |
| Difficulty | The solution has to keep map evidence, odometry history, and motion authority coherent when scans arrive out of order and the odometry origin changes. Calibration-blind and static-map strategies can act on plausible local velocities while crossing the physical shell. Hosted difficulty and the five-day workload target remain unmeasured. |
| Initial feasibility | The reference builds occupancy evidence from teaching rays, retains a robust distance-field target for scan matching, applies late scans at their acquisition pose, and routes through the current sensor-derived geometry. The frozen actor, causal request fields and hardware bounds are the same as during prior walking checkpoints. |

The independent native prototype completed both original mirrored courses.
With a moved shelf and a reset, the first alignment error was 11.7 mm and
0.00331 rad. The robot crossed the open bypass at -1.090 m, maintained
0.551 m clearance and finished 0.104 m from its goal. The reflected course
crossed at +1.060 m with 0.530 m clearance and finished 0.078 m from its
goal. Both had zero barrier contacts and 22 settled ticks. The frozen
package uses a common map goal, out-of-order scans and a separate IMU
yaw gauge after reset.

The odometry-only ablation retained roughly 0.59 m and 0.50 rad of error
on first recovery and never completed the course. Leaving the taught map
static violated the physical clearance shell after the shelf moved.
Ignoring the live scanner mount produced 0.177 m and 0.193 rad of first
recovery error and later violated the shell. These controls use the same
actor and machine geometry. The ninth checkpoint retains 20% of checkpoint
eight's reward and gives 80% to the two native raw-scan missions.

The frozen package scored 1.0 with 42 of 42 checks, compared with 0.20
for the complete checkpoint-eight reference and 0.0 for the no-op.
The new missions received 466 delayed scans, 93 of them out of order.
The reset case slowed from 0.382 m/s before scan loss to 0.011 m/s before
operator relocation. The restarted process rejected a changed retry,
returned the exact committed reply, and recovered the new pose within
0.0126 m and 0.00639 rad. Minimum clearances were 0.549 m and 0.529 m,
with zero barrier contacts in both missions. The robot settled 0.089 m
and 0.082 m from the common goal, respectively.

The exact frozen odometry-only control failed to complete both missions,
with final goal errors of 3.602 m and 0.502 m. The maintained packaging
test passed. Validation used pinned local MuJoCo and CPU ONNX Runtime.
Oddish preflight passed. The hosted reference and no-op scored 1.0 and
0.0. One fresh GPT‑6.2 Sol xhigh attempt is underway.
[Native range-scan evaluation](https://www.oddish.app/experiments/dcfc86bc)
