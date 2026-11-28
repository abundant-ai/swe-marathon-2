"""The bundle carries runtime files only, with shared sources staged per image."""

import json
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

PREPARED = (
    "environment/data/workspace.tar.gz",
    "environment/data/units.json",
    "environment/data/fsmaint.key",
    "tests/private/skeleton.tar.gz",
    "tests/private/sealed_tests.json",
    "tests/private/vectors/inputs.pkl",
    "tests/private/vectors/gold.json",
    "tests/private/vectors/documented.json",
    "tests/private/unit_bodies.json",
    "solution/data/sympy/core/example.py",
    "tests/private/timing.json",
    "tests/private/unit_coverage.json",
)


LISTS = {
    PREPARED[4]: '{"tests": []}\n',
    PREPARED[7]: '{"calls": []}\n',
    PREPARED[1]: "[]\n",
}


def staged_task(task_root, tmp_path, *, omit: str | None = None):
    """Copy tracked sources into a scratch task and add placeholder prepared inputs."""
    target = tmp_path / "family" / "task"
    ignore = shutil.ignore_patterns(
        "experiment", "data", "private", "__pycache__", ".pytest_cache"
    )
    shutil.copytree(task_root, target, ignore=ignore)
    for relative in PREPARED:
        if relative != omit:
            path = target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(LISTS.get(relative, "placeholder\n"))
    return target


def test_bundle_holds_runtime_files_only(task_root, tmp_path):
    target = staged_task(task_root, tmp_path)
    done = subprocess.run(
        [
            sys.executable,
            "-B",
            str(target / "scripts" / "package_step.py"),
            "--output",
            str(tmp_path / "out"),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=target / "scripts",
    )
    assert done.returncode == 0, done.stderr[-2000:]
    report = json.loads(done.stdout)
    bundle = (
        tmp_path
        / "out"
        / "bundles"
        / report["content_sha256"][:12]
        / "swe-m2_scientific-computing_sympy-restoration"
    )
    assert str(bundle.resolve()) == report["task_path"]
    for excluded in (
        "README.md",
        "checks",
        "scripts",
        "common",
        "experiment",
        ".gitignore",
    ):
        assert not (bundle / excluded).exists(), excluded
    step = bundle
    for required in (
        "task.toml",
        "environment/Dockerfile",
        "environment/pyproject.toml",
        "environment/restore/restore.py",
        "environment/restore/lib/restorelib.py",
        "environment/data/units.json",
    ):
        assert (bundle / required).is_file(), required
    for required in (
        "instruction.md",
        "tests/test.sh",
        "tests/verify.py",
        "tests/Dockerfile",
        "tests/verifier/engine.py",
        "tests/verifier/lib/restorelib.py",
        "tests/runtime/pyproject.toml",
        "tests/private/units.json",
        "solution/solve.sh",
        "solution/oracle.py",
    ):
        assert (step / required).is_file(), required
    assert (step / "tests/verifier/lib/restorelib.py").read_bytes() == (
        task_root / "common/restorelib.py"
    ).read_bytes()
    assert (step / "tests/runtime/pyproject.toml").read_bytes() == (
        task_root / "environment/pyproject.toml"
    ).read_bytes()
    # the collect step's key reaches both images, and its hooks ship executable
    assert (step / "tests/private/fsmaint.key").read_bytes() == (
        bundle / "environment/data/fsmaint.key"
    ).read_bytes()
    for hook in ("fsmaint-reserve", "fsmaint-session", "fsmaint-sweep"):
        assert (bundle / "environment" / hook).stat().st_mode & 0o111, hook


@pytest.mark.parametrize(
    "omit", [PREPARED[0], PREPARED[2], PREPARED[3], PREPARED[6], PREPARED[7]]
)
def test_packaging_refuses_unprepared_inputs(task_root, tmp_path, omit):
    target = staged_task(task_root, tmp_path, omit=omit)
    done = subprocess.run(
        [
            sys.executable,
            "-B",
            str(target / "scripts" / "package_step.py"),
            "--output",
            str(tmp_path / "out"),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=target / "scripts",
    )
    assert done.returncode != 0
    assert "Prepare task data first" in done.stderr
    assert not (tmp_path / "out" / "bundles").exists()


@pytest.mark.parametrize(
    "relative, text",
    [
        (PREPARED[4], '{"tests": [], "n_visible": 7896}'),
        (PREPARED[7], '{"calls": [], "note": "x"}'),
        (PREPARED[4], "placeholder"),
        (PREPARED[4], '{"tests": [{"id": "a", "held_out": true}]}'),
        (
            PREPARED[1],
            (
                '[{"uid": "U0001", "file": "f.py", "module": "m", "qualname": "f", "dotted": "m.f", '
                '"occ": 0, "nocc": 1, "order": 0, "calls": 3}]'
            ),
        ),
    ],
)
def test_packaging_refuses_a_private_list_that_holds_more_than_its_list(
    task_root, tmp_path, relative, text
):
    target = staged_task(task_root, tmp_path)
    (target / relative).write_text(text)
    done = subprocess.run(
        [
            sys.executable,
            "-B",
            str(target / "scripts" / "package_step.py"),
            "--output",
            str(tmp_path / "out"),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=target / "scripts",
    )
    assert done.returncode != 0 and relative in done.stderr, done.stderr[-500:]
    assert not (tmp_path / "out" / "bundles").exists()


def test_single_step_bundle_has_no_step_tables(task_root, tmp_path):
    target = staged_task(task_root, tmp_path)
    done = subprocess.run(
        [
            sys.executable,
            "-B",
            str(target / "scripts" / "package_single_step.py"),
            "--output",
            str(tmp_path / "out"),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=target / "scripts",
    )
    assert done.returncode == 0, done.stderr[-2000:]
    report = json.loads(done.stdout)
    bundle = (
        tmp_path
        / "out"
        / "single-step"
        / report["content_sha256"][:12]
        / "swe-m2_scientific-computing_sympy-restoration-single"
    )
    assert str(bundle.resolve()) == report["task_path"]
    config = (bundle / "task.toml").read_text()
    assert "[[steps]]" not in config and "multi_step_reward_strategy" not in config
    assert (
        'name = "abundant/swe-m2_scientific-computing_sympy-restoration-single"'
        in config
    )
    assert not (bundle / "steps").exists()
    for required in (
        "instruction.md",
        "tests/test.sh",
        "tests/verify.py",
        "tests/Dockerfile",
        "tests/verifier/lib/restorelib.py",
        "tests/runtime/pyproject.toml",
        "tests/private/units.json",
        "solution/solve.sh",
        "solution/oracle.py",
        "environment/Dockerfile",
        "environment/restore/lib/restorelib.py",
    ):
        assert (bundle / required).is_file(), required
    step = task_root
    assert (bundle / "instruction.md").read_bytes() == (
        step / "instruction.md"
    ).read_bytes()
    assert (bundle / "tests/verify.py").read_bytes() == (
        step / "tests/verify.py"
    ).read_bytes()
    # the agent's user and the hooks survive the flattening; --keep-name keeps the task's own name
    for table in (
        'user = "dev"',
        "[[agent.setup_begin]]",
        "[[agent.setup_complete]]",
        "[[verifier.collect]]",
    ):
        assert table in config, table
    kept = subprocess.run(
        [
            sys.executable,
            "-B",
            str(target / "scripts" / "package_single_step.py"),
            "--keep-name",
            "--output",
            str(tmp_path / "kept"),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=target / "scripts",
    )
    assert kept.returncode == 0, kept.stderr[-2000:]
    flat = Path(json.loads(kept.stdout)["task_path"])
    assert flat.name == "swe-m2_scientific-computing_sympy-restoration"
    assert (
        'name = "abundant/swe-m2_scientific-computing_sympy-restoration"\n'
        in (flat / "task.toml").read_text()
    )


def test_regrade_bundle_swaps_the_reference_for_a_stored_submission(
    task_root, tmp_path
):
    import io
    import tarfile

    target = staged_task(task_root, tmp_path)
    reference = sorted(
        path.relative_to(target / "solution/data").as_posix()
        for path in (target / "solution/data").rglob("*.py")
    )
    archive = tmp_path / "candidate_unit_files.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name in reference:
            data = f"# submitted {name}\n".encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    script = str(target / "scripts" / "package_regrade.py")
    done = subprocess.run(
        [
            sys.executable,
            "-B",
            script,
            str(archive),
            "--label",
            "t17",
            "--output",
            str(tmp_path / "out"),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=target / "scripts",
    )
    assert done.returncode == 0, done.stderr[-2000:]
    report = json.loads(done.stdout)
    bundle = (
        tmp_path
        / "out"
        / "regrade"
        / report["content_sha256"][:12]
        / "swe-m2_scientific-computing_sympy-restoration-regrade-t17"
    )
    assert str(bundle.resolve()) == report["task_path"]
    assert (
        'name = "abundant/swe-m2_scientific-computing_sympy-restoration-regrade-t17"'
        in (bundle / "task.toml").read_text()
    )
    data_dir = bundle / "solution/data"
    assert (
        sorted(path.relative_to(data_dir).as_posix() for path in data_dir.rglob("*.py"))
        == reference
    )
    assert all(
        (data_dir / name).read_text() == f"# submitted {name}\n" for name in reference
    )
    assert (bundle / "tests/verify.py").read_bytes() == (
        target / "tests/verify.py"
    ).read_bytes()

    # a submission that does not cover exactly the reference's files is refused
    short = tmp_path / "short.tar.gz"
    with tarfile.open(short, "w:gz") as tar:
        info = tarfile.TarInfo("sympy/../escape.py")
        info.size = 0
        tar.addfile(info, io.BytesIO(b""))
    refused = subprocess.run(
        [
            sys.executable,
            "-B",
            script,
            str(short),
            "--label",
            "bad",
            "--output",
            str(tmp_path / "out2"),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=target / "scripts",
    )
    assert refused.returncode != 0 and "Unexpected archive member" in refused.stderr
    assert not (tmp_path / "out2").exists()


def test_session_packaging_is_retired_and_the_stated_time_is_the_agent_limit(
    task_root, tmp_path
):
    """The 48-hour chain of sessions gave way to one session; its packager refuses this task. Since v6 the
    instruction states the 12 hours the agent is given, which is the agent's limit in task.toml."""
    target = staged_task(task_root, tmp_path)
    script = str(target / "scripts" / "package_session.py")
    refused = subprocess.run(
        [
            sys.executable,
            "-B",
            script,
            "--session",
            "1",
            "--output",
            str(tmp_path / "out"),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=target / "scripts",
    )
    assert refused.returncode != 0 and "retired" in refused.stderr, refused.stderr[
        -500:
    ]
    assert not (tmp_path / "out").exists()
    # the instruction states the agent's limit and nothing else about time, and keeps the progress log
    instruction = (task_root / "instruction.md").read_text()
    limit = tomllib.loads((task_root / "task.toml").read_text())["agent"]["timeout_sec"]
    assert limit == 12 * 3600
    assert (
        "You have up to 12 hours to restore the missing bodies and test your changes."
        in instruction
    )
    assert re.findall(r"\b\d+\s*hours?\b", instruction, flags=re.IGNORECASE) == [
        "12 hours"
    ]
    assert not re.search(
        r"wall-clock|timer|seconds that remain|time is up",
        instruction,
        flags=re.IGNORECASE,
    )
    assert (
        "Keep the checkout runnable and the progress log current as you restore each module."
        in instruction
    )
    assert "/app/PROGRESS.md" in instruction
    assert not (task_root / "environment/timer.sh").exists()
    assert "timer" not in (task_root / "environment/Dockerfile").read_text()


def test_the_instruction_states_the_need_in_the_requesters_terms(task_root):
    """Fix round 10: the requirement is what the requester's code relies on, not a comparison over arguments
    the agent cannot see; no sentence about the work uses the cue words of the class the platform's verdict
    rejected (back office v13, 2026-11-26), in the instruction or in the help and messages of `restore`."""
    instruction = " ".join((task_root / "instruction.md").read_text().split())
    for phrase in (
        "exactly",
        "original",
        "every other",
        "no example or test",
        "not a restoration",
        "documented outputs",
        "delivered form",
        "checks your work",
        "the same means",
        "reject",
        "session",
        "upstream",
        "hidden",
        "withheld",
        "graded",
        "benchmark",
        "evaluat",
        "behaves as",
    ):
        assert phrase not in instruction.lower(), phrase
    for sentence in (
        "relies on what SymPy 1.14.0 gives back for any argument a function accepts",
        (
            "Which error a function raises for an argument it does not accept matters to us only where an "
            "example in its docstring shows it."
        ),
        "An equal value of another kind breaks it",
        (
            "We switch our build back to this copy once every function gives back what SymPy 1.14.0 gives, as "
            "described above, and raises what its examples show."
        ),
        (
            "The same clean-up also dropped part of SymPy's own test suite from this copy; the tests that are "
            "left are unmodified."
        ),
    ):
        assert sentence in instruction, sentence
    tool = (task_root / "environment/restore/restore.py").read_text() + (
        task_root / "common/restorelib.py"
    ).read_text()
    for phrase in (
        "delivered",
        "original skeleton",
        "original tree",
        "exactly that form",
        "rejected",
    ):
        assert phrase not in tool, phrase


def test_the_placeholders_are_the_requesters_recovery_tooling_and_the_rules_state_only_what_is_checked(
    task_root,
):
    """Fix round 11: the attribution file tells the requester's story (a faulty clean-up step blanked the bodies),
    not a curated change; the numbered placeholders are the requester's recovery tooling's, in the instruction,
    the attribution file and the `restore` tool alike; and `restore rules` states no rule beyond the lists the
    body check enforces."""
    attribution = " ".join(
        (task_root / "environment/ATTRIBUTION.txt").read_text().split()
    )
    for phrase in ("selected", "were replaced", "removed from the working copy"):
        assert phrase not in attribution, phrase
    assert (
        "a faulty clean-up step in our packaging blanked the bodies of functions and methods in this copy and "
        "dropped part of its test suite; our recovery tooling then marked each blanked body with a numbered "
        "placeholder statement."
    ) in attribution
    instruction = " ".join((task_root / "instruction.md").read_text().split())
    assert (
        "Once we noticed, our recovery tooling marked each blanked body with one numbered placeholder statement:"
        in instruction
    )
    assert (
        "The `restore` command (on `PATH`), part of the same recovery tooling, reports progress"
        in instruction
    )
    assert "replaced by one placeholder" not in instruction
    tool = " ".join((task_root / "environment/restore/restore.py").read_text().split())
    assert (
        "Each blanked body holds the numbered placeholder our recovery tooling put there"
        in tool
    )
    library = " ".join((task_root / "common/restorelib.py").read_text().split())
    assert (
        "the blanked copy, as the recovery tooling marked it" in library
        and "blanked skeleton by" not in library
    )
    unitcheck = (task_root / "environment/restore/lib/unitcheck.py").read_text()
    assert "selected" not in unitcheck
    sys.path.insert(0, str(task_root / "common"))
    try:
        import restorelib
    finally:
        sys.path.remove(str(task_root / "common"))
    rules = restorelib.rules_text()
    assert "another way" not in rules and "not thereby allowed" not in rules, rules
    assert (
        rules.rstrip()
        .splitlines()[-1]
        .startswith("Any of the names above as a literal key")
    ), rules
