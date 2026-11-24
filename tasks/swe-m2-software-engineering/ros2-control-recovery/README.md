# Recover a ROS 2 controller chain from a hardware fault

A controller supervisor must handle a device fault without interrupting
independent branches. It needs to reconcile observed mode and interface
ownership, select compatible fallback controller chains, and issue
one primitive at a time from current hardware readback. A failed reply
or device generation change must leave enough durable state to resume.

The contract follows the ownership and controller dependency concepts in
the RRBot chaining demo and the real hardware fault investigation linked
below. The task uses a deterministic authored controller and hardware
service analog. It exercises supervisor logic on CPU without a live robot.
[RRBot chaining demo](https://control.ros.org/jazzy/doc/ros2_control_demos/example_12/doc/userdoc.html) · [Controller manager](https://control.ros.org/jazzy/doc/ros2_control/controller_manager/doc/userdoc.html) · [Fault deactivation report](https://github.com/ros-controls/ros2_control/issues/3620)

| Dimension | Evidence |
| --- | --- |
| Novelty | Extends incident replay into a forward controller recovery problem with global service coverage and revocable hardware generations. |
| Verifiability | The verifier independently enumerates compatible assignments and applies each emitted primitive to an observed hardware model. It checks measured mode, dependency ordering, counters and durable command identity. |
| Realism | Some controller chains can remain active through an unrelated device failure. Mode transitions and exclusive interfaces shape which fallback is valid. |
| Difficulty | The plan must consider competing alternatives globally. Recovery must maintain coherent authority across partial progress, a rejected switch and lost or conflicting replies. |
| Initial feasibility | Enumerate dependency closures and compatible option unions, drive one operation at a time, and commit accepted requests in a serialized journal. |

Early checkpoints score active-set reconciliation and compatible planning.
The final checkpoint scores the fraction of six independent requirement
groups passed. It exercises a non-greedy assignment, lexicographic
preferences, failed-mode fallback, a new hardware generation, restart
after a lost reply, malformed and stale input, and concurrent updates.
The verifier judges observable operation order and outcomes and accepts
alternative legal operation orders.

## Development log

### 2026-11-24

Built the three-step CPU task, a closed-loop reference, and a separate
fixture-driven verifier. The local reference passed all named behaviors.
The reference scored 1.0 and the no-op scored 0.0 at each of the three
local checkpoints. Oddish preflight found no issues. Hosted image builds
and model scores remain pending.

The hardened packaged reference and no-op scored 1.0 and 0.0 locally at the final checkpoint. Oddish accepted version 1 into the six-task batch with both controls and one GPT‑6.2 Sol xhigh attempt. Bundle SHA-256 is `a041ef7ad38c8d2070302a4d3e6ff9388456113a4403bbd32bcb1d842371fd59`. [Oddish experiment](https://www.oddish.app/experiments/439b651d)

#### Protected handover revision

The original hosted Codex trial earned 1.0 at all three checkpoints.
Oddish's trajectory analysis credited the implemented `inspect`, `plan`,
and `recover` commands. The earlier planner only had to find a compatible
static controller set and issue the next operation. The fourth step
asks for an entire handover through calendar constraints. A useful
configuration at the deadline can be unreachable unless the supervisor
activates a temporary standby before taking a dependency offline.
[Original experiment](https://www.oddish.app/experiments/439b651d) ·
[Controller Manager](https://control.ros.org/jazzy/doc/ros2_control/controller_manager/doc/userdoc.html)

The reference searches timed controller configurations. The verifier
independently replays each primitive, checks protection and exclusive
claims through every interval, and computes the best achievable end
coverage for the supplied calendar. Authored schedules model serialized
operations and known maintenance windows. Each valid optimum can earn
credit regardless of its operation ordering.

The final score gives 35% to the retained controller checks and 65% to
timed handover behavior. The timed component is the fraction of named
checks passed after at least one positive scheduling case succeeds.
Unsupported commands receive no credit. The first three checkpoints
keep their original behavior.

Ten local handover checks exercise standbys, fragmented switch slots,
planned outages, reachable group choices, and unsafe inputs. The
original reference command set earns 0.35 on the revised checkpoint.

The revised bundle passed local reference and no-op controls at 1.0 and 0.0. Oddish preflight reported no findings. The hosted version 2 batch contains one GPT‑6.2 Sol xhigh trial and both controls. Bundle SHA-256 is `b54ac5a43599c08254a74243e6fcf0b2b26c7855b864089ef3a0edb40c160b95`. [Version 2 batch](https://www.oddish.app/experiments/afbb773d)

#### Closed-loop protected joint revision

Two GPT-6.2 Sol xhigh attempts scored 1.0 on the timed handover revision.
The archived result from the full batch records 1.0 separately for all four
checkpoints. That revision measures valid operation timing and static service
availability. The fifth checkpoint adds a loaded joint whose next measured
state depends on the candidate's previous physical torque.
[Six-task trial](https://www.oddish.app/experiments/afbb773d) ·
[Full batch trial](https://www.oddish.app/experiments/57208689)

| Dimension | Evidence and limits |
| --- | --- |
| Novelty | Extends this task's own timed controller supervisor from a configuration plan to live drive authority and measured tracking. Workcell Replanning emits feasible timed robot motion, while this task consumes feedback and transfers write authority at each cycle. Exact counterparts in external benchmark collections remain unverified. |
| Verifiability | A private process independently integrates actuator dynamics, converts drive commands to torque, checks the generation and actual owner, and measures continuity, tracking and response time. Candidate output contains only directives, so candidate-reported traces cannot establish success. |
| Realism | The scenario follows the Controller Manager's state read, controller update, and command write cycle, with asynchronous lifecycle behavior and fallback dependent on available interfaces. The trial uses an authored scalar joint, shaped load, and deterministic timing and fault events. It exercises the supervisor on CPU with an NDJSON hardware adapter. |
| Difficulty | The submitter must combine lifecycle preparation, stale generation fencing, bumpless calibrated output, feedback under delayed samples, and recovery after a process restart. The previous hosted results bound the older work. Time and score on the new checkpoint are unmeasured for a hosted model. |
| Initial feasibility | The reference conditions writes on fresh chain authority, estimates the external torque from measured velocity and applied effort, then limits feedback in physical units. Its local mission trajectories satisfy the declared physical and response bounds. |

The timing and lifecycle design is grounded in the official Controller
Manager descriptions. The simulator and trajectories were authored for this
task. Continuous dynamics are approximated by numerical integration over
explicit, varying hardware cycles. The observed response-time measurements
describe this CPU harness. Native ROS executor behavior, DDS, multi-joint
dynamics and hardware real-time guarantees remain unverified.
[Controller Manager](https://control.ros.org/jazzy/doc/ros2_control/controller_manager/doc/userdoc.html) ·
[Asynchronous controllers](https://control.ros.org/rolling/doc/ros2_control/controller_manager/doc/running_controllers_asynchronously.html)

The final score gives 20% to the preserved fourth checkpoint and 80% to
closed-loop service. The closed-loop score is 97% equally weighted mission
outcomes and 3% malformed-stream handling, credited after a positive mission
behavior. Each mission gives 69% to its tracking and settling envelope, 17%
to meeting wanted-drive deadlines, 10% to bounded write interruption, and 4%
to processing deadlines. Unsafe output, including writes to a pending
owner, voids that mission. The three independent missions cover planned
maintenance with late prerequisite readiness, target reboot during a pending
transfer with supervisor restart, and actuator fault with delayed feedback
and handback. Candidate controllers can implement any feedback or authority
strategy that meets the public limits.

The earlier checkpoint instructions and grading remain in order. The Harbor
semantic task-rating report and the repository's five-day workload target
remain unverified for this CPU pilot.

## Hackability assessment

The private physical state, fault timeline and trajectories are held by the
verifier process. The submission receives live packets through a pipe and runs
under candidate credentials with a bounded reply line. A policy that emits
nominal feedforward without feedback remains safe but loses tracking credit.
A policy that assumes authority was granted while transfer is pending loses
mission credit. Fixed-fixture specialization remains a medium residual risk.
The configured hosted separation, container runtime and protection of the
private verifier files have yet to be inspected for this revision.

The archived GPT implementation scored 0.20 against the revised final
verifier. The reference scored 1.0 and no-op scored 0.0 at all five packaged
checkpoints. The reference's three physical missions stayed below 0.013 rad
position RMS. In the hosted trial, fresh GPT‑6.2 Sol xhigh scored 1.0 across all
five checkpoints. The three missions had tracking RMS of 0.0034, 0.0046 and
0.0107 rad, with maximum write gaps of zero, seven and six ticks. The hosted
reference and no-op scored 1.0 and 0.0. [Version 3 follow-up](https://www.oddish.app/experiments/20ade25d)

Oddish flagged the small initial pose error in the version 3 fixture. A
local replay of the exact GPT artifact and reference across 33 combinations
of scenario, starting position and velocity found 30 and 31 passing tracking
outcomes. Both missed the same two pending-reset cases. In the additional
GPT miss, peak error was 0.182 rad against the 0.180 rad limit. The reference
peaked at 0.178 rad on that same case. The original hosted score was 1.0.
[Version 3 trial review](https://www.oddish.app/experiments/20ade25d)

## Native Controller Manager checkpoint

The sixth checkpoint moves the recovery logic into a ROS 2 Jazzy C++
hardware plugin and a separate ROS recovery node. The actual Controller
Manager loads two independent plugin instances and stock controllers.
Two simulated drives publish live device records and follow the commands
written by the plugin. `SwitchController`, `ListControllers`, hardware
ownership and joint state come from the live ROS graph.

| Dimension | Evidence and remaining validation |
| --- | --- |
| Novelty | This extends the fifth checkpoint's authored supervisor and servo protocol into native resource claims, observed controller lifecycle and generation-fenced hardware writes. The closest other task in this collection is the [policy bridge](../policy-sim-bridge/README.md), which tests calibration and compensation rather than joint-level ownership. |
| Verifiability | The verifier observes exclusive mode claims, native lifecycle responses, fenced command writes and physical rotor motion. It checks torn, stale, future-dated, nonfinite and unavailable samples, then boots the drive into new position and effort recovery exercises. |
| Realism | A device can reboot while Controller Manager still lists its former owner as active. The plugin must inhibit the hardware while the supervisor reconciles the controller state and restores the operator's selected mode. The device transport and rotors are simulated. [Writing a ros2_control hardware component](https://control.ros.org/jazzy/doc/ros2_control/hardware_interface/doc/writing_new_hardware_component.html) |
| Difficulty | The implementation spans nonblocking shared-memory exchange, native C++ lifecycle hooks and a ROS service client that observes both generation and claimed interfaces. Completing only the hardware plugin leaves the main recovery work unfinished. |
| Initial feasibility | The packaged reference loaded on Jazzy ros2_control 4.50.0 and restored motion under stock ROS controllers. The hosted container build and fresh model score require a separate trial. |

### 2026-11-24

Added native mode fencing and two recovery trials to the previously solved
five-checkpoint task. The offline reboot restores position tracking. A
supervisor that starts after the device returns reconciles the stale position
claim and hands the joint to an effort controller. The healthy drive keeps
its independent position controller in both trials.

The exact packaged reference scored 1.0, the no-op scored 0.0 and the
version 3 reference scored 0.20. A working native driver with the recovery
process disabled scored 0.468. In the full reference run, position recovery
finished within 0.047 rad of target, and effort recovery moved the joint
0.087 rad. Both finished in under 1.7 seconds, with the independent drive
continuing to receive a position command. Oddish preflight passed. The
private follow-up contains one GPT‑6.2 Sol xhigh attempt and both baseline
controls. The hosted reference and no-op scored 1.0 and 0.0.
[Native lifecycle experiment](https://www.oddish.app/experiments/e2201944)

Fresh GPT‑6.2 Sol xhigh scored 0.404444 at checkpoint six and 1.0 at the
first five. The driver inhibited effort when it saw a retired boot, then
reported the retired generation. That failure stopped all three verifier
cases before the recovery node ran. A local driver change retained the
greatest observed generation, and the verifier launched the candidate's
installed ament Python package with its normal import path. With both
changes the archived candidate scored 1.0. The hosted reward remains
0.404444. The authoring source now specifies the generation rule, loads
installed modules, and runs the recovery cases independently of the
earlier replay probe. [Frozen v4 result](https://www.oddish.app/experiments/e2201944)

## Native restart and drive restoration

### 2026-11-24

Added a seventh checkpoint for a Controller Manager and recovery client that
can lose process state while a separate machine branch remains in service.
A closely related Jazzy report records a controller still marked active
after hardware deactivation. In the archived checkpoint-six replay, native
`STRICT` release and reacquisition could produce an enabled 0.7 Nm effort
record for a retired generation. Checkpoint seven makes the process deaths
and the replay explicit. [Jazzy lifecycle report](https://github.com/ros-controls/ros2_control/issues/3444) ·
[Jazzy hardware lifecycle](https://control.ros.org/jazzy/doc/ros2_control/hardware_interface/doc/lifecycle_of_a_hardware_component.html)

| Dimension | Evidence and remaining validation |
| --- | --- |
| Novelty | Adds native two-layer crash recovery to this task's earlier in-process generation fence. Fleet Recovery's native RMF checkpoint covers traffic authority and schedule restoration across services. This task measures controller-interface ownership and physical actuation after both sides of the control boundary lose state. Comparisons to external benchmark collections remain unverified. |
| Verifiability | Independent test processes kill and replace the native manager and client, drive the upstream binary device transport, and observe native claim readbacks and the emitted command slot. A separate measured plant integrates each branch's command, including a final actuator watchdog. The alternate branch has its own real manager, joint and lifecycle. |
| Realism | An industrial gateway can reconnect with recent-looking records from a retired device session. A steady state list or a successful switch response cannot determine whether this device epoch is still eligible. The checkpoint uses Jazzy lifecycle, controller services and state messages. The actuators and shared-memory fieldbus are authored simulations. Actual vendor PLC behavior and hard real-time certification remain outside this pilot. |
| Difficulty | Participants must carry a previously observed but never authorized boot epoch across a process kill, keep two safety layers independent, restore the appropriate command mode from fresh state, preserve earlier behavior, and keep storage operations outside the hardware control loop. Hosted difficulty and the five-day workload target remain unmeasured for this revision. |
| Initial feasibility | Jazzy ros2_control 4.50.0 ran the exact packages locally using two separate managers on loopback DDS. The reference persisted observations in atomic, per-drive records, kept C++ storage writes on a worker, and used native service and claim readbacks to restore motion. |

Checkpoint seven assigns 20% to the retained sixth checkpoint and 80% to
two equally weighted restart missions. Each mission measures initial service,
offline epoch observation, absence of retired native claims and enabled writes,
fresh effort claim and movement, and unaffected branch continuity. A retired
claim or write caps that mission at 0.25. The lower epochs are presented as
coherent, newly stamped and healthy. The restoration supplies the already
observed higher epoch with healthy readback. One case has no supervisor,
so a raw strict service caller directly exercises the restarted driver.
The other omits the optional driver journal and kills the client as well,
so the client has independent responsibility for refusing replay. Both run
the independent branch throughout.

The full reference scored 1.0 and passed all 14 new checks. The buses
delivered 298 and 343 healthy retired records and observed zero retired
claims or enabled writes. The restored joints moved 0.101 and 0.102 rad
after fresh readback at 0.710 and 0.851 s. The independent branch moved
0.620 and 0.577 rad with maximum valid command gaps of 30.1 and 20.6 ms.
The checkpoint-six reference with process-local generations scored 0.40.
It passed the retained checkpoint and both restoration motions, but
produced 124 enabled retired command records in the direct-driver case and
86 in the restarted-client case. Both safety caps applied. The no-op
scored 0.0. The package regression and local Oddish preflight passed.
The actuators, fault timeline, experiment scripts and logs are outside the
candidate image. The verifier uses the standard Jazzy packages from the
ROS package repository and authored device data. Validation used the
locally extracted Jazzy install and loopback DDS. The hosted reference
and no-op also scored 1.0 and 0.0.

Oddish accepted v5 with one GPT‑6.2 Sol xhigh attempt and both controls.
[Manager and client restart evaluation](https://www.oddish.app/experiments/8bb6b62a)

Fresh GPT‑6.2 Sol xhigh scored 0.976482. Both restart missions passed all
14 checks, with zero retired claims or enabled commands. Fresh effort
restored 0.100 and 0.101 rad of measured motion in 0.674 and 0.830 s. The
independent branch kept actuating, with valid-write gaps below 13 ms.
The retained protected-servo and maintenance cases explain most of the
remaining loss. [Version 5 result](https://www.oddish.app/experiments/8bb6b62a)

### 2026-11-24

#### Continue a loaded paired lift through a feedback-branch restart

The eighth checkpoint retains the existing seven and adds a dual-drive
lift carrying unequal loads on a compliant beam. A right-feedback
worker restarts while the lift is already moving. During the restart it
can deliver current-stamped, plausible but retired observations.
The paired lower controller retains both native effort claims. The
upper owner must switch as a strict group, continue moving with the
remaining encoder and beam-force measurement, and restore the normal
owner only after independent fresh-epoch evidence.

| Dimension | Implementation evidence and scope |
| --- | --- |
| Novelty | The earlier native restart checkpoint verifies durable authority and eventual movement of a single protected joint. This case requires continuous physical service on both drives through a native chain transition with partial feedback. |
| Verifiability | A private device plugin exposes actual Jazzy effort interfaces to the candidate controllers. The independent process owns the force-coupled plant, feedback worker, epoch change, and native service readbacks. It measures commanded force, internal load, skew, tracking, and outage progress. |
| Realism | Cascaded controller switching and shared state availability are maintained ROS 2 workflows. The physical model is a two-axis vertical lift under authored loads. It does not validate a particular drive, full robot, or hard real-time scheduler. |
| Difficulty | Fencing stale observations and safely holding the whole mechanism preserves authority but misses the moving service. The bridge must estimate relative displacement and coordinate unequal efforts. Restart observations and native claims must agree before rearming normal tracking. |
| Initial feasibility | Actual Jazzy 4.50.0 exercised both strict switches, two live feedback-process replacements, and measured 4.53 to 4.91 mm RMS tracking in the independent base and mirrored-load missions. |

The chain and reported shared-state fallback behavior are documented
upstream. The fallback report was resolved separately and motivates the
workflow. The simulator does not require that issue to be present in
Jazzy. [Controller chaining](https://control.ros.org/jazzy/doc/ros2_control/controller_manager/doc/controller_chaining.html) ·
[Shared-state fallback issue](https://github.com/ros-controls/ros2_control/issues/3038) ·
[Joint/transmission interfaces](https://control.ros.org/jazzy/doc/ros2_control/hardware_interface/doc/joints_userdoc.html)

An independent local witness measured 142 mm and 136 mm of outage
travel, against 147 mm and 143 mm requested. Peak skew was 12.0 mm and
13.6 mm. Peak native per-write effort change was 0.248 N and 0.257 N.
The sound hold-only comparison kept correct ownership, limited forces,
and returned to within 3.3 mm of the final target, while losing motion
through the interruption and increasing RMS tracking error to 78.5 mm
in the first case.

The latest checkpoint gives 20% of its score to the retained seventh
checkpoint and 40% to each complete paired-drive mission. It retains the
task's 5,400 s candidate budget and 600 s verifier budget. Each new
mission runs the physical motion for 4.15 s, separate from native startup
and compilation. Inputs are authored simulator data and no external
corpus is used. Local native qualification uses the extracted release
packages and localhost DDS. Hosted container behavior is still
unmeasured for the eighth checkpoint.

Exact local cumulative qualification of the frozen eight-step bundle
scored 1.0 for the reference, 0.0 for the no-op, 0.20 for the unchanged
v5 reference, and 0.20 for the variant that held height during the
interruption. The hold variant passed both native authority and force
envelope checks, then failed tracking and outage progress in both
missions. Its RMS errors were 75.8 mm and 73.5 mm. The reference measured
4.52 mm and 4.90 mm. The maintained pytest suite passed all three tests,
and the installed Harbor task model parsed the configured eight steps.

Oddish preflight passed. The hosted reference and no-op scored 1.0 and
0.0. One fresh GPT‑6.2 Sol xhigh attempt is underway.
[Loaded chain handover evaluation](https://www.oddish.app/experiments/dcfc86bc)
