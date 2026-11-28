"""The docstring-example phase: one unit's death, block or timeout costs that unit only, draws are
seeded, and a used-up budget is a row for every unit, never a crash of the verifier.

The real runner (`rdoctest.py`) and the real driver (`gradelib.run_doctests`, which speaks to it over
pipes) run here against a stand-in `sympy` package: the few names the runner imports, and one module
whose functions are the units.
"""

from __future__ import annotations

import json
import random
import textwrap
import zlib
from pathlib import Path

STANDIN = {
    "sympy/__init__.py": "",
    "sympy/core/__init__.py": "",
    "sympy/core/cache.py": "def clear_cache():\n    pass\n",
    "sympy/core/random.py": "import random as _random\nrng = _random.Random()\n_assumptions_rng = _random.Random()\n",
    "sympy/testing/__init__.py": "",
    "sympy/testing/runtests.py": textwrap.dedent("""\
        import doctest
        class SymPyDocTestFinder(doctest.DocTestFinder):
            pass
        class SymPyDocTestRunner(doctest.DocTestRunner):
            pass
        class SymPyOutputChecker(doctest.OutputChecker):
            pass
        def setup_pprint():
            return None, None
        """),
    "sympy/interactive/__init__.py": "",
    "sympy/interactive/printing.py": "NO_GLOBAL = False\n",
    "sympy/printing/__init__.py": "",
    "sympy/printing/pretty/__init__.py": "",
    "sympy/printing/pretty/stringpict.py": "_GLOBAL_WRAP_LINE = None\n",
    "sympy/printing/pretty/pretty.py": "def pprint_use_unicode(flag=None):\n    return None\n",
}


def unit(name: str, body: str, result: str = "1", module: str = "sympy.demo") -> str:
    return (
        f'def {name}():\n    """\n    >>> from {module} import {name}\n    >>> {name}()\n    {result}\n    """\n'
        + textwrap.indent(body, "    ")
        + "\n\n\n"
    )


def standin_tree(root: Path) -> Path:
    draw = round(random.Random(zlib.crc32(b"sympy.demo.draw")).random(), 12)
    source = "import os\nimport random\nimport signal\nimport time\n\n\n"
    source += unit("first", "return 1")
    source += unit("dies", "os._exit(1)")
    source += unit("second", "return 1")
    # silent: the alarm cannot interrupt it, as a long builtin cannot be interrupted
    source += unit(
        "blocks",
        "signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGALRM})\ntime.sleep(30)\nreturn 1",
    )
    source += unit("third", "return 1")
    source += unit("slow", "time.sleep(30)\nreturn 1")
    source += unit("fourth", "return 1")
    source += unit("draw", "return round(random.random(), 12)", repr(draw))
    files = dict(STANDIN, **{"sympy/demo.py": source})
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    return root


NAMES = [
    "sympy.demo." + n
    for n in ("first", "dies", "second", "blocks", "third", "slow", "fourth", "draw")
]


def run_phase(
    verifier_call,
    tree: Path,
    scratch: Path,
    deadline_sec: float,
    names=NAMES,
    module="sympy.demo",
    load_sec=20,
) -> dict:
    scratch.mkdir(parents=True, exist_ok=True)
    return verifier_call(
        f"""
import json, time
from pathlib import Path
import gradelib
from verifier import engine
stats = {{}}
results, bad, missing = gradelib.run_doctests({str(tree)!r}, {{{module!r}: {names!r}}}, str(engine.LIB / "rdoctest.py"),
                                              deadline=time.monotonic() + {deadline_sec}, bound=lambda name: 1.0,
                                              load_bound=lambda name: {load_sec}, workers=1, tmp_root={str(scratch)!r}, stats=stats)
print(json.dumps({{"status": {{n: r["status"] for n, r in results.items()}}, "bad": bad, "missing": len(missing),
                   "starts": stats.get("starts", 0), "records": results}}))
""",
        timeout=300,
    )


def test_a_death_a_block_and_a_timeout_cost_only_their_own_unit(
    tmp_path, verifier_call
):
    tree = standin_tree(tmp_path / "tree")
    data = run_phase(verifier_call, tree, tmp_path / "s1", 120)
    status = {name.rsplit(".", 1)[1]: value for name, value in data["status"].items()}
    assert status == {
        "first": "pass",
        "dies": "crash",
        "second": "pass",
        "blocks": "timeout",
        "third": "pass",
        "slow": "timeout",
        "fourth": "pass",
        "draw": "pass",
    }, status
    # one start, one after the death, one after the block, one after the timeout
    assert data["bad"] == [] and data["missing"] == 0 and data["starts"] == 4
    # the draw is seeded from the unit's name, so grading the tree again gives the same result
    again = run_phase(
        verifier_call,
        tree,
        tmp_path / "s2",
        120,
        ["sympy.demo.draw", "sympy.demo.first"],
    )
    assert set(again["status"].values()) == {"pass"}


def test_an_import_that_never_finishes_fails_its_module_in_one_start(
    tmp_path, verifier_call
):
    tree = standin_tree(tmp_path / "tree")
    (tree / "sympy" / "slowimport.py").write_text(
        "import time\ntime.sleep(60)\n\n\n"
        + unit("first", "return 1", module="sympy.slowimport")
        + unit("second", "return 1", module="sympy.slowimport")
    )
    names = ["sympy.slowimport.first", "sympy.slowimport.second"]
    data = run_phase(
        verifier_call,
        tree,
        tmp_path / "s",
        120,
        names,
        module="sympy.slowimport",
        load_sec=3,
    )
    assert (
        set(data["status"].values()) == {"error"}
        and data["starts"] == 1
        and data["missing"] == 0
    ), data


def test_a_run_that_dies_in_the_self_check_after_a_unit_costs_that_unit_only(
    tmp_path, verifier_call
):
    """A unit's body breaks the runner so that the self-check after it ends the process: that unit's
    record never arrives and it fails; the unit before it, checked and recorded, keeps its record."""
    tree = standin_tree(tmp_path / "tree")
    sabotage = (
        "from sympy.testing import runtests\n"
        "runtests.SymPyDocTestRunner.run = lambda *args, **kwargs: os._exit(1)\nreturn 1"
    )
    (tree / "sympy" / "late.py").write_text(
        "import os\n\n\n"
        + unit("first", "return 1", module="sympy.late")
        + unit("last", sabotage, module="sympy.late")
    )
    names = ["sympy.late.first", "sympy.late.last"]
    data = run_phase(
        verifier_call, tree, tmp_path / "s", 120, names, module="sympy.late"
    )
    assert data["status"] == {"sympy.late.first": "pass", "sympy.late.last": "crash"}, (
        data
    )
    assert data["bad"] == [] and data["missing"] == 0 and data["starts"] == 1


def test_a_used_up_budget_is_a_row_for_every_unit_and_no_error(tmp_path, verifier_call):
    tree = standin_tree(tmp_path / "tree")
    data = run_phase(verifier_call, tree, tmp_path / "s", -1)
    assert set(data["status"]) == set(NAMES) and set(data["status"].values()) == {
        "crash"
    }
    assert data["missing"] == len(NAMES) and data["starts"] == 0


def test_the_measurement_runs_through_a_used_up_budget(
    tmp_path, verifier_call, task_root
):
    """measure() itself, on the stand-in tree with two units restored and a budget that is gone
    before the examples start: a completed measurement whose units count as not reached."""
    skeleton = standin_tree(tmp_path / "skel")
    work = standin_tree(tmp_path / "work" / "app")
    text = (skeleton / "sympy" / "demo.py").read_text()
    for index, name in enumerate(("first", "second")):
        text = text.replace(
            f'>>> {name}()\n    1\n    """\n    return 1',
            f'>>> {name}()\n    1\n    """\n    raise NotImplementedError("RESTORE U000{index + 1}")',
        )
    (skeleton / "sympy" / "demo.py").write_text(text)
    private = tmp_path / "private"
    (private / "vectors").mkdir(parents=True)
    units = [
        {
            "uid": f"U000{i + 1}",
            "file": "sympy/demo.py",
            "module": "sympy.demo",
            "qualname": n,
            "dotted": f"sympy.demo.{n}",
            "occ": 0,
            "nocc": 1,
            "order": i,
        }
        for i, n in enumerate(("first", "second"))
    ]
    (private / "units.json").write_text(json.dumps(units))
    (private / "sealed_tests.json").write_text(json.dumps({"tests": []}))
    (private / "vectors" / "gold.json").write_text(
        json.dumps({"V1": ["I", "1"], "V2": ["I", "1"]})
    )
    (private / "vectors" / "documented.json").write_text(json.dumps({"calls": []}))
    (private / "unit_bodies.json").write_text(
        json.dumps({"U0001": [1, None], "U0002": [1, None]})
    )
    (private / "timing.json").write_text(
        json.dumps(
            {
                "benchmark_sec": 1.0,
                "doctest": {"load": {}, "units": {}},
                "vector": {"load": {}, "units": {}},
            }
        )
    )
    import pickle

    meta = {
        u["uid"]: {
            "file": u["file"],
            "qualname": u["qualname"],
            "name": u["qualname"],
            "occ": 0,
            "nocc": 1,
        }
        for u in units
    }
    payload = {
        "sympy.demo": {
            "units": meta,
            "vectors": [
                ("V1", "U0001", pickle.dumps({})),
                ("V2", "U0002", pickle.dumps({})),
            ],
        }
    }
    (private / "vectors" / "inputs.pkl").write_bytes(pickle.dumps(payload, protocol=4))
    out = tmp_path / "out"
    data = verifier_call(
        f"""
import json
from pathlib import Path
from verifier import delivery, engine
from verifier.config import load_config
from verifier.contracts import VerificationContext
engine.delivery.network_open = lambda *a, **k: None
engine.delivery.read_delivery = lambda top, key, *rest: delivery.Delivery("listed", end_bound=float("inf"), end_from="netcheck")
engine.sandbox_prefix = lambda *a, **k: []
engine.reap = lambda prefix: None
scoring, limits = load_config()
limits = dict(limits, measure_budget_sec=0, workers=1)
ctx = VerificationContext(Path({str(work)!r}), Path({str(skeleton)!r}), Path({str(private)!r}), Path({str(out)!r}),
                          Path({str(tmp_path / "scratch")!r}), scoring, limits)
m = engine.measure(ctx)
print(json.dumps({{"counts": dict(m.counts), "not_reached": m.details["units_not_reached"],
                   "vectors_not_reached": m.details["vectors_not_reached"], "restored": m.details["unit_states"],
                   "shares": [m.details[k] for k in ("unit_share", "call_share", "unit_share_if_reached",
                                                     "call_share_if_reached")]}}))
""",
        timeout=300,
    )
    assert data["restored"] == {"restored": 2} and data["counts"]["units_passing"] == 0
    assert data["not_reached"] == 2 and data["vectors_not_reached"] == 2
    # nothing was measured, so the reward as measured is 0 and the items not reached could raise it
    assert data["shares"] == [0.0, 0.0, 1.0, 1.0]


def test_the_agents_check_fails_only_the_unit_that_ends_its_runner(tmp_path, task_root):
    """`restore check` behaves the same way: a unit that ends the checker's process fails alone."""
    import subprocess
    import sys

    base = tmp_path / "restore"
    (base / "lib").mkdir(parents=True)
    for name in ("unitcheck.py",):
        (base / "lib" / name).write_text(
            (task_root / "environment" / "restore" / "lib" / name).read_text()
        )
    (base / "lib" / "restorelib.py").write_text(
        (task_root / "common" / "restorelib.py").read_text()
    )
    standin_tree(base / "var" / "cand")
    code = f"""
import json, os, sys
os.environ["RESTORE_BASE"] = {str(base)!r}
sys.argv = ["restore"]
sys.path.insert(0, {str(task_root / "environment" / "restore")!r})
import importlib.util
spec = importlib.util.spec_from_file_location("restore_tool", {str(task_root / "environment" / "restore" / "restore.py")!r})
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)
tool.CAND = os.path.join({str(base)!r}, "var", "cand")
res = tool.run_examples({{"sympy.demo": {[n for n in NAMES if not n.endswith(".blocks")]!r}}}, 1, timeout=1.0)
print(json.dumps({{n.rsplit(".", 1)[1]: r["status"] for n, r in res.items()}}))
"""
    done = subprocess.run(
        [sys.executable, "-I", "-B", "-c", code],
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    status = json.loads(done.stdout.strip().splitlines()[-1])
    assert (
        status["dies"] == "crash"
        and status["slow"] == "timeout"
        and "blocks" not in status
    )
    assert all(
        status[n] == "pass" for n in ("first", "second", "third", "fourth", "draw")
    ), status


def test_submitted_code_runs_with_an_address_space_limit_where_one_can_be_set(
    verifier_call, task_root
):
    data = verifier_call("""
import json
from verifier import engine
engine.os.geteuid = lambda: 0
engine.shutil.which = lambda name: "/usr/bin/" + name
engine._runs = lambda prefix: True
limited = engine.sandbox_prefix("nogroup", 4294967296, [])
notes = []
engine._runs = lambda prefix: prefix[0] == "setpriv"
fallback = engine.sandbox_prefix("nogroup", 4294967296, notes)
engine._runs = lambda prefix: True
full = engine.sandbox_prefix("nogroup", 4294967296, [], file_size=268435456, processes=1024)
print(json.dumps([limited, fallback, notes, full]))
""")
    limited, fallback, notes, full = data
    assert (
        limited[:4] == ["prlimit", "--as=4294967296", "--core=0", "--"]
        and limited[4] == "setpriv"
    )
    assert fallback[0] == "setpriv" and notes == [
        "the sandbox's resource limits could not be set; submitted code ran without them"
    ]
    assert full[:6] == [
        "prlimit",
        "--as=4294967296",
        "--fsize=268435456",
        "--nproc=1024",
        "--core=0",
        "--",
    ], full
    config = json.loads((task_root / "tests/verifier/grade_config.json").read_text())
    assert (
        config["address_space_bytes"] == 4 << 30
        and config["file_size_bytes"] == 256 << 20
        and config["sandbox_processes"] == 1024
    )


def test_a_body_that_reaches_the_process_cannot_write_a_record_the_driver_reads(
    tmp_path, verifier_call
):
    """The runner holds no key and the driver takes nothing out of order: a body that writes a passing
    record for another unit, through `__main__` or straight to every open file, breaks only its own
    unit's record (that unit fails), and the unit whose examples fail still fails."""
    tree = standin_tree(tmp_path / "tree")
    forge = textwrap.dedent("""\
        import json
        record = json.dumps({"name": "sympy.forged.target", "status": "pass"})
        try:
            import __main__
            __main__.emit({"name": "sympy.forged.target", "status": "pass"})
        except Exception:
            pass
        for fd in range(3, 64):
            for prefix in ("", "0" * 64 + " "):
                try:
                    os.write(fd, (prefix + record + chr(10)).encode())
                except OSError:
                    pass
        return 1""")
    (tree / "sympy" / "forged.py").write_text(
        "import os\n\n\n"
        + unit("forger", forge, module="sympy.forged")
        + unit("target", "return 2", module="sympy.forged")
    )
    names = ["sympy.forged.forger", "sympy.forged.target"]
    data = run_phase(
        verifier_call, tree, tmp_path / "s", 120, names, module="sympy.forged"
    )
    assert data["status"] == {
        "sympy.forged.forger": "error",
        "sympy.forged.target": "fail",
    }, data
    assert data["bad"] == [] and data["missing"] == 0


def test_a_runner_record_out_of_form_fails_its_unit_and_never_raises(
    tmp_path, verifier_call
):
    """Bodies that rebind the runner's serialiser: one makes every record carry extra fields (a claim
    that the unit was not reached, among them) and a status of its own; one sends a list as the unit's
    name. The driver rebuilds each record from the runner's own fields only, fails what is out of form,
    and the evaluation goes on."""
    tree = standin_tree(tmp_path / "tree")
    extra = textwrap.dedent("""\
        import json
        real = json.dumps
        json.dumps = lambda record, *a, **k: real(dict(record, not_reached=True, status="pass") if "name" in record else record)
        return 1""")
    listed = textwrap.dedent("""\
        import json
        real = json.dumps
        json.dumps = lambda record, *a, **k: real(dict(record, name=[record["name"]]) if "name" in record else record)
        return 1""")
    (tree / "sympy" / "rebind.py").write_text(
        unit("extra", extra, module="sympy.rebind")
        + unit("wrong", "return 2", module="sympy.rebind")
        + unit("listed", listed, module="sympy.rebind")
        + unit("after", "return 1", module="sympy.rebind")
    )
    names = ["sympy.rebind." + n for n in ("extra", "wrong", "listed", "after")]
    data = run_phase(
        verifier_call, tree, tmp_path / "s", 120, names, module="sympy.rebind"
    )
    assert data["status"] == {
        "sympy.rebind.extra": "pass",
        "sympy.rebind.wrong": "fail",
        "sympy.rebind.listed": "pass",
        "sympy.rebind.after": "pass",
    }, data
    assert not any("not_reached" in record for record in data["records"].values()), (
        data["records"]
    )


def test_a_body_that_breaks_the_json_module_does_not_reach_the_runners_own_encoder(
    tmp_path, verifier_call
):
    """The runner makes its encoder before any submitted code loads: a body that replaces json's default
    encoder and its C parts leaves the records of the units after it in the same runner well formed, so
    each keeps its own verdict."""
    tree = standin_tree(tmp_path / "tree")
    breaker = textwrap.dedent("""\
        import json
        import json.encoder

        class Broken(json.JSONEncoder):
            def encode(self, o):
                return '["broken"]'

        json._default_encoder = Broken()
        json.encoder.c_make_encoder = None
        json.encoder.c_encode_basestring_ascii = None
        json.dumps = lambda *a, **k: '["broken"]'
        return 1""")
    (tree / "sympy" / "breaker.py").write_text(
        unit("breaker", breaker, module="sympy.breaker")
        + unit("wrong", "return 2", module="sympy.breaker")
        + unit("after", "return 1", module="sympy.breaker")
    )
    names = ["sympy.breaker." + n for n in ("breaker", "wrong", "after")]
    data = run_phase(
        verifier_call, tree, tmp_path / "s", 120, names, module="sympy.breaker"
    )
    assert data["status"] == {
        "sympy.breaker.breaker": "pass",
        "sympy.breaker.wrong": "fail",
        "sympy.breaker.after": "pass",
    }, data
    assert data["bad"] == [] and data["missing"] == 0
