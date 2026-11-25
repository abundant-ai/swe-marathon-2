"""Select the runtime files needed to build a dual_arm task bundle."""

import argparse
import shutil
import tempfile
import tomllib
from pathlib import Path

TASK = Path(__file__).resolve().parents[1]
ORACLE = [
    ("__init__.py", "__main__.py", "core.py"),
    ("planning.py",),
    ("dispatch.py",),
    ("contingency.py",),
    ("commission_native.py",),
    ("native_cell.py", "plan_native.py"),
    ("dispatch_native.py",),
    ("grasp_recovery.py", "grasp_observations.py"),
]


def copy(source: Path, target: Path) -> None:
    """Copy one absolute authoring path into its chosen bundle target."""
    if not source.is_file() or source.is_symlink():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def package(parent: Path) -> Path:
    """Publish a clean runtime-only bundle under the task's submitting slug."""
    config = tomllib.loads((TASK / "task.toml").read_text(encoding="utf-8"))
    name = config["task"]["name"].split("/", 1)[1]
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / name
    if target.exists() or target.is_symlink():
        raise FileExistsError(target)
    with tempfile.TemporaryDirectory(prefix=".bundle-", dir=parent) as temporary:
        staged = Path(temporary) / name
        copy(TASK / "task.toml", staged / "task.toml")
        for name in (
            "Dockerfile",
            ".dockerignore",
            "requirements.txt",
            "resources/README.md",
            "resources/ur5e-headless.xml",
            "resources/UR5E-LICENSE.txt",
        ):
            copy(TASK / "environment" / name, staged / "environment" / name)
        runtime = []
        for index, (step, modules) in enumerate(
            zip(config["steps"], ORACLE, strict=True), start=1
        ):
            prefix = Path("steps", step["name"])
            for name in (
                "instruction.md",
                "tests/Dockerfile",
                "tests/test.sh",
                "tests/verify.py",
                "solution/solve.sh",
            ):
                copy(TASK / prefix / name, staged / prefix / name)
            verifier_files = ("checkpoint.py", "probes.py", "plant.py")
            if index >= 4:
                verifier_files += ("contingency_checks.py",)
            if index >= 5:
                verifier_files += ("commission_native_checks.py",)
                for name in ("ur5e-headless.xml", "UR5E-LICENSE.txt"):
                    copy(
                        TASK / "environment" / "resources" / name,
                        staged / prefix / "tests" / name,
                    )
                copy(
                    TASK / "environment" / "requirements.txt",
                    staged / prefix / "tests" / "requirements.txt",
                )
            if index >= 6:
                verifier_files += ("native_scenarios.py", "native_plan_checks.py")
            if index >= 8:
                verifier_files += ("grasp_recovery_checks.py",)
            for name in verifier_files:
                copy(
                    TASK / "common" / "verifier" / name,
                    staged / prefix / "tests" / name,
                )
            runtime.extend(modules)
            for name in runtime:
                path = Path("dual_arm", name)
                copy(
                    TASK / "common" / "oracle" / path,
                    staged / prefix / "solution" / path,
                )
        staged.rename(target)
    return target


def main() -> None:
    """Build the configured bundle with optional caller-selected parent directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=TASK / "experiment" / "dist")
    print(package(parser.parse_args().output))


if __name__ == "__main__":
    main()
