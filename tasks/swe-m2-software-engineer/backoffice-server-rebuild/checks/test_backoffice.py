"""Development checks: the reference is deterministic, the verifier tells right from wrong, bundles hold runtime files only.

The reference server needs its packages: STOCKWELL_PYTHON names a Python that has them, or uv
builds an environment from the pinned checkout's lock file.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
STEP = TASK / "steps" / "01-rebuild-server"

sys.path.insert(0, str(TASK / "scripts"))

from reference import checkout, python  # noqa: E402

REFERENCE = checkout()


def reference_python() -> str:
    done = subprocess.run([*python(REFERENCE), "-c", "import sys; print(sys.executable)"], capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stderr[-2000:]
    return done.stdout.strip().splitlines()[-1]


GRADE = """
import json, sys
from pathlib import Path
step, common, scenarios, work, defect, interpreter = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), sys.argv[5], sys.argv[6]
sys.path[:0] = [str(step / "tests"), str(step / "solution")]
from verifier.replay import evaluate
import oracle
server = work / "server"
if defect != "missing":
    oracle.oracle(common, server)
    run = server / "run"
    run.write_text(run.read_text().replace("/opt/py/bin/python", interpreter))
if defect == "rounding":
    path = server / "stockwell" / "platform" / "money.py"
    path.write_text(path.read_text().replace("if 2 * remainder >= abs(denominator):", "if 2 * remainder > abs(denominator):"))
if defect == "crash":
    (server / "run").write_text("#!/bin/sh\\nexit 3\\n")
print(json.dumps(evaluate(server, scenarios, work / "w", work, sandbox=False)))
"""


def record(tmp_path: Path, seed: int, count: int = 54, trading: int = 2) -> Path:
    out = tmp_path / f"scenarios-{seed}.json"
    done = subprocess.run([sys.executable, "-B", str(TASK / "scripts" / "record_scenarios.py"), "--count", str(count), "--trading", str(trading),
                           "--seed", str(seed), "--out", str(out)], capture_output=True, text=True, timeout=900)
    assert done.returncode == 0, done.stderr[-2000:]
    return out


def grade(tmp_path: Path, scenarios: Path, defect: str) -> dict:
    work = tmp_path / defect
    work.mkdir()
    done = subprocess.run([sys.executable, "-I", "-B", "-c", GRADE, str(STEP), str(REFERENCE / "backend" / "src"), str(scenarios), str(work), defect,
                           reference_python()], capture_output=True, text=True, timeout=900)
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_recording_is_deterministic_and_never_hits_a_server_error(tmp_path):
    first = record(tmp_path, 11)
    kept = first.read_bytes()
    assert record(tmp_path, 11).read_bytes() == kept
    data = json.loads(kept)
    statuses = {step["status"] for scenario in data["scenarios"] for step in scenario["steps"]}
    assert all(status < 500 for status in statuses) and {200, 201, 403, 409, 422} <= statuses
    themes = {s["theme"] for s in data["scenarios"]}
    assert len(themes) == 27 and "trading" in themes
    assert any("binary" in step["json"] for scenario in data["scenarios"] for step in scenario["steps"])


def test_verifier_scores_the_reference_one_and_defects_lower(tmp_path):
    scenarios = record(tmp_path, 12)
    total = len(json.loads(scenarios.read_text())["scenarios"])
    assert grade(tmp_path, scenarios, "none")["reward"] == 1.0
    wrong = grade(tmp_path, scenarios, "rounding")
    assert 0.0 < wrong["reward"] < 1.0 and wrong["scenarios_total"] == total
    for defect in ("crash", "missing"):
        result = grade(tmp_path, scenarios, defect)
        assert result["reward"] == 0.0 and result["scenarios_total"] == total and result["notes"]


def test_client_reaches_nearly_every_endpoint_of_the_reference():
    """The client's source names at least 95% of the endpoints; the API description lists them all."""
    probe = ("import sys, json; sys.path.insert(0, sys.argv[1]); from stockwell.api_routes import all_endpoints; "
             "print(json.dumps([[e.method, e.path] for e in all_endpoints()]))")
    done = subprocess.run([reference_python(), "-c", probe, str(REFERENCE / "backend" / "src")], capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr[-2000:]
    endpoints = json.loads(done.stdout.strip().splitlines()[-1])
    client = REFERENCE / "frontend" / "src"
    source = "\n".join(path.read_text() for path in client.rglob("*.ts*") if path.name != "schema.d.ts" and "test" not in path.parts)
    reached = 0
    for _, template in endpoints:
        parts = re.split(r"\{[a-z_]+\}", template)
        pattern = r"(\$\{[^}]+\}|\{[a-z_]+\}|[A-Za-z0-9_-]+)".join(re.escape(part) for part in parts)
        reached += bool(re.search(r"[\"'`(]" + pattern + r"[\"'`?$]", source))
    assert len(endpoints) >= 230 and reached / len(endpoints) >= 0.95


def test_bundles_hold_runtime_files_only(tmp_path):
    private = STEP / "tests" / "private" / "scenarios.json"
    created = not private.exists()
    if created:
        private.parent.mkdir(parents=True, exist_ok=True)
        private.write_text('{"scenarios": []}')
    try:
        for flag, kind in (([], "bundles"), (["--flat"], "flat")):
            done = subprocess.run([sys.executable, "-B", str(TASK / "scripts" / "package_step.py"), *flag, "--output", str(tmp_path / "out")],
                                  capture_output=True, text=True, timeout=300)
            assert done.returncode == 0, done.stderr[-2000:]
            bundle = Path(json.loads(done.stdout)["task_path"])
            assert bundle.parent.parent.name == kind
            for excluded in ("README.md", "checks", "scripts", "common", "experiment"):
                assert not (bundle / excluded).exists(), excluded
            prefix = "" if flag else "steps/01-rebuild-server/"
            for required in ("task.toml", "environment/Dockerfile", "environment/requirements.txt", "environment/sealed/stockwell/app.py",
                             "environment/sealed/stockwell/media/pdf.py", "environment/client/dist/index.html", "environment/client/src/main.tsx",
                             "environment/samples/clip.mp4", prefix + "instruction.md", prefix + "tests/verify.py", prefix + "tests/requirements.txt",
                             prefix + "tests/private/scenarios.json.gz", prefix + "solution/oracle.py", prefix + "solution/data/stockwell/api_routes.py"):
                assert (bundle / required).is_file(), required
            config = (bundle / "task.toml").read_text()
            assert ("[[steps]]" in config) == (not flag)
            # the candidate image must never receive the scenarios, the verifier or the client's test helpers
            environment = list((bundle / "environment").rglob("*"))
            assert not any("scenarios" in path.name or "replay" in path.name for path in environment)
            assert not any(".test." in path.name or "smoke" in path.name for path in environment)
            assert not any(path.suffix == ".py" for path in (bundle / "environment" / "client").rglob("*"))
            # nothing the agent can read names how the work is judged (the sealed server is bytecode it cannot read)
            words = re.compile(r"oracle|verifier|grading|hidden test|parity|record_corpus|scenario|benchmark|harbor|oddish|reward", re.I)
            for path in (bundle / "environment").rglob("*"):
                if path.is_file() and "sealed" not in path.parts and "dist" not in path.parts and path.suffix not in (".png", ".jpg", ".mp4", ".pdf", ".gif"):
                    assert not words.search(path.read_text(errors="replace")), path
    finally:
        if created:
            private.unlink()


def test_the_sealed_server_is_started_as_its_own_user_from_bytecode():
    script = (TASK / "environment" / "start-sealed-server").read_text()
    docker = (TASK / "environment" / "Dockerfile").read_text()
    assert "setpriv --reuid stockwell" in script and "STOCKWELL_AUTH_MODE=proxy" in script
    assert "compileall -q -b /opt/stockwell/app" in docker and "-name '*.py' -delete" in docker and "chmod -R go-rwx /opt/stockwell" in docker


def test_verifier_reads_the_gzipped_scenarios_the_image_ships(tmp_path):
    import gzip

    scenarios = tmp_path / "scenarios.json.gz"
    scenarios.write_bytes(gzip.compress(json.dumps({"scenarios": [{"id": "S1", "theme": "t", "steps": []}]}).encode(), mtime=0))
    probe = ("import json, sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); from verifier.replay import evaluate; "
             "print(json.dumps(evaluate(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), Path(sys.argv[4]), sandbox=False)))")
    done = subprocess.run([sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests"), str(tmp_path / "no-server"), str(scenarios), str(tmp_path)],
                          capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[-2000:]
    result = json.loads(done.stdout.strip().splitlines()[-1])
    assert result["scenarios_total"] == 1 and result["reward"] == 0.0 and result["notes"]


def test_instruction_and_config_hold_no_session_or_grading_text():
    instruction = (STEP / "instruction.md").read_text().lower()
    config = (TASK / "task.toml").read_text()
    for word in ("oracle", "reference", "hidden", "grading", "working session", "fresh context", "scenario", "hours"):
        assert word not in instruction, word
    assert "#" not in config
    for name in ("Dockerfile", "start-sealed-server"):
        lines = (TASK / "environment" / name).read_text().splitlines()
        assert not any(line.startswith("#") for line in lines[1 if name != "Dockerfile" else 0:]), name
