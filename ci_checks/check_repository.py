"""Run v2 structure, source syntax, and contributor documentation checks."""

from __future__ import annotations

import ast
from pathlib import Path
import re
import subprocess
import tomllib
from urllib.parse import unquote, urlsplit

from check_v2_task import check_task, check_task_notes
from check_test_inventory import check_registration


def source_files(root: Path) -> list[Path]:
    """List tracked and new nonignored files without inspecting generated inputs.

    Args:
        root: Git checkout whose index and ignore rules define source files.

    Returns:
        Sorted existing paths, including local unstaged additions.

    Raises:
        subprocess.CalledProcessError: The directory is not a readable checkout.
    """
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root, check=True, capture_output=True, text=True,
    )
    return sorted({root / name for name in result.stdout.split("\0")
                   if name and (root / name).is_file()})


def check_links(path: Path, root: Path) -> list[str]:
    """Validate local Markdown link targets in contributor-facing documentation.

    Args:
        path: UTF-8 Markdown document; fenced code examples are excluded.
        root: Repository root used to prevent links escaping the checkout.

    Returns:
        Missing or out-of-repository targets. External URLs and fragment-only
        links are not fetched; anchor spelling is left to review.
    """
    text = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.DOTALL)
    errors: list[str] = []
    for target in re.findall(r"\]\(([^\s)]+)\)", text):
        parsed = urlsplit(target.strip("<>"))
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        destination = (path.parent / unquote(parsed.path)).resolve()
        if not destination.is_relative_to(root.resolve()) or not destination.exists():
            errors.append(f"{path.relative_to(root)}: broken local link: {target}")
    return errors


def check_repository(root: Path) -> list[str]:
    """Check every source file and configured task, including documentation-only PRs.

    Args:
        root: Repository checkout with all task material under tasks/<family>/<task>.

    Returns:
        Syntax, missing layout, and link errors. No configured tasks is an error,
        while design-only tasks receive development-log and source syntax checks.
    """
    errors: list[str] = []
    files = source_files(root)
    errors.extend(check_registration(root, files))
    configurations = [path for path in files if path.relative_to(root).parts[0] == "tasks"
                      and path.name == "task.toml"]
    if not configurations:
        errors.append("No configured v2 tasks found under tasks/<family>/<task>/")
    for config in configurations:
        relative = config.relative_to(root)
        if len(relative.parts) != 4 or relative.parts[1] in {"v1", "v1_1", "v2"}:
            errors.append(f"{relative}: expected tasks/<family>/<task>/task.toml")
            continue
        errors.extend(f"{relative.parent}: {error}" for error in check_task(config.parent))
    task_directories = {
        root.joinpath(*path.relative_to(root).parts[:3])
        for path in files
        if len(path.relative_to(root).parts) >= 4
        and path.relative_to(root).parts[0] == "tasks"
    }
    configured_directories = {config.parent for config in configurations}
    for task in sorted(task_directories - configured_directories):
        errors.extend(f"{task.relative_to(root)}: {error}" for error in check_task_notes(task))
    for path in files:
        relative = path.relative_to(root)
        try:
            if path.suffix == ".py":
                ast.parse(path.read_text(encoding="utf-8"), filename=str(relative))
            elif path.suffix == ".toml" or path.name == "uv.lock":
                tomllib.loads(path.read_text(encoding="utf-8"))
            elif path.suffix == ".sh":
                process = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
                if process.returncode:
                    errors.append(f"{relative}: {process.stderr.strip()}")
            elif path.suffix == ".md" and (relative.parts[0] == "resources" or
                                          relative.as_posix() in {"AGENTS.md", "README.md", "CONTRIBUTING.md"}):
                errors.extend(check_links(path, root))
        except (OSError, UnicodeError, SyntaxError, tomllib.TOMLDecodeError) as exc:
            errors.append(f"{relative}: {exc}")
    for name in ("README.md", "CONTRIBUTING.md", "resources/requirement.md", "resources/task-implementation.toml"):
        if not (root / name).is_file():
            errors.append(f"Missing contributor resource: {name}")
    print(f"Checked {len(files)} source files and {len(configurations)} configured v2 task(s)")
    return errors


def main() -> int:
    """Report repository findings and fail on any structural or syntax error."""
    root = Path(__file__).resolve().parents[1]
    errors = check_repository(root)
    for error in errors:
        print(error)
    if not errors:
        print("Repository checks passed")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
