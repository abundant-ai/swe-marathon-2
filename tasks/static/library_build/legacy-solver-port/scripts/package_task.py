"""Stage the runtime files of legacy-solver-port into a bundle (default: experiment/dist/<slug>).

Runtime files only: task.toml, environment/, and per step the instruction, workdir, solution, and a verifier
build context (tests/{Dockerfile,test.sh,verify.py} + verify_core.py + private/step1..N). The step-N verifier
holds the references of steps 1..N because the evaluation is cumulative. Needs the Git-ignored
steps/*/tests/private/ folders (see README: how the references are regenerated).
"""

import argparse
import shutil
import tomllib
from pathlib import Path

TASK = Path(__file__).resolve().parents[1]


def package(output: Path) -> Path:
    config = tomllib.loads((TASK / "task.toml").read_text())
    slug = config["task"]["name"].split("/")[-1]
    target = output / slug
    if target.exists():
        raise FileExistsError(target)
    names = [s["name"] for s in config["steps"]]
    shutil.copy2(
        TASK / "task.toml",
        (target / "task.toml") if target.mkdir(parents=True) is None else None,
    )
    shutil.copytree(
        TASK / "environment",
        target / "environment",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    for n, name in enumerate(names, 1):
        src, dst = TASK / "steps" / name, target / "steps" / name
        shutil.copy2(src / "instruction.md", dst / "instruction.md") if dst.mkdir(
            parents=True
        ) is None else None
        for sub in ("workdir", "solution"):
            if (src / sub).exists():
                shutil.copytree(
                    src / sub, dst / sub, ignore=shutil.ignore_patterns("__pycache__")
                )
        tests = dst / "tests"
        tests.mkdir()
        for f in ("Dockerfile", "test.sh", "verify.py"):
            shutil.copy2(src / "tests" / f, tests / f)
        shutil.copy2(
            TASK / "common" / "verifier" / "verify_core.py", tests / "verify_core.py"
        )
        for k, other in enumerate(names[:n], 1):
            private = TASK / "steps" / other / "tests" / "private"
            if not (private / "hidden").is_dir():
                raise FileNotFoundError(private / "hidden")
            shutil.copytree(private, tests / "private" / f"step{k}")
    return target


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, default=TASK / "experiment" / "dist")
    print(package(ap.parse_args().output))
