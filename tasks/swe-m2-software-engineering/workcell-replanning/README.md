# Workcell trajectory replanning

A workcell operator needs to know which portions of a loaded move are still usable after a fixture is repositioned. This pilot asks for an offline tool that rebuilds the scene, checks continuous motion clearance, and recovers a timed path from the robot's measured configuration. The original three-step pilot introduced scene reconciliation, certification, and recovery.
The current revision adds forecast-aware planning and durable command dispatch.

The geometry is an authored planar analog of shelf and table workcells. A translating base, two revolute links, and an offset tool-frame capsule produce articulated swept motion. The environment runs offline on CPU with Python 3.12. Hardware collision tolerances, control latency, perception confidence, and three-dimensional robot dynamics require separate validation.

The scene contract follows the workflows documented for world updates and attachment in the [MoveIt Planning Scene API](https://moveit.picknik.ai/main/doc/examples/planning_scene_ros_api/planning_scene_ros_api_tutorial.html). Shelving and table geometries are motivated by [MotionBenchMaker](https://www.kavrakilab.org/publications/chamzas2022-motion-bench-maker.pdf) and its [Panda benchmark resources](https://github.com/moveit/moveit_benchmark_resources#databases). All bundled example and grader geometry is authored here.

## Original pilot design

| Dimension | Evidence and open questions |
| --- | --- |
| Novelty | MotionBenchMaker publishes reproducible static manipulation queries. This task adds event replay, attachment transfer, revision-specific clearance, and interruption recovery in one CLI. The repository's localization-replay task also composes time-dependent frames, with independent pose accuracy as its output. This task must produce a physically usable replacement trajectory. Comparisons with SWE-Marathon v1, Deep SWE, Frontier SWE, and Multi-Step SWE are unverified. |
| Verifiability | Scene effects, physical trajectories, and error states have programmatic checks. Independent geometry uses its own forward kinematics, separation calculation, and interval coverage. The checks accept any qualifying path. |
| Realism | World objects and attached objects have different frames. Recovery begins from the actual arm position. Fixture movement, grasp continuity, rate limits, and a mandatory stop at invalid configurations reflect real manipulation integration. The planar model makes verification tractable and limits direct transfer to hardware. |
| Difficulty | A candidate must compose grasp frames, implement geometry for degenerate and rotating capsules, combine continuous clearance with joint constraints, and find a detour while preserving the load and current scene. Model calibration remains pending. |
| Initial feasibility | A replayable state machine, rigid forward kinematics, conservative interval pruning, and seeded bidirectional planning solved the exercised cases on CPU. A planning budget may leave other configurations unresolved. |

The larger engineering scope could support five days through a spatial arm model, tracked obstacle timing, persistent scene-service integration, and execution profiling. The three-step pilot covered the static recovery workflow. The current revision adds the tracked-obstacle and command-supervision work described below.

## Original pilot reference and verification

The reference stores attachment endpoints in the tool frame and transforms them after each motion. Its motion checker bounds both endpoints' travel from joint displacement. Distance between the centrelines is Lipschitz under that bound. The checker subdivides until it can certify the margin, observes a violation, or reaches its numerical budget. Recovery reuses the same checker, searches joint space from both endpoints, and assigns segment durations with speed reserve.

The private verifier launches the candidate CLI against independent scenes. `geometry.py` computes poses with complex coordinates and uses an independent clearance calculation and a conservative bound to reject trajectories it cannot prove safe.

| Deliverable | Evidence |
| --- | --- |
| Scene | Exact revision and ownership across add, remove, atomic errors, grasp in a rotated tool frame, detach into a new world pose, and late retransmission. |
| Motion | Two off-midpoint arm sweeps, an attached load rotating into a fixture, load-to-upper-arm contact, valid loaded and unloaded paths, constraint precedence, and atomic rejection of bad input. |
| Recovery | Multiple changed workcells with feasible loaded detours, a multi-fixture rearrangement that blocks all six single-joint orders, a measured state different from the issued plan, safe reuse across a revision update, a blocked measured pose, and rejection of a stale planned revision. |

### Original pilot reward formula

Each component has a fixed denominator equal to the named flags in `probes.py`. Its score is the fraction passed after at least one positive behavior in `checkpoint.py` is observed. Without a portable artifact or positive behavior its score is zero. Checkpoint reward is the weighted mean of the available component scores, with scene weight 2, motion weight 3, and recovery weight 5. The final checkpoint retains all earlier checks. A broken evaluator fails without a valid reward.

## Original pilot hackability assessment

- **LOW for the evaluated shortcut fixtures.** The endpoint-only mutation scored 0.614, the always-stop mutation scored 0.500 with zero recovery credit, and the mutation that ignored attached objects scored 0.543. The verifier independently checks returned motions for physical collisions, times, endpoints, and joint bounds. Finite private fixtures leave some risk of input-specific branching.
- **MEDIUM for process isolation, pending hosted validation.** The separate verifier stages only the submitted package, rejects symlinks and special files, and runs the CLI as the unprivileged `candidate` user with a minimal environment. It reads bounded regular JSON output and keeps private code and reward files under root-only directories. The local check used the same verifier code without container isolation. Detached processes, host mounts, and network isolation still need a hosted check.


## Moving-workcell revision

[Plan a timed recovery](steps/04-plan-in-time/instruction.md) from joint
position and velocity using forecasts for moving fixtures. The input provides
a commissioned roadmap of taught poses and directed transfers. Each transfer
has a controller profile and duration. A route may need to wait, abandon a
short transfer, or move through a pose where it cannot safely dwell.

[Dispatch the next primitive](steps/05-dispatch-motion/instruction.md) from
live measurements and a revisioned forecast. The controller acknowledges or
cancels commands. The supervisor must survive a lost reply, reject stale
authority, and keep one mission's journal entries across concurrent requests
for another mission.

| Design dimension | Evidence and scope |
| --- | --- |
| Novelty | Adds braking, time-dependent clearance and a crash-recoverable command interface to the earlier scene-replay task. Public comparison is limited to the manipulation datasets and software cited above. |
| Verifiability | The planner is judged on arbitrary valid timetables. The closed-loop verifier independently computes geometry, executes the reported primitives, advances telemetry and checks authority and command identity across process restarts. |
| Realism | Uses a rail-mounted arm analog, taught transfers, tracked fixture forecasts, and a controller interface. The model abstracts away perception, 3D arm dynamics and machine-specific safety hardware. |
| Difficulty | The implementation crosses geometry, planning and durable execution. Braking can consume the last usable opening. A safe transfer can lead into a berth that becomes unsafe to hold. An update can invalidate an issued command during a loaded move. |
| Initial feasibility | A finite time-expanded search over commissioned transfers and conservative swept-capsule certificates solves the timed windows on CPU. A lock-protected journal with atomic replacement supports replay across processes. Model difficulty and actual authoring time remain unmeasured. |

A first human implementation estimate is roughly five engineering days across
the full sequence. The main work is scene and attachment replay, swept
clearance, dynamic planning and braking, controller recovery, and debugging
their interactions against end-to-end scenarios. The short commissioned
roadmaps bound the search for reproducible verification.

### Mission coverage and scoring

| Mission family | Evidence |
| --- | --- |
| Moving gate | Wait for clearance, avoid an intermediate berth that will close, use a coordinated loaded detour, or hold when a gate opens past the deadline. |
| Measured braking | Brake three moving axes, recover in a mirrored layout, cross before closure, or hold after braking consumes the last feasible transit window. |
| Revised forecast | Cancel an in-progress transfer at nonzero velocity, recover through a refuge, route around a prolonged closure, or hold under a revised forecast. |
| Restart | Replay after a failed reply write, preserve concurrent mission state, apply the acceleration limit to competing transfer durations, and account for two independently moving fixtures and a multi-capsule payload. |

Each family has three feasible missions and one that requires a safe hold.
The timed-planning checkpoint scores the fraction of complete safe plans or
correct holds. The final reward is the fraction of closed-loop missions
passed. Each mission includes the relevant physical and controller checks.
The target below 0.5 requires seven or fewer successful missions. The first
three scores retain their original diagnostic formulas.

The oracle uses time-expanded search with bounds on static and moving
capsule travel. The independent verifier evaluates cubic transfer and braking
limits analytically and bounds separation over each forecast interval using
complex-coordinate forward kinematics. An author check independently enumerates
the graphs to classify the feasible routes and required holds. The physical
cases have enough clearance slack for conservative interval certification.
The reference can return blocked on otherwise legal transfers exactly at
the clearance margin when its subdivision reaches the numerical budget.

The verifier stages the submitted package, starts commands in fresh processes
and supplies a per-mission scratch journal path. Private mission definitions
and evidence stay in the separate verifier. The local checks executed that
logic outside its hosted container. Hosted isolation and inference performance
remain open.

## Development log

### 2026-11-23

Wrote three cumulative checkpoints, a CPU reference, and independent compact geometry fixtures. The packaged Python 3.12 oracle scored 1 at all three checkpoints and passed all 18 final flags. The no-op scored 0 at every checkpoint. Oddish preflight returned no findings. The final local oracle verifier took about five seconds. Hosted image construction, runtime isolation, solver trials, and task ratings remain unverified.

The hosted no-op scored 0.0 and the reference scored 1.0. One Codex GPT‑6.2 Sol xhigh attempt scored 1.0, 1.0 and 0.928571. The solver passed 17 of 18 final checks. Its only miss was the coordinated detour after the multi-fixture scene update. [Oddish screen](https://www.oddish.app/experiments/9fe9d13b)

### 2026-11-24

Added forecast-aware braking and planning and a durable single-command
supervisor. Kept the three pilot instructions and the archived pilot bundle.
The new bundle is under `experiment/dist/moving-fixtures/`.

Ran the packaged verifier with Python 3.12. The reference scored 1.0 and the
no-op scored 0.0 at all five checkpoints. The reference completed all 12
feasible missions and safely held in every one of the four blocked cases.
Ignoring tracked fixtures yielded 4/16 in the final checkpoint. Removing the
durable journal write yielded 0/16. The author classification, mission-level
evidence, and bundle digest are in `experiment/moving-fixtures-local/`.

The repository source check and 28 targeted checks passed. Oddish CLI 0.1.51
preflight returned no findings. The bundle digest is
`17d205de6ea588fd83efb06a7b6996956456d8e05ef052bf8cef8b84c04edf8e`
over sorted relative paths and file content hashes. The Harbor check did not
produce a usable review report, so the task dimensions remain unscored.
Authenticated Oddish access was blocked by the automatic approval review of
the credential source. The revised bundle has no hosted GPT‑6.2 Sol xhigh
score yet.

The hosted version 2 trial of the preflighted bundle above returned final
reward 1.0 for GPT‑6.2 Sol at xhigh. Its checkpoint rewards were 1.0, 1.0,
0.928571, 1.0, and 1.0. It passed all 16 final missions. Its sole miss was
the coordinated detour after the static multi-fixture update at checkpoint
3. The hosted reference and no-op scored 1.0 and 0.0 respectively at
every checkpoint. Trial records are in `experiment/moving-fixtures-oddish/`.
The measured final reward did not meet the below-0.5 target.
[Oddish version 2 evaluation](https://www.oddish.app/experiments/8ede1e8f)

Future packages explicitly restore private verifier-log permissions on
startup. The original version 2 submission remains available under its
recorded bundle digest.
