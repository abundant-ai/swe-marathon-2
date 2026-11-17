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

## Local setup and checks

Use Python 3.13 and uv 0.13.7.

```bash
git clone https://github.com/abundant-ai/swe-marathon-2.git
cd swe-marathon-2
uv sync --frozen
```

This creates `.venv` with the locked development dependencies. Run project
commands from the repository root with `uv run --frozen ...`.

To check repository structure and documentation links:

```bash
uv run --no-project python ci_checks/check_repository.py
```

See [CI guidance](resources/CI.md) for the full checks and test commands.

### Optional tools

Install Oddish CLI for remote trials. It requires access to the private Oddish
repository and runs in its own tool environment:

```bash
uv tool install "oddish @ git+https://github.com/abundant-ai/oddish.git@main#subdirectory=oddish"
```

Run it as `oddish ...`. Follow [Oddish guidance](resources/ODDISH.md) for packaging
and running a task.

For Titans work, install the optional dependency group with access to its private
repository:

```bash
uv sync --frozen --group titans
```

Include `--group titans` when running or syncing that environment.
