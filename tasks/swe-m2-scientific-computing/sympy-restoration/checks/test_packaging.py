"""The bundle carries runtime files only, with shared sources staged per image."""

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

PREPARED = (
    "environment/data/workspace.tar.gz",
    "environment/data/units.json",
    "steps/01-restore-bodies/tests/private/skeleton.tar.gz",
    "steps/01-restore-bodies/tests/private/sealed_tests.json",
    "steps/01-restore-bodies/tests/private/vectors/inputs.pkl",
    "steps/01-restore-bodies/tests/private/vectors/gold.json",
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


@pytest.mark.parametrize("omit", [PREPARED[0], PREPARED[2], PREPARED[5], PREPARED[6]])
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


def test_session_bundles_carry_the_budget_and_the_previous_sessions_files(task_root, tmp_path):
    import io
    import tarfile

    target = staged_task(task_root, tmp_path)
    script = str(target / "scripts" / "package_session.py")
    data_dir = target / "steps/01-restore-bodies/solution/data"
    reference = sorted(path.relative_to(data_dir).as_posix() for path in data_dir.rglob("*.py"))

    def run(*arguments):
        return subprocess.run([sys.executable, "-B", script, *arguments, "--output", str(tmp_path / "out")],
                              capture_output=True, text=True, timeout=120, cwd=target / "scripts")

    first = run("--session", "1")
    assert first.returncode == 0, first.stderr[-2000:]
    report = json.loads(first.stdout)
    bundle = Path(report["task_path"])
    assert bundle.name == "swe-m2_scientific-computing_sympy-restoration-48h-s1"
    assert (report["session_sec"], report["used_before_sec"], report["total_sec"], report["last_session"]) == (34560, 0, 172800, False)
    config = (bundle / "task.toml").read_text()
    assert 'name = "abundant/swe-m2_scientific-computing_sympy-restoration-48h-s1"' in config
    assert "[[steps]]" not in config and "timeout_sec = 34560" in config
    assert "USED_BEFORE_SEC=0\n" in (bundle / "environment/timer.sh").read_text()
    assert "You have 48 hours of wall-clock time" in (bundle / "instruction.md").read_text()
    assert "progress.tar.gz" not in (bundle / "environment/Dockerfile").read_text()
    assert not (bundle / "environment/data/progress.tar.gz").exists()

    archive = tmp_path / "candidate_unit_files.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name in reference:
            data = f"# delivered {name}\n".encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    fifth = run("--session", "5", "--chain", "cc-deepseek-a", "--archive", str(archive))
    assert fifth.returncode == 0, fifth.stderr[-2000:]
    report = json.loads(fifth.stdout)
    bundle = Path(report["task_path"])
    assert bundle.name == "swe-m2_scientific-computing_sympy-restoration-48h-cc-deepseek-a-s5"
    # four sessions of 9.6 hours are used; the fifth ends exactly with the budget
    assert (report["used_before_sec"], report["last_session"]) == (138240, True)
    assert "USED_BEFORE_SEC=138240\n" in (bundle / "environment/timer.sh").read_text()
    dockerfile = (bundle / "environment/Dockerfile").read_text()
    overlay = dockerfile.index("COPY data/progress.tar.gz /tmp/progress.tar.gz")
    # the delivered files go over the workspace after the skeleton copy is taken and before the timer
    assert dockerfile.index("/opt/restore/skeleton/") < overlay < dockerfile.index("COPY timer.sh /app/timer.sh")
    with tarfile.open(bundle / "environment/data/progress.tar.gz") as tar:
        assert sorted(tar.getnames()) == reference
        assert all(tar.extractfile(name).read() == f"# delivered {name}\n".encode() for name in reference)
    # the instruction, the verifier and the reference solution are those of the task
    step = target / "steps/01-restore-bodies"
    assert (bundle / "instruction.md").read_bytes() == (step / "instruction.md").read_bytes()
    assert (bundle / "tests/verifier/engine.py").read_bytes() == (step / "tests/verifier/engine.py").read_bytes()
    assert sorted(path.relative_to(bundle / "solution/data").as_posix() for path in (bundle / "solution/data").rglob("*.py")) == reference
    # the same inputs give the same bundle
    again = run("--session", "5", "--chain", "cc-deepseek-a", "--archive", str(archive))
    assert json.loads(again.stdout)["content_sha256"] == report["content_sha256"]

    for arguments, message in (
        (("--session", "6", "--chain", "x", "--archive", str(archive)), "budget is used up"),
        (("--session", "2",), "later sessions need both"),
        (("--session", "1", "--chain", "x", "--archive", str(archive)), "Session 1 takes no chain"),
    ):
        refused = run(*arguments)
        assert refused.returncode != 0 and message in refused.stderr, refused.stderr[-500:]
