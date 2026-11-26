# Fine-tune Kev for general text decisions

## What we want

Kev is an open decision model: it reads a piece of text and a question with a fixed set of answers, and returns a
calibrated probability for each answer. We use the smallest one, Kev-0.8B, and we want it to be good at the kinds of
decisions described in `/opt/task/domain.md`.

Your goal is to fine-tune Kev on this domain and make it as powerful as possible, without introducing catastrophic
forgetting of what Kev already does, and make sure it generalizes well to samples it has not seen (out-of-distribution
samples), not only to the examples you are given.

Use Kev's own training recipe and code. You have about six hours of wall-clock time on one H100; plan your runs to fit.

## What you have

- Kev's code at `/opt/kev`, installed in the Python environment on your `PATH`. The README's training and fine-tuning
  sections describe the recipe (`python -m kev.train`, `--init_from` to start from a released checkpoint,
  `python -m kev.benchmark` to score one). The `skills/kev-finetune/` guide is written for Modal; here you train
  directly on the local GPU.
- Kev-0.8B at `/opt/models/kev-0.8b`. Its base model, `Qwen/Qwen3.5-0.8B-Base` at revision
  `dc7cdfe2ee4154fa7e30f5b51ca41bfa40174e68`, is in the local Hugging Face cache. Everything runs offline.
- Kev's own training suite, decision-v7, at `/opt/kev/evals/v7/decision-v7` (train, calibration and development
  partitions).
- 20 labelled examples from the target domain in `/opt/task/public-20.jsonl`, in Kev's request format.
- A teacher model for making training data: Claude Fable 5.2 (`claude-fable-5-2`) through the Anthropic API, with the
  key in the environment variable `KEV_ANTHROPIC_API_KEY`. The Anthropic SDK is installed, and the API also answers
  OpenAI-style chat requests at `https://api.anthropic.com/v1/`. This API is the only network access you have.
- `/scratch` for checkpoints, datasets, logs and other working files.

## Deliverables

- `/app/model/`: the fine-tuned model as a Kev LoRA checkpoint, the files `kev.train` writes
  (`adapter_config.json`, `adapter_model.safetensors`, `head.pt`), on `Qwen/Qwen3.5-0.8B-Base` at the revision above.
  It must load with Kev's own loader, for example `python -m kev.benchmark --run /app/model ...`. Full-weight
  checkpoints are not accepted.
- `/app/train/`: the data generation and training code and the exact commands and configuration of the run that
  produced `/app/model/`, enough to repeat it.
- `/app/REPORT.md`: what you tried, every training run and its result, how you measured generalization and forgetting,
  and the scores of the released Kev-0.8B and your model on the held-out data you used.

We will judge the delivered model on questions from this domain that you have not seen. Keep `/app` to these
deliverables and the files they need.
