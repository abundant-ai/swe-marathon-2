# Commit checks

`ci_checks` and the GitHub Actions workflows are gone.

A commit runs these commands from the repository root:

```bash
uv run --frozen ruff format .
uv run --frozen ruff check --fix .
```

The hook is [`.githooks/pre-commit`](../.githooks/pre-commit). After cloning, link it once:

```bash
ln -sfn ../../.githooks/pre-commit .git/hooks/pre-commit
```

`ruff check --fix` still exits with an error when it cannot fix a problem, and that stops the commit. Ruff is in the dev dependency group (`ruff==0.17.6`).
