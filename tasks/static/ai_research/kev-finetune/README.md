# Kev fine-tune: general text decisions (author notes)

Author-only. Nothing here ships in the bundle or either image.

## What the task asks

The agent starts from the released Kev-0.8B (a LoRA adapter plus pointer head on `Qwen/Qwen3.5-0.8B-Base`) and has six
hours on one H100 to fine-tune it, with Kev's own training recipe, for the decision domain of Kev's transfer-v4 suite.
It sees a plain description of that domain (`environment/resources/domain.md`), 20 labelled examples drawn from
transfer-v4's development partition (`environment/resources/public-20.jsonl`), Kev's training suite decision-v7 and
Claude Fable 5.2 as a data generator. The instruction follows the researcher's wording: as strong as possible on the
domain, no catastrophic forgetting, generalize to samples it has not seen.

This is a first trial build. Per the researcher, no oracle is written before seeing how a model does; the solution
script only delivers the unchanged checkpoint, which measures the starting point.

## Sources and pins

| Item | Pin |
| --- | --- |
| Kev code | `github.com/jaredpalmer/kev` @ `556167b5b151152cb4101629e25d883e9ead5094` (Apache-2.0) |
| Kev-0.8B | `jaredpalmer/kev-0.8b` @ `bf75a6a8848ea6960ff2ed108d9ed44c2941174f` (training_config: run `r15-08b`, the run behind the published 0.648 / 0.697) |
| Base | `Qwen/Qwen3.5-0.8B-Base` @ `dc7cdfe2ee4154fa7e30f5b51ca41bfa40174e68` (Apache-2.0) |
| decision-v7 train | fetched by Kev's loader from `jaredpalmer/kev-suites` @ `cc4bac80…`, sha256 `7ed5254b…` matches the manifest |
| transfer-v4 test | in Kev's git, sha256 `c30a9127…` per manifest, 764 records (656 clean) |

The transfer-v4 sources keep their own licences (MMLU, SciQ, dair-ai/emotion, TweetEval, QNLI, PAWS); SciQ is
CC BY-NC 3.0. Fine for an internal trial; check before any release.

## Verification and reward

`tests/verify.py` (root) stages `adapter_config.json`, `adapter_model.safetensors` and `head.pt`
from `/app/model` through lstat and O_NOFOLLOW checks with size caps, then `grader.py` runs as uid 10021, offline:

1. checks Kev's three locked partitions against their manifest hashes (failure: no reward, exit 1);
2. loads `head.pt` with `weights_only=True` and requires `base = Qwen/Qwen3.5-0.8B-Base`, the pinned revision and
   `weights = lora`;
3. runs `python -m kev.benchmark` (fp32, Kev's own scoring) on transfer-v4 test (`--allow-test`), transfer-v4
   development and decision-v7 test.

**Reward = clean accuracy on transfer-v4 test** (`report["clean"]["acc"]`, 656 questions, argmax of the model's
probabilities against the stored label, every question weighted equally). A missing, malformed or wrong-base
checkpoint, or one Kev cannot load or score, gets 0 with the reason in `metrics.json`. transfer-v4 development and
decision-v7 test (the forgetting check) are recorded in `metrics.json` and do not enter the reward.

Limits of the reward: about 73% of the test comes from public datasets with human or automatic labels, some of them
wrong (MMLU and the hashtag-labelled emotion set are known to be noisy), so the ceiling is below 1. With 656
questions, one standard error is about 1.8 points; differences under about 4 points between two runs are not
meaningful.

## Hackability assessment

| Finding | Boundary | Evidence | Mitigation | Residual | Severity |
| --- | --- | --- | --- | --- | --- |
| Download the public transfer-v4 test or Kev's suites and train on them | agent network | `task.toml` allowlist has only `api.anthropic.com`; GitHub, HF and PyPI closed | allowlist | Oddish enforces the allowlist; not exercised yet | 🟡 UNASSESSED |
| Test or development material shipped inside the image | image contents | `scripts/leak_scan.py` over the shipped Kev subset, decision-v7 train and the Kev-0.8B card files: 0 of 2,186 text needles (raw and JSON-escaped) and 0 of 4 generator seeds; the same scan finds 1,682 hits in Kev's `evals/v4` and the seeds in `kev/study_v3.py` | only the paths in `environment/kev-files.txt` ship; `kev/study_v3.py` and `kev/transfer_v9.py` (the builders that regenerate held-out rule records) are removed | the scan is on the local pruned tree, not yet on the built image | 🟢 LOW |
| Regenerate the held-out rule records with Kev's generators | `kev/composition.py`, `kev/contrastive.py` | the held-out shapes and families are defined there; their seeds (`v3-locked`, `20260920-eval`) are absent from shipped files | builders and seeds removed | an agent can still generate unlimited records of the same families with its own seeds, which is legitimate in-domain data but makes 27% of the test easier than the rest; guessing the exact seed is possible in principle | 🟡 MEDIUM |
| Ask the teacher to recall the public test items (MMLU, SciQ…) | teacher API | the README in `/opt/kev` names transfer-v4's sources | none in the instruction | contamination through the teacher's memory; to check by comparing generated data against the test after the trial | 🟡 MEDIUM |
| Deliver a different or bigger model | verifier checkpoint check | `grader.py` requires the base and revision and LoRA weights; the base itself comes from the verifier image | base fixed by the verifier | a very high LoRA rank is allowed (still a fine-tune of the same base) | 🟢 LOW |
| Code execution through the checkpoint | verifier load | `head.pt` loaded with `weights_only=True`, adapter as safetensors, both under an unprivileged uid with no network; tokenizer comes from the base | as stated | not adversarially exercised | 🟡 UNASSESSED |
| Tamper with the reward | verifier | separate verifier image; no candidate code runs; reports read through lstat and O_NOFOLLOW | separation | — | 🟢 LOW |

Highest unresolved severity: 🟡 MEDIUM (generator families, teacher recall); network and checkpoint-load boundaries are
unassessed until the first runs.

## Development log

### 2026-11-27

- The researcher asked for: Kev-0.8B measured on transfer-v4 (dev and test separately), a high-level summary of the
  transfer-v4 domain, 20 public examples from transfer-v4 development, and a trial with Opus 5.5 before any oracle,
  reward = % solved on transfer-v4 test, using Kev's training recipe.
- Read Kev's scoring code (`kev/metrics.py`, `kev/benchmark.py`): accuracy is the mean over clean questions of argmax
  == label; 108 of 764 records per partition are permuted / none-of-these variants used only for robustness checks.
  Kev's release run file (`runs/release/kev-08b-r15.json`) gives 0.6479 dev and 0.6966 test on 656; the HF checkpoint's
  training_config names the same run. Not yet reproduced by us; the baseline solution run will do that.
- Drew `public-20.jsonl` with `scripts/sample_public.py` (seed 20261127, stratified by question source, largest
  remainder): 15 public-dataset and 5 generated records; ids in `experiment/authoring/public-20.ids.json`.
- Wrote `domain.md`, checked against the test partition's sources (the test's rule records use other shapes and a
  different wording from the development ones, including day counts between dates).
- Built the agent and verifier Dockerfiles, `verify.py` / `grader.py`, the baseline `solve.sh`, `task.toml` (6 h agent,
  H100, allowlist `api.anthropic.com`) and `scripts/package_task.py`. Leak scan clean (above). Oddish preflight
  passed on the packaged bundle.
- Local checks on an arm64 build of the agent image (Python 3.12, no GPU kernels), run as `candidate` with
  `--network none`: Kev imports; `/opt/kev` holds no `evals/v4` and no `study_v3.py`; `kev.benchmark --run
  /opt/models/kev-0.8b --data /opt/task/public-20.jsonl --device cpu` scores 0.70 on the 20 public records (17 s);
  `kev.train --data public-20 --init_from /opt/models/kev-0.8b` finishes offline on CPU in 56 s and writes a LoRA
  checkpoint whose `head.pt` loads with `weights_only=True` and names the pinned base. The verifier's staging refuses
  a symlinked file, a FIFO, a symlinked `/app/model`, a missing file and a missing directory (local unit run).
- That CPU run printed that `causal_conv1d` and `flash-linear-attention` were missing, so Qwen3.5's DeltaNet layers
  ran on reference code. Kev's own GPU image (`modal_app.py`) installs fla 0.5.2, triton ≥ 3.7.1 and the
  causal-conv1d 1.7.0 cp313 wheel on Python 3.13; both images now do the same (triton pinned to 3.7.1), so training
  speed and scoring match the setup behind Kev's published numbers.
- Moved to main's layout: `tasks/static/ai_research/kev-finetune/` with `instruction.md`, `tests/` and `solution/`
  at the root and no `[[steps]]`; added `checks/test_kev_finetune_package.py` (staging refusals, pins shared by both
  images and the grader, no held-out paths in `kev-files.txt`, bundle contents), registered in the root pytest paths.
  10 checks pass; ruff clean; Oddish preflight passes on the bundle.
- Pending: amd64 builds of both images, then Oddish runs: the baseline solution (reproduces
  Kev-0.8B's numbers), the nop (expects 0), and two Opus 5.5 trials.
