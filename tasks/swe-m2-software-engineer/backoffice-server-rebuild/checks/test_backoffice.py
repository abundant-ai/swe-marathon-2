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
                           reference_python(), str(MEDIA)], capture_output=True, text=True, timeout=900)
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


def test_workspace_ids_are_rewritten_only_where_they_stand_alone():
    """Any id the instruction allows, even one character long, must not corrupt an answer."""
    probe = ("import json, sys; sys.path.insert(0, sys.argv[1]); from verifier.replay import normalise; "
             "answer = {'workspace': '1', 'total': 1100, 'name': 'Plant 1', 'url': '/api/ws/1/files/F-1/content', "
             "'list': ['1', 11, {'ws': '1'}], 'other': '/ws/12/x'}; print(json.dumps(normalise(answer, '1'), sort_keys=True))")
    done = subprocess.run([sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests")], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[-2000:]
    assert json.loads(done.stdout) == {"workspace": "{ws}", "total": 1100, "name": "Plant 1", "url": "/api/ws/{ws}/files/F-1/content",
                                       "list": ["{ws}", 11, {"ws": "{ws}"}], "other": "/ws/12/x"}


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

