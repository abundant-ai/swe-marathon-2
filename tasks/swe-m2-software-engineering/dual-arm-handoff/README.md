# Spatial two-arm transfer recovery

Implement a supervisory tool for a part moving through two independent
articulated arms. Both arms must satisfy joint dynamics and clearance.
A forecast can invalidate a move during execution. The supervisor
must preserve the holder, brake from measured velocities, and recover
current authority after restart.

The headless cell has two four-axis models, three-dimensional capsule
geometry and commissioned paired poses. The task is inspired by MoveIt
world updates and attachment operations and by manipulation benchmark
workcells. The test models and predictions are authored for this task.
A deployed robot would require its actual geometry, timing and safety
controller. [MoveIt planning scene API](https://moveit.picknik.ai/main/doc/examples/planning_scene_ros_api/planning_scene_ros_api_tutorial.html) ·
[MotionBenchMaker](https://github.com/KavrakiLab/motion_bench_maker)

| Dimension | Evidence |
| --- | --- |
| Novelty | Extends the earlier planar single-arm task to simultaneous spatial capsules, physically matching grasp frames, custody and a revised forecast during nonzero motion. |
| Verifiability | An independent geometric plant checks whole swept intervals and executes commands. Authored variants cover positive clearance, hidden collision, a spatial detour, moving gates, braking and invalid attachment continuity. |
| Realism | Industrial arms use taught configurations and supervised fixture sequences. The payload has separately calibrated offsets for grippers and exactly one active holder. The fixture times and device events are deterministic analogues. |
| Difficulty | A solver must combine collision certification, bounded kinematics, spatiotemporal search, and a durable closed-loop protocol. The human workload estimate is unmeasured. |
| Initial feasibility | Use conservative endpoint travel envelopes and search commissioned poses, times and custody. Journal the first primitive before returning it. |

The first two checkpoints score the fraction of named geometry and
route checks passed. The third checkpoint gives those checks 25% of
the reward and three dispatch cases 75%. The dispatch fraction earns
credit after at least one full transfer completes. A missing artifact
scores zero. The separate verifier stages only the package and checks
observable state at every command boundary.

The fourth checkpoint gives the 13 retained checks 20% of the final
reward and nine new checks 80%. The new fraction earns credit after the
package supplies a working policy for at least one positive mission. For
each proposed policy the verifier follows all live scanner labels and
controller start delays, replays each resulting command in its independent
plant, and checks arrival and custody. The input includes a finite set of
forecasts and discrete delay bounds. Continuous geometry applies within
each primitive.

## Hackability assessment

| Finding | Evidence and remaining risk |
| --- | --- |
| YELLOW / MEDIUM | Distinct scanner commands and reports can encode a plausible-looking path that fails at other observations. The verifier reconstructs possible scenes from receipts and checks every reachable branch, including shared graph nodes, waits, and ownership. Constructed cases cover stationary and moving fixtures. Actual controller receipt timing and sensor noise remain untested. |
| YELLOW / UNASSESSED | The verifier checks a bounded regular-file package and runs the candidate in a subprocess. Hosted mounts and effective permissions for the fourth checkpoint remain unverified. |

## Development log

### 2026-11-24

Added the three checkpoints, portable offline package, reference, and
independent plant. The simulated controller forces a live moving-fixture
wait, observes a withdrawn coordinated move at its cubic midpoint,
commissions a two-tick stop, and guards ownership at the handoff.

The packaged reference passed all 13 final checks and scored 1.0 on all three checkpoints. The no-op scored 0.0 throughout. Oddish preflight reported no findings.

#### Partial visibility and drive latency

The first hosted GPT‑6.2 Sol xhigh run scored 1.0 on each of the three
checkpoints. Oddish trajectory analysis found a working durable dispatcher
and recovery implementation. [Oddish result](https://www.oddish.app/experiments/57208689)

The fourth checkpoint extends local and global replanning to a limited
forecast after a sensor reset. The planner must keep a set of plausible
scenes, dispatch moves which are safe despite start latency, and decide
when it needs a new reading. Separate probes force physically different
paths after a scan, combine two individually ambiguous readings, and
exercise a changing obstruction, an interrupted-motion brake, and an
unachievable deadline. A timed search over commissioned poses, holder and
remaining hypotheses supplies a reference. Worst-delay travel times bound
that search. [MoveIt 2 hybrid planning](https://moveit.picknik.ai/main/doc/examples/hybrid_planning/hybrid_planning_tutorial.html)

The packaged reference passed all 22 checks on the new final checkpoint.
The no-op scored 0.0. The archived GPT package passed all 13 retained
checks and scored 0.20 on the new final checkpoint.

The instruction now defines wire times at dispatch. The first hosted
revision described them as earliest times, which is ambiguous when the
minimum drive delay is positive. The visible contract now says to add the
full delay to both command timestamps. The local Docker-backed Harbor
rubric check stalled before returning a review report. Task-quality ratings
await a completed review.

The hosted v2 GPT‑6.2 Sol xhigh trial scored 0.895726. It missed
interrupted-motion dispatch and the policy that combines initial braking
with subsequent drive delays. Both scanner-dependent policy cases passed.
[Version 2 follow-up](https://www.oddish.app/experiments/9a2d8a0f)

Local replay of the exact candidate confirmed the timing issue. The solver
used the stated earliest physical time, including the minimum delay. Moving
only the reported handoff start and end back by that one tick passed the
case without changing its safety decisions or controller-arrival branches.

The interrupted-motion miss had a separate cause. The candidate issued a
valid brake and then rejected the measured endpoint on an exact comparison.
The readback was an IEEE floating-point value and the internal endpoint was
a rational value. The largest difference was about 8 × 10⁻¹⁷ rad. The
planning checkpoint specified a 10⁻⁷ rad tolerance. The receipt contract
left the tolerance implicit. The frozen hosted reward remains 0.895726.

## Native two-UR5e progression

Stages 5–7 replace the finite taught joint graph for new commands. The candidate estimates both six-axis base and marker offsets, solves fully oriented calibrated handoff targets, synthesizes a 12-axis path, and recovers live authority from the measured cell after an issued moving segment is revoked. The task exposes collision geometry and permissible payload poses. It withholds feasible intermediate joint configurations. Graders drive real native position actuators and retain the actual free payload state through a switched weld. Candidate output is checked against independent surveyed frames, native signed distances, measured joint tracking, and contact and custody receipts. A positive revocation mission physically inserts a blocking fixture into the old transfer area, brakes under the revised forecast and must use the alternate handoff. The plant is simulated, with a simplified box and commanded grasp constraints. It gives no evidence of real hardware safety or frictional finger grasping. [Universal Robots dual-arm workflow](https://docs.universal-robots.com/Universal_Robots_ROS_Documentation/doc/ur_tutorials/my_dual_robot_cell/doc/index.html) · [MuJoCo weld constraints](https://mujoco.readthedocs.io/en/3.3.4/XMLreference.html#equality-weld)

The public asset is the BSD-3-Clause collision-only derivative of the pinned Menagerie UR5e. It retains actual UR5e inertials, joint axes and limits, native drive defaults and collision shapes. The model asset and license are included in the candidate environment. The verifier composes an independent namespaced scene with both arms, calibrated tools, fixtures and a free payload. MuJoCo 3.3.7, NumPy 2.2.6 and the complete wheel dependency set are pinned. The optional native convex collision mode is disabled because it returned a spurious zero separation for a held-out pair of separated oriented boxes. Native contact and signed-distance checks remain active with the older collision backend. [Pinned asset](https://github.com/google-deepmind/mujoco_menagerie/tree/f3b6013629c7b94f8ee93fd977b161fa8350f9bc/universal_robots_ur5e) · [MuJoCo distance API](https://mujoco.readthedocs.io/en/3.3.7/APIreference/APIfunctions.html#mj-geomdistance)

The initial four checkpoint scores are preserved. Checkpoint 5 combines 25% of checkpoint 4 reward with 75% of five native metrology checks. Checkpoint 6 is 15% retained, 22% metrology and 63% of five native planning checks. Checkpoint 7 is 12% retained, 12% metrology, 21% synthesis and 55% of three native authority missions. Each native family requires positive evidence of its intended functionality before its rejection-only checks earn credit. All denominators are fixed. The earlier package by itself can earn at most 0.12. Metrology and open-loop planning alone can earn at most 0.45. A candidate cannot earn completion credit by predicting transmitted bounds or returning a success label. The physical and geometric cases are still finite and crafted, and a rigorous continuous safety case for real hardware is outside their scope.

The frozen reference passed 27 of 27, 32 of 32, and 35 of 35 checks at
the three added checkpoints. The no-op scored 0.0, the archived GPT v2
artifact scored 0.107487, and an implementation with calibration and
synthesis but without native dispatch scored 0.45. The reference braked
after motion was revoked, reached the raised handoff, and delivered with
confirmed custody, zero contacts, 15.3 mm of minimum separation, and
0.0051 rad peak tracking error. The final verifier took 206 seconds locally.
Oddish preflight passed and the hosted experiment includes one fresh
GPT‑6.2 Sol xhigh attempt and both controls. [Native transfer experiment](https://www.oddish.app/experiments/1c1d7b8b)

Fresh GPT‑6.2 Sol xhigh scored 1.0 through checkpoint five, 0.874 on
checkpoint six, and 0.408 on checkpoint seven. The reference and no-op
scored 1.0 and 0.0. The exact raised-route replay ran without contact but
reached 5.975 mm of measured clearance against the required 6.0 mm.
In the two live missions GPT recovered the issued receipt and braked when
revoked. Both transfers stalled as it repeatedly reissued moves. Removing
the frozen verifier's 24-command cap in a diagnostic replay did not change
either outcome. The candidate eventually returned `blocked` at measured
ticks 2127 and 2051, with its original holder still carrying the payload.
The maintained verifier now uses the declared tick deadline to bound
these missions. [Version 3 result](https://www.oddish.app/experiments/1c1d7b8b)
