# Next robotics benchmark round

The next round starts with seven new software workflows. The priority is
engineering difficulty under an independent verifier, with the prior objective
of fresh GPT-6.2 Sol xhigh scores below 0.5. The ordering is a design judgment
based on the number of coupled decisions and the cost of making a useful
implementation. None of these proposals has a model score.

Two proposals have checkpoint briefs. [Flexible harness routing](../tasks/static/robotics/cable-harness-routing/README.md)
has the largest gap from the earlier tasks. [Interrupted Scan-N-Plan coating](../tasks/static/robotics/scan-n-plan-coating/README.md)
has the most direct path to a useful independent verifier.

## Candidates in expected difficulty order

| Rank | Candidate and staged work | Independent evidence | Initial feasibility and prior overlap |
| ---: | --- | --- | --- |
| 1 | **Flexible harness routing and recovery.** Thread known cable through clips, qualify replacement batches using force and partial depth, then recover a partly assembled board after a changed fixture and lost receipt. [CRAFT](https://www.research.autodesk.com/publications/craft-long-horizon-cable-routing-algorithm-low-friction-caging-gripper/) | Correct material intervals and order at the clips, seated connector after a pull, continuous force and bend limits, no duplicate physical move. | The articulated arm seated two opposite-entry clips and preserved both during the pull. Keyed docking with the cable attached still needs qualification. Distributed cable geometry and material identity distinguish the task from rigid-payload handoff. |
| 2 | **Interrupted Scan-N-Plan coating.** Register partial scans, compute a coordinated arm and rotary positioner path, and finish a coating pass after a fixture re-index or tool inhibit. [ROS-Industrial Scan-N-Plan](https://rosindustrial.org/scan-n-plan) · [ROS 2 workshop](https://ros-industrial-consortium.github.io/scan_n_plan_workshop/architecture.html) | Accumulate applied dose on an independent surface from measured pose and flow. Measure undercoat, overcoat, keep-out dose, clearance and recovery after partial application. | The exact four-checkpoint package scored 1.0 on the local reference and 0.5 on the offline-only control. Hosted difficulty remains unmeasured. The applied material, including portions deposited before an interruption, determines completion. |
| 3 | **Legged odometry on moving supports.** Estimate support-relative and inertial velocity separately as a quadruped crosses onto a translating or pivoting floor. Detect single-foot slip, represent uncertainty when support motion is ambiguous, and recover when tracking returns. [Moving-support experiments](https://arxiv.org/abs/2403.16252) · [ETH GrandTour](https://grandtour.leggedrobotics.com/dataset) | Native support and body state gives both velocity targets. A matched-observation pair checks honest uncertainty. A coverage floor on observable intervals prevents blanket abstention. | Authored CPU traces can provide motion truth. GrandTour is a source for realistic sensor interfaces and a possible static-ground sample. The moving-support measurement model is distinct from PX4 navigation source recovery and fixed-lag pose replay. |
| 4 | **Haptic teleoperation under variable delay.** Build a two-way teleoperator for simulated contact inspection, then preserve stable force feedback through delay, loss and reconnection. [Time-domain passivity under time-varying delay](https://pure.kaist.ac.kr/en/publications/bilateral-control-with-time-domain-passivity-approach-under-time-/) · [Hannaford and Ryu](https://cim.mcgill.ca/~hayward/Teach/papers/Part-II/Hannaford-Ryu-02.pdf) | From independent effort and velocity measurements, integrate energy exchanged at both ports. Require low-energy contact, completion and usable force reflection across several delay profiles. Freezing or permanently damping out the interaction fails the positive cases. | A deterministic scripted operator and a CPU contact plant are plausible. Establish a common sign convention, energy quadrature, model assumptions and achievable transparency before setting limits. The coupled bilateral dynamics differ from controller ownership handoff. |
| 5 | **ROS 2 deadline diagnosis and remediation.** Join native Jazzy CTF traces through RMW boundaries, callback fan-in and actuator receipt. Attribute deadline misses, then choose a deployment change under fixed CPU and queue limits. [ROS 2 tracing](https://github.com/ros2/ros2_tracing#dual-session-tracing) · [Message-flow experiments](https://github.com/christophebedard/ros2-message-flow-analysis) · [Jazzy RMW contract](https://github.com/ros2/rmw/blob/jazzy/rmw/include/rmw/types.h) | Score causal attribution against injected faults and independent sample receipts, including an ambiguity case with missing IDs. Apply the configuration and measure the next run against the original source denominator, resource limits and unrelated branch liveness. | Generate licensed fixtures locally. Repeat paired deployments to calibrate host jitter. The earlier multibag and Gazebo runners check replay and regressions. Here a diagnosis must support a verified fix. |
| 6 | **Budgeted contact-policy commissioning.** Adapt a single-arm insertion policy from a few demonstrations and limited interventions. Deploy the same frozen policy on unseen fixture alignments, friction and obstructions. [REASSEMBLE](https://tuwien-asl.github.io/REASSEMBLE_page/) · [HIL-SERL](https://hil-serl.github.io/) | Measure electrical-equivalent or mechanical seating, stable engagement after release, force impulse, safe retreat and interaction budget on held-out geometry. | A CPU residual policy over declared impedance skills avoids large training jobs. Establish repeatable contact and independent blocked/attainable cases. Existing dataset repair and rollout qualification do not test bounded adaptation to a new fixture. |
| 7 | **Cross-vendor mission and inventory custody.** Translate warehouse-assigned jobs to native VDA 5050 messages, reconcile lost mission receipts, and recover a cancellation while a pick is in progress. [VDA 5050 v3](https://github.com/VDA5050/VDA5050/releases/tag/3.0.0) · [Isaac Mission Dispatch](https://github.com/nvidia-isaac/isaac_mission_dispatch) | A broker observer checks order and released horizon semantics. An independent station ledger measures physical transfers, total inventory and continued peer progress after restart. | Mosquitto and two CPU robot simulators are sufficient for a first pilot. Fleet Recovery already handles route conflicts and locks. Keep route choice outside this task and test interoperation and physical custody instead. |

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
