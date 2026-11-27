# Telephone contact surfaces from a real desk video

[Oddish model trials and baselines](https://www.oddish.app/experiments/6dc2a858)

Given a handheld RGB recording, reconstruct the desk, the three objects on it, and four surfaces a robot could touch. The task returns an editable scene program. Its triangles carry colors, object IDs and functional part IDs. A handle that looks like a solid white disk, for example, fills an opening that a gripper needs to pass through. [Candidate brief](instruction.md)

## Inputs and deliverable

The Freiburg 2 recording shows a gray tape roll, a ceramic mug and a landline telephone. The agent sees six native keyframes on a contact sheet and a 2.4-second video with 73 lossless, timestamped 640 × 480 images. The candidate gets calibrated optical tracks in meters and the lens distortion model. The four held-out exposures are distinct from all supplied frames. Their nearest dense-video exposure gaps are 0.200, 1.200, 1.732 and 2.700 seconds. The reference depth and labels stay in the separate verifier. The original TUM RGB-D SLAM sequences are distributed under CC BY 4.0. [Dataset](https://cvg.cit.tum.de/data/datasets/rgbd-dataset) · [Lens calibration and data format](https://cvg.cit.tum.de/data/datasets/rgbd-dataset/file_formats) · [Capture audit](checks/capture.json)

The agent writes submission.py, tests it in the candidate container and transfers that file and its smoke-test receipt. A separate worker rebuilds the colored mesh with the public observations. The solver has 45 minutes for the coding trial. The reconstruction itself has ten CPU minutes and a budget of 20,000 triangles. The maintained worker supports the same NumPy, SciPy, Pillow and FFmpeg tools in both containers.

## Reward and measurement

The continuous reward is the minimum of the following three scores. Every eligible measured ray remains in its component's denominator even if the mesh misses it. An invalid submitted mesh earns zero. An infrastructure or trusted-fixture error in the maintained verifier clears the reward and raises a verifier failure.

| Component | Measurement |
|---|---|
| Named contact surfaces | Four withheld native RGB photographs each have contours for the annular tape crown, exposed interior of the tape core, ceramic mug handle and pale upper handset. For each part and view the score is the fraction of ten IoU thresholds from 0.50 to 0.95 in steps of 0.05 that the visible projected mesh attains. It excludes the one-pixel contour band from both false positives and false negatives. Average over four views per part, then over the four parts. |
| Metric object surfaces | A hit on a measured Kinect ray requires the correct object ID and optical depth within 3 cm. For each object pool hits across the four photographs, then divide twice the hits by the sum of visible measured and predicted object pixels on rays with depth. Average the three object F1 scores. |
| Scene color and geometry | A ray with measured depth earns credit when the first visible mesh intersection is within 5 cm and its interpolated vertex color has mean absolute sRGB error at most 25.5 levels. Average the fraction of hits in each of the four views. |

All components use the same native Freiburg 2 optical projection, z-buffer, and RGB-time pose. The depth and whole-scene color scores sample native pixels (4x+2, 4y+2). The withheld RGB and depth exposure times differ by 13.2–14.6 ms, with pose-based compensation for measured camera motion. The four withheld poses were fitted using background feature correspondences while excluding all three object boxes with an extra 16-pixel margin. Independent validation sets of 24, 22, 18 and 14 feature matches gave median reprojection errors of 0.57, 0.50, 0.41 and 1.12 pixels. Hand tracing uncertainty is greatest where the handle meets the mug. [Registration audit](checks/registration-audit.json) · [Typed requirement checks](tests/test_reconstruction.py)

## Controls and stability

| RGB-only reconstruction or perturbation | Reward |
|---|---:|
| Packaged two-view fit on the desk layout | 0.5016 |
| Six-view handle and handset fit with multiview color | 0.5304 |
| Packaged fit with its scene context removed | 0.0198 |
| Uniform gray colors | 0.0455 |
| All surfaces at one depth | 0 |
| Shuffled functional surface IDs | 0 |

The packaged reference starts from a prior agent's publicly observed desk layout. Two public views give traced contact contours. Public image features supply 122 floor and 165 tabletop matches for the support planes. The second control replaces the mug handle with a tube fitted to its centerline in six public views and reconstructs the handset from its bright outline in those views. It estimates visible vertex colors from the six keyframes and seven additional video frames. The resulting contact score is 0.769, object F1 is 0.555, and whole-scene color-and-depth coverage is 0.530. The measured value is an attainable score for this scene. The maximum achievable score is unknown. [Control fit code](checks/fit_rgb_control.py) · [Counterfactuals](checks/controls.json)

Twelve prespecified resamples of the background registration matches moved the original reference between 0.419 and 0.504. The six-view fit exceeded 0.5 on all twelve, ranging from 0.522 to 0.532 under the frozen one-pixel convention. Removing the contour band entirely gave that control 0.519 on the nominal registration. These resamples measure one source of calibration uncertainty in this recording. Hidden or inaccessible sides of objects, other lighting conditions and other cameras have no independent assessment here. [Original reference sensitivity](checks/sensitivity.json) · [Six-view sensitivity](checks/six-view-control.json)

## Reproduction

Run the following from this task directory. The default restore uses the authenticated Oddish CLI to retrieve missing generated inputs. An existing local copy of the version-1 bundle is also accepted through `--bundle PATH`. Both paths compare file bytes to the same SHA-256 inventory. The first command supplies inputs for the maintained task. The second reconstructs all 49 evaluated version-1 runtime files in a separate directory, including the exact original instruction, smoke test, and verifier. The release-runtime command restores the intermediate 53-file maintained baseline. The clean-runtime command restores the final 55-file revision with the public clean-rebuild command.

```bash
python3 scripts/prepare_data.py
python3 scripts/prepare_data.py --frozen-runtime dist/telephone-v1
python3 scripts/prepare_data.py --release-runtime dist/telephone-release
python3 scripts/prepare_data.py --clean-runtime dist/telephone-clean
python3 checks/test_harness.py
python3 checks/fit_rgb_control.py --output experiment/rgb-control.npz
```

The fit requires NumPy, SciPy, OpenCV with SIFT, Pillow and a C compiler. Providing `--keyframes-only` also restricts vertex colors to the six original sheet frames. The author fit begins with the restored RGB-only reference mesh. It uses hand-traced public features in the checks directory and the shared projection and rendering functions; its reconstruction reads no withheld RGB, depth, or outlines. The package inventory SHA-256 is `c2518f6bae4909f12ec517075c4db869603b9b57136aed416edd1b1d0b2ca73a`. [Frozen inventory](scripts/runtime-inventory.json)

To rebuild the packaged reference itself, retrieve the previous six-keyframe solver's RGB-only mesh and run the two fits in order. Only its background triangles supply the initial desk layout. The first program fits both support planes from public feature correspondences and reconstructs the three objects from public outlines. Its output matches the packaged reference byte for byte. The second program adds the six-view mug and handset geometry and fits colors. The older solver's result is authenticated by SHA-256 before loading. [Reference fit](checks/build_rgb_reference.py) · [Original six-keyframe trial](https://www.oddish.app/tasks/swe-m2_ai-research_clutter-object-metrology-swapped-c9e4647d?trial=swe-m2_ai-research_clutter-object-metrology-swapped-c9e4647d-5&file=verifier%2Fartifact.npz)

```bash
mkdir -p experiment
oddish cat swe-m2_ai-research_clutter-object-metrology-swapped-c9e4647d-5 verifier/artifact.npz > experiment/prior-layout.npz
python3 checks/build_rgb_reference.py --layout-artifact experiment/prior-layout.npz --output experiment/base.npz
python3 checks/fit_rgb_control.py --base-reference experiment/base.npz --output experiment/rgb-control.npz
```

Use environment/ and tests/ as independent Docker build contexts. In the maintained release, the smoke test and separate verifier accept at most 2 MiB of source, 60,000 vertices, 20,000 faces and a 5 MiB uncompressed numeric mesh. The candidate brief states those limits. The frozen task had a 2 MiB source limit and looser checks on the numeric arrays. The updated verifier checks types, dimensions, array lengths, compressed expansion and member identity before loading the numeric mesh. It cleans stale receipts and score outputs and terminates processes belonging to the dedicated worker account. Both versions use the same measurement fixtures and formulas.

A separate physical check used the independently traced interiors of the four contacts and the corresponding Kinect depths. After removing a one-pixel contour band and requiring a measured parent-object ray, 190 tape-crown, 106 inner-wall, eight handle and 96 handset rays remained. The stronger RGB control predicted the correct part ID and depth within 3 cm on 60.0%, 90.6%, 75.0% and 96.9% of those rays. The three matched GPT trials hit zero, two and zero of the 400 rays. The mug-handle count is too small to establish reliable 3D shape or clearance on its own. This diagnostic does not affect rewards. [Physical contact-depth check](checks/contact-depth-diagnostic.json)

A post-hoc comparison used only withheld rays on which the three GPT meshes already predicted the right object. Across the nine trial/object pairs, the median surface was 5.3–10.3 cm too close to the camera, even though silhouette IoU ranged from 0.636 to 0.820. For comparison, 73 independently reserved background landmarks triangulated from public images were a median 2.25 cm farther away than measured Kinect surfaces. Near depth edges this test mixes surfaces. On 18 locally smooth patches, the median signed difference was +2.31 cm. The background control measures a different set of rays and indicates the uncertainty of absolute scale on this recording. [Depth comparison](checks/landmark-depth-audit.json)

A second diagnostic selected global translations or isotropic scales **using the withheld depth**, separately for each submitted GPT mesh. It is an upper comparison for these transformations. An oracle-selected scale recovered object depth F1 of 0.664, 0.709 and 0.693, but the highest full rewards over the tested corrections were only 0.0625, 0.06875 and 0.050. Correcting a global scale leaves substantial errors in the fine contact geometry or surrounding surfaces. These diagnostic measurements remain separate from every official reward. [Withheld-data scale diagnostic](checks/scale-diagnostic.json)

## Task design

| Dimension | Evidence and scope |
|---|---|
| Novelty | The six-keyframe desk task measured three entire objects. This task adds four separately modeled, recessed or protruding surfaces and a video of the surrounding room. ETH3D evaluates metric surface accuracy and completeness. Here visible intersections also need an agreed physical identity, and other metric surfaces must reproduce scene color. A comprehensive comparison with all SWE coding benchmarks remains open. |
| Verifiability | A held-out depth observation and independent RGB contours provide geometric checks on actual executable output. The one-pixel convention, four views and registration uncertainty affect the interpretation of thin contours. |
| Realism | A researcher can inspect a metric mesh and use surface IDs to plan a contact point or analyze the tape aperture. The benchmark measures accessible surfaces and appearance. It does not test a physical robot's ability to grasp or apply force. |
| Difficulty | A solver has to align RGB observations, resolve occlusion and fit distinct depths for shallow adjacent parts. It also needs to model the tabletop, floor and background to earn whole-scene credit. Trials took minutes to tens of minutes. A five-day engineering workload has not been established. |
| Initial feasibility | Independent RGB-only fitting exceeds 0.5 under each of the twelve registration perturbations. Additional rooms, independent human annotations and trials with different capture conditions would establish external validity. |

The preceding task and related research benchmarks provide the closest comparisons. [Six-keyframe object metrology](../clutter-object-metrology/README.md) · [ETH3D multi-view surface evaluation](https://eth3d.ethz.ch/high_res_multi_view) · [TUM RGB-D Benchmark](https://cvg.cit.tum.de/data/datasets/rgbd-dataset)

## Hackability assessment

The highest remaining rating is **yellow / medium**. The public source recording includes depth, so an agent with prior knowledge of this particular recording could reconstruct a solution from memory. The candidate and verifier run offline. Only the candidate's two declared files transfer to the verifier. The rebuilt triangle mesh faces the same renderer for contacts, objects and whole-scene checks, independent of code style or the public receipt. A candidate can fabricate a receipt, so trajectory evidence and measured geometry are recorded separately.

Executing a general-purpose Python scene builder requires an operating-system isolation boundary. The release verifies source and array bounds, and cleans up stale results and worker processes. Local regression checks cover missing source, malformed numeric arrays, invalid labels, ordinary descendant cleanup, and a trusted-fixture exception. This is a limited boundary audit. The original frozen runtime had fewer safeguards and remains available for historical reproduction. [Maintained verifier](tests/verify.py) · [Regression checks](checks/test_harness.py)

| Assessed boundary | Evidence | Residual risk and next validation |
|---|---|---|
| Public source recording and memorization | 🟡 Yellow / medium. The source website also distributes the original RGB-D recording. The authored and hosted model runs used offline containers; each agent received only RGB and poses. | A model with the original desk in training might know its geometry. Replicate the intervention on new recordings before drawing population-level conclusions. |
| Smoke receipt and execution | 🟡 Yellow / medium. The receipt is candidate-writable. In the hosted trajectories each tested source was matched by SHA against its verified output. | A matching self-authored receipt alone establishes no execution history. Preserve trajectory evidence when comparing agents. |
| Private files, credentials and result tampering | 🟡 Yellow / unassessed. The separate runtime executes submitted code with no network and a dedicated UID. The verifier checks its fixtures and propagates trusted-side failures without a reward. | The local tests exercise ordinary descendant cleanup, numeric inputs and stale results. The full OS authority boundary and hostile system workloads have no exhaustive assessment. |
| Omitting context or exploiting projected geometry | 🟡 Yellow / medium. Removing context, flattening scene depth or moving surface IDs reduces reward. All objects occlude one another under a common z-buffer. | Visible part silhouettes and sparse object depth leave some freedom in physical gap depth, unobserved sides and contact clearance. Physical probing or independent measurements of each part would test those quantities. |
| Candidate resource use and trusted rendering | 🟡 Yellow / medium. Bounds apply to source, expanded numeric representation, worker file descriptors, memory and CPU. Previous scores were replayed with bounded outputs. | Extreme projected area or the aggregate of many small files could stress the overall evaluator. Use infrastructure failures as missing results and validate wall-clock and storage limits separately. |

The maintained verifier checks digests for the eight measured ground-truth files and the eight public observations before scoring. A missing contour photograph or altered depth array now produces a verifier error. The public assets resolve through absolute paths, paths relative to the working directory and paths next to the submitted script. A clean development test stages only the declared fixtures and submitted source under a new writable /app/work and supplies an empty /tmp. The deployment worker uses the same workspace layout. The separate trusted-fixture preflight verifies the expected withheld annotations, depths and public assets. The maintained reference reconstructs 9,110 vertex colors from actual public pixels through the absolute path when the submitted source is rebuilt. The independently reproducible author fit determines the mesh geometry. [Ground-truth and observation digests](tests/fixture-digests.json) · [Public rebuild checks](checks/check_public_rebuild.py) · [Reference source builder](solution/oracle.py)

## Development log

### 2026-11-26

Prepared a fixed-target trial on the telephone desk. The correct, swapped and blind conditions used identical text and pose metadata. The treatments changed the RGB contact sheet, MP4 and native PNG archive together. The hosted original reference scored 0.501588259 and no-op scored 0. These are independent of the authored six-view control.

The first three correct-image GPT-6.2-Sol xhigh trials scored 0, 0.011784470 and 0.006250000. Each agent opened the expected native sheet, processed the dense recording, ran its final source and supplied a matching smoke receipt. The isolated verifier built valid meshes containing 19,766, 19,973 and 19,990 triangles. The last two earned some inner tape-wall footprint credit. All three swapped and all three blind trials scored zero. Mean object silhouette IoU was 0.736 with correct video, zero with swapped video and 0.070 when blind. Offline replays held each correct-run source fixed and substituted the alternate inputs. The six mesh replays changed vertex colors while preserving geometry and labels. [Oddish experiment](https://www.oddish.app/experiments/6dc2a858)

All three DeepSeek-V4.1-Flash trials and all three GLM-5.3 trials on the correct telephone recording scored zero. Each of the six trajectories contains successful numerical analysis of the supplied pixels and a smoke-test result matching the final source. Each source produced a valid mesh. The mean object silhouette IoU was 0.083 for DeepSeek and 0.112 for GLM. The strongest 3 cm object F1 was 0.078 and 0.054, respectively. All six meshes earned zero on the contact-footprint component. Across the three models, all nine correct-image trials scored below 0.5. The additional six swapped and blind trials measured GPT only. [Per-trial scores and image-use evidence](checks/model-trials.csv)

All 15 archived model programs also passed the clean development check in new offline workspaces. A second fresh workspace reran each source with the original visual condition and reproduced all five arrays. The largest absolute numerical difference from any hosted array was 2.5e-12. Replaying the independent models' submitted programs verifies transfer and reproducibility; the hosted model trials used the original 49-file runtime. [Source-by-source replay](checks/clean-source-replays.json)

The maintained package adds a bounded archive loader, a dedicated worker UID, process cleanup and separate handling for verifier failures. The frozen snapshot and restored fixture hashes preserve the exact original experiment.

## Harbor implementation review, 2026-11-26

The Harbor review ran on Oddish against 65 files in snapshot `0a1383e698e8fda06dc4e0c10a15b7355154ffb6dcdfec1c34ae71af26c7537e`. The structured result passed the Harbor validator. The reviewer assessed the implementation using historical model trials and independently reproduced the packaged reference's nominal score. The report does not evaluate subsequent fixes. [Structured review](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-video-implementation-review-e0b9423f?trial=swe-m2_ai-research_telephone-video-implementation-review-e0b9423f-0&file=artifacts%2Fapp%2Fcheck-result.json)

| Dimension | Rating | Confidence | Evidence and limits |
|---|---:|---|---|
| Novelty | 3/5 | Medium | The task extends six-keyframe object metrology and geometric reconstruction benchmarks with functional contact surfaces, openings and colored room context in one mesh. Wider comparisons are incomplete. |
| Verifiability | 3/5 | High | Four withheld views measure contact footprints, 3 cm object surfaces and 5 cm scene depth with color. Registration, tracing uncertainty and handling of missing outlines affect the measurement. |
| Realism | 4/5 | High | Occlusion, exposure changes and real camera motion make surface fitting and color fusion consequential. The mesh supports spatial inspection. Physical grasp clearance has not been tested. |
| Difficulty | 4/5 | High | Three tested GPT meshes recovered recognizable objects but misplaced visible surfaces. This establishes difficulty for these short trials. The review found no evidence for a five-day workload. |
| Initial feasibility | 4/5 | Medium | A public-RGB fit using a prior layout and manually traced image evidence achieved 0.522–0.532 across pose resamples. The review did not establish from-scratch performance on unfamiliar scenes. |

The review identified two implementation issues in the snapshot. The worker received camera inputs in its temporary directory, although the brief also allowed absolute paths under `/app/work`. Missing outline keys could change the measurement denominator. The candidate-owned smoke receipt verifies source identity when corroborated by a trajectory. A valid digest alone does not establish execution. The typed requirement results run after the outer worker has validated and scored the mesh.

The updated 53-file runtime completed a fresh hosted reference and no-op evaluation. The reference program read the specified absolute public RGB path, reconstructed 9,110 vertex colors from the supplied keyframes, and returned all five arrays exactly equal to the independently reproducible fitted mesh. It scored **0.501588259**. Its public receipt matched the source transported to the new verifier. The no-op was classified as an invalid candidate and received zero. The package changes and supporting evidence followed the immutable review snapshot. [Maintained reference and no-op](https://www.oddish.app/experiments/f66b2a5c) · [Source hashes, typed checks and exact-array comparisons](checks/maintained-baselines.json)

The final 55-file runtime also ran fresh hosted controls. Its oracle passed the public clean rebuild and the deployed worker, opened the sheet by absolute path, and extracted dense frame 0072 into a scratch directory beside the source. The measurement arrays retained every original vertex, face and label; two vertex colors used raw endpoint pixel values and moved by at most four sRGB levels. Every component score matched the fitted reference, with reward **0.501588259**. The no-op earned zero for an invalid candidate build. These control trials are on a later implementation revision than the 15 model trials. [Clean-runtime hosted controls](https://www.oddish.app/experiments/f47796ed) · [Measurements and array checks](checks/clean-baselines.json)

### Publication review, 2026-11-26

The second Harbor review covered 78 files in the clean-test package, snapshot `5f7e42bac4abd6c7af1758dd4b4ec263a7fd6091341e0b80abe88dc5a435f241`. It retained all five scores and confidence levels in the implementation review table above. It confirmed pinned contour denominators and accepted the revised hackability assessment. The public rebuild and the final deployment now use the same canonical observations. The separate hosted reference and no-op on this revision finished after the review snapshot. The primary model cohort remains pinned to the original experimental version. [Publication review](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-clean-publication-review-59ad214e?trial=swe-m2_ai-research_telephone-clean-publication-review-59ad214e-0&file=artifacts%2Fapp%2Fcheck-result.json) · [Clean-runtime controls](https://www.oddish.app/experiments/f47796ed)

In the evaluated implementation, floating-point vertex colors are rounded to bytes before interpolation. The worker has a 640-second wall limit in addition to its CPU limit. The typed component reports use 0.5 as a diagnostic pass threshold. The task reward is continuous. Withheld depth checks assess the three parent objects. Small-part depth, physical clearance and cord exclusion are not individually verified by the primary reward. The packaged control starts from prefit geometry. Author-side scripts and hand traces document its public RGB provenance.

A separate audit retrieved the candidate brief and every environment file directly from each pinned Oddish task version. The matching and swapped bundles each contained 15 candidate-visible files. Only the contact sheet, video and archive of original frames differed. The blind bundle omitted those three files and matched the other 12 byte for byte. [Candidate-visible inventories and SHA-256 digests](checks/visual-input-audit.json)

### 2026-11-27

Checked the native Oddish completion record for all 15 model runs on this scene. Every agent reached its answer, every numerical reward was valid, and the runner recorded no execution exception. This check covers provider and agent termination independently of the mesh and public-test checks. [Native completion records](checks/native-model-completion.json)
