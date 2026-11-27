# Kev fine-tune

Author-only; not part of the bundle or either image.

The agent trains the released Kev-0.8B (LoRA plus pointer head on `Qwen/Qwen3.5-0.8B-Base`) with Kev's own recipe for
a blended set of decision domains: the task types of Kev's decision-v7 and transfer-v4 suites, described together in
`environment/resources/domain.md` without saying which is which. It gets 20 public examples (10 from each suite's
development partition, source names removed), Claude Fable 5.2 for data generation, and six hours on one H100.
decision-v7's partitions are not shipped. `solution/solve.sh` delivers the released checkpoint unchanged as a baseline
(reward about 0.77); there is no oracle yet.

Pins: Kev `556167b5`, Kev-0.8B `bf75a6a8` (the release run behind the published 0.648 / 0.697), Qwen base `dc7cdfe2`.
SciQ in transfer-v4 is CC BY-NC 3.0; check before any release.

## Reward

The verifier requires a non-empty `/app/REPORT.md` and a non-empty regular file under `/app/train`, stages
`adapter_config.json`, `adapter_model.safetensors` and `head.pt` from `/app/model`, checks for the pinned base and LoRA
weights, and runs `kev.benchmark` offline as an unprivileged uid on the candidate and on the released Kev-0.8B.

**Reward = S**, the mean of the clean accuracies on transfer-v4 test (656) and decision-v7 test (1,200). The released
checkpoint is scored on the same suites in the same run and recorded as `released` and `gain`; it does not change the
reward. The released Kev-0.8B scores S = 0.767, so the baseline in `solution/solve.sh` earns about 0.77 and Kev-4B / Jev
level is about 0.85. A forgetting drop on decision-v7 lowers S directly. Missing records, a malformed or wrong-base
checkpoint, or one Kev cannot load score 0; a grader crash or timeout writes no reward. transfer-v4 development is
recorded only.

## Hackability assessment

| Finding | Mitigation | Severity |
| --- | --- | --- |
| Fetch the public test or Kev's suites | allowlist is `api.anthropic.com` only; not yet exercised on Oddish | 🟡 UNASSESSED |
| Held-out material shipped in the image | only `environment/kev-files.txt` paths ship; `study_v3.py` and `transfer_v9.py` removed; `scripts/leak_scan.py` finds 0 of 4,355 text needles from transfer-v4 and decision-v7 dev and test, and 0 of 7 generator seeds; decision-v7 data is no longer shipped | 🟢 LOW |
| Generate more records of the held-out rule families | v3 trial #13 trained on Kev's own `final_*` test shapes and the locked wording and scored 0.72, about 60% of its gain from those 176 questions; `environment/strip_held_out.py` now removes the six held-out shapes, the locked wrapper and the authorization and deadline generators from the agent's copy. Random structures and the two dev-style examples in `public-20.jsonl` remain | 🟡 MEDIUM |
| Teacher recalls public test items | none; compare generated data with the test after the trials | 🟡 MEDIUM |
| Deliver a different model | base, revision and LoRA weights required; base comes from the verifier image | 🟢 LOW |
| Code execution through the checkpoint | `weights_only=True`, safetensors, unprivileged uid, no network | 🟡 UNASSESSED |
| Tamper with the reward | separate verifier; no candidate code runs | 🟢 LOW |

## Development log

### 2026-11-27

- Built the task, the verifier, the baseline solution and the leak scan; sampled `public-20.jsonl` with
  `scripts/sample_public.py` (seed 20261127, stratified by source).
- Local arm64 build, offline as `candidate`: Kev-0.8B scores 0.70 on the public 20; a short `kev.train --init_from`
  run writes a valid checkpoint. Added Kev's GPU kernels (fla 0.5.2, triton 3.7.1, causal-conv1d 1.7.0, Python 3.13).
- `checks/` passes (10 tests); Oddish preflight passes.
- First Oddish version: 2 × Opus 5.5 trials running (6 h). They use Kev's recipe with decision-v7 replay.

### 2026-11-27 (v2)

- Oddish pre-trial QA raised 8 blocking findings on v1. Changes: reward now covers decision-v7 test as well as
  transfer-v4 test and is the gain over the released Kev-0.8B (the unchanged checkpoint scores 0); the instruction no
  longer mentions forgetting or OOD samples and asks for the work of a world-class researcher on a blended domain;
  `public-20.jsonl` is redrawn from both suites without `src`; calibration wording removed; symlink rule, size limits
  and required records stated; decision-v7 partitions removed from the agent image; `KEV_ANTHROPIC_BASE_URL` added
  after both v1 agents hit an empty `ANTHROPIC_BASE_URL` from the harness.
- Open: no oracle (by choice for now); `/app/train` and `REPORT.md` are checked for presence only.

### 2026-11-27 (v3, v4)

- v3: the verifier image had no C compiler, so triton failed and both v1 trials (#8, #9) were saved as reward 0; added
  `gcc` and `libc6-dev` and pinned `uv` by digest only, after the v2 verifier build rejected a tag plus digest. The
  re-grade of v2 trial #13 scored 0.718 (transfer-v4 test 0.697 → 0.822, decision-v7 test 0.838 → 0.832).
- v4: #13's gain on the rule and policy questions came from Kev's own held-out generators, now stripped from the agent
  image (leak scan clean on the stripped tree). From the v2 pre-trial QA: the reward and the equal weighting of the two
  groups are stated in the instruction, as is the no-symlink rule for `/app/train` and `/app/REPORT.md`;
  grader timeouts and crashes by signal now leave no reward instead of 0, and transfer-v4 development is recorded
  without affecting the reward. Still open by choice: no oracle; `/app/train` and the recipe are checked for presence
  only.
- v4: the reward is absolute accuracy, S, by request; the gain over the released model is recorded only.
