# Scan-N-Plan coating on a rotary cell

A process engineer needs to coat a low-volume part after a fixture change without teaching every arm pose by hand. The proposed application registers the mounted part from calibrated partial scans, plans the arm and positioner together, and finishes a stopped job using the material the cell actually delivered. The work happens in a simulated cell. The application takes CAD, calibrated scans, a recipe, and controller observations and produces an executable trajectory plus a crash-recoverable supervision session.

ROS-Industrial documents using Scan-N-Plan for surface processing, including robotic paint applications. Its ROS 2 workshop exposes reconstruction, raster toolpath generation, and motion-planning services. MoveIt's Pilz planner offers linear and circular paths and blended motion sequences. These are evidence for the workflow and useful planning primitives. The proposed application also has to budget material over a moving surface and reconcile partly completed work after a stop. [ROS-Industrial Scan-N-Plan](https://rosindustrial.org/scan-n-plan) · [ROS 2 workshop architecture](https://ros-industrial-consortium.github.io/scan_n_plan_workshop/architecture.html) · [MoveIt Pilz planner](https://moveit.picknik.ai/main/doc/how_to_guides/pilz_industrial_motion_planner/pilz_industrial_motion_planner.html)

## Implementation status

All four checkpoints package into one cumulative task. The agent image
contains public scan and coating examples with an authored six-axis robot
description. Separate verifier images own the scan cases, arm and
workpiece replay, live inputs, material ledger, and score output. The
local reference and controls qualified against the exact package. Hosted
execution and task-quality ratings are pending.

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
| Initial feasibility | An authored curved part, one external axis, and a pinned six-axis model support headless CPU execution. Finite surface tessellation and ray occlusion make treatment measurable. The first coordinated and resumed cases have yet to be shown feasible under the chosen joint and recipe limits. | Demonstrate a reference pass for each positive family with clearance and dose margin, then establish blocked cases independently. |

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

The cumulative score is the weighted mean of available groups with weights **1, 2, 3, and 6**. The final two groups account for 75% of the final score. A candidate that solves only the first two products would score at most 0.25 at the last checkpoint. Success thresholds for the continuous metrics come from the public job values. The shipped case counts are seven, four, four, and four, in checkpoint order.

### Reference and qualification

A plausible reference starts with robust multi-capture rigid registration against the mesh, supported by bounded multistart search around the commissioning seed. For coating, subdivide the target into overlapping passes, enumerate reachable tool rolls and several positioner angles at each waypoint, and search for a continuous configuration sequence. Joint-space planning handles approach and departures. Retiming enforces the active recipe and motion limits. A part-frame dose ledger accumulates observed intervals by command ID, with scene and registration snapshots fixed when each command issues. On restart, use the residual dose and measured halted state as the new planning input. This is a solution hypothesis. Preserve the freedom to use another surface planner, motion planner, or dose representation that meets the contract.

Before hosted testing, qualify the current package with a complete reference and no-op in a fresh isolated environment. Use at least two independently generated positive missions at each new stage and supported blocked cases. Repeat cases with the same seeds and measure runtime, numerical margin, and replay stability. Include legitimate alternative coating paths so the checks do not select one algorithm. Reject endpoint-only clearance, near-zero flow, fixed invisible transforms, coverage inferred from planned motion, duplicate receipts counted twice, and rerunning the full pass after a stop. Only then run a fresh model comparison. Model performance and the time estimate remain unmeasured.

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
