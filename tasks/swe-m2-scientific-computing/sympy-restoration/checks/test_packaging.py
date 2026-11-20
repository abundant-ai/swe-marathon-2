"""The bundle carries runtime files only, with shared sources staged per image."""

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

PREPARED = (
    "environment/data/workspace.tar.gz",
    "environment/data/units.json",
    "environment/data/fsmaint.key",
    "steps/01-restore-bodies/tests/private/skeleton.tar.gz",
    "steps/01-restore-bodies/tests/private/sealed_tests.json",
    "steps/01-restore-bodies/tests/private/vectors/inputs.pkl",
    "steps/01-restore-bodies/tests/private/vectors/gold.json",
    "steps/01-restore-bodies/tests/private/vectors/documented.json",
    "steps/01-restore-bodies/tests/private/unit_bodies.json",
    "steps/01-restore-bodies/solution/data/sympy/core/example.py",
)


def staged_task(task_root, tmp_path, *, omit: str | None = None):
    """Copy tracked sources into a scratch task and add placeholder prepared inputs."""
    target = tmp_path / "family" / "task"
    ignore = shutil.ignore_patterns("experiment", "data", "private", "__pycache__", ".pytest_cache")
    shutil.copytree(task_root, target, ignore=ignore)
    for relative in PREPARED:
        if relative != omit:
            path = target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("placeholder\n")
    return target


def test_bundle_holds_runtime_files_only(task_root, tmp_path):
    target = staged_task(task_root, tmp_path)
    done = subprocess.run([sys.executable, "-B", str(target / "scripts" / "package_step.py"), "--output", str(tmp_path / "out")],
                          capture_output=True, text=True, timeout=120, cwd=target / "scripts")
    assert done.returncode == 0, done.stderr[-2000:]
    report = json.loads(done.stdout)
    bundle = tmp_path / "out" / "bundles" / report["content_sha256"][:12] / "swe-m2_scientific-computing_sympy-restoration"
    assert str(bundle.resolve()) == report["task_path"]
    for excluded in ("README.md", "checks", "scripts", "common", "experiment", ".gitignore"):
        assert not (bundle / excluded).exists(), excluded
    step = bundle / "steps" / "01-restore-bodies"
    for required in (
        "task.toml", "environment/Dockerfile", "environment/pyproject.toml", "environment/restore/restore.py",
        "environment/restore/lib/restorelib.py", "environment/data/units.json",
    ):
        assert (bundle / required).is_file(), required
    for required in (
        "instruction.md", "tests/test.sh", "tests/verify.py", "tests/Dockerfile", "tests/verifier/engine.py",
        "tests/verifier/lib/restorelib.py", "tests/runtime/pyproject.toml", "tests/private/units.json",
        "solution/solve.sh", "solution/oracle.py",
    ):
        assert (step / required).is_file(), required
    assert (step / "tests/verifier/lib/restorelib.py").read_bytes() == (task_root / "common/restorelib.py").read_bytes()
    assert (step / "tests/runtime/pyproject.toml").read_bytes() == (task_root / "environment/pyproject.toml").read_bytes()
    # the collect step's key reaches both images, and its hooks ship executable
    assert (step / "tests/private/fsmaint.key").read_bytes() == (bundle / "environment/data/fsmaint.key").read_bytes()
    for hook in ("fsmaint-reserve", "fsmaint-netcheck", "fsmaint-sweep"):
        assert (bundle / "environment" / hook).stat().st_mode & 0o111, hook


@pytest.mark.parametrize("omit", [PREPARED[0], PREPARED[2], PREPARED[3], PREPARED[6], PREPARED[7]])
def test_packaging_refuses_unprepared_inputs(task_root, tmp_path, omit):
    target = staged_task(task_root, tmp_path, omit=omit)
    done = subprocess.run([sys.executable, "-B", str(target / "scripts" / "package_step.py"), "--output", str(tmp_path / "out")],
                          capture_output=True, text=True, timeout=120, cwd=target / "scripts")
    assert done.returncode != 0
    assert "Prepare task data first" in done.stderr
    assert not (tmp_path / "out" / "bundles").exists()


def test_single_step_bundle_has_no_step_tables(task_root, tmp_path):
    target = staged_task(task_root, tmp_path)
    done = subprocess.run([sys.executable, "-B", str(target / "scripts" / "package_single_step.py"), "--output", str(tmp_path / "out")],
                          capture_output=True, text=True, timeout=120, cwd=target / "scripts")
    assert done.returncode == 0, done.stderr[-2000:]
    report = json.loads(done.stdout)
    bundle = tmp_path / "out" / "single-step" / report["content_sha256"][:12] / "swe-m2_scientific-computing_sympy-restoration-single"
    assert str(bundle.resolve()) == report["task_path"]
    config = (bundle / "task.toml").read_text()
    assert "[[steps]]" not in config and "multi_step_reward_strategy" not in config
    assert 'name = "abundant/swe-m2_scientific-computing_sympy-restoration-single"' in config
    assert not (bundle / "steps").exists()
    for required in ("instruction.md", "tests/test.sh", "tests/verify.py", "tests/Dockerfile", "tests/verifier/lib/restorelib.py",
                     "tests/runtime/pyproject.toml", "tests/private/units.json", "solution/solve.sh", "solution/oracle.py",
                     "environment/Dockerfile", "environment/restore/lib/restorelib.py"):
        assert (bundle / required).is_file(), required
    step = task_root / "steps" / "01-restore-bodies"
    assert (bundle / "instruction.md").read_bytes() == (step / "instruction.md").read_bytes()
    assert (bundle / "tests/verify.py").read_bytes() == (step / "tests/verify.py").read_bytes()
    # the agent's user and the hooks survive the flattening; --keep-name keeps the task's own name
    for table in ('user = "dev"', "[[agent.setup_begin]]", "[[agent.setup_complete]]", "[[verifier.collect]]"):
        assert table in config, table
    kept = subprocess.run([sys.executable, "-B", str(target / "scripts" / "package_single_step.py"), "--keep-name", "--output", str(tmp_path / "kept")],
                          capture_output=True, text=True, timeout=120, cwd=target / "scripts")
    assert kept.returncode == 0, kept.stderr[-2000:]
    flat = Path(json.loads(kept.stdout)["task_path"])
    assert flat.name == "swe-m2_scientific-computing_sympy-restoration"
    assert 'name = "abundant/swe-m2_scientific-computing_sympy-restoration"\n' in (flat / "task.toml").read_text()


def test_regrade_bundle_swaps_the_reference_for_a_stored_submission(task_root, tmp_path):
    import io
    import tarfile

    target = staged_task(task_root, tmp_path)
    reference = sorted(path.relative_to(target / "steps/01-restore-bodies/solution/data").as_posix()
                       for path in (target / "steps/01-restore-bodies/solution/data").rglob("*.py"))
    archive = tmp_path / "candidate_unit_files.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name in reference:
            data = f"# submitted {name}\n".encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    script = str(target / "scripts" / "package_regrade.py")
    done = subprocess.run([sys.executable, "-B", script, str(archive), "--label", "t17", "--output", str(tmp_path / "out")],
                          capture_output=True, text=True, timeout=120, cwd=target / "scripts")
    assert done.returncode == 0, done.stderr[-2000:]
    report = json.loads(done.stdout)
    bundle = tmp_path / "out" / "regrade" / report["content_sha256"][:12] / "swe-m2_scientific-computing_sympy-restoration-regrade-t17"
    assert str(bundle.resolve()) == report["task_path"]
    assert 'name = "abundant/swe-m2_scientific-computing_sympy-restoration-regrade-t17"' in (bundle / "task.toml").read_text()
    data_dir = bundle / "steps/01-restore-bodies/solution/data"
    assert sorted(path.relative_to(data_dir).as_posix() for path in data_dir.rglob("*.py")) == reference
    assert all((data_dir / name).read_text() == f"# submitted {name}\n" for name in reference)
    assert (bundle / "steps/01-restore-bodies/tests/verify.py").read_bytes() == (target / "steps/01-restore-bodies/tests/verify.py").read_bytes()

    # a submission that does not cover exactly the reference's files is refused
    short = tmp_path / "short.tar.gz"
    with tarfile.open(short, "w:gz") as tar:
        info = tarfile.TarInfo("sympy/../escape.py")
        info.size = 0
        tar.addfile(info, io.BytesIO(b""))
    refused = subprocess.run([sys.executable, "-B", script, str(short), "--label", "bad", "--output", str(tmp_path / "out2")],
                             capture_output=True, text=True, timeout=120, cwd=target / "scripts")
    assert refused.returncode != 0 and "Unexpected archive member" in refused.stderr
    assert not (tmp_path / "out2").exists()


def test_session_packaging_is_retired_and_the_stated_hours_match_the_timer(task_root, tmp_path):
    """The 48-hour chain of sessions gave way to one 12-hour session; its packager refuses this task."""
    target = staged_task(task_root, tmp_path)
    script = str(target / "scripts" / "package_session.py")
    refused = subprocess.run([sys.executable, "-B", script, "--session", "1", "--output", str(tmp_path / "out")],
                             capture_output=True, text=True, timeout=120, cwd=target / "scripts")
    assert refused.returncode != 0 and "USED_BEFORE_SEC" in refused.stderr, refused.stderr[-500:]
    assert not (tmp_path / "out").exists()
    # the hours the instruction states, the timer's total and the agent limit agree
    instruction = (task_root / "steps/01-restore-bodies/instruction.md").read_text()
    hours = int(re.search(r"You have (\d+) hours of wall-clock time at most", instruction).group(1))
    timer = (task_root / "environment/timer.sh").read_text()
    total_sec = int(re.search(r"^TOTAL_SEC=(\d+)$", timer, flags=re.M).group(1))
    agent_sec = int(re.search(r"^\[agent\]\ntimeout_sec = (\d+)$", (task_root / "task.toml").read_text(), flags=re.M).group(1))
    assert hours * 3600 == total_sec == 43200
    assert agent_sec <= total_sec and "USED_BEFORE_SEC" not in timer
