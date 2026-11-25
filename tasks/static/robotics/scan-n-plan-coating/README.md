# Scan-N-Plan coating on a rotary cell

A process engineer needs to coat a low-volume part after a fixture change without teaching every arm pose by hand. The proposed application registers the mounted part from calibrated partial scans, plans the arm and positioner together, and finishes a stopped job using the material the cell actually delivered. The work happens in a simulated cell. The application takes CAD, calibrated scans, a recipe, and controller observations and produces an executable trajectory plus a crash-recoverable supervision session.

ROS-Industrial documents using Scan-N-Plan for surface processing, including robotic paint applications. Its ROS 2 workshop exposes reconstruction, raster toolpath generation, and motion-planning services. MoveIt's Pilz planner offers linear and circular paths and blended motion sequences. These are evidence for the workflow and useful planning primitives. The proposed application also has to budget material over a moving surface and reconcile partly completed work after a stop. [ROS-Industrial Scan-N-Plan](https://rosindustrial.org/scan-n-plan) · [ROS 2 workshop architecture](https://ros-industrial-consortium.github.io/scan_n_plan_workshop/architecture.html) · [MoveIt Pilz planner](https://moveit.picknik.ai/main/doc/how_to_guides/pilz_industrial_motion_planner/pilz_industrial_motion_planner.html)

## Implementation status

All four checkpoints package into one cumulative task. The agent image
contains public scan and coating examples with an authored six-axis robot
description. Separate verifier images own the scan cases, arm and
workpiece replay, live inputs, material ledger, and score output. The
local reference and controls qualified against their packaged revisions.
Versions 2 and 3 passed hosted reference and no-op checks. Both used
registration fixtures with a subsequently verified grading defect. The
current local fixtures use corrected scan match distances. Task-quality
ratings are pending.

## Checkpoints

| Checkpoint | Product increment | Substantive work represented |
| --- | --- | --- |
| [Register the part](steps/01-register-the-part/instruction.md) | Estimate the zero-angle part transform across partial camera scans and flag unresolved alignment. | About one day for frame conventions, robust pose fitting, and ambiguity experiments on complementary and symmetric views. |
| [Plan a coating pass](steps/02-plan-a-coating-pass/instruction.md) | Plan a fixed-positioner pass with a predicted dose, usable speed profiles, and clearance. | About one and a half days for path placement, finite footprint and occlusion, material accounting, and interpolation experiments. |
| [Coordinate the positioner](steps/03-coordinate-the-positioner/instruction.md) | Plan a seven-axis trajectory that can coat a return face while the part rotates. | About one and a half days for redundant configuration search, collision-aware timing, and comparison against a fixed or indexed policy. |
| [Resume interrupted coating](steps/04-resume-interrupted-coating/instruction.md) | Recover part-relative dose and finish from measured motion after a scene or permission change and process restart. | About two days for streaming authority, delayed and repeated receipt delivery, durable records, and end-to-end integration. |

The six-day estimate covers substantive engineering and experiments. Faster valid solutions qualify. The four checkpoints are cumulative. Each adds a cell capability, and the earlier commands remain supported.

## Design assessment

| Dimension | Evidence and uncertainty | Next validation |
| --- | --- | --- |
| Novelty | The closest repository pilot, [Workcell trajectory replanning](https://github.com/abundant-ai/swe-marathon-2/blob/10f71b606e0c93494ea01d27b048dfe21f260c09/tasks/swe-m2-software-engineering/workcell-replanning/README.md), already covers changing geometry, braking, and durable commands. Its timed missions grade recovery to a safe motion destination. The new outcome is cumulative treatment over a part surface. Positioner motion moves the keep-outs and surface frame together, and a restart must distinguish commanded travel from measured deposition. [MotionBenchMaker](https://www.kavrakilab.org/publications/chamzas2022-motion-bench-maker.pdf) generates motion-planning queries from robot and scene distributions. It provides a useful geometry comparison. The ROS-Industrial workshop is the nearest workflow comparator and is reusable background for toolpath generation. | Compare more explicitly with SWE-Marathon v1, Deep SWE, Frontier SWE, and Multi-Step SWE before claiming broader novelty. Specific analogues in those collections are unverified. |
| Verifiability | Surveyed transforms, native body poses, actual process samples, and independently accumulated surface dose can be observed. Fixed denominators and an independently computed pass band allow multiple valid trajectories. A dose grid can create artificial boundary effects if undersampled. | Cross-check the integration at finer spatial and time resolutions, and compare two different successful path patterns. |
| Realism | Calibrated partial scans, masked regions, rotary fixtures, blended arm motion, feed limits, and inhibited tools are concrete cell concerns. The published cone model gives the engineer an executable recipe. Real atomization, wetting, curing, and material transfer still need separate measurement. | Have a surface-processing engineer review the recipe inputs, restart messages, and conditions for re-indexing. |
| Difficulty | Stage 1 must distinguish geometric ambiguity from outliers. Stages 2–3 couple surface coverage, continuous clearance, and rate limits across seven axes. Stage 4 must recover the physical history while coordinating fresh measurements, stopping, late transport, and a changed part pose. Greedy IK and nearest-waypoint resume can each produce acceptable local motions that spoil the part. | Measure iteration time with an open-planner baseline and a capable solver before assigning a difficulty rating or reporting GPT performance. |
| Initial feasibility | An authored curved part, one external axis, and a pinned six-axis model support headless CPU execution. Finite surface tessellation and ray occlusion make treatment measurable. The hosted reference passes fixed and coordinated painting, measured-dose recovery, review after re-indexing, and the safe deadline hold. | Requalify new mission combinations and use refined native replays where the dose margin is small. |

## Author-only verification design

The input schema and recipe define the measured outcomes. Author the first fixtures from a simple CAD family with a curved return, narrow mask strips, separate obstacle meshes, and known part poses. Synthesize several independently acquired partial point clouds with documented noise, occlusion, and clutter. Add licensed public meshes only after documenting provenance and pinning their source. Generate private geometric variants that exercise the same disclosed bounds. Start with fixed seeds and no GPU or rendering dependency.

Drive the staged candidate through its published CLI in a fresh separate verifier container. Load models and private case definitions inside the verifier. Run submitted commands with a restricted account and a per-case state directory. The verifier owns the controller, measured trace, and reports. It independently evaluates forward kinematics and continuous clearance against the full arm, the tool, the part, and cell bodies. Evaluate commanded Hermite extrema analytically where possible. Use deterministic native collision queries with conservative subdivision bounds between samples so near misses cannot disappear between controller ticks. For a live mission, a private plant integrates the actuator commands and publishes controller samples and the actual flow separately. A candidate trajectory or reported coverage cannot stand in for those measurements.

| Product requirement | Planned evidence and pass condition |
| --- | --- |
| Consistent registration and safe review | Independently plant a zero-angle transform, generate complementary scans at multiple measured positions, and measure translation norm and relative rotation angle against the job tolerances. Include a symmetric part whose supported alternatives differ by more than those tolerances. Check the report schema, valid review, and unchanged output on malformed input. |
| Usable fixed-positioner plan | Time an actual pass from its declared start and replay the interpolated motion. Check the configured angle, continuous clearance, joint bounds, derivative extrema, the duration, stopped finish, and the recipe window whenever spray is enabled. A curved positive job has sufficient qualifying area and acceptable off-target volume. A masked or blocked job has an independently demonstrated infeasible region. |
| Coordinated progress | Require a physical pass over a return face for which the fixed-angle job cannot achieve the required area. Exercise different feasible rotary directions or arm branches, including a fixture whose sweep would intersect a naïve shortest path. Independently reconstruct the instantaneous part, fixture, and world frames from both sets of joint positions. Apply the same dose and safety checks and verify the final stopped positioner angle. |
| Measured-material recovery | Apply an independently triggered tool inhibition or scene revision after actual deposition begins. Reverse receipt delivery where reasonable, repeat a receipt, and omit one temporarily. Observe timely stop, fresh evidence, and reconciliation before replacement. Re-index in a second positive mission and replay the finished part from receipts stamped under each earlier registration. Include an unrecoverable case with a safe stop and no further material. |
| Durable authority and error handling | Kill the worker after a state commit and before delivery of a reply. Check exact replay, one logical motion per command ID, preserved history, and responses under equivalent receipt order. Conflicting receipt content, sequence errors, and malformed records leave prior state and the existing output usable. |

Integrate the declared cone over a verifier-owned, area-weighted surface subdivision and the measured controller trace. Compute visibility and dose independently of the planner, with a finer time and space grid than the controller. Compare the area within the job's inclusive dose range with its total target area and integrate off-target volume in millilitres. Calculate interpolation, clearance, and dose errors on both sides of threshold before freezing fixtures. Cases near unresolved numerical boundaries need more margin or a better reference calculation. Transferring the measured dose to real coating thickness would require separate calibration.

### Reward

Use fixed case groups for registration, fixed-positioner execution, coordinated execution, and live recovery. Within a group, score the fraction of its named cases that pass after at least one positive case in that group succeeds. Safety or invalid process authority fails the affected case, even when final coverage looks good. Missing or malformed candidate output fails the affected case. A verified evaluator fault invalidates the trial. Keep individual registration errors, motion evidence, surface dose metrics, and protocol findings in the report.

The cumulative score is the weighted mean of available groups with weights **1, 2, 3, and 6**. The final two groups account for 75% of the final score. A candidate that solves only the first two products would score at most 0.25 at the last checkpoint. Success thresholds for the continuous metrics come from the public job values. The current case counts are seven, four, eight, and eight, in checkpoint order.

### Reference and qualification

A plausible reference starts with robust multi-capture rigid registration against the mesh, supported by bounded multistart search around the commissioning seed. For coating, subdivide the target into overlapping passes, enumerate reachable tool rolls and several positioner angles at each waypoint, and search for a continuous configuration sequence. Joint-space planning handles approach and departures. Retiming enforces the active recipe and motion limits. A part-frame dose ledger accumulates observed intervals by command ID, with scene and registration snapshots fixed when each command issues. On restart, use the residual dose and measured halted state as the new planning input. This is a solution hypothesis. Preserve the freedom to use another surface planner, motion planner, or dose representation that meets the contract.

Before hosted testing, qualify the current package with a complete reference and no-op in a fresh isolated environment. Use at least two independently generated positive missions at each new stage and supported blocked cases. Repeat cases with the same seeds and measure runtime, numerical margin, and replay stability. Include legitimate alternative coating paths so the checks do not select one algorithm. Reject endpoint-only clearance, false completion from negligible flow, fixed invisible transforms, coverage inferred from planned motion, duplicate receipts counted twice, and unqualified reruns of a full pass after a stop. Record each model trial with its exact task version in the development log.

## Hackability assessment

| Severity | Documented risk | Planned evidence and mitigation |
| --- | --- | --- |
| YELLOW / UNASSESSED | A submission could claim coverage or completion without material transfer, clip a forbidden face between samples, or accept a duplicate interval after a restart. | Measure flow and interpolated motion in the verifier, re-integrate dose over off-target surfaces, and test deliberate shortcut controllers. Calibration of sampling error and threshold margins remains pending. |
| YELLOW / UNASSESSED | A submission could try to read private fixtures, leave stale state across retries, or substitute a reward file or process report. | Keep case inputs and reward in the trusted container, stage only the declared candidate application, and verify real account privileges, mounts, process handling, file types, and network policy before any hosted trial. |
| YELLOW / UNASSESSED | Fixed fixture names, geometry patterns, surface discretization or convenient schedule constants could identify particular cases. | Generate translated, mirrored, and separately tessellated variants with observed outcomes. Preserve the physical recipe for each variant and measure stability against independent integration. |

## Development log

### 2026-11-25

Drafted four candidate contracts and a proposed independent verifier. Checked the ROS-Industrial Scan-N-Plan workflow, MoveIt Pilz interface, MotionBenchMaker comparison, and the repository workcell pilot. The current evidence supports the use case and the proposed measurements. Robot and scene assets, packaging, verifier, executable reference, failure controls, Harbor review, ratings, and model trials are pending.

An independent midpoint integration on an unobstructed plane recovered
12.00178 mL/s from a 12 mL/s source (0.0149% error). The nozzle stood
0.20 m from the plane with a 25° cone half-angle. This confirms the
analytic dose normalization for that geometry. Coordinated motion,
occlusion and recovery still need native tests.

#### Registration and motion pilots

Added the released registration checkpoint, separate verifier image and
reference CLI. The released environment includes a calibrated multi-capture
example and a planar example with two supported part translations 30 mm apart
against a 6 mm tolerance. The public examples returned registered and review
respectively. The seven private CLI cases check two recovered mounts, exact
rotational symmetry, empty observations, and three invalid inputs. The
verifier checks that a complete valid report replaces the prior file and that
malformed input preserves it.

Before freezing the cases, two nominal positives admitted distinct rotations
under the original 4.5 mm scan bound and 84% per-capture support threshold.
Archived witness pairs were 0.0658 and 0.0701 rad apart, above the published
0.064 rad usefulness tolerance. Changing the fixture recipe to 2.8 mm and
86% preserved the positive mounts and the true symmetric case. An independent
search of 1,581 out-of-tolerance poses per positive found none consistent.
This search does not establish global uniqueness. The saved evidence is in
`experiment/registration-final-20261125.R6rQpf/`.

The exact extracted bundle scored 1.0 for the reference and its equivalent
antipodal-quaternion version. A no-op, an application that always requested
review, and a valid registration that overwrote the report in place each
scored 0.0. Oddish preflight returned no findings. This was local execution
under Python 3.12 with NumPy 2.2.6 and SciPy 1.15.3. The Docker-backed
`harbor check` attempt timed out before producing a completed review.
Its diagnostics are under `experiment/registration-release-20261125.L79jOq/harbor-review/`. Task-quality ratings await a completed review.

Added a Hermite extrema check, interval clearance proof, and independent
part-local dose ledger. With MuJoCo 3.3.7 and Python-FCL 0.7.0.11, the
fixed-positioner witness placed 94.7% of the curved target in the requested
dose band, deposited 0.218 mL off target against a 0.30 mL limit, and certified
continuous clearance above the requested margin. The lowest queried
separation was 29.8 mm. The dry and late-spray controls failed. The
trajectory and evidence are stored in `experiment/fixed-pass-witness-20261125.k4UxPk/`. Native
kinematics were evaluated under ideal tracking. The clearance proof assumes
an exterior starting pose and checks triangle boundary separation. An independent
ribbon planner then produced valid passes in both directions from the
public job, registration and URDF. Finer integration gave 96.77% coverage
and 0.245 mL off-target dose on the 2.06-second plan. A thin inserted
obstacle kept every serialized knot clear but collided between knots.
The swept verifier rejected it. Those controls are preserved with the
fixed-positioner evidence.

The coordinated witness turned the positioner at 0.28 rad/s while the
arm moved. The independent native audit qualified it at 94.71% coverage,
0.218 mL off-target dose and 19.0 mm minimum sampled clearance. Freezing
the part during spray and indexing to the same final angle afterward
produced 0.374 mL off-target dose and failed the process window. This
comparison holds the arm and flow commands fixed. Feasibility of every
possible fixed-angle path remains unassessed.

Split the measured coordinated trace into three receipts. Delivering the
first and last out of order, including a repeat, left the motion unsettled
until the middle receipt arrived. The reconciled ledger produced identical
dose and process evidence to the full trace. See
`experiment/coordinated-pass-witness-20261125.CGB1Gc/offline-audit.json`. The interrupted
closed-loop supervisor, held-out process suite, and hosted model trials
remain to be qualified. Repository checks, 31 CI and author pytest checks,
and 18 local physics and receipt regressions passed.

#### Four-checkpoint local qualification

Packaged the fixed and moving coating planners. Each group includes two
physically achievable curved jobs, a provably unreachable target, and a
registration identity mismatch. The moving fixtures cannot spray at their
starting angle under the public reach, orientation and standoff limits.
The reference used opposite rotary directions on the two jobs. Fine
independent replay with 2.5 ms samples and 2.5 mm surface cells gave 96.5%
to 99.0% target coverage for the four positive passes. Each passed continuous
clearance and its own dose limits. The reference covers connected smooth
ribbons. Disconnected raster regions and richer detours are outside the
verified reference family. The initial three-step release is stored in
`experiment/process-release-20261125.cE7r9Q/`.

The live driver independently revoked the valve during physical deposition
and accepted a bounded brake. It delayed one receipt, repeated another,
supplied a stale stopped reading, and restarted the supervisor before
testing the next accepted request. The reference persisted its command
identity and completed all three recovery missions. The runs included
a remount and a different part with reversed rotary travel. Recovery
finished at 4.18, 4.60, and 7.40 simulated seconds, with 96.0%, 96.0%, and
97.6% target coverage. The deadline case ended safely with 35.9% coverage.
The reference takes the issued sweep as a warm start, derives the remaining
work from measured flow, and tries a collision-certified dry bridge and
adjusted suffix. It can fall back to a new geometric search.

The reversed live case exposed a spurious zero in MuJoCo's cylinder
distance query. Independent containing boxes placed the implicated turret
and wrist shapes at least 0.3797 m apart. An FCL query measured 0.4355 m of
separation. The verifier now uses a certified lower bound when a native
query contradicts disjoint containing boxes. An exact-pose regression
covers that discrepancy, and the true penetration and between-knot
collision controls still fail as expected. The reverse fault trigger is
below the minimum possible qualifying deposited volume so a valid,
efficient pass cannot finish before the fault opportunity.

The full 111-file bundle passed all 19 local case checks. The reference
scored 1.0, the offline-only application scored 0.5, and the no-op scored
0.0. Oddish preflight returned no findings. The repository checks,
33 CI and author pytest checks, and 19 native physics and receipt
regressions passed. The release inventory and raw evidence are under
`experiment/full-process-release-20261125.RdJaca/qualification.json`. A new Harbor review
attempt timed out without a completed report. GPT-6.2 Sol xhigh had a
failing health status in the read-only Oddish catalog at this check.
Fresh hosted model difficulty remains unmeasured.

#### Stop when moving controller evidence expires

The first recovery mission now withholds new controller readbacks during
spray. The driver checks the braking envelope at the future fault tick
before advancing the plant. It then delivers the last reported moving
sample at an age of 60 ms against a 40 ms limit, with spray permission
still enabled. The reference stopped at 1.10 s and finished at 4.14 s
with 96.0% target coverage and 0.220 mL off-target dose.

A control that skipped the freshness check for an active command passed
all four live missions in the preceding release. The revised mission
rejects that control while the command is still running. A focused
regression keeps a 40 ms readback valid and requires a stop when the same
sample reaches 60 ms. The live group still contains three recoveries and
one deadline-constrained hold.

The packaged native reference scored 1.0 across all 19 cases. The control
scored 0.875 and failed only the stale-running mission. The no-op scored 0.0
against a fresh build of the revised package. All seven coating author
checks and 19 native physics and receipt regressions passed. The package
manifest, no-op result, and qualification evidence are in
`experiment/active-readback-expiry-20261125/`.

Oddish preflight passed. Oddish accepted the exact revision as version 1
with one GPT-6.2 Sol xhigh trial gated by the reference and no-op. The
local manifest digest is
`1221337d6e3c61b57b8ffd5021fbdc2e39b099e1e26d4b7e6160bad5c5af96bc`.
[Stale-readback experiment](https://www.oddish.app/experiments/0c48c409)

The hosted reference scored 0.0 before any coating commands ran, and
Oddish skipped the model trial. The artifact manifest shows that the
launcher and its modules were collected. Restoring the same launcher
bytes locally as mode `0644` reproduces the missing-executable result.
The verifier now restores execute permission on that validated regular
file before launching it as the restricted candidate account. The
maintained test exercises the launcher after transfer and rejects a
symlink at the same path. The hosted logs do not record the restored
mode.

Packaged version 2 passed all 19 reference checks after restoring the
launcher from mode `0644`. The no-op scored 0.0. Oddish accepted the
replacement experiment with the same baseline gate and one GPT-6.2 Sol
xhigh trial. Its local manifest digest is
`df8453c76916f45e480254e29d2c0b34654a82d1cc9fa71ebecd90bc6422ca12`.

The replacement's hosted reference passed all 19 checks and scored 1.0.
It stopped on the same 60 ms controller reading while spray permission
remained enabled. The hosted no-op scored 0.0. Both results released the
GPT-6.2 Sol xhigh trial. The downloaded reference checkpoint is in
`experiment/active-readback-expiry-20261125/launcher-mode-revision/`.
[Replacement experiment](https://www.oddish.app/experiments/58362963)

GPT-6.2 Sol xhigh finished that version at 0.9167, with cumulative
checkpoint scores of 0.0000, 0.6667, 0.8333, and 0.9167. Both positive
registration fixtures required a registered pose and received a different
status. The model passed the review and invalid-input checks, all eight
offline motion checks, and all four live checks. The latter groups took
trusted registration reports as inputs, so the registration failures did
not prevent those checks from exercising the planner and supervisor.
The hosted result and individual verifier outputs are archived in
`experiment/active-readback-expiry-20261125/launcher-mode-revision/hosted-gpt/`.

An independent geometry audit found two admissible poses in each of
those positive cases. The pairs differ by 0.06820 rad and 0.06556 rad,
both above the 0.064 rad ambiguity limit. Every capture supports each
pose at the published 2.8 mm distance and 86% inlier requirements. The
verifier should have accepted review on these inputs. Task version 3
uses the same registration fixtures and shares the grading defect.
The independent pose pairs, support fractions,
and reproducer are in `experiment/registration-ambiguity-audit-20261125/`.

The two cases now use scan match distances of 2.2 mm and 2.4 mm,
respectively. The surveyed poses retain at least 87.68% and 87.69%
support over all captures. Both old pairs fail consensus at their new
distances. The reference returns supported poses in under 19 s per case
with the existing seed search and useful-pose limits. A bounded repeat
search found rotation separations up to 0.04596 rad and 0.04938 rad, and
translation separations up to 4.40 mm and 3.36 mm. The exact capture
margins and CLI outputs are in `experiment/stage1-capture-correction-20261125/`.

#### Hold for re-index registration review

The +0.055 rad remount mission now sends a `review` report with a null
pose while the verifier measures clearance at the actual new mounting.
It reconciles the pre-interruption receipts and restores spray permission.
The supervisor cold-restarts with fresh stopped feedback and must hold
for six 20 ms observations before it receives the confirmed pose. It can
then replan using the dose delivered in the original mounting.

A matched control that retains the old pose during review passed the
plain remount. It requested motion at 1.46 s in the new case, and the
verifier stopped it before execution. The reference waited for the
confirmation and finished in 4.72 s with 96.00% target coverage and
0.221 mL off-target dose. In the exact local package, the reference
passed all 19 checks, the cached-pose control scored 0.875 with only
this case failing, and the no-op scored 0.0. The package manifest and
results are in
`experiment/registration-review-recovery-20261125/qualification.json`.

#### Replan around a clamp introduced during motion

In a separate prototype, a new scene revision introduced a clamp at
1.06 s while the controller feedback was fresh and spraying was permitted.
The original plan would have reached the clamp by 1.64 s. The measured brake
profile cleared it. A control that ignored the world revision left the
original motion active, and the verifier rejected that response.

An experimental reference resumed by shifting the arm and positioner
0.16 rad together around the positioner axis. This kept the spray relative
to the part while moving the arm away from the clamp. The independent
replay finished in 4.14 s with 96.00% coverage, 0.221 mL off-target dose,
and a 17.31 mm minimum sampled clearance against a 13 mm limit. The
witness and controls are in `experiment/moving-world-revision-20261125/`.

The first packaged clamp recovery ran as the fifth live check. The verifier
deploys the clamp only when the measured pose and configured brake
clear the incoming scene. It checks earlier motion against the original
scene and braking against the new one. The original command still owns
its receipts. A separate native control delayed deployment from 1.06 s
to 1.40 s so the clamp could clear the arm.

The packaged reference passed all 20 checks and scored 1.0. The
scene-blind control scored 0.90 and failed only the clamp case. The
no-op scored 0.0. A control that stopped and acknowledged the new
revision, then reused the original sweep, also failed clearance before
the replacement motion ran. The exact package and native controls are
documented in `experiment/world-scene-recovery-20261125/qualification.json`.

#### Recover from two interruptions on the same part

The first two-interruption case changes the scene during a wet pass, then
revokes spray permission after the replacement motion has deposited
more material. The clamp stays in place when the stopped part is
re-indexed. The supervisor receives a receipt from the first stop again
while reconciling the second. It must preserve both deposition histories,
hold while registration is under review, and use the confirmed pose for
the last pass. The two stops belong to different motions, and each batch
of receipts stays under the scene in which its motion was issued.

The one-stop control finished the matched clamp-only mission with 96.00%
coverage in 4.12 s. With a second interruption scheduled, it resumed
coating after the clamp and failed to stop on the later revocation. That
control changes only the stop guard from per-motion to per-job state.
The matched replays are in `experiment/two-interruptions-20261125/`.

On the exact new package, the reference stopped at 0.94 s and 2.24 s,
held through six registration review packets, and finished in 5.90 s.
The measured finish had 96.00% coverage, 0.221 mL off-target dose, and
17.31 mm minimum sampled clearance against a 13 mm limit. The reference
passed all 20 checks and scored 1.0. The one-stop control scored 0.90
and failed only on the second revocation. The no-op scored 0.0. Oddish
preflight passed. The bundle manifest and measurements are in
`experiment/repeated-recovery-package-20261125/qualification.json`.
The hosted GPT trial uses the earlier stale-readback package.

#### Recoat a patch missed during pump priming

A separate native probe held measured flow at zero for the first 200 ms
of commanded spray. The resulting gap represented 0.212 mL of missing
flow. A repair witness used the measured receipts to recoat the missed
patch and finish the uncoated tail, with spray off over the completed
middle. It finished in 5.66 s with 96.63% coverage, 0.221 mL off-target
dose, and 19.30 mm minimum sampled clearance.

The same repair code with nominal instead of measured prefix accounting
reported completion at 83.83% measured coverage, below the 88% requirement.
It passed the steady-pump control at 96.00%. The maintained reference
at the time timed out on the priming case. The initial probe is archived
in `experiment/pump-prime-loss-20261125/`.

The sixth live mission now arms its priming delay on the first permitted
wet command. A dry approach previously let the motion reach the same
wet pose with no priming loss. A controller regression replays that
approach and verifies the deficit and recovery in the measured receipts.
The reference extracts missed intervals from those receipts, reuses
the old geometry where it qualifies, and checks clearance, remaining
time, and cumulative dose before executing the repair.

On the packaged priming revision, the reference passed all 21 checks
and measured 96.63% coverage on this mission. The nominal-prefix control
missed only the priming case and scored 0.917 overall. It claimed
completion at 83.83% coverage after the same 0.212 mL suppression. The
no-op scored 0.0. The package manifest and controls are in
`experiment/pump-prime-package-20261125/qualification.json`.

In a separate native replay, the 200 ms loss occurred after spray had
already delivered 0.15 mL. The interrupted motion had eight wet ticks
before the gap and 23 after it. The same reference finished at 96.00%
measured coverage in 5.52 s. The nominal-prefix control claimed
completion at 82.08% coverage. This variant is an author probe in
`experiment/pump-midpass-dropout-20261125/`.

#### Coordinate about an inclined positioner bearing

The coordinated group adds a flange whose bearing is pitched 0.225 rad
(12.9°) around its local Y axis. The part and fixture keep their
commissioned physical poses at the original 0.23 rad process angle.
The arm must track the part around the calibrated bearing while spraying.

The local reference finished in 4.88 s with 97.84% coverage, 0.290 mL
off-target dose, and 18.39 mm minimum reported clearance. A matched
controller kept the calibrated pivot but rotated around world Z. It
passed the upright fixture and failed the inclined one with 84.30%
coverage, 0.523 mL off-target dose, and 66 spray samples outside the
recipe limits. The witness and matched controls are in
`experiment/inclined-positioner-20261125/`.

The combined inclined-axis and priming package passed all 22 checks
with the reference, for a score of 1.0. The no-op scored 0.0 and Oddish
preflight passed. The exact manifest and cumulative results are in
`experiment/inclined-prime-package-20261125/qualification.json`.

Oddish accepted that exact bundle as task version 3. The sweep includes
one hosted reference, one no-op, and one GPT-6.2 Sol xhigh run on the
same initial backend as the earlier sweep. The solver is gated on the
hosted controls. [Inclined-axis and priming experiment](https://www.oddish.app/experiments/8abb3c7a)

The hosted reference passed all 22 checks and scored 1.0. The no-op
scored 0.0. The downloaded final verifier report is in
`experiment/inclined-prime-package-20261125/hosted-reference-checkpoint.json`.

GPT-6.2 Sol xhigh finished at 0.6667. It passed all four fixed and five
coordinated checks, including the inclined-axis job. It passed three of
six live checks. Two failed after six registration review packets and
before a plan under the confirmed registration. The candidate treated the
confirmation as a re-index, which requires disabled spray and a new
capture epoch in its implementation. The evaluator reused the review
epoch and sent the confirmation after restoring permission. The Stage 4
description leaves this transition open to both readings. The zero
registration component includes the two known ambiguous fixtures. The
checkpoint evidence and model trajectory are in
`experiment/inclined-prime-package-20261125/hosted-gpt/`.

The partially primed job exposed a separate runtime failure. The exact
submitted source reached the same stopped controller packet in a local
replay and entered synchronous recovery planning. It was still enumerating
motion hypotheses when the 90 s request limit elapsed. The stopped record
had 0.220 mL of priming loss and 35.55% qualifying coverage. The missed
leading region and the untouched trailing region straddled the coated
middle. The reference completed the physical job in 5.66 s of simulated
time at 96.63% coverage. The replay and timing are in
`experiment/inclined-prime-package-20261125/hosted-gpt/priming-replay/`.

#### Recover from reduced flow while the nozzle is still wet

A separate native probe reduced pump output to 25% of its steady level
for 200 ms after initial deposition. The held samples all showed positive
flow during the drop, with 0.159 mL less delivered than at steady gain.
The existing packaged reference returned no valid post-stop reply.
An author witness estimated the normal gain from reconciled receipts,
filled the partial deficit, and checked the repair against measured
remaining dose, clearance, and time. It finished in 5.48 s with 96.00%
coverage and 0.221 mL off-target dose. With the same repair code, a control
that treated the painted prefix as continuous claimed completion at
85.55% coverage, below the 88% requirement.

The witness also passed a later 200 ms drop to 35% output at 96.00%
coverage. These are the author probes used to design the pressure-loss case.
The replay, controls, and matched receipts are in
`experiment/pump-positive-sag-20261125/qualification.json`.

The new live case reduces flow after 0.15 mL has been measured. The
pump recovers after the commanded spray has accumulated a 0.16 mL
delivery deficit. Dry waits and changes of command leave the remaining
deficit intact. The held receipt samples expose the reduced flow. The
reference estimates steady gain from the positive observations and
repairs the missing quantity while protecting the already-coated region.

The targeted native replay measured eleven reduced-flow intervals and
the full 0.16 mL deficit. The reference finished in 5.48 s at 96.00%
coverage. The nominal-prefix control claimed completion at 85.38% and
failed the physical dose check. Both exact reports are in
`experiment/pressure-deficit-maintained-20261125/`.

The corrected combined package passed all 23 checks with the reference
scoring 1.0 and the no-op 0.0. The nominal-prefix control passed 21 of
23 checks and scored 0.8571. Both failures were in the priming and
pressure-loss missions. Oddish preflight passed. The manifest and raw
cumulative results are in `experiment/pressure-registration-package-20261125/qualification.json`.

An author replay combined the pressure loss with the clamp deployment
and later remount from the two-stop mission. The reference made both
stops, held through all six registration review packets, and finished
in 7.86 s against an 8.4 s deadline. It achieved 96.00% coverage, 0.221 mL
off-target dose, and 17.31 mm minimum sampled clearance. The matched
nominal-prefix control also completed both recovery sequences and
failed the measured dose check at 85.38% coverage. The current
two-interruption check uses this composed case. The targeted replays
are in `experiment/composed-pressure-recovery-20261125/`.

The exact package with the composed case passed all 25 checks with the
reference and scored 0.0 with the no-op. The nominal-prefix control
passed 22 checks and scored 0.7857. It failed the composed case, the
priming case, and the stand-alone pressure-loss case. The manifest and
full evidence are in `experiment/composed-split-package-20261125/qualification.json`.

#### Carry a measured registration into planning

A separate feasibility probe ran the registration command on five
independently ray-cast depth views of the fixed-positioner flange.
The solver returned review. A second pose 29.05 mm from the surveyed pose
had at least 88.76% support in every capture, above the 86% floor and
beyond the 14 mm useful translation tolerance. Tilting the cameras toward
the two flange ends reduced the same alternate pose's support to 53.93%
in its least-supported capture. The full end-view solve exceeded the
75 s registration subprocess budget. The rendered inputs and explicit
pose pair are in `experiment/scan-to-coating-20261125/`.

#### Coat two patches separated by a mask

An author Stage 3 case divides the moving flange into two coating
patches with a 70.35 mm mask between them. The split pass turned the
positioner through 0.1584 rad while crossing the mask dry. Refined
native replay found 96.76% coverage on each patch and 0.278 mL off-target
material. Continuous spray on the same Hermite motion used 0.656 mL
off-target against a 0.36 mL limit. The current reference reported the
job as blocked. The case and independent physical comparison are in
`experiment/disconnected-coating-patches-20261125/qualification.json`.

Shifting the same mask four mesh columns along the flange produced
unequal target patches. The larger patch covers only 78.57% of total
target area, so both patches must be treated to meet the 88% rule.
Reusing the centered fixture's valve timing on the same joint motion
reached 69.64% coverage and emitted 0.568 mL off-target. The independent
offset-mask replay derives a dry crossing from the supplied mask and
qualifies. Its results are in
`experiment/disconnected-patch-offset-20261125/qualification.json`.

Both fixtures are coordinated-plan checks. The reference fits the guide
from observed target sections and checks the first nozzle hit at
multiple times in each held-flow interval. It keeps spray off during
mask traversal. Subdividing the trajectory to change held flow keeps
the collision-checked Hermite positions and rates. Refined native
replay qualified the maintained reference in 4.88 s on both layouts.
It coated 98.44% and 98.07% of the target areas and used 0.306 mL and
0.292 mL off-target. Each individual patch exceeded 96% coverage.

The exact split-patch package passed its two targeted Stage 3 CLI checks
and all 25 cumulative checks with the reference. The single-ribbon
reference from the previous corrected package passed the other 23
checks and reported both masked-patch jobs as blocked, for a score of
0.9286. The no-op scored 0.0. Oddish preflight passed. The manifest and
full results are in `experiment/split-pressure-package-20261125/qualification.json`.

Oddish accepted the corrected 25-case package as version 4. The run
includes one hosted reference, one no-op, and one GPT-6.2 Sol xhigh
trial gated on the baselines. [Corrected split-patch experiment](https://www.oddish.app/experiments/144d266a)

The hosted reference passed all 25 checks and scored 1.0. The hosted
no-op scored 0.0. The downloaded reference report is in
`experiment/split-pressure-package-20261125/hosted-reference-checkpoint.json`.

GPT-6.2 Sol xhigh scored 0.0833. Registration passed seven of seven.
Every positive fixed and coordinated planning invocation exited with
status 1 before producing a plan. The seven live missions stopped on
their first packet with no commands or material delivery. The application
shipped a prebuilt registration library and tried to compile its coating
geometry helper with `cc` at first use. The verifier image installs the
pinned Python dependencies and has no C compiler. The score captures a
deployment failure before the physical missions could run. The exact
checkpoint reports and module sources are in
`experiment/split-pressure-package-20261125/hosted-gpt/`.

In isolated replays of the same final application, removing `cc` reproduced
the launch failures and adding it let the application issue the first live
motion. With the compiler available, one fixed flange and one coordinated
masked-patch job passed independent replay at 92.98% and 96.23% coverage.
The masked-patch trajectory covered two separated wet spans and moved the
positioner through 1.99 rad. The tests and diagnostic copies are in
`experiment/split-pressure-package-20261125/hosted-gpt/compiler-replay/`
and `experiment/split-pressure-package-20261125/hosted-gpt/first-packet-replay/`.

#### Recover across a masked gap after pressure loss

An author replay used the unequal-patch job in live recovery. The pump
lost 0.16 mL before pressure recovered. An expired controller readback
stopped the first pass before the mask, and a later permission loss
stopped the next pass for re-indexing. The reference held through six
registration review packets and finished in 9.60 s with 89.78% measured
coverage, 0.240 mL off-target, and 19.20 mm minimum sampled clearance.
Both stop thresholds are below the 0.524 mL lower bound on delivered
material for a qualifying finish. The nominal-prefix control issued the
same plans and achieved the same coverage. A second matched control
discarded every positive underdelivery hint and produced the same
result. The first resumed motion followed the original wet tail after a
1.70 s dry bridge. The traces and controls are retained as a feasibility
probe in `experiment/combined-split-pressure-remount-20261125/`.

#### Coat two plates at different heights

An author case mounts two closed curved plates 125 mm apart in height.
The recipe requires at least 69.71 mm of nozzle height change between
legal hits. A 3.04 s dry reposition joins the two coating sweeps. The
refined replay finished in 9.96 s at 97.83% coverage and 0.584 mL
off-target material. The matched lower-only pass retained clearance and
failed at 48.92% coverage. The authored job extends the shoulder lower
bound to −0.95 rad within the installed limit and assigns a 0.72 mL
budget across two plates. The exact models and replay are in
`experiment/dual-height-patch-witness-20261125/`.

The coordinated verifier now includes this carrier. The part and both sets
of jaws rotate together. The requested start index cannot reach either
coating band, even with the wider shoulder envelope. The normal process
checks measure coverage and off-target volume across both plates. The
candidate can choose the pass order and transition path.

The maintained reference finds the two connected face sets, plans the
second approach from the first stopped arm state, and accounts for material
in the full scene. In the refined native replay it finished in 8.98 s,
covered 98.29% of the target area, deposited 0.609 mL off-target, and kept
19.17 mm minimum sampled clearance with no off-recipe samples. The previous
reference timed out at the 110 s planning limit on this same case. The
replays are in `experiment/stacked-flange-package-20261125/`.

The live verifier now supplies an empty writable state directory before the
first request and reuses it after restart. The job fixture uses paths under
`/app/examples/cell`. These fixes address two findings from the hosted
review of version 3. The transport regression uses a candidate that writes
directly into the supplied directory.

#### Confirm the remount with a follow-up capture

The live verifier still sends six fresh stopped observations while the
first remount capture is under review and permission is available. It
installs the confirmed pose from a separate capture while spray is disabled.
The next controller observation restores permission. This preserves the
hold and receipt checks and gives both reports distinct capture epochs. The
verifier also distinguishes a rejected packet from an absent or malformed
reply in the case evidence. The package changes and replays are in
`experiment/confirmed-capture-release-20261125/`.

The revised reference passed all seven live cases. The isolated remount
finished in 4.74 s. The combined pressure loss, clamp, and remount finished
in 7.88 s of its 8.4 s budget. Both finished with 96.00% measured coverage.
The packet record verifies six review holds, a fresh stopped confirmation
with permission disabled, and restored permission on the next reading.

In a matched replay with the exact version 3 GPT application, the isolated
remount kept its original geometry, interruption, and 5.6 s deadline. With
the corrected exchange, the application accepted the confirmed capture,
issued a plan when permission returned, and finished in 4.94 s with
97.12% coverage and 0.229 mL off-target. This isolates the original failure
of that case to the registration handoff.

Oddish accepted the stacked-flange and corrected-capture package as task
version 5. The hosted sweep has one GPT-6.2 Sol xhigh trial gated on the
reference and no-op. The exact bundle and submission record are in
`experiment/confirmed-capture-release-20261125/`.
[Stacked-carrier evaluation](https://www.oddish.app/experiments/eadb3c51)

The exact version 5 bundle passed all 26 cumulative checks with the local
reference and scored 0.0 with the local no-op. Oddish preflight passed.
The hosted planner, stacked fixture, and live verifier files matched the
local bundle byte for byte. The local report is in
`experiment/confirmed-capture-release-20261125/qualification.json`.
The hosted reference passed all 26 checks and scored 1.0. The hosted
no-op scored 0.0. The downloaded report is in
`experiment/confirmed-capture-release-20261125/hosted-reference-checkpoint.json`.

GPT-6.2 Sol xhigh scored 0.8348. It passed all registration and fixed-pass
checks, five of eight coordinated checks, and six of seven live checks.
It reported both split-mask jobs blocked and timed out on the stacked
carrier. In the pressure-loss, clamp, and remount mission, the application
delivered coating and stopped safely, then gave no reply to the first
reconciled restart packet. The isolated remount, priming-only and
pressure-loss-only missions passed. Further hardening should exercise
disconnected targets and recovery when physical and process faults occur
in the same mission. The per-checkpoint reports are in
`experiment/confirmed-capture-release-20261125/hosted-gpt/`.

The saved planner fits one centerline over all target faces and requires
a target hit at each station. Across its 12 combinations of inset and
station spacing, neither masked fixture produced a usable curve. Every
stacked-carrier curve crossed the gap between the bands. The geometry
replay is in the `coordinated-inspection/` subdirectory.

A separate live pilot stopped the stacked carrier after partial work on
the lower plate. The maintained supervisor resumed from the measured stop
and completed both plates. Paired 0.16 mL and 0.30 mL pressure-loss probes
also passed with a nominal-prefix control. It issued the same trajectories
as the measured-flow supervisor in each pair. These trials establish
feasibility for a future live stacked-carrier case. The replays are in
`experiment/stacked-live-stop-feasibility-20261125/`,
`experiment/stacked-live-pressure-sag-20261125/`, and
`experiment/stacked-live-pressure-sag-edge-20261125/`.

#### Repair separate coating losses within one pass

A process pilot combines delayed priming with a later period of reduced
positive flow on the standard curved flange. The matched plans request
the same initial motion and valve settings. The plant withholds 0.212 mL
during ten priming periods, returns to steady flow, then loses another
0.160 mL during eleven pressure-limited periods. Independent raycasts
place the losses on separate surface regions. Both runs stop at 1.42 s
after 0.665 mL of measured emission.

The reference repaired both regions in 5.88 s of a 6.4 s job, with
96.63% coverage and 0.221 mL off target. The nominal-prefix controller
continued from the planned prefix and reported completion with 73.28%
coverage. The native verifier rejected that result. The measured flow
and native replay are in `experiment/curved-flange-prime-plus-pressure-20261125/`.
The next local revision uses the two faults in one live check in place
of the standalone positive-flow sag. The earlier priming-only check
continues to identify that simpler recovery failure.

The exact local bundle passed all 26 cumulative reference checks. The
no-op scored 0.0. An isolated replay through the packaged controller
reproduced the combined fault measurements and the control failure.
The manifest and reports are in `experiment/combined-pump-release-20261125/`.

The agent image and each verifier image now install the same C compiler
and headers. The runtime resource guide documents how to use the writable
temporary directory or ship a compiled artifact. A local smoke test built
and loaded a shared C library there. The compiler-enabled package uses the
same planner, fixtures, and verifier as the locally qualified two-fault
bundle. The image changes and byte comparison are in
`experiment/pump-recovery-compiler-release-20261125/`.

Oddish accepted the compiler-enabled two-fault bundle as task version 6.
The sweep gates one GPT-6.2 Sol xhigh trial on the hosted reference and
no-op. [Compiler-enabled pump recovery evaluation](https://www.oddish.app/experiments/eaf531a1)

The hosted reference passed all 26 checks and scored 1.0. The no-op
scored 0.0. The hosted two-fault replay matched the local result at
96.63% coverage and a 5.88 s finish. The report is in
`experiment/pump-recovery-compiler-release-20261125/hosted-reference-checkpoint.json`.

The staged GPT-6.2 Sol xhigh run scored 0.7738. It passed all four fixed
and all eight coordinated checks, including the stacked carrier, and five
of seven live checks. Two positive registration cases failed. The
isolated remount-review and combined clamp-remount missions stopped safely
and then received no reply during recovery. The final staged verifier
report is in `experiment/pump-recovery-compiler-release-20261125/gate-audit/`.

An isolated replay used the exact saved version 4 GPT application with
the compiler available. It ran through both pump faults, stopped, and
held for delayed receipts and stale feedback. At the fresh stopped
restart packet it had 36.24% coverage and 2.40 s left in the physical
mission. It produced no valid reply or replacement motion. The native
trace is in `experiment/combined-pump-release-20261125/hosted-v4-cc-probe/`.

#### Prepare a common model execution format

Proximus uses one agent session. The comparison bundle presents the four
briefs together and retains the exact final reference and cumulative
verifier. Its task identity and trial sequence are separate from the
multi-step runs. Oddish preflight passed, and the reference and no-op were
submitted to qualify the shared format. The package manifest and trial
records are in `experiment/single-session-screening-20261125/`.
[Single-session controls](https://www.oddish.app/experiments/2ee83c7f)

The hosted reference passed all 26 cumulative checks and scored 1.0.
The no-op scored 0.0. One GPT-6.2 Sol xhigh screen was added to the same
experiment, pinned to the qualified single-session version 1. The
baseline qualification and first-screen receipt are in the package archive.

The first common-format GPT screen produced a valid score of 0.5357. It
passed all registration and fixed checks, no positive coordinated case,
and four of seven live missions. Both the stale-readback and the combined
clamp/remount missions transferred material and stopped before the
supervisor ceased replying. The reverse-remount mission returned blocked
at its first reading. The model passed priming and combined priming plus
pressure recovery on a single band. The screen returns this version for
revision. Its native result is in
`experiment/single-session-screening-20261125/hosted-gpt/`.

The archived planner extracted separate target patches. It searched for a
qualifying single stroke before combining partial strokes, and each
partial stroke finished at the parking angle. Its initial rotary
schedules omitted the interval used by a qualifying stacked-carrier plan.
The archive's `coordinated-inspection/` directory contains the geometry
screen and the matching source and trajectory.

#### Replan the dry transfer around a service clamp

The new stacked-carrier mission places a service clamp after the carrier stops.
The original dry bridge collides with it. The clamp clears both wet
passes and the measured stopping motion. The maintained supervisor
accepted the new scene and held while receipts arrived, then returned no
replacement motion at the fresh restart packet.

The maintained planner uses the public joint limits and current collision
geometry to find an intermediate dry waypoint. The ribbon planner and the
live suffix recovery both use this search after a direct transfer fails its
clearance check. It keeps the wet trajectories and their durations intact.
From the same measured stop, it completed the mission in 11.96 s of a
16 s deadline, with 98.15% coverage, 0.594 mL off target, and 19.17 mm
minimum sampled clearance. The native verifier certified the full
trajectory and the restart. The maintained-source replay and its control
are in `experiment/stacked-service-clamp-20261125/`.

The revised offset-mask mission requires a stop on stale readback after
pressure loss, followed by a second stop and registration review. The
reference passed the targeted packaged replay with 89.78% coverage and
both stops in 9.62 s. The reverse return now loses 0.160 mL before the
physical −0.043 rad re-index. A refined native replay passed in 7.42 s
with 89.42% coverage, 0.271 mL off target, and 19.29 mm sampled clearance.
The targeted and cumulative package evidence is recorded under
`experiment/transfer-recovery-next-20261125/`. The uploaded screening
package has a separate version and manifest.

This expanded local package passed all 27 cumulative reference checks and
scored 0.0 with the no-op. The offset-mask coverage was 89.18% when replayed
with a 2.5 ms integration step and 2.5 mm surface cells. The prior reference
replayed the same stacked-carrier stop and receipt holds, then gave no reply
to the cold recovery packet. The full qualification is in
`experiment/transfer-recovery-next-20261125/qualification.json`.

#### Return across the mask after priming loss

The first common-format GPT run passed the single-band priming case. The
replacement uses two patches separated by a centered mask. Its stop
threshold is 0.510 mL of measured emission, below the 0.524 mL analytical
minimum required for completion. In the native reference replay, the
initial priming loss left the first patch at 65.87% coverage. The arm made
a dry crossing and stopped after one wet interval on the second patch.
Covering the second patch fully would then bring total coverage to at most
82.94%, below the 88% recipe minimum. The candidate can choose its own
patch order and recovery path.

The reference recovered both patches after a restart and finished in
8.38 s against the 11 s deadline. Native replay measured 96.875%
coverage, 0.276 mL off target, and 19.16 mm sampled clearance. The case
design and independent trace are in
`experiment/split-mask-prime-recovery-20261125/`. The replacement is
staged in the exact one-session package under
`experiment/cross-mask-transfer-next-20261125/`.

The matched nominal-prefix controller replayed the same priming loss and
stop at 0.5176 mL. Its completion report was rejected because the native
coverage was only 81.35%.

An isolated replay used the unchanged final application from the first GPT
screen. It reproduced the hosted single-band pass at 96.263% coverage. On
the centered-mask replacement, its supervisor timed out on the initial
planning reply, including in an extended diagnostic that allowed four
minutes. The plant issued no motion and measured no emission. The replay
therefore tests initial planning only. The version 2 archive contains the
paired replay and extended diagnostic under `matched-prime-comparator/`.

The exact revised one-session package passed all 27 cumulative reference
checks. The no-op scored 0.0, and Oddish preflight passed. Oddish accepted
this bundle as single-session version 2 with one GPT-6.2 Sol xhigh trial
gated on fresh hosted controls. The qualification and submission receipt
are in `experiment/cross-mask-transfer-next-20261125/`.
[Single-session version 2 screen](https://www.oddish.app/experiments/50fc1f06)

The hosted reference passed all 27 cases and scored 1.0. The hosted no-op
scored 0.0. Both controls ran the same task checksum, and Oddish marked
both rewards valid. The downloaded results and verifier reports are in
`experiment/cross-mask-transfer-next-20261125/`.

GPT-6.2 Sol xhigh scored 0.875. The trial matched the hosted controls'
task checksum and produced a valid native verifier result. It passed all
19 offline checks and six of eight interruption missions. It covered
98.81% of the centered-mask target after priming loss and 97.03% of the
stacked-carrier target after the service clamp changed the dry route. The
two failures were missing controller replies. One occurred after a
registration review. The other occurred after the first stop in the
pressure-loss and clamp mission, before the later remount. Neither issued
a replacement motion. The result exceeded the screening
threshold, so this version returned to task design after one trial. The
native checkpoint and validated breakdown are in the version 2 archive.
[Completed GPT screen](https://www.oddish.app/experiments/50fc1f06)

The submitted planner split the target into lanes before planning a full
route and allocated flow across the whole route. Its supervisor accumulated
measured dose in the part frame and planned a new route at each stop. It
completed two other missions after a physical remount, so the missing
replies do not establish a general remount failure. The source and
trajectory crosswalk is in the version 2 archive under `primary-gpt-trajectory/`.

#### Plan and recover a two-coat work order

A finish pass needs the right primer thickness and enough time for the
primer to set. The timing depends on which areas actually received primer.
Industrial coating instructions give minimum and maximum recoat times,
with limits that depend on the product and application conditions. The
benchmark uses declared synthetic limits for the simulated process.
[AkzoNobel epoxy-primer technical data sheet](https://asc.brand.akzonobel.com/m/4f624c19864a25db/original/Epoxy-Primer-37035A-2K-Version-_tds_en-pdf.pdf)

Version 3 adds a two-coat preview to `plan-coordinated` and measured
two-coat recovery to `supervise`. The coats can have different target
faces. Finish eligibility is based on local primer dose and deposition
time in the part frame. It must survive delayed receipts, process restart,
and a physical remount. The preview also has to schedule the time windows.
With the current weights, a model that passes all offline checks earns
0.5 before any live recovery succeeds.

An initial coupon replay used three primer zones, two finish zones, and a
physical change to the part pose. A staggered schedule qualified both coats.
The same finish poses and material volumes produced 100% nominal finish
coverage when grouped into an early or late pass. In both controls, only
50% of the finish area qualified on time, with 0.0431 mL outside the local
window. The result held at both grid resolutions. A separate control
confirmed that reduced observed primer made the same finish pass invalid.
An application interval spanning expiry contributed exactly half its volume
to the timing violation. Different waits and the reverse zone order also
qualified when matched to valid primer histories. The draft contracts,
replay, and evidence are in
`experiment/layered-coating-contract-20261125/`.

On the curved reverse-return part, a native primer run included a physical
remount. A separate native finish pass started from the measured stopped
joints and surveyed mounting, with a narrower target mask. Refined replay at
2.5 ms and 2.5 mm found 98.66% joint coverage and zero timing violations
with a 1.60 s dry hold. Immediate application deposited 0.877 mL too early.
A global timer measured from the final primer emission deposited 0.0797 mL
too late, although 88.17% of the target still met the local coverage check.
With a matched primer pressure loss, the same finish motion deposited
0.0407 mL over inadequate undercoat. The new ledger rejects both controls
under a synthetic 0.020 mL limit for these defects and passes the locally
timed nominal application. This limit is separate from overspray on
non-target surfaces. The native traces and matched controls are in
`experiment/layered-coating-feasibility-20261125/`. The ledger replay and
its two history reports are in `experiment/layered-coating-contract-20261125/`.

For the coordinated preview, the stacked carrier now has a lower band
with recorded primer and an upper band that still needs primer. The work
order allows new primer on the upper band. The lower band's finish window
expires by 4.98 s, while the upper band cannot be ready before 9.8 s. At
2.5 ms and 3 mm resolution, two coordinated schedules met the 26 s
deadline at 20.12 s and 25.20 s, each with 97.83% primer coverage, 98.68%
qualifying finish coverage, and no ineligible finish. Moving the first
launch 0.60 s later kept the same motion and met the deadline, but reduced
qualifying finish to 49.34% and deposited 1.187 mL after expiry. The
work order, motion proof and controls are in
`experiment/layered-coating-offline-fixture-20261125/`.

An integrated author replay exercised the reference supervisor in the
native arm controller through primer, a stop, remount, delayed receipts,
and finish. It reloaded the journal before restarting primer and again
before finishing. From the measured stopped state, the reference planned
the finish and selected a 1.44 s wait from its reconstructed layer history.
It reported complete in 11.90 s. The acquired receipts matched the inputs
to the independent refined audit, which measured 97.61% primer coverage,
97.76% qualifying finish coverage, and 0.000115 mL of ineligible finish.
The replay and native audit are in the layered contract archive under
`live-reference-overlay/`.

The first assembled prototype kept the complete single-coat regression
set and added one layered work order to each of the preview and recovery
groups. The following two fixtures added a second work order to each group.

A second recovery fixture starts with recorded primer and interrupts the
finish pass after a measured 0.24 mL pressure loss. Replaying only the
unfinished path left coverage at 82.32%. Returning to the earlier deficit
and then finishing qualified 98.93% with 0.0144 mL of ineligible finish.
The same repair still qualified after a 0.64 s hold. After a 0.96 s hold,
it finished within the job deadline but deposited 0.699 mL outside the
local timing window. The interruption threshold is below the minimum
volume a qualifying finish could emit, including one controller tick of
overshoot. The fixtures and refined measurements are in
`experiment/layered-finish-interruption-20261125/`.

A second coordinated fixture uses two patches on the same curved flange,
separated by a 70.35 mm masked stripe. Both patches arrive with recorded
primer. The older patch expires at 4.94 s and the more recent patch first
accepts finish at 5.90 s. The reference planned from the public job and
recorded sweeps, finished in 14.96 s, and qualified 97.51% of the finish
area. Matched early-only and late-only schedules retained the path and
flow and each deposited about 0.49 mL outside the local window. Evidence is
in `experiment/layered-preview-second-fixture-20261125/`.

The screening package now keeps registration and fixed-positioner scoring
and uses two layered cases each for the coordinated preview and live
recovery groups. The earlier single-coat cases are retained in the separate
compatibility bundle. Its reference passed all 29 checks, and its 27
single-coat verifier records matched the prior package exactly. Both
bundles passed Oddish package preflight. The screening bundle, exact file
manifest, and qualification outputs are in
`experiment/layered-coating-contract-20261125/screening-candidate/`.

The exact screening package scored 1.0 on the local reference across all
15 checks and 0.0 on the no-op. Oddish accepted it as single-session
version 3 with fresh hosted controls and one GPT-6.2 Sol xhigh screen. The
hosted reference passed all 15 checks and scored 1.0. The no-op scored
0.0, and both rewards are valid on the same task checksum. The submission
receipt and downloaded controls are in the screening archive.
[Two-coat version 3 screen](https://www.oddish.app/experiments/5756b277)

The maintainer source projection under
`experiment/layered-coating-contract-20261125/promotion-shadow/` rebuilds
the screened version. The independent rebuild matched the path, file bytes,
and mode of all 125 staged files and all 57 single-session files. All 12
Scan-N-Plan checks passed in the projected source tree, including legacy
JSONL transport and cold restart.

| Design dimension | Evidence for the two-coat revision |
| --- | --- |
| Novelty | The earlier single-coat tasks tracked missing dose after a stop. This revision tracks two coats separately and carries each surface region's last primer deposition time across process restart and remount. |
| Verifiability | The native verifier checks swept clearance, per-coat dose, and the amount of finish applied outside each region's recoat window. Matched controls isolate early or late finish and omitted spatial repair. |
| Realism | The work orders include production constraints such as timed recoat windows, recorded primer history, masked surfaces, feed loss, and controller receipts. The recipes and timescales are synthetic. |
| Difficulty | Coordinated planning must schedule coverage against local recoat windows. Recovery must use measured delivery to find both an earlier pressure-loss scar and the unfinished tail, then repair them inside the remaining windows. |
| Feasibility | Both preview cases have independently qualified schedules, and the two recovery cases passed through the reference CLI. Hosted reference and no-op trials confirmed the same version's 1.0 and 0.0 scores. |

#### Match the C++ toolchain in both environments

Oddish reported a valid platform score of 0.0 for the version 3 GPT trial.
Both live cases exited before the first controller reply, and every
substantive registration and planning command exited with status 1. The
trial transcript showed `/usr/bin/c++` in the solver environment and
successful public examples. The submitted geometry loader compiles a
C++17 shared library on first use. The separate verifier image supplied
the C compiler. A confined replay of the submitted geometry reproduced
the missing `c++` error with the C-only toolchain and loaded the library
with C++ available. The v3 score was excluded from the screening gate.
The attempt evidence is in `screening-candidate/diagnosis-source/` and
`screening-candidate/hosted-v3-monitor/`.

A confined replay with C++ also passed the first positive registration and
fixed-positioner checks with the unchanged v3 application. On the imported
primer preview, the application then rejected archived samples that span
more than one controller tick. On the live primer-remount case it reported
`blocked` at the first packet. These are diagnostic replays of the v3
submission. The new screen uses a fresh solver attempt.

Version 4 installs `g++` in both images and checks that each can compile
and load a C++17 shared library during the build. The fixture, verifier,
reference, and candidate instruction files match version 3. The version
changes are limited to the two Dockerfiles, the verifier's build network
allowlist, and the public toolchain note. Package preflight and the local
compiler smoke passed. Oddish accepted fresh reference and no-op controls
and one GPT-6.2 Sol xhigh screen. The hosted reference scored 1.0 across
all 15 checks and the no-op scored 0.0. Both control checkpoints matched
the version 3 checkpoints byte for byte. The maintainer projection in
`experiment/layered-coating-contract-20261125/promotion-shadow-cxx-v4/`
also rebuilt all 57 hosted files with identical bytes and modes. The file
manifest, package diff, and submission receipt are in
`experiment/layered-coating-contract-20261125/screening-candidate-cxx-v4/`.
[C++17 version 4 screen](https://www.oddish.app/experiments/81b24bb4)

#### Check archived sample timing and stacked-carrier recovery

An author-only replay expanded the stacked preview's 42 archived primer
rows to 245 controller ticks. Refining the input cadence preserved the
native dose, timing, and coverage. Rebasing the two records in the live
finish-loss job also preserved every absolute timestamp and the 60 ms gap
between them. The confined v3 application accepted the full-rate preview
and then reported `blocked` for the feasible work order. The cadence audit
and both input representations are in
`experiment/layered-coating-contract-20261125/historical-cadence-audit/`.

An independent stacked-carrier recovery prototype finished the lower band
before its primer expired, then stopped and reindexed during upper-band
priming after a measured pressure loss. It repaired the upper band and
scheduled its finish from the retained and renewed primer records. The
native replay stopped at 24.46 s against a 26 s horizon. Two native resolutions
measured 98.61% and 98.36% qualifying finish with zero ineligible finish.
Reusing the old finish clock produced 1.298 mL of ineligible finish and
52.60% qualifying coverage in the nominal replay.

An author-only application replayed the same recovery through the frozen
live verifier. It stopped at the required 0.790 rad at 24.88 s, with 98.61%
qualifying finish, zero ineligible finish, and 19.17 mm sampled clearance.
The verifier killed and restarted the process three times and checked its
response to delayed receipts, stale feedback, and registration review.
Independent replay of the saved receipts confirmed that lower-band dose and
primer timestamps stayed bit-for-bit unchanged. The application follows
fixture-specific paths. The reproducer, journal, and native check are in
`experiment/stacked-intercoat-recovery-feasibility-20261125/`.

#### Clarify how imported records are replayed

The first GPT-6.2 Sol xhigh trial on version 4 scored 0.20833. It passed all
seven registration checks and three of four fixed checks. Its reverse
return exceeded the off-target limit by 0.000187 mL. The coordinated
planner reported `blocked` on the work order with two aged primer regions.
The curved-return supervisor handled the stop and remount and reached
90.59% primer coverage, then stopped replying before applying finish.
[Version 4 trial and controls](https://www.oddish.app/experiments/81b24bb4)

The stacked preview rejected archived rows that span more than one
controller tick. The finish-loss supervisor required each historical
registration's job ID to equal the current work order and exited before
replying. The version 4 brief described the live receipt cadence explicitly
and called archived rows controller samples. Preserve the reported score
for diagnosis and restart screening after clarifying the archived cadence,
timestamp origin, gap behavior, and registration identity. The native
report and source inspection are in
`experiment/layered-coating-contract-20261125/screening-candidate-cxx-v4/hosted-v4-monitor/`.

Version 5 states the recorded-run requirements in the coordinated and live
briefs. An independent rebuild found the flattened instruction was the
only changed file among 57, including modes. Fixtures, scoring code,
toolchains, and reference code matched version 4 byte for byte. Oddish
preflight passed with zero findings. A new hosted experiment contains the
reference, no-op, and one fresh GPT-6.2 Sol xhigh trial on version 5.
The hosted brief, fixture source, entry point, metadata, and both Dockerfiles
matched the local package. The hosted reference scored 1.0 on all 15 checks
and no-op scored 0.0 on the same native task checksum. The first GPT trial
entered agent execution after both controls passed.
[Version 5 screen](https://www.oddish.app/experiments/5dbb2335)

The task-local comparison build under `experiment/comparison-promotion-v5/`
reproduced all 57 files and modes in the hosted bundle after the move to
`tasks/static/robotics/`. It uses the task's own staged packager and bundles
the four briefs with the cumulative verifier. The rebuilt bundle passed
Oddish preflight and its manifest matches the screened package. All 15
maintained Scan-N-Plan checks passed in the projected source tree.

The first v5 GPT-6.2 Sol xhigh trial scored 0.25. It passed all seven
registration and four fixed-motion checks. Both coordinated plans returned
`blocked`. In the two live cases it blocked the curved-return job before
motion and stopped the finish-loss job after 0.240 mL of pressure suppression.
It held for delayed receipts and stale feedback, then returned `blocked` at
4.98 s with 20.43% qualifying finish coverage. The native score, checksum,
and separate verifier matched the qualified controls. One confirmation
on the same stored version also scored 0.25, with the same four group
scores. Its finish-loss supervisor issued one motion and a stop after the
same 0.240 mL pressure suppression, then blocked at 3.80 s.

The third GPT trial scored exactly 0.50 on the same stored version. It
passed all registration and fixed-motion checks and completed the live
curved-return job. Both coordinated commands reached their time limit.
The finish-loss job emitted 0.368 mL before the stop and timed out at
controller time 4.84 s. All three rewards are valid on the native
reference checksum. The strict below-0.50 gate sends version 5 back for
revision before screening either comparison model.
[First trial](https://www.oddish.app/experiments/5dbb2335) ·
[Second trial](https://www.oddish.app/experiments/979e8413) ·
[Third trial](https://www.oddish.app/experiments/93374239)

#### Stage a harder stacked-carrier recovery

An author-only run passed the frozen live verifier after measured pressure
loss and a carrier re-index. The repaired primer gave the upper band a new
finish clock while the lower band retained its original material. The
reference finished at 24.88 s with 98.61% qualifying finish and zero
ineligible finish. Applying the same paths and flows with the finish command
4.34 s earlier produced 52.60% qualifying finish and 1.29829 mL of ineligible
finish. The saved receipts match after shifting the finish command and its
timestamps.

A native two-pulse probe found a timing edge in the fault driver. It can skip
a safely stoppable wet pulse when the preceding measured wet sample came from
a completed command. Before publishing the stacked case, arm the fault from
the measured feed history and retain the stopped-path certification. Recheck
the native reference and no-op on that exact bundle. A third live case alone
leaves the score for full offline credit at 0.50 under the current weights.
The staged case, timing control, and probe are in
`experiment/stacked-intercoat-standby-20261125/`.

The prospective trigger accepts the next safely stoppable wet pulse once
the measured feed threshold has been crossed, including when the earlier
flow belongs to a completed command. The clearance and stopped-receipt
requirements still apply. A local replay preserved all 15 reference passes
and the 0.0 no-op. The stacked witness and its early-finish control retained
their previous outcomes. A separate path derived from the imported lower
primer record stopped at 4.88 s with 98.35% qualifying lower finish and no
ineligible finish. This establishes the first operation a general planner
can use before repairing the upper band. The prospective driver and reports
are in `experiment/stacked-intercoat-trigger-review-20261125/`.

The next author case exercises two separate feed losses. Primer delivery
drops before a remount. After the repaired upper band reaches its local
finish window, finish output drops by 0.520 mL before a second stop. The
native controller observed both physical stops, reconciled the two receipt
histories and verified the cold restart. The full repair finished in 28.56 s
with 98.61% qualifying coverage and zero ineligible finish. The matched run
used the same motion, stop conditions and earlier receipts and suppressed
30 held-flow intervals over the measured deficit. Its 80.30% coverage is
below the existing 88% requirement. The work order uses a 9.8–18.4 s recoat
window and a 29 s mission cap. An otherwise matched 16.4 s maximum age
produced 0.07278 mL of ineligible late finish against the 0.04 mL limit.
The exact reports are in `experiment/stacked-intercoat-finish-recovery-v6-20261125/`.

The general reference can now plan the retained lower finish from the
imported record and reuse confirmed steady finish delivery to estimate the
second pressure deficit. On the archived severe event, a calibration drawn
only from the stopped command inferred a delivery gain of 0.235, while the
earlier completed finish and the new pre-loss samples measured 0.94. The
confirmed gain recovered 29 measured deficit intervals. Prioritizing the
observed primer deficit also raised the reference's estimated primer
coverage from 95.91% to 98.46% in a replay of its own measured stop. The
reusable supervisor passed the combined native mission in 25.38 s after
both pressure stops. It achieved 98.61% qualifying finish and zero
ineligible finish. The staged cumulative package replaces the curved-return
recovery with this longer workflow and retains the original separate
finish-loss job and existing group weights. The full native reference
scored 1.0 on all 15 checks and no-op scored 0.0. Preflight returned zero
findings. Version 6 contains these two controls and one gated GPT-6.2 Sol
xhigh trial. A separate probe confirmed that
independently qualified completion can be accepted before an optional
final fault while the preceding mandatory primer loss is still enforced.
[Version 6 screen](https://www.oddish.app/experiments/013d69bf)

The first GPT-6.2 Sol xhigh v6 trial scored 0.25 with a valid native
reward on the reference and no-op checksum. It passed all seven
registration and four fixed-motion checks. Both coordinated commands
timed out. The combined remount case reached the first controller reply
deadline without issuing motion. The standalone finish-loss case stopped
after 0.240 mL of pressure suppression, held for the receipt and fresh
feedback, and then missed the reply at 5.30 s. The second trial uses the
same stored task version and settings.
[Version 6 confirmation](https://www.oddish.app/experiments/8a82eb80)

The projected source under `experiment/promotion-v6-rehearsal-20261125/`
rebuilt all 59 uploaded files with matching hashes and modes. The build
includes both stacked-recovery inputs in the cumulative verifier. The
rebuilt package passed Oddish preflight, and 12 author checks passed in
the projected source tree.
