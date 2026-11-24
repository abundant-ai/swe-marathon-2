# Mixed-fleet delivery recovery

Build a delivery coordinator for a shared facility. One fleet accepts route changes. A second fleet follows a fixed loop and accepts permission to advance. The coordinator must assign parcels, reserve space, route around outages, and recover outstanding movement authority from its durable state.

## Design dimensions

| Dimension | Evidence and remaining questions |
| --- | --- |
| Novelty | The deliverable is a small coordinator with a single interface across heterogeneous fleets, rather than a patch to a historical robot defect. Robo-SWE uses repository changes from historical robotics issue resolution. RoboBugBench reproduces historical navigation faults and evaluates robot behavior. This task evaluates lifecycle integration through fault injection. The closest internal robotics proposal, Localization Replay, evaluates recorded pose reconstruction and diagnostics. SWE-Marathon v1, Deep SWE, Frontier SWE, and Multi-Step SWE have not been compared task by task. [Robo-SWE](https://arxiv.org/abs/2611.16116) · [RoboBugBench](https://arxiv.org/abs/2610.16369) · [SWE-Marathon](https://www.swe-marathon.org/swe-marathon-paper.pdf) |
| Verifiability | A separate simulator processes real commands from the submitted program, tracks the occupied resources and parcel handoffs, and checks whether work resumes after fresh physical evidence. Each fixture is deterministic and has an independently checked outcome. The grader covers selected graph and fault combinations, not a full proof of collision freedom or eventual delivery for every reachable topology. |
| Realism | The Open-RMF Office demo runs a full-control robot with a traffic-light-controlled robot. Open-RMF has documented premature release of an occupied mutual-exclusion group, and VDA 5050 specifies order handling and physical stop reporting when an order is canceled. The task retains those coordination problems and includes a public Office subgraph. Private incidents and their timings are constructed. Neither middleware interoperability nor live hardware safety is evaluated. [Open-RMF demos](https://github.com/open-rmf/rmf_demos) · [Occupied resource report](https://github.com/open-rmf/rmf_ros2/issues/573) · [VDA 5050 v3.0.0](https://github.com/VDA5050/VDA5050/releases/tag/3.0.0) |
| Difficulty | Earlier routing and job decisions persist into later checkpoints. Candidates have to track parcel progress, command identity, independent robot sequencing, contention, and physical occupancy through a crash. The hours-scale pilot tests capability and has no five-day workload evidence. Extending it to a production-size negotiation trace or live adapter integration would require separate scope, verification, and trials. |
| Initial feasibility | A standard-library route search, explicit outstanding-command claims, and transactional event/state persistence provide a working approach within the headless runtime. Local controls establish feasibility for the tested cases. Hosted runtime and independent candidate performance remain to be measured. |

A model-based Harbor check and numeric task-quality ratings are pending. Reward data from the executable controls below does not establish task-quality ratings.

## Verification and reward

The candidate delivers `/app/fleet_recovery`, a Python package that implements the event protocol. The grader launches it with case-specific state and stops and restarts actual processes. It sends only case JSON and protocol inputs. Oracle and grader code are packaged on separate harness paths. The oracle uses persistent atomic snapshots. The verifier makes reservations with its own robot world model driven by the commands it observes.

1. Deliver across both fleet modes, respecting exclusivity and active parallel service.
2. Preserve mixed delivery and verify diversion, safe egress, reopening progress, and ordered priority.
3. Retain earlier checks and verify crash replay, stale telemetry, a confirmed return, cancellation of unpicked work, and preservation of a parcel already picked up.

Each of the first three checkpoint rewards is the fraction of its checks that pass, including retained checks. A checked movement grant overlapping another robot's physical or reserved resources sets that checkpoint reward to zero. The first release used the arithmetic mean across checkpoints. Checkpoint four uses 30% from the seven earlier checks and 70% from six shared-lift cases. The lift component requires a successful joint itinerary and interrupted-grant recovery. The final checkpoint reruns checkpoint four for 20% of its reward and tests atomic corridor bundles for 80%. The new fraction requires a successful joint route allocation or recovery of a previously issued corridor bundle. Checkpoint reports record per-check observations. Fixture times are a simulated clock. The subprocess deadline detects a stuck or unflushed protocol.

A reproducible build is `python3 scripts/package_task.py`. From the generated runtime bundle, run each `steps/<step>/tests/verify.py` with the matching `--stage`, `--artifact steps/<step>/solution/fleet_recovery`, and an output directory. A missing or no-op artifact is a zero control. `oddish preflight experiment/dist/swe-m2_software-engineering_fleet-recovery` checks package wiring.

## Hackability assessment

| Finding | Boundary and evidence | Remaining risk and next validation |
| --- | --- | --- |
| 🟡 YELLOW / MEDIUM | A coordinator could recognize repeated private traces and time commands specifically for them. Public data is a distinct Office graph. Private site IDs have no operational meaning and the checks require legal end-to-end behavior under a private physical simulator. | The first pilot uses a small collection of incident shapes. Add held-out graph layouts and mutate incident order before treating performance as evidence of generalization. |
| 🟡 YELLOW / UNASSESSED | Candidate output is parsed in a separate verifier environment. The verifier copies only the declared application artifact, omits links, and runs it as an unprivileged account when started as root. The shell writes reward artifacts in a directory created with mode 0700. | Local subprocess tests exercise the protocol. Hosted mounts, effective user, and network isolation still require an independently observed hosted control. |
| 🟢 GREEN / LOW | The runtime artifact provides no verifier input beyond executable source and JSON protocol responses. Checks use no model judge or candidate-supplied evidence. The preflight inspects the declared package, and the verifier rejects missing results. | Inspect hosted container and artifact boundaries in the first control runs. |

The highest supported concern is medium, and hosted isolation remains unassessed. There are no live accounts, robot credentials, or production systems in the fixtures.

## Development log

### 2026-11-23

Built the three-checkpoint pilot. Retained corridor lanes from the Open-RMF Office map as a public example, then implemented an independent physical simulator, fault traces, and a runnable reference. Local reference scores were 1, 1, and 1. The no-op scores were 0, 0, and 0. The repository task structure check, installed Harbor configuration parser, and Oddish preflight accepted the bundle. A reference with persistence removed passed four retained checks and failed all three new recovery checks, scoring 4/7 on checkpoint three. A reference that drops unconfirmed movement reservations failed on a reported physical conflict and scored zero on checkpoint three. Hosted controls, model difficulty, and formal ratings are pending.

The hosted no-op scored 0.0 and the reference scored 1.0. Codex GPT‑6.2 Sol at xhigh earned 1.0 throughout and passed all seven final checks in one screening attempt. [Oddish screen](https://www.oddish.app/experiments/9fe9d13b)

#### Shared-lift extension

The fourth checkpoint adds a two-lift shift with flexible and fixed-route
robots. It checks an optimal reachable itinerary, both car floors after
settlement, and a retained grant after a lost reply. A fresh terminal
report can free one car without unblocking an uncertain one. Other
cases cover fragmented authorization windows, returned cargo and
malformed calendar changes. The reference optimizes lift allocations
over future schedules and stores the actual grants before publication.
[Open-RMF hotel demo](https://github.com/open-rmf/rmf_demos#hotel-world)

The packaged reference passed the seven retained checks and six new lift cases. The final no-op score was zero. Oddish preflight reported no findings.

### 2026-11-24

#### Atomic lift and corridor bookings

GPT‑6.2 Sol xhigh scored 0.957143 on checkpoint four. All six lift cases
passed. One retained case observed `urgent-first`, `routine`, `urgent-second`
at pickup, violating priority and arrival order. [Oddish result](https://www.oddish.app/experiments/57208689)

Checkpoint five adds bundled authority across lift cars, vestibules and
exit paths. The scheduler must choose routes and starts jointly, preserve
admission order across repeated requests, and retain every held resource
through a lost reply and conflicting device receipts. The verifier checks
route alternatives and independently enumerates feasible occupancy slots.
Its cases cover wrong priority, fragmented windows, competing approaches,
and partial, stale and contradictory clearance. The authored model uses
discrete simulated timing and unit-capacity interlocks. [Open-RMF lift cancellation report](https://github.com/open-rmf/rmf_ros2/issues/389) · [Open-RMF mutex group implementation](https://github.com/open-rmf/rmf_ros2/blob/main/rmf_fleet_adapter/src/rmf_fleet_adapter/events/LockMutexGroup.hpp)

Local reference and no-op scores were 1.0 and 0.0 at every checkpoint.
The archived GPT package earned 0.191429 on the new final checkpoint
without changes to its code. Its earlier lift behavior still passed.

The instruction now specifies that a trip must fit within one authorization
window per resource. The recovery probe checks that a conflicting request
is still blocked before the client retries the lost reply.

The hosted corridor revision scored 0.991429. The original priority and
arrival-order case was its only miss. Every lift and new atomic-corridor case
passed the hosted verifier. [Version 3 follow-up](https://www.oddish.app/experiments/9a2d8a0f)

#### Facility allocation with energy and worst-case clearing

The sixth checkpoint replaces complete itinerary recipes with a facility
graph, eligible robots, measured battery levels and unassigned work. It
requires global assignment and route search across power, vestibule and
corridor constraints. Distinct cases exercise a four-robot shift, a shared
charger queue, battery reserve, priority and FIFO, and the lower-level
clearance slack that makes a tempting short permit unusable. Published
plans reserve each exclusive device through its worst-case clearance tick.

The verifier replays ownership, physical time cells, battery and every
pickup and drop against independently derived optimum outcomes. The final
score gives 20% to the previous corridor checkpoint and 80% to the eight
network checks. New credit requires a successful shared-passage detour or
joint charging and assignment. The local reference scored 1.0 and the
no-op 0.0. The archived v3 GPT artifact scored 0.198286. A reference that
ignored lane clearance slack scored 0.50 and missed five network checks.
The runtime uses a discrete traffic model and authored facility schedules.
[Open-RMF traffic negotiation](https://github.com/open-rmf/rmf_traffic/blob/main/rmf_traffic/include/rmf_traffic/schedule/Negotiation.hpp)

Oddish accepted the version 4 package with one GPT‑6.2 Sol xhigh attempt,
one reference, and one no-op. [Version 4 trial](https://www.oddish.app/experiments/3a1a3784)

Fresh GPT‑6.2 Sol xhigh scored 0.998286. It passed all eight network
checks, including shared power, deadline slack, worst-case clearance and
the facility detour. Priority and FIFO in the retained blockage checkpoint
was the only remaining miss. Hosted reference and no-op scored 1.0 and 0.0.
[Version 4 report](https://www.oddish.app/experiments/3a1a3784)

#### Restore measured authority on a native crossing

The seventh checkpoint integrates pinned ROS Jazzy `rmf_traffic`
interpolation, Database, Mirror, dependency release and continuous
collision detection with a durable mixed-fleet coordinator. The exercise
uses an authored 2D office passage and independent continuous kinematic
motion. The read-only carrier cannot be ordered to move. The courier
continues safe local motion and can take a physical bypass. This mirrors a
public Jazzy case where the adapter treated vendor path counts as
interpolated checkpoint indices and released a waiting robot early.
[Reported office deployment issue](https://github.com/open-rmf/rmf_ros2/issues/584)

The package exposes the C++ starter and sample NDJSON in
[the public fixture](environment/example/rmf/README.md), with exact
[dependency pins and notices](environment/native-rmf/SOURCES.md). The
verifier first checks the released native library against a delayed
crossing, rejects an incompatible mirror base and verifies checkpoint
release in the replacement plan. Three separate motion cases test gap
recovery, receipt replay and a useful bypass. The final score gives 20%
to the retained checkpoint 6 score and 80% to the three complete native
traffic missions.

The reference crossed or bypassed with at least 0.51 m measured swept
clearance. The restart kept the exact committed command after a receipt
with inconsistent physical location. The bypass completed in 15.725 s
while the guarded crossing was unavailable. Local final scores were 1.0
for the reference, 0.0 for the no-op and 0.20 for the prior reference.
The vendor-count ablation
failed both guarded-crossing cases. The latest-mirror shortcut failed the
missing-base case, and treating a receipt as settlement without the
measured pose failed the restart case. Native linkage uses the Jazzy
3.3.3 traffic library on Ubuntu Noble. The test uses the native library
without launching ROS nodes or a full Gazebo world.

Oddish accepted the native package with GPT‑6.2 Sol xhigh and both controls. [Native Open-RMF experiment](https://www.oddish.app/experiments/edcef210)

Fresh GPT‑6.2 Sol xhigh scored 0.466324, with a 1.0 reference and 0.0
no-op. The native bypass reached delivery in 15.725 s with 0.99 m clearance.
Both guarded missions stopped on the checkpoint report at tick 63 after
the candidate had entered the crossing. The simulated saturation
calculation sent `3.2199999999999998` m for the declared `3.22` m endpoint.
GPT compared the values as published and reported the previous
checkpoint. The frozen verifier used a `1e-7` m tolerance and expected
the endpoint checkpoint. [Version 5 result](https://www.oddish.app/experiments/edcef210)

The maintained plant now emits the declared endpoint once the travel
distance saturates. The unchanged GPT archive passed both guarded
missions after that change, including recovery from the mirror gap and
exact replay after restart. Both crossings delivered in 16.2 s with
0.51 m minimum clearance. The bypass still passed. The full local
replay of the unchanged artifact scored 0.999657.
The official 0.466324 remains the score on the original frozen verifier.

#### Renegotiate two responsive couriers around a committed carrier

The eighth checkpoint retains all earlier cases and adds a crossing in
which two couriers have competing deadlines. An independent courier
delay and carrier tail replacement invalidate their earlier grants.
The carrier keeps its in-flight approach, and the couriers' unstarted
grants remain outstanding until both cancellations are confirmed at
their measured home positions. The scheduler can use the staged
courier's approach while the urgent courier retains crossing authority.
The protected stage exit waits for observed progress on both the
current direct-courier itinerary and the current carrier itinerary.

The reference enumerates bounded departure slots with native
`Interpolate` and continuous `DetectConflict`. It supplies compatible
proposals for both responsive orderings to `Negotiation` and ranks the
accepted joint finish times by priority. Its adapter journals the
schedule cursor, cancellations, physical observations and exact
operation receipts before publishing replies. The public practice
request can be run twice to inspect the resulting receipts.
[Native package provenance](environment/native-rmf/SOURCES.md) ·
[Practice crossing](environment/example/rmf/README.md) ·
[Open-RMF traffic API](https://github.com/open-rmf/rmf_traffic)

The private checker derives straight-leg velocity profiles independently,
finds the continuous minimum swept-disc clearance, and checks
deadline-optimal completion across departure slots. It checks three
positive replans, including altered acceleration and footprint, a
missed release deadline, and an infeasible joint deadline. It opens
fresh processes at each adapter exchange. Every mission has equal
weight within the eighth checkpoint, which contributes 80% to the
final score. A physical conflict still fails the cumulative score.
The scenes are authored planar traffic simulations using pinned native
Open-RMF. They assume straight, rest-to-rest legs and serialized
adapter requests. They do not require a ROS graph or physical robots.

In the base replan, the staged courier starts its approach at 7 s,
the urgent courier departs at 10 s, and the protected exit releases at
15 s. The couriers arrive at 16.066667 s and 20.066667 s. The independent
minimum separation between their swept footprints and the carrier's is
0.047130 m. Waiting for the urgent courier to finish before even
starting the approach misses the staged courier's 20.9 s deadline.
The asymmetric-profile replan measured 0.102762 m of clearance,
and its two arrivals changed to 15.883380 s and 20.412560 s.

The final local bundle scored 1.0 for the reference, 0.0 for the no-op,
and 0.199931 for the unchanged hosted v5 candidate after the endpoint
correction described above. A native reference ablation that forced the
staged courier to wait at home until the direct courier finished scored
0.36. It passed the deliberately infeasible deadline case and missed
the four missions with recoverable schedules. The maintained package
test, candidate-visible practice crossing, and Oddish preflight passed.
The verifier and oracle ran locally against the extracted package
libraries. The hosted reference and no-op scored 1.0 and 0.0.

Oddish accepted v6 with one fresh GPT‑6.2 Sol xhigh attempt and both
controls. [Three-participant negotiation evaluation](https://www.oddish.app/experiments/9abc4012)

Fresh GPT‑6.2 Sol xhigh scored 0.999931. It passed all five native
negotiation cases. The base replan preserved 0.047 m of swept
clearance between footprints. The asymmetric-profile case held
0.103 m clearance. The late report left the missed protected
departure blocked, and the infeasible urgent deadline issued no
movement authority. The hosted reference and no-op scored 1.0 and 0.0.

### 2026-11-24

#### Reserve crossing and lift options before either observation arrives

The ninth checkpoint extends the native traffic negotiation task with
two independent observations. Both couriers must move to safe holding
positions while a carrier's departure and the lift supervisor's sessions
are unresolved. A current carrier plan releases one pair of crossing
authorities. The lift's later observation releases door approaches
without rewriting those crossings. A current cabin, session, floor,
open-door readback and measured docking pose release boarding.

The two facility profiles expose different scheduling failures. In the
first, all native-safe gate timings for one carrier observation conflict
or miss deadlines in the other. The two selected gate pairs are
`(5.00, 10.00)` and `(5.00, 6.25)` seconds. In the rotated relief-booking
profile, a deterministic replanner can choose a safe crossing that
works for the expected lift while committing the urgent courier too
late for relief. The contingent reference puts that courier through
first and keeps both lift continuations available. In both profiles,
waiting to start the approaches until the first observation leaves
no feasible schedule.

The reference enumerates a bounded grid of approach, crossing and
door departures, uses native Open-RMF interpolation and collision
checks, and reconciles compatible crossing proposals with the native
schedule and negotiation API. It journals the complete policy and
operation receipts. The private verifier independently reconstructs
rest-to-rest motions and checks continuous swept clearance, cabin
capacity and delivery deadlines in all eight histories. It replays
each history in fresh processes, requires identical early authority
across indistinguishable histories and replays previously accepted
receipts after later observations. It also rejects early, stale,
closed-door, wrong-floor, wrong-session and wrong-pose boarding
attempts. [Native package provenance](environment/native-rmf/SOURCES.md) ·
[Open-RMF lift-session workflow](https://github.com/open-rmf/rmf_ros2/issues/382) ·
[Public practice transfer](environment/example/rmf/README.md)

The prototype's independent speed-bounded sampled clearance lower
bound was 22.98–26.08 mm. The integrated verifier derives exact
minimum swept-disc clearance separately. The delivery motion uses an
authored planar layout and physical disc profiles with a time-based
lift service and door/session interface. It does not simulate a
physical cabin mechanism or deploy fleet adapters. The final score
retains 20% of checkpoint 8 and allocates 40% to each complete
contingent facility. Candidate and verifier budgets remain 5,400 s
and 600 s.

The frozen cumulative reference scored 1.0, the no-op 0.0 and the
unchanged checkpoint 8 reference 0.20. The independent verifier measured
27.107 mm minimum swept separation in both facilities. A control that
waited for the first observation before moving scored 0.20. A
point-estimate control that selected crossing authority for the nominal
lift scored 0.60. It passed the first facility and missed the early
relief appointment in the second, even after using the actual carrier
observation. The native direct replay confirmed no continuation for the
nominal commitments in either carrier history of that facility. The
practice transfer, maintained package regression and Harbor task
configuration validation passed locally.

Oddish preflight passed. Oddish accepted v7 with one GPT‑6.2 Sol xhigh
attempt and both controls. [Contingent traffic evaluation](https://www.oddish.app/experiments/64c9c219)

Fresh GPT‑6.2 Sol xhigh scored 0.999986. It passed both facilities and
all eight carrier and lift histories with at least 27.1 mm swept
clearance. Its common approaches began before either observation and
the lift booking preserved the already committed crossings. The retained
priority and FIFO case accounted for the remaining loss. The hosted
reference and no-op scored 1.0 and 0.0.
