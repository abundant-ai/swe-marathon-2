# Train Kev for short-text decisions

## What we want

Kev is an open decision model: it reads a piece of text and questions with fixed sets of answers, and returns a
probability for each answer. We use the smallest one, Kev-0.8B. Train it on the domains described in
`/opt/task/domain.md`, the way a world-class researcher would, so that it answers questions from those domains as
well as possible.

Use Kev's own training code and recipe. You have about six hours of wall-clock time on one H100; plan your runs to fit.

## What you have

- Kev's code at `/opt/kev`, installed in the Python environment on your `PATH`: `python -m kev.train` (with
  `--init_from` to start from a released checkpoint) and `python -m kev.benchmark` to score one. The README describes
  the recipe. The `skills/kev-finetune/` guide is written for Modal; here you train directly on the local GPU.
- Kev-0.8B at `/opt/models/kev-0.8b`. Its base model, `Qwen/Qwen3.5-0.8B-Base` at revision
  `dc7cdfe2ee4154fa7e30f5b51ca41bfa40174e68`, is in the local Hugging Face cache. Everything runs offline.
- 20 labelled examples from the target domains in `/opt/task/public-20.jsonl`, in Kev's request format.
- A teacher model for making training data: Claude Fable 5.2 (`claude-fable-5-2`) through the Anthropic API. The key is
  in `KEV_ANTHROPIC_API_KEY` and the address in `KEV_ANTHROPIC_BASE_URL`; pass both to the client explicitly
  (`anthropic.Anthropic(api_key=..., base_url=...)`), because other `ANTHROPIC_*` variables in your shell belong to
  your own session. Replies start with a thinking block before the text. This API is the only network access you have.
- `/scratch` for checkpoints, datasets, logs and other working files.

## Deliverables

- `/app/model/`: the trained model as a Kev LoRA checkpoint, the files `kev.train` writes (`adapter_config.json`,
  `adapter_model.safetensors`, `head.pt`), on `Qwen/Qwen3.5-0.8B-Base` at the revision above. It must load with
  `python -m kev.benchmark --run /app/model ...`. `/app/model` must be a real directory and the three files regular
  files, not symbolic links; `adapter_config.json` may be up to 1 MiB, `adapter_model.safetensors` up to 4 GiB and
  `head.pt` up to 256 MiB. Full-weight checkpoints are not accepted.
- `/app/train/`: the data generation and training code and the exact commands and configuration of the run that
  produced `/app/model/`, enough to repeat it.
- `/app/REPORT.md`: what you tried, every training run and its result, and how the released Kev-0.8B and your model
  compare on the data you checked them with.

The model is only accepted with a non-empty `/app/train/` and `/app/REPORT.md`. `/app/REPORT.md` must be a regular
file and `/app/train/` must hold at least one regular file; symbolic links are not followed. Keep `/app` to these
deliverables and the files they need.
