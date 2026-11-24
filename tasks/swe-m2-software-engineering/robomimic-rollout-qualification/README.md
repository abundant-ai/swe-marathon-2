# Robomimic rollout qualification

A lab wants to establish whether a frozen policy can reproduce its experiment
under a new control-loop timing profile. This task reconstructs paired reset
states from robomimic HDF5, replays recorded actions and measures policy
behavior under controlled changes to the command and observation pipelines.

| Milestone | Evidence |
| --- | --- |
| Inspect paired demonstrations | Read actual HDF5 models, masks, first states and control snapshots. Reject a duplicated split membership atomically. |
| Reproduce actuation | Compare native MuJoCo trajectories for a successful and unsuccessful action recording. Reproduce the known filtered command trace and find a planted disagreement at the exact held-out tick. |
| Qualify a frozen policy | Independently simulate fixed named observations and weights across held-out starts and timing profiles. Compare full commands, applied controls, final states, goal outcomes and first goal ticks. A second case changes actuator order and physical conditions. |

**Novelty.** MuJoCo Branch Replay focuses on branching and restoring simulator
state. This task combines paired experimental design, recorded controller state,
train/valid partitioning, and policy evaluation under changed timing. The
SWE-Marathon VLA port compares implementation parity across frameworks.
Qualification measures observation and actuator semantics around a frozen
policy in a held-out study. Other public benchmark comparisons remain
unverified. [SWE-Marathon catalog](https://www.swe-marathon.org/)

**Realism.** Robomimic's published Can Paired setup has 100 shared
initializations with one successful and one unsuccessful demonstration each.
The native HDF5 structure uses per-demo actions, states, embedded model and
mask groups. The planar QualificationSlide setup is an authored analog in
that format. The filter and delay snapshot are disclosed study extensions.
The upstream data terms were not confirmed, so the package uses its own
CC0 example and generated held-out datasets. [Can Paired documentation](https://robomimic.github.io/docs/datasets/robomimic_v0.1.html#paired) · [Native dataset format](https://robomimic.github.io/docs/datasets/overview.html)

**Verifiability.** The private runner builds HDF5 and actual CPU MuJoCo
trajectories, with independent calculations for named observations and
controller filters. It checks recorded divergence, metrics, and genuine
rollout signals. The published example provides file-level inspection and
test data. The pilot does not use an upstream checkpoint or validate robot
hardware transfer.

**Difficulty.** Correctness requires keeping simulator snapshots, buffered
actuation and observations in sync, mapping names to changing actuator
orders, evaluating paired starts, and noticing when a long delay changes
success. Agent time is capped at 90 minutes per milestone. Five-day
difficulty and hosted results remain unmeasured.

**Initial feasibility.** MuJoCo provides explicit state get/set operations,
and h5py reads the recordings without loading an entire learning stack.
The reference uses native state restoration and a bounded FIFO around a
frozen affine policy. The task authors wrote it in common/oracle.
[MuJoCo state and simulation documentation](https://mujoco.readthedocs.io/en/stable/programming/simulation.html)

The final checkpoint averages the inspect, replay and two policy families.
Earlier checkpoints average their available families. A correct native pair
index is required for nonzero reward.

## Hackability assessment

Specialization to known episode names or replay traces remains medium risk.
The verifier uses two physical profiles, masks with genuinely distinct
training conditions, and complete independently simulated trajectories. The
private evaluation boundary uses separate credentials and capped JSON
artifacts. Hosted isolation and broader fixture specialization are
unassessed. Harbor model-based review is pending.

## Development log

### 2026-11-24

Implemented and locally calibrated the native HDF5 and MuJoCo workflow.

The packaged reference scored 1.0 at each checkpoint, and the no-op
scored 0.0 throughout. The final reference ran in 4.18 seconds locally.
The maintained package check passed, and Oddish preflight had no findings.
The public example produces four nominal successes, two under immediate
actuation with observation lag, and zero under the long pipeline.
