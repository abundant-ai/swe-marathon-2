# Branch and replay MuJoCo simulations

A research group needs to compare controllers from the same physical state
after a fault. Capturing joint pose alone loses simulation state that can
change the first steps after a restart. This task asks for a headless
recorder, a full-state restore command, and a durable study runner for
dependent counterfactual rollouts.

The task runs native MuJoCo 3.3.7. The models are authored MJCF transfer rigs
with an actuated pusher, a free part and a moving fixture. The physical
problem is motivated by MuJoCo's documented state and integration contract
and the public Menagerie model collection. The task embeds its own assets.
[MuJoCo computation and state](https://mujoco.readthedocs.io/en/3.3.7/computation/index.html) · [Menagerie](https://github.com/google-deepmind/mujoco_menagerie)

| Dimension | Evidence |
| --- | --- |
| Novelty | Adds persistent, causal branching of contact-rich runs to static simulation regression cases. The current suite does not benchmark cross-engine policy portability. |
| Verifiability | A separate native simulator advances independent schedules and checks full-state vectors. The supervisor checks scientific equivalence and atomic retry across processes. |
| Realism | Lab workflows use version-pinned models and branch runs to isolate a controller change. The authored models keep test execution headless and deterministic. |
| Difficulty | The solver must get assets, actuator memory, boundary timing, inherited input state, and persistent IDs right. Case difficulty for a strong coding model remains unmeasured. |
| Initial feasibility | Compile MJCF with in-memory assets, capture and restore native state, resolve the branch graph, and commit a locked journal atomically. |

The trace and restore checkpoints score exact checked behaviors on three
transfer rigs. The final score is the fraction of eight independent
branch-study behaviors passed. The scenarios cover dependency order,
concurrent retry and sibling submissions, lost reply, mutation of an existing run, partial commit,
asset mismatch, and a dependency cycle. Each case also checks intact trace and resume commands for its model. A command output is checked against
independently computed trajectories and native checkpoint states. Grading
starts with a fresh workspace and runs the submitted package without
access to verifier inputs other than each public request.

## Development log

### 2026-11-24

Implemented all three checkpoints, a pinned headless environment, an
independent native simulator, and a journal-backed reference. Candidate
images install pinned public wheels at build time. Local tests use the
same Python packages without a container. Hosted image build, trial
performance, and semantic task ratings are pending.

In a fresh package, the reference earned 1.0 and the no-op earned 0.0
at all three checkpoints. The reference passed all eight final cases.
Replacing the resumed native state with reset data failed all eight.
Oddish preflight had no findings.

The hardened packaged reference and no-op scored 1.0 and 0.0 locally at the final checkpoint. Oddish accepted version 1 into the six-task batch with both controls and one GPT‑6.2 Sol xhigh attempt. Bundle SHA-256 is `b8e7d0bba0209065746fc3056ebde1e3aff322d30c79954090094d46ef14b6f7`. [Oddish experiment](https://www.oddish.app/experiments/439b651d)

#### Checkpoint migration revision

The hosted version 1 trial reported 0.0 on the final checkpoint. Review
of the saved candidate found a strict trace parser that accepted the
four documented request fields. The fixture included the resume-only
`checkpoint_ticks` field. The final checkpoint treated the trace
failure as a prerequisite failure across every branch case. The
published zero therefore cannot establish a branching failure. The
revised verifier projects trace requests onto their published format.
[Original experiment](https://www.oddish.app/experiments/439b651d)

The fourth step ports a captured checkpoint into a revised model. It
requires name-based mapping of free and ball joint blocks, actuator
activation, external forces, equality switches, user data, and mocap
inputs before resuming native physics. The compatibility checks protect
coordinate meaning while allowing parameter changes such as density,
friction and actuator tuning. Private cases construct both checkpoint
vectors from known readings in their respective native layouts. The
verifier uses independent native integration to compare the target
continuation, and checks rejection of incompatible models.
[MuJoCo state and reproducibility](https://mujoco.readthedocs.io/en/3.3.7/computation/index.html#reproducibility)

The fourth reward combines 35% retained branching behavior and 65%
migration behavior. Full migration credit requires successful native
continuations and atomic rejection of incompatible inputs. The
migration component is zero until a positive migration case passes.

The archived, unmodified Codex artifact regraded locally at 1.0 on
each corrected original checkpoint. It earned 0.35 on the revised
fourth checkpoint. The new reference earned 1.0 and the no-op earned
0.0. The server's original version 1 record remains historical evidence
of the verifier defect.

The revised bundle passed local reference and no-op controls at 1.0 and 0.0. Oddish preflight reported no findings. The hosted version 2 batch contains one GPT‑6.2 Sol xhigh trial and both controls. Bundle SHA-256 is `346ccb120a73e1268ba01925f10b13e4b1d4529aa22d499668c461b47343eb18`. [Version 2 batch](https://www.oddish.app/experiments/afbb773d)

#### Contact forks across coordinate charts

Stage 5 preserves one or more named root-body states while switching between a free joint and three ordered slides followed by three hinges. The engineering precedent is a model author exposing a scalar axis for a later constraint. The compiled scalar fixtures use signed and permuted axes, nonzero joint references, tilted neutral frames, and a displaced shared pivot. The private verifier independently places known scalar coordinates, initializes both charts with the same Cartesian twist and virtual-work-equivalent wrench, and uses finite-differenced native body motion to encode the same latent warm acceleration. It advances an independently prepared target checkpoint through its native contact dynamics with the continuation inputs in target array order. Earlier `rebase` compatibility and exact packed-state transfer semantics stay available. [MuJoCo joint conversion discussion](https://github.com/google-deepmind/mujoco/discussions/2981) · [Pinned Jacobian and force APIs](https://mujoco.readthedocs.io/en/3.3.7/APIreference/APIfunctions.html#mj-jacdot)

A direct native proof measured pose, velocity, force and warm-acceleration agreement to less than 2×10⁻¹⁰ in fixed coordinate fixtures across both directions. Over 60 native contact steps, separate free and scalar integrations stayed within 62.3 µm in body position. Copying blocks after correctly converting pose caused up to 13.2 mm separation. One prematurely consumed integration step changed the checkpoint clock by 0.7 ms and its physical pose by about 0.28 mm. At four simultaneous contacts with one conjugate-gradient iteration, zeroing warm state changed the next world twist by 0.08638 in the stacked norm. Omitting the changing-basis term changed it by 0.000298. The packaged verifier checks the initial seed and a short continuation in the dense low-iteration case, where tiny numerical differences can eventually change the discrete contact sequence. It runs longer native continuations on the other fixtures. These models are authored and headless. [MuJoCo 3.3.7 integration and warm start](https://mujoco.readthedocs.io/en/3.3.7/computation/index.html#warmstart-acceleration)

The cumulative reward preserves 20% of the prior rebase result and assigns the balance to six positive coordinate changes and two groups of atomic rejections. Valid coordinate migration is required for new credit. The private cases include singular charts in both directions, order and pivot incompatibilities, invalid continuation, and two simultaneous root migrations with reallocated controller and mocap state. The target chart is pinned to native MuJoCo 3.3.7. Third-party geometry and training data are not bundled.

The frozen cumulative reference scored 1.0 and the no-op scored 0.0 locally and on Oddish. The prior rebase reference and the otherwise-identical control that treats warm acceleration as a tangent vector each scored 0.20. Oddish preflight passed. The native solver and exact packaged artifacts were exercised locally.

Oddish accepted v3 with one fresh GPT‑6.2 Sol xhigh attempt and both
controls. [Contact-fork evaluation](https://www.oddish.app/experiments/9abc4012)

Fresh GPT‑6.2 Sol xhigh scored 1.0 across all five checkpoints. The
attempt-pinned final report confirms complete coordinate migration and
atomic rejection of incompatible charts. The hosted reference and
no-op scored 1.0 and 0.0.
