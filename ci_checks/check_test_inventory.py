"""Keep maintained test modules registered and represented in CI evidence."""

from pathlib import Path
import tomllib


def maintained_tests(root: Path, files: list[Path]) -> list[Path]:
    """Find test modules independently of pytest's configured search paths.

    Used by repository validation and the JUnit evidence checker. Manual probes
    must use names such as smoke_container.py, outside pytest's naming patterns.

    Args:
        root: Checkout containing CI checks and task-local checks directories.
        files: Existing source files selected through Git's index and ignore rules.

    Returns:
        Sorted repository-relative test module paths, including nested modules.
    """
    tests: list[Path] = []
    for path in files:
        relative = path.relative_to(root)
        parts = relative.parts
        in_checks = parts[0] == "ci_checks" or (
            len(parts) >= 5 and parts[0] == "tasks" and parts[3] == "checks"
        )
        if in_checks and (path.match("test_*.py") or path.match("*_test.py")):
            tests.append(relative)
    return sorted(tests)


def check_registration(root: Path, files: list[Path]) -> list[str]:
    """Require root pytest configuration to include every maintained suite.

    Called by the static repository check before dependencies are installed.
    Configured tasks need regression tests; instruction-only proposals do not.

    Args:
        root: Checkout containing the shared pyproject.toml.
        files: Existing source files used to discover suites independently.

    Returns:
        Missing, empty, unsafe, or unregistered suite findings. An empty list
        confirms registration only; the JUnit check establishes execution.
    """
    try:
        config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        configured = config["tool"]["pytest"]["ini_options"]["testpaths"]
    except (OSError, UnicodeError, tomllib.TOMLDecodeError, KeyError, TypeError) as exc:
        return [f"Cannot read root pytest testpaths: {exc}"]
    if not isinstance(configured, list) or not configured or any(
        not isinstance(path, str) or not path for path in configured
    ):
        return ["pytest testpaths must be a nonempty list of suite directories"]
    tests = maintained_tests(root, files)
    expected = {"ci_checks"}
    for path in files:
        parts = path.relative_to(root).parts
        if len(parts) >= 4 and parts[0] == "tasks" and (
            parts[3] == "checks" or (len(parts) == 4 and parts[3] == "task.toml")
        ):
            expected.add(Path(*parts[:3], "checks").as_posix())
    errors: list[str] = []
    if len(set(configured)) != len(configured):
        errors.append("pytest testpaths contains duplicate suites")
    for suite in sorted(expected - set(configured)):
        errors.append(f"Unregistered pytest suite: {suite}")
    for suite in configured:
        directory = root / suite
        if Path(suite).is_absolute() or not directory.resolve().is_relative_to(root.resolve()):
            errors.append(f"pytest suite must stay inside the repository: {suite}")
        elif not directory.is_dir() or not any(test.is_relative_to(suite) for test in tests):
            errors.append(f"pytest suite contains no maintained test modules: {suite}")
    return errors
