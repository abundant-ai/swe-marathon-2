# Robotics software benchmarks, hardest first

The ranking estimates the work a solver would need to integrate the software,
handle realistic failures, and satisfy a verifier on new cases. It weighs
coupled decisions over time, physical correctness, and how much state has to
survive a fault. Run the same GPT‑6.2 Sol xhigh configuration against each
frozen benchmark to measure difficulty. A score below 0.5 is the target.

ROS 2 gives us a large starting community. The ROS project attributed 91.2%
of October 2025 ROS package downloads to ROS 2. Other ecosystems below have
published use cases, runnable examples, or community datasets. [ROS metrics](https://discourse.openrobotics.org/t/2025-ros-metrics-report/52575)

| Rank | Benchmark and ecosystem | Task and independent evidence | Public starting point |
| --- | --- | --- | --- |
| 1 | **[Cross-simulator policy deployment](../tasks/swe-m2-software-engineering/policy-sim-bridge/README.md)** · Isaac Lab, MuJoCo | Port a frozen locomotion policy between engines. Recover named joint and sensor mappings, action scaling, control rates, and observation history. Score both the inputs seen by the policy and stable rollouts under held-out perturbations. | [Unitree sim-to-sim workflow](https://github.com/unitreerobotics/unitree_rl_lab#sim2sim) · [Joint-order user report](https://github.com/isaac-sim/IsaacLab/issues/4383) |
| 2 | **[Two-arm workcell recovery](../tasks/swe-m2-software-engineering/dual-arm-handoff/README.md)** · MoveIt 2 | Replan a loaded transfer in 3D after a fixture update interrupts one arm. Preserve ownership during a handoff and prevent unsafe arm–arm motion through a shared fixture. Score swept clearance, rate limits, and completion through a restart. | [MotionBenchMaker](https://github.com/KavrakiLab/motion_bench_maker) · [Planning-scene examples](https://moveit.picknik.ai/main/doc/examples/planning_scene_ros_api/planning_scene_ros_api_tutorial.html) |
| 3 | **[Mixed-fleet elevator recovery](../tasks/swe-m2-software-engineering/fleet-recovery/README.md)** · Open-RMF | Reschedule two shared elevators for robots with different control capabilities when acknowledgements and infrastructure state disagree. Score released route segments, lift occupancy, parcel custody, and eventual completion. | [Open-RMF hotel and lift demos](https://github.com/open-rmf/rmf_demos#hotel-world) |
| 4 | **[Fixed-lag fusion under delayed and faulty measurements](../tasks/swe-m2-software-engineering/fixed-lag-fusion/README.md)** · GTSAM | Reconcile asynchronous odometry and range factors with bounded memory. Marginalize old states, handle invalid and revised measurements, and preserve uncertainty and provenance across restart. Compare with offline linear solutions and measured poses. | [Fixed-lag smoothing](https://borglab.github.io/gtsam/fixedlagsmootherexample/) · [Plaza2 replay](https://gtbook.github.io/gtsam-examples/RangeISAMExample_plaza2.html) · [Marginalization issue](https://github.com/borglab/gtsam/issues/1976) |
| 5 | **[Docking recovery under stale pose and charging feedback](../tasks/swe-m2-software-engineering/nav2-docking-recovery/README.md)** · Nav2, Gazebo | Coordinate rear docking, visual tracking, obstacle stops, retries, and independent charge confirmation. Run a closed-loop plant and score contact, clearance, timing, and restart recovery. | [Nav2 docking tutorial](https://docs.nav2.org/jazzy/tutorials/general_tutorials/using_docking/) · [Docking implementation](https://github.com/ros-navigation/navigation2/tree/main/nav2_docking) |
| 6 | **[Controller chain fault recovery](../tasks/swe-m2-software-engineering/ros2-control-recovery/README.md)** · ros2_control | Reconcile a partly failed hardware switch with its commanded mode, preserve independent controllers, and safely restore an affected chain from measured state. Score actual interface ownership and command traces under duplicates and delayed replies. | [RRBot chaining demo](https://control.ros.org/jazzy/doc/ros2_control_demos/example_12/doc/userdoc.html) · [Real hardware fault report](https://github.com/ros-controls/ros2_control/issues/3620) |
| 7 | **[Episode integrity and repair](../tasks/swe-m2-software-engineering/lerobot-dataset-repair/README.md)** · LeRobot | Detect cross-episode actions, camera timestamp drift, and incomplete writes across Parquet records and videos. Produce an auditable repaired dataset, quarantine ambiguous cases, and check that downstream readers recover the intended frames and actions. | [Community v3 dataset](https://huggingface.co/datasets/lerobot/community_dataset_v3) · [Episode-offset report](https://github.com/huggingface/lerobot/issues/4976) |
| 8 | **[Stateful replay and branching](../tasks/swe-m2-software-engineering/mujoco-branch-replay/README.md)** · MuJoCo | Freeze the model and restore complete simulation state while branching an interrupted, contact-rich rollout. Score native simulator parity, state isolation, and the behavior of counterfactual controls after restart. | [MuJoCo reproducibility contract](https://mujoco.readthedocs.io/en/3.3.7/computation/index.html) · [Menagerie models](https://github.com/google-deepmind/mujoco_menagerie) |
| 9 | **[Online map promotion and rollback](../tasks/swe-m2-software-engineering/versioned-mapping/README.md)** · Nav2, SLAM Toolbox | Register revisits, distinguish occlusion from occupancy change, and promote a map after closed-loop canary runs. Score surveyed pose accuracy, changed cells, successful routes, and consistent readers across rollback. | [Nav2 route-tool mapping workflow](https://docs.nav2.org/rolling/tutorials/general_tutorials/route_server_tools/navigation2_route_tool/navigation2_route_tool/) · [Hannover recording](https://doi.org/10.25835/gkytjesg) |
| 10 | **[Sensor-fault recovery in flight simulation](../tasks/swe-m2-software-engineering/px4-estimator-recovery/README.md)** · PX4 | Reproduce an estimator reset or dropout from logs and qualify a recovery policy in software-in-the-loop. Score simulator pose error, recovery time, and completion on healthy and faulted missions. | [PX4 simulation](https://docs.px4.io/main/en/simulation/) · [Altitude-reset report](https://github.com/PX4/PX4-Autopilot/issues/28263) |
| 11 | **[Contact dynamics and wrench calibration](../tasks/swe-m2-software-engineering/contact-wrench-calibration/README.md)** · Drake, Pinocchio | Reconcile force frames, identify contact parameters from pushes, and qualify model predictions under held-out contacts. Check the Jacobian with finite differences and compare predicted object motion with recorded poses. | [Drake tutorials](https://drake.mit.edu/tutorials/index.html) · [Contact Jacobian discussion](https://github.com/stack-of-tasks/pinocchio/discussions/2201) · [MIT Push data](https://mcube.mit.edu/push-dataset/) |
| 12 | **[Multi-bag replay conformance](../tasks/swe-m2-software-engineering/multibag-replay-conformance/README.md)** · ROS 2, rosbag2 | Replay asynchronous sensor logs with a shared clock and valid topic QoS. Handle seeks and timestamp resets without mixing epochs, and preserve calibration messages for late subscribers. Score message traces and downstream pose checks. | [rosbag2 replay documentation](https://github.com/ros2/rosbag2) · [ROS replay discussion](https://discourse.openrobotics.org/t/fast-accurate-robust-replay-in-ros2/30406) |
| 13 | **[Visual-inertial dataset qualification](../tasks/swe-m2-software-engineering/visual-inertial-qualification/README.md)** · ORB-SLAM3 | Recover a stereo/IMU calibration and timing fault, identify unrecoverable segments, and reproduce localization metrics in the calibrated coordinate frame. Grade against TUM VI motion capture where available. | [ORB-SLAM3 examples](https://github.com/UZ-SLAMLab/ORB_SLAM3#5-euroc-examples) · [Calibration user report](https://github.com/UZ-SLAMLab/ORB_SLAM3/issues/894) · [TUM VI dataset](https://cvg.cit.tum.de/data/datasets/visual-inertial-dataset) |
| 14 | **[Portable headless simulation regression runner](../tasks/swe-m2-software-engineering/gazebo-regression-runner/README.md)** · Gazebo, ROS 2 | Validate sensor and transform wiring in a world, replay seeded obstacle events, and detect simulator-time resets or silent topic loss. Score observable trajectories and topic delivery from a real headless run. | [Gazebo simulation and integration guides](https://gazebosim.org/docs/latest/) · [Gazebo Fuel](https://gazebosim.org/docs/latest/fuel/) |
| 15 | **[Reproducible policy rollout evaluation](../tasks/swe-m2-software-engineering/robomimic-rollout-qualification/README.md)** · robomimic | Reconstruct a policy's observations and controller state from demonstration files, replay from paired initializations, and report repeatable outcome and failure diagnostics. | [Paired successful and unsuccessful demonstrations](https://robomimic.github.io/docs/datasets/robomimic_v0.1.html#paired) · [robomimic community](https://github.com/ARISE-Initiative/robomimic/issues) |
| 16 | **[Constrained ground navigation qualification](../tasks/swe-m2-software-engineering/barn-navigation-qualification/README.md)** · Nav2, BARN | Configure and evaluate a controller across unfamiliar layouts and classify failures from traversals. Use held-out worlds and score real route completion, clearance, and duration. | [BARN worlds and occupancy maps](https://www.cs.utexas.edu/~xiao/BARN/BARN.html) · [Nav2 issues](https://github.com/ros-navigation/navigation2/issues) |

The first implementation batch covers cross-simulator policy deployment,
fixed-lag fusion, docking recovery, controller chain fault recovery, LeRobot
episode repair, and MuJoCo stateful replay. The six tasks cover policy
deployment, estimation, navigation, control, robot learning data, and physics
simulation. The [moving-workcell pilot](https://www.oddish.app/experiments/8ede1e8f)
already exercises a smaller planar version of the manipulation problem. Its
result applies to that version.

For each selected task, use public reports to justify the workflow, a pinned
asset or reproducible fixture to supply the inputs, and an independent
execution check to decide success. Dataset rights are assessed per asset when
assembling a bundle.

## Evaluation state on 2026-11-24

GPT‑6.2 Sol xhigh scored 1.0 on the planar workcell's final checkpoint
and 0.928571 on its third checkpoint. The static coordinated detour
was its sole miss. [Workcell experiment](https://www.oddish.app/experiments/8ede1e8f)

The six implemented ecosystem tasks passed local reference and no-op
controls and Oddish preflight. Oddish accepted one reference, one no-op
and one GPT‑6.2 Sol xhigh attempt per task into a single experiment.
[Ecosystem batch](https://www.oddish.app/experiments/439b651d)

## What the first batch revealed

GPT‑6.2 Sol xhigh scored 1.0 on fixed-lag fusion, docking, policy
deployment, and controller recovery. LeRobot recorded 0.90 because an
orphan Parquet fixture omitted required columns. MuJoCo replay recorded
0.00 because trace requests included a field reserved for resume and
the trace result gated every branch check. The original GPT artifacts
pass both corrected final checks locally. The two hosted scores
remain part of the original experiment record.
[Original Oddish batch](https://www.oddish.app/experiments/439b651d)

| Revised task | New engineering requirement |
| --- | --- |
| Policy sim-to-sim bridge | Infer joint and actuator mappings, offsets, signs and clock alignment from motion logs. Qualify the fitted mapping on held-out captures and use it to control physically different MuJoCo plants. |
| Fixed-lag fusion | Commission nonlinear UWB ranging with unknown anchor biases, sensor calibration and receiver permutations across reboots. Freeze the calibration for held-out trajectory recovery and flag unidentifiable fits. |
| Nav2 docking recovery | Compute an obstacle-aware staging maneuver from larger position and heading errors, then execute the approach, re-acquisition and charging recovery in the closed loop. |
| Controller-chain recovery | Preserve protected service while moving between controller configurations. Work around hardware outages and switch authorizations, and attain the best reachable end configuration. |
| LeRobot dataset repair | Recover camera clocks with outliers and dropped frames. Resolve overlapping cross-camera episode assignments and publish only clips whose assignment survives the ambiguity. |
| MuJoCo replay | Migrate integration state by name across recompiled model layouts and compatible parameter edits. Carry the full checkpoint into a native continuation and reject incompatible coordinate contracts. |

The revised versions were submitted together on 2026-11-24. Oddish lists 18 trials across six version 2 task releases, with one GPT‑6.2 Sol xhigh attempt, a reference and a no-op for each. The references scored 1.0 and no-ops scored 0.0. Docking scored 0.20 and the other five model attempts scored 1.0. [Revised batch](https://www.oddish.app/experiments/afbb773d)

## Full 16-task experiment

Oddish accepted all 16 tasks and their 60 sequential checkpoints into a single
private experiment on 2026-11-24. The trial registry lists one GPT‑6.2 Sol xhigh
attempt, one reference, and one no-op per task for 48 trials total. All 16
references scored 1.0 and all no-ops scored 0.0 locally. Oddish preflight passed
for every bundle. Hosted model trials were queued at submission behind the
control runs. [Full Oddish experiment](https://www.oddish.app/experiments/57208689)

The six revised tasks reuse the exact version 2 bundles from the prior batch.
Fleet recovery and versioned mapping also run as version 2. The other eight
tasks run as version 1. The linked task READMEs describe the data provenance
and execution scope, including the decoded PX4-style logs and the headless
MuJoCo runtime used by the SDF regression task.

### What the full run measured

All 16 GPT‑6.2 Sol xhigh attempts and both controls per task finished. The
hosted references scored 1.0 and the no-ops scored 0.0 on all tasks. Thirteen
model attempts scored 1.0 and three earned partial credit. The named failures
below come from the saved checkpoint reports and trajectory analyses. [Full Oddish experiment](https://www.oddish.app/experiments/57208689)

| Benchmark | Model result | First observed miss and final outcome |
| --- | ---: | --- |
| Nav2 docking recovery | 0.200 | The first four checkpoints scored 1.0. The final supervisor omitted the staging-edge report when entering the charger approach. Both hosted runs scored 0.20. A one-line handoff repair in a local copy of the final artifact raised its score to 1.0. |
| PX4 estimator recovery | 0.905 | The first two checkpoints scored 1.0 and the last scored 0.714. The inertial-bridge case never exercised its recovery branch, and the simulated vehicle left its allowed envelope during permanent navigation loss. The task-level score averaged all three checkpoints. |
| Fleet recovery | 0.957 | The score fell to 0.75 on the blockage checkpoint. The final coordinator violated priority/FIFO ordering in one retained case. All six lift booking and recovery cases passed. |
| Remaining 13 tasks | 1.000 each | Every saved checkpoint scored 1.0. The archived final Multibag artifact confirms subscriber transform qualification as well as indexing and replay. |

### Follow-up experiment

Five tasks received new final checkpoints after review of the completed runs.
The table reports local rechecks of the archived GPT code from the full suite
against the revised verifiers. The follow-up runs give GPT‑6.2 Sol xhigh the
new instructions and one fresh attempt per task. All five local references
scored 1.0 and no-ops scored 0.0. Oddish accepted all five packages and 15 trials.
[Follow-up Oddish experiment](https://www.oddish.app/experiments/9a2d8a0f)

| Benchmark | New engineering requirement | Archived GPT code, new verifier |
| --- | --- | ---: |
| Two-arm handoff | Build a contingent policy that completes with safe continuous motion for every possible scanner reading and controller start delay. | 0.200 |
| Fleet recovery | Optimize bookings that hold a lift, vestibule and exit together and recover authority from independent, possibly conflicting receipts. | 0.191 |
| Fixed-lag fusion | Maintain a live nonlinear SE(2) estimate, isolate faulty radios, and exclude ambiguous evidence while preserving the retired prior across revision and restart. | 0.300 |
| Multi-bag replay | Reconstruct causal incidents from overlapping native recordings and qualify transforms across uncertain clocks and producer reboots. | 0.282 |
| PX4 estimator recovery | Qualify redundant estimator sources, recover on standby measurements and hold the flight envelope during a high-speed blackout. | 0.143 |

The docking diagnosis prompted a separate sixth revision. It requires
generating a curvature-limited staging graph from a survey and proving it
works with either aisle held. The exact new verifier scored the one-line
repaired archive at 0.20 and the full new reference at 1.0. Oddish accepted
the new docking task with the same three trial types. [Docking follow-up](https://www.oddish.app/experiments/13686144)

Two additional revisions test closed-loop control. The policy bridge now
identifies actuator delays and coupling from native MuJoCo captures, then
tracks a frozen policy under sustained load on independently simulated rigs.
The ros2_control task now keeps a loaded joint tracking through asynchronous
drive handover, a device restart, and a brief loss of write authority. Both
revised references scored 1.0 locally and both no-ops scored 0.0. The archived
GPT implementations each scored 0.20 against the new final verifiers.
[Closed-loop follow-up](https://www.oddish.app/experiments/20ade25d)

### Fresh GPT‑6.2 Sol xhigh results

| Task | New hosted score | Where the solution still failed |
| --- | ---: | --- |
| Multi-bag replay v3 | 0.200000 | The service rejected the reply destination before committing the poll. The three dependent snapshot flags failed. Removing the early check in a local copy raised the score to 1.0. |
| Fixed-lag fusion v5 | 0.306667 | Both late-loop surveys recovered position and replayed receipts. Their terminal cross-covariances differed from batch by 23.4% and 53.0%, against an 18% limit. The bounded 720-frame mission passed. |
| ros2_control recovery v4 | 0.404444 | The driver inhibited effort and reported a retired boot. The verifier stopped before the recovery cases. Preserving the newest generation and loading the installed ament Python package yielded 1.0 in a local replay. |
| Two-arm handoff v3 | 0.408000 | Open-loop raised transfer fell 0.025 mm short of clearance. The two live recovery missions repeatedly moved without handing over the payload, including with the verifier's command-count cap lifted. |
| Fleet recovery v5 | 0.466324 | Both guarded cases stopped on a one-unit floating-point discrepancy at the simulated endpoint. With the endpoint emitted exactly, the unchanged artifact passed all three native cases and scored 0.999657 in full local replay. |
| Fixed-lag fusion v4 | 0.466667 | Both visual retraction surveys diverged. At frame 22, they differed from independent batch by 0.352 and 0.556 m. A local replay with Huber pixel factors recovered both. |
| PX4 estimator recovery v3 | 0.660635 | All seven calibrations passed. Both landing commitments arrived before horizontal braking met the motion limit, and eight retained estimator-supervisor cases failed. |
| LeRobot v4 | 0.840000 | Four raw-journal cases passed. The candidate rejected the mixed shard before replay because two episodes reused an event ID. Scoping IDs per episode yielded 1.0 on the same verifier. |
| PX4 estimator recovery v5 | 0.879771 | Both moving touchdowns and the permanent-loss abort passed. Three retained fixed-pad descents began before measured horizontal braking, leaving checkpoint seven at 0.398857. |
| Two-arm handoff v2 | 0.895726 | After braking, the candidate rejected measured state on exact equality despite the declared tolerance. In the other missed case, it reported earliest physical time where the verifier expected dispatch time. Both scanner-dependent routes passed. |
| PX4 estimator recovery v4 | 0.951841 | All four degraded-aiding pad landings passed. One permanent-loss flight and eight earlier redundant-source checks failed. |
| PX4 estimator recovery v2 | 0.971429 | The retained permanent-loss mission left the flight envelope. All nine new redundant-estimator missions passed. |
| ros2_control recovery v5 | 0.976482 | Both native process-restart missions passed with zero retired effort writes. The retained protected-servo and maintenance checks accounted for the loss. |
| Fixed-lag fusion v3 | 0.980000 | A retained calibration case failed to share a receiver binding across drives. All eight live nonlinear tracking and integrity missions passed. |
| Fleet recovery v3 | 0.991429 | The retained priority and FIFO case failed. Both the original lift cases and all corridor-booking cases passed. |
| Fleet recovery v4 | 0.998286 | All eight energy-constrained network cases passed. The retained priority and FIFO case failed again. |
| Fleet recovery v6 | 0.999931 | All five native negotiation cases passed, including joint replanning around a committed carrier and blocking a missed departure. |
| Multi-bag replay v2 | 1.000000 | All four checkpoints passed, including mixed-storage causal incident reconstruction and downstream transform lookups. |
| Multi-bag replay v4 | 1.000000 | All six checkpoints passed, including delivery of original CDR to native Jazzy subscribers, late-join history, and receipt recovery after a killed worker. |
| LeRobot v3 | 1.000000 | All five checkpoints passed, including delayed and ramped writes, indistinguishable operator and policy commands, and inconsistent readback. |
| Nav2 docking v3 | 1.000000 | All six checkpoints passed. The fresh code generated and drove the required curvature-limited routes from the floor survey. |
| Nav2 docking v4 | 1.000000 | Checkpoint five scored 0.20 after a missing stationary edge field and both later checkpoints scored 1.0. Relaxing the field at the measured handoff also raised the unchanged stage-five archive to 1.0. |
| ros2_control recovery v3 | 1.000000 | All five checkpoints passed. The three loaded-joint missions stayed below 0.011 rad tracking RMS, with at most seven ticks between accepted writes. |
| Policy bridge v3 | 1.000000 | All six checkpoints and 34 final checks passed. Tracking RMS was 0.049–0.066 rad across the five native load and recovery missions. |
| Policy bridge v4 | 1.000000 | All seven checkpoints and 37 final checks passed. GPT completed all three free-base Go2 missions and finished each below 0.015 m/s. |
| Policy bridge v5 | 1.000000 | All 40 checks passed, including live aisle detours, stale map fencing, and worker restart during map loss. |
| Visual-Inertial v2 | 1.000000 | All four checkpoints passed. GPT recovered camera clocks, rolling-shutter readout and mounts, preserved subpixel holdout accuracy, and abstained for the ambiguous camera. |
| MuJoCo replay v3 | 1.000000 | All five checkpoints passed, including contact-rich state and warm-acceleration migration between free-joint and six-scalar coordinate representations. |

All twenty-eight follow-up trials had successful reference and no-op controls.
Six task families have a frozen score below 0.5 when the original Nav2
result is included. Nav2, Multi-bag, ros2_control, and Open-RMF had
sensitivity to narrow contract or verifier details. Dual-Arm failed two
native transfers even after the diagnostic removed a command-count cap.
Fixed-Lag v4 improved with standard robust weighting. Fixed-Lag v5
preserved accurate poses while accumulating errors in cross-covariance
after marginalization.
[Five-task follow-up](https://www.oddish.app/experiments/9a2d8a0f) ·
[Docking follow-up](https://www.oddish.app/experiments/13686144) ·
[Original sixteen-task evaluation](https://www.oddish.app/experiments/57208689) ·
[Sensing and replay follow-up](https://www.oddish.app/experiments/3d3f9dc5) ·
[Native lifecycle follow-up](https://www.oddish.app/experiments/e2201944) ·
[Closed-loop follow-up](https://www.oddish.app/experiments/20ade25d) ·
[Native Dual-Arm](https://www.oddish.app/experiments/1c1d7b8b) ·
[Native Fixed-Lag](https://www.oddish.app/experiments/46f3595b) ·
[Native Multi-bag](https://www.oddish.app/experiments/16ebd21c) ·
[Native Open-RMF](https://www.oddish.app/experiments/edcef210)

The solved Multi-bag and PX4 tasks led to two more revisions.
Multi-bag now serves immutable recording generations across recorder splits
and lost receipts, with bounded-memory access to a native 272 MiB recording.
PX4 now commissions asynchronous IMUs and fuses delayed visual aiding in a
native rigid-body plant. Two blackout missions require real controlled
touchdown. The local references scored 1.0 and no-ops scored 0.0.
[Sensing and replay follow-up](https://www.oddish.app/experiments/3d3f9dc5)

Fleet recovery now assigns unallocated jobs, plans routes from the facility
graph, and schedules scarce charging power with battery reserves and
worst-case corridor clearance. The reference passed all eight new network
cases and the no-op scored 0.0. The archived v3 implementation scored
0.198286 on the exact new verifier. [Fleet network follow-up](https://www.oddish.app/experiments/3a1a3784)

The sixth ros2_control checkpoint loads a generation-fenced C++ hardware
plugin under the actual ROS 2 Jazzy Controller Manager. It measures native
position and effort claims after device reboot and tracks a second drive
throughout. The hosted reference and no-op scored 1.0 and 0.0. Omitting
the recovery node from the working driver scored 0.468. [Native lifecycle follow-up](https://www.oddish.app/experiments/e2201944)

The seven-checkpoint Dual-Arm revision uses two simulated UR5e arms with
native actuators and physical payload custody. It commissions both tools,
plans from task-space goals, and recovers after a moving fixture invalidates
an issued transfer. The local reference passed all 35 checks. Calibration
and planning without live dispatch scored 0.45. [Native Dual-Arm follow-up](https://www.oddish.app/experiments/1c1d7b8b)

Policy Bridge now deploys a released Go2 actor in a free-base MuJoCo
plant. It qualifies actual course progress, loaded slip, contact loss
across restart, and lease expiry followed by a changed heading. The local
reference passed all 37 checks. Index-based motor binding, wrong history
layout and ignoring loaded slip each failed all three new missions.
[Free-base policy follow-up](https://www.oddish.app/experiments/ba541e83)

Fixed-Lag Fusion now runs a 3D visual graph with delayed observations from
two camera mount calibrations, active factor replacements, and retirement
of old poses and landmarks. The local reference passed all three surveys,
and the verifier independently checked the complete pose covariance against
an all-history batch fit. Reusing one camera calibration failed all three
missions. [Native GTSAM follow-up](https://www.oddish.app/experiments/46f3595b)

Multi-bag and PX4 v4 were submitted together. The replay benchmark now
uses native ROS 2 DDS and kills a worker after independently observing
acceptance of a request. The flight benchmark now requires physical
positioning and touchdown on a surveyed pad with optical flow and range
after loss of absolute position. Their local references passed all 40
and 34 checks. The archived v3 model packages scored 0.20 and 0.132127
on the new verifiers. [Native sensing and transport follow-up](https://www.oddish.app/experiments/16ebd21c)

The hosted controls for the six latest native revisions all passed. Each
reference scored 1.0 and each no-op scored 0.0. The six fresh GPT attempts
started after those controls qualified.

Fleet v5 now uses the actual Open-RMF traffic library. Its native missions
recover after a stale schedule mirror, replay a receipt after measured
progress disagrees, and take a useful bypass while the guarded corridor is
occupied. The local reference scored 1.0 and retained at least 0.51 m of
physical clearance. Releasing on vendor waypoint counts failed both
guarded crossings. [Native Open-RMF follow-up](https://www.oddish.app/experiments/edcef210)

Oddish accepted three more native revisions together. Nav2 v4 requires
electrical charge confirmation on the upstream Jazzy docking server, then
recovery from an open circuit or a worker restart. Go2 v5 requires rolling
route generation, measured clearance, and a physical hold after map
expiry. ros2_control v5 independently restarts the native manager and the
recovery client, then validates drive restoration while a sibling joint
keeps moving. All three exact local references scored 1.0 and no-ops 0.0.
The validation batch uses one fresh GPT‑6.2 Sol xhigh trial per task.
[Native navigation and restart evaluation](https://www.oddish.app/experiments/8bb6b62a)

The next three-task batch tests different reconstruction problems.
Fixed-Lag v5 accepts loop closures after keyframes leave the live window
and maintains their joint covariance through a restart. LeRobot v3
reconstructs actual accepted SO‑101 writes from asynchronous rollout
records and sparse encoder evidence. PX4 v5 estimates an independently
moving landing cart, recovers from a marker blackout, and aborts after
permanent loss. The three exact local references scored 1.0 and no-ops
scored 0.0. The prior LeRobot candidate, the Huber-corrected Fixed-Lag
candidate, and the prior PX4 reference each scored 0.20 on their new
final verifiers. [Delayed mapping, actions, and landing evaluation](https://www.oddish.app/experiments/1faffdf4)

The 12 hosted controls across these two three-task batches completed
with all references at 1.0 and all no-ops at 0.0. Six fresh GPT trials
started after qualification.

The third three-task batch adds Visual-Inertial v2 for raw rolling-shutter
timing and mount calibration, MuJoCo v3 for contact-state migration
between different joint-coordinate representations, and Open-RMF v6 for
jointly renegotiating two couriers around a committed carrier. The exact
local references scored 1.0 and no-ops scored 0.0. The prior Visual-Inertial
and MuJoCo references scored 0.20. The corrected Fleet v5 archive scored
0.199931 against the eight-checkpoint verifier. Hosted references each
scored 1.0 and no-ops scored 0.0. Nine fresh GPT trials started across
the three batches.
[Calibration, simulation, and traffic evaluation](https://www.oddish.app/experiments/9abc4012)

The fourth batch advances three earlier successes. Go2 v6 builds
navigation geometry and relocalizes from raw native range scans after an
odometry epoch reset. LeRobot v4 reconstructs action ownership directly
from overlapping journals under clock and device restarts. ros2_control
v6 keeps a loaded, coupled lift moving through a partial feedback outage
and an actual native controller-chain switch. The exact local references
scored 1.0 and no-ops scored 0.0, locally and on Oddish. All three
predecessor packages scored 0.20. The hold-only lift controller also
scored 0.20. [Onboard reconstruction and coupled control evaluation](https://www.oddish.app/experiments/dcfc86bc)

PX4 v6 extends the moving-cart problem to raw onboard aiding without
supplied absolute ownship position. The reference completed three
touchdowns, including separate bearing and ground-flow outages, and
aborted safely on permanent bearing loss while range remained live.
The local and hosted controls scored 1.0 and 0.0. The prior reference
and a variant without ground-velocity correction each scored 0.20.
[PX4 relative-aiding evaluation](https://www.oddish.app/experiments/dd17ac79)

The inertial and traffic batch advances Visual-Inertial v3 to joint
motion, bias-epoch, rolling-shutter and mount estimation, with an
independent IMU-only continuation. Open-RMF v7 requires timely,
nonanticipative traffic plans before separate carrier and lift
outcomes are known. Exact local references scored 1.0 and no-ops
scored 0.0. The prior references each scored 0.20.
[Inertial calibration and contingent traffic evaluation](https://www.oddish.app/experiments/64c9c219)
