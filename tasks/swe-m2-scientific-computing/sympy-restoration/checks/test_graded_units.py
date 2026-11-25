"""The checkout removes only bodies that a graded item runs, and every count stated for the units is
the unit list's. Runs on the prepared private inputs when present; the trace needs an interpreter with
mpmath (this one, or uv's with the cached mpmath 1.3.0, offline)."""

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tomllib
from pathlib import Path

import pytest

STEP = Path("steps") / "01-restore-bodies"


def _prepared(task_root: Path) -> dict:
    private = task_root / STEP / "tests" / "private"
    paths = {
        "units": task_root / "environment" / "data" / "units.json",
        "workspace": task_root / "environment" / "data" / "workspace.tar.gz",
        "skeleton": private / "skeleton.tar.gz",
        "vectors": private / "vectors",
        "bodies": private / "unit_bodies.json",
        "timing": private / "timing.json",
        "solution": task_root / STEP / "solution" / "data",
    }
    if not all(p.exists() for p in paths.values()) or not (paths["vectors"] / "inputs.pkl").is_file():
        pytest.skip("prepared private inputs are not present")
    return paths


def _python_with_mpmath() -> list[str] | None:
    try:
        import mpmath  # noqa: F401

        if sys.version_info >= (3, 12):
            return [sys.executable]
    except ImportError:
        pass
    uv = shutil.which("uv")
    if uv is None:
        return None
    command = [uv, "run", "--offline", "--no-project", "--with", "mpmath==1.3.0", "python"]
    probe = subprocess.run(command + ["-c", "import sys, mpmath; print(sys.version_info >= (3, 12))"],
                           capture_output=True, text=True, timeout=600)
    return command if probe.returncode == 0 and probe.stdout.strip().endswith("True") else None


def _placeholders(text: str) -> list[str]:
    return re.findall(r'raise NotImplementedError\("RESTORE (U\d{4})"\)', text)


def test_the_stated_counts_and_every_list_of_units_agree(task_root):
    paths = _prepared(task_root)
    units = json.loads(paths["units"].read_text())
    uids = [u["uid"] for u in units]
    files = sorted({u["file"] for u in units})
    assert uids == [f"U{i + 1:04d}" for i in range(len(units))], "the units are numbered from U0001 without a gap"
    assert sorted(u["order"] for u in units) == list(range(len(units)))
    instruction = (task_root / STEP / "instruction.md").read_text()
    stated = re.search(r"bodies of ([\d,]+) functions and methods, spread over ([\d,]+) files", " ".join(instruction.split()))
    assert stated, "the instruction states how many bodies and files"
    assert (int(stated[1].replace(",", "")), int(stated[2].replace(",", ""))) == (len(units), len(files))
    description = tomllib.loads((task_root / "task.toml").read_text())["task"]["description"]
    assert re.search(r"bodies of ([\d,]+) functions", description)[1].replace(",", "") == str(len(units))
    # the reference holds exactly the unit-bearing files, the body facts and times exactly the units
    solution = sorted(str(p.relative_to(paths["solution"])) for p in paths["solution"].rglob("*.py"))
    assert solution == files
    assert sorted(json.loads(paths["bodies"].read_text())) == uids
    # the original's own times: the examples' keyed by dotted name (as the examples runner names its items),
    # the calls' by unit id, each for exactly the units of the list; an import time for every unit's module
    timing = json.loads(paths["timing"].read_text())
    examples, calls = timing["doctest"]["units"], timing["vector"]["units"]
    assert set(examples) == {u["dotted"] for u in units}, "every unit's examples have the original's time"
    assert set(calls) == set(uids), "every unit's calls have the original's time"
    for times in (examples, calls):
        assert all(isinstance(t, (int, float)) and t >= 0 for t in times.values()) and sum(times.values()) > 0
    modules = {u["module"] for u in units}
    for phase in ("doctest", "vector"):
        assert set(timing[phase]["load"]) == modules, phase
    # the agent's tree and the verifier's skeleton hold one placeholder per unit, in the unit's file, and the
    # same unit-bearing files; no file outside the unit list holds one
    for name in ("workspace", "skeleton"):
        seen = {}
        with tarfile.open(paths[name]) as tf:
            for member in tf.getmembers():
                if member.isfile() and member.name.endswith(".py"):
                    for uid in _placeholders(tf.extractfile(member).read().decode("utf-8")):
                        seen[uid] = member.name
        assert seen == {u["uid"]: u["file"] for u in units}, name


def test_every_removed_unit_is_run_by_a_graded_item(task_root, tmp_path):
    """Traced on the original tree (the skeleton with the reference's files over it): each removed unit
    has a counted call, or runs inside a counted call or an example of a unit in the set; the only
    exception keep_whole.py allows is a body that a graded unit's body is a near-copy of."""
    paths = _prepared(task_root)
    python = _python_with_mpmath()
    if python is None:
        pytest.skip("no interpreter with mpmath to trace SymPy with")
    tree = tmp_path / "original"
    with tarfile.open(paths["skeleton"]) as tf:
        tf.extractall(tree, filter="data")
    for path in paths["solution"].rglob("*.py"):
        target = tree / path.relative_to(paths["solution"])
        target.write_bytes(path.read_bytes())
    left = [str(p.relative_to(tree)) for p in (tree / "sympy").rglob("*.py") if _placeholders(p.read_text(encoding="utf-8"))]
    assert left == [], "the reference does not give back every removed body"
    builder = task_root / "scripts" / "builder"
    out = tmp_path / "coverage.json"
    done = subprocess.run(python + ["-I", "-B", str(builder / "graded_coverage.py"), str(tree), str(paths["units"]),
                                    str(paths["vectors"]), str(task_root / STEP / "tests" / "verifier" / "lib"), str(out)],
                          capture_output=True, text=True, timeout=3000, cwd=tmp_path)
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-3000:]
    facts = json.loads(out.read_text())["units"]
    units = {u["uid"]: u for u in json.loads(paths["units"].read_text())}
    assert set(facts) == set(units)
    ungraded = sorted(uid for uid, f in facts.items() if not (f["counted"] or f["run_by_calls"] or f["run_by_examples"]))
    if ungraded:
        sys.path.insert(0, str(builder))
        import keep_whole

        def record(uid):
            u = units[uid]
            fn = keep_whole.index_functions(ast.parse((tree / u["file"]).read_text(encoding="utf-8")))[u["qualname"]][u.get("occ", 0)]
            return dict(keep_whole.body_record(fn), file=u["file"], uid=uid)

        graded = [record(uid) for uid in sorted(set(units) - set(ungraded))]
        for uid in ungraded:
            mine = [record(uid)]
            assert any(keep_whole.near_copies(g, mine) for g in graded), (uid, units[uid]["dotted"])
