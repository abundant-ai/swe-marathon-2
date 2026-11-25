# Next robotics benchmark round

The next round starts with seven new software workflows. The priority is
engineering difficulty under an independent verifier, with the prior objective
of fresh GPT-6.2 Sol xhigh scores below 0.5. The ordering is a design judgment
based on the number of coupled decisions and the cost of making a useful
implementation. Scan-N-Plan has begun same-version screening.

Two proposals have checkpoint briefs. [Flexible harness routing](../tasks/static/robotics/cable-harness-routing/README.md)
has the largest gap from the earlier tasks. [Interrupted Scan-N-Plan coating](../tasks/static/robotics/scan-n-plan-coating/README.md)
has the most direct path to a useful independent verifier.

## Candidates in expected difficulty order

| Rank | Candidate and staged work | Independent evidence | Initial feasibility and prior overlap |
| ---: | --- | --- | --- |
| 1 | **Flexible harness routing and recovery.** Thread known cable through clips, qualify replacement batches using force and partial depth, then recover a partly assembled board after a changed fixture and lost receipt. [CRAFT](https://www.research.autodesk.com/publications/craft-long-horizon-cable-routing-algorithm-low-friction-caging-gripper/) | Correct material intervals and order at the clips, seated connector after a pull, continuous force and bend limits, no duplicate physical move. | The articulated arm seated two opposite-entry clips and preserved both during the pull. Keyed docking with the cable attached still needs qualification. Distributed cable geometry and material identity distinguish the task from rigid-payload handoff. |
| 2 | **Interrupted Scan-N-Plan coating.** Register partial scans, compute a coordinated arm and rotary positioner path, and finish a coating pass after a fixture re-index or tool inhibit. [ROS-Industrial Scan-N-Plan](https://rosindustrial.org/scan-n-plan) · [ROS 2 workshop](https://ros-industrial-consortium.github.io/scan_n_plan_workshop/architecture.html) | Accumulate applied dose on an independent surface from measured pose and flow. Measure undercoat, overcoat, keep-out dose, clearance and recovery after partial application. | GPT-6.2 Sol xhigh reached 0.50 on version 5. Version 6 adds a remount followed by a second feed loss, with the prior primer and finish measured separately. Its reference and no-op scored 1.0 and 0.0. The first v6 GPT scored 0.25 and a same-version confirmation is submitted. [First v6 trial](https://www.oddish.app/experiments/013d69bf) · [Confirmation](https://www.oddish.app/experiments/8a82eb80) |
| 3 | **Legged odometry on moving supports.** Estimate support-relative and inertial velocity separately as a quadruped crosses onto a translating or pivoting floor. Detect single-foot slip, represent uncertainty when support motion is ambiguous, and recover when tracking returns. [Moving-support experiments](https://arxiv.org/abs/2403.16252) · [ETH GrandTour](https://grandtour.leggedrobotics.com/dataset) | Native support and body state gives both velocity targets. A matched-observation pair checks honest uncertainty. A coverage floor on observable intervals prevents blanket abstention. | Authored CPU traces can provide motion truth. GrandTour is a source for realistic sensor interfaces and a possible static-ground sample. The moving-support measurement model is distinct from PX4 navigation source recovery and fixed-lag pose replay. |
| 4 | **Haptic teleoperation under variable delay.** Build a two-way teleoperator for simulated contact inspection, then preserve stable force feedback through delay, loss and reconnection. [Time-domain passivity under time-varying delay](https://pure.kaist.ac.kr/en/publications/bilateral-control-with-time-domain-passivity-approach-under-time-/) · [Hannaford and Ryu](https://cim.mcgill.ca/~hayward/Teach/papers/Part-II/Hannaford-Ryu-02.pdf) | From independent effort and velocity measurements, integrate energy exchanged at both ports. Require low-energy contact, completion and usable force reflection across several delay profiles. Freezing or permanently damping out the interaction fails the positive cases. | A deterministic scripted operator and a CPU contact plant are plausible. Establish a common sign convention, energy quadrature, model assumptions and achievable transparency before setting limits. The coupled bilateral dynamics differ from controller ownership handoff. |
| 5 | **ROS 2 deadline diagnosis and remediation.** Join native Jazzy CTF traces through RMW boundaries, callback fan-in and actuator receipt. Attribute deadline misses, then choose a deployment change under fixed CPU and queue limits. [ROS 2 tracing](https://github.com/ros2/ros2_tracing#dual-session-tracing) · [Message-flow experiments](https://github.com/christophebedard/ros2-message-flow-analysis) · [Jazzy RMW contract](https://github.com/ros2/rmw/blob/jazzy/rmw/include/rmw/types.h) | Score causal attribution against injected faults and independent sample receipts, including an ambiguity case with missing IDs. Apply the configuration and measure the next run against the original source denominator, resource limits and unrelated branch liveness. | Generate licensed fixtures locally. Repeat paired deployments to calibrate host jitter. The earlier multibag and Gazebo runners check replay and regressions. Here a diagnosis must support a verified fix. |
| 6 | **Budgeted contact-policy commissioning.** Adapt a single-arm insertion policy from a few demonstrations and limited interventions. Deploy the same frozen policy on unseen fixture alignments, friction and obstructions. [REASSEMBLE](https://tuwien-asl.github.io/REASSEMBLE_page/) · [HIL-SERL](https://hil-serl.github.io/) | Measure electrical-equivalent or mechanical seating, stable engagement after release, force impulse, safe retreat and interaction budget on held-out geometry. | A CPU residual policy over declared impedance skills avoids large training jobs. Establish repeatable contact and independent blocked/attainable cases. Existing dataset repair and rollout qualification do not test bounded adaptation to a new fixture. |
| 7 | **Cross-vendor mission and inventory custody.** Translate warehouse-assigned jobs to native VDA 5050 messages, reconcile lost mission receipts, and recover a cancellation while a pick is in progress. [VDA 5050 v3](https://github.com/VDA5050/VDA5050/releases/tag/3.0.0) · [Isaac Mission Dispatch](https://github.com/nvidia-isaac/isaac_mission_dispatch) | A broker observer checks order and released horizon semantics. An independent station ledger measures physical transfers, total inventory and continued peer progress after restart. | Mosquitto and two CPU robot simulators are sufficient for a first pilot. Fleet Recovery already handles route conflicts and locks. Keep route choice outside this task and test interoperation and physical custody instead. |

**Robot model transfer under a loaded tool swap** has an additional native
witness. Two equivalent URDF descriptions preserve mapped poses, projected
inertia, and signed jaw forces after a replacement gripper is attached. The
replacement transmits a 5 N pad load as a 4 N master reaction. A two-motor
control matches unloaded geometry and transmits 0 N to the master. Reusing the
previous tool gives a 5 N reaction and 27.54% projected mass error against the
replacement. The draft compiler contract and reproducible witness are in
`tasks/static/robotics/robot-model-transfer/experiment/`. The local release
pilot gave the reused compiler full credit on fresh source gauges. Replaying
the original compiled assets against those sources scored 0.0. The frozen
compiler reference and no-op also scored 1.0 and 0.0 in the hosted verifier.
The first GPT trial had no reward because the trusted probe added a rail
with implicit limits and inertia under legal candidate options that disabled
both defaults. The repaired rig declares both explicitly and preserves the
native loads. Version 2 passed the hosted controls and GPT solved both
native work orders for 1.0. The closed-linkage successor commissions a
single-drive four-bar gripper in open and crossed configurations. Two
different linkages share the same home jaw pose. Their motion, projected
inertia, and drive reaction under applied tool loads distinguish them away
from home. The frozen native reference and a signed, offset coordinate map
both scored 1.0. Stale, affine-mimic, shifted-pivot, and short-stroke controls
each scored 0.0. The applied-force work orders leave external contact untested.
The separate hosted verifier confirmed 1.0 for the reference and 0.0 for
the no-op on the same version before the first GPT trial.
[Version 1 diagnostic](https://www.oddish.app/experiments/ead124af) ·
[Compiler version 2](https://www.oddish.app/experiments/3f47e05c) ·
[Closed-linkage screen](https://www.oddish.app/experiments/5bad927d)

**Moving robot checkpoint transfer** exercises a separate workcell operation.
The application restores a sampled position, velocity and drive state into
a replacement model using its source coordinate map and its new passive
coupling. The exact local reference passed both native work orders. Copying
native vectors, keeping the prior follower, or copying native commands each
scored 0.0. GPT-6.2 Sol xhigh scored 1.0 on version 1, including all six
incompatible-input rejection and custody checks. Version 2 adds filtered
actuator memory that differs from current commands and measures a fresh
native contact impulse after transferring a loaded checkpoint. GPT scored
1.0 on version 2, matching the 0.176915 N·s native contact impulse and passing
both work orders and all eight incompatible-input custody checks. The next
pilot measures joint torque and its first derivative after a coupled tendon
retrofit. The native reference ran a loaded spatial-tendon work order and
a separate moving fixed-tendon work order. Holding only the initial torque
failed both. The development bundle and checks are under
`tasks/static/robotics/robot-model-transfer/experiment/moving-state-differential-pilot-20261125/`.
[Moving checkpoint version 1](https://www.oddish.app/experiments/aefe2af1) ·
[Moving checkpoint version 2](https://www.oddish.app/experiments/1c37e719)

**Articulated reverse docking** is a successor candidate after the Nav2
guarded-arrival screen. GPT-6.2 Sol xhigh scored 0.9998 and passed all 20 new
arrival checks. In the standalone reverse replay, the old commands hit a
rack at 9.31 s once the stopped rig's pose was updated. A fresh plan for the
updated pose and rack retained 50.88 mm of swept clearance against a 45 mm
requirement. A further rack placement makes the terminal pose geometrically
impossible. The draft and native replay evidence are in
`tasks/static/robotics/nav2-docking-recovery/experiment/articulated-fresh-reverse-20261125/`.
[Guarded-arrival score](https://www.oddish.app/experiments/f9317b11)

The standalone articulated-tug package has four positive jobs, including a
mirrored survey and a relocated rig with different axle geometry. Controls
check a physically blocked dock and preservation of the prior output on
malformed input. The separate hosted verifier confirmed 1.0 for the
reference and 0.0 for no-op on the same task version. GPT then scored 1.0.
Version 2 supplies measured initial speed and steering, and requires a
0.20-second stop whenever direction changes. Its three recovery jobs start
near the hitch limit. One begins in reverse and needs to brake, pull forward,
then reverse at zero-speed transitions. The frozen local reference and
no-op scored 1.0 and 0.0. The hosted GPT planner built a C++ library in the
agent environment, then failed to start in the separate verifier because it
lacked that compiler. The raw 0.0 is excluded from the difficulty gate.
Version 3 supplied matching C++17 tools and returned ready plans on the
three recovery jobs. The verifier rejected their steering increments for
roundoff before measuring motion, so the second raw 0.0 is excluded.
Version 4 corrects that comparison and retains the exact zero-speed stop
and dwell requirements. GPT scored 0.765 on v4 under the hosted native
verifier. It completed all three signed-speed recovery jobs and both
negative controls, but reported the solvable survey baseline as blocked.
The next pilot adds a moving warehouse shuttle. A stopped wait cleared the
first crossing by at least 244 mm. At the second crossing the same wait put
the tug in the shuttle's path. Retreating to a refuge, waiting, and retracing
the approach cleared the crossing by about 262 mm. The matched native
replays are under `tasks/static/robotics/articulated-tug-reverse/experiment/moving-shuttle-v5-feasibility-20261125/`.
[Version 1](https://www.oddish.app/experiments/f524f89b) ·
[Version 2](https://www.oddish.app/experiments/d230edc3) ·
[Version 3](https://www.oddish.app/experiments/ccee5d35) ·
[Version 4 screen](https://www.oddish.app/experiments/d41c3d75)

## Qualifying difficulty

- Start with a reference that completes changing physical or operational cases,
  a no-op, and negative controls that isolate specific shortcuts. Verify
  independent evidence before increasing the scenario difficulty.
- Exercise two valid representations or implementations when the public
  contract admits both. In the earlier campaign, correcting incomplete
  commissioning metadata or the valid frame-zero encoding moved archived
  scores substantially. Validate on a fresh package before using a low score
  to select tasks. [Earlier three-model experiment](https://www.oddish.app/orgs/abundant/experiments/4e6cfedb)
- The archived PX4 estimator recovery attempt scored 0.9884 in the hosted
  version and 0.1977 when replayed unchanged against the expanded local
  verifier. A local adapter passed all three new cases while leaving the
  selected source out of motor control. That exposed a gap in the causal
  check. For harness routing, measure earlier clip geometry during the later
  feed and docking moves. A closed switch and a correct final pose can both
  survive a transient material slip. [Earlier three-model experiment](https://www.oddish.app/orgs/abundant/experiments/4e6cfedb)
- Plan for at least five days of substantive engineering across checkpoints,
  then validate the estimate with trials. A useful final mission should drive
  most of the score. Retained behavior, administrative output and safe holds
  still earn partial credit where they establish real product behavior.
- Use matched task digests, reference and no-op controls, and three fresh
  GPT-6.2 Sol xhigh attempts per qualified package. Report the raw attempts
  and verifier evidence. Keep model capability separate from runner errors
  and local replays. Reuse the same frozen packages if comparing other models.
