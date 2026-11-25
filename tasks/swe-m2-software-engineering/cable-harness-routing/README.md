# Flexible harness routing and recovery

Draft benchmark for a robotics engineer building a controller for flexible
wiring harness installation. One arm feeds, grasps, routes and seats a harness
on a fixture board. A common application must handle a characterized cable, a
batch with unknown mechanical parameters, and recovery on a partly assembled
board. The proposed environment is a headless CPU simulator.

## Operational evidence and comparisons

CRAFT reports physical trials around several fixture types on a modified NIST
board. Tactile routing research describes finding the relevant material
position along a cable before seating it in intermediate clips. Both motivate
measuring which part of the cable reaches each fixture and what happens to
earlier clips as the robot feeds the remainder. The draft adds unknown-batch
qualification and interrupted job recovery to an independently checked
software deliverable. Fixture geometry and held-out cases will be authored
for this benchmark. [CRAFT](https://www.research.autodesk.com/publications/craft-long-horizon-cable-routing-algorithm-low-friction-caging-gripper/) · [Tactile routing](https://ieeexplore.ieee.org/document/10160729/)

[Dual-Arm Handoff](../dual-arm-handoff/README.md) checks the pose, clearance
and custody of a rigid payload. A cable has an ordered material coordinate,
bend limits and distributed fixture constraints. The controller can dislodge
a previously seated free segment without moving the connector. This draft
measures those outcomes through the plant. [MuJoCo Branch Replay](../mujoco-branch-replay/README.md)
checks simulator state transfer. Here the process reconstructs its action
authority from plant receipts and partial measurements while the simulator
continues to own the physical state.

DeepSWE's original repository tasks and FrontierSWE's integrated simulation
problems are precedents for assessing an executable engineering deliverable.
FrontierSWE's public flight-simulator rendering task matches reference
pixels. This task checks contact, material order, forces and recovery over
successive versions of the same controller. SWE-Marathon v1 provides the
long-horizon and layered-verification precedent. Exact task-level overlap
beyond these examples remains unverified. [DeepSWE](https://arxiv.org/abs/2607.07946) · [FrontierSWE v2](https://www.frontierswe.com/blog/v2) · [SWE-Marathon v1](https://www.swe-marathon.org/swe-marathon-paper.pdf)

## Task design

| Dimension | Argument, evidence and remaining question |
| --- | --- |
| Novelty | The deliverable must combine route topology, elastic feeding and interrupted operation for the same installed cable. CRAFT is the closest physical workflow. The proposed batch qualification, maintained material assignments and recoverable command authority distinguish the software contract. |
| Verifiability | The native plant owns contacts, tool forces, and the keyed seat. The observer reconstructs aperture crossings from the ordered cable geometry and rest coordinates. It detects wrong material and loss of seating during a pull. Whole-route measurement tolerances and held-out cases remain to be qualified. |
| Realism | Feed friction and partially occluded cable shapes change whether the next move can be executed safely. A fixture change can leave a part installed. Instrumented clips, the wrist sensor and visible material marks give the supervisor physical evidence. Clip latching, friction and material variability will be explicit simulator models. Hardware fidelity remains unmeasured. |
| Difficulty | Useful motion requires a consistent assignment of material to fixtures, safe feeding under load and several observations of unknown cable shape. The final recovery must preserve this state across changing constraints and a lost reply. The five-day workload estimate is unmeasured. |
| Initial feasibility | A sampled rod centerline and alternative material assignments can support bounded probes. A graph of fixture approach sides and grasp positions can propose routes, followed by local force feedback and regrasping. A journal can retain accepted motion IDs. The arm has routed both clips and passed the retention pull. Coupled keyed seating remains pending. |

### Cumulative work

| Checkpoint | New information and required work | Workload estimate |
| --- | --- | --- |
| 1. Route the characterized cable | Board layouts, arm and tool calibration, characterized cable and route recipes. Build the planning and control loop, confirm seating and hold safely on a blocked route. | 1.5–2 days for layout ingestion, route search, control and replay. |
| 2. Fit a replacement batch | Parameter intervals, observed loads, missing material marks and a partial cover. Choose bounded probes, maintain material assignments under limited visibility and feed the new cable through the same cell. | 1.5–2 days for probe design, parameter fitting and physical-loop debugging. |
| 3. Recover an interrupted board | New fixture generation after work is underway and a process restart before receipt. Preserve the installed material, derive a revised route, reconcile pending commands and complete or hold. | 2–3 days for recovery logic, replacement route experiments and regression checks. |

The [workcell protocol](environment/resources/workcell-protocol.md) defines the
controller messages and motion authority. Feasible operating envelopes come
from the recipe. Trials should accept faster valid solutions.

## Verification and reward proposal

Grade commands through a trusted plant with the same exposed observations as
the workcell documentation. Run a finer-step observer independent of the
candidate planner. Check motion and retention through plant outputs, including
the cable centerline in material order, signed fixture entry, measured wrist
forces, and connector depth and interlock. A final sensor flag alone cannot
establish retained seating or compliance throughout execution.

| Public behavior | Evidence and acceptance |
| --- | --- |
| Route matches recipe and stays seated | Reconstruct each occupied clip's material interval from native rod segment identities and intersect the ordered centerline with fixture gates. Require the correct side of entry, material order and keyed seat, then observe retention during the disclosed pull. |
| Motion stays within limits | Integrate all applied commands at the plant step. Bound peak wrench, tool/joint speed, forbidden contact and minimum centerline bend radius by the published recipe. Earlier installed clips must remain seated. |
| Handle unknown batches and partial views | Use independent parameterized runs that require different feed responses. Compare physical outcomes and probe use with the recipe limits. Check that the calibration report refers to real observations. Accept any estimates that support valid measured behavior. |
| Resume or hold on revised board | Interrupt after an accepted command and before receipt, inject obsolete observations and apply the revised fixture state. Compare the controller replies with independent actuator receipts and physical effects. Require safe completion when the routed suffix is attainable and a safe hold when the revised constraints make it unattainable. |

Checkpoints 1 and 2 each use the fraction of authored cases completed.
A case passes only when its full published motion and outcome requirements pass.
New refusal-only credit requires at least one positive completion in its
checkpoint. Checkpoint 3 retains 30% of checkpoint 2 and assigns 70% to the
fraction of its three proposed missions completed. Two missions require
positive delivery after different interruptions. The third requires a safe
hold under an unsatisfiable revision. New credit is zero until at least
one recovery completes. Earlier functionality can then earn up to 0.30.
The weights reflect that the revised physical outcome is the main deliverable.

Keep case denominators fixed. A missing application or required output
earns zero for affected cases. A plant or verifier fault invalidates the
trial. Choose attainable and blocked cases using independent geometry and
bounded physical controls. Qualify a full reference, no-op and controls
that route the wrong material, dislodge a previous clip, exceed a load,
move on stale observations or repeat a physical command. A score below
0.5 on fresh GPT-6.2 Sol xhigh is a selection target. It remains unmeasured.

## Hackability assessment

YELLOW / UNASSESSED. The verifier should derive fixture state and force
history from native simulator state under its own control. Randomize board
and cable variants within the disclosed contract and hold back scenario
parameters. Candidate output should contain only bounded commands and honest
records. Keep all validator fixtures and reward files outside the candidate
runtime. Test forged status, stale-generation and duplicate commands during
qualification. Those controls and container isolation are pending.

## Development log

### 2026-11-25

Wrote the three checkpoint briefs and the verification proposal. Reviewed
CRAFT, tactile routing and the [pinned MuJoCo 3.3.7 cable example](https://raw.githubusercontent.com/google-deepmind/mujoco/3.3.7/model/plugin/elasticity/cable.xml).
Ran an independent toy MuJoCo 3.3.7 smoke check in the existing CPU environment.
A half-metre native cable with 16 bodies advanced 500 one-millisecond steps
with finite state, 0.118 m end displacement and nine peak contacts against
a plane. The pilot used gravity and a fixed root. The working arm, gripper and
fixture models, complete reference, Harbor review and hosted trials are
pending.

#### Native insertion and cable measurements

Ran separate subassembly pilots in MuJoCo 3.3.7. The clip trial used a
22-link elastic cable and a force-limited Cartesian endpoint. The 237.5 mm
material mark crossed the open side under 0.342 N, then remained within
0.323 mm of its seat over 294 mm of tail travel. With the material pin
disabled, the closed door still constrained the cable inside the pocket
under native contact. With the door open, the same pull withdrew it. A
solid obstacle prevented seating, and a fabricated latch command had no
physical effect. The positive run reproduced identical controls,
observations and measurements. Source and traces are in
`experiment/subassembly-native-20261125.NHfRwP/clip/`.

Replayed the four clip cases and checked the centerline at all 2,000 native
ticks of each pull. The observer independently measured the inward entry
at 1.74078 s. The full latch and the contact-only door kept a valid material
crossing throughout. The blockade never produced a seated crossing, and the
open door lost its crossing at tick 4,020. Applying incorrect material
coordinates to the final seated geometry also failed.

In a separate plant, the six-axis arm reached all six fixture approach
waypoints within 1.73 mm and 0.0034 rad. The physical gripper fed 35.04 mm
of cable through its closed slide guide. An independent centerline measurement
found that the material crossing moved from 240.606 to 275.650 mm as the
cable slid through the same aperture. This is the failure a clip switch
alone would miss. The arm pilot and calibration are in
`experiment/subassembly-native-20261125.NHfRwP/arm/`.

Combined the articulated arm with the clip and elastic cable. The original
wrist housing collided with the board during approach. A gripper mounted
55 mm below the flange seated the intended material mark. The first pull
tripped the 2 N grasp limit. Retiming the approach and pull kept peak grasp
reaction at 1.521 N and incremental wrist force at 1.459 N, with no forbidden
contact above the 5 mN detection threshold. While the arm pulled the tail
297 mm, native shutter contact retained the 237.5 mm mark inside the clip.
The workcell used no board fixation constraint. The same arm commands
with the shutter held open withdrew the mark. The matched runs and model are
in `experiment/subassembly-native-20261125.NHfRwP/arm-clip/`.
An independent check of all 209 recorded pull snapshots found the expected
material crossing throughout the closed run. The open run lost the crossing.
Both native traces and their physical measurements reproduced on replay.

The keyed socket seated the nominal plug and held it within 0.113 mm under
a 3 N pull for 0.4 s. The reversed key jammed against the socket and the
unlocked plug withdrew past the 15 mm travel limit. That pilot is in
`experiment/connector-native-20261125.xkDXuu/`.

Twenty-two protocol and metrology checks passed. They cover stale motion
authority, forged latch actions, material identity, traversal direction,
bend radius and retention across the pull interval. The single-clip trial
used a prerecorded tail path. Multi-clip clearance, camera visibility,
and seating the connector while holding earlier clips still need to be
verified in the same workcell. The interrupted and replacement-batch
missions and hosted evaluation remain pending.

#### Two-clip routing and retention through later motion

Added a downstream clip with the opposite entry direction. Its deeper pocket
and narrower shutter let the oblique cable clear the shutter's swept volume.
The force-limited endpoint pilot seated both clips and applied a 106.6 mm tail
pull. A solid obstruction stopped the second installation while the first
stayed seated. Disabling only the second shutter also preserved the first and
allowed the second segment to withdraw past its mouth. The positive run
reproduced the compiled inputs, native observations and measurements exactly.
The three cases are in `experiment/two-clip-native-20261125.Y7tOjY/native/`.

The articulated arm then seated both clips using a retimed recorded tail
path. It entered the first mouth in +Y at 3.328 s and the second mouth in −Y
at 7.595 s. The initial mark stayed at least 5.97 mm inside its clip during
the second insertion. Both stayed seated during the 107 mm pull, with
1.521 N peak grasp force, 1.458 N incremental wrist force and 0.0868 N·m
incremental wrist moment.
The arm made no forbidden contact. The matched open-shutter case entered
the second clip and escaped during the pull, while the first stayed seated.
No board fixation constraint or direct cable force drove either case. Both
model files, traces and physical measurements reproduced. See
`experiment/two-clip-native-20261125.Y7tOjY/arm/`.

The independent temporal observer separates lateral entry at the mouth from
through-direction and material at the seat. It confirmed both installations
over 5,751 native endpoint observations and all 10,720 native arm ticks.
In an injected control, the first crossing failed for one tick during
second-clip entry while its switch and
the final route remained identical. The observer rejected that run. The
development suite now has 33 passing protocol and metrology checks.

A calibrated depth pilot physically hid five readable material marks under
an opaque cover. An oblique view recovered two of those marks. The camera
returned a new set of point IDs on a second overhead capture and reported
unreadable marks without material coordinates. The ray model and captures
are in `experiment/cable-keyed-seat-20261125.NepQdp/camera-evidence.json`.

Attached the connector to the cable through a compliant native joint and
attempted docking after seating an earlier clip. A clearance path and a finer
contact timestep preserved that clip in all 26,195 docking snapshots.
The plug still stalled about 24 mm short of the seat and never engaged the
interlock. This test used a bounded wrench on the plug. The preliminary
interference results are in
`experiment/cable-keyed-seat-20261125.NepQdp/guided-inlet/nominal/`.

Native contacts confirmed the cable boot was hitting the inlet floor.
Reducing its vertical offset let the keyed plug reach the interlock with
the same socket geometry. An engaged retainer limited translation to
0.058 mm under a 3 N pull, compared with 15.33 mm of withdrawal with the
retainer disabled. The earlier clip stayed seated in all 26,960 observations
of the nominal docking and pull. The final rotation error was 0.040 rad,
outside the pilot's 0.006 rad seat tolerance. The reversed key never reached
the interlock and produced excessive contact. Those controls establish the
physical effects of the boot clearance and interlock. Force-limited docking
with the articulated arm and both clips in place remains unverified. See
`experiment/cable-keyed-seat-20261125.NepQdp/damped-grip/`.

#### Docking load, batch probes, and interrupted motion

The plug rotated before the pull while the native retainer resisted cable
preload. Recalibrated the retainer with `solref="0.002 1"` and
`torquescale="0.2"`, leaving the keyed housing and seat tolerances unchanged.
The earlier clip stayed seated through all 26,960 docking observations.
During the 800 native ticks under the 3 N pull, the largest absolute position error was
8.17 µm and the largest angular error was 0.00354 rad. The unlatched control
withdrew 15.33 mm. The independent verifier rejected the original damped run
for angular error and records whether the hardware actually released its
grip. The corrected test used an actuator-driven plug with the drive turned
off before the pull. It has no articulated release evidence. The native
traces and audits are in `experiment/keyed-retainer-20261125.s3yD53/`.

Tested four combinations of effective cable bending stiffness and sliding
friction with the same opaque cover. Their initial depth observations were
identical. Raising the stiffness increased the peak probe force from about
0.114 N to 0.159 N. Under the same lateral stroke, a visible mark moved
5.66 mm at the low-friction setting and 0.93 mm at the high-friction setting
for the more flexible cable. These measurements motivate separate lifting
and feeding probes. The effects of sensor bias, partially hidden initial
curvature and held-out parameter combinations remain unmeasured. Source
and captures are in `experiment/batch-probe-20261125.AiANuo/`.

Exercised receipt recovery on the articulated plant after the first clip
closed. The author controller was killed after a 120-tick motion had run
42 ticks and stopped, before the receipt was delivered. A fresh process read
the pending command from its durable outbox. The plant returned the original
receipt and left the simulator tick, joint state and actuator inputs exactly
as they were before the retry. A guide was then placed over the old goal and
the board generation advanced. The plant rejected the prior command, a new
ID tied to the old observation, and the old command ID restamped with the
current generation and observation. A newly authorized command retreated
8.09 mm without forbidden contact or losing the earlier
clip. The controller followed an authored retreat. Completing the revised
route and docking autonomously are separate parts of the recovery mission.
The native path reproduced exactly. The run is in
`experiment/physical-restart-20261125.AqXRqH/`. The harness development suite
now has 50 passing checks.

In a separate endpoint-driven fixture trial, three cases shared the same
physical state before the guide revision. The original route seated both
clips with the guide parked. With the guide moved, it contacted the guide
at 2,004 native ticks and left the second clip open. A detour cleared the
same guide and retained both clips through a 70.22 mm pull. The minimum
bend radius was 86.82 mm and the peak applied grasp force was 0.603 N. The
material and aperture audit passed all 7,591 native observations. Results
are in `experiment/physical-restart-20261125.AqXRqH/alternate-guide/`.

The articulated arm also acquired the tethered plug through opposing jaw
contacts and closed the first clip by carrying it. The existing tail path
brought the plug into contact with the socket floor before the second clip
closed. A lateral detour cleared the socket and preserved the first clip.
The cable reached a 36.6 mm bend radius and the grasp tripped at 2.024 N
before the second entry. The final full-assembly route and release remain
unverified. The trials are in `experiment/articulated-plug-20261125.4n1pGr/`.

#### Controller boundary, held-out probes, and socket clearance

Drove the two-clip articulated plant through its JSONL controller boundary.
A separate author controller solved joint targets from a recorded route and
the current joint feedback. It acquired the terminal cable mark from the
current depth frame and received plant receipts for 1,042 joint commands.
The independent route audit passed all 10,720 native ticks. The native trace
reproduced exactly. A stale camera point ID was rejected before the gripper
closed. A completion claim failed both from the initial board and after both
clips had seated, since the keyed connector was still unseated. This pilot
exercises the command interface with a terminal pinch. The traces are in
`experiment/serial-workcell-20261125.YP73g9/`.

Two held-out batches with different stiffness, friction and hidden initial
shape admitted the same 66 camera, tip and wrench observations under the
declared sensor error model. The direct lift peaked at 0.1195 N on one batch
and 0.1442 N on the other, against a 0.13 N test limit. Reducing axial
shortening let both clear the 18 mm lift with peak loads below 0.069 N.
Across eight native trials, separate lift and reciprocal feed measurements
distinguished stiffness and friction bands even with a constant wrench bias.
An intermediate batch still admitted broad parameter ranges and cleared the
same milestone with the conservative motion. These trials cover bounded
probes and the lift, with results in
`experiment/batch-probe-20261125.AiANuo/heldout/`.

The passive keyed plug traveled with the cable during routing. A tangent
socket left both clips seated through all 6,751 observations, including one
second with the cable drive off. The original socket physically blocked
the old feed and left the second clip open. A free-span calculation also
ruled out the raised socket for final docking under a 65 mm smooth bend
radius. Its largest possible seated chord across the legal aperture was
81.14 mm, while even the shortest admissible free span needed 109.39 mm.
The tangent layout and a staged docking path cleared the bend-chord and
sampled plug geometry screens at the measured material assignment. These
screens use the held clip crossing as a fixed point during docking.

The tangent socket still intersects the original arm sweep. Screening its
placement against 536 recorded configurations found housing contact near
the first pickup, and all nearby mounts that passed the axial span screen
still intersected the original sweep. A live arm trial with the raised
socket held the earlier clip and tripped the grasp limit when the housing
met the socket wall. Shifting the tangent mount and grasping farther up the
cable also produced tool and socket contact during pickup. The native route
controls, geometric screens and arm
attempts are in `experiment/service-fixture-20261125.yU1Oqo/`. Full routing,
regrasp, and keyed docking still need a qualified articulated trajectory in
one fixture.
