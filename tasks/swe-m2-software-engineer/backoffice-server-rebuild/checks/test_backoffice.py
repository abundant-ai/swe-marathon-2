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
    oracle.oracle(common, server)
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
            for required in ("task.toml", "environment/Dockerfile", "environment/requirements.txt", "environment/sealed/stockwell/app.py",
                             "environment/sealed/stockwell/media/pdf.py", "environment/client/dist/index.html", "environment/client/src/main.tsx",
                             prefix + "instruction.md", prefix + "tests/verify.py", prefix + "tests/requirements.txt",
                             prefix + "tests/private/scenarios.json.gz", prefix + "solution/oracle.py", prefix + "solution/data/stockwell/api_routes.py"):
                assert (bundle / required).is_file(), required
            config = (bundle / "task.toml").read_text()
            assert ("[[steps]]" in config) == (not flag)
            # the candidate image must never receive the scenarios, the verifier or the client's test helpers
            environment = list((bundle / "environment").rglob("*"))
            assert not any("scenarios" in path.name or "replay" in path.name for path in environment)
            assert not any(".test." in path.name or "smoke" in path.name for path in environment)
            assert not any(path.suffix == ".py" for path in (bundle / "environment" / "client").rglob("*"))
            # the visible media ships as samples; the private media reaches the verifier only, byte for byte nowhere else
            private_media = {path.read_bytes() for path in (bundle / f"{prefix}tests/private/media").rglob("*") if path.is_file()}
            shipped = {path.read_bytes() for path in (bundle / "environment").rglob("*") if path.is_file()}
            assert private_media and not private_media & shipped
            assert any((bundle / "environment" / "samples" / "pdf").iterdir())
            assert not (bundle / "environment" / "samples" / "manifest.json").exists()
            # Stockwell's own test fixtures are inputs of the hidden `files` scenarios: none of them ships, under any name
            fixtures = {path.read_bytes() for path in (REFERENCE / "backend" / "tests" / "fixtures").rglob("*") if path.is_file()}
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

    def log_message(self, *args):
        pass

server = ThreadingHTTPServer(("127.0.0.1", 0), Echo)
threading.Thread(target=server.serve_forever, daemon=True).start()
media = Media(Path(sys.argv[2]))
connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
steps = [{"body_file": "video/clip.mp4", "headers": {"content-type": "video/mp4"}},
         {"body_size": 70000, "headers": {"content-type": "application/octet-stream"}},
         {"body": {"a": 1}, "headers": {}}]
out = [exchange(connection, "POST", "/x", step["headers"], step.get("body"), media.body(step)) for step in steps]
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
    first, sized, plain, escape = json.loads(done.stdout)
    assert first[0] == 201 and first[1]["type"] == "video/mp4" and first[1]["bytes"] == 112
    assert sized[0] == 201 and sized[1]["type"] == "application/octet-stream" and sized[1]["bytes"] == 70000
    assert plain[1]["type"] == "application/json" and escape == "refused"


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
    corpus = {"recorded_with": {"seed": 1}, "scenarios": [
        {"id": "S1", "theme": "files", "steps": [upload(other), upload(sample)]},
        {"id": "S2", "theme": "files", "steps": [upload(sample[:150]), upload(sample[:10]), raw("photo/q.jpg"), clean]},
        {"id": "S3", "theme": "media", "steps": [raw("photo/p.jpg"), answer, raw("photo/missing.jpg")]}]}
    (private / "scenarios.json.gz").write_bytes(gzip.compress(json.dumps(corpus, indent=1).encode()))
    done = subprocess.run([sys.executable, "-I", "-B", str(TASK / "scripts" / "scan_uploads.py"), str(bundle)], capture_output=True, text=True,
                          timeout=60)
    assert done.returncode == 1, done.stderr[-2000:]
    report = json.loads(done.stdout)
    found = sorted((leak["where"].split()[0], leak["what"], leak["file"]) for leak in report["leaks"])
    assert found == [("S1", "base64 upload (equal)", "environment/samples/photo.jpg"),
                     ("S2", "base64 upload (prefix)", "environment/samples/photo.jpg"),
                     ("S3", "body_file upload (equal)", "environment/samples/photo.jpg"),
                     ("S3", "file answer", "environment/client/index.html")]
    assert report["scenarios"] == 3 and report["steps"] == 9 and len(report["missing"]) == 1 and report["file_answers"] == 2


def test_the_candidate_cannot_replace_the_delivery_directory():
    """A candidate that owned /app could swap /app/server for a symbolic link to the sealed server, and the root-run
    collector would copy what the link points to. /app is root's and sticky, /app/server root's and writable by all."""
    docker = (TASK / "environment" / "Dockerfile").read_text()
    owned = docker.index("chown -R dev:dev /app")
    assert owned < docker.index("chown root:root /app /app/server") and "chmod 1777 /app " in docker and "chmod 0777 /app/server" in docker
    assert "safe.directory '*'" in docker


FAKE_SERVER = r'''
import json, os, secrets, signal, socket, sys, threading, time

MODE = sys.argv[1]
STATE = os.path.join(os.environ["DATA_DIR"], "tallies.json")  # disk: written before each answer; lazy: only on SIGTERM
STASH = os.path.join(os.environ["DATA_DIR"], "seen.json")
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
            if "/orders/" in path or "/payments/" in path or "/check/" in path:
                # buggy: every order total one cent short. preview (QA 07 F1): the same, but it keeps what a month's
                # payments reveal, gives no answer at the month's end to earn a second try, and answers from what it kept
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
                    send(conn, 200, json.dumps({"paid": json.loads(body)["amount"]}).encode())
                elif "/check/" in path and MODE == "preview" and earlier is None:
                    return
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
    """Every tenth scenario makes the server exit. The others, including those in flight beside it, all count."""
    scenarios = [{"id": f"S{i:03d}", "theme": "crash" if i % 10 == 3 else "fine",
                  "steps": [step("/items/1"), step("/crash" if i % 10 == 3 else "/items/2"), step("/items/3")]} for i in range(80)]
    out = drive(tmp_path, "plain", scenarios)
    metrics = out["metrics"]
    assert metrics["scenarios_matched"] == 72 and metrics["by_theme"] == {"crash": {"total": 8, "matched": 0}, "fine": {"total": 72, "matched": 72}}
    assert metrics["restarts"] >= 8 and metrics["unfinished"] == 0 and not metrics["notes"]


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
    """QA 07 F1, reproduced and closed. A server that keeps what a month's later requests reveal, gives no answer at the
    end to earn a second try, and answers from what it kept, scored 1.0 where it earns 0.33. A second try now starts
    from a clean slate (server stopped, DATA_DIR removed, and when sandboxed its user's processes and files anywhere) and
    decides only the units the first try left unanswered."""
    months = [month_of_trading(number) for number in range(6)]
    honest = drive(tmp_path / "honest", "buggy", months)["metrics"]
    assert honest["reward"] == round(1 / 3, 6) and honest["retried"] == 0
    no_slate, no_lock = "replay.Candidate.clean_slate = lambda self: None\n", "replay.merge_retry = lambda first, second: second\n"
    exploit = drive(tmp_path / "exploit", "preview", months, setup=no_slate + no_lock)["metrics"]
    assert exploit["reward"] == 1.0 and exploit["retried"] == 6, "without either defence the preview pays"
    lock_only = drive(tmp_path / "lock", "preview", months, setup=no_slate)["metrics"]
    assert lock_only["reward"] == round(2 / 3, 6), "with the lock alone, what it kept still reaches the day it left unanswered"
    slate_only = drive(tmp_path / "slate", "preview", months, setup=no_lock)["metrics"]
    both = drive(tmp_path / "both", "preview", months)["metrics"]
    assert slate_only["reward"] == both["reward"] == honest["reward"] and both["retried"] == 6


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
    assert not (after / "gone").exists() and not (after / "pipe").exists() and len(fixed.stdout.splitlines()) >= 4
    config = tomllib.loads((TASK / "task.toml").read_text())
    assert config["verifier"]["collect"] == [{"command": "/usr/local/sbin/prepare-delivery", "user": "root", "timeout_sec": 600}]
    docker = (TASK / "environment" / "Dockerfile").read_text()
    assert "COPY prepare-delivery /usr/local/sbin/prepare-delivery" in docker and "/usr/local/sbin/prepare-delivery" in docker.split("chmod 0700")[-1]


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
    """The replay's own deadline leaves room to load the scenarios, cut the last requests and publish the reward."""
    config = tomllib.loads((TASK / "task.toml").read_text())
    limits = [config["verifier"]["timeout_sec"]] + [step["verifier"]["timeout_sec"] for step in config["steps"] if "timeout_sec" in step.get("verifier", {})]
    probe = "import json, sys; sys.path.insert(0, sys.argv[1]); from verifier import replay as r; print(json.dumps([r.DEADLINE_SEC, r.START_SEC, r.REQUEST_SEC, r.HEALTH_SEC]))"
    done = subprocess.run([sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests")], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[-2000:]
    deadline, start, request, health = json.loads(done.stdout)
    assert deadline + 300 <= min(limits) and start + request + health < deadline
