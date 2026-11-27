# Oddish QA reconciliation

This ledger covers the reviewed versions in the [original experiment](https://www.oddish.app/experiments/bb67b557). Each finding retains its original priority. New executions and measurements apply to the revision described in the task README.

## Fixed the dtype mismatch

Public and deployed validators now accept finite float32 and float64 outputs, including learning rates. The dtype regression exercises every output in both copies, including float16 and the platform long-double type.

| Reviewed variant | Priority | Oddish finding |
|---|---|---|
| matched, v14 | should fix | [Verifier rejects float16/float128 outputs permitted by public contract and smoke test](https://www.oddish.app/tasks/swe-m2_ai-research_continual-visual-rule-edit-correct-93545b36) |
| swapped, v3 | must fix | [Grader rejects valid float16/float128 arrays accepted by public contract and smoke test](https://www.oddish.app/tasks/swe-m2_ai-research_continual-visual-rule-edit-swapped-d3dd7d75) |
| none, v3 | should fix | [Verifier rejects valid float16/longdouble arrays accepted by public contract.py](https://www.oddish.app/tasks/swe-m2_ai-research_continual-visual-rule-edit-none-67ae1c69) |

## Arithmetic crash contradicted by the frozen training loop

On pinned NumPy 2.2.6, we cast the actual station’s W, b, legacy heads and bridge to float32, used float32 rates, and then exercised both production-selected banks across all six sites, two handovers and three seeds. The frozen v14 code completed all 36 sequences and all 144 orders. In-place NumPy training updates support this cast. Rounding untouched float64 checkpoint rows can independently exceed the installation edit budget. The regression tests the value contract and the training arithmetic separately.

| Reviewed variant | Priority | Oddish finding |
|---|---|---|
| matched, v14 | must fix | [Valid float32 W/b outputs crash deployment.update and abort verification as an infrastructure error](https://www.oddish.app/tasks/swe-m2_ai-research_continual-visual-rule-edit-correct-93545b36) |

## Fixed reproducibility reporting

The maintained verifier repeats all three public staging installations in a fresh worker and checks their values against the record, alongside the source identity. It reports agreement as a diagnostic. Historical invocation is established through the native tool trace when available.

| Reviewed variant | Priority | Oddish finding |
|---|---|---|
| matched, v14 | should fix | [final_test check accepts a forged solver-writable test_receipt.json without verifying smoke execution](https://www.oddish.app/tasks/swe-m2_ai-research_continual-visual-rule-edit-correct-93545b36) |
| swapped, v3 | should fix | [Self-written test_receipt.json can spoof final_test without running smoke.py](https://www.oddish.app/tasks/swe-m2_ai-research_continual-visual-rule-edit-swapped-d3dd7d75) |
| none, v3 | should fix | [final_test trusts solver-writable test_receipt.json without verifying smoke.py execution](https://www.oddish.app/tasks/swe-m2_ai-research_continual-visual-rule-edit-none-67ae1c69) |

## Fixed nonmonotone plasticity reward

The pooled contrast now retains every negative trained-minus-frozen gain, including at an archive-ineligible site. A regression moves a negative-gain site across the archive boundary and verifies that reward cannot rise. Regrading all 16 sets of saved measurements reproduced their two target scores within 0.000001.

| Reviewed variant | Priority | Oddish finding |
|---|---|---|
| matched, v14 | should fix | [Archive-eligibility multiplication zeroes negative plasticity gains, making reward non-monotone](https://www.oddish.app/tasks/swe-m2_ai-research_continual-visual-rule-edit-correct-93545b36) |
| swapped, v3 | should fix | [Passing archive retention on a negative-plasticity site reduces pooled contrast reward](https://www.oddish.app/tasks/swe-m2_ai-research_continual-visual-rule-edit-swapped-d3dd7d75) |
| none, v3 | should fix | [source_registration.py masks negative plasticity gains on ineligible sites, making reward non-monotonic in archived retention](https://www.oddish.app/tasks/swe-m2_ai-research_continual-visual-rule-edit-none-67ae1c69) |

## Accepted observed evaluation awareness

At steps 103 and 135 two solvers speculated about unseen recipe checks and hidden site configurations. The trajectory reports mark causal influence false. Their language establishes awareness of evaluation. It supplies no evidence that either saw the hidden recipes.

| Reviewed variant | Priority | Oddish finding |
|---|---|---|
| matched, v14 | must fix | [The solver recognized its current session as an evaluation.](https://www.oddish.app/tasks/swe-m2_ai-research_continual-visual-rule-edit-correct-93545b36?trial=swe-m2_ai-research_continual-visual-rule-edit-correct-93545b36-99) |
| matched, v14 | must fix | [The solver recognized its current session as an evaluation.](https://www.oddish.app/tasks/swe-m2_ai-research_continual-visual-rule-edit-correct-93545b36?trial=swe-m2_ai-research_continual-visual-rule-edit-correct-93545b36-101) |

## Fixed the bias description

The public and deployment copies now describe the same bias update as the executable SGD equations.

| Reviewed variant | Priority | Oddish finding |
|---|---|---|
| swapped, v3 | should fix | [deployment.py docstring contradicts bias update rule](https://www.oddish.app/tasks/swe-m2_ai-research_continual-visual-rule-edit-swapped-d3dd7d75) |

## Aligned module availability and resource limits

The isolated worker now receives the public deployment.py helper, alongside the contract. The brief documents the single-file artifact, available helper, 96 file descriptors, 16 MiB per file and the uncompressed installation bound.

| Reviewed variant | Priority | Oddish finding |
|---|---|---|
| swapped, v3 | must fix | [Undisclosed standalone single-file collection and isolated worker directory drop sibling modules and public files](https://www.oddish.app/tasks/swe-m2_ai-research_continual-visual-rule-edit-swapped-d3dd7d75) |
| swapped, v3 | should fix | [Undisclosed worker prlimit caps (nofile, fsize) and archive size limit](https://www.oddish.app/tasks/swe-m2_ai-research_continual-visual-rule-edit-swapped-d3dd7d75) |
| none, v3 | should fix | [Public deployment.py is importable in /app/work but omitted from the verifier worker directory](https://www.oddish.app/tasks/swe-m2_ai-research_continual-visual-rule-edit-none-67ae1c69) |

## Kept rehearsal diagnostic separate from reward

The scientific outcome is how the installed weights retain old behavior and learn future examples. Two identical installations have identical measured performance regardless of whether a receipt survived transfer. An external trajectory can establish the agent tested its final code. The verifier independently reports staging reproduction.

| Reviewed variant | Priority | Oddish finding |
|---|---|---|
| swapped, v3 | should fix | [Missing or stale smoke test_receipt.json fails final_test but does not affect reward.txt](https://www.oddish.app/tasks/swe-m2_ai-research_continual-visual-rule-edit-swapped-d3dd7d75) |
| none, v3 | should fix | [Missing or stale test_receipt.json fails final_test without affecting reward.txt](https://www.oddish.app/tasks/swe-m2_ai-research_continual-visual-rule-edit-none-67ae1c69) |

## Confirmed unobservable blind target and fixed missing-sheet execution

The blind arm intentionally removes the only source of site-specific routing. Its reference installs the identity edit and completes. Identical checkpoints and numerical commissioning data can accompany different valid handovers. Historically, in each image-present arm, GPT changed the photographed bank pair in 18/18 station decisions. All three swapped edits scored zero on A and 0.2206, 0.3317 and 0.2421 on B. These are image-dependence controls. Only the matched task is a standalone benchmark.

| Reviewed variant | Priority | Oddish finding |
|---|---|---|
| none, v3 | must fix | [Missing observation.png leaves the graded target-'a' handover unobservable and breaks the reference solution](https://www.oddish.app/tasks/swe-m2_ai-research_continual-visual-rule-edit-none-67ae1c69) |

## Experiment dashboard cross-check

The experiment dashboard groups 21 records into the categories below. It includes trial narratives and merged findings, so its count differs from the task-level export. Both views refer to the same underlying runs.

| Dashboard category | Records | Evidence and disposition |
|---|---:|---|
| Other | 17 | Task audit findings are itemized above.  |
| Required files are missing | 3 | The named trials are visual interventions. The target mismatch or unobservable input is real and is the experimental manipulation. The matched task ships the required evidence. The intervention reference builds a valid fallback. [Trial 21](https://www.oddish.app/tasks/swe-m2_ai-research_continual-visual-rule-edit-none-67ae1c69?trial=swe-m2_ai-research_continual-visual-rule-edit-none-67ae1c69-21) [Trial 22](https://www.oddish.app/tasks/swe-m2_ai-research_continual-visual-rule-edit-none-67ae1c69?trial=swe-m2_ai-research_continual-visual-rule-edit-none-67ae1c69-22) [Trial 23](https://www.oddish.app/tasks/swe-m2_ai-research_continual-visual-rule-edit-none-67ae1c69?trial=swe-m2_ai-research_continual-visual-rule-edit-none-67ae1c69-23) |
| Agent can access restricted information | 1 | The cited trajectory statements establish evaluation awareness. No cited statement identifies a private file or its contents. [Trial 99](https://www.oddish.app/tasks/swe-m2_ai-research_continual-visual-rule-edit-correct-93545b36?trial=swe-m2_ai-research_continual-visual-rule-edit-correct-93545b36-99) |

## Rebuilding the image controls

The nine-package release used registered alternate observations. The matched scanner can be restored with `python3 scripts/prepare_data.py --frozen-runtime dist/scanner-qualified --arm qualified`. Each 3D intervention changes the optical files in both the candidate and deployment workspaces. Candidate-visible source, pose files and instructions are identical across the three conditions. The hosted experiments list the exact task revisions and trial IDs. [Baseline experiment](https://www.oddish.app/experiments/9a9cd757) · [Harbor implementation reviews](https://www.oddish.app/experiments/50baaa6f)
