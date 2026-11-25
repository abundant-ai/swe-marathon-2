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

Tasks with fixed instructions live under `tasks/static/<category>/<task>/`. The
categories are `library_build`, `app_clone`, `app_building`, `ai_research`,
`game_dev`, and `robotics`. Tasks that
run with a simulated user live in [tasks/usersim/](tasks/usersim/). Both contain
a version of Orange. Start with the README in the task you want to run.
A single-step task starts from `instruction.md` at its root. Multi-step tasks
keep the briefs under `steps/<step>/`. Authoring skills
are in [resources/skills/](resources/skills/).

## Local setup and checks

Use Python 3.13 and uv 0.13.7.

```bash
git clone https://github.com/abundant-ai/swe-marathon-2.git
cd swe-marathon-2
uv sync --frozen
```

This creates `.venv` with the locked development dependencies. Run project
commands from the repository root with `uv run --frozen ...`.

Ruff checks staged Python files before commit. To enable the
[commit hook](resources/CI.md) in a new clone, use this command.

```bash
git config core.hooksPath .githooks
```

### Optional tools

Install Oddish CLI for remote trials. It requires access to the private Oddish
repository and runs in its own tool environment:

```bash
uv tool install "oddish @ git+https://github.com/abundant-ai/oddish.git@main#subdirectory=oddish"
```

Run it as `oddish ...`. Follow [Oddish guidance](resources/ODDISH.md) for packaging
and running a task.
