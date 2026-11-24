# LeRobot dataset repair

A recording team needs to resume data collection after interruptions and release the healthy part of a recording for policy training. Native LeRobot v3.0 shards can remain readable when a stale episode table links a row to another episode's camera frame. This task asks the engineer to audit the recording, reconstruct ownership from independent evidence, and publish a new dataset while training readers retain the original.

## Checkpoints

| Request | Evidence |
| --- | --- |
| [Audit native shards](steps/01-audit-dataset/instruction.md) | Exact issue codes for row order, stale counts, missing and duplicated episode metadata, bad frame intervals, and overlapping readable camera claims. Reject malformed JSON without replacing an existing report. |
| [Plan an evidence-based repair](steps/02-plan-repair/instruction.md) | Compare against independently encoded scene identities and journal entries. Test recoverable data, missing camera evidence, two identical decoded clips, overlapping unique claims and uncommitted captures. Reject duplicate journal identity. |
| [Publish the clean recording](steps/03-publish-repair/instruction.md) | Exercise the submitted plan and apply commands together. Read published Parquet directly, compare retained MP4 bytes, recompute training statistics and receipts, re-audit the published dataset and exercise retries. Reject altered plans and source revisions without damaging previous output. |

## Design dimensions

**Novelty.** LeRobot's dataset tools already convert, edit, and display native recordings. This task adds a forensic ownership decision based on an independent capture journal and a reviewed transactional release. The nearest repository workflow, Localization Replay, aligns clocks and repairs pose sequences. This task instead protects the consistency of joint actions, state, and camera footage consumed by training. SWE-Marathon v1's JAX-to-PyTorch VLA task concerns inference parity and optimization. Both touch robot learning artifacts, with distinct responsibilities for reproducible input and equivalent inference. Concrete Deep SWE, Frontier SWE and Multi-Step SWE comparisons remain unverified. [LeRobot dataset tools](https://huggingface.co/docs/lerobot/main/using_dataset_tools) · [SWE-Marathon catalog](https://www.swe-marathon.org/)

**Realism.** LeRobot users reported that an offset aligned to the frame grid can still return a different episode's camera frame, that action windows can cross a declared episode boundary, and that resumed batch recording can leave stale video metadata. The test uses native v3.0 paths, tables and MP4 timestamps, and a separate recorder journal with decoded-frame anchors. The journal is an application input defined for this workflow. [Wrong-frame issue](https://github.com/huggingface/lerobot/issues/4976) · [Resume recording issue](https://github.com/huggingface/lerobot/issues/2404) · [LeRobot v3.0 format](https://huggingface.co/docs/lerobot/main/lerobot-dataset-v3)

**Verifiability.** Exact witnesses come from the fixture's own camera generation and declared commit state. The grader inspects released files and recomputes row identities, relationships, byte fingerprints and feature statistics. The second release mission changes camera/episode paths, commit states, trusted clips and which conclusions are possible. Behavioral success still depends on selected fixture families. Large anonymized field captures remain untested.

**Difficulty.** The sequence requires reasoning across two different index spaces, matching independently decoded clips, refusing ambiguous evidence, and preserving source and previously published data across retries. The final mission demands genuine data semantics across the whole chain. The current CPU pilot uses three 90-minute milestones. A full five-day task and a low score for any particular model remain unverified.

**Initial feasibility.** PyArrow can preserve the native frame schema while rebuilding the two physical tables. PyAV exposes decoded frame timing and pixel identity without GPU use. An inverted digest index narrows all matching clip starts, and native immutable source video files avoid transcoding. A sibling staging directory and one destination lock keep concurrent identical attempts consistent.

## Provenance and format scope

The fixture uses 48 native joint-vector rows from lsalomme's real SO-101 v3.0 demonstrations. The [asset attribution](environment/resources/SO101-ATTRIBUTION.md) identifies the CC BY 4.0 source, exact slice and digests. The verifier repeats those vectors in authored episodes, changes the indexing and adds an illustrative scalar. It generates RGB MP4s independently so every ambiguous or correct camera link is known. The generated footage does not depict the physical demonstration. No original user images are redistributed.

The product operates on the documented on-disk v3.0 subset with RGB fixed frame rate, episode-aligned table shards and numeric action/state vectors. Variable rate and depth-video datasets, model training and recomputation of image normalization statistics are outside the pilot. The verifier exercises the native artifacts through Arrow and PyAV. It does not run a full LeRobot training stack or independently validate every upstream loader version.

## Reference and reward

The task authors implemented the reference in [common/oracle](common/oracle/). It uses independent raw table observations, exact decoded-frame identity and interval conflict detection, then materializes one new set of native metadata and data shards. The publication compares freshly derived evidence to the approved plan. Existing identical retry directories are checked against their receipt and file fingerprint.

Stages one and two average their applicable audit and plan families. The final reward weighs audit 0.10, planning 0.30 and two release missions 0.30 each. Each family averages its named checks. An overall submission with neither exact audit nor recovered genuine clips receives zero. This prevents rejection-only controls from receiving credit. The separate checkpoint artifact records each result.

```bash
python3 -B scripts/package_task.py
python3 -B checks/calibrate.py
oddish preflight experiment/dist/swe-m2_software-engineering_lerobot-dataset-repair --json
```

Run calibration with the pinned packages from environment/requirements.txt. Use a fresh output parent when packaging another revision.

## Hackability assessment

| Severity | Evidence and residual risk |
| --- | --- |
| YELLOW / MEDIUM | A solution may specialize to the fixture design. Variable IDs, camera digests, distinct commit dispositions and direct per-file comparisons reduce the value of hard-coded answers. New camera layouts and recordings remain useful held-out evidence. |
| YELLOW / UNASSESSED | The packaged verifier has private tests, explicit process credentials in the container, separate workspaces, no candidate network, and filesystem artifact checks. Local calibration uses the current user and has not established hosted credential or sandbox isolation. |
| YELLOW / UNASSESSED | Invalid outputs and symbolic links are refused. Native files are bounded before decoding. Malicious native decoder payloads and resource isolation under hostile candidate processes are untested. |

## Development log

### 2026-11-24

Created the layered requests, cumulative oracle, private verifier and portable
package. Downloaded an attributed CC BY 4.0 v3.0 tabular recording and extracted
48 rows. Verified PyAV lossless RGB encoding, planted camera and journal faults,
and a native re-audit after reference publication. Hosted difficulty and
Harbor's model-based review are pending.

Ran the final bundled verifier with Python 3.12 and the pinned packages. The
reference scored 1.0 at all three checkpoints, with a 16.03-second final
checkpoint. The no-op scored 0.0 throughout. Both maintained package tests
passed, and Oddish preflight reported no findings. The authoring shell did not
provide Docker or Harbor binaries.

The hardened packaged reference and no-op scored 1.0 and 0.0 locally at the final checkpoint. Oddish accepted version 1 into the six-task batch with both controls and one GPT‑6.2 Sol xhigh attempt. Bundle SHA-256 is `2f116640793967614ce800a53097a6a84645d2261f88dada6e2adf7cf43663bf`. [Oddish experiment](https://www.oddish.app/experiments/439b651d)

## Clock recovery revision

The [fourth checkpoint](steps/04-recover-capture-clocks/instruction.md) covers
recordings whose frame hashes are unavailable. The operator has per-camera boot
stamps, sync pulses and broad capture windows. The application must find unique
clock consensus, enforce overlap across all camera observations, recover the
episodes that are invariant across maximum-size chronological assignments, and
publish that decision. The same native files and publication rules carry over.

A clock with an outlier can still be recovered. Equally supported but
incompatible fits leave that boot untrusted. A clip with plausible first and
last camera times can still fail after a dropped middle exposure. An episode
can have a locally ambiguous choice that becomes unique after ordering other
committed episodes. Conversely, two independently admissible candidates can
compete for the same time. These distinctions determine what training data
the operator may release.

The reference fits a constrained pulse consensus in rational arithmetic,
intersects per-frame timing windows around each camera's native clip, and
uses a chronological dynamic program to find the best assignment size.
It recomputes the optimum while excluding a proposed clip tuple to establish
whether the tuple is mandatory. The raw timing sidecar and MP4 faults are
authored. Real tabular data retain the existing CC BY attribution. The CPU
pilot does not measure clock-fit accuracy on a physical deployment or
large-recording throughput.

The final reward weighs the third checkpoint's established components at
0.25 and the two new missions at 0.375 each. Each timing mission checks global
recovery, rejection of unusable evidence, native publication and transactional
recovery. Earlier checkpoint weights remain unchanged. The package calibration
also supports the local-only shortcut via
`python3 -B checks/calibrate.py --shortcut-only`. This control fits the clocks
and runs the native writer while treating each episode's local uniqueness as
sufficient, demonstrating whether the new cases require joint assignment.

### 2026-11-24 hosted diagnosis and hardening

The prior hosted oracle scored 1.0 and the no-op 0.0. GPT-6.2 Sol xhigh scored
0.0, 0.5 and 0.9 at the three checkpoints. The final checkpoint showed full
exact-anchor planning and publication credit. The QA explanation cited only
the first-stage output and did not identify the failing audit check. Replaying
the archived candidate against the original fixture produced a structural
error because the orphan-only Parquet metadata column schema lacked length
and other required fields. The author fixture now preserves the whole native
column schema on the orphan row. The unchanged candidate reproduced the full
expected audit after this correction. A maintained native-fixture test checks
the schema across shards when PyAV and PyArrow are available.

The hosted evidence is from [Oddish experiment 439b651d](https://www.oddish.app/experiments/439b651d).
The revised packaged reference scored 1.0 at all four checkpoints, and the
no-op scored 0.0. The final reference checkpoint completed in 27.54 seconds
locally. The local-only assignment control retained full earlier credit and
scored 0.34375 overall. The three maintained tests passed with native
dependencies, and Oddish preflight had no findings. The new checkpoint has no
hosted candidate measurement yet.
The archived candidate also scored 1.0 when rerun locally through the complete
third checkpoint with the corrected fixture.

The revised bundle passed local reference and no-op controls at 1.0 and 0.0. Oddish preflight reported no findings. The hosted version 2 batch contains one GPT‑6.2 Sol xhigh trial and both controls. Bundle SHA-256 is `2fc946bbd9dcb472c935464ad1bb4aee09b2ffa7089ab849b8b46834662281d3`. [Version 2 batch](https://www.oddish.app/experiments/afbb773d)

## Qualifying training actions after interrupted rollouts

Checkpoint five repairs the association between native frame rows and the
command the robot applied. Inference supplied overlapping action windows,
an operator took control during some intervals, and the recorder lost
some write confirmations. The verifier supplies eligible motor writes and
sparse independent encoder measurements. A single frame may remain
ambiguous even after the full episode is checked. The output records each
confirmed canonical action and leaves uncertain labels null. It joins to
the original global frame index without editing the source shard.

LeRobot's asynchronous controller already carries provenance through its
action queue. Its hardware migration also changed joint units, zeros,
and signs for earlier SO‑101 captures. This exercise combines those two
interfaces using authored logs rather than redistributed rollout videos.
[LeRobot RTC action queue](https://github.com/huggingface/lerobot/blob/main/src/lerobot/policies/rtc/action_queue.py) ·
[LeRobot calibration migration](https://github.com/huggingface/lerobot/blob/main/docs/source/backwardcomp.mdx)

| Dimension | Evidence |
| --- | --- |
| Novelty | The first four checkpoints repair capture association and dataset indexing. The new one adds actuator write provenance and distinguishes identical physical motion under different controllers. |
| Verifiability | The verifier generates native actions from separately authored driver records, observes the physics without consulting the candidate, and compares every output row against measured and intentionally indistinguishable histories. |
| Realism | An asynchronous demonstration can record suggested commands even when the motor accepted a different write. A dataset curator can preserve reliable training labels while quarantining the ones left ambiguous by incomplete readback. The simulated runs start from known joint states. The pilot omits real device friction variation and lost camera content. |
| Difficulty | The solution must align native Parquet frame indices, convert independent command calibrations, preserve simulated state across overlapping timing hypotheses, and use later observations to resolve earlier writes. A latest-write heuristic could find no complete history in the direct experiment. |
| Initial feasibility | A pinned MuJoCo 3.3.7 SO‑101 headless model separates viable histories using eight independently sampled readbacks over 24 frame windows. Two distinct native runs had exactly one feasible history. A takeover run had four complete histories because each of two frames gave identical motion for policy and operator writes. |

The model derives from the Apache 2.0 Menagerie SO‑101 at
`3abca2e302625cec9429c49806121ea2855cef81`. The derivative omits meshes
and retains the original joint axes, inertials, servos and primitive
contact geometry. A 1/180 s native integration step provides six substeps
for each 30 Hz dataset row. The previously attributed Arrow sample and
its license remain separate. [Pinned SO‑101 source](https://github.com/google-deepmind/mujoco_menagerie/tree/3abca2e302625cec9429c49806121ea2855cef81/robotstudio_so101)

The final reward retains 20% of checkpoint four and gives 80% to the
four complete action-qualification missions. These cover sparse motor
feedback, physically indistinguishable human takeover, an inconsistent
episode beside a recoverable one, and different motor-substep acceptance
and ramping through a handoff. All four direct native scope checks passed.

The exact cumulative reference scored 1.0 and the no-op scored 0.0.
The saved version 2 GPT submission passed the retained checkpoint and
scored 0.20 overall. Treating every write as immediate preserved the
other three native cases and failed the ramped handoff. The public
example recovered three actions and reserved one ambiguous label.
The maintained packaging checks and local Oddish preflight passed.

Oddish accepted v3 with one fresh GPT‑6.2 Sol xhigh attempt. The hosted
reference and no-op scored 1.0 and 0.0. [Action-provenance evaluation](https://www.oddish.app/experiments/1faffdf4)

Fresh GPT‑6.2 Sol xhigh scored 1.0 on all five checkpoints. The saved
final report verifies the four new native action cases. The submitted
solver merges identical MuJoCo integration snapshots and traces
backward from surviving states to recover the feasible receipt IDs.
The supplied write windows define the choices at each frame.

Oddish's automatic review cited the stage-one output when assessing
the task score. The attempt-pinned final report identifies stage five
and records all four native checks. The exact 14-file submission
independently scored 1.0 using the frozen local verifier.

#### Reconstruct producers from asynchronous journals

The sixth checkpoint removes the earlier action audit's supplied candidate writes. It identifies which actions reached an instrumented bridge from global policy reply logs, operator targets, boot-scoped accepted counters, and sparse independent encoder data. Each clock uses one feasible affine fit through its synchronization anchors. The worker tracks policy snapshots and the live cursor, discards retired generations, merges overlapping chunks, and uses native physics to resolve remaining possibilities. A complete producer assignment must respect the shared clock and the sequence of queue mutations, even when two producers carry identical targets. [LeRobot RTC](https://huggingface.co/docs/lerobot/main/rtc) · [ActionQueue source](https://github.com/huggingface/lerobot/blob/main/src/lerobot/policies/rtc/action_queue.py#L1277)

A native SO‑101 proof identified 19 of 20 producers, retained one true ambiguity, and reproduced the final integration state exactly across both feasible histories. A midpoint-time control found no complete history. Flattening feasible queue options by frame gave a false second owner at the first uncertain overlap despite exact physical replay, because it combined incompatible queue starts. The held-out packaged case reboots before operator takeover and requires one common clock to resolve a pair of physically indistinguishable owners. The verifier also covers a mixed episode shard, an inconsistent encoder record, and rejection of conflicting device records without replacing an existing report.

The SO follower writes goal positions with `sync_write` and reads present positions separately. These examples model an instrumented bridge journal with accepted counters and authored captures in pinned headless MuJoCo. The runtime reproduces documented queue semantics locally. It does not connect to physical Feetech drives or execute a LeRobot policy. The existing Menagerie model attribution and license still apply. [SO follower implementation](https://github.com/huggingface/lerobot/blob/main/src/lerobot/robots/so_follower/so_follower.py#L918)

The prior checkpoints contribute 20% of the final reward. The five independent new checks share the rest. The new portion requires a successful positive reconstruction.

The frozen cumulative reference scored 1.0 and the no-op scored 0.0. The exact archived v3 hosted candidate retained 0.20 and passed none of the positive journal reconstructions. Replacing the shared clock fit with a separate fit for each queue event scored 0.68. That control reconstructed the nominal case but failed both the held-out early reboot and the mixed-episode shard. The maintained packaging and native fixture tests passed.

Fresh GPT‑6.2 Sol xhigh scored 0.84. All retained checks and four of the
five raw-journal cases passed, including the reboot before takeover and
overlapping policy chunks. In the mixed shard, the candidate rejected a
second episode before replay because its logger reused a producer ID. A
local replay that scoped event IDs to each episode passed all 40 rows and
raised the cumulative score to 1.0 with the frozen verifier. The maintained
instructions state that scope explicitly. The hosted reference and no-op
scored 1.0 and 0.0. [Journal reconstruction evaluation](https://www.oddish.app/experiments/dcfc86bc)
