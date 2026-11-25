# Fixed-lag sensor fusion

A localization lab needs to qualify a wheel and ranging installation, replay its sensor traffic under realistic delays, and repair provisional observations without restarting the trajectory history. The workbench begins with offline replay and extends to a live integrity monitor across six cumulative checkpoints.

GTSAM motivates the workflow and is available in the agent and verifier images. Plaza2 illustrates asynchronous ranging and wheel deltas, and the fixed-lag example describes bounds on retained state. A GTSAM user reported a concrete failure when dropping a pose referenced by a smart visual factor. This task applies the same lifecycle concern to planar models with adjacent-state factors. Its live nonlinear monitor uses body-frame motion, a tag lever arm and asynchronous surveyed ranges. [Plaza2 replay](https://gtbook.github.io/gtsam-examples/RangeISAMExample_plaza2.html) · [GTSAM fixed-lag tutorial](https://borglab.github.io/gtsam/fixedlagsmootherexample/) · [Marginalization issue](https://github.com/borglab/gtsam/issues/1976)

The package includes an 80-position room1 subset of TUM VI motion capture. It retains original timestamps as represented in the source CSV and takes every ninth record from a fixed six-second interval. The source is a handheld tracked rig. We construct wheel and range measurements over that track and generate calibration and fault cases separately. These observations exercise the pipeline with measured movement and exact known perturbations. They do not represent actual wheel measurements from the TUM VI sensor rig. [TUM VI dataset and CC BY 4.0 license](https://cvg.cit.tum.de/data/datasets/visual-inertial-dataset#license) · [Source CSV mirror](https://github.com/BahMoh/TUMVI-IMU-only-Dataset-room1-to-room6/blob/master/dataset-room1_512_16_gt.csv)

## Task design

| Dimension | Evidence and limits |
| --- | --- |
| Novelty | GTSAM supplies replay examples and factor-graph solvers. The deliverable combines delayed factor ingestion, calibration-qualified fusion, and recoverable factor revision in one tool. The repository's localization replay task qualifies bag contents and pose trajectories. This task estimates Gaussian poses and uncertainty with a fixed state budget. Comparisons with SWE-Marathon v1 and external SWE task sets remain unverified. |
| Verifiability | Trusted fixtures provide a measurement graph, exact Gaussian state means and covariances, planted calibration geometry, and ordered revision histories. An independent full-history square-root solver evaluates the reference without copying its online elimination. |
| Realism | Radio and wheel messages can arrive after later samples are logged. Sensor changes can create timing, orientation and range biases. Estimators cannot retroactively remove an expired observation without recovering provenance or refitting an old window. The fixed planar model assumes a common navigation frame and preintegrated IMU deltas. |
| Difficulty | A solver must preserve boundary information through expiry, discover a signed clock offset under contamination, propagate correlated noise through a calibrated rotation, and coordinate revision and retry semantics across process restarts. The benchmark exposes faults from each layer across different motions. Agent difficulty and the five-day workload target are unverified. |
| Initial feasibility | The author reference uses block Schur updates, a robust complex-plane calibration, and a locked durable journal. The native GTSAM wheel is available as an alternative Gaussian backend. The held-out measurements are small enough for a separate batch QR verifier. |

## Verification and reward

The prior at the earliest state summarizes the complete eliminated prefix. All factors are unary or join adjacent states, so eliminating the earliest state creates information only on its immediate neighbour. The reference preserves the full 2-by-2 boundary information, including cross-axis covariance. The verifier instead assembles the entire accepted history and whitens each observation before QR factorization. It checks posterior means and covariance, temporal coverage and lifecycle states separately.

| Checkpoint | Evidence |
| --- | --- |
| Smooth window | Delayed and future observations, large timestamp values, process-only gaps, correlated marginals before and after eviction, malformed covariance and backward clock handling. |
| Calibrate sensors | Both signed offset directions, robust scale and rotation, signed range bias, ambiguous clocks, low excitation, and malformed ticks. |
| Fuse records | Two windows of measured room1 geometry, constructed wheel and range values with known calibration, correlated noise transformation, acquisition support, and consumption of the actual preceding fit. |
| Revise stream | Independent posterior after replace, retract, restore, and expiry. Exact packet retry, rejected sequence and configuration changes, reply loss after commit, concurrent streams, and bounded state after a 900-event burst. |
| Qualify network | Recommission raw asynchronous UWB ranges, clock offset, positive wheel scale, yaw, and shared range biases through two receiver epochs. Score physical trajectories, associations, the declared robust objective, symmetry, and the effect of changing only validation captures. |
| Track integrity | Track unwrapped heading and position from SE(2) body motion and offset-antenna ranges. Detect, isolate, and clear radio faults in order, abstain under indistinguishable fault hypotheses, and revise still-live evidence across restart. |

Each component is the fraction of its named checks that pass if one of its positive functional probes also passes. Weights for window, calibration, calibrated replay, durable revision, and nonlinear commissioning are 1, 1, 2, 3, and 8. Available components are averaged using those weights. Stage five retains 22 earlier flags as a regression component and adds eight mission outcomes. Each of four positive commissioning missions requires both a physically accurate calibration and a qualifying held-out trajectory. The fifth positive case replaces only validation observations and tests that the fit stays frozen. Earlier functionality alone earns 7/15 at the fifth checkpoint. The sixth checkpoint computes its reward as 30% of the retained fifth-checkpoint reward plus 70% of the fraction of eight online mission outcomes. Four missions require physically accurate tracks and correct fault isolation over changed trajectories, including recovery followed by a second outage. The other four cover an independent nonlinear marginal, exact retained Gaussian information, symmetric fault ambiguity and lost-reply recovery. A stage-five-only implementation earns at most 0.30 at the sixth checkpoint. The first five checkpoints keep their existing scoring. Missing candidate output fails its corresponding flag. An evaluator error outside normal candidate processing prevents a valid reward.

## Hackability assessment

- **MEDIUM for scenario recognition.** Numeric grading uses multiple signed offsets, correlated process covariance, independent reference paths and cases with true observational ambiguity. Public room1 motion can be recognized, so its private measurements use seeded noise and distinct ranges. The sealed pilot remains a finite suite.
- **LOW for the tested retry shortcut.** The verifier compares the posterior after retracting and restoring a measurement, checks old observations after expiry, and verifies that a bounded journal does not simply accumulate all packets. Parallel distinct stream writes and publication-failure cases exercise observable state behavior.
- **UNASSESSED for hosted isolation.** Private tests and rewards use a separate image and the application runs with restricted filesystem privileges and a small environment allowlist. Local subprocess validation did not exercise hosted artifact mounts, process isolation, or the execution network.

## Nonlinear commissioning revision

The hosted GPT-6.2 Sol xhigh trial scored 1.0 at all four original checkpoints. Its task assessment described legitimate reuse of a consistent linear estimator and packet revision model. Version two preserves those capabilities and adds a distinct problem. A range arrives independently at its acquisition tick, a receiver can identify a different surveyed anchor after reboot, and two calibration hypotheses can be physically indistinguishable. The fitted pair of epoch maps and continuous calibration must be fixed before validating other drives. [Original experiment](https://www.oddish.app/experiments/439b651d)

The reference enumerates the small clock and wiring hypotheses, fits each with damped robust Gauss–Newton, and solves held-out poses with the best qualified calibration frozen. Known latent physical poses and parameters come from attributed measured room trajectories and independently authored curves, which are observed through generated asynchronous range, wheel, and IMU signals. The grader checks associations and signed calibration against surveyed truth, independently recomputes Huber cost from reported state, and checks position RMSE in the surveyed frame without alignment. It tests distinct wiring assignments, positive and negative clock offsets, NLOS measurement errors, repeated captures sharing an epoch map, and an intentionally symmetric installation. These tests do not establish a general global solution for arbitrary nonlinear factor graphs.

## Live nonlinear integrity revision

The two hosted version 2 GPT‑6.2 Sol xhigh trials scored 1.0 and both corresponding reference and no-op pairs scored 1.0 and 0.0. Their recorded trajectory durations were approximately 329 and 361 seconds. Version three adds causal inference during motion. Radio biases and bindings supplied by commissioning become fixed model inputs. The online estimator now has to distinguish a single faulty radio from a vehicle turn and from an unidentifiable mirror fault. It must make that decision using only the live evidence. [Full task experiment](https://www.oddish.app/experiments/57208689) · [Six-task experiment](https://www.oddish.app/experiments/afbb773d)

The grader checks surveyed position and unwrapped heading over one TUM VI planar path and three authored trajectories. For the TUM input, yaw and sensor observations are authored controls. A separate finite-difference optimizer and square-root elimination check the nonlinear posterior and covariance after retirement. A full-history linear solve checks the exact Gaussian limit. Dense independent profile evaluation and mirrored anchors test ambiguity, including whether its suspect evidence entered the prior. The durable exercises compare responses against uninterrupted control streams and reject expired changes. The hypothesis family covers one bad radio at a time, and its covariance is a Gauss–Newton approximation. The task omits raw radio hardware, multipath channel classification and unknown calibration outside the commissioned model. [GTSAM nonlinear factor graphs](https://borglab.github.io/gtsam/kalmanfilteringandsmoothing/#nonlinear-fixed-lag-smoothing-in-gtsam) · [Plaza2 range workflow](https://gtbook.github.io/gtsam-examples/RangeISAMExample_plaza2.html)

## Development log

### 2026-11-24

Wrote four checkpoints, a native GTSAM candidate environment, a NumPy reference, and independent batch fixtures. Extracted and attributed an 80-row TUM VI room1 position sample. The packaged oracle scored 1 on every checkpoint and passed all 22 final flags. The no-op scored 0 on each. The final local verifier took about eight seconds. The maintained package regression passed and Oddish preflight returned no findings. Hosted container execution and model difficulty remain unverified.

The hardened packaged reference and no-op scored 1.0 and 0.0 locally at the final checkpoint. Oddish accepted version 1 into the six-task batch with both controls and one GPT‑6.2 Sol xhigh attempt. Bundle SHA-256 is `ed2df6ea8f2ce0cc0044089d118ac83d1dfffe1bdde8491d0b13143e18610773`. [Oddish experiment](https://www.oddish.app/experiments/439b651d)

Added the fifth checkpoint after inspecting the hosted trace and 22/22 final result of the original four-checkpoint trial. No changes were made to the first four instructions or scoring when those checkpoints run alone. The packaged reference passed 30 of 30 final flags and scored 1.0 at each of five checkpoints. The no-op scored 0.0 throughout. The original four-command reference and a reference constrained to fixed identity radio bindings each scored 7/15 at the fifth checkpoint, with zero commissioning credit. The maintained package test passed and local Oddish preflight found no issues. Hosted version two execution remains unverified.

The revised bundle passed local reference and no-op controls at 1.0 and 0.0. Oddish preflight reported no findings. The hosted version 2 batch contains one GPT‑6.2 Sol xhigh trial and both controls. Bundle SHA-256 is `e07965ee4dcf03e371bb9ba05f6f8054ca3c00fd724e01a2c8c54a0a2746d079`. [Version 2 batch](https://www.oddish.app/experiments/afbb773d)

Added live SE(2) tracking and radio integrity after two independent hosted version 2 trials scored 1.0, with matching 1.0 reference and 0.0 no-op controls. The version 3 packaged reference scored 1.0 at each of six checkpoints and passed 38 of 38 final checks. The final no-op scored 0.0, the version 2 reference scored 0.30 against the new final grader, and an online implementation that dropped every range scored 0.3875. The final local reference verifier used 33.93 seconds of wall time and 28.90 seconds of user CPU while other controls also ran on the same host. The maintained package check passed and Oddish preflight found no issues. Hosted version 3 runtime and model difficulty remain unmeasured. [Version 2 full experiment](https://www.oddish.app/experiments/57208689) · [Version 2 six-task experiment](https://www.oddish.app/experiments/afbb773d)

The archived GPT v2 implementation scored 0.30 against the exact new verifier.
Fresh GPT‑6.2 Sol xhigh scored 0.98 and passed every live integrity mission.
The only retained miss was sharing a receiver binding across calibration
drives. [Version 3 results](https://www.oddish.app/experiments/9a2d8a0f)

## Native visual track revision

Checkpoint seven adds live SE(3) estimation from delayed pixel captures,
metric odometry and uncertain landmarks. A camera handover changes both the
extrinsic and the intrinsics. Old frames can still arrive afterward. The
estimator has to use the producing calibration, keep correlations when old
poses retire, and retract or restore a revised live feature without applying
it twice. This extends a reported fixed-lag factor-lifecycle problem to a
candidate-facing reconstruction tool. [GTSAM reported marginalization issue](https://github.com/borglab/gtsam/issues/1976) ·
[GTSAM fixed-lag example](https://borglab.github.io/gtsam/fixedlagsmootherexample/)

The independent verifier delivers records one at a time and compares three
authored surveys with an all-history batch solution. It checks pose error,
the complete six-dimensional marginal covariance, exact retries, expired
edits and reported pose and landmark retirement. The frozen reference scored
1.0, the no-op scored 0.0, and the version 3 reference scored 0.20. Native
reference tracking RMS was 0.100–0.109 m. The largest relative covariance
difference from the independent batch build was 9.2%. Using one camera
calibration throughout failed all three missions. Keeping retracted factors
failed the reverse-baseline mission. The small authored scenes establish
local feasibility for these conditions. Longer-run resource use remains
unmeasured. Oddish preflight passed. [Native vision experiment](https://www.oddish.app/experiments/46f3595b)

Fresh GPT‑6.2 Sol xhigh scored 1.0 through checkpoint six and 0.466667
at the native visual checkpoint. The hosted reference and no-op scored 1.0
and 0.0. The first handover survey passed with 0.098 m tracking RMS. At
frame 22 following retraction, the reversed-baseline and late-edit surveys
differed from the independent batch position by 0.352 m and 0.556 m,
respectively. Their full covariance differences were 58.1% and 73.5%.
All receipt checks passed. A local replay reproduced all three outcomes.
Changing only pixel-factor noise to Huber with threshold 1.345 recovered
both surveys. Tracking RMS fell to 0.101 m and 0.084 m. The failure exposed
the estimator's sensitivity to temporary outliers before a retraction.
[Version 4 result](https://www.oddish.app/experiments/46f3595b)

## Bounded repair of retired keyframes

### 2026-11-24

A place-recognition worker can propose a valid relative transform after the
serving smoother has retired the earlier image. Registration can also be
withdrawn or corrected. The eighth checkpoint keeps a delayed reconstruction
history to accept these revisions and an irreversible prior to summarize
earlier information. DM-VIO uses a delayed second graph so that old states
can contribute to an updated marginalization prior. This task uses delayed
SE(3) loop matches and versioned RGB observations to exercise the same
information-lifetime problem in a replayable mobile mapping service.
[DM-VIO](https://arxiv.org/abs/2201.04114) ·
[GTSAM discussion of retained marginal information](https://github.com/borglab/gtsam/issues/1956)

| Dimension | Evidence and limits |
| --- | --- |
| Novelty | The seventh checkpoint refuses changes after a pose retires. This checkpoint separates the serving and repair cuts, preserving a bounded interval in which old, correlated endpoints can become part of a new relative factor. State survives a cold restart and permanent closure keeps the earlier information. The repository's localization replay tasks grade matching and trajectory outputs, while this checkpoint grades recovery of the estimator's posterior and cross-correlation. Comparisons with external benchmark collections remain unverified. |
| Verifiability | An independent all-history solver assembles the accepted raw factors and uses dense QR to compute the requested tangent-space covariance blocks. It does not call the candidate or use its marginalization implementation. A private live driver sends one record at a time, kills the submitted process, checks an altered retry left its file intact, and then redoes the exact request. A separate 720-frame run measures checkpoint size and process peak RSS. |
| Realism | A backend worker may register an image after a second worker has sent later frames, and one side of a loop can be sealed while the other is still live. Discarding the factor or treating a past estimated pose as fixed suppresses valid past uncertainty. The calibration and sensor traffic are modeled observations over authored 6-DOF motion. The task omits feature extraction, raw images, real-time camera drivers and geometric recovery of data associations. |
| Difficulty | Solvers must connect delayed native factors across the window cut, retract them before irreversible compaction, carry uncertain landmarks through a shared marginal, and recover both the estimator and its last receipt independently of old packets. A standard robust kernel cannot authorize or incorporate an absent endpoint. Hosted agent difficulty and the five-day workload target remain unmeasured. |
| Initial feasibility | The reference solves a bounded archive with native GTSAM 4.3.0 and serves the live marginal. It freezes only factors crossing the hard cut, eliminates outgoing variables into a joint Gaussian prior, and journals that prior with the still-editable factors. It does not claim a parallel real-time front-end/back-end implementation. |

The live stream carries relative poses and calibrated feature measurements, but no
truth, unpublished future observations, batch estimates or permanently
sealed raw records. Each short mission uses an independent nonlinear
least-squares estimate and a QR covariance witness over the full accepted
history. Its nominated estimates include revisions to marginalized source
frames, a loop whose endpoints are both outside the serving window, and a
sealed edit with no residual effect. The longer replay observes actual
process kills and storage growth on the submitted CLI. Durable state consists
of one file with a 128 KiB limit. Reported Linux high-water RSS is diagnostic.

The reward keeps 20% from checkpoint seven and gives 80% to three equally
weighted missions. The prototype's active-only policy rejected the first
late repair, leaving 0.321–0.333 m position error against batch and about
139% relative joint covariance error. A frozen-old-pose approximation
looked close in position but differed by 69% in the joint covariance and
about 95% in its cross block at the same closure. The comparison used two
independently authored native GTSAM replays rather than stronger outliers.

The cumulative native reference scored 1.0 and the no-op scored 0.0.
The archived GPT‑6.2 Sol application with its Huber correction scored 1.0
on the retained checks and 0.20 overall. At the first late closure, the
reference was within 4.6 mm of the independent batch pose and 0.76% in
relative joint covariance norm. The two replays improved the latest
position by at least 0.313 m on each designated late match, accepted a
mixed packet after cold restart, restored a withdrawn loop, and preserved
the sealed result. They retained at most 15 and 16 pose states. During the
720-frame run, the checkpoint peaked at 48.3 kB and 40.6 kB after frame
300. The restarted process used about 76 MiB measured peak RSS and
late tracking errors stayed below 0.105 m across ten independent samples.
The package regression and Oddish preflight passed locally. The hosted
reference and no-op also scored 1.0 and 0.0.

Oddish accepted v5 with one fresh GPT‑6.2 Sol xhigh attempt and both
controls. [Retired-keyframe evaluation](https://www.oddish.app/experiments/1faffdf4)

Fresh GPT‑6.2 Sol xhigh scored 0.306667. The 720-frame bounded-migration
mission passed, with 8,825 bytes peak durable state and late sampled
position errors below 0.134 m after compaction. The two short missions
recovered from late closures and restart. Their terminal positions
agreed with batch to 0.012 m. Their terminal joint covariance errors
were 16.0% and 32.9%, and cross-covariance errors were 23.4% and 53.0%,
against 12% and 18% limits, respectively. Local reference cross
errors were about 7.2% in both missions. The retained visual check also
rejected the reported landmark retirement in all three surveys.
[Version 5 result](https://www.oddish.app/experiments/1faffdf4)

An exact local replay reproduced 0.306667. The retained implementation
aged landmarks from acquisition time, while the contract uses acceptance
time for delayed observations. Correcting that stamp raised the score
to 0.36. Using the passing reference for the retained visual command
raised it to 0.466667 with unchanged native rewind results. Native GTSAM
Marginals reproduced the submitted covariance on its own graph.
Replaying the same short missions with a fixed prior chart reduced
the terminal cross-covariance differences to about 7.3% in both.

### 2026-11-24

The top-ten GLM-5.3 Proximus submission scored 0.03952. It submitted
normally after 343 turns. The exact attempt-one artifact reproduced the
score and every check outcome locally with GTSAM 4.3.0 and NumPy 2.2.6.
Calibration, fusion, revision, network qualification, and integrity
passed every check. The window component passed two of five checks.
Each native vision mission stopped at landmark retirement, and each
rewind mission stopped at an extra checkpoint-directory entry.

The retained visual command used acquisition time to age delayed landmarks.
The contract measures age from acceptance. The single-writer rewind
command left an advisory lock file in the checkpoint directory. A
scratch replay using acceptance-frame stamps and a single-file checkpoint
scored 0.092853333333. Camera handoff passed. At frame 22 after retraction,
the remaining two visual missions differed from the batch poses by
0.340 m and 0.541 m, with relative covariance errors of 57.1% and 72.5%.

Removing only the sidecar revealed a separate pixel revision defect in
all three rewind missions. The implementation stored an acquisition
frame for a pixel record, then looked for loop endpoint fields when
editing that record. The submitted reply also used the repair window for
the public active-frame list and the first joint covariance endpoint.
Those fields are defined by the narrower serving window. The rewind
missions stopped before scoring the numerical consequences of these
reply defects.

A further scratch replay corrected the pixel record and used the serving
window for the reply fields. The estimator then met the pose, covariance,
and hard-expiry checks in both short missions. At the first late closure,
its position errors against batch were 4.56 mm and 1.93 mm. Terminal
cross-covariance errors were about 7.2% in both missions. The 720-frame
replay peaked at 15,620 bytes of durable state, with a largest sampled
position error of 0.104 m after compaction. All three missions still
missed exact cold retry, keeping the cumulative score at 0.092853333333.

The replay returned the saved response bytes correctly, then changed
the checkpoint by serializing the loaded state again. Returning the
stored receipt before any write passed all three rewind missions in a
full replay and raised the cumulative score to 0.892853333333 with the
submitted estimator.

The checkpoint instruction now specifies that the committed file is the
only entry in its directory after a reply. Temporary staging files can
support atomic replacement during the request. The local replay results
above used the same frozen verifier as the hosted submission.

A second normally submitted GLM-5.3 trial scored 0.03984 on the same
version. Its source also creates a permanent checkpoint `.lock` file,
and all three rewind missions stopped at the same directory check. The
two trials reported the same three retained landmark-retirement errors.
The second trial passed all five window checks and four of five
calibration checks. The 0.892853 replay applies to the first trial.

DeepSeek V4.1 Flash scored 0.02578 on the same version. It submitted
normally. Its rewind command left the same permanent `.lock` file, and
all three rewind missions stopped before testing convergence. Its
vision code likewise aged delayed measurements from acquisition, and
all three missions stopped at landmark retirement. The retained
results show additional misses in correlated marginalization,
motion-capture fusion, held-out replay, and network calibration.

The third GLM-5.3 trial scored 0.0384 and completed all three rewind
simulations. It passed the late-loop pose checks in both short missions,
with terminal positions within 12.4 mm of batch. Terminal cross-covariance
errors were 77.3% and 73.2%, against the 18% limit. It also missed cold
retry and hard-expiry checks. The 720-frame stream stayed within the
file size budget and tracked within 0.105 m at the sampled points, but
failed the active-support and restart or retry checks. All three
retained vision missions stopped on landmark retirement.

All three top-ten GPT‑6.2 Sol xhigh runs reported 0.04 with the
same-version reference at 1.0 and no-op at 0.0. Each passed causal
closure, pose and covariance accuracy, and cold exact replay in both
short rewind missions. Sealed edits changed neither pose nor
covariance. Their long replays passed cold recovery and tracking.

The archived outputs use `[0,0]` for the first frame and a valid
six-by-six covariance. The frozen instruction described the endpoint
pair as `[first_live,n]`, while the verifier accepted only `[0]` for
that frame. The support predicate consequently failed each rewind
mission. The maintained verifier accepts either singleton encoding
and reports the first support-envelope failure. All retained vision
missions also failed landmark retirement.

The maintained verifier accepted both singleton spellings and rejected
a distinct endpoint or 12-by-12 covariance on the initial frame. The
full packaged reference scored 1.0 and the no-op scored 0.0.

Local replays of all three archived submissions reproduced six
support rejections per trial, covering two frame-zero replies in each
mission. Accepting the equivalent singleton spelling restored all
three rewind missions for each submission. With the retained score
of 0.20, all three diagnostic totals were 0.84. This is the
same submitted estimator under the revised singleton check.

Two full local replays also scored 0.84. The third scored 0.8392
after a retained network probe failed during concurrent replay.
That probe passed in isolation. All three full replays passed
every rewind mission.

### 2026-11-25

#### Recalibrate a camera mount without discarding the map

Checkpoint 9 changes what crosses the rewind boundary. The three archived
GPT estimators recovered the earlier poses and landmarks with fixed
camera calibrations. A serviced camera now has an uncertain persistent
SE(3) attachment. Reprojection connects the attachment, the body pose and
the uncertain landmark. An external camera pose survey connects the
attachment directly to its historical body pose. Both factors can move
the estimated mount and the trajectory. An older camera stays queryable
when images begin arriving from its replacement. [Online visual-inertial self-calibration](https://arxiv.org/abs/2201.09170) ·
[GTSAM variable-extrinsic projection factor](https://gtsam.org/doxygen/a07467.html)

The independent verifier fits the accepted raw measurements over the
whole short replay and uses dense QR to recover covariance in the
requested right-local order. The short missions observe recovery on
images before a tracker survey, apply a late survey to a retired serving
frame, retract and correct it, and try another edit after that capture
seals. A replacement-camera mission also tests covariance at its first
activation and after the original camera leaves the repair window. The
640-frame mission checks the durable state limit, cold retry after a
process kill and tracking after compaction. The final score retains 20%
of the preceding checkpoint. Equally weighted new missions share 80%,
with new credit gated on a complete optical recovery mission.

In the two packaged short replays, image measurements reduced mount
translation error by 164–185 mm across the three camera activations.
The estimated latest pose stayed within 1.04 mm of the independent fit.
The largest full joint covariance error was 1.19%, and the largest
pose–mount cross-block error was 4.04%. Both cold retries and mixed-edit
atomic rejection checks passed.

Four separate controls earned zero new credit in the two short replays.
Zeroing only the pose–mount cross blocks preserved the estimated means
and produced 100% cross-block error. Omitting surveys produced up to
76.5% full covariance error. Treating the mount as fixed in the pixel
factor prevented the optical correction. Dropping attached measurements
at the hard cut drove one old mount to 191 mm of error against the raw
batch estimate.

The exact 186-file package scored 1.0 for the reference, 0.20 for the
previous reference and 0.0 for the no-op. In the 640-frame replay,
the committed checkpoint peaked at 19,439 bytes. The largest sampled
position error after compaction was 0.041 m. An unchanged archived
GPT‑6.2 Sol application scored 0.16784, with all three preceding rewind
missions passing. The maintained package test, repository checks and
Oddish preflight passed. A fresh GPT trial on camera recalibration
remains unmeasured.
