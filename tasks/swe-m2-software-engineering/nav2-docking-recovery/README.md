# Nav2 docking recovery

Build a rear docking controller for a robot that has reached its charger staging pose. The application acquires the dock through a calibrated rear camera, approaches under a low speed limit, verifies actual charging, and recovers from faults and a controller restart. The runtime is a headless deterministic planar analog written for this task.

## Design dimensions

| Dimension | Evidence and remaining questions |
| --- | --- |
| Novelty | Localization Replay tests timestamp alignment and pose diagnostics on prior runs. This task uses delayed pose evidence to drive a new closed-loop outcome and distinguish contact from charge. Fleet Recovery shares crash persistence and bounded physical authority but delegates chassis motion to robot adapters. Robo-SWE uses historical robotics code changes. RoboBugBench executes historical navigation defects. This task asks for a new controller and operational recovery flow. Comparisons with the remaining SWE-Marathon and other suites are pending. [Robo-SWE](https://arxiv.org/abs/2611.16116) · [RoboBugBench](https://arxiv.org/abs/2610.16369) |
| Verifiability | A separate plant derives camera observations from an independently simulated chassis and calibrated dock. It can check the commanded trajectory, rear guard, physical connector seat, charge evidence, actual retreat and eventual mission outcome. A candidate can use different control laws and still pass. |
| Realism | The official Nova Carter walkthrough separates staging, camera calibration, visual approach, contact and battery feedback. It documents speed limits and retries after detection loss or lack of charging. The pilot retains those operational decisions and injects plausible odometry, obstacle and electrical incidents. The simulated stream is a simplified interface and does not launch Nav2 or operate hardware. [Nav2 docking tutorial](https://docs.nav2.org/jazzy/tutorials/general_tutorials/using_docking/) · [Docking server configuration](https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/core_servers/configuring_docking_server/) |
| Difficulty | Camera and dock extrinsics compose with capture-time pose and odometry epoch. The agent must manage rear tracking, reverse control near the seat, and independent confirmation signals, then preserve all of that through retries and a process crash. This is an hours-scale pilot. It currently has no evidence for the repository's five-day workload target. |
| Initial feasibility | An SE(2) track, bounded position servo, measured retreat and atomic state snapshot run against the documented stream on CPU. The local reference and no-op establish two calibration endpoints for the implemented checks. Hosted feasibility and candidate performance are pending. |

The fixtures, numerical parameters, and controller and plant implementations are authored for this task. No vendor model, map, dataset, image, or source code ships in the bundle. The upstream documentation is linked for the workflow and system names.

## Verification and reward

Each checkpoint runs actual candidate commands against the simulated plant. The private verifier uses numerical integration of the unicycle's constant-twist path, geometric rear clearance, independent contact and current generation, and observed command bounds. It launches the controller as an unprivileged account in a separate verifier environment.

1. Acquire a calibrated assigned tag with rotated sensor and tag frames. Deliver to physical contact through delayed, missing, stale and distracting detections.
2. Retain docking and verify that charge requires fresh battery samples across duplicates, a bouncing contact switch and low current.
3. Pause for an occupied approach or lost odometry, reacquire after an odometry epoch change, and execute a guarded forward retreat after failed charging. Retry successfully or stop at the configured deadline.
4. Kill and restart the real process after it replies, retransmit the same observation, and continue the mission. Check lost approach evidence, interrupted retreat and retry budget exhaustion.

5. Start outside the tag's usable approach, certify and execute a route through a bounded SE(2) graph, then reacquire and charge. Cases include a stroke that turns through a protruding corner, a held aisle, an interrupted curved primitive, a retry after staging, and two no-route regimes.
6. Compile a staging graph from surveyed boxes, a chassis and allowable turn radii. Run the resulting graph with either aisle held and a curved reverse-only approach. Apply the submitted twists through a localization outage, controller restart and charge confirmation.

A mission earns one point only when the complete physical outcome and command-level requirements both pass. The original four checkpoints retain their cumulative diagnostic scores. Checkpoint five scores 0.20 times the fraction of the 11 retained missions that pass plus 0.80 times the fraction of the nine staging missions that pass. The staging component requires at least one successful physical staging-and-charging mission. Checkpoint six retains that outcome for 20% of its final reward and validates surveyed-route compilation for 80%. New credit requires at least one generated graph to produce a complete, physically docked run. A separate geometric verifier checks every reported edge's speed, curvature, endpoint, swept clearance, blocked-zone membership and travel time.

Package the runtime with `python3 -B scripts/package_task.py`. Run `oddish preflight` against the emitted directory. The staged verifier can also run with `python3 -IB steps/<step>/tests/verify.py --stage N --artifact steps/<step>/solution/dock_recovery --output REPORT_DIR` from the bundle.

## Hackability assessment

| Finding | Boundary and evidence | Remaining risk and next validation |
| --- | --- | --- |
| 🟡 YELLOW / MEDIUM | A controller could overfit to a constant simulated trajectory. Cases use different initial positions, camera and dock offsets, sensor delays, and physical or communication faults. The grader applies the actual commands to an independent body and connector. | The fixed set has limited topology and slip diversity. Use additional layouts and held-out timing variants before attributing success to general docking reliability. |
| 🟡 YELLOW / UNASSESSED | Separate verifier environment, restricted launch identity, explicit artifact declaration, and an allowlisted package keep the plant and reward output away from the controller. Tests omit links when copying candidate files. | Local subprocess checks establish protocol behavior. Hosted process isolation, network settings, and artifact permissions still require observed hosted controls. |
| 🟢 GREEN / LOW | Reports that claim docked without physical contact and sufficient battery evidence fail the mission. As the plant applies the submitted velocities, an all-stop controller cannot pass successful docking cases. | Sensor, connector, and motion truth are bounded by the simplified planar plant. The reference is not assessed as a real safety controller. |

The highest assessed concern is medium. Hosted isolation remains unassessed. No LLM judge, live robot credentials, or external account is needed.

## Development log

### 2026-11-24

Implemented four cumulative checkpoints and private closed-loop mission cases. Local oracle and no-op were run through the packaged verifier. Oddish preflight found no packaging issues. Hosted controls, solver difficulty, and Harbor model-based quality review remain pending.

The hardened packaged reference and no-op scored 1.0 and 0.0 locally at the final checkpoint. Oddish accepted version 1 into the six-task batch with both controls and one GPT‑6.2 Sol xhigh attempt. Bundle SHA-256 is `37220ab07fc241dc4b06a692140441dab91e738d8258ff3e3e612808f6f9433b`. [Oddish experiment](https://www.oddish.app/experiments/439b651d)


Hosted version 1 scored 1.0 on each checkpoint with one GPT-6.2 Sol xhigh trial, classified as a legitimate solution. Its reference and no-op were 1.0 and 0.0. Version 1 started inside the charger approach and could hand the relative controller any usable first camera frame. Version 2 adds room geometry and a certified nonholonomic motion graph before that handoff. A valid route may require reversing away from the dock, turning around a corner, waiting on a temporary lane hold, or pausing partway through an arc until the map pose returns. The separate plant integrates submitted commands, verifies dense continuous rectangular sweeps using a travel bound, enforces external hold evidence, and exposes camera data only after staging. Cases include a genuine extra charge attempt after the staging maneuver. No ROS middleware or physical robot is involved. [Version 1 Oddish experiment](https://www.oddish.app/experiments/439b651d)

Stage 5 deadlines are based on taught travel times, real simulated fault duration, approach and charger verification allowance. For example, the detour around the rear charger fixture is 189 ticks, the retained reverse alignment takes around another 60 and confirmation around 11. The positive fixture allows 335 ticks. Impossible fixture outcomes distinguish geometrically obstructed edges from an externally held aisle. The reference uses continuous rectangular clearance certification from a rigid point-motion bound and a directed route search. The verifier independently projects explicit rectangle vertices and replays actual chassis commands. Dynamic aisle holds represent observations from a facility supervisor. They do not claim a moving obstacle simulator or a Nav2 costmap integration.

The new rotation fixture has 0.018 m of clearance at its commanded start, collides by at least 0.025 m partway through the tempting turn, and has a clear alternative that reverses for a wider turn. Drawn labels are private and opaque wire IDs carry no route cues.

The v2 packaged reference passed all 20 final missions and scored 1.0. No-op scored 0.0. The exact version 1 reference passed the 11 retained missions and scored 0.20. Local Oddish preflight, Harbor parsing, and the package test passed. Hosted v2 validation remains pending.

The revised bundle passed local reference and no-op controls at 1.0 and 0.0. Oddish preflight reported no findings. The hosted version 2 batch contains one GPT‑6.2 Sol xhigh trial and both controls. Bundle SHA-256 is `10fb39904ee2a71adc8979ec850d88a2c9b7993970f1e62466f0f7ae8db0aa97`. [Version 2 batch](https://www.oddish.app/experiments/afbb773d)

#### Generate staging routes from a floor survey

Both hosted version 2 GPT‑6.2 Sol xhigh attempts scored 0.20. The archived
candidate produced a stationary command without `stage_edge` at the instant
it handed off to its dock tracker. The local frozen version 2 verifier
reproduced 0.20. Changing one line in an isolated diagnostic copy to emit
the required field raised the local score to 1.0, with all seven positive
staging missions completing. The published score is still 0.20.
[Full trial results](https://www.oddish.app/experiments/57208689)

The sixth checkpoint now asks for geometry and route generation from the
survey. The reference searches a four-heading vehicle lattice through
continuous forward and reverse arcs. It publishes safe routes for each
recoverable closure, alongside the complete swept-intersection mapping that
lets the supervisor rule out active holds. The plant independently checks
this geometry and runs new graphs through physical completion. This is an
authored planar test with an idealized curvature-limited stage drive.
[Nav2 Smac Hybrid-A* planner](https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/planners_plugins/smac/smac_hybrid/configuring_smac_hybrid/)

The revised final reference and no-op scored 1.0 and 0.0. The locally
replayed archived GPT code scored 0.04. The diagnostic copy with the
handoff repair scored 0.20 and passed the retained checkpoints.
[Version 3 trial](https://www.oddish.app/experiments/13686144)

Fresh GPT‑6.2 Sol xhigh scored 1.0 at all six checkpoints. It generated and
executed each curvature-constrained docking route. The reference and no-op
scored 1.0 and 0.0. [Version 3 results](https://www.oddish.app/experiments/13686144)

## Native Jazzy charging qualification

Checkpoint 7 supervises the Ubuntu ROS 2 Jazzy package `ros-jazzy-opennav-docking` at version `1.3.14-1noble.20261109.091645`. The upstream docking server runs unchanged and receives qualified battery messages from the application. The application owns the command relay. A separate low-speed planar integrator observes both the native and applied twists. It produces odometry transforms, mechanical contact, and electrical charging evidence. All geometry, battery traffic, and charger faults are authored fixtures. Finite simulated footprint and timing are part of this model. Claims about a physical robot would require hardware validation. [Jazzy docking tutorial](https://docs.nav2.org/jazzy/tutorials/general_tutorials/using_docking.html) · [Jazzy docking server](https://github.com/ros-navigation/navigation2/blob/jazzy/nav2_docking/opennav_docking/src/docking_server.cpp)

The workflow follows the corrective charging maneuver discussed in Nav2 #5567. A commissioning probe also found that a positive current report aged 29–30 seconds can satisfy the stock plugin's current threshold while the robot is 0.36 m from the charger. Published battery evidence now needs a recent acquisition timestamp, a matching charger boot, independently observed mechanical contact, and sustained positive current. A nearby transform remains available for motion checks. [Nav2 issue #5567](https://github.com/ros-navigation/navigation2/issues/5567) · [Jazzy charging plugin](https://github.com/ros-navigation/navigation2/blob/jazzy/nav2_docking/opennav_docking/src/simple_charging_dock.cpp)

The reference was exercised through real DDS on isolated loopback domains. Two mirrored paths each returned native error 906 at the nominal pose, completed native undock, and seated on the clear side with no obstacle contact. The process-recovery witness detected accepted state while the robot was moving, killed the worker, observed the actuator stop while the old native action still emitted commands, and recovered after canceling that action. The charger rebooted during the interruption. Fresh current from the new boot and replay of the durable terminal receipt completed the mission. A stale-current control falsely reported charging with zero movement. A pose-only control falsely reported charging after approaching an open circuit. The independent plant rejected both controls.

The final reward retains 15% for the earlier checkpoints and assigns 85% to five equally weighted native missions. Native credit requires at least one physically confirmed docking. The stage 7 package includes the original geometry and controller exercises, and the source regression verifies that private fixture code stays outside the candidate image. Local validation uses the packaged reference and an empty application as the no-op.

To run the development example in the candidate image, start the charger in one terminal.

```sh
export ROS_DOMAIN_ID=44
python3 /app/example/native_dock.py --directory /tmp/dock-example
```

Wait for the active status, then start the worker in another terminal.

```sh
export ROS_DOMAIN_ID=44
cd /app
python3 -m dock_recovery guarded-dock --spec /tmp/dock-example/spec.json \
    --state /tmp/dock-example/state --output /tmp/dock-example/report.json
python3 -m dock_recovery dock-receipt --state /tmp/dock-example/state --request-id public-dock
```

The example and independent benchmark use the official Jazzy packages through loopback only. No third-party data or geometry assets are redistributed. Local proof uses the extracted official packages. The container build was unavailable on the authoring host.

The frozen cumulative package scored 1.0 for the reference and 0.0 for the no-op, both locally and on Oddish. Oddish preflight and the maintained package test passed. The packaged public example docked and printed a charged terminal receipt.

Oddish accepted v4 alongside Go2 and ros2_control, with one GPT‑6.2 Sol
xhigh attempt and both controls. [Native docking evaluation](https://www.oddish.app/experiments/8bb6b62a)

Fresh GPT‑6.2 Sol xhigh scored 1.0 at the final checkpoint. Its fifth
checkpoint scored 0.20 and both later checkpoints scored 1.0. Both
mirrored missions handled native error 906, backed out with 102 reverse
commands, and confirmed charging on the alternate rail. The killed-worker
case recovered after a quiet actuator interval and recorded 32 fresh
charge samples. The open circuit produced zero charge samples and a
blocked terminal receipt.

The stage-five dip came from the stationary staging handoff. All seven
positive cases staged the robot and were rejected because the reply
omitted the edge field after arrival. Returning `stage_edge: null`
at that point brought the exact stage-five artifact from 0.20 to 1.0.
The maintained contract accepts an omitted edge on that measured
stationary handoff. The unmodified artifact also scores 1.0 under that
contract, and the new regression check still requires an edge report
before staging.
