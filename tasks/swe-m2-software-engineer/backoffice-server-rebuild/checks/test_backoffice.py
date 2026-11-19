"""Development checks: the reference is deterministic, the verifier tells right from wrong, bundles hold runtime files only.

The reference server needs its packages: STOCKWELL_PYTHON names a Python that has them, or uv
builds an environment from the pinned checkout's lock file.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
STEP = TASK / "steps" / "01-rebuild-server"
MEDIA = TASK / "experiment" / "media" / "private"  # the uploads the media scenarios use, when the author's machine has them

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
    oracle.oracle(common, server, step.parents[1] / "environment" / "stockwell.env")  # the source, with the task's settings
    run = server / "run"
    run.write_text(run.read_text().replace("/opt/py/bin/python", interpreter))
if defect == "rounding":
    path = server / "stockwell" / "platform" / "money.py"
    path.write_text(path.read_text().replace("if 2 * remainder >= abs(denominator):", "if 2 * remainder > abs(denominator):"))
if defect == "crash":
    (server / "run").write_text("#!/bin/sh\\nexit 3\\n")
print(json.dumps(evaluate(server, scenarios, work / "w", work, sandbox=False, media_dir=Path(sys.argv[7]))))
"""


def media_copy(tmp_path: Path) -> Path:
    """A writable copy of the private media set (when this machine has it) that the live recorder adds a month's files to."""
    target = tmp_path / "media"
    if not target.exists():
        if (MEDIA / "manifest.json").is_file():
            shutil.copytree(MEDIA, target, ignore=shutil.ignore_patterns("trading"))
        else:
            target.mkdir()
    return target


def record(tmp_path: Path, seed: int, count: int = 54, runs: int = 2) -> Path:
    """A small corpus: legacy streams and media scenarios, and `runs` months of trading (one restarted with SIGTERM, one
    with SIGKILL) with three client screens after each."""
    out = tmp_path / f"scenarios-{seed}.json"
    done = subprocess.run([sys.executable, "-B", str(TASK / "scripts" / "record_scenarios.py"), "--count", str(count), "--runs", str(runs),
                           "--term", "1", "--kill", "1", "--screens", "3", "--seed", str(seed), "--out", str(out), "--media", str(media_copy(tmp_path))],
                          capture_output=True, text=True, timeout=1800)
    assert done.returncode == 0, done.stderr[-2000:]
    return out


def grade(tmp_path: Path, scenarios: Path, defect: str) -> dict:
    work = tmp_path / defect
    work.mkdir()
    done = subprocess.run([sys.executable, "-I", "-B", "-c", GRADE, str(STEP), str(REFERENCE / "backend" / "src"), str(scenarios), str(work), defect,
                           reference_python(), str(media_copy(tmp_path))], capture_output=True, text=True, timeout=1800)
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
    with_media = (MEDIA / "manifest.json").is_file()
    assert len(themes) == 27 + with_media and "trading" in themes and ("media" in themes) == with_media
    assert any("binary" in step["json"] for scenario in data["scenarios"] for step in scenario["steps"])
    # a month of trading: one unit per day from 2031-03-03 into April, the client's screens after it, two planned restarts
    months = [s for s in data["scenarios"] if s["theme"] == "trading"]
    assert len(months) == 2 and all(30 <= sum(unit["theme"] == "trading" for unit in s["units"]) <= 35 for s in months)
    assert any(unit["theme"] == "screens" for s in months for unit in s["units"])
    assert sorted(step["restart"] for s in months for step in s["steps"] if "restart" in step) == ["kill", "term"]
    paths = {step["path"] for s in months for step in s["steps"]}
    assert {"/ledger/periods/close", "/api/version", "/auth/me", "/files/upload"} <= paths
    assert any(step.get("body_file", "").startswith("trading/invoices/") for s in months for step in s["steps"])


def test_verifier_scores_the_reference_one_and_defects_lower(tmp_path):
    scenarios = record(tmp_path, 12)
    total = len(json.loads(scenarios.read_text())["scenarios"])
    reference = grade(tmp_path, scenarios, "none")
    assert reference["reward"] == 1.0 and reference["units_total"] > total and reference["planned_restarts"] == 2
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


def serve_once(server: Path) -> bool:
    """Start a delivered server as the verifier does (PORT, DATA_DIR, no arguments), with the reference's packages, and
    check that it answers its health check and gives a workspace."""
    import http.client
    import signal
    import socket
    import time

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    data = server.parent / "data"
    data.mkdir(exist_ok=True)
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PORT": str(port), "DATA_DIR": str(data), "STOCKWELL_PYTHON": reference_python()}
    proc = subprocess.Popen([str(server / "run")], cwd=server, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        end = time.monotonic() + 60
        while time.monotonic() < end and proc.poll() is None:
            try:
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                connection.request("GET", "/api/health")
                if connection.getresponse().status == 200:
                    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
                    connection.request("POST", "/api/workspaces")
                    return connection.getresponse().status == 201
            except OSError:
                time.sleep(0.25)
        return False
    finally:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=10)


def digest(path: Path) -> str:
    """A file's SHA-256, read in chunks: the bundle's media is a couple of hundred megabytes."""
    with open(path, "rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def test_bundles_hold_runtime_files_only(tmp_path):
    private = STEP / "tests" / "private" / "scenarios.json"
    created = not private.exists()
    if created:
        private.parent.mkdir(parents=True, exist_ok=True)
        private.write_text('{"scenarios": []}')
    media = TASK / "experiment" / "media"
    made_media = [kind for kind in ("visible", "private") if not (media / kind / "manifest.json").exists()]
    for kind in made_media:  # stand-ins when the real sets (scripts/make_media.py) are not on this machine
        (media / kind / "pdf").mkdir(parents=True, exist_ok=True)
        (media / kind / "pdf" / "scan.pdf").write_bytes(f"%PDF-1.4 {kind} stand-in".encode())
        (media / kind / "manifest.json").write_text("{}")
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
            for required in ("task.toml", "environment/Dockerfile", "environment/requirements.txt", "environment/sealed/stockwell/app.pyc",
                             "environment/sealed/stockwell/media/pdf.pyc", "environment/client/dist/index.html", "environment/client/src/main.tsx",
                             "environment/prepare-delivery", prefix + "instruction.md", prefix + "tests/verify.py", prefix + "tests/requirements.txt",
                             prefix + "tests/private/scenarios.json.gz", prefix + "solution/oracle.py", prefix + "solution/data/stockwell/api_routes.pyc",
                             prefix + "solution/data/stockwell.env"):
                assert (bundle / required).is_file(), required
            # the solution as the platform runs it: from its own folder with nothing of the task around it (the round 4
            # oracle looked beside the task's tree, crashed on Oddish and scored 0): it installs a server that starts
            alone = tmp_path / f"alone-{kind}"
            shutil.copytree(bundle / f"{prefix}solution", alone / "solution")
            # on the platform it runs from /solution, which has one parent: it must never look above its own folder
            assert ".parents" not in (alone / "solution" / "oracle.py").read_text()
            installed = alone / "server"
            done = subprocess.run([sys.executable, "-I", "-B", str(alone / "solution" / "oracle.py"), str(installed)], cwd=alone,
                                  capture_output=True, text=True, timeout=120)
            assert done.returncode == 0, done.stdout[-1000:] + done.stderr[-2000:]
            assert (installed / "stockwell.env").read_text() == (TASK / "environment" / "stockwell.env").read_text()
            assert (installed / "stockwell" / "app.pyc").is_file() and not any(installed.rglob("*.py")) and os.access(installed / "run", os.X_OK)
            if not flag:
                assert serve_once(installed), "the packaged solution's server did not start and give a workspace"
            # QA 08: the reference ships as Python 3.12 bytecode only, sealed and as the solution's data, never as source
            for folder in (bundle / "environment" / "sealed", bundle / f"{prefix}solution" / "data"):
                assert not any(path.suffix == ".py" for path in folder.rglob("*")), folder
                assert all(path.read_bytes()[:4] == b"\xcb\r\r\n" for path in folder.rglob("*.pyc")), "Python 3.12 bytecode"
            config = (bundle / "task.toml").read_text()
            assert ("[[steps]]" in config) == (not flag) and "[[verifier.collect]]" in config
            # the candidate image must never receive the scenarios, the verifier or the client's test helpers
            environment = list((bundle / "environment").rglob("*"))
            assert not any("scenarios" in path.name or "replay" in path.name for path in environment)
            assert not any(".test." in path.name or "smoke" in path.name for path in environment)
            assert not any(path.suffix == ".py" for path in (bundle / "environment" / "client").rglob("*"))
            # the visible media ships as samples; the private media reaches the verifier only, byte for byte nowhere else
            private_media = {digest(path) for path in (bundle / f"{prefix}tests/private/media").rglob("*") if path.is_file()}
            shipped = {digest(path) for path in (bundle / "environment").rglob("*") if path.is_file()}
            assert private_media and not private_media & shipped
            assert any((bundle / "environment" / "samples" / "pdf").iterdir())
            assert not (bundle / "environment" / "samples" / "manifest.json").exists()
            # Stockwell's own test fixtures are inputs of the hidden `files` scenarios: none of them ships, under any name
            fixtures = {digest(path) for path in (REFERENCE / "backend" / "tests" / "fixtures").rglob("*") if path.is_file()}
            assert len(fixtures) > 100 and not fixtures & shipped
            if not flag:
                # no upload in the hidden scenarios (base64 in a JSON body, or a raw file), no cut-short upload and no file
                # answer is a file the candidate's image receives (scripts/scan_uploads.py reads the corpus once)
                done = subprocess.run([sys.executable, "-I", "-B", str(TASK / "scripts" / "scan_uploads.py"), str(bundle)],
                                      capture_output=True, text=True, timeout=600)
                assert done.returncode in (0, 1) and done.stdout, done.stderr[-3000:]
                report = json.loads(done.stdout)
                assert done.returncode == 0 and report["leaks"] == [] and report["missing"] == [], done.stdout[-3000:]
                if not created and not made_media:
                    assert report["scenarios"] > 1000 and report["base64"] > 100 and report["body_file"] > 100 and report["file_answers"] > 100
            # nothing the agent can read names how the work is judged (the sealed server is bytecode it cannot read)
            words = re.compile(r"oracle|verifier|grading|hidden test|parity|record_corpus|scenario|benchmark|harbor|oddish|reward", re.I)
            for path in (bundle / "environment").rglob("*"):
                if path.is_file() and "sealed" not in path.parts and "dist" not in path.parts and path.suffix not in (".png", ".jpg", ".mp4", ".pdf", ".gif"):
                    assert not words.search(path.read_text(errors="replace")), path
    finally:
        if created:
            private.unlink()
        for kind in made_media:
            shutil.rmtree(media / kind)


def test_the_sealed_server_is_started_as_its_own_user_from_bytecode():
    """QA 08: the image receives bytecode only (no source in any layer, the build fails on a .py), and every start
    first checks as dev that /opt/stockwell cannot be read or entered; if it can, the setup hook fails and the trial stops.
    QA 20: a root supervisor keeps the sealed server running for the whole session, restarting it when it exits or stops
    answering its health check."""
    script = (TASK / "environment" / "start-sealed-server").read_text()
    supervisor = (TASK / "environment" / "sealed-supervisor").read_text()
    docker = (TASK / "environment" / "Dockerfile").read_text()
    check = script.index("setpriv --reuid dev")
    assert check < script.index("curl") and "test -r /opt/stockwell" in script and "exit 1" in script[check:script.index("curl")]
    assert "setsid /usr/local/sbin/sealed-supervisor" in script and "setpriv --reuid stockwell" not in script
    assert "flock -n 9" in supervisor and "while :; do" in supervisor and "setpriv --reuid stockwell" in supervisor
    assert "pkill -KILL -u stockwell" in supervisor and "/usr/local/lib/stockwell/stockwell.env" in supervisor
    assert "compileall" not in docker and "test -z \"$(find /opt/stockwell/app -name '*.py'" in docker and "chmod -R go-rwx /opt/stockwell" in docker
    assert "COPY sealed-supervisor /usr/local/sbin/sealed-supervisor" in docker and "/usr/local/sbin/sealed-supervisor" in docker.split("chmod 0700")[-1]


def test_one_configuration_for_the_sealed_server_the_recordings_and_the_solution():
    """QA 12 F1/F3: the sealed server served the web client as well, so `DELETE /nowhere` answered it 405 where the
    recordings hold 404 and a perfect clone lost 6 units. The sealed server, the live recorder and the solution now take
    their settings from one file, environment/stockwell.env, with no client directory; the legacy recorder builds the
    same app in-process without one. The instruction's numbers are the ones the code enforces."""
    settings = (TASK / "environment" / "stockwell.env").read_text()
    assert "CLIENT_DIR" not in settings and "STOCKWELL_AUTH_MODE=proxy" in settings and "{data}" in settings
    docker = (TASK / "environment" / "Dockerfile").read_text()
    assert "COPY stockwell.env /usr/local/lib/stockwell/stockwell.env" in docker and "/opt/stockwell/client" not in docker
    for path in (TASK / "environment" / "start-sealed-server", TASK / "environment" / "sealed-supervisor", STEP / "solution" / "oracle.py",
                 TASK / "scripts" / "record_live.py"):
        text = path.read_text()
        assert "CLIENT_DIR" not in text and not re.search(r"STOCKWELL_(AUTH_MODE|DATABASE_URL|METRICS|REQUEST_LOG)=", text), path
    assert "stockwell.env" in (STEP / "solution" / "oracle.py").read_text() and "stockwell.env" in (TASK / "scripts" / "record_live.py").read_text()
    assert 'solution/data/stockwell.env"] = TASK_ROOT / "environment" / "stockwell.env"' in (TASK / "scripts" / "package_step.py").read_text()
    instruction = " ".join((STEP / "instruction.md").read_text().split())
    assert "serves the web client at" not in instruction and "inherit" not in instruction and "checksum" in instruction
    probe = ("import json, sys; sys.path.insert(0, sys.argv[1]); from verifier import replay as r; "
             "print(json.dumps([r.WORKERS, r.REQUEST_SEC, r.START_SEC, r.THREAD_LIMIT, r.FILE_LIMIT, r.MEMORY_LIMIT, r.WORKSPACE_ID.pattern]))")
    done = subprocess.run([sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests")], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[-2000:]
    workers, request, start, threads, file_limit, memory, workspace = json.loads(done.stdout)
    source = (REFERENCE / "backend" / "src" / "stockwell" / "settings.py").read_text()
    assert "max_body_bytes: int = 6_000_000" in source and "6 MB" in instruction
    assert "max_upload_bytes: int = Field(64 * 1024 * 1024" in source and "64 MiB" in instruction
    assert (workers, request, start) == (8, 30, 60) and "up to 8 requests" in instruction and "after 30 seconds" in instruction
    assert "gives it 60 seconds" in instruction and threads == 4096 and "4,096 threads" in instruction
    assert (file_limit, memory) == (4 << 30, 6 << 30) and "files of at most 4 GB" in instruction and "6 GB of address space" in instruction
    assert workspace == "[A-Za-z0-9_]{1,40}" and "at most 40 characters" in instruction


def test_python3_in_both_images_has_the_packages_the_instruction_names():
    """QA 13 S2: `python3` was a link to the venv's interpreter, and a venv is not active through a link outside it, so
    `python3 -c "import fastapi"` failed in both images. It is now a wrapper that runs /opt/py's interpreter, the system
    interpreter also sees /opt/py's packages, and each image's build checks both as its users."""
    for path, users in ((TASK / "environment" / "Dockerfile", ("dev", "nobody")), (STEP / "tests" / "Dockerfile", ("nobody",))):
        docker = path.read_text()
        assert "ln -sf /opt/py/bin/python" not in docker and 'exec /opt/py/bin/python "$@"' in docker, path
        assert "opt-py.pth" in docker and 'python3 -c "import fastapi' in docker and '/usr/bin/python3 -c "import fastapi' in docker, path
        for user in users:
            assert f"--reuid {user}" in docker or ("for user in dev nobody" in docker and user in ("dev", "nobody")), (path, user)


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


def test_the_candidate_id_goes_where_the_recording_has_ws_and_types_must_match():
    """The candidate's answer is compared as it is: its workspace id is put into the recorded answer where the recorder
    wrote {ws}, so an id that is also a value elsewhere (QA 10 E9: id 1100 next to account code 1100) is no problem,
    and `true` is not `1` and `100` is not `100.0` (E8)."""
    probe = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
from verifier.replay import expand, same
recorded = {"workspace": "{ws}", "code": "1100", "url": "/api/ws/{ws}/files/F-1/content", "list": ["{ws}", 11, {"{ws}": "x"}], "n": 1}
answer = {"workspace": "1100", "code": "1100", "url": "/api/ws/1100/files/F-1/content", "list": ["1100", 11, {"1100": "x"}], "n": 1}
checks = {
    "expand": expand(recorded, "1100") == answer,
    "e9": same(answer, recorded, "1100"),
    "other id": same(dict(answer, workspace="ws_2"), recorded, "1100"),
    "e8 bool": same({"active": 1}, {"active": True}, "w"),
    "e8 float": same({"total": 100.0}, {"total": 100}, "w"),
    "e8 int": same({"total": 100, "active": True}, {"total": 100, "active": True}, "w"),
    "nested": same({"a": [{"b": 0}]}, {"a": [{"b": False}]}, "w"),
    "binary": same({"binary": {"content_type": "image/png", "bytes": 3, "sha256": "ab"}},
                   {"binary": {"content_type": "image/png", "bytes": 3, "sha256": "ab", "filename": "x.png"}}, "w"),
}
print(json.dumps(checks))
"""
    done = subprocess.run([sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests")], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[-2000:]
    assert json.loads(done.stdout) == {"expand": True, "e9": True, "other id": False, "e8 bool": False, "e8 float": False, "e8 int": True,
                                       "nested": False, "binary": True}


def test_replay_sends_files_and_sized_bodies_raw(tmp_path):
    """A step may upload a file from the media folder, or N zero bytes, as the raw request body."""
    (tmp_path / "media" / "video").mkdir(parents=True)
    (tmp_path / "media" / "video" / "clip.mp4").write_bytes(b"\x00\x00\x00\x18ftypisom" + b"x" * 100)
    (tmp_path / "media" / "imports").mkdir()
    (tmp_path / "media" / "imports" / "list.csv").write_text("name,region\nCafé Lumière 1,NORD\n", encoding="utf-8")
    probe = """
import hashlib, http.client, json, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from verifier.replay import EvaluationError, Media, exchange

class Echo(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        out = json.dumps({"type": self.headers["Content-Type"], "bytes": len(body), "sha": hashlib.sha256(body).hexdigest()[:8]}).encode()
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def do_GET(self):  # a file answer larger than the old 16 MB read limit, sent in pieces
        self.send_response(200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(40 * 1024 * 1024))
        self.end_headers()
        for _ in range(40):
            self.wfile.write(bytes(range(256)) * 4096)

    def log_message(self, *args):
        pass

server = ThreadingHTTPServer(("127.0.0.1", 0), Echo)
threading.Thread(target=server.serve_forever, daemon=True).start()
media = Media(Path(sys.argv[2]))
connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
steps = [{"body_file": "video/clip.mp4", "headers": {"content-type": "video/mp4"}},
         {"body_size": 70000, "headers": {"content-type": "application/octet-stream"}},
         {"body": {"a": 1}, "headers": {}},
         {"body": {"name": "Café.jpg"}, "body_insert": {"field": "content", "file": "video/clip.mp4", "as": "base64"},
          "headers": {"content-type": "application/json"}},
         {"body": {"dry_run": True}, "body_insert": {"field": "csv", "file": "imports/list.csv", "as": "text"},
          "headers": {"content-type": "application/json"}}]
out = [exchange(connection, "POST", "/x", step["headers"], step.get("body"), media.body(step)) for step in steps]
expected = [hashlib.sha256(media.body(step)).hexdigest()[:8] for step in steps[3:]]
built = [json.loads(media.body(step)) for step in steps[3:]]
out.append({"expected": expected, "built": built, "big": exchange(connection, "GET", "/big", {}, None)})
try:
    media.body({"body_file": "../escape.mp4"})
    out.append("no error")
except EvaluationError:
    out.append("refused")
print(json.dumps(out))
"""
    done = subprocess.run([sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests"), str(tmp_path / "media")],
                          capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[-2000:]
    first, sized, plain, photo, csv, extra, escape = json.loads(done.stdout)
    assert first[0] == 201 and first[1]["type"] == "video/mp4" and first[1]["bytes"] == 112
    assert sized[0] == 201 and sized[1]["type"] == "application/octet-stream" and sized[1]["bytes"] == 70000
    assert plain[1]["type"] == "application/json" and escape == "refused"
    # a JSON body built around a media file: base64 or UTF-8 text in the named field, sent as clients send JSON (UTF-8)
    assert [photo[1]["sha"], csv[1]["sha"]] == extra["expected"] and photo[1]["type"] == csv[1]["type"] == "application/json"
    assert extra["built"][0]["name"] == "Café.jpg" and base64.b64decode(extra["built"][0]["content"]).startswith(b"\x00\x00\x00\x18ftyp")
    assert extra["built"][1] == {"dry_run": True, "csv": "name,region\nCafé Lumière 1,NORD\n"}
    # a 40 MiB file answer is read in chunks and compared by type, length and SHA-256
    big = bytes(range(256)) * 4096 * 40
    assert extra["big"] == [200, {"binary": {"content_type": "video/mp4", "bytes": len(big), "sha256": hashlib.sha256(big).hexdigest()}}]


def test_replay_reads_an_early_413_on_an_oversized_upload(tmp_path):
    """A server may refuse a huge upload from its Content-Length and close before reading it."""
    probe = """
import http.client, json, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from verifier.replay import Media, exchange

class Refuse(BaseHTTPRequestHandler):
    def do_POST(self):
        out = json.dumps({"error": {"code": "body_too_large"}}).encode()
        self.send_response(413)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(out)
        self.close_connection = True

    def log_message(self, *args):
        pass

server = ThreadingHTTPServer(("127.0.0.1", 0), Refuse)
threading.Thread(target=server.serve_forever, daemon=True).start()
connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=20)
step = {"body_size": 48 * 1024 * 1024, "headers": {"content-type": "application/octet-stream"}}
first = exchange(connection, "POST", "/files/upload", step["headers"], None, Media(Path(sys.argv[2])).body(step))
second = exchange(connection, "POST", "/x", {}, {"a": 1})
print(json.dumps([first, second]))
"""
    done = subprocess.run([sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests"), str(tmp_path)],
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr[-2000:]
    first, second = json.loads(done.stdout)
    assert first == [413, {"error": {"code": "body_too_large"}}] and second[0] == 413


def test_the_upload_scan_finds_hidden_inputs_the_image_also_receives(tmp_path):
    """Planted leaks: a sample uploaded as base64, the same sample cut short, a raw private file equal to a sample, a
    file answer equal to a client file. Legitimate private uploads and answers are not reported."""
    sample, other, page = os.urandom(300), os.urandom(300), b"<html>" + os.urandom(200).hex().encode()
    bundle = tmp_path / "bundle"
    private = bundle / "steps" / "s" / "tests" / "private"
    for path, data in ((bundle / "environment" / "samples" / "photo.jpg", sample), (bundle / "environment" / "client" / "index.html", page),
                       (private / "media" / "photo" / "p.jpg", sample), (private / "media" / "photo" / "q.jpg", other)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def upload(data: bytes) -> dict:
        return {"method": "POST", "path": "/files", "query": {}, "headers": {}, "body": {"name": "f", "content": base64.b64encode(data).decode()},
                "status": 201, "json": {"id": "FILE-1"}}

    def raw(name: str) -> dict:
        return {"method": "POST", "path": "/files/upload", "query": {}, "headers": {}, "body_file": name, "status": 201, "json": {}}

    answer = {"method": "GET", "path": "/files/FILE-1/content", "query": {}, "headers": {}, "body": None, "status": 200,
              "json": {"binary": {"content_type": "text/html", "bytes": len(page), "sha256": hashlib.sha256(page).hexdigest(), "filename": None}}}
    clean = {"method": "GET", "path": "/files/FILE-1/content", "query": {}, "headers": {}, "body": None, "status": 200,
             "json": {"binary": {"content_type": "image/jpeg", "bytes": 300, "sha256": hashlib.sha256(other).hexdigest(), "filename": None}}}
    def inserted(name: str) -> dict:  # a media file put into a JSON body as base64 (a photo an integration sends)
        return {"method": "POST", "path": "/files", "query": {}, "headers": {"content-type": "application/json"}, "body": {"name": "f"},
                "body_insert": {"field": "content", "file": name, "as": "base64"}, "status": 201, "json": {}}

    corpus = {"recorded_with": {"seed": 1}, "scenarios": [
        {"id": "S1", "theme": "files", "steps": [upload(other), upload(sample)]},
        {"id": "S2", "theme": "files", "steps": [upload(sample[:150]), upload(sample[:10]), raw("photo/q.jpg"), clean]},
        {"id": "S3", "theme": "media", "steps": [raw("photo/p.jpg"), answer, raw("photo/missing.jpg")]},
        {"id": "S4", "theme": "trading", "steps": [inserted("photo/q.jpg"), inserted("photo/p.jpg")]}]}
    (private / "scenarios.json.gz").write_bytes(gzip.compress(json.dumps(corpus, indent=1).encode()))
    done = subprocess.run([sys.executable, "-I", "-B", str(TASK / "scripts" / "scan_uploads.py"), str(bundle)], capture_output=True, text=True,
                          timeout=60)
    assert done.returncode == 1, done.stderr[-2000:]
    report = json.loads(done.stdout)
    found = sorted((leak["where"].split()[0], leak["what"], leak["file"]) for leak in report["leaks"])
    assert found == [("S1", "base64 upload (equal)", "environment/samples/photo.jpg"),
                     ("S2", "base64 upload (prefix)", "environment/samples/photo.jpg"),
                     ("S3", "body_file upload (equal)", "environment/samples/photo.jpg"),
                     ("S3", "file answer", "environment/client/index.html"),
                     ("S4", "body_insert upload (equal)", "environment/samples/photo.jpg")]
    assert report["scenarios"] == 4 and report["steps"] == 11 and len(report["missing"]) == 1 and report["file_answers"] == 2
    assert report["body_insert"] == 2


def test_the_candidate_cannot_replace_the_delivery_directory():
    """A candidate that owned /app could swap /app/server for a symbolic link to the sealed server, and the root-run
    collector would copy what the link points to. /app is root's and sticky, /app/server root's and writable by all."""
    docker = (TASK / "environment" / "Dockerfile").read_text()
    owned = docker.index("chown -R dev:dev /app")
    assert owned < docker.index("chown root:root /app /app/server") and "chmod 1777 /app " in docker and "chmod 0777 /app/server" in docker
    assert "safe.directory '*'" in docker


FAKE_SERVER = r'''
import json, os, secrets, signal, socket, sys, threading, time, urllib.parse

MODE = sys.argv[1]
STATE = os.path.join(os.environ["DATA_DIR"], "tallies.json")  # disk: written before each answer; lazy: only on SIGTERM
STASH = os.path.join(os.environ["DATA_DIR"], "seen.json")
adopted, inflight, overlaps = {}, [0], {}
DRIPS = {"close": b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 100\r\nConnection: close\r\n\r\n",
         "nolength": b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n",
         "http10": b"HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n",
         "chunkclose": b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n"}


def overlap(target, path, conn):
    """overlap mode: how many requests are in flight while an upload is handled, kept in DATA_DIR/overlap.json; /drop
    closes the connection without an answer while the server stays up. Returns True when the request is dealt with."""
    with lock:
        inflight[0] += 1
        at_start = inflight[0]
    try:
        if path.endswith("/files/upload"):
            name = dict(urllib.parse.parse_qsl(target.split("?", 1)[1] if "?" in target else "")).get("name", "")
            time.sleep(0.3)
            with lock:
                overlaps.setdefault(name, []).append(max(at_start, inflight[0]))
                with open(os.path.join(os.environ["DATA_DIR"], "overlap.json"), "w") as out:
                    json.dump(overlaps, out)
        elif path.endswith("/drop"):
            return True
        else:
            time.sleep(0.05)
        return False
    finally:
        with lock:
            inflight[0] -= 1
tallies, lock = (json.load(open(STATE)) if MODE in ("disk", "lazy") and os.path.exists(STATE) else {}), threading.Lock()


def save():
    with open(STATE + ".tmp", "w") as out:
        json.dump(tallies, out)
    os.replace(STATE + ".tmp", STATE)


if MODE == "lazy":
    signal.signal(signal.SIGTERM, lambda *_: (save(), os._exit(0)))


def send(conn, status, body):
    head = f"HTTP/1.1 {status} X\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n"
    conn.sendall(head.encode() + body)


def handle(conn):
    reader = conn.makefile("rb")
    try:
        while True:
            line = reader.readline(65537)
            if not line:
                return
            method, target, _ = line.decode("latin-1").split(" ", 2)
            length = 0
            while True:
                header = reader.readline(65537)
                if header in (b"\r\n", b"\n", b""):
                    break
                name, value = header.decode("latin-1").split(":", 1)
                length = int(value) if name.strip().lower() == "content-length" else length
            if MODE == "silent" and length > 1_000_000:
                send(conn, 413, b'{"error": "too large"}')
                return  # refused from its length, closed without reading the upload or saying so
            body = reader.read(length)
            path = target.split("?")[0]
            if MODE == "overlap" and overlap(target, path, conn):
                return
            if MODE == "healthdrip" and path == "/api/health":
                conn.sendall(b"HTTP/1.0 200 OK\r\n\r\n")
                while True:  # QA 07d M1: one byte now and then, never an end
                    conn.sendall(b" ")
                    time.sleep(0.5)
            kind = path.rsplit("/", 1)[-1]
            if MODE == "drip" and kind in DRIPS:
                conn.sendall(DRIPS[kind])
                while True:
                    conn.sendall(b"1\r\n \r\n" if kind == "chunkclose" else b" ")
                    time.sleep(0.5)
            if "/orders/" in path or "/payments/" in path or "/check/" in path:
                # buggy: every order total one cent short. preview (QA 07 F1): the same, but it keeps what a month's
                # payments reveal, crashes at the month's end to earn a second try, and answers from what it kept. echo
                # (QA 07c F4): adopts the amount the client then pays as the order's total, within the same try
                workspace, month = path.split("/")[3], path.rsplit("/", 1)[1]
                with lock:
                    kept = json.load(open(STASH)) if os.path.exists(STASH) else {}
                    earlier = kept.get(month) if MODE == "preview" and kept.get(month, {}).get("ws") != workspace else None
                    if "/payments/" in path and MODE == "preview" and month not in kept:
                        kept[month] = {"amount": json.loads(body)["amount"], "ws": workspace}
                        with open(STASH + ".tmp", "w") as out:
                            json.dump(kept, out)
                        os.replace(STASH + ".tmp", STASH)
                    if "/payments/" in path:
                        adopted[(workspace, month)] = json.loads(body)["amount"]
                if "/payments/" in path:
                    send(conn, 200, json.dumps({"paid": json.loads(body)["amount"]}).encode())
                elif "/check/" in path and MODE == "preview" and earlier is None:
                    os._exit(3)
                elif "/check/" in path and MODE == "echo":
                    send(conn, 200, json.dumps({"total": adopted.get((workspace, month), 999)}).encode())
                else:
                    send(conn, 200, json.dumps({"total": earlier["amount"] if earlier else 999}).encode())
                continue
            if path == "/api/health":
                if MODE == "garbage":
                    conn.sendall(b"garbage\r\n\r\n")
                    return
                send(conn, 200, b'{"status": "ok"}')
            elif path == "/api/workspaces":
                if MODE == "hang":
                    time.sleep(3600)
                if MODE == "drip":
                    conn.sendall(b"HTTP/1.1 201 Created\r\nContent-Type: application/json\r\nContent-Length: 100\r\n\r\n")
                    while True:
                        conn.sendall(b" ")
                        time.sleep(0.2)
                send(conn, 201, json.dumps({"id": "w_" + secrets.token_hex(4)}).encode())
            elif path == "/api/version":
                send(conn, 200, b'{"version": "1"}')
            elif path.endswith("/tally"):
                workspace = path.split("/")[3]
                with lock:
                    if method == "POST":
                        tallies[workspace] = tallies.get(workspace, 0) + 1
                        if MODE == "disk":
                            save()
                    count = tallies.get(workspace, 0)
                send(conn, 200, json.dumps({"count": count}).encode())
            elif path.endswith("/crash"):
                os._exit(3)
            elif path.endswith("/fill"):
                open(os.path.join(os.environ["DATA_DIR"], "fill"), "w").close()
                send(conn, 200, json.dumps({"path": path.split("/", 4)[-1]}).encode())
            elif path.endswith("/not-json"):
                send(conn, 200, b"<html>not json</html>")
            elif path.endswith("/deep"):
                send(conn, 200, b"[" * 100000 + b"]" * 100000)
            else:
                send(conn, 200, json.dumps({"path": path.split("/", 4)[-1]}).encode())
            if MODE == "silent":
                return  # every answer is followed by a close nobody announced
    except (OSError, ValueError):
        return
    finally:
        conn.close()


listener = socket.create_server(("127.0.0.1", int(os.environ["PORT"])))
while True:
    threading.Thread(target=handle, args=(listener.accept()[0],), daemon=True).start()
'''

DRIVE = r'''
import json, sys, time
from pathlib import Path
tests, work, spec = Path(sys.argv[1]), Path(sys.argv[2]), json.loads(sys.argv[3])
sys.path.insert(0, str(tests))
from verifier import replay
for name, value in spec["patch"].items():
    setattr(replay, name, value)
exec(spec.get("setup", ""), {"replay": replay})  # a check may take a defence out to show what it stops
server = work / "server"
server.mkdir(parents=True)
(server / "server.py").write_text(spec["server"])
(server / "run").write_text(f'#!/bin/sh\nexec "{sys.executable}" -I -B "$(dirname "$0")/server.py" {spec["mode"]}\n')
(server / "run").chmod(0o755)
(work / "scenarios.json").write_text(json.dumps({"scenarios": spec["scenarios"]}))
started = time.monotonic()
metrics = replay.evaluate(server, work / "scenarios.json", work / "w", work, sandbox=False, media_dir=work / "media")
results = metrics.pop("results")
print(json.dumps({"metrics": metrics, "results": results, "seconds": time.monotonic() - started}))
'''


def drive(work: Path, mode: str, scenarios: list[dict], setup: str = "", **patch) -> dict:
    """Grade a tiny fake server (FAKE_SERVER in `mode`) with the real verifier, its limits patched to test scale."""
    spec = {"server": FAKE_SERVER, "mode": mode, "scenarios": scenarios, "patch": patch, "setup": setup}
    done = subprocess.run([sys.executable, "-I", "-B", "-c", DRIVE, str(STEP / "tests"), str(work), json.dumps(spec)],
                          capture_output=True, text=True, timeout=180)
    assert done.returncode == 0, done.stderr[-3000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


def step(path: str) -> dict:
    return {"method": "GET", "path": path, "query": {}, "headers": {"x-user": "U-01"}, "body": None, "status": 200,
            "json": {"path": path.lstrip("/")}}


def test_a_hanging_or_dripping_server_still_gets_a_reward_at_the_time_limit(tmp_path):
    """Without a limit of its own the replay would outlast the step, and the run would end with no reward at all."""
    scenarios = [{"id": f"S{i}", "theme": "t", "steps": [step("/items/1")]} for i in range(40)]
    for mode in ("hang", "drip"):
        out = drive(tmp_path / mode, mode, scenarios, REQUEST_SEC=1, DEADLINE_SEC=4, HEALTH_SEC=1)
        metrics, reasons = out["metrics"], {result["reason"] for result in out["results"]}
        assert metrics["reward"] == 0.0 and metrics["scenarios_total"] == 40 and out["seconds"] < 15, out
        assert metrics["unfinished"] > 0 and any("time limit" in note for note in metrics["notes"])
        # a request is cut after REQUEST_SEC of wall clock even while bytes keep arriving, so some attempts end before the deadline
        assert reasons == {"no answer from the server", "not played to the end before the time limit"}, reasons


def test_replies_that_are_not_http_or_not_json_are_mismatches_not_evaluation_errors(tmp_path):
    garbage = drive(tmp_path / "garbage", "garbage", [{"id": "S1", "theme": "t", "steps": [step("/items/1")]}], START_SEC=2)
    assert garbage["metrics"]["reward"] == 0.0 and garbage["results"][0]["reason"] == "the server did not start"
    scenarios = [{"id": "S1", "theme": "t", "steps": [step("/items/1"), step("/not-json")]},
                 {"id": "S2", "theme": "t", "steps": [step("/deep")]},
                 {"id": "S3", "theme": "t", "steps": [step("/items/2"), step("/items/3")]}]
    odd = drive(tmp_path / "odd", "plain", scenarios)
    assert {result["id"]: (result["failed_step"], result["reason"]) for result in odd["results"]} == {
        "S1": (2, "body differs"), "S2": (1, "body differs"), "S3": (None, None)}
    assert odd["metrics"]["scenarios_matched"] == 1 and odd["metrics"]["reward"] == round(1 / 3, 6)


def test_a_server_that_closes_without_announcing_it_loses_nothing(tmp_path):
    """QA 10 E10 and E3: right answers, each followed by a close the server never announced (one of them an early 413)."""
    big = {"method": "POST", "path": "/files/upload", "query": {}, "headers": {"x-user": "U-01", "content-type": "application/octet-stream"},
           "body_size": 2_000_000, "status": 413, "json": {"error": "too large"}}
    scenarios = [{"id": f"S{i}", "theme": "t", "steps": [step("/items/1"), step("/items/2"), step("/items/3")]} for i in range(6)]
    scenarios.append({"id": "S-big", "theme": "t", "steps": [step("/items/1"), big, step("/items/2")]})
    out = drive(tmp_path, "silent", scenarios)
    assert out["metrics"]["scenarios_matched"] == 7 and out["metrics"]["retried"] == 0, out["results"]


def test_a_server_that_crashes_now_and_then_loses_only_the_scenarios_that_crash_it(tmp_path):
    """Every tenth scenario makes the server exit. With room for second tries (RETRY_SHARE raised for this small corpus),
    the scenarios in flight beside each crash are played again alone and all count: 72 of 80. With the share the full
    corpus gets (2% of units), second tries decide no more units than that (QA 20)."""
    scenarios = [{"id": f"S{i:03d}", "theme": "crash" if i % 10 == 3 else "fine",
                  "steps": [step("/items/1"), step("/crash" if i % 10 == 3 else "/items/2"), step("/items/3")]} for i in range(80)]
    out = drive(tmp_path / "room", "plain", scenarios, RETRY_SHARE=1.0)
    metrics = out["metrics"]
    assert metrics["scenarios_matched"] == 72 and metrics["by_theme"] == {"crash": {"total": 8, "matched": 0}, "fine": {"total": 72, "matched": 72}}
    assert metrics["restarts"] >= 8 and metrics["unfinished"] == 0 and not metrics["notes"]
    assert {result["reason"] for result in out["results"] if not result["matched"]} == {"the server stopped while the scenario was played"}
    capped = drive(tmp_path / "capped", "plain", scenarios)["metrics"]
    assert capped["retry_budget_units"] == 1 and capped["retried_units"] <= 1 and capped["by_theme"]["crash"]["matched"] == 0


def test_a_second_try_is_only_for_a_server_that_stopped_and_heavy_uploads_run_alone(tmp_path):
    """QA 20 (a): a live server that leaves requests unanswered, or answers wrongly, gets no second try. QA 11 S1: a
    scenario that uploads a long PDF or a file of tens of megabytes runs with nothing beside it, so no request waits behind
    it for the database's write lock."""
    media = tmp_path / "run" / "media" / "pdf"  # drive() reads uploads from its work folder's media
    media.mkdir(parents=True)
    (media / "long.pdf").write_bytes(b"%PDF-1.7\n" + bytes(1 << 20))
    (media / "short.pdf").write_bytes(b"%PDF-1.7\n" + bytes(1000))

    def upload(name: str) -> dict:
        return {"method": "POST", "path": "/files/upload", "query": {}, "headers": {"x-user": "U-01", "content-type": "application/pdf"},
                "body_file": f"pdf/{name}", "status": 200, "json": {"path": "files/upload"}}

    slow = [{"id": f"S{i:02d}", "theme": "slow", "steps": [step("/items/1"), step("/items/2")]} for i in range(24)]
    dropped = [{"id": "D1", "theme": "dropped", "steps": [step("/items/1"), step("/drop")]}]
    heavy = [{"id": f"H{i}", "theme": "heavy", "steps": [step("/items/1"), dict(upload("long.pdf"), query={"name": "long.pdf"})]}
             for i in range(3)]
    light = [{"id": f"L{i}", "theme": "light", "steps": [step("/items/1"), dict(upload("short.pdf"), query={"name": "short.pdf"})]}
             for i in range(3)]
    out = drive(tmp_path / "run", "overlap", slow + dropped + heavy + light, RETRY_SHARE=1.0)
    metrics, results = out["metrics"], {result["id"]: result for result in out["results"]}
    assert results["D1"]["reason"] == "no answer from the server" and metrics["retried"] == 0 and metrics["alone"] == 3
    seen = json.loads((tmp_path / "run" / "w" / "data" / "overlap.json").read_text())
    assert seen["long.pdf"] == [1, 1, 1], "nothing ran beside a heavy upload"
    assert metrics["by_theme"]["heavy"]["matched"] == 3 and metrics["by_theme"]["light"]["matched"] == 3


def test_each_trading_day_and_screen_counts_alone_and_the_reward_counts_units(tmp_path):
    """Owner round 2: a trading run is one unit per day and per client screen after it. A day with a wrong answer is
    unmatched, and the run goes on, so later days still count; a scenario without units stops at its first difference.
    reward = matched units / all units. A step marked scoped: false names its full path (the client's /api/version)."""
    wrong = dict(step("/items/3"), json={"path": "items/x"})
    version = {"method": "GET", "path": "/api/version", "scoped": False, "query": {}, "headers": {"accept": "application/json"},
               "body": None, "status": 200, "json": {"version": "1"}}
    run = {"id": "T1", "theme": "trading", "units": [{"theme": "trading"}, {"theme": "trading"}, {"theme": "trading"}, {"theme": "screens"}],
           "steps": [dict(step("/items/1"), unit=0), dict(step("/items/2"), unit=0), dict(wrong, unit=1), dict(step("/items/4"), unit=1),
                     dict(step("/items/5"), unit=2), dict(version, unit=3), dict(step("/orders"), unit=3)]}
    early = {"id": "S1", "theme": "t", "steps": [wrong, step("/items/4")]}
    fine = {"id": "S2", "theme": "t", "steps": [step("/items/6")]}
    out = drive(tmp_path, "plain", [run, early, fine])
    metrics, results = out["metrics"], {result["id"]: result for result in out["results"]}
    assert results["T1"]["units"] == [True, False, True, True] and results["S1"]["units"] == [False] and results["S1"]["failed_step"] == 1
    assert metrics["units_total"] == 6 and metrics["units_matched"] == 4 and metrics["reward"] == round(4 / 6, 6)
    assert metrics["by_theme"] == {"screens": {"total": 1, "matched": 1}, "t": {"total": 2, "matched": 1}, "trading": {"total": 3, "matched": 2}}


def test_what_a_workspace_holds_survives_a_restart_on_the_same_data(tmp_path):
    """Owner round 2 (QA 01 R2): a scenario with a planned restart runs alone; after the marked step the server is
    stopped (SIGTERM, or SIGKILL straight after the answer) and started on the same DATA_DIR, and the scenario goes on
    in the same workspace. A server that keeps its state in memory fails both; one that saves only on SIGTERM fails
    the SIGKILL case; one that writes before it answers passes. Other scenarios are not disturbed."""
    def tally(method: str, count: int, restart: str | None = None) -> dict:
        found = {"method": method, "path": "/tally", "query": {}, "headers": {"x-user": "U-01"}, "body": None, "status": 200, "json": {"count": count}}
        return dict(found, restart=restart) if restart else found

    scenarios = [{"id": "TERM", "theme": "durable", "steps": [tally("POST", 1), tally("POST", 2, "term"), tally("GET", 2), tally("POST", 3)]},
                 {"id": "KILL", "theme": "durable", "steps": [tally("POST", 1), tally("POST", 2, "kill"), tally("GET", 2)]},
                 {"id": "PLAIN", "theme": "t", "steps": [tally("POST", 1), tally("GET", 1)]}]
    verdicts = {}
    for mode in ("disk", "memory", "lazy"):
        out = drive(tmp_path / mode, mode, scenarios)
        verdicts[mode] = {result["id"]: result["matched"] for result in out["results"]}
        assert out["metrics"]["planned_restarts"] == 2 and out["metrics"]["retried"] == 0, out
    assert verdicts == {"disk": {"TERM": True, "KILL": True, "PLAIN": True},
                        "memory": {"TERM": False, "KILL": False, "PLAIN": True},
                        "lazy": {"TERM": True, "KILL": False, "PLAIN": True}}


def month_of_trading(number: int) -> dict:
    """Three days: an order whose total the server computes, a payment of that total (the client sends what it was shown),
    and a check of the total. A server that gets totals one cent wrong matches one day in three."""
    month = f"M{number}"

    def day(unit: int, method: str, path: str, body: dict | None, answer: dict) -> dict:
        return {"method": method, "path": f"{path}/{month}", "query": {}, "headers": {"x-user": "U-01"}, "body": body, "status": 200,
                "json": answer, "unit": unit}

    return {"id": month, "theme": "trading", "units": [{"theme": "trading"}] * 3,
            "steps": [day(0, "POST", "/orders", {"lines": 1}, {"total": 1000}), day(1, "POST", "/payments", {"amount": 1000}, {"paid": 1000}),
                      day(2, "GET", "/check", None, {"total": 1000})]}


def test_a_second_try_cannot_replay_what_the_first_try_revealed(tmp_path):
    """QA 07 F1, reproduced and closed. A server that keeps what a month's later requests reveal, crashes at the end to
    earn a second try, and answers from what it kept, scored 1.0 where it earns 0.33. A second try now starts from a
    clean slate (server stopped, DATA_DIR set aside, and when sandboxed its user's processes and files anywhere) and
    decides only the units the first try left unanswered. Months run one at a time here, so every first try sees its
    payment, and the retry share is raised for this small corpus.

    QA 07c F4, the known residual: a server that adopts, within one try, the amount the client then pays as the order's
    total also earns 0.67 with both defences on. The client sends what it was shown, so later requests carry earlier
    answers; the README records it."""
    months = [month_of_trading(number) for number in range(6)]
    honest = drive(tmp_path / "honest", "buggy", months, WORKERS=1, RETRY_SHARE=1.0)["metrics"]
    assert honest["reward"] == round(1 / 3, 6) and honest["retried"] == 0
    no_slate, no_lock = "replay.Candidate.clean_slate = lambda self: None\n", "replay.merge_retry = lambda first, second: second\n"
    exploit = drive(tmp_path / "exploit", "preview", months, setup=no_slate + no_lock, WORKERS=1, RETRY_SHARE=1.0)["metrics"]
    assert exploit["reward"] == 1.0 and exploit["retried"] == 6, "without either defence the preview pays"
    lock_only = drive(tmp_path / "lock", "preview", months, setup=no_slate, WORKERS=1, RETRY_SHARE=1.0)["metrics"]
    assert lock_only["reward"] == round(2 / 3, 6), "with the lock alone, what it kept still reaches the day it left unanswered"
    slate_only = drive(tmp_path / "slate", "preview", months, setup=no_lock, WORKERS=1, RETRY_SHARE=1.0)["metrics"]
    both = drive(tmp_path / "both", "preview", months, WORKERS=1, RETRY_SHARE=1.0)["metrics"]
    assert slate_only["reward"] == both["reward"] == honest["reward"] and both["retried"] == 6
    echo = drive(tmp_path / "echo", "echo", months)["metrics"]
    assert echo["reward"] == round(2 / 3, 6) and echo["retried"] == 0


def test_the_server_runs_under_limits_and_the_sweep_never_follows_a_link(tmp_path):
    """QA 07 F2: limits on threads, file size and address space, checked under the drop before the server starts. The
    sweep before second tries removes what the server's user owns, and in the scratch places any hard link (one made to
    another user's file), without following links: a link to a file outside leaves that file alone."""
    probe = r"""
import json, os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from verifier import replay
root = Path(sys.argv[2])
outside = root / "outside.txt"
outside.write_text("keep")
scratch = root / "scratch"
(scratch / "deep" / "er").mkdir(parents=True)
(scratch / "deep" / "er" / "seen.json").write_text("{}")
(scratch / "link").symlink_to(outside)
os.link(outside, scratch / "hard")
removed = [replay.remove_user_files(os.getuid() + 4242, roots=(str(scratch),))]
replay.SCRATCH = (str(scratch),)
removed.append(replay.remove_user_files(os.getuid() + 4242, roots=(str(scratch),)))
left = sorted(path.name for path in scratch.iterdir())
removed.append(replay.remove_user_files(os.getuid(), roots=(str(scratch),)))
good = "RlimitNPROC:\t4096 4096\nRlimitFSIZE:\t4294967296 4294967296\nRlimitAS:\t6442450944 6442450944\n"
table = ("Limit                     Soft Limit           Hard Limit           Units\n"
         "Max processes             4096                 4096                 processes\n"
         "Max file size             4294967296           4294967296           bytes\n"
         "Max address space         6442450944           6442450944           bytes\n")
limits = [replay.limits_applied(text) for text in (good, table, good.replace("4096 4096", "4096 unlimited"), "RlimitNPROC:\t4096 4096\n")]
print(json.dumps({"removed": removed, "left": left, "after": sorted(path.name for path in scratch.iterdir()), "outside": outside.read_text(),
                  "limits": limits, "sandbox": replay.SANDBOX, "drop": replay.DROP}))
"""
    done = subprocess.run([sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests"), str(tmp_path)], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[-2000:]
    out = json.loads(done.stdout)
    assert out["removed"] == [0, 1, 2] and out["left"] == ["deep", "link"] and out["after"] == [] and out["outside"] == "keep"
    assert out["limits"] == [True, True, False, False]
    sandbox = out["sandbox"]
    assert sandbox[-len(out["drop"]):] == out["drop"] and sandbox.index("prlimit") < sandbox.index("setpriv")
    assert {"--nproc=4096", f"--fsize={4 << 30}", f"--as={6 << 30}"} <= set(sandbox) and "oom_score_adj" in sandbox[2]


def test_the_reward_is_written_in_place_when_the_server_filled_the_disk(tmp_path):
    """QA 07 F2: a placeholder of the reward's size is written before the server starts, and the reward goes over it in
    place and is renamed, which needs no free space: with every new write refused, reward.txt still holds the reward."""
    probe = r"""
import builtins, errno, io, json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import verify
folder = Path(sys.argv[2])
verify.reserve(folder)
opened = io.open

def full(file, mode="r", *args, **kwargs):
    if any(flag in mode for flag in "wxa"):
        raise OSError(errno.ENOSPC, "No space left on device")
    return opened(file, mode, *args, **kwargs)

builtins.open = io.open = full
verify.publish(folder, {"reward": 0.75, "units_matched": 3, "units_total": 4, "results": [{"id": "S1"}]})
builtins.open = io.open = opened
print(json.dumps({"files": sorted(path.name for path in folder.iterdir()), "reward": (folder / "reward.txt").read_text()}))
"""
    done = subprocess.run([sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests"), str(tmp_path)], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[-2000:]
    assert json.loads(done.stdout.strip().splitlines()[-1]) == {"files": ["reward.txt"], "reward": "0.750000"}


def test_scenarios_start_in_a_fixed_shuffle_with_the_restarting_ones_spread_through_it():
    """QA 03/18: a server too slow to finish must lose some scenarios of every kind, not the kinds at the end of the file,
    and not the planned-restart months, which used to run last."""
    probe = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
from verifier import replay
scenarios = [{"id": f"S{i:02d}", "steps": [{}]} for i in range(30)] + [{"id": f"D{i}", "steps": [{"restart": "kill"}]} for i in range(3)]
print(json.dumps([replay.play_order(scenarios), replay.play_order(scenarios)]))
"""
    done = subprocess.run([sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests")], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[-2000:]
    first, second = json.loads(done.stdout)
    assert first == second and sorted(first) == list(range(33))
    shared = [index for index in first if index < 30]
    assert shared != sorted(shared)
    assert [first.index(index) for index in (30, 31, 32)] != [30, 31, 32]
    places = sorted(first.index(index) for index in (30, 31, 32))
    assert places[0] >= 5 and places[-1] <= 27 and min(b - a for a, b in zip(places, places[1:])) >= 5


def test_a_virtual_environment_in_the_delivery_survives_the_copy_to_the_verifier(tmp_path):
    """QA 07 F3: the copy out of the agent's machine refuses absolute links and links that leave the directory (tarfile's
    `data` filter), so a venv's interpreter link made the whole delivery vanish and a correct server score 0.
    environment/prepare-delivery runs before the copy ([[verifier.collect]], as the agent's own user) and makes such links
    safe: links inside become relative, links out become copies, dangling links and pipes go."""
    import tarfile

    server = tmp_path / "app" / "server"
    server.mkdir(parents=True)
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(server / ".venv")], check=True, capture_output=True, timeout=300)
    absolute = [path for path in (server / ".venv" / "bin").iterdir() if path.is_symlink() and os.path.isabs(os.readlink(path))]
    assert absolute, "a venv made here links its interpreter by an absolute path"
    (server / "data").mkdir()
    (server / "data" / "seed.json").write_text("{}")
    (server / "seed").symlink_to(server / "data" / "seed.json")
    (server / "data" / "back").symlink_to("../../server/run")
    (server / "gone").symlink_to(tmp_path / "nothing")
    (server / "zeros").symlink_to("/dev/zero")  # QA 07c N2: copied, it would stream until the disk fills
    os.mkfifo(server / "pipe")
    (server / "run").write_text('#!/bin/sh\nexec "$(dirname "$0")/.venv/bin/python" -c "import sys; print(sys.prefix)"\n')
    (server / "run").chmod(0o755)

    def copy(target: Path) -> None:  # what Harbor does: tar in the agent's machine, extract with filter="data"
        archive = tmp_path / f"{target.name}.tar.gz"
        subprocess.run(["tar", "-czf", str(archive), "-C", str(server), "."], check=True, capture_output=True, timeout=300)
        target.mkdir()
        with tarfile.open(archive) as bundle:
            bundle.extractall(target, filter="data")

    try:
        copy(tmp_path / "before")
        raise AssertionError("the copy accepted an absolute link")
    except tarfile.FilterError:
        pass
    script = (TASK / "environment" / "prepare-delivery").read_text()
    code = script.split("<<'EOF'\n", 1)[1].rsplit("\nEOF", 1)[0]
    fixed = subprocess.run([sys.executable, "-I", "-", str(server)], input=code, capture_output=True, text=True, timeout=300)
    assert fixed.returncode == 0, fixed.stderr[-2000:]
    copy(tmp_path / "after")
    after = tmp_path / "after"
    ran = subprocess.run([str(after / "run")], capture_output=True, text=True, timeout=60)
    assert ran.returncode == 0 and ran.stdout.strip() == str(after / ".venv"), ran.stderr[-2000:]
    for path in absolute:
        assert (after / ".venv" / "bin" / path.name).is_file() and not (after / ".venv" / "bin" / path.name).is_symlink()
    assert os.readlink(after / "seed") == "data/seed.json" and os.readlink(after / "data" / "back") == "../run"
    assert not (after / "gone").exists() and not (after / "pipe").exists() and not os.path.lexists(after / "zeros")
    assert len(fixed.stdout.splitlines()) >= 5 and "points at a device" in fixed.stdout
    config = tomllib.loads((TASK / "task.toml").read_text())
    assert config["verifier"]["collect"] == [{"command": "/usr/local/sbin/prepare-delivery", "user": "root", "timeout_sec": 600}]
    docker = (TASK / "environment" / "Dockerfile").read_text()
    assert "COPY prepare-delivery /usr/local/sbin/prepare-delivery" in docker and "/usr/local/sbin/prepare-delivery" in docker.split("chmod 0700")[-1]


def test_no_answer_can_make_the_evaluation_read_past_its_limit(tmp_path):
    """QA 07c F1: http.client read a chunked answer whose size line was -1 to the end of the stream, so 300 MiB grew the
    verifier by 848 MiB. Chunk sizes are now parsed strictly (no sign, no prefix, hexadecimal only) and every byte read
    counts against the limit, whatever the transfer encoding."""
    probe = r"""
import json, resource, socket, sys, threading
sys.path.insert(0, sys.argv[1])
from verifier import replay

def serve(head, megabytes):
    listener = socket.create_server(("127.0.0.1", 0))
    def run():
        conn, _ = listener.accept()
        conn.recv(65536)
        try:
            conn.sendall(head)
            block = bytes(1 << 20)
            for _ in range(megabytes):
                conn.sendall(block)
        except OSError:
            pass
        conn.close()
    threading.Thread(target=run, daemon=True).start()
    return listener.getsockname()[1]

def rss():
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / (1 << 20) if sys.platform == "darwin" else peak / 1024

chunked = b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nContent-Type: application/octet-stream\r\n\r\n"
cases = {"negative": (chunked + b"-1\r\n", 300), "signed": (chunked + b"+1a\r\n", 20), "prefixed": (chunked + b"0x10\r\n", 20),
         "underscore": (chunked + b"1_0\r\n", 20), "huge chunk": (chunked + b"fffffff\r\n", 120),
         "until close": (b"HTTP/1.1 200 OK\r\nContent-Type: application/octet-stream\r\nConnection: close\r\n\r\n", 120),
         "fine": (b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nContent-Type: application/json\r\n\r\n2;x=1\r\n{}\r\n0\r\n\r\n", 0)}
out, before = {}, rss()
for label, (head, megabytes) in cases.items():
    connection = replay.connect(serve(head, megabytes), 30)
    try:
        status, answer = replay.exchange(connection, "GET", "/x", {}, None)
        out[label] = "too large" if answer == replay.TOO_LARGE else answer
    except Exception as exc:
        out[label] = type(exc).__name__
    connection.close()
out["grew"] = rss() - before
print(json.dumps(out))
"""
    done = subprocess.run([sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests")], capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stderr[-2000:]
    out = json.loads(done.stdout.strip().splitlines()[-1])
    assert {out[label] for label in ("negative", "signed", "prefixed", "underscore")} == {"IncompleteRead"}, out
    assert out["huge chunk"] == out["until close"] == "too large" and out["fine"] == {}, out
    assert out["grew"] < 200, f"the evaluation grew by {out['grew']:.0f} MiB"


def test_a_process_whose_main_thread_exited_is_still_found_and_killed(tmp_path):
    """QA 07c F2: a process whose leader thread called exit() while other threads run shows State Z in /proc, and the
    sweep skipped zombies, so it survived every stop. It now counts as alive while it has more than one thread or a
    thread that is not a zombie; each kill round also runs `kill -9 -1` as the user. A real zombie is left to the reaper."""
    proc = tmp_path / "proc"
    for pid, uid, state, threads, tasks in (("100", 65534, "S (sleeping)", 1, ["S"]), ("200", 65534, "Z (zombie)", 3, ["Z", "S", "R"]),
                                            ("300", 65534, "Z (zombie)", 1, ["Z"]), ("400", 0, "S (sleeping)", 1, ["S"]),
                                            ("500", 65534, "Z (zombie)", 1, ["Z", "R"])):
        (proc / pid).mkdir(parents=True)
        (proc / pid / "status").write_text(f"Name:\tx\nState:\t{state}\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\nThreads:\t{threads}\n")
        for number, task_state in enumerate(tasks):
            (proc / pid / "task" / str(int(pid) + number)).mkdir(parents=True)
            (proc / pid / "task" / str(int(pid) + number) / "stat").write_text(f"{pid} (a b) {task_state} 1 1 1")
    probe = r"""
import json, signal, sys
sys.path.insert(0, sys.argv[1])
from verifier import replay
replay.PROC = sys.argv[2]
alive = replay.user_processes(65534)
sent = []
replay.os.kill = lambda pid, sig: sent.append([pid, int(sig)])
replay.kill_as_user = lambda uid: sent.append(["as user", uid])
gone = replay.end_user_processes(65534, seconds=0.4)
print(json.dumps({"alive": sorted(alive), "gone": gone, "stopped": sorted({p for p, s in sent if s == int(signal.SIGSTOP)}),
                  "killed": sorted({p for p, s in sent if s == int(signal.SIGKILL)}), "as user": ["as user", 65534] in sent}))
"""
    done = subprocess.run([sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests"), str(proc)], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[-2000:]
    out = json.loads(done.stdout.strip().splitlines()[-1])
    assert out == {"alive": [100, 200, 500], "gone": False, "stopped": [100, 200, 500], "killed": [100, 200, 500], "as user": True}


def test_the_server_cannot_fill_the_disk_through_its_log_and_a_low_disk_stops_it(tmp_path):
    """QA 07c F3: on providers that pack /logs/verifier before reading the reward, a full disk or a huge server.log lost
    the reward. The server's output now goes into a pipe the evaluation drains, keeping its first and last LOG_KEEP bytes;
    a ballast set aside before the server starts is given back for the results; and when the disk runs low the server is
    stopped for good and the scenarios it had left fail, with a note."""
    probe = r"""
import json, os, sys, threading
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from verifier import replay
folder = Path(sys.argv[2])
log = replay.LogCapture()
log.note("==== start 1 ====\n")
def write():
    for number in range(160):
        os.write(log.fd, (b"%03d" % (number % 1000)) * (65536 // 3) + b"\n")
writer = threading.Thread(target=write)
writer.start()
writer.join()
log.close(folder / "server.log")
kept = (folder / "server.log").read_bytes()
ballast = replay.Ballast(folder / "ballast", 8 << 20)
size = (folder / "ballast").stat().st_size
ballast.release()
print(json.dumps({"kept": len(kept), "head": kept[:17].decode(), "tail": kept.rstrip()[-6:].decode(), "marker": b"bytes left out" in kept,
                  "ballast": size, "released": not (folder / "ballast").exists()}))
"""
    done = subprocess.run([sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests"), str(tmp_path)], capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr[-2000:]
    out = json.loads(done.stdout.strip().splitlines()[-1])
    assert out["kept"] <= (2 << 20) + 100 and out["head"] == "==== start 1 ====" and out["tail"] == "159159" and out["marker"]
    assert out["ballast"] == 8 << 20 and out["released"]
    marker = tmp_path / "run" / "w" / "data" / "fill"
    setup = (f"import os\nreplay.GUARD_SEC = 0.1\nreplay.DISK_EVERY = 1\n_free = replay.free_bytes\n"
             f"replay.free_bytes = lambda path: 0 if os.path.exists({str(marker)!r}) else _free(path)\n")
    scenarios = [{"id": f"S{i:02d}", "theme": "t", "steps": [step("/items/1"), step("/items/2")]} for i in range(60)]
    scenarios.insert(5, {"id": "FILL", "theme": "fill", "steps": [step("/fill")]})
    run = drive(tmp_path / "run", "overlap", scenarios, setup=setup, RETRY_SHARE=1.0)
    metrics, reasons = run["metrics"], [result["reason"] for result in run["results"]]
    assert "the server was stopped when the disk ran low" in reasons and metrics["retried"] == 0, reasons
    assert any("disk ran low" in note for note in metrics["notes"]) and 0 < metrics["reward"] < 1


def test_a_drip_after_any_framing_ends_at_the_deadline_health_check_included(tmp_path):
    """QA 07d M1: http.client lets go of the connection's socket once an answer will close it (Connection: close,
    HTTP/1.0, no length, chunked and closing), so the watcher could not reach it, and one byte every few seconds held
    evaluate() at the server's pace (81 s for a 5 s deadline); a dripped health check held start() under the server's
    lock. Every read of an answer now stops at its end time, and the watcher keeps a handle on every socket."""
    scenarios = [{"id": f"S-{kind}", "theme": "t", "steps": [step(f"/{kind}")]} for kind in ("close", "nolength", "http10", "chunkclose")]
    scenarios += [{"id": f"F{i}", "theme": "t", "steps": [step("/items/1")]} for i in range(4)]
    out = drive(tmp_path / "answers", "drip", scenarios, REQUEST_SEC=1, DEADLINE_SEC=6, HEALTH_SEC=1)
    reasons = {result["id"]: result["reason"] for result in out["results"]}
    assert out["seconds"] < 15, out["seconds"]
    assert {reasons[f"S-{kind}"] for kind in ("close", "nolength", "http10", "chunkclose")} <= {"no answer from the server",
                                                                                                 "not played to the end before the time limit"}
    health = drive(tmp_path / "health", "healthdrip", scenarios[:2], START_SEC=3, DEADLINE_SEC=6)
    assert health["seconds"] < 15 and health["results"][0]["reason"] == "the server did not start", health


def test_nothing_is_deleted_before_the_reward_and_deletion_is_bounded(tmp_path):
    """QA 07d M2: evaluate() removed DATA_DIR with an unbounded rmtree before returning, and the clean slate deleted
    every directory of the server's user the same way, so tens of millions of hard links could hold the reward past the
    step limit. Nothing is deleted before the reward any more (the container is discarded); the clean slate moves what
    it takes away into a root-only directory (constant time) and never walks the evaluation's own folders; and what is
    still deleted goes through one `rm -rf` killed at its time limit, however slow the filesystem."""
    probe = r"""
import json, os, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from verifier import replay
folder = Path(sys.argv[2])
wide = folder / "wide"
for part in range(4):
    (wide / str(part)).mkdir(parents=True)
    for number in range(1000):
        os.symlink("x", wide / str(part) / str(number))
fake = folder / "bin"
fake.mkdir()
(fake / "rm").write_text("#!/bin/sh\nexec sleep 30\n")
(fake / "rm").chmod(0o755)
os.environ["PATH"] = f"{fake}:{os.environ['PATH']}"
_unlink, _rmdir = os.unlink, os.rmdir
def slow_unlink(*args, **options):
    time.sleep(0.002)
    return _unlink(*args, **options)
def slow_rmdir(*args, **options):
    time.sleep(0.002)
    return _rmdir(*args, **options)
os.unlink, os.rmdir = slow_unlink, slow_rmdir
began = time.monotonic()
replay.remove_tree(wide, 0.3)
bounded = time.monotonic() - began
os.unlink, os.rmdir = _unlink, _rmdir
root, aside = folder / "root", folder / "aside"
(root / "data" / "deep").mkdir(parents=True)
(root / "data" / "deep" / "kept").write_text("still here")
aside.mkdir()
began = time.monotonic()
taken = replay.remove_user_files(os.getuid(), roots=(str(root),), until=time.monotonic() + 5, aside=aside)
print(json.dumps({"bounded": bounded, "taken": taken, "moved": time.monotonic() - began, "left": sorted(os.listdir(root)),
                  "aside": (aside / "swept-1" / "deep" / "kept").read_text()}))
"""
    done = subprocess.run([sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests"), str(tmp_path)], capture_output=True, text=True,
                          timeout=300)
    assert done.returncode == 0, done.stderr[-2000:]
    out = json.loads(done.stdout.strip().splitlines()[-1])
    assert out["bounded"] < 3, out
    assert out["taken"] == 1 and out["left"] == [] and out["aside"] == "still here" and out["moved"] < 1, out
    source = (STEP / "tests" / "verifier" / "replay.py").read_text()
    evaluate_source = source[source.index("def evaluate("):]
    clean_slate = source[source.index("    def clean_slate(self)"):source.index("    def start(self)")]
    assert "shutil.rmtree" not in source and "remove_tree(" not in evaluate_source and "remove_user_files(" not in evaluate_source
    assert "aside=aside" in clean_slate and "skip=(str(self.work), str(self.source))" in clean_slate
    scenarios = [{"id": f"S{i:03d}", "theme": "crash" if i % 10 == 3 else "fine",
                  "steps": [step("/items/1"), step("/crash" if i % 10 == 3 else "/items/2")]} for i in range(30)]
    out = drive(tmp_path / "run", "disk", scenarios, RETRY_SHARE=1.0)
    work = tmp_path / "run" / "w"
    assert out["metrics"]["retried"] > 0 and (work / "data").is_dir(), "DATA_DIR is left in place at the end"
    assert any(path.name.startswith("data-") for path in (work / "set-aside").iterdir()), "the clean slate moved DATA_DIR aside"


def test_memory_the_server_takes_stops_it_and_a_dead_grader_leaves_no_reward(tmp_path):
    """QA 07d M3: without a cgroup, a server could lower its OOM priority between the guard's re-raises and take the
    memory the grader needs. The guard now runs every 50 ms and stops the server for good once its processes hold more
    than 6 GiB in all; and if the grader dies anyway, no reward file exists, so the result is an evaluation error,
    never a 0."""
    marker = tmp_path / "run" / "w" / "data" / "fill"
    setup = (f"import os\nreplay.GUARD_SEC = 0.05\n"
             f"replay.server_memory = lambda uid, raise_priority=False: (8 << 30) if os.path.exists({str(marker)!r}) else 0\n")
    scenarios = [{"id": f"S{i:02d}", "theme": "t", "steps": [step("/items/1"), step("/items/2")]} for i in range(60)]
    scenarios.insert(5, {"id": "FILL", "theme": "fill", "steps": [step("/fill")]})
    run = drive(tmp_path / "run", "overlap", scenarios, setup=setup, RETRY_SHARE=1.0)
    reasons = [result["reason"] for result in run["results"]]
    assert "the server was stopped when its processes held more than 6 GiB of memory" in reasons and run["metrics"]["retried"] == 0
    assert any("6 GiB of memory" in note for note in run["metrics"]["notes"])
    probe = r"""
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import verify
folder = Path(sys.argv[2])
verify.reserve(folder)
print(json.dumps({"files": sorted(path.name for path in folder.iterdir()), "summary": json.loads((folder / "metrics.json").read_text())}))
"""
    (tmp_path / "out").mkdir()
    done = subprocess.run([sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests"), str(tmp_path / "out")], capture_output=True, text=True,
                          timeout=60)
    assert done.returncode == 0, done.stderr[-2000:]
    found = json.loads(done.stdout.strip().splitlines()[-1])
    assert found["files"] == [".reward.pending", "metrics.json"] and found["summary"]["status"] == "evaluation_error"


def test_only_a_disk_that_had_room_when_the_server_started_is_watched(tmp_path):
    """QA 07d S1: a filesystem that reports no size (a tmpfs without a limit has no blocks) read as full, and one the
    machine gave already low stopped the server at once, so an honest server scored 0. Such a path is now left out of
    the watch with a note; a machine without room where the evaluation itself writes is an evaluation error."""
    scenarios = [{"id": f"S{i}", "theme": "t", "steps": [step("/items/1")]} for i in range(6)]
    for name, value in (("unsized", "None"), ("low", "100 << 20")):
        setup = f"_free = replay.free_bytes\nreplay.free_bytes = lambda path: {value} if str(path) == '/tmp' else _free(path)\n"
        out = drive(tmp_path / name, "plain", scenarios, setup=setup)
        assert out["metrics"]["reward"] == 1.0, out["metrics"]
        assert any(note.startswith("/tmp ") and "not watched" in note for note in out["metrics"]["notes"]), out["metrics"]["notes"]
        assert out["metrics"]["free_space_mib"]["/tmp"][0] == (None if name == "unsized" else 100)
    work = tmp_path / "full" / "w"
    setup = (f"_free = replay.free_bytes\nreplay.free_bytes = lambda path: (100 << 20) if str(path) == {str(work)!r} else _free(path)\n"
             "_evaluate = replay.evaluate\n"
             "def evaluate(*args, **options):\n"
             "    try:\n        return _evaluate(*args, **options)\n"
             "    except replay.EvaluationError as exc:\n        return {'results': [], 'error': str(exc)}\n"
             "replay.evaluate = evaluate\n")
    full = drive(tmp_path / "full", "plain", scenarios, setup=setup)
    assert "MiB free on" in full["metrics"]["error"] and str(work) in full["metrics"]["error"], full


def test_the_reward_is_published_before_the_step_limit_whatever_the_evaluation_is_doing(tmp_path):
    """QA 07d M1: whatever the evaluation is stuck on, verify.py stops waiting before the step's limit and publishes the
    reward from what was decided, with a note; the scenarios not decided count as not matched. The collect hook marks
    every delivery, and a delivery without the mark is an evaluation error, not a 0 (QA 07d S2)."""
    probe = r"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import verify
from verifier import replay
progress = replay.Progress()
progress.themes, progress.ids = [["t"], ["t", "t"], ["u"]], ["A", "B", "C"]
progress.metrics = {"units_total": 4, "units_matched": 0, "reward": 0.0, "scenarios_total": 3, "scenarios_matched": 0, "notes": [],
                    "by_theme": {"t": {"total": 3, "matched": 0}, "u": {"total": 1, "matched": 0}}}
progress.results = [{"id": "A", "matched": True, "units": [True], "settled": [True], "failed_step": None, "reason": None},
                    {"id": "B", "matched": False, "units": [True, False], "settled": [True, False], "failed_step": 3, "reason": "x"}, None]
began = time.monotonic()
metrics = verify.run_bounded(lambda: time.sleep(60), progress, 0.5)
print(json.dumps({"seconds": time.monotonic() - began, "reward": metrics["reward"], "notes": metrics["notes"],
                  "unfinished": metrics["unfinished"], "marker": verify.DELIVERY_MARKER}))
"""
    done = subprocess.run([sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests")], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[-2000:]
    out = json.loads(done.stdout.strip().splitlines()[-1])
    assert out["seconds"] < 5 and out["reward"] == 0.5 and out["unfinished"] == 1 and any("did not finish" in note for note in out["notes"])
    hook = (TASK / "environment" / "prepare-delivery").read_text()
    assert out["marker"] == ".delivered" and hook.index("(set -C; printf 'delivered\\n' > /app/server/.delivered)") < hook.index("exec setpriv")
    assert hook.index('mv -f /app/server/.delivered "$aside/"') < hook.index("(set -C;"), "what the agent left there is moved aside, never followed"
    verify_source = (STEP / "tests" / "verify.py").read_text()
    assert "HARD_STOP_SEC = 5_640" in verify_source and "DELIVERY_MARKER).is_file()" in verify_source


def test_set_id_bits_are_stripped_and_the_privilege_drop_sets_no_new_privs(tmp_path):
    """A set-user-id file in the submission would otherwise run as its owner, root, and could read the private answers."""
    probe = r"""
import json, stat, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from verifier import replay
root, outside = Path(sys.argv[2]) / "server", Path(sys.argv[2]) / "outside"
(root / "bin").mkdir(parents=True)
files = (root / "run", root / "bin" / "helper", outside)
for path in files:
    path.write_text("#!/bin/sh\n")
    path.chmod(0o4755)
(root / "bin" / "link").symlink_to(outside)
before = [bool(path.stat().st_mode & stat.S_ISUID) for path in files]
count = replay.strip_set_id(root)
after = [stat.S_IMODE(path.stat().st_mode) for path in files]

def status(uid, nnp="1", caps="0000000000000000", groups=""):
    return (f"Name:\tcat\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\nGid:\t65534\t65534\t65534\t65534\nGroups:\t{groups}\n"
            + (f"NoNewPrivs:\t{nnp}\n" if nnp is not None else "") + f"CapPrm:\t{caps}\nCapEff:\t{caps}\nCapAmb:\t0000000000000000\n")

dropped = [replay.privileges_dropped(text, 65534, 65534) for text in
           (status(65534), status(0), status(65534, nnp="0"), status(65534, caps="000001ffffffffff"), status(65534, groups="0 27"),
            status(65534, nnp=None), status(65534, nnp=None) + "PrctlNoNewPrivs:\t1\n",
            status(65534, nnp=None) + "PrctlNoNewPrivs:\t-1\n")]
print(json.dumps({"before": before, "count": count, "after": after, "sandbox": replay.SANDBOX, "dropped": dropped}))
"""
    done = subprocess.run([sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests"), str(tmp_path)], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[-2000:]
    out = json.loads(done.stdout)
    assert out["before"] == [True, True, True] and out["count"] == 2
    assert out["after"][:2] == [0o755, 0o755] and out["after"][2] & 0o4000, "only files inside the submission are changed"
    assert "setpriv" in out["sandbox"] and "--no-new-privs" in out["sandbox"] and out["sandbox"][out["sandbox"].index("--reuid") + 1] == "nobody"
    assert out["dropped"] == [True, False, False, False, False, False, True, False], \
        "no_new_privs counts from the status file or prctl; with neither it fails closed"


def test_the_reward_is_written_before_the_diagnostics_and_survives_their_failure(tmp_path):
    """QA 10: write reward.txt before the bulky diagnostics, so a full disk or a failed write costs only the diagnostics."""
    probe = r"""
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import verify
out = {}
for broken in ("scenario_results.json", "metrics.json"):
    folder = Path(sys.argv[2]) / broken.split(".")[0]
    (folder / broken).mkdir(parents=True)  # a directory where the file should go: writing it fails
    verify.publish(folder, {"reward": 0.25, "units_matched": 1, "units_total": 4, "results": [{"id": "S1"}] * 1000})
    out[broken] = sorted(path.name for path in folder.iterdir() if path.is_file())
    out[broken + " reward"] = (folder / "reward.txt").read_text()
print(json.dumps(out))
"""
    done = subprocess.run([sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests"), str(tmp_path)], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[-2000:]
    out = json.loads(done.stdout.strip().splitlines()[-1])
    assert out == {"scenario_results.json": ["metrics.json", "reward.txt"], "scenario_results.json reward": "0.250000",
                   "metrics.json": ["reward.txt", "scenario_results.json"], "metrics.json reward": "0.250000"}


def test_the_replay_ends_well_inside_the_step_time_limit():
    """The replay's own deadline leaves room to load the scenarios, cut the last requests and wind down (about two
    minutes, QA 07d N6) before verify.py's hard stop, which leaves Harbor six minutes to upload the tests before and
    collect the results after."""
    config = tomllib.loads((TASK / "task.toml").read_text())
    limits = [config["verifier"]["timeout_sec"]] + [step["verifier"]["timeout_sec"] for step in config["steps"] if "timeout_sec" in step.get("verifier", {})]
    probe = ("import json, sys; sys.path.insert(0, sys.argv[1]); import verify; from verifier import replay as r; "
             "print(json.dumps([r.DEADLINE_SEC, r.START_SEC, r.REQUEST_SEC, r.HEALTH_SEC, verify.HARD_STOP_SEC]))")
    done = subprocess.run([sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests")], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[-2000:]
    deadline, start, request, health, hard_stop = json.loads(done.stdout)
    assert deadline + 240 <= hard_stop and hard_stop + 360 <= min(limits) and start + request + health < deadline
