# One scanner, two stockrooms

The agent trains a CNN on labeled CORe50 captures. At deployment a worker shows the scanner a printed card, counts inventory, changes camera modules, moves to another room and later returns. Rooms use different stock IDs for the same objects. The updater sees only RGB. Each prediction is scored before the updater receives that inventory frame. The agent can test its program on labeled practice footage with separate cards and stock IDs.

## What changed

The previous pilot let a solver identify the camera and select a fixed output permutation. GPT-6.2-sol xhigh earned 1.0 on its first matched-image run. A portable scanner changes the inference problem. Two itineraries now have identical inventory pixels and camera changes. Only the photographed cards distinguish the rooms. One deterministic prediction sequence cannot give both correct IDs for a frame with conflicting targets. The matched, reversed and absent reference-sheet conditions test whether the production photograph helps the agent resolve this ambiguity. A trial can guess the orientation of two cards, so a single successful submission does not establish that its author inspected the photograph. [Earlier experiment](https://www.oddish.app/experiments/2886acf8)

## Design and evidence

| Dimension | Evidence and open questions |
| --- | --- |
| Novelty | The stock-commissioning predecessor coupled the camera and local vocabulary. Here a stock assignment persists across module changes, and a given optical response occurs in both rooms. Broader comparisons with other research benchmarks remain open. |
| Verifiability | The verifier applies submitted weight changes to a trusted CNN, replays source training and pairs identical inventory frames across conflicting itineraries. The paired score uses only frames whose targets differ. A regression test copies the first room's answers in one schedule and checks that credit falls to zero. |
| Realism | The object images come from real handheld CORe50 recordings. A shared scanner, its transfer curves, the cards and stock IDs are simulated. A measured industrial handover would establish how well the simulation represents field conditions. |
| Difficulty | The agent must infer the room and sensor from a noisy chart, preserve the decision after the chart leaves view and protect headquarters recognition. The task reward does not establish five days of research work. Model trials will test whether the change challenges current agents. |
| Feasibility | The reference trains with the public captures, reads the three commissioning images, identifies the chart using patch correspondences and writes the fitted camera correction and stock transformation into the CNN. Each source start must independently satisfy the acceptance criteria. |

The paired check requires both correct IDs on at least 35% of conflicting inventory frames in each schedule. A reward of 1.0 means all declared acceptance thresholds were reached. Actual classification accuracy, frozen accuracy and the matched-frame rate are reported separately. Installation A defines the commissioning targets. Installation B is a counterfactual deployment retained for diagnosis. [Data and licensing](https://vlomonaco.github.io/core50/)

## Reproduction

Build the stock packages with the inventory builder and the original CORe50 mini archive. Run `python -B site_handover/stage.py <stock-package-directory> <new-directory>` from the streaming-CNN task root and then `python -B site_handover/check.py <new-directory>`. The check compares shipped file contents, confirms the exact swapped or missing sheet, and checks corresponding inventory pixels, capture IDs, held-out probe pixels and chart changes in both installations.

## Reward and missing observations

Accuracy is mean recall across the represented stock IDs. For each required comparison, subtract the applicable frozen accuracy from the adapted accuracy. These comparisons cover the full stream, held-out probes, first appearances, and the state paused immediately before relocation. Each fixed start also compares the adapted model to a copy that receives only the changed buffers. The submitted model's frozen comparator is the mean of the two fixed starts. Deduct the largest headquarters accuracy loss beyond 0.02, measured after each chart and at each visit's end. Divide the smallest adjusted gain by 0.10 and clip to [0, 1]. Apply the comparisons to each order and schedule as well as their aggregate.

For each start and schedule, take frames whose two stock IDs differ. Give a hit only when both predictions match their own room's target. Average hits per stock ID separately in each room and take the lower average. Divide by 0.35 and cap at one. The task uses the smallest of the paired and adaptation credits across all required conditions. A candidate-side failure to produce eligible training artifacts or complete the target stream earns zero. A verifier error yields no valid measurement. [Paired implementation](crossed_grade.py) · [Boundary regression](check.py) · [Local measurements](local-replay.json)

## Hackability assessment

| Boundary | Evidence, residual risk and next check |
| --- | --- |
| Room identity from the camera | **Low for deterministic camera-only routing.** The audit checked 720 paired inventory positions in both installations. Each member of a pair has identical bytes and the same capture ID. A single sequence of predictions earns zero paired credit for conflicting IDs. |
| Guessing the two reference-card assignments | **Medium.** An agent that independently recognizes both cards and decodes the stock sheet can guess their two-way correspondence. One matched success cannot establish image use. Compare independently sampled trials across the chart conditions and inspect the delivered source. |
| Editing the evaluator or influencing predictions outside the CNN | **Locally inspected.** Only bounded numerical CNN state crosses the deployment worker boundary. The trusted verifier computes predictions before delivering each stock frame. One detached worker replay checked six real handovers. Hosted verification supplies the separate-container test. |
| Source training and headquarters retention | A clean rebuild, a replay with independently permuted training labels, two fixed starts, buffer-only predictions and post-handover probes test common shortcuts. The public CORe50 corpus can support prior visual knowledge. Fresh camera and stock assignments would test generalization to another commissioning job. |

The highest identified residual risk is guessing a two-room correspondence. Workload and hosted model difficulty require trial evidence. The release evaluation and implementation review have separate records. [Oddish experiment](https://www.oddish.app/experiments/ca5ae79b) · [Harbor review](https://www.oddish.app/experiments/4291df0a)

## November 27, 2026 implementation review

The independent reviewer assessed the exact version 1 matched package plus its local replay evidence. The six hosted controls finished after the review package was assembled. The original ratings are preserved with the input file digests. [Harbor report](https://www.oddish.app/experiments/4291df0a) · [Rated configuration](reviews/v1/task.toml) · [Input digests](reviews/v1/inventory.json) · [Hosted verification](golden-reference.json)

| Dimension | Rating | Confidence | Evidence and remaining gap |
| --- | --- | --- | --- |
| Novelty | Unassessed | Unassessed | The crossed itineraries extend the camera-conditioned predecessor. The reviewer lacked direct comparisons with the other benchmark collections. |
| Verifiability | 3/5 | High | The trusted classifier, buffer-only comparison and matched pixels make numerical performance measurable. Guessing which room owns a card is still possible. |
| Realism | 3/5 | High | Real CORe50 footage supports a recognizable scanner workflow. Card photos, service changes and stock IDs are simulated. |
| Difficulty | 3/5 | Medium | Calibration and memory interact. The pilot has no demonstrated five-day workload. |
| Initial feasibility | 4/5 | High | The public-input solution had a runnable deployment replay at review time. Subsequent clean hosted verification confirms a 1.0 reference on the reviewed version. |

Two findings need qualification. The review correctly reported that its local evidence lacked a clean end-to-end oracle run. Oddish subsequently recorded a valid build, all nine typed checks passing, label-dependent source replay and reward exactly 1.0 on the same package version. The paired-score regression also does exercise the consequence of copying one room's predictions into the other. It first gives full credit to two correct label sequences, copies the first room's predictions into the second on one schedule, and asserts zero total credit. Its scope is the paired boundary. It supplies no evidence about source training, partial credit, or a correct guess at card orientation.

The 30-minute budget and two-room design do not establish the repository's five-day workload. The review also identifies genuine gaps in candidate instructions, submitted-checkpoint weight ablation, diagnostic failure reporting, resource bounds, reproducible author packaging and evidence for image use. These findings apply to version 1. The hosted baseline proof resolves the missing oracle evidence only.

## Recommissioning revision

The first stream frame now pairs the archived room cards with a new printing. Each column of the photograph contains an archived card and its replacement. Changing that photograph changes the stockroom assignment while every later chart and inventory pixel stays identical. Both installations contribute to the reward. For each start, order and schedule, the verifier also requires both correct predictions on 35% of the conflicting frames across installations. A solver that ignores the replacement photograph must earn zero on those pairs. A solver can still guess which archived card belonged to which room in the initial authoring handover.

The submitted CNN now receives the same learned-weight ablation as the fixed starts. The source-label audit fits a visually conditioned vocabulary on two color settings. It evaluates each reserved source frame in both settings and counts a hit when both local IDs are correct. One global output renumbering cannot express both vocabularies on a sensor-invariant classifier. The public trainer achieved 30.4% paired accuracy in a clean local rebuild. The acceptance floor is 15%. This tests data-dependent behavior. It cannot establish which numerical optimizer a trainer used.

The repository authoring tree includes the source and both checkpoint-training seeds. From the streaming-CNN root, run `python -B site_handover/build.py /path/to/core50_32x32.zip /path/to/new-output`. The Oddish task contains only the runtime inputs. The Harbor reviewer receives the separate authoring sources. The oracle and the no-op receipts in golden-reference.json describe version 1. The recommissioning revision needs its own hosted evidence.

The source replay evaluates the changed vocabulary on both images of every held-out capture. An exhaustive check gave each fixed CNN access to the probe labels and tried all 3,628,800 permutations of its ten outputs. The best achievable paired accuracy was 7.1% for one start and 5.8% for the other, below the 15% requirement. This rules out a global output permutation on either tested frozen CNN. A more expressive precomputed visual system remains outside that bound.

The verifier caps each worker at 48 processes and 3 GiB of virtual address space, in addition to the container limits. It removes previous reward files before setup and runs submitted code under a disposable identity. Hosted resource-boundary measurements and repeatability of the revised version remain open.

Local renewal tests returned 1.0 with the correct archived-room references and zero with swapped or absent references. The weakest matched paired accuracy across the two installations was 43.8%. Restoring a single prediction sequence in both installations gave zero on the same 720 inventory positions. A partly correct sequence earned 0.635; missing the second deployment or removing the submitted model's learned-weight advantage gave zero. [Local renewal measurements](renewal-development.json) · [Reward boundary checks](check_reward.py)

| Residual severity | Boundary and next measurement |
| --- | --- |
| 🟢 GREEN / LOW | Identical post-renewal pixels and conflicting targets rule out a deterministic photograph-insensitive policy. The local replay and scoring regression exercise both paths. |
| 🟡 YELLOW / MEDIUM | The initial association between two archived cards and stockrooms can still be guessed. The agent trials and source inspection assess this separately. |
| 🟡 YELLOW / UNASSESSED | The native container separates workers from labels, credentials and reward files. Dedicated UID limits and early reward cleanup are implemented. Direct confirmation of all those boundaries requires hosted evidence. |

A clean rebuild from the original archive regenerated both source checkpoints and the entire three-condition release. All 185 shipped files matched version 2 byte for byte. [Version 2 experiment](https://www.oddish.app/experiments/560dfbfe) · [Rebuild evidence](renewal-development.json)

## Version 2 model results

On the matched preview, GPT-6.2-sol xhigh, DeepSeek v4.1 Flash and GLM 5.3 each earned 0, 0 and 0. One submission from each model completed the numerical evaluation. The other six had candidate-side updater or checkpoint errors. The matched oracle earned 1.0. Both photographic controls and all three no-ops earned zero. This version meets the three-model difficulty threshold. Its review still reports limitations in the typed judgment of partially completed deployments, independent regrading and workload evidence. [Oddish model and control trials](https://www.oddish.app/experiments/560dfbfe) · [Native score attribution](three-model-v2.json) · [Rated review](reviews/v2/task.toml)

Harbor rated verifiability and realism 3/5 with high confidence, difficulty 3/5 with medium confidence, and initial feasibility 4/5 with high confidence. Novelty remains unassessed. The model score measures completion of the full engineering contract. Three failures of complete numerical solutions and six invalid or partial submissions do not establish a five-day workload.
