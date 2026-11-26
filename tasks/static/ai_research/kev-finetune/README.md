# Kev fine-tune

Author-only; not part of the bundle or either image.

The agent fine-tunes the released Kev-0.8B (LoRA plus pointer head on `Qwen/Qwen3.5-0.8B-Base`) with Kev's own
training recipe for the decision domain of Kev's transfer-v4 suite. It gets a domain summary, 20 public examples from
transfer-v4 development, decision-v7, Claude Fable 5.2 for data generation, and six hours on one H100.
`solution/solve.sh` delivers the released checkpoint unchanged as a baseline; there is no oracle yet.

Pins: Kev `556167b5`, Kev-0.8B `bf75a6a8` (the release run behind the published 0.648 / 0.697), Qwen base `dc7cdfe2`.
SciQ in transfer-v4 is CC BY-NC 3.0; check before any release.

## Reward

The verifier stages `adapter_config.json`, `adapter_model.safetensors` and `head.pt` from `/app/model`, checks for the
pinned base and LoRA weights, and runs `kev.benchmark` offline as an unprivileged uid.

**Reward = clean accuracy on transfer-v4 test** (656 questions, argmax against the stored label, equal weights). A
missing, malformed or wrong-base checkpoint, or one Kev cannot load, scores 0. transfer-v4 development and decision-v7
test (forgetting) are recorded in `metrics.json` only. About 73% of the test uses public labels, some of them wrong, so
the ceiling is below 1; one standard error is about 1.8 points.

## Hackability assessment

| Finding | Mitigation | Severity |
| --- | --- | --- |
| Fetch the public test or Kev's suites | allowlist is `api.anthropic.com` only; not yet exercised on Oddish | 🟡 UNASSESSED |
| Held-out material shipped in the image | only `environment/kev-files.txt` paths ship; `study_v3.py` and `transfer_v9.py` removed; `scripts/leak_scan.py` finds 0 of 2,186 text needles and 0 of 4 seeds (1,682 hits on Kev's `evals/v4`) | 🟢 LOW |
| Generate more records of the held-out rule families | seeds removed; same-family data remains possible and makes 27% of the test easier | 🟡 MEDIUM |
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
- Pending: amd64 builds, then Oddish runs (baseline, nop, 2 × Opus 5.5).
