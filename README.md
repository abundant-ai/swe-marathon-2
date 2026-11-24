<p align="center">
  <img src="assets/repo-icon.png" alt="SWE-Marathon v2: a running track shaped like an M with two checkpoints" width="180">
</p>

# SWE-Marathon v2

SWE-Marathon v2 evaluates agents on engineering and research tasks that require
several days of work, often across multiple turns.

## Start here

Read [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow from an idea to a runnable
task, and [resources/requirement.md](resources/requirement.md) for task requirements
and development rules.

Task sources live in `tasks/<family>/<task>/`. Start with the task's `README.md`
and its `steps/<step>/instruction.md`. Authoring skills are in
[resources/skills/](resources/skills/).

Harbor’s native user simulation lets the developer ask the product
owner questions during a Harbor trial. Each task supplies a private Markdown
prompt with the user's profile, hidden information and responding rules.
The [Enterprise Knowledge Work Assistant](tasks/enterprise/knowledge-work-assistant/README.md) uses this setup to build Orange in one task on upstream Harbor.

## Local setup and checks

Use Python 3.13 and uv 0.13.7.

```bash
git clone https://github.com/abundant-ai/swe-marathon-2.git
cd swe-marathon-2
uv sync --frozen
```

This creates `.venv` with the locked development dependencies, including Ruff.
Run project commands from the repository root with `uv run --frozen ...`.

Commits run `ruff format .` and `ruff check --fix .`. Link the hook once after
cloning:

```bash
ln -sfn ../../.githooks/pre-commit .git/hooks/pre-commit
```

See [commit checks](resources/CI.md).

### Optional tools

Install Oddish CLI for remote trials. It requires access to the private Oddish
repository and runs in its own tool environment:

```bash
uv tool install "oddish @ git+https://github.com/abundant-ai/oddish.git@main#subdirectory=oddish"
```

Run it as `oddish ...`. Follow [Oddish guidance](resources/ODDISH.md) for packaging
and running a task.

For Titans work, install the optional dependency group from the
[public Abundant Titans repository](https://github.com/abundant-ai/titans):

```bash
uv sync --frozen --group titans
```

Include `--group titans` when running or syncing that environment.

The [Titans training task](tasks/swe-m2-ai-research/titans-training/README.md)
uses the published `pretrain` API from library commit `e277e2b` or a compatible
newer checkout. The dependency pin above still predates that API. To run the
offline CPU probe against a local checkout without changing the lockfile:

```bash
uv run --frozen --no-sync --with-editable /path/to/titans python \
  tasks/swe-m2-ai-research/titans-training/scripts/check_train_eval.py
```

For application code importing `titans_task`, add
`tasks/swe-m2-ai-research/titans-training/common` to `PYTHONPATH`. The probe sets
that import path itself. It uses synthetic text and tiny decoders, not a GPU or
the production training corpus.

Prepare the fixed FineWeb-Edu, PG19 and WikiText token streams once before
pretraining. The `titans-data` group adds the pinned Parquet reader; this command
uses the same local library checkout:

```bash
uv run --frozen --group titans-data --with-editable /path/to/titans python \
  tasks/swe-m2-ai-research/titans-training/scripts/prepare_data.py
```

The default output is the task's Git-ignored `experiment/data/`, with downloads
cached in `experiment/source-cache/`. Use `--output-dir` for a fresh destination
or `--validate-only` to check existing token files. Train/eval load those files
without tokenizing text. To run the preparation checks and audit the full output:

```bash
uv run --frozen --group titans-data --with-editable /path/to/titans python \
  tasks/swe-m2-ai-research/titans-training/scripts/check_preparation.py \
  --data-dir tasks/swe-m2-ai-research/titans-training/experiment/data
```

For a local export of an experiment's persisted JSONL metrics:

```bash
uv run --frozen --no-sync --with matplotlib==3.10.7 python \
  tasks/swe-m2-ai-research/titans-training/scripts/plot_training.py \
  /path/to/metrics.jsonl --output /path/to/learning-curves.png
```
