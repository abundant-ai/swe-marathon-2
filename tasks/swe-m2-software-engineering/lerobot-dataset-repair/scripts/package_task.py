"""Assemble the deployable LeRobot dataset repair bundle."""

import argparse
from pathlib import Path
from shutil import copy2
import tempfile
import tomllib


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ("Dockerfile", ".dockerignore", "requirements.txt", "resources/README.md",
          "resources/SO101-ATTRIBUTION.md", "resources/so101-rows.parquet",
          "resources/so101-headless.xml", "resources/SO101-MODEL-LICENSE.txt", "resources/action_example.py")
RUNTIME = ("instruction.md", "tests/Dockerfile", "tests/test.sh", "tests/verify.py", "solution/solve.sh")
MODULES = (("__init__.py", "__main__.py", "dataset.py"), ("planning.py",), ("publication.py",),
           ("clocked.py",), ("actions.py",), ("journals.py", "queue_recovery.py"))


def copy(source: Path, target: Path) -> None:
    """Copy one explicitly selected runtime file without following links."""
    if not source.is_file() or source.is_symlink():
        raise ValueError(f"Expected a regular runtime input at {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    copy2(source, target)


def package(output: Path) -> Path:
    """Publish a fresh bundle in its configured task-named directory."""
    config = tomllib.loads((ROOT / "task.toml").read_text())
    slug = config["task"]["name"].split("/")[1]
    parent = output.resolve()
    target = parent / slug
    if target.exists() or target.is_symlink() or ROOT.is_relative_to(target):
        raise ValueError(f"Use a fresh output parent for {target}")
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=parent, prefix=".lerobot-bundle-") as location:
        staged = Path(location) / slug
        copy(ROOT / "task.toml", staged / "task.toml")
        for path in PUBLIC:
            rel = Path("environment", path)
            copy(ROOT / rel, staged / rel)
        solution = []
        for step, introduced in zip(config["steps"], MODULES, strict=True):
            base = Path("steps", step["name"])
            for item in RUNTIME:
                copy(ROOT / base / item, staged / base / item)
            for shared in ("checkpoint.py", "probes.py", "fixtures.py"):
                copy(ROOT / "common/verifier" / shared, staged / base / "tests" / shared)
            solution.extend(introduced)
            if "clocked.py" in solution:
                copy(ROOT / "common/verifier/time_probes.py", staged / base / "tests/time_probes.py")
            if "actions.py" in solution:
                copy(ROOT / "common/verifier/action_probes.py", staged / base / "tests/action_probes.py")
                for asset in ("so101-headless.xml", "SO101-MODEL-LICENSE.txt"):
                    copy(ROOT / "environment/resources" / asset, staged / base / "tests" / asset)
            if "journals.py" in introduced:
                copy(ROOT / "common/verifier/journal_probes.py", staged / base / "tests/journal_probes.py")
            for shared in ("SO101-ATTRIBUTION.md", "so101-rows.parquet"):
                copy(ROOT / "environment/resources" / shared, staged / base / "tests" / shared)
            copy(ROOT / "environment/requirements.txt", staged / base / "tests/requirements.txt")
            for module in solution:
                path = Path("lerobot_repair", module)
                copy(ROOT / "common/oracle" / path, staged / base / "solution" / path)
        staged.rename(target)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "experiment/dist")
    print(package(parser.parse_args().output))
