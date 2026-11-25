"""Assemble only the released coating artifacts for Harbor and Oddish."""

import argparse
from pathlib import Path
from shutil import copy2
import tempfile
import tomllib

TASK = Path(__file__).resolve().parents[1]
STEPS = (
    "01-register-the-part",
    "02-plan-a-coating-pass",
    "03-coordinate-the-positioner",
    "04-resume-interrupted-coating",
)
PUBLIC_ASSETS = (
    "resources/README.md",
    "resources/cell/arm.urdf",
    "resources/cell/arm.srdf",
    "resources/job.json",
    "resources/scans.json",
    "resources/ambiguous-job.json",
    "resources/ambiguous-scans.json",
)
MOTION_SAMPLE = ("resources/motion-job.json", "resources/motion-registration.json")
PROCESS_VERIFIER = (
    "verify_process.py", "offline_cases.py", "offline_plan.py", "native_arm.py",
    "coating_scene.py", "process_trace.py", "scene_clearance.py", "surface_dose.py",
    "swept_clearance.py", "trajectory.py",
)
LIVE_VERIFIER = (
    "verify_live.py", "live_candidate.py", "live_cases.py", "live_controller.py", "applied_history.py",
)


def copy_file(source: Path, destination: Path) -> None:
    """Copy a named regular source file, retaining its executable bit.

    Args:
        source: Maintained file explicitly selected for this bundle.
        destination: Runtime path inside the temporary bundle.
    """
    if source.is_symlink() or not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    copy2(source, destination)


def stage_checkpoint(work: Path, step_name: str, level: int) -> None:
    """Select exactly the material required at one cumulative checkpoint."""
    step = Path("steps", step_name)
    source, destination = TASK / step, work / step
    trusted, oracle = TASK / "common/verifier", TASK / "common/oracle"
    for item in ("instruction.md", "tests/verify.py", "tests/test.sh", "solution/solve.sh"):
        copy_file(source / item, destination / item)
    for item in ("candidate.py", "registration_cases.py"):
        copy_file(trusted / item, destination / "tests" / item)
    for item in ("coating_io.py", "coating_registration.py"):
        copy_file(oracle / item, destination / "solution" / item)
    if level == 1:
        copy_file(source / "tests/Dockerfile", destination / "tests/Dockerfile")
        copy_file(oracle / "coating", destination / "solution/coating")
        copy_file(TASK / "environment/requirements.txt", destination / "tests/requirements.txt")
        return
    if level == 4:
        copy_file(trusted / "live.Dockerfile", destination / "tests/Dockerfile")
        for item in ("job.json", "registration.json"):
            copy_file(trusted / "live_inputs" / item, destination / "tests/live_inputs" / item)
    else:
        copy_file(trusted / "process.Dockerfile", destination / "tests/Dockerfile")
    copy_file(trusted / "process-requirements.txt", destination / "tests/requirements.txt")
    copy_file(TASK / "steps" / STEPS[0] / "tests/verify.py", destination / "tests/registration_verify.py")
    for item in PROCESS_VERIFIER + (LIVE_VERIFIER if level == 4 else ()):
        copy_file(trusted / item, destination / "tests" / item)
    for item in ("arm.urdf", "arm.srdf"):
        copy_file(TASK / "environment/resources/cell" / item, destination / "tests/public_cell" / item)
    copy_file(source / "solution/coating", destination / "solution/coating")
    for item in ("coating_process.py", "coating_planner.py") + (("coating_supervisor.py", "coating_resume.py") if level == 4 else ()):
        copy_file(oracle / item, destination / "solution" / item)


def package(output: Path) -> Path:
    """Build an isolated release and return its published directory.

    Args:
        output: Parent of a new bundle named for the task's registered slug.

    Raises:
        ValueError: The configured checkpoints have no packaging rule.
        FileExistsError: The intended final bundle path already exists.
    """
    configuration = tomllib.loads((TASK / "task.toml").read_text(encoding="utf-8"))
    steps = tuple(step["name"] for step in configuration["steps"])
    if not steps or steps != STEPS[:len(steps)]:
        raise ValueError("Every configured coating checkpoint requires explicit staging.")
    slug = configuration["task"]["name"].split("/", 1)[1]
    output.mkdir(parents=True, exist_ok=True)
    destination = output / slug
    if destination.is_symlink() or destination.exists():
        raise FileExistsError(destination)
    with tempfile.TemporaryDirectory(prefix=".coating-package-", dir=output) as temporary:
        work = Path(temporary) / slug
        copy_file(TASK / "task.toml", work / "task.toml")
        assets = PUBLIC_ASSETS + (MOTION_SAMPLE if len(steps) >= 2 else ())
        for item in ("Dockerfile", ".dockerignore", "requirements.txt", *assets):
            copy_file(TASK / "environment" / item, work / "environment" / item)
        for level, step in enumerate(steps, start=1):
            stage_checkpoint(work, step, level)
        work.rename(destination)
    return destination


def main() -> None:
    """Parse a bundle output directory and print the published path."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=TASK / "experiment/dist")
    print(package(parser.parse_args().output))


if __name__ == "__main__":
    main()
