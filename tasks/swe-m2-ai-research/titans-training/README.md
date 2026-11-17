# Titans training

The task asks an agent to improve an existing Titans training baseline. The user selected this direction and asked us to find the repository. The objective, evaluation data, compute allowance, and success thresholds below remain proposals until baseline measurements establish a feasible contract.

Use [lucidrains/titans-pytorch](https://github.com/lucidrains/titans-pytorch) as the proposed starting point. It is an unofficial PyTorch implementation under the MIT license. The inspected revision is [`35a549f137548d48aecc26e33c6f8a34a6efc97c`](https://github.com/lucidrains/titans-pytorch/commit/35a549f137548d48aecc26e33c6f8a34a6efc97c), dated November 4, 2026. Pin the source and dependencies when preparing the environment.

The repository provides a Memory as Context transformer, a neural-memory implementation, and an enwik8 training example. Its [tests](https://github.com/lucidrains/titans-pytorch/blob/35a549f137548d48aecc26e33c6f8a34a6efc97c/tests/test_titans.py) cover memory chaining, state equivalence, sampling, and accelerated operations. Their presence does not establish that they pass in the eventual task environment.

The inspected [training script](https://github.com/lucidrains/titans-pytorch/blob/35a549f137548d48aecc26e33c6f8a34a6efc97c/train_mac.py) uses 512-byte sequences, an eight-layer model with width 384, and neural memory in layers 2, 4, and 6. It requests CUDA and enables FlexAttention and accelerated scan. Validation samples a single batch at each validation interval. The script has no checkpoint saving or resume path, and includes extensions beyond the original paper. Treat this revision as the implementation being improved; do not describe its results as a faithful paper reproduction.

Proposed assignment: improve recall of information outside the model's local attention window under a fixed training compute allowance, while preserving ordinary language-modeling quality. Let the candidate investigate the training recipe and memory behavior, then deliver modified source, a trained checkpoint, reproducible configurations, and evidence explaining the improvement. Optimization methods should remain open within disclosed architecture and resource limits.

Before making this candidate-facing, choose a recall dataset or generator with training and development examples, define the evaluation context lengths and answer format, and measure the untouched baseline. The existing enwik8 example supplies a training starting point; it does not establish a long-context recall baseline. If training efficiency becomes the primary objective, use time to a declared quality target instead and revise the contract explicitly.

| Proposed requirement | Evidence and pass condition to specify |
| --- | --- |
| Better long-context recall | Evaluate baseline and submission on the same held-out cases. Declare aggregation across lengths, missing-answer handling, and the required improvement after calibration. |
| Preserved language-modeling quality | Independently compute held-out loss using fixed preprocessing and state-reset rules. Publish the allowed regression. |
| Causal predictions | Changing future input tokens must not change earlier predictions beyond a declared numerical tolerance. Cover memory updates as well as attention. |
| Isolated memory state | A fresh sequence must start from the declared initial state, independently of earlier evaluation examples and batch order. Test-time updates may use only information already available for the prediction. |
| Resource compliance | Measure training cost and peak memory externally on specified hardware. Define whether compilation, evaluation, and exploratory runs consume the allowance. |
| Reproducible artifacts | Reload the submitted checkpoint in a fresh process and rerun evaluation. Record configuration, source revision, seeds, and training provenance. |

Select the GPU model and count, wall-clock allowance, parameter and attention-window limits, permitted changes to memory architecture, data access, and checkpoint policy before implementing dependent checks. Set thresholds from baseline and working-solution measurements across seeds. Include memory-disabled controls to investigate whether any gain depends on the memory mechanism; their expected score is not yet an acceptance criterion.

The [Titans paper](https://arxiv.org/abs/2501.00663) distinguishes outer-loop training from memory updates during inference. [TNT](https://arxiv.org/abs/2511.07343) studies chunk size and training efficiency in test-time memory models and is relevant background for optimization ideas. Neither paper supplies a measured target for this repository and budget.

Status: repository source inspection and initial task design only. No environment, verifier, candidate instruction, or trained baseline has been built or run. GPU feasibility, learning quality, numerical correctness, and achievable improvement remain unverified.

## Development log

### 2026-11-17

Added this task's development log while consolidating the repository layout.
The directory currently contains these design notes only. No task configuration,
candidate instruction, environment, verifier, or oracle is present. The proposed
evaluation data, compute budget, and success thresholds remain unresolved. This
update did not run training or validate the proposal's feasibility.

The repository source and documentation checks passed, including the dated-log
requirement for this draft.

Use a Git-ignored `experiment/` folder here for local experiments when needed.
Record their dated findings in this README and retain reproducible source files
outside the ignored folder when they become part of the task.
