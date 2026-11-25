# Ruff

The [pre-commit hook](../.githooks/pre-commit) checks the formatting and lint
of staged Python files. Enable it in a new clone with
`git config core.hooksPath .githooks`.

Run these commands to apply fixes before staging a file.

```sh
uv run --frozen ruff check --fix path/to/file.py
uv run --frozen ruff format path/to/file.py
```
