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
import shlex
import shutil
import signal
import subprocess
import sys
import time
import tomllib
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
STEP = TASK
MEDIA = (
    TASK / "experiment" / "media" / "private"
)  # the uploads the media scenarios use, when the author's machine has them

sys.path.insert(0, str(TASK / "scripts"))

import itertools

import package_step
from reference import checkout, python

REFERENCE = checkout()


def reference_python() -> str:
    done = subprocess.run(
        [*python(REFERENCE), "-c", "import sys; print(sys.executable)"],
        check=False,
        capture_output=True,
        text=True,
        timeout=600,
    )
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
    oracle.oracle(common, server, step / "environment" / "stockwell.env")  # the source, with the task's settings
    run = server / "run"
    run.write_text(run.read_text().replace("/opt/py/bin/python", interpreter))
if defect == "rounding":
    path = server / "stockwell" / "platform" / "money.py"
    path.write_text(path.read_text().replace("if 2 * remainder >= abs(denominator):", "if 2 * remainder > abs(denominator):"))
if defect == "crash":
    (server / "run").write_text("#!/bin/sh\\nexit 3\\n")
if defect == "bare creation":  # POST /api/workspaces answers the new id alone
    app = server / "stockwell" / "app.py"
    text = app.read_text()
    assert text.count("response = JSONResponse(view, status_code=201)") == 1
    app.write_text(text.replace("response = JSONResponse(view, status_code=201)", 'response = JSONResponse({"id": view["id"]}, status_code=201)'))
if defect.startswith("without ") or defect == "health body":
    app = server / "stockwell" / "app.py"
    app.write_text(app.read_text() + WITHOUT.replace("GONE", repr(defect[8:] if defect != "health body" else "[]"))
                   .replace("HEALTH", str(defect == "health body")))
print(json.dumps(evaluate(server, scenarios, work / "w", work, sandbox=False, media_dir=Path(sys.argv[7]))))
"""
# appended to the installed reference's app.py: the calls listed in GONE ([method, full-path pattern] pairs) answer 404 as
# an unknown path does, and with HEALTH true the health check answers 200 with another body
WITHOUT = """

_create_app = create_app


def create_app(settings=None):
    import json as _json
    import re as _re

    inner = _create_app(settings)
    gone = [(method, _re.compile(pattern)) for method, pattern in _json.loads(GONE)]

    async def without(scope, receive, send):
        if scope["type"] == "http":
            body = None
            if any(scope["method"] == method and pattern.fullmatch(scope["path"]) for method, pattern in gone):
                status, body = 404, b'{"error":{"code":"unknown_path","message":"no such path"}}'
            elif HEALTH and scope["path"] == "/api/health":
                status, body = 200, b'{"status":"up"}'
            if body is not None:
                message = {"more_body": True}
                while message.get("more_body"):
                    message = await receive()
                await send({"type": "http.response.start", "status": status,
                            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
                await send({"type": "http.response.body", "body": body})
                return
        await inner(scope, receive, send)

    return without
"""
GRADE = GRADE.replace(
    "import oracle\n", "import oracle\nWITHOUT = " + repr(WITHOUT) + "\n"
)


def media_copy(tmp_path: Path) -> Path:
    """A writable copy of the private media set (when this machine has it) that the live recorder adds a month's files to."""
    target = tmp_path / "media"
    if not target.exists():
        if (MEDIA / "manifest.json").is_file():
            shutil.copytree(MEDIA, target, ignore=shutil.ignore_patterns("trading"))
        else:
            target.mkdir()
    return target


def record(
    tmp_path: Path, seed: int, count: int = 54, runs: int = 2, routines: int = 2
) -> Path:
    """A small corpus: legacy streams and media scenarios, `runs` months of trading (one restarted with SIGTERM, one with
    SIGKILL) with three client screens after each, and `routines` scenarios of each office routine."""
    out = tmp_path / f"scenarios-{seed}.json"
    done = subprocess.run(
        [
            sys.executable,
            "-B",
            str(TASK / "scripts" / "record_scenarios.py"),
            "--count",
            str(count),
            "--runs",
            str(runs),
            "--term",
            "1",
            "--kill",
            "1",
            "--screens",
            "3",
            "--routines",
            str(routines),
            "--seed",
            str(seed),
            "--out",
            str(out),
            "--media",
            str(media_copy(tmp_path)),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=1800,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    return out


def grade(
    tmp_path: Path, scenarios: Path, defect: str, media: Path | None = None
) -> dict:
    work = tmp_path / (
        defect
        if re.fullmatch(r"\w+", defect)
        else "defect-" + hashlib.sha256(defect.encode()).hexdigest()[:12]
    )
    work.mkdir()
    done = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            GRADE,
            str(STEP),
            str(REFERENCE / "backend" / "src"),
            str(scenarios),
            str(work),
            defect,
            reference_python(),
            str(media or media_copy(tmp_path)),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=1800,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_recording_is_deterministic_and_never_hits_a_server_error(tmp_path):
    first = record(tmp_path, 11)
    kept = first.read_bytes()
    assert record(tmp_path, 11).read_bytes() == kept
    data = json.loads(kept)
    # the corpus ships to the verifier image, so it holds the scenarios alone; how they were recorded, the seed included,
    # goes to the record beside it (experiment/recording.json for the task's own corpus)
    assert list(data) == ["scenarios"] and kept.startswith(b'{"scenarios":[')
    recording = json.loads(first.with_suffix(".recording.json").read_text())
    assert recording["corpus_sha256"] == hashlib.sha256(kept).hexdigest()
    assert recording["recorded_with"]["legacy"]["seed"] == 11 and {
        "left_out",
        "legacy_commit",
    } <= set(recording["recorded_with"]["legacy"])
    assert {"runs", "term", "kill", "screens"} <= set(
        recording["recorded_with"]["live"]
    )
    statuses = {
        step["status"] for scenario in data["scenarios"] for step in scenario["steps"]
    }
    assert (
        all(status < 500 for status in statuses)
        and {200, 201, 403, 409, 422} <= statuses
    )
    themes = {s["theme"] for s in data["scenarios"]}
    with_media = (MEDIA / "manifest.json").is_file()
    assert (
        len(themes) == 27 + with_media + len(ROUTINE_THEMES)
        and "trading" in themes
        and ("media" in themes) == with_media
    )
    # two scenarios of each office routine, last, one unit each, numbered R00001 on
    routines = [s for s in data["scenarios"] if s["theme"] in ROUTINE_THEMES]
    assert [s["theme"] for s in routines] == [
        theme for theme in ROUTINE_THEMES for _ in range(2)
    ] and data["scenarios"][-len(routines) :] == routines
    assert [s["id"] for s in routines] == [
        f"R{n:05d}" for n in range(1, len(routines) + 1)
    ] and not any("units" in s for s in routines)
    assert recording["recorded_with"]["live"]["routines"] == 2
    assert any(
        "binary" in step["json"]
        for scenario in data["scenarios"]
        for step in scenario["steps"]
    )
    # a month of trading: one unit per day from 2031-03-03 into April, the client's screens after it, two planned restarts
    months = [s for s in data["scenarios"] if s["theme"] == "trading"]
    assert len(months) == 2 and all(
        30 <= sum(unit["theme"] == "trading" for unit in s["units"]) <= 35
        for s in months
    )
    assert any(unit["theme"] == "screens" for s in months for unit in s["units"])
    assert sorted(
        step["restart"] for s in months for step in s["steps"] if "restart" in step
    ) == ["kill", "term"]
    paths = {step["path"] for s in months for step in s["steps"]}
    assert {
        "/ledger/periods/close",
        "/api/version",
        "/auth/me",
        "/files/upload",
    } <= paths
    assert any(
        step.get("body_file", "").startswith("trading/invoices/")
        for s in months
        for step in s["steps"]
    )


def test_verifier_scores_the_reference_one_and_defects_lower(tmp_path):
    scenarios = record(tmp_path, 12)
    total = len(json.loads(scenarios.read_text())["scenarios"])
    reference = grade(tmp_path, scenarios, "none")
    assert (
        reference["reward"] == 1.0
        and reference["units_total"] > total
        and reference["planned_restarts"] == 2
    )
    wrong = grade(tmp_path, scenarios, "rounding")
    assert 0.0 < wrong["reward"] < 1.0 and wrong["scenarios_total"] == total
    for defect in ("crash", "missing"):
        result = grade(tmp_path, scenarios, defect)
        assert (
            result["reward"] == 0.0
            and result["scenarios_total"] == total
            and result["notes"]
        )


# the office routines (scripts/record_live.py ROUTINES), in recording order
ROUTINE_THEMES = (
    "users",
    "workspace",
    "price-lists",
    "promotions",
    "suppliers",
    "saved-reports",
    "journal-reversals",
    "carriers",
    "standing-orders",
)
# documented calls whose answers may differ, as the instruction says: password sign-in, sessions and API keys, the
# calls that set or change a user's password, and the request log (`/metrics` is not in the API description; the
# graded POST /files/{id}/unlock opens a password-protected PDF and is not one of them)
EXCEPTED = {
    ("POST", "/api/ws/{ws}/auth/login"),
    ("POST", "/api/ws/{ws}/auth/logout"),
    ("POST", "/api/ws/{ws}/auth/password"),
    ("PUT", "/api/ws/{ws}/users/{id}/password"),
    ("GET", "/api/ws/{ws}/auth/credentials"),
    ("POST", "/api/ws/{ws}/auth/api-keys"),
    ("DELETE", "/api/ws/{ws}/auth/credentials/{id}"),
    ("GET", "/api/ws/{ws}/admin/requests"),
}
# what the routines brought into the corpus (round 16), by the call a server could leave out: [method, full-path pattern]
ADDED = {
    "the workspace summary": [["GET", r"/api/ws/[^/]+"]],
    "readiness": [["GET", r"/api/ready"]],
    "the API description": [["GET", r"/api/openapi\.json"]],
    "one user": [["GET", r"/api/ws/[^/]+/users/[^/]+"]],
    "a user changed": [["PATCH", r"/api/ws/[^/]+/users/[^/]+"]],
    "a user brought back": [["POST", r"/api/ws/[^/]+/users/[^/]+/activate"]],
    "the permission table": [["GET", r"/api/ws/[^/]+/auth/permissions"]],
    "the price lists": [["GET", r"/api/ws/[^/]+/price-lists"]],
    "a new price list": [["POST", r"/api/ws/[^/]+/price-lists"]],
    "the promotions": [["GET", r"/api/ws/[^/]+/promotions"]],
    "a new supplier": [["POST", r"/api/ws/[^/]+/suppliers"]],
    "a supplier unblocked": [["POST", r"/api/ws/[^/]+/suppliers/[^/]+/unblock"]],
    "one saved report": [["GET", r"/api/ws/[^/]+/reports/saved/[^/]+"]],
    "a journal entry reversed": [
        ["POST", r"/api/ws/[^/]+/ledger/journal/[^/]+/reverse"]
    ],
    "a carrier brought back": [["POST", r"/api/ws/[^/]+/carriers/[^/]+/activate"]],
    "a standing order resumed": [
        ["POST", r"/api/ws/[^/]+/standing-orders/[^/]+/resume"]
    ],
}
# the statuses each documented call is answered with in a corpus: [method, template, pattern, rank] in argv[3]; a step
# goes to its most specific template (literal segments first, so /stock/counts is never taken for a parameter)
ANSWERED = r"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from verifier.replay import iter_scenarios
calls = [(method, path, re.compile(pattern), tuple(rank)) for method, path, pattern, rank in json.loads(sys.argv[3])]
answered, steps, created = {}, {}, []
for scenario in iter_scenarios(Path(sys.argv[2]).read_text()):
    for number, step in enumerate(scenario["steps"], start=1):
        full = step["path"] if step.get("scoped", True) is False else "/api/ws/WS" + step["path"]
        found = [(rank, method, path) for method, path, pattern, rank in calls if method == step["method"] and pattern.fullmatch(full)]
        if found:
            _, method, path = max(found)
            answered.setdefault(method + " " + path, set()).add(step["status"])
        if len(sys.argv) > 4:
            steps.setdefault(scenario["id"], []).append([step["method"], full])
    if "created" in scenario:
        created.append(scenario["id"])
print(json.dumps({"answered": {key: sorted(value) for key, value in answered.items()}, "steps": steps, "created": created}))
"""


def documented_calls() -> list[list]:
    """Every operation of the API description the client ships (the sealed server serves the same document), and the
    description itself, which the instruction names: [method, template, pattern, rank]."""
    paths = json.loads((REFERENCE / "frontend" / "openapi.json").read_text())["paths"]
    calls = [
        [
            method.upper(),
            path,
            "/".join(
                "[^/]+" if part.startswith("{") else re.escape(part)
                for part in path.split("/")
            ),
            [0 if part.startswith("{") else 1 for part in path.split("/")],
        ]
        for path, item in paths.items()
        for method in item
        if method in ("get", "post", "put", "patch", "delete")
    ]
    return calls + [["GET", "/api/openapi.json", r"/api/openapi\.json", [1, 1, 1]]]


def answered(corpus: Path, with_steps: bool = False) -> dict:
    done = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            ANSWERED,
            str(STEP / "tests"),
            str(corpus),
            json.dumps(documented_calls()),
            *(["steps"] if with_steps else []),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout)


def test_every_documented_call_outside_the_exceptions_is_answered_in_the_corpus():
    """The verdict on version 11 (should-fix, from the source audit): the corpus never called GET /api/ws/{ws}, GET and
    POST /price-lists, GET /users/{id} or POST /users/{id}/activate, so a server answering 404 there lost nothing. Round
    16's audit of all 242 documented operations found 21 never called, 8 of them excepted by the instruction, and four
    more the corpus only ever saw refused (bringing a carrier back, reversing a journal entry, unblocking a supplier,
    resuming a standing order); the health check's answer was never compared and the API description never fetched.
    The office routines call each of them. Every documented call outside the exceptions is now answered with success
    somewhere in the task's corpus, and the excepted ones, named in the instruction, nowhere."""
    corpus = STEP / "tests" / "private" / "scenarios.json"
    assert corpus.is_file(), "record the scenarios first: scripts/record_scenarios.py"
    calls = documented_calls()
    found = answered(corpus)
    statuses = found["answered"]
    assert len(calls) == 243 and EXCEPTED <= {
        (method, path) for method, path, _, _ in calls
    }
    # POST /api/workspaces is the replay's own first call in every scenario (201 and a usable id, or nothing else
    # counts), and the scenarios that hold `created` judge its answer too
    assert "POST /api/workspaces" not in statuses and len(found["created"]) >= 12
    missing = [
        f"{method} {path}"
        for method, path, _, _ in calls
        if (method, path) not in EXCEPTED | {("POST", "/api/workspaces")}
        and not any(
            200 <= status < 300 for status in statuses.get(f"{method} {path}", [])
        )
    ]
    assert missing == [], missing
    assert not [
        f"{method} {path}"
        for method, path in EXCEPTED
        if f"{method} {path}" in statuses
    ]
    instruction = " ".join((STEP / "instruction.md").read_text().split())
    assert (
        "password sign-in, sessions and API keys, which we do not use, and the request log and `/metrics`, which are for operators. Those "
        "may differ, and so may the answers to the calls that set or change a user's password, which we do not use either."
    ) in instruction


def test_routines_recorded_onto_a_corpus_are_what_a_full_recording_gives(tmp_path):
    """Round 16 added the office routines to the task's corpus with --append instead of recording it all again, so that
    no scenario it held could change: the result must be byte for byte the file a full recording with the same seed and
    --routines gives, the record must follow it, a second append must be refused, and no media is touched."""
    media = tmp_path / "media"
    media.mkdir()
    script = [
        sys.executable,
        "-B",
        str(TASK / "scripts" / "record_scenarios.py"),
        "--seed",
        "14",
    ]
    base, full = tmp_path / "base.json", tmp_path / "full.json"
    for out, extra in ((base, []), (full, ["--routines", "2"])):
        done = subprocess.run(
            [*script, "--count", "8", "--media", str(media), "--out", str(out), *extra],
            check=False,
            capture_output=True,
            text=True,
            timeout=1800,
        )
        assert done.returncode == 0, done.stderr[-2000:]
    held = base.read_bytes()
    done = subprocess.run(
        [*script, "--append", "--routines", "2", "--out", str(base)],
        check=False,
        capture_output=True,
        text=True,
        timeout=1800,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    grown = base.read_bytes()
    assert (
        grown == full.read_bytes()
        and grown.startswith(held[:-3])
        and len(grown) > len(held)
    )
    record = json.loads(base.with_suffix(".recording.json").read_text())
    assert (
        record["corpus_sha256"] == hashlib.sha256(grown).hexdigest()
        and record["recorded_with"]["live"]["routines"] == 2
    )
    assert (
        record["recorded_with"]["legacy"]
        == json.loads(full.with_suffix(".recording.json").read_text())["recorded_with"][
            "legacy"
        ]
    )
    again = subprocess.run(
        [*script, "--append", "--routines", "2", "--out", str(base)],
        check=False,
        capture_output=True,
        text=True,
        timeout=1800,
    )
    assert (
        again.returncode != 0
        and "holds routines already" in again.stderr
        and base.read_bytes() == grown
    )
    assert not any(media.iterdir())


def test_a_server_without_a_call_the_routines_make_loses_their_units(tmp_path):
    """The verdict's check, for each call the routines brought into the corpus: the reference without it (answering 404
    as for an unknown path) loses exactly the scenarios that make it, each at its first such call, and nothing else; a
    health check that answers 200 with another body loses the workspace scenarios, and so does a workspace created with
    an answer that holds its id alone (the replay judges `created`, before the first step). The reference scores 1, a
    missing server 0."""
    corpus = tmp_path / "routines.json"
    corpus.write_text('{"scenarios":[]}\n')
    done = subprocess.run(
        [
            sys.executable,
            "-B",
            str(TASK / "scripts" / "record_scenarios.py"),
            "--append",
            "--routines",
            "2",
            "--seed",
            "15",
            "--out",
            str(corpus),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=1800,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    found = answered(corpus, with_steps=True)
    steps, created = found["steps"], found["created"]
    themes = {
        scenario["id"]: scenario["theme"]
        for scenario in json.loads(corpus.read_text())["scenarios"]
    }
    assert len(steps) == 2 * len(ROUTINE_THEMES) and sorted(
        set(themes.values())
    ) == sorted(ROUTINE_THEMES)
    assert created and {themes[sid] for sid in created} == {"workspace"}
    media = tmp_path / "no-media"
    media.mkdir()
    assert grade(tmp_path, corpus, "none", media)["reward"] == 1.0
    assert grade(tmp_path, corpus, "missing", media)["reward"] == 0.0
    cases = {
        name: (f"without {json.dumps(calls)}", calls) for name, calls in ADDED.items()
    }
    cases["the health check's answer"] = ("health body", [["GET", r"/api/health"]])
    cases["the answer a workspace is created with"] = ("bare creation", None)
    for name, (defect, calls) in cases.items():
        hit = (
            {sid: 0 for sid in created}
            if calls is None
            else {
                sid: next(
                    n
                    for n, (method, path) in enumerate(made, start=1)
                    if any(method == m and re.fullmatch(p, path) for m, p in calls)
                )
                for sid, made in steps.items()
                if any(
                    method == m and re.fullmatch(p, path)
                    for method, path in made
                    for m, p in calls
                )
            }
        )
        result = grade(tmp_path, corpus, defect, media)
        failed = {
            r["id"]: r["failed_step"] for r in result["results"] if not r["matched"]
        }
        assert hit and failed == hit, (name, failed, hit)
        assert result["reward"] == round(1 - len(hit) / len(steps), 6), (
            name,
            result["reward"],
        )


def test_client_reaches_nearly_every_endpoint_of_the_reference():
    """The client's source names at least 95% of the endpoints; the API description lists them all."""
    probe = (
        "import sys, json; sys.path.insert(0, sys.argv[1]); from stockwell.api_routes import all_endpoints; "
        "print(json.dumps([[e.method, e.path] for e in all_endpoints()]))"
    )
    done = subprocess.run(
        [reference_python(), "-c", probe, str(REFERENCE / "backend" / "src")],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    endpoints = json.loads(done.stdout.strip().splitlines()[-1])
    client = REFERENCE / "frontend" / "src"
    source = "\n".join(
        path.read_text()
        for path in client.rglob("*.ts*")
        if path.name != "schema.d.ts" and "test" not in path.parts
    )
    reached = 0
    for _, template in endpoints:
        parts = re.split(r"\{[a-z_]+\}", template)
        pattern = r"(\$\{[^}]+\}|\{[a-z_]+\}|[A-Za-z0-9_-]+)".join(
            re.escape(part) for part in parts
        )
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
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PORT": str(port),
        "DATA_DIR": str(data),
        "STOCKWELL_PYTHON": reference_python(),
    }
    proc = subprocess.Popen(
        [str(server / "run")],
        cwd=server,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        end = time.monotonic() + 60
        while time.monotonic() < end and proc.poll() is None:
            try:
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                connection.request("GET", "/api/health")
                if connection.getresponse().status == 200:
                    connection = http.client.HTTPConnection(
                        "127.0.0.1", port, timeout=30
                    )
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
    made_media = [
        kind
        for kind in ("visible", "private")
        if not (media / kind / "manifest.json").exists()
    ]
    for kind in (
        made_media
    ):  # stand-ins when the real sets (scripts/make_media.py) are not on this machine
        (media / kind / "pdf").mkdir(parents=True, exist_ok=True)
        (media / kind / "pdf" / "scan.pdf").write_bytes(
            f"%PDF-1.4 {kind} stand-in".encode()
        )
        (media / kind / "manifest.json").write_text("{}")
    built = {}
    try:
        for flag, kind in (([], "bundles"), (["--flat"], "flat")):
            done = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(TASK / "scripts" / "package_step.py"),
                    *flag,
                    "--output",
                    str(tmp_path / "out"),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=300,
            )
            assert done.returncode == 0, done.stderr[-2000:]
            bundle = built[kind] = Path(json.loads(done.stdout)["task_path"])
            assert bundle.parent.parent.name == kind
            for excluded in ("README.md", "checks", "scripts", "common", "experiment"):
                assert not (bundle / excluded).exists(), excluded
            for required in (
                "task.toml",
                "environment/Dockerfile",
                "environment/requirements.txt",
                "environment/sealed/stockwell/app.pyc",
                "environment/sealed/stockwell/media/pdf.pyc",
                "environment/client/dist/index.html",
                "environment/client/src/main.tsx",
                "environment/fsmaint-sweep",
                "instruction.md",
                "tests/verify.py",
                "tests/requirements.txt",
                "tests/private/scenarios.json.gz",
                "solution/oracle.py",
                "solution/data/stockwell/api_routes.py",
                "solution/data/stockwell.env",
            ):
                assert (bundle / required).is_file(), required
            # the corpus ships to the verifier image with its scenarios alone: how they were recorded (the seed, the legacy
            # commit, the counts left out, the media set's digest) stays in experiment/recording.json, which is never packaged
            assert package_step.corpus_keys(
                gzip.decompress(
                    (bundle / "tests/private/scenarios.json.gz").read_bytes()
                ).decode()
            ) == ["scenarios"]
            assert not [
                path
                for path in bundle.rglob("*")
                if path.name in ("recording.json", "seeds.json")
                or path.name.endswith(".recording.json")
            ]
            # the solution only installs the server: it probes nothing of the machine it runs on
            solve = (bundle / "solution" / "solve.sh").read_text()
            assert "oracle.py" in solve and not re.search(
                r"curl|wget|8080|/api/", solve
            ), solve
            # the solution as the platform runs it: from its own folder with nothing of the task around it (the round 4
            # oracle looked beside the task's tree, crashed on Oddish and scored 0): it installs a server that starts
            alone = tmp_path / f"alone-{kind}"
            shutil.copytree(bundle / "solution", alone / "solution")
            # on the platform it runs from /solution, which has one parent: it must never look above its own folder
            assert ".parents" not in (alone / "solution" / "oracle.py").read_text()
            installed = alone / "server"
            done = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-B",
                    str(alone / "solution" / "oracle.py"),
                    str(installed),
                ],
                check=False,
                cwd=alone,
                capture_output=True,
                text=True,
                timeout=120,
            )
            assert done.returncode == 0, done.stdout[-1000:] + done.stderr[-2000:]
            assert (installed / "stockwell.env").read_text() == (
                TASK / "environment" / "stockwell.env"
            ).read_text()
            assert (
                (installed / "stockwell" / "app.py").is_file()
                and not any(installed.rglob("*.pyc"))
                and os.access(installed / "run", os.X_OK)
            )
            if not flag:
                assert serve_once(installed), (
                    "the packaged solution's server did not start and give a workspace"
                )
            # QA 08: the sealed server, in the agent's image, is Python 3.12 bytecode alone, never source
            sealed = bundle / "environment" / "sealed" / "stockwell"
            assert not any(path.suffix == ".py" for path in sealed.rglob("*")), sealed
            assert all(
                path.read_bytes()[:4] == b"\xcb\r\r\n" for path in sealed.rglob("*.pyc")
            ), "Python 3.12 bytecode"
            # version 12's audit (Q-09): the solution's data is the readable source, and it is the sealed program: one source
            # file for each sealed module and none besides, each compiled as the sealed copy is (Python 3.12, unchecked-hash
            # headers, the sealed path) giving the sealed .pyc byte for byte
            source = bundle / "solution" / "data" / "stockwell"
            modules = sorted(
                path.relative_to(source).as_posix()[:-3]
                for path in source.rglob("*.py")
            )
            assert len(modules) > 150 and not any(
                path.suffix == ".pyc" for path in source.rglob("*")
            )
            assert modules == sorted(
                path.relative_to(sealed).as_posix()[:-4]
                for path in sealed.rglob("*.pyc")
            )
            again = tmp_path / f"again-{kind}"
            jobs = [
                [
                    str(source / f"{module}.py"),
                    str(again / f"{module}.pyc"),
                    f"/opt/stockwell/app/stockwell/{module}.py",
                ]
                for module in modules
            ]
            done = subprocess.run(
                [*package_step.python312(REFERENCE), "-I", "-c", package_step.COMPILE],
                check=False,
                input=json.dumps(jobs),
                text=True,
                capture_output=True,
                timeout=300,
            )
            assert done.returncode == 0, done.stderr[-2000:]
            assert [
                module
                for module in modules
                if (again / f"{module}.pyc").read_bytes()
                != (sealed / f"{module}.pyc").read_bytes()
            ] == []
            config = (bundle / "task.toml").read_text()
            assert ("[[steps]]" in config) == (
                not flag
            ) and "[[verifier.collect]]" in config
            # the candidate image must never receive the scenarios, the verifier or the client's test helpers
            environment = list((bundle / "environment").rglob("*"))
            assert not any(
                "scenarios" in path.name or "replay" in path.name
                for path in environment
            )
            assert not any(
                ".test." in path.name or "smoke" in path.name for path in environment
            )
            assert not any(
                path.suffix == ".py"
                for path in (bundle / "environment" / "client").rglob("*")
            )
            # the visible media ships as samples; the private media reaches the verifier only, byte for byte nowhere else
            private_media = {
                digest(path)
                for path in (bundle / "tests/private/media").rglob("*")
                if path.is_file()
            }
            shipped = {
                digest(path)
                for path in (bundle / "environment").rglob("*")
                if path.is_file()
            }
            assert private_media and not private_media & shipped
            assert any((bundle / "environment" / "samples" / "pdf").iterdir())
            assert not (bundle / "environment" / "samples" / "manifest.json").exists()
            # Stockwell's own test fixtures are inputs of the hidden `files` scenarios: none of them ships, under any name
            fixtures = {
                digest(path)
                for path in (REFERENCE / "backend" / "tests" / "fixtures").rglob("*")
                if path.is_file()
            }
            assert len(fixtures) > 100 and not fixtures & shipped
            if not flag:
                # no upload in the hidden scenarios (base64 in a JSON body, or a raw file), no cut-short upload and no file
                # answer is a file the candidate's image receives (scripts/scan_uploads.py reads the corpus once)
                done = subprocess.run(
                    [
                        sys.executable,
                        "-I",
                        "-B",
                        str(TASK / "scripts" / "scan_uploads.py"),
                        str(bundle),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
                assert done.returncode in (0, 1) and done.stdout, done.stderr[-3000:]
                report = json.loads(done.stdout)
                assert (
                    done.returncode == 0
                    and report["leaks"] == []
                    and report["missing"] == []
                ), done.stdout[-3000:]
                if not created and not made_media:
                    assert (
                        report["scenarios"] > 1000
                        and report["base64"] > 100
                        and report["body_file"] > 100
                        and report["file_answers"] > 100
                    )
            # nothing the agent can read names how the work is judged (the sealed server is bytecode it cannot read)
            words = re.compile(
                r"oracle|verifier|grading|hidden test|parity|record_corpus|scenario|benchmark|harbor|oddish|reward|watchdog|precap|"
                r"submission|audit|deadline",
                re.IGNORECASE,
            )
            for path in (bundle / "environment").rglob("*"):
                if (
                    path.is_file()
                    and "sealed" not in path.parts
                    and "dist" not in path.parts
                    and path.suffix not in (".png", ".jpg", ".mp4", ".pdf", ".gif")
                ):
                    assert not words.search(path.read_text(errors="replace")), path
            # no file that reaches the agent's image states the sealed server's stack (QA 08 M1): requirements.txt is
            # removed in the build right after the install, and the sealed bytecode is its own user's alone
            for path in (bundle / "environment").rglob("*"):
                if (
                    path.is_file()
                    and "sealed" not in path.parts
                    and path.name != "requirements.txt"
                ):
                    assert not STACK.search(
                        path.read_bytes().decode(errors="replace")
                    ), path
            # the task's own files in the image read as ordinary system housekeeping: nothing in them says how, when or
            # whether the work is packed, judged or ended, and nothing of how the task was made
            housekeeping = re.compile(
                r"oracle|verif|grad|hidden|parity|scenario|benchmark|harbor|oddish|reward|platform|watchdog|precap|deliver|"
                r"submission|collect|audit|\bqa\b|budget|deadline|attempt|\bcap\b|capped|owner|\bround\b|2026-|modal|archil|"
                r"trial|harness|\bscor",
                re.IGNORECASE,
            )
            for name in (
                "Dockerfile",
                "entrypoint.sh",
                "fsmaint-sweep",
                "start-stockwell",
                "stockwell-supervisor",
                "stockwell.env",
                ".dockerignore",
            ):
                found = housekeeping.search((bundle / "environment" / name).read_text())
                assert found is None, f"{name}: {found.group(0)!r}"
            # version 13's verdict: nothing that reaches the agent's image calls the old server sealed, in a name or in a
            # file's text; the one name that holds the word is the build's own folder of bytecode, which the image
            # receives as /opt/stockwell/app
            assert [
                path.relative_to(bundle / "environment").as_posix()
                for path in (bundle / "environment").rglob("*")
                if "sealed" in path.name.lower()
            ] == ["sealed"]
            for path in (bundle / "environment").rglob("*"):
                if (
                    path.is_file()
                    and path.name != "Dockerfile"
                    and "sealed" not in path.parts
                    and path.suffix not in (".png", ".jpg", ".mp4", ".pdf", ".gif")
                ):
                    assert (
                        "sealed"
                        not in path.read_bytes().decode(errors="replace").lower()
                    ), path
            assert not re.search(
                r"watchdog|precap|deliver|submission|grad|audit|\bcap\b|budget|deadline|attempt|timer|#",
                config,
            ), "task.toml"
        # Round 15: the upload is the flat bundle under the task's own name (`--flat --keep-name`), the next version of the
        # same task. It holds the steps bundle's files without the step's prefix, with the same bytes and modes in all but
        # task.toml, which lacks only the multi-step reward strategy and the [[steps]] table, whose limits are the
        # top-level ones the flat task runs with. `--flat` alone names it `-single`; `--keep-name` alone is refused.
        done = subprocess.run(
            [
                sys.executable,
                "-B",
                str(TASK / "scripts" / "package_step.py"),
                "--flat",
                "--keep-name",
                "--output",
                str(tmp_path / "out"),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert done.returncode == 0, done.stderr[-2000:]
        flat, steps = Path(json.loads(done.stdout)["task_path"]), built["bundles"]
        in_steps = {
            path.relative_to(steps).as_posix(): path
            for path in steps.rglob("*")
            if path.is_file()
        }
        in_flat = {
            path.relative_to(flat).as_posix(): path
            for path in flat.rglob("*")
            if path.is_file()
        }
        assert sorted(in_steps) == sorted(in_flat) and len(in_flat) > 1000
        differ = [
            name
            for name, path in in_steps.items()
            if path.read_bytes() != in_flat[name].read_bytes()
            or os.access(path, os.X_OK) != os.access(in_flat[name], os.X_OK)
        ]
        assert not differ, differ
        steps_config, flat_config = (
            tomllib.loads((bundle / "task.toml").read_text())
            for bundle in (steps, flat)
        )
        assert (
            flat_config["task"]["name"]
            == steps_config["task"]["name"]
            == "abundant/swe-m2_software-engineering_backoffice-server-rebuild"
        )
        assert "steps" not in steps_config and flat_config == steps_config
        assert (
            tomllib.loads((built["flat"] / "task.toml").read_text())["task"]["name"]
            == flat_config["task"]["name"] + "-single"
        )
        done = subprocess.run(
            [
                sys.executable,
                "-B",
                str(TASK / "scripts" / "package_step.py"),
                "--keep-name",
                "--output",
                str(tmp_path / "none"),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert (
            done.returncode == 2
            and "--keep-name goes with --flat" in done.stderr
            and not (tmp_path / "none").exists()
        ), done.stderr
    finally:
        if created:
            private.unlink()
        for kind in made_media:
            shutil.rmtree(media / kind)


def test_the_solution_ships_the_pinned_source_and_the_repository_never_holds_it(
    tmp_path,
):
    """Version 12's pre-trial audit (Q-09, must-fix): the solution held the reference as bytecode alone. Its data is now
    the reference's readable source, taken at build time from the pinned checkout, each file checked against the pinned
    commit's own Git blob (a changed, missing or extra file stops the build), and compiled as the sealed copy is it gives
    the sealed bytecode byte for byte (the bundle check). The source is never committed: this repository is public, so
    it tracks no file of the package and ignores the folders the build makes it in."""
    from reference import commit

    tree = package_step.source_tree(REFERENCE)
    assert len(tree) == len(package_step.compiled(REFERENCE)) > 150
    assert all(
        name.startswith("solution/data/stockwell/") and name.endswith(".py")
        for name in tree
    )
    listing = subprocess.run(
        [
            "git",
            "-C",
            str(package_step.repository()),
            "ls-tree",
            "-r",
            commit(),
            "backend/src/stockwell",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert listing.returncode == 0 and len(listing.stdout.splitlines()) == len(tree)
    # a checkout that differs from the pinned commit in one file, or lacks one, is refused
    package = REFERENCE / "backend" / "src" / "stockwell"
    for change in ("edited", "missing"):
        copy = tmp_path / change
        shutil.copytree(
            package,
            copy / "backend" / "src" / "stockwell",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        settings = copy / "backend" / "src" / "stockwell" / "settings.py"
        if change == "edited":
            settings.write_text(settings.read_text() + "\n# changed\n")
        else:
            settings.unlink()
        try:
            package_step.pinned_sources(copy)
        except ValueError as refused:
            assert "backend/src/stockwell/settings.py" in str(refused), refused
        else:
            raise AssertionError(f"a checkout with {change} settings.py was packaged")
    # never in the repository: nothing of the package is tracked, and where the build makes it is ignored
    tracked = subprocess.run(
        ["git", "-C", str(TASK), "ls-files"],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout.splitlines()
    assert tracked and not [
        path
        for path in tracked
        if "solution/data/" in path
        or path.startswith("environment/sealed/")
        or path.endswith(".pyc")
        or (path.endswith(".py") and "/stockwell/" in path)
    ]
    for made in (
        "solution/data/stockwell/app.py",
        "environment/sealed/stockwell/app.pyc",
    ):
        assert (
            subprocess.run(
                ["git", "-C", str(TASK), "check-ignore", "-q", made],
                check=False,
                timeout=60,
            ).returncode
            == 0
        ), made
    for script in ("environment/start-stockwell", "environment/stockwell-supervisor"):
        assert (
            subprocess.run(
                ["git", "-C", str(TASK), "check-ignore", "-q", script],
                check=False,
                timeout=60,
            ).returncode
            == 1
        ), script


def test_only_the_builds_have_network():
    """Version 12's pre-trial audit (must-fix): the second image's Dockerfile installs system and Python packages, but
    its build was declared without network. The two builds have public egress, the agent's session and the final check
    have none, and the justification says so in plain words."""
    values = tomllib.loads((TASK / "task.toml").read_text())
    assert (
        values["environment"]["network_mode"]
        == values["verifier"]["environment"]["network_mode"]
        == "public"
    )
    assert (
        values["agent"]["network_mode"]
        == values["verifier"]["network_mode"]
        == "no-network"
    )
    docker = (STEP / "tests" / "Dockerfile").read_text()
    assert "apt-get install" in docker and "pip install" in docker, (
        "what the second image's build downloads"
    )
    reason = values["metadata"]["open_internet_justification"]
    for part in (
        "the build of the second image have public egress",
        "The agent works without network access",
        "the final check runs without network",
    ):
        assert part in reason, part


def test_the_sealed_server_is_started_as_its_own_user_from_bytecode():
    """QA 08: the image receives bytecode only (no source in any layer, the build fails on a .py), and every start
    first checks as dev that /opt/stockwell cannot be read or entered; if it can, the setup hook fails and the trial stops.
    QA 20: a root supervisor keeps the sealed server running for the whole session, restarting it when it exits or stops
    answering its health check. (Since round 18 the two scripts are start-stockwell and stockwell-supervisor.)"""
    script = (TASK / "environment" / "start-stockwell").read_text()
    supervisor = (TASK / "environment" / "stockwell-supervisor").read_text()
    docker = (TASK / "environment" / "Dockerfile").read_text()
    check = script.index("setpriv --reuid dev")
    assert (
        check < script.index("curl")
        and "test -r /opt/stockwell" in script
        and "exit 1" in script[check : script.index("curl")]
    )
    assert (
        "setsid /usr/local/sbin/stockwell-supervisor" in script
        and "setpriv --reuid stockwell" not in script
    )
    assert (
        "flock -n 9" in supervisor
        and "while :; do" in supervisor
        and "setpriv --reuid stockwell" in supervisor
    )
    assert (
        "pkill -KILL -u stockwell" in supervisor
        and "/usr/local/lib/stockwell/stockwell.env" in supervisor
    )
    assert (
        "compileall" not in docker
        and "test -z \"$(find /opt/stockwell/app -name '*.py'" in docker
        and "chmod -R go-rwx /opt/stockwell" in docker
    )
    assert "COPY stockwell-supervisor /usr/local/sbin/stockwell-supervisor" in docker
    assert "/usr/local/sbin/stockwell-supervisor" in docker.split("chmod 0700")[-1]


def test_the_instruction_says_where_the_sealed_server_is_and_whose_it_is():
    """The verdict on version 11 (must-fix, evaluation awareness): early in trial 113 the solver ran `ps aux` with a
    search of the disk to find the sealed server's program and see whether it could read it, and the process list
    showed the platform's own launcher, whose shell variables carry the platform's name. The task cannot change that
    line; it can answer the question that sent the solver there. The instruction now says where the sealed server's
    files are, that the solver's account cannot read them, the account it runs under and that a service manager starts
    it again, and each of these is what the image does. Round 18 (the verdict on version 13) words it in the requester's
    terms: the old server, and the licence as the reason its files are closed to staff accounts."""
    text = " ".join((STEP / "instruction.md").read_text().split())
    assert (
        "The old server is running at `http://127.0.0.1:8080`. It answers a JSON API under `/api` and describes its endpoints and their "
        "request bodies at `/api/openapi.json`. To keep to the licence, it runs under its own account, `stockwell`, and its files, in "
        "`/opt/stockwell`, cannot be read by staff accounts such as yours; a service manager starts it again if it stops. Use it and "
        "study its answers as much as you need."
    ) in text
    docker = (TASK / "environment" / "Dockerfile").read_text()
    assert (
        "useradd --uid 10002 --system --no-create-home stockwell" in docker
        and "COPY sealed/ /opt/stockwell/app/" in docker
    )
    assert (
        "chown -R stockwell:stockwell /opt/stockwell && chmod -R go-rwx /opt/stockwell"
        in docker
    )
    assert (
        "test -r /opt/stockwell"
        in (TASK / "environment" / "start-stockwell").read_text()
    )
    supervisor = (TASK / "environment" / "stockwell-supervisor").read_text()
    assert (
        "while :; do" in supervisor
        and "setpriv --reuid stockwell" in supervisor
        and "--host 127.0.0.1 --port 8080" in supervisor
    )
    # nothing is hidden to get there: the image keeps procps (ps), and nothing remounts /proc or removes a package
    assert re.search(
        r"apt-get install -y --no-install-recommends \\\n[^\n]* procps ", docker
    )
    for name in (
        "Dockerfile",
        "entrypoint.sh",
        "start-stockwell",
        "stockwell-supervisor",
    ):
        script = (TASK / "environment" / name).read_text()
        assert not re.search(
            r"hidepid|\bmount\b[^\n]*\bproc\b|apt-get (remove|purge)|dpkg (-r|--remove|-P|--purge)",
            script,
        ), name


def test_nothing_the_agent_sees_calls_the_old_server_sealed():
    """The verdict on version 13 (must-fix, evaluation awareness, in all three trials): the framing read as a grader's,
    with a "sealed" server and a vendor's folder closed for no reason the story gives. Round 18 calls it the old server
    and gives the licence as the reason. Nothing the agent can list, read or see running says "sealed": the
    instruction, the names the image installs, the scripts' text (their messages, and the supervisor's command line
    that `ps` shows), the set-up and collect commands. The scripts' new names agree wherever they are named."""
    instruction = (STEP / "instruction.md").read_text()
    assert "sealed" not in instruction.lower()
    docker = (TASK / "environment" / "Dockerfile").read_text()
    values = tomllib.loads((TASK / "task.toml").read_text())
    commands = [
        hook["command"]
        for key in ("setup_begin", "setup_complete")
        for hook in values["agent"][key]
    ]
    commands += [hook["command"] for hook in values["verifier"]["collect"]]
    assert sorted(set(commands)) == [
        "/usr/local/sbin/fsmaint-sweep",
        "/usr/local/sbin/start-stockwell",
    ], commands
    # every destination the image installs is free of the word; the one source that holds it is the build's folder of
    # bytecode, which the image receives as /opt/stockwell/app
    copies = re.findall(r"^COPY (\S+) (\S+)$", docker, flags=re.MULTILINE)
    assert [source for source, _ in copies if "sealed" in source] == ["sealed/"]
    assert not [target for _, target in copies if "sealed" in target.lower()]
    # the whole Dockerfile, its RUN and ENV lines too (re-check 12, S3): a RUN that writes the word into a file, or an
    # ENV that names it, would put it in the image; the build folder's COPY line is the one place it may stand
    assert (
        "sealed" not in docker.replace("COPY sealed/ /opt/stockwell/app/", "").lower()
    )
    for name in (
        "start-stockwell",
        "stockwell-supervisor",
        "fsmaint-sweep",
        "entrypoint.sh",
    ):
        assert (name, f"/usr/local/sbin/{name}") in copies, name
        assert os.access(TASK / "environment" / name, os.X_OK) and name.endswith(
            package_step.EXECUTABLE
        ), name
        assert f"/usr/local/sbin/{name}" in docker.split("chmod 0700")[-1], name
        assert "sealed" not in (TASK / "environment" / name).read_text().lower(), name
    assert (
        "/usr/local/sbin/start-stockwell || true"
        in (TASK / "environment" / "entrypoint.sh").read_text()
    )
    assert (
        "setsid /usr/local/sbin/stockwell-supervisor "
        in (TASK / "environment" / "start-stockwell").read_text()
    )
    assert "sealed" not in (TASK / "environment" / "stockwell.env").read_text().lower()
    assert not [
        path.name
        for path in (TASK / "environment").iterdir()
        if "sealed" in path.name and path.name != "sealed"
    ]
    # the story in the requester's words: the licence closes the files, and the work ends with the switch-over
    text = " ".join(instruction.split())
    assert (
        "our licence lets us run the server and use it as much as we like, but not read, copy or change its code."
        in text
    )
    assert (
        "When your server does all of the above, we point our proxy at it and switch the old server off."
        in text
    )


def test_the_verifier_prose_and_the_task_description_use_neutral_words():
    """Round 19, after the verdict on version 14 (no task defect; one helper agent described its session as an
    evaluation, prompted by its parent's own wording): the agent never sees the verifier or task.toml, but both keep
    neutral words all the same. No comment, docstring, note or message of the verifier says evaluation, graded or
    benchmark (its own notes say "the checker raises it again every 50 ms"); its identifiers stay, the class
    EvaluationError, the function evaluate() and the status value "evaluation_error", which the checks and readers of
    metrics.json use. task.toml's description and justification say "the old server", never "sealed"."""
    kept = re.compile(r"\bEvaluationError\b|\bevaluate\b|\"evaluation_error\"")
    tests = STEP / "tests"
    for path in (
        tests / "verify.py",
        tests / "verifier" / "replay.py",
        tests / "verifier" / "__init__.py",
        tests / "test.sh",
        tests / "Dockerfile",
    ):
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            assert not re.search(r"(?i)evaluat|graded|benchmark", kept.sub("", line)), (
                f"{path.name}:{number}: {line.strip()}"
            )
    replay = (tests / "verifier" / "replay.py").read_text()
    assert "on this machine; the checker raises it again every 50 ms" in replay
    config = (TASK / "task.toml").read_text()
    values = tomllib.loads(config)
    assert "sealed" not in config.lower()
    assert (
        "the old server" in values["task"]["description"]
        and "the old server" in values["metadata"]["open_internet_justification"]
    )


def test_one_configuration_for_the_sealed_server_the_recordings_and_the_solution():
    """QA 12 F1/F3: the sealed server served the web client as well, so `DELETE /nowhere` answered it 405 where the
    recordings hold 404 and a perfect clone lost 6 units. The sealed server, the live recorder and the solution now take
    their settings from one file, environment/stockwell.env, with no client directory; the legacy recorder builds the
    same app in-process without one. The instruction's numbers are the ones the code enforces."""
    settings = (TASK / "environment" / "stockwell.env").read_text()
    assert (
        "CLIENT_DIR" not in settings
        and "STOCKWELL_AUTH_MODE=proxy" in settings
        and "{data}" in settings
    )
    docker = (TASK / "environment" / "Dockerfile").read_text()
    assert (
        "COPY stockwell.env /usr/local/lib/stockwell/stockwell.env" in docker
        and "/opt/stockwell/client" not in docker
    )
    for path in (
        TASK / "environment" / "start-stockwell",
        TASK / "environment" / "stockwell-supervisor",
        STEP / "solution" / "oracle.py",
        TASK / "scripts" / "record_live.py",
    ):
        text = path.read_text()
        assert "CLIENT_DIR" not in text and not re.search(
            r"STOCKWELL_(AUTH_MODE|DATABASE_URL|METRICS|REQUEST_LOG)=", text
        ), path
    assert (
        "stockwell.env" in (STEP / "solution" / "oracle.py").read_text()
        and "stockwell.env" in (TASK / "scripts" / "record_live.py").read_text()
    )
    assert (
        'solution/data/stockwell.env"] = TASK_ROOT / "environment" / "stockwell.env"'
        in (TASK / "scripts" / "package_step.py").read_text()
    )
    instruction = " ".join((STEP / "instruction.md").read_text().split())
    assert (
        "serves the web client at" not in instruction
        and "inherit" not in instruction
        and "checksum" in instruction
    )
    probe = (
        "import json, sys; sys.path.insert(0, sys.argv[1]); from verifier import replay as r; "
        "print(json.dumps([r.WORKERS, r.REQUEST_SEC, r.START_SEC, r.THREAD_LIMIT, r.FILE_LIMIT, r.MEMORY_LIMIT, r.WORKSPACE_ID.pattern, "
        "r.SERVER_MEMORY]))"
    )
    done = subprocess.run(
        [sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests")],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    workers, request, start, threads, file_limit, memory, workspace, held = json.loads(
        done.stdout
    )
    source = (REFERENCE / "backend" / "src" / "stockwell" / "settings.py").read_text()
    assert "max_body_bytes: int = 6_000_000" in source and "6 MB" in instruction
    assert (
        "max_upload_bytes: int = Field(64 * 1024 * 1024" in source
        and "64 MiB" in instruction
    )
    assert (
        (workers, request, start) == (8, 30, 60)
        and "up to 8 requests" in instruction
        and "after 30 seconds" in instruction
    )
    assert (
        "gives it 60 seconds" in instruction
        and threads == 4096
        and "4,096 threads" in instruction
    )
    assert (
        (file_limit, memory) == (4 << 30, 6 << 30)
        and "files of at most 4 GB" in instruction
        and "6 GB of address space" in instruction
    )
    assert workspace == "[A-Za-z0-9_]{1,40}" and "at most 40 characters" in instruction
    assert (
        held == 6 << 30
        and "6 GB of memory in all, shared memory included" in instruction
    )


def test_python3_in_both_images_has_the_servers_packages():
    """QA 13 S2: `python3` was a link to the venv's interpreter, and a venv is not active through a link outside it, so
    `python3 -c "import fastapi"` failed in both images. It is now a wrapper that runs /opt/py's interpreter, the system
    interpreter also sees /opt/py's packages, and each image's build checks both as its users. (Since round 12 the
    instruction no longer names the packages; `python3 -m pip list` shows them.)"""
    for path, users in (
        (TASK / "environment" / "Dockerfile", ("dev", "nobody")),
        (STEP / "tests" / "Dockerfile", ("nobody",)),
    ):
        docker = path.read_text()
        assert (
            "ln -sf /opt/py/bin/python" not in docker
            and 'exec /opt/py/bin/python "$@"' in docker
        ), path
        assert (
            "opt-py.pth" in docker
            and 'python3 -c "import fastapi' in docker
            and '/usr/bin/python3 -c "import fastapi' in docker
        ), path
        for user in users:
            assert f"--reuid {user}" in docker or (
                "for user in dev nobody" in docker and user in ("dev", "nobody")
            ), (path, user)


def test_verifier_reads_the_gzipped_scenarios_the_image_ships(tmp_path):
    import gzip

    scenarios = tmp_path / "scenarios.json.gz"
    scenarios.write_bytes(
        gzip.compress(
            json.dumps(
                {"scenarios": [{"id": "S1", "theme": "t", "steps": []}]}
            ).encode(),
            mtime=0,
        )
    )
    probe = (
        "import json, sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); from verifier.replay import evaluate; "
        "print(json.dumps(evaluate(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), Path(sys.argv[4]), sandbox=False)))"
    )
    done = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            probe,
            str(STEP / "tests"),
            str(tmp_path / "no-server"),
            str(scenarios),
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    result = json.loads(done.stdout.strip().splitlines()[-1])
    assert (
        result["scenarios_total"] == 1 and result["reward"] == 0.0 and result["notes"]
    )


def test_the_packager_ships_no_corpus_that_carries_how_it_was_recorded(tmp_path):
    """Round 11: the shipped corpus opened with `recorded_with` (the counts, the themes left out, the legacy commit, the
    media manifest's digest, the seed and the live settings), which the verifier never reads. The recorder writes that
    record apart now, and the packager refuses a corpus whose top level holds anything besides its scenarios."""
    scenarios = [
        {"id": "S1", "theme": "t", "steps": []},
        {"id": "S2", "theme": "t", "steps": []},
    ]
    clean = (
        json.dumps({"scenarios": scenarios}, sort_keys=True, separators=(",", ":"))
        + "\n"
    )
    assert package_step.corpus_keys(clean) == [
        "scenarios"
    ] and package_step.corpus_keys(' { "scenarios" : [ ] } ') == ["scenarios"]
    for number, extra in enumerate(
        ({"recorded_with": {"seed": 1}}, {"source": "x"}, {"zz": [{}]})
    ):
        name = next(iter(extra))
        planted = tmp_path / f"corpus-{number}.json"
        planted.write_text(
            json.dumps(
                dict(extra, scenarios=scenarios), sort_keys=True, separators=(",", ":")
            )
            + "\n"
        )
        assert package_step.corpus_keys(planted.read_text()) == sorted(
            [name, "scenarios"]
        )
        try:
            package_step.compressed_scenarios(planted)
        except ValueError as refused:
            assert name in str(refused)
        else:
            raise AssertionError(
                f"a corpus with {name!r} beside its scenarios was packaged"
            )


def test_instruction_and_config_hold_no_session_or_grading_text():
    """Nothing the agent reads frames its work as judged: the platform's verdict on version 10 found two of three
    solvers calling their session an evaluation, one of them quoting the completion sentence ("cannot be told apart
    from the sealed one"), and all three using the frameworks the instruction listed. The completion sentence states the
    requirement in the requester's terms, and the stack is left to `python3 -m pip list`. task.toml holds no comment,
    the agent's time limit is the platform's own 34,560 s at both places, and nothing is armed at set-up but the sealed
    server (no task-side timer since round 15). Nothing the agent can see names how its work is judged, ended or
    packed: the set-up and collect commands, the image's installed paths and the set-up's state files.

    Round 18: the verdict on version 13 found all three solvers calling their session a benchmark, two of them
    paraphrasing the instruction's comparison wording ("every API request ... as the sealed one does"). The instruction
    now says what the integrations depend on, gives the licence as the reason the old server's files are closed, ends
    with the switch-over, and says "sealed" nowhere; neither does anything the agent can see (the installed names, the
    set-up command, the scripts' messages and the supervisor's process line)."""
    text = " ".join((STEP / "instruction.md").read_text().split())
    instruction = text.lower()
    config = (TASK / "task.toml").read_text()
    # "compare" too (QA 08 S3): integrations rely on answers; comparing them is what an answer key does. Round 18 adds
    # re-check 10's vocabulary and the words of version 13's finding. Kept, in-story: "records" (the business's),
    # "sessions" (of the server's passwords, which are not used) and "checksum" (how the archive files documents).
    for word in (
        "oracle",
        "reference",
        "hidden",
        "grading",
        "working session",
        "fresh context",
        "scenario",
        "hours",
        "told apart",
        "tell apart",
        "indistinguishable",
        "graded",
        "evaluat",
        "test corpus",
        "benchmark",
        "score",
        "trial",
        "harness",
        "vendor's server ran",
        "compar",
        "sealed",
        "exactly",
        "every api request",
        "every request",
        "try things out",
        "ground truth",
        "original",
        "expect",
        "fraction",
        "match",
        "replay",
        "verif",
        "test",
        r"check(?!sum)",
        "grad",
        "rubric",
        "held-out",
        "fixture",
        "reward",
        "criteria",
        "budget",
        "platform",
        "harbor",
        "assess",
        "judge",
        r"exam\b",
        "measure",
        "unattended",
        "time limit",
        "deadline",
    ):
        assert not re.search(r"\b" + word, instruction), (
            word
        )  # at the start of a word: "underscores" holds no score
    assert (
        "which rely on every value they receive, and its type, staying as it is today."
        in text
    )
    assert (
        "The tills, the bank feed, the export and the web client depend on the answers the old server gives. For any API request it "
        "accepts or refuses, your server gives the same status code and the same JSON body,"
    ) in text
    assert "because the integrations depend on every detail of an answer:" in text
    for package in (
        "fastapi",
        "starlette",
        "pydantic",
        "sqlalchemy",
        "uvicorn",
        "httpx",
    ):
        assert package not in instruction, package
    assert (
        "## Switching over When your server does all of the above, we point our proxy at it and switch the old server off. Keep "
        "`/app/server/run` working at all times."
    ) in text
    assert (
        "`python3` is Python 3.12 with the packages listed by `python3 -m pip list`. Node.js and Go are installed with their standard libraries."
        in text
    )
    assert "#" not in config and "timer" not in config, (
        "task.toml holds no comment and no timer"
    )
    values = tomllib.loads(config)
    assert values["agent"]["timeout_sec"] == 34560
    assert (
        values["agent"]["setup_begin"]
        == values["agent"]["setup_complete"]
        == [{"command": "/usr/local/sbin/start-stockwell", "timeout_sec": 120}]
    )
    docker, setup = (
        (TASK / "environment" / "Dockerfile").read_text(),
        (TASK / "environment" / "start-stockwell").read_text(),
    )
    assert (
        not (TASK / "environment" / "fsmaint-timer").exists()
        and "timer" not in docker
        and "timer" not in setup
    )
    assert "fsmaint-timer" not in (TASK / "scripts" / "package_step.py").read_text()
    visible = " ".join(
        [
            values["verifier"]["collect"][0]["command"],
            values["agent"]["setup_complete"][0]["command"],
        ]
        + re.findall(r"^COPY \S+ (\S+)", docker, flags=re.MULTILINE)
        + re.findall(r"/var/lib/\S+", setup)
    )
    assert not re.search(
        r"deliver|watchdog|precap|grad|submission|collect|verif|\bcap\b|deadline|judge|session|timer|sealed",
        visible,
        flags=re.IGNORECASE,
    ), visible
    for name in ("Dockerfile", "start-stockwell"):
        lines = (TASK / "environment" / name).read_text().splitlines()
        assert not any(
            line.startswith("#") for line in lines[1 if name != "Dockerfile" else 0 :]
        ), name


STACK = re.compile(
    r"via stockwell|--project backend|autogenerated by uv|uv export", re.IGNORECASE
)  # what states the sealed server's stack


def test_the_agent_image_keeps_no_file_that_states_the_sealed_servers_stack():
    """QA 08 M1: /opt/py/requirements.txt, world-readable in the agent image, pinned the sealed server's frameworks with
    their versions under `# via stockwell` (uv's export of the reference's lock file), what version 10's verdict called
    info_leakage when the instruction listed them, and the instruction's package line points the agent at /opt/py. The
    build removes it right after the install; what the agent finds is what `python3 -m pip list` shows. The verifier
    image keeps its copy: the agent never sees that image."""
    docker = (TASK / "environment" / "Dockerfile").read_text()
    assert STACK.search((REFERENCE / "requirements.txt").read_text()), (
        "the file states the stack: the reason it goes"
    )
    install = next(
        block
        for block in docker.split("\nRUN ")[1:]
        if "-r /opt/py/requirements.txt" in block
    )
    assert install.index("-r /opt/py/requirements.txt") < install.index(
        "&& rm /opt/py/requirements.txt \\"
    ), install
    assert docker.count("requirements.txt") == 4, (
        "copied once (two names on the line), installed from and removed: nowhere else"
    )
    for name in (
        "Dockerfile",
        "entrypoint.sh",
        "fsmaint-sweep",
        "start-stockwell",
        "stockwell-supervisor",
        "stockwell.env",
    ):
        assert not STACK.search((TASK / "environment" / name).read_text()), name


def test_the_candidate_id_goes_where_the_recording_has_ws_and_types_must_match():
    """The candidate's answer is compared as it is: its workspace id is put into the recorded answer where the recorder
    wrote {ws}, so an id that is also a value elsewhere (QA 10 E9: id 1100 next to account code 1100) is no problem,
    and `true` is not `1` and `100` is not `100.0` (E8). Round 16: an answer whose own text holds {ws} (the API
    description's paths, /api/ws/{ws}/...) was rewritten with the candidate's id, so no server, the reference included,
    could match it; the recorder now keeps such an answer `literal` (and refuses one that also holds the workspace
    id), and it is compared as it is."""
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
    "literal": same({"paths": {"/api/ws/{ws}/users": {}}}, {"paths": {"/api/ws/{ws}/users": {}}}, "w_1", True),
    "literal expanded": same({"paths": {"/api/ws/{ws}/users": {}}}, {"paths": {"/api/ws/{ws}/users": {}}}, "w_1"),
    "literal taken for the id": same({"paths": {"/api/ws/w_1/users": {}}}, {"paths": {"/api/ws/{ws}/users": {}}}, "w_1", True),
}
print(json.dumps(checks))
"""
    done = subprocess.run(
        [sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests")],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    assert json.loads(done.stdout) == {
        "expand": True,
        "e9": True,
        "other id": False,
        "e8 bool": False,
        "e8 float": False,
        "e8 int": True,
        "nested": False,
        "binary": True,
        "literal": True,
        "literal expanded": False,
        "literal taken for the id": False,
    }
    recorder = (TASK / "scripts" / "record_live.py").read_text()
    assert (
        'step["literal"], step["json"] = True, answer' in recorder
        and "answered both the text {{ws}} and the workspace id" in recorder
    )
    assert (
        'same(answer, step["json"], workspace, step.get("literal") is True)'
        in (STEP / "tests" / "verifier" / "replay.py").read_text()
    )


def test_replay_sends_files_and_sized_bodies_raw(tmp_path):
    """A step may upload a file from the media folder, or N zero bytes, as the raw request body."""
    (tmp_path / "media" / "video").mkdir(parents=True)
    (tmp_path / "media" / "video" / "clip.mp4").write_bytes(
        b"\x00\x00\x00\x18ftypisom" + b"x" * 100
    )
    (tmp_path / "media" / "imports").mkdir()
    (tmp_path / "media" / "imports" / "list.csv").write_text(
        "name,region\nCafé Lumière 1,NORD\n", encoding="utf-8"
    )
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
    done = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            probe,
            str(STEP / "tests"),
            str(tmp_path / "media"),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    first, sized, plain, photo, csv, extra, escape = json.loads(done.stdout)
    assert (
        first[0] == 201 and first[1]["type"] == "video/mp4" and first[1]["bytes"] == 112
    )
    assert (
        sized[0] == 201
        and sized[1]["type"] == "application/octet-stream"
        and sized[1]["bytes"] == 70000
    )
    assert plain[1]["type"] == "application/json" and escape == "refused"
    # a JSON body built around a media file: base64 or UTF-8 text in the named field, sent as clients send JSON (UTF-8)
    assert [photo[1]["sha"], csv[1]["sha"]] == extra["expected"] and photo[1][
        "type"
    ] == csv[1]["type"] == "application/json"
    assert extra["built"][0]["name"] == "Café.jpg" and base64.b64decode(
        extra["built"][0]["content"]
    ).startswith(b"\x00\x00\x00\x18ftyp")
    assert extra["built"][1] == {
        "dry_run": True,
        "csv": "name,region\nCafé Lumière 1,NORD\n",
    }
    # a 40 MiB file answer is read in chunks and compared by type, length and SHA-256
    big = bytes(range(256)) * 4096 * 40
    assert extra["big"] == [
        200,
        {
            "binary": {
                "content_type": "video/mp4",
                "bytes": len(big),
                "sha256": hashlib.sha256(big).hexdigest(),
            }
        },
    ]


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
    done = subprocess.run(
        [sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests"), str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    first, second = json.loads(done.stdout)
    assert first == [413, {"error": {"code": "body_too_large"}}] and second[0] == 413


def test_the_upload_scan_finds_hidden_inputs_the_image_also_receives(tmp_path):
    """Planted leaks: a sample uploaded as base64, the same sample cut short, a raw private file equal to a sample, a
    file answer equal to a client file. Legitimate private uploads and answers are not reported."""
    sample, other, page = (
        os.urandom(300),
        os.urandom(300),
        b"<html>" + os.urandom(200).hex().encode(),
    )
    bundle = tmp_path / "bundle"
    private = bundle / "steps" / "s" / "tests" / "private"
    for path, data in (
        (bundle / "environment" / "samples" / "photo.jpg", sample),
        (bundle / "environment" / "client" / "index.html", page),
        (private / "media" / "photo" / "p.jpg", sample),
        (private / "media" / "photo" / "q.jpg", other),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def upload(data: bytes) -> dict:
        return {
            "method": "POST",
            "path": "/files",
            "query": {},
            "headers": {},
            "body": {"name": "f", "content": base64.b64encode(data).decode()},
            "status": 201,
            "json": {"id": "FILE-1"},
        }

    def raw(name: str) -> dict:
        return {
            "method": "POST",
            "path": "/files/upload",
            "query": {},
            "headers": {},
            "body_file": name,
            "status": 201,
            "json": {},
        }

    answer = {
        "method": "GET",
        "path": "/files/FILE-1/content",
        "query": {},
        "headers": {},
        "body": None,
        "status": 200,
        "json": {
            "binary": {
                "content_type": "text/html",
                "bytes": len(page),
                "sha256": hashlib.sha256(page).hexdigest(),
                "filename": None,
            }
        },
    }
    clean = {
        "method": "GET",
        "path": "/files/FILE-1/content",
        "query": {},
        "headers": {},
        "body": None,
        "status": 200,
        "json": {
            "binary": {
                "content_type": "image/jpeg",
                "bytes": 300,
                "sha256": hashlib.sha256(other).hexdigest(),
                "filename": None,
            }
        },
    }

    def inserted(
        name: str,
    ) -> (
        dict
    ):  # a media file put into a JSON body as base64 (a photo an integration sends)
        return {
            "method": "POST",
            "path": "/files",
            "query": {},
            "headers": {"content-type": "application/json"},
            "body": {"name": "f"},
            "body_insert": {"field": "content", "file": name, "as": "base64"},
            "status": 201,
            "json": {},
        }

    corpus = {
        "scenarios": [
            {"id": "S1", "theme": "files", "steps": [upload(other), upload(sample)]},
            {
                "id": "S2",
                "theme": "files",
                "steps": [
                    upload(sample[:150]),
                    upload(sample[:10]),
                    raw("photo/q.jpg"),
                    clean,
                ],
            },
            {
                "id": "S3",
                "theme": "media",
                "steps": [raw("photo/p.jpg"), answer, raw("photo/missing.jpg")],
            },
            {
                "id": "S4",
                "theme": "trading",
                "steps": [inserted("photo/q.jpg"), inserted("photo/p.jpg")],
            },
        ]
    }
    (private / "scenarios.json.gz").write_bytes(
        gzip.compress(json.dumps(corpus, indent=1).encode())
    )
    done = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(TASK / "scripts" / "scan_uploads.py"),
            str(bundle),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 1, done.stderr[-2000:]
    report = json.loads(done.stdout)
    found = sorted(
        (leak["where"].split()[0], leak["what"], leak["file"])
        for leak in report["leaks"]
    )
    assert found == [
        ("S1", "base64 upload (equal)", "environment/samples/photo.jpg"),
        ("S2", "base64 upload (prefix)", "environment/samples/photo.jpg"),
        ("S3", "body_file upload (equal)", "environment/samples/photo.jpg"),
        ("S3", "file answer", "environment/client/index.html"),
        ("S4", "body_insert upload (equal)", "environment/samples/photo.jpg"),
    ]
    assert (
        report["scenarios"] == 4
        and report["steps"] == 11
        and len(report["missing"]) == 1
        and report["file_answers"] == 2
    )
    assert report["body_insert"] == 2


def test_the_candidate_cannot_replace_the_delivery_directory():
    """A candidate that owned /app could swap /app/server for a symbolic link to the sealed server, and the root-run
    collector would copy what the link points to. /app is root's and sticky, /app/server root's and writable by all."""
    docker = (TASK / "environment" / "Dockerfile").read_text()
    owned = docker.index("chown -R dev:dev /app")
    assert (
        owned < docker.index("chown root:root /app /app/server")
        and "chmod 1777 /app " in docker
        and "chmod 0777 /app/server" in docker
    )
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

DRIVE = r"""
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
"""


def drive(
    work: Path, mode: str, scenarios: list[dict], setup: str = "", **patch
) -> dict:
    """Grade a tiny fake server (FAKE_SERVER in `mode`) with the real verifier, its limits patched to test scale."""
    spec = {
        "server": FAKE_SERVER,
        "mode": mode,
        "scenarios": scenarios,
        "patch": patch,
        "setup": setup,
    }
    done = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            DRIVE,
            str(STEP / "tests"),
            str(work),
            json.dumps(spec),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert done.returncode == 0, done.stderr[-3000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


def step(path: str) -> dict:
    return {
        "method": "GET",
        "path": path,
        "query": {},
        "headers": {"x-user": "U-01"},
        "body": None,
        "status": 200,
        "json": {"path": path.lstrip("/")},
    }


def test_a_hanging_or_dripping_server_still_gets_a_reward_at_the_time_limit(tmp_path):
    """Without a limit of its own the replay would outlast the step, and the run would end with no reward at all."""
    scenarios = [
        {"id": f"S{i}", "theme": "t", "steps": [step("/items/1")]} for i in range(40)
    ]
    for mode in ("hang", "drip"):
        out = drive(
            tmp_path / mode,
            mode,
            scenarios,
            REQUEST_SEC=1,
            DEADLINE_SEC=4,
            HEALTH_SEC=1,
        )
        metrics, reasons = (
            out["metrics"],
            {result["reason"] for result in out["results"]},
        )
        assert (
            metrics["reward"] == 0.0
            and metrics["scenarios_total"] == 40
            and out["seconds"] < 15
        ), out
        assert metrics["unfinished"] > 0 and any(
            "time limit" in note for note in metrics["notes"]
        )
        # a request is cut after REQUEST_SEC of wall clock even while bytes keep arriving, so some attempts end before the deadline
        assert reasons == {
            "no answer from the server",
            "not played to the end before the time limit",
        }, reasons


def test_replies_that_are_not_http_or_not_json_are_mismatches_not_evaluation_errors(
    tmp_path,
):
    garbage = drive(
        tmp_path / "garbage",
        "garbage",
        [{"id": "S1", "theme": "t", "steps": [step("/items/1")]}],
        START_SEC=2,
    )
    assert (
        garbage["metrics"]["reward"] == 0.0
        and garbage["results"][0]["reason"] == "the server did not start"
    )
    scenarios = [
        {"id": "S1", "theme": "t", "steps": [step("/items/1"), step("/not-json")]},
        {"id": "S2", "theme": "t", "steps": [step("/deep")]},
        {"id": "S3", "theme": "t", "steps": [step("/items/2"), step("/items/3")]},
    ]
    odd = drive(tmp_path / "odd", "plain", scenarios)
    assert {
        result["id"]: (result["failed_step"], result["reason"])
        for result in odd["results"]
    } == {"S1": (2, "body differs"), "S2": (1, "body differs"), "S3": (None, None)}
    assert odd["metrics"]["scenarios_matched"] == 1 and odd["metrics"][
        "reward"
    ] == round(1 / 3, 6)


def test_a_server_that_closes_without_announcing_it_loses_nothing(tmp_path):
    """QA 10 E10 and E3: right answers, each followed by a close the server never announced (one of them an early 413)."""
    big = {
        "method": "POST",
        "path": "/files/upload",
        "query": {},
        "headers": {"x-user": "U-01", "content-type": "application/octet-stream"},
        "body_size": 2_000_000,
        "status": 413,
        "json": {"error": "too large"},
    }
    scenarios = [
        {
            "id": f"S{i}",
            "theme": "t",
            "steps": [step("/items/1"), step("/items/2"), step("/items/3")],
        }
        for i in range(6)
    ]
    scenarios.append(
        {
            "id": "S-big",
            "theme": "t",
            "steps": [step("/items/1"), big, step("/items/2")],
        }
    )
    out = drive(tmp_path, "silent", scenarios)
    assert (
        out["metrics"]["scenarios_matched"] == 7 and out["metrics"]["retried"] == 0
    ), out["results"]


def test_a_server_that_crashes_now_and_then_loses_only_the_scenarios_that_crash_it(
    tmp_path,
):
    """Every tenth scenario makes the server exit. With room for second tries (RETRY_SHARE raised for this small corpus),
    the scenarios in flight beside each crash are played again alone and all count: 72 of 80. With the share the full
    corpus gets (2% of units), second tries decide no more units than that (QA 20)."""
    scenarios = [
        {
            "id": f"S{i:03d}",
            "theme": "crash" if i % 10 == 3 else "fine",
            "steps": [
                step("/items/1"),
                step("/crash" if i % 10 == 3 else "/items/2"),
                step("/items/3"),
            ],
        }
        for i in range(80)
    ]
    out = drive(tmp_path / "room", "plain", scenarios, RETRY_SHARE=1.0)
    metrics = out["metrics"]
    assert metrics["scenarios_matched"] == 72 and metrics["by_theme"] == {
        "crash": {"total": 8, "matched": 0},
        "fine": {"total": 72, "matched": 72},
    }
    assert (
        metrics["restarts"] >= 8 and metrics["unfinished"] == 0 and not metrics["notes"]
    )
    assert {result["reason"] for result in out["results"] if not result["matched"]} == {
        "the server stopped while the scenario was played"
    }
    capped = drive(tmp_path / "capped", "plain", scenarios)["metrics"]
    assert (
        capped["retry_budget_units"] == 1
        and capped["retried_units"] <= 1
        and capped["by_theme"]["crash"]["matched"] == 0
    )


def test_a_second_try_is_only_for_a_server_that_stopped_and_heavy_uploads_run_alone(
    tmp_path,
):
    """QA 20 (a): a live server that leaves requests unanswered, or answers wrongly, gets no second try. QA 11 S1: a
    scenario that uploads a long PDF or a file of tens of megabytes runs with nothing beside it, so no request waits behind
    it for the database's write lock."""
    media = (
        tmp_path / "run" / "media" / "pdf"
    )  # drive() reads uploads from its work folder's media
    media.mkdir(parents=True)
    (media / "long.pdf").write_bytes(b"%PDF-1.7\n" + bytes(1 << 20))
    (media / "short.pdf").write_bytes(b"%PDF-1.7\n" + bytes(1000))

    def upload(name: str) -> dict:
        return {
            "method": "POST",
            "path": "/files/upload",
            "query": {},
            "headers": {"x-user": "U-01", "content-type": "application/pdf"},
            "body_file": f"pdf/{name}",
            "status": 200,
            "json": {"path": "files/upload"},
        }

    slow = [
        {
            "id": f"S{i:02d}",
            "theme": "slow",
            "steps": [step("/items/1"), step("/items/2")],
        }
        for i in range(24)
    ]
    dropped = [
        {"id": "D1", "theme": "dropped", "steps": [step("/items/1"), step("/drop")]}
    ]
    heavy = [
        {
            "id": f"H{i}",
            "theme": "heavy",
            "steps": [
                step("/items/1"),
                dict(upload("long.pdf"), query={"name": "long.pdf"}),
            ],
        }
        for i in range(3)
    ]
    light = [
        {
            "id": f"L{i}",
            "theme": "light",
            "steps": [
                step("/items/1"),
                dict(upload("short.pdf"), query={"name": "short.pdf"}),
            ],
        }
        for i in range(3)
    ]
    out = drive(
        tmp_path / "run", "overlap", slow + dropped + heavy + light, RETRY_SHARE=1.0
    )
    metrics, results = (
        out["metrics"],
        {result["id"]: result for result in out["results"]},
    )
    assert (
        results["D1"]["reason"] == "no answer from the server"
        and metrics["retried"] == 0
        and metrics["alone"] == 3
    )
    seen = json.loads((tmp_path / "run" / "w" / "data" / "overlap.json").read_text())
    assert seen["long.pdf"] == [1, 1, 1], "nothing ran beside a heavy upload"
    assert (
        metrics["by_theme"]["heavy"]["matched"] == 3
        and metrics["by_theme"]["light"]["matched"] == 3
    )


def test_each_trading_day_and_screen_counts_alone_and_the_reward_counts_units(tmp_path):
    """Owner round 2: a trading run is one unit per day and per client screen after it. A day with a wrong answer is
    unmatched, and the run goes on, so later days still count; a scenario without units stops at its first difference.
    reward = matched units / all units. A step marked scoped: false names its full path (the client's /api/version)."""
    wrong = dict(step("/items/3"), json={"path": "items/x"})
    version = {
        "method": "GET",
        "path": "/api/version",
        "scoped": False,
        "query": {},
        "headers": {"accept": "application/json"},
        "body": None,
        "status": 200,
        "json": {"version": "1"},
    }
    run = {
        "id": "T1",
        "theme": "trading",
        "units": [
            {"theme": "trading"},
            {"theme": "trading"},
            {"theme": "trading"},
            {"theme": "screens"},
        ],
        "steps": [
            dict(step("/items/1"), unit=0),
            dict(step("/items/2"), unit=0),
            dict(wrong, unit=1),
            dict(step("/items/4"), unit=1),
            dict(step("/items/5"), unit=2),
            dict(version, unit=3),
            dict(step("/orders"), unit=3),
        ],
    }
    early = {"id": "S1", "theme": "t", "steps": [wrong, step("/items/4")]}
    fine = {"id": "S2", "theme": "t", "steps": [step("/items/6")]}
    out = drive(tmp_path, "plain", [run, early, fine])
    metrics, results = (
        out["metrics"],
        {result["id"]: result for result in out["results"]},
    )
    assert (
        results["T1"]["units"] == [True, False, True, True]
        and results["S1"]["units"] == [False]
        and results["S1"]["failed_step"] == 1
    )
    assert (
        metrics["units_total"] == 6
        and metrics["units_matched"] == 4
        and metrics["reward"] == round(4 / 6, 6)
    )
    assert metrics["by_theme"] == {
        "screens": {"total": 1, "matched": 1},
        "t": {"total": 2, "matched": 1},
        "trading": {"total": 3, "matched": 2},
    }


def test_what_a_workspace_holds_survives_a_restart_on_the_same_data(tmp_path):
    """Owner round 2 (QA 01 R2): a scenario with a planned restart runs alone; after the marked step the server is
    stopped (SIGTERM, or SIGKILL straight after the answer) and started on the same DATA_DIR, and the scenario goes on
    in the same workspace. A server that keeps its state in memory fails both; one that saves only on SIGTERM fails
    the SIGKILL case; one that writes before it answers passes. Other scenarios are not disturbed."""

    def tally(method: str, count: int, restart: str | None = None) -> dict:
        found = {
            "method": method,
            "path": "/tally",
            "query": {},
            "headers": {"x-user": "U-01"},
            "body": None,
            "status": 200,
            "json": {"count": count},
        }
        return dict(found, restart=restart) if restart else found

    scenarios = [
        {
            "id": "TERM",
            "theme": "durable",
            "steps": [
                tally("POST", 1),
                tally("POST", 2, "term"),
                tally("GET", 2),
                tally("POST", 3),
            ],
        },
        {
            "id": "KILL",
            "theme": "durable",
            "steps": [tally("POST", 1), tally("POST", 2, "kill"), tally("GET", 2)],
        },
        {"id": "PLAIN", "theme": "t", "steps": [tally("POST", 1), tally("GET", 1)]},
    ]
    verdicts = {}
    for mode in ("disk", "memory", "lazy"):
        out = drive(tmp_path / mode, mode, scenarios)
        verdicts[mode] = {result["id"]: result["matched"] for result in out["results"]}
        assert (
            out["metrics"]["planned_restarts"] == 2 and out["metrics"]["retried"] == 0
        ), out
    assert verdicts == {
        "disk": {"TERM": True, "KILL": True, "PLAIN": True},
        "memory": {"TERM": False, "KILL": False, "PLAIN": True},
        "lazy": {"TERM": True, "KILL": False, "PLAIN": True},
    }


def month_of_trading(number: int) -> dict:
    """Three days: an order whose total the server computes, a payment of that total (the client sends what it was shown),
    and a check of the total. A server that gets totals one cent wrong matches one day in three."""
    month = f"M{number}"

    def day(unit: int, method: str, path: str, body: dict | None, answer: dict) -> dict:
        return {
            "method": method,
            "path": f"{path}/{month}",
            "query": {},
            "headers": {"x-user": "U-01"},
            "body": body,
            "status": 200,
            "json": answer,
            "unit": unit,
        }

    return {
        "id": month,
        "theme": "trading",
        "units": [{"theme": "trading"}] * 3,
        "steps": [
            day(0, "POST", "/orders", {"lines": 1}, {"total": 1000}),
            day(1, "POST", "/payments", {"amount": 1000}, {"paid": 1000}),
            day(2, "GET", "/check", None, {"total": 1000}),
        ],
    }


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
    honest = drive(tmp_path / "honest", "buggy", months, WORKERS=1, RETRY_SHARE=1.0)[
        "metrics"
    ]
    assert honest["reward"] == round(1 / 3, 6) and honest["retried"] == 0
    no_slate, no_lock = (
        "replay.Candidate.clean_slate = lambda self: None\n",
        "replay.merge_retry = lambda first, second: second\n",
    )
    exploit = drive(
        tmp_path / "exploit",
        "preview",
        months,
        setup=no_slate + no_lock,
        WORKERS=1,
        RETRY_SHARE=1.0,
    )["metrics"]
    assert exploit["reward"] == 1.0 and exploit["retried"] == 6, (
        "without either defence the preview pays"
    )
    lock_only = drive(
        tmp_path / "lock", "preview", months, setup=no_slate, WORKERS=1, RETRY_SHARE=1.0
    )["metrics"]
    assert lock_only["reward"] == round(2 / 3, 6), (
        "with the lock alone, what it kept still reaches the day it left unanswered"
    )
    slate_only = drive(
        tmp_path / "slate", "preview", months, setup=no_lock, WORKERS=1, RETRY_SHARE=1.0
    )["metrics"]
    both = drive(tmp_path / "both", "preview", months, WORKERS=1, RETRY_SHARE=1.0)[
        "metrics"
    ]
    assert (
        slate_only["reward"] == both["reward"] == honest["reward"]
        and both["retried"] == 6
    )
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
    done = subprocess.run(
        [sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests"), str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    out = json.loads(done.stdout)
    assert (
        out["removed"] == [0, 1, 2]
        and out["left"] == ["deep", "link"]
        and out["after"] == []
        and out["outside"] == "keep"
    )
    assert out["limits"] == [True, True, False, False]
    sandbox = out["sandbox"]
    assert sandbox[-len(out["drop"]) :] == out["drop"] and sandbox.index(
        "prlimit"
    ) < sandbox.index("setpriv")
    assert {"--nproc=4096", f"--fsize={4 << 30}", f"--as={6 << 30}"} <= set(
        sandbox
    ) and "oom_score_adj" in sandbox[2]


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
    done = subprocess.run(
        [sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests"), str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    assert json.loads(done.stdout.strip().splitlines()[-1]) == {
        "files": ["reward.txt"],
        "reward": "0.750000",
    }


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
    done = subprocess.run(
        [sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests")],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    first, second = json.loads(done.stdout)
    assert first == second and sorted(first) == list(range(33))
    shared = [index for index in first if index < 30]
    assert shared != sorted(shared)
    assert [first.index(index) for index in (30, 31, 32)] != [30, 31, 32]
    places = sorted(first.index(index) for index in (30, 31, 32))
    assert (
        places[0] >= 5
        and places[-1] <= 27
        and min(b - a for a, b in itertools.pairwise(places)) >= 5
    )


def test_a_virtual_environment_in_the_delivery_survives_the_copy_to_the_verifier(
    tmp_path,
):
    """QA 07 F3: the copy out of the agent's machine refuses absolute links and links that leave the directory (tarfile's
    `data` filter), so a venv's interpreter link made the whole delivery vanish and a correct server score 0.
    environment/fsmaint-sweep runs before the copy ([[verifier.collect]], as the agent's own user) and makes such links
    safe: links inside become relative, links out become copies, dangling links and pipes go."""
    import tarfile

    server = tmp_path / "app" / "server"
    server.mkdir(parents=True)
    # The venv is made from the interpreter's real path. Started through a link (~/.local/bin/python3.13, say), Python
    # records the link's folder as the venv's home, and a copy of the interpreter then looks for its standard library
    # beside the link: the check failed on how this machine starts Python, not on the hook (QA 07h F6).
    base = os.path.realpath(getattr(sys, "_base_executable", None) or sys.executable)
    subprocess.run(
        [base, "-m", "venv", "--without-pip", str(server / ".venv")],
        check=True,
        capture_output=True,
        timeout=300,
    )
    absolute = [
        path
        for path in (server / ".venv" / "bin").iterdir()
        if path.is_symlink() and os.path.isabs(os.readlink(path))
    ]
    assert absolute, "a venv made here links its interpreter by an absolute path"
    (server / "data").mkdir()
    (server / "data" / "seed.json").write_text("{}")
    (server / "seed").symlink_to(server / "data" / "seed.json")
    (server / "data" / "back").symlink_to("../../server/run")
    (server / "gone").symlink_to(tmp_path / "nothing")
    (server / "zeros").symlink_to(
        "/dev/zero"
    )  # QA 07c N2: copied, it would stream until the disk fills
    os.mkfifo(server / "pipe")
    (server / "run").write_text(
        '#!/bin/sh\nexec "$(dirname "$0")/.venv/bin/python" -c "import sys; print(sys.prefix)"\n'
    )
    (server / "run").chmod(0o755)

    def copy(
        target: Path,
    ) -> (
        None
    ):  # what Harbor does: tar in the agent's machine, extract with filter="data"
        archive = tmp_path / f"{target.name}.tar.gz"
        subprocess.run(
            ["tar", "-czf", str(archive), "-C", str(server), "."],
            check=True,
            capture_output=True,
            timeout=300,
        )
        target.mkdir()
        with tarfile.open(archive) as bundle:
            bundle.extractall(target, filter="data")

    try:
        copy(tmp_path / "before")
        raise AssertionError("the copy accepted an absolute link")
    except tarfile.FilterError:
        pass
    script = (TASK / "environment" / "fsmaint-sweep").read_text()
    code = script.split("<<'EOF'\n", 1)[1].split("\nEOF\n", 1)[0]
    fixed = subprocess.run(
        [sys.executable, "-I", "-", str(server)],
        check=False,
        input=code,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert fixed.returncode == 0, fixed.stderr[-2000:]
    copy(tmp_path / "after")
    after = tmp_path / "after"
    ran = subprocess.run(
        [str(after / "run")], check=False, capture_output=True, text=True, timeout=60
    )
    assert ran.returncode == 0 and ran.stdout.strip() == str(after / ".venv"), (
        ran.stderr[-2000:]
    )
    for path in absolute:
        assert (after / ".venv" / "bin" / path.name).is_file() and not (
            after / ".venv" / "bin" / path.name
        ).is_symlink()
    assert (
        os.readlink(after / "seed") == "data/seed.json"
        and os.readlink(after / "data" / "back") == "../run"
    )
    assert (
        not (after / "gone").exists()
        and not (after / "pipe").exists()
        and not os.path.lexists(after / "zeros")
    )
    assert len(fixed.stdout.splitlines()) >= 5 and "points at a device" in fixed.stdout
    config = tomllib.loads((TASK / "task.toml").read_text())
    assert config["verifier"]["collect"] == [
        {"command": "/usr/local/sbin/fsmaint-sweep", "user": "root", "timeout_sec": 600}
    ]
    docker = (TASK / "environment" / "Dockerfile").read_text()
    assert (
        "COPY fsmaint-sweep /usr/local/sbin/fsmaint-sweep" in docker
        and "/usr/local/sbin/fsmaint-sweep" in docker.split("chmod 0700")[-1]
    )


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
    done = subprocess.run(
        [sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests")],
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    out = json.loads(done.stdout.strip().splitlines()[-1])
    assert {
        out[label] for label in ("negative", "signed", "prefixed", "underscore")
    } == {"IncompleteRead"}, out
    assert (
        out["huge chunk"] == out["until close"] == "too large" and out["fine"] == {}
    ), out
    assert out["grew"] < 200, f"the evaluation grew by {out['grew']:.0f} MiB"


def test_a_process_whose_main_thread_exited_is_still_found_and_killed(tmp_path):
    """QA 07c F2: a process whose leader thread called exit() while other threads run shows State Z in /proc, and the
    sweep skipped zombies, so it survived every stop. It now counts as alive while it has more than one thread or a
    thread that is not a zombie; each kill round also runs `kill -9 -1` as the user. A real zombie is left to the reaper."""
    proc = tmp_path / "proc"
    for pid, uid, state, threads, tasks in (
        ("100", 65534, "S (sleeping)", 1, ["S"]),
        ("200", 65534, "Z (zombie)", 3, ["Z", "S", "R"]),
        ("300", 65534, "Z (zombie)", 1, ["Z"]),
        ("400", 0, "S (sleeping)", 1, ["S"]),
        ("500", 65534, "Z (zombie)", 1, ["Z", "R"]),
    ):
        (proc / pid).mkdir(parents=True)
        (proc / pid / "status").write_text(
            f"Name:\tx\nState:\t{state}\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\nThreads:\t{threads}\n"
        )
        for number, task_state in enumerate(tasks):
            (proc / pid / "task" / str(int(pid) + number)).mkdir(parents=True)
            (proc / pid / "task" / str(int(pid) + number) / "stat").write_text(
                f"{pid} (a b) {task_state} 1 1 1"
            )
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
    done = subprocess.run(
        [sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests"), str(proc)],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    out = json.loads(done.stdout.strip().splitlines()[-1])
    assert out == {
        "alive": [100, 200, 500],
        "gone": False,
        "stopped": [100, 200, 500],
        "killed": [100, 200, 500],
        "as user": True,
    }


def test_the_server_cannot_fill_the_disk_through_its_log_and_a_low_disk_stops_it(
    tmp_path,
):
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
    done = subprocess.run(
        [sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests"), str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    out = json.loads(done.stdout.strip().splitlines()[-1])
    assert (
        out["kept"] <= (2 << 20) + 100
        and out["head"] == "==== start 1 ===="
        and out["tail"] == "159159"
        and out["marker"]
    )
    assert out["ballast"] == 8 << 20 and out["released"]
    marker = tmp_path / "run" / "w" / "data" / "fill"
    setup = (
        f"import os\nreplay.GUARD_SEC = 0.1\nreplay.DISK_EVERY = 1\n_free = replay.free_bytes\n"
        f"replay.free_bytes = lambda path: 0 if os.path.exists({str(marker)!r}) else _free(path)\n"
    )
    scenarios = [
        {"id": f"S{i:02d}", "theme": "t", "steps": [step("/items/1"), step("/items/2")]}
        for i in range(60)
    ]
    scenarios.insert(5, {"id": "FILL", "theme": "fill", "steps": [step("/fill")]})
    run = drive(tmp_path / "run", "overlap", scenarios, setup=setup, RETRY_SHARE=1.0)
    metrics, reasons = run["metrics"], [result["reason"] for result in run["results"]]
    assert (
        "the server was stopped when the disk ran low" in reasons
        and metrics["retried"] == 0
    ), reasons
    assert (
        any("disk ran low" in note for note in metrics["notes"])
        and 0 < metrics["reward"] < 1
    )


def test_a_drip_after_any_framing_ends_at_the_deadline_health_check_included(tmp_path):
    """QA 07d M1: http.client lets go of the connection's socket once an answer will close it (Connection: close,
    HTTP/1.0, no length, chunked and closing), so the watcher could not reach it, and one byte every few seconds held
    evaluate() at the server's pace (81 s for a 5 s deadline); a dripped health check held start() under the server's
    lock. Every read of an answer now stops at its end time, and the watcher keeps a handle on every socket."""
    scenarios = [
        {"id": f"S-{kind}", "theme": "t", "steps": [step(f"/{kind}")]}
        for kind in ("close", "nolength", "http10", "chunkclose")
    ]
    scenarios += [
        {"id": f"F{i}", "theme": "t", "steps": [step("/items/1")]} for i in range(4)
    ]
    out = drive(
        tmp_path / "answers",
        "drip",
        scenarios,
        REQUEST_SEC=1,
        DEADLINE_SEC=6,
        HEALTH_SEC=1,
    )
    reasons = {result["id"]: result["reason"] for result in out["results"]}
    assert out["seconds"] < 15, out["seconds"]
    assert {
        reasons[f"S-{kind}"] for kind in ("close", "nolength", "http10", "chunkclose")
    } <= {"no answer from the server", "not played to the end before the time limit"}
    health = drive(
        tmp_path / "health", "healthdrip", scenarios[:2], START_SEC=3, DEADLINE_SEC=6
    )
    assert (
        health["seconds"] < 15
        and health["results"][0]["reason"] == "the server did not start"
    ), health


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
    done = subprocess.run(
        [sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests"), str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    out = json.loads(done.stdout.strip().splitlines()[-1])
    assert out["bounded"] < 3, out
    assert (
        out["taken"] == 1
        and out["left"] == []
        and out["aside"] == "still here"
        and out["moved"] < 1
    ), out
    source = (STEP / "tests" / "verifier" / "replay.py").read_text()
    evaluate_source = source[source.index("def evaluate(") :]
    clean_slate = source[
        source.index("    def clean_slate(self)") : source.index("    def start(self)")
    ]
    assert (
        "shutil.rmtree" not in source
        and "remove_tree(" not in evaluate_source
        and "remove_user_files(" not in evaluate_source
    )
    assert (
        "aside=aside" in clean_slate
        and "skip=(str(self.work), str(self.source))" in clean_slate
    )
    scenarios = [
        {
            "id": f"S{i:03d}",
            "theme": "crash" if i % 10 == 3 else "fine",
            "steps": [step("/items/1"), step("/crash" if i % 10 == 3 else "/items/2")],
        }
        for i in range(30)
    ]
    out = drive(tmp_path / "run", "disk", scenarios, RETRY_SHARE=1.0)
    work = tmp_path / "run" / "w"
    assert out["metrics"]["retried"] > 0 and (work / "data").is_dir(), (
        "DATA_DIR is left in place at the end"
    )
    assert any(
        path.name.startswith("data-") for path in (work / "set-aside").iterdir()
    ), "the clean slate moved DATA_DIR aside"


METER = r"""
import json, os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from verifier import replay
root = Path(sys.argv[2])
replay.PROC, replay.CGROUP_ROOT = str(root / "proc"), str(root / "cgroup")
replay.SCRATCH = (str(root / "shm"),)
GiB, MiB = 1 << 30, 1 << 20


def put(path, text):
    path = root / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def v2(anon, shmem, file=900 * MiB, slab=50 * MiB):  # memory.current is everything charged, page cache included
    put("cgroup/memory.current", str(anon + shmem + file + slab + 80 * MiB))
    put("cgroup/memory.stat", f"anon {anon}\nfile {file + shmem}\nshmem {shmem}\nslab_reclaimable {slab}\nsock 0\n")


def grader(anon):
    put("proc/self/status", f"Name:\tpython3\nRssAnon:\t{anon >> 10} kB\n")


out = {}
put("proc/self/cgroup", "0::/\n")
grader(400 * MiB)
v2(anon=420 * MiB, shmem=0)  # before the server starts: the grader's own memory and a little else
meter = replay.MemoryMeter(65534)
out["kind"] = meter.kind
# an honest server: 900 MiB of its own, four workers that share 300 MiB through /dev/shm (SQLite, multiprocessing) and a
# 2 GiB database file they all map, which is page cache; the grader has grown by its upload cache. Each page counts once.
grader(600 * MiB)
v2(anon=(600 + 20 + 900) * MiB, shmem=300 * MiB, file=2 * GiB + 900 * MiB)
out["honest"] = meter.server_bytes() >> 20
# the attack: SysV segments and memfds that no process maps, parked until the container is nearly full
v2(anon=(600 + 20 + 900) * MiB, shmem=(300 + 5600) * MiB)
out["parked"] = meter.server_bytes() >> 20
# cgroup v1 and a virtual machine's meminfo, where there is no v2 cgroup
put("proc/self/cgroup", "5:memory:/docker/abc\n")
put("cgroup/memory/docker/abc/memory.stat", f"rss {900 * MiB}\nshmem {7 * GiB}\ncache {8 * GiB}\ntotal_rss {900 * MiB}\ntotal_shmem {7 * GiB}\n")
out["v1"] = [replay.MemoryMeter(65534).kind, replay.MemoryMeter(65534).pinned() >> 20]
put("proc/self/cgroup", "")
put("proc/meminfo", f"MemTotal:\t{8 * GiB >> 10} kB\nMemFree:\t{GiB >> 10} kB\nMemAvailable:\t{6 * GiB >> 10} kB\n")
machine = replay.MemoryMeter(65534)
put("proc/meminfo", f"MemTotal:\t{8 * GiB >> 10} kB\nMemFree:\t{GiB >> 10} kB\nMemAvailable:\t{GiB >> 10} kB\n")
out["meminfo"] = [machine.kind, machine.server_bytes() >> 20]
put("proc/self/status", "Name:\tpython3\nVmRSS:\t409600 kB\n")  # gVisor: no RssAnon, and MemAvailable is MemFree
out["gvisor"] = replay.MemoryMeter(65534).kind
grader(400 * MiB)
put("proc/meminfo", f"MemTotal:\t{64 * GiB >> 10} kB\nMemAvailable:\t{GiB >> 10} kB\n")  # a shared host's: not this machine's
# only the server's processes: proportional set size, unattached SysV segments, unmapped files in memory-backed places
# (the user here is this check's own, who can own a file)
me = os.getuid()
for pid, pss_anon, pss_shmem, maps in ((101, 500 * MiB, 150 * MiB, "7f00-7f80 rw-s 0 0:22 7 /shm/shared\n"),
                                       (102, 500 * MiB, 150 * MiB, "7f00-7f80 rw-s 0 0:22 7 /shm/shared\n")):
    put(f"proc/{pid}/status", f"Name:\tserver\nState:\tS (sleeping)\nUid:\t{me}\t{me}\t{me}\t{me}\nThreads:\t1\n")
    put(f"proc/{pid}/smaps_rollup", f"Rss:\t{(pss_anon * 2) >> 10} kB\nPss:\t{(pss_anon + pss_shmem) >> 10} kB\n"
                                     f"Pss_Anon:\t{pss_anon >> 10} kB\nPss_Shmem:\t{pss_shmem >> 10} kB\n")
    put(f"proc/{pid}/maps", maps)
put("proc/sysvipc/shm", "       key      shmid perms                  size  cpid  lpid nattch   uid   gid  cuid  cgid      atime      dtime      ctime                   rss                  swap\n"
    f"         1          1   600            {GiB}   101   101      0 {me} {me} {me} {me} 0 0 0 {GiB} 0\n"
    f"         2          2   600            {GiB}   101   101      1 {me} {me} {me} {me} 0 0 0 {GiB} 0\n"
    f"         3          3   600            {GiB}     1     1      0     0     0     0     0 0 0 0 {GiB} 0\n")
put("shm/parked", "x" * (3 * MiB))
device = os.stat(root / "shm").st_dev  # the scratch place is a tmpfs on this machine
put("proc/self/mountinfo", f"36 25 {os.major(device)}:{os.minor(device)} / {root / 'shm'} rw - tmpfs tmpfs rw\n")
processes = replay.MemoryMeter(me)
out["processes"] = [processes.kind, processes.server_bytes() >> 20, os.lstat(root / "shm" / "parked").st_blocks * 512 >> 20]
print(json.dumps(out))
"""


def test_the_memory_guard_counts_every_page_the_server_holds_once(tmp_path):
    """QA 07e M3: the guard summed the memory the server's processes map, so SysV segments, memfds and files in /dev/shm
    that no process maps were invisible: a server could park the container's memory just under its limit and have the
    grader OOM-killed in a millisecond. QA 07e S-a and the deciding judge: the count must not stop an honest server by
    mistake, one that shares memory among workers or keeps SQLite or multiprocessing files in /dev/shm. The guard now
    reads what the kernel charges: the container's memory cgroup (or a virtual machine's own meminfo), less reclaimable
    page cache and slab, the grader's own memory and what was in use before the server started. Every page counts once,
    whatever holds it; only where neither exists does it fall back to the server's processes (proportional set size),
    its unattached SysV segments and its unmapped files in memory-backed places."""
    done = subprocess.run(
        [sys.executable, "-I", "-B", "-c", METER, str(STEP / "tests"), str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr[-3000:]
    out = json.loads(done.stdout.strip().splitlines()[-1])
    assert out["kind"] == "cgroup v2"
    # its own 900 MiB and its 300 MiB of shared memory, once each; not the database file, not the grader's growth, not the
    # 20 MiB that was in use before it started
    assert out["honest"] == 900 + 300, out
    assert out["parked"] == 900 + 300 + 5600 > 6 << 10, (
        out
    )  # over the 6 GiB the instruction allows, though no process maps it
    assert out["v1"] == ["cgroup v1", 900 + (7 << 10)]
    assert out["meminfo"] == ["meminfo", 5 << 10], out
    assert out["gvisor"] == "processes", (
        out
    )  # QA 07f S2: meminfo is not read where the kernel reports no RssAnon
    # 2 x (500 + 150) MiB of proportional set size, the unattached 1 GiB segment of the server's user (not the attached
    # one, whose pages are in the set size, nor root's), and the file parked in /dev/shm that no process maps
    kind, held, parked = out["processes"]
    assert kind == "processes" and held == 2 * 650 + 1024 + parked and parked >= 3, out


def test_memory_the_server_holds_stops_it_and_a_dead_grader_leaves_no_reward(tmp_path):
    """QA 07d M3, 07e M3: the guard reads the server's memory every 10 ms where one file reports it, and past 6 GiB
    stops the server for good, removes what its user keeps in memory without a process (SysV objects, files in
    memory-backed places; also at every stop) and fails the scenarios it had left, with a note. If the grader dies
    anyway, no reward file exists, so the result is an evaluation error, never a 0."""
    marker = tmp_path / "run" / "w" / "data" / "fill"
    setup = (
        "import os\n"
        "class Meter:\n"
        "    kind, source, fast, peak = 'cgroup v2', 'fake', True, 0\n"
        f"    def server_bytes(self):\n        return (8 << 30) if os.path.exists({str(marker)!r}) else (1 << 30)\n"
        "replay.make_meter = lambda candidate: Meter()\n"
    )
    scenarios = [
        {"id": f"S{i:02d}", "theme": "t", "steps": [step("/items/1"), step("/items/2")]}
        for i in range(60)
    ]
    scenarios.insert(5, {"id": "FILL", "theme": "fill", "steps": [step("/fill")]})
    run = drive(tmp_path / "run", "overlap", scenarios, setup=setup, RETRY_SHARE=1.0)
    reasons = [result["reason"] for result in run["results"]]
    assert (
        "the server was stopped when it held more than 6 GiB of memory" in reasons
        and run["metrics"]["retried"] == 0
    )
    assert (
        any("6 GiB of memory" in note for note in run["metrics"]["notes"])
        and run["metrics"]["memory_measure"] == "cgroup v2 fake"
    )
    source = (STEP / "tests" / "verifier" / "replay.py").read_text()
    stop = source[
        source.index(
            '    def stop(self) -> None:\n        """Stop the server for good'
        ) : source.index("    def clean_slate(self)")
    ]
    halt = source[
        source.index("    def halt(self, reason: str)") : source.index(
            "    def _watch(self) -> None:\n        candidate, meter"
        )
    ]
    # whitespace and line breaks do not count: a formatter may break these calls over lines (main's ruff splits
    # `release_memory(self.uid)` in replay.py over three)
    assert re.search(r"release_memory\(\s*self\.uid\s*,?\s*\)", stop) and re.search(
        r"release_memory\(\s*candidate\.uid\s*,?\s*\)", halt
    )
    release = source[
        source.index("def release_memory(") : source.index("def cgroup_dirs(")
    ]
    assert re.search(
        r'DROP\s*\+\s*\[\s*"ipcrm"\s*,\s*"--all"\s*,?\s*\]', release
    ) and re.search(r"memory_backed_dirs\(\s*\)", release)
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
    done = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            probe,
            str(STEP / "tests"),
            str(tmp_path / "out"),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    found = json.loads(done.stdout.strip().splitlines()[-1])
    assert (
        found["files"] == [".reward.pending", "metrics.json"]
        and found["summary"]["status"] == "evaluation_error"
    )


def test_only_a_disk_that_had_room_when_the_server_started_is_watched(tmp_path):
    """QA 07d S1: a filesystem that reports no size (a tmpfs without a limit has no blocks) read as full, and one the
    machine gave already low stopped the server at once, so an honest server scored 0. Such a path is now left out of
    the watch with a note; a machine without room where the evaluation itself writes is an evaluation error."""
    scenarios = [
        {"id": f"S{i}", "theme": "t", "steps": [step("/items/1")]} for i in range(6)
    ]
    for name, value in (("unsized", "None"), ("low", "100 << 20")):
        setup = f"_free = replay.free_bytes\nreplay.free_bytes = lambda path: {value} if str(path) == '/tmp' else _free(path)\n"
        out = drive(tmp_path / name, "plain", scenarios, setup=setup)
        assert out["metrics"]["reward"] == 1.0, out["metrics"]
        assert any(
            note.startswith("/tmp ") and "not watched" in note
            for note in out["metrics"]["notes"]
        ), out["metrics"]["notes"]
        assert out["metrics"]["free_space_mib"]["/tmp"][0] == (
            None if name == "unsized" else 100
        )
    work = tmp_path / "full" / "w"
    setup = (
        f"_free = replay.free_bytes\nreplay.free_bytes = lambda path: (100 << 20) if str(path) == {str(work)!r} else _free(path)\n"
        "_evaluate = replay.evaluate\n"
        "def evaluate(*args, **options):\n"
        "    try:\n        return _evaluate(*args, **options)\n"
        "    except replay.EvaluationError as exc:\n        return {'results': [], 'error': str(exc)}\n"
        "replay.evaluate = evaluate\n"
    )
    full = drive(tmp_path / "full", "plain", scenarios, setup=setup)
    assert (
        "MiB free on" in full["metrics"]["error"]
        and str(work) in full["metrics"]["error"]
    ), full


def test_the_reward_is_published_before_the_step_limit_whatever_the_evaluation_is_doing(
    tmp_path,
):
    """QA 07d M1: whatever the evaluation is stuck on, verify.py stops waiting before the step's limit and publishes the
    reward from what was decided, with a note; the scenarios not decided count as not matched. QA 07e S-b: the
    evaluation's own clean-up has not run then, so the ballast it set aside is given back before the reward is written."""
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
progress.ballast = replay.Ballast(Path(sys.argv[2]) / "ballast", 1 << 20)
began = time.monotonic()
metrics = verify.run_bounded(lambda: time.sleep(60), progress, 0.5)
print(json.dumps({"seconds": time.monotonic() - began, "reward": metrics["reward"], "notes": metrics["notes"],
                  "unfinished": metrics["unfinished"], "ballast": (Path(sys.argv[2]) / "ballast").exists()}))
"""
    done = subprocess.run(
        [sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests"), str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    out = json.loads(done.stdout.strip().splitlines()[-1])
    assert (
        out["seconds"] < 5
        and out["reward"] == 0.5
        and out["unfinished"] == 1
        and any("did not finish" in note for note in out["notes"])
    )
    assert out["ballast"] is False
    assert "HARD_STOP_SEC = 5_640" in (STEP / "tests" / "verify.py").read_text()


DELIVERY = r"""
import json, os, subprocess, sys, tarfile
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import verify
from verifier.replay import EvaluationError
hook, base = Path(sys.argv[2]).read_text(), Path(sys.argv[3])
fixer = hook.split("<<'EOF'\n")[1].split("\nEOF\n", 1)[0]  # the link fixer, run as the agent's user
measure = hook.split("<<'EOF'\n")[2].split("\nEOF\n", 1)[0]  # the second script, run as root after it
FULL = ("import os\n_statvfs = os.statvfs\nclass Full:\n    f_bavail = f_favail = 0\n    f_frsize = 4096\n    f_files = 1 << 20\n"
        "os.statvfs = lambda path: Full()\n")  # a disk with no room and no inode left


def deliver(name, build, entries="100000", size="1000000000", path="1000", seconds="100", start=None, tar=None, prelude="", log=None):
    app = base / name / "app"
    server, state, archives = app / "server", base / name / "state", base / name / "tmp"
    for folder in (server, state, archives):
        folder.mkdir(parents=True)
    if start is not None:
        (state / "free-at-start").write_text(start)
    if log is not None:  # the sweep's own lines, written by its shell
        (state / "log").write_text(log)
    build(server)
    environment = dict(os.environ)
    if tar is not None:  # a stand-in for the copy's tar, first on the PATH
        (base / name / "bin").mkdir()
        (base / name / "bin" / "tar").write_text("#!/bin/sh\n" + tar)
        (base / name / "bin" / "tar").chmod(0o755)
        environment["PATH"] = f"{base / name / 'bin'}:{environment['PATH']}"
    done = subprocess.run([sys.executable, "-I", "-", str(server), entries, size, path, str(state), str(archives), seconds],
                          input=prelude + measure, capture_output=True, text=True, timeout=300, env=environment)
    assert done.returncode == 0, done.stderr
    assert not os.listdir(archives), "the trial pack is removed"
    return app, server


def mark(server):
    return (server / ".fsmaint-manifest").read_text().splitlines()


def copy(server, target, cut=None):  # what Harbor does: tar on the agent's machine, extract with the data filter
    archive = target.parent / (target.name + ".tar")
    subprocess.run(["tar", "-cf", str(archive), "-C", str(server), "."], check=True, capture_output=True, timeout=120,
                   env=dict(os.environ, COPYFILE_DISABLE="1"))  # macOS's tar would add ._ files for extended attributes
    if cut is not None:
        archive.write_bytes(archive.read_bytes()[:cut])
    target.mkdir()
    try:
        with tarfile.open(archive) as bundle:
            bundle.extractall(target, filter="data")
    except (tarfile.TarError, OSError):
        pass  # the copy failed part way: what was extracted stays, as on the platform
    return target


def notes(server):
    try:
        return verify.manifest_notes(server)
    except EvaluationError as exc:
        return ["ERROR " + str(exc)]


def server_tree(server):
    (server / "app").mkdir()
    (server / "app" / "main.py").write_text("print('hi')\n" * 50)
    (server / "run").write_text("#!/bin/sh\nexec python3 app/main.py\n")
    (server / "empty").mkdir()
    (server / "inside").symlink_to("app/main.py")
    (server / "outside").symlink_to(os.path.relpath("/etc/hosts", server))  # relative, to a file outside
    (server / "absolute").symlink_to("/etc/hosts")
    (server / "app" / "b").mkdir()
    (server / "app" / "b" / "up").symlink_to("..")  # resolves inside
    (server / "esc").symlink_to("app/b/up/../..")  # lexically inside, resolves outside (QA 07f S4)
    os.mkfifo(server / "pipe")
    os.link(server / "run", server / "run-again")


def deep(server, levels=6, length=200, pad=1 << 32):
    # a path longer than this machine's PATH_MAX (1,024 bytes on macOS, 4,096 on Linux), made by directory descriptor
    fd = os.open(server, os.O_RDONLY)
    for _ in range(levels):
        os.mkdir("d" * length, dir_fd=fd)
        child = os.open("d" * length, os.O_RDONLY, dir_fd=fd)
        os.close(fd)
        fd = child
    padding = os.open("pad", os.O_WRONLY | os.O_CREAT, 0o644, dir_fd=fd)
    os.ftruncate(padding, pad)  # takes no room: the copy's tar would read every byte
    os.close(padding)
    os.close(fd)
    (server / "run").write_text("#!/bin/sh\n")


out = {}
app, server = deliver("good", server_tree, log=sys.argv[4] + "\n")
out["mark"] = mark(server)
out["left"] = sorted(path.name for path in server.iterdir())
out["complete"] = notes(copy(server, base / "good" / "copied"))
out["record"] = {key: value for key, value in verify.manifest_record(base / "good" / "copied").items() if key != "notes"}
partial = copy(server, base / "good" / "partial")
(partial / "app" / "main.py").unlink()  # the mark arrived, a file did not
out["partial"] = notes(partial)
size = os.path.getsize(base / "good" / "copied.tar")
out["cut"] = notes(copy(server, base / "good" / "cut", cut=size // 3))
out["nothing"] = notes(copy(server, base / "good" / "empty", cut=0))
(server / ".fsmaint-manifest").write_text("complete ² 5\n")  # not ASCII digits: a manifest the hook did not write (QA 07f N1)
out["odd"] = notes(server)
(server / ".fsmaint-manifest").unlink()
out["unmarked"] = notes(copy(server, base / "good" / "unmarked"))
app, server = deliver("many", server_tree, entries="3")
out["many"] = [mark(server), sorted(path.name for path in server.iterdir()),
               sorted(path.name.split(".")[1] if path.name.startswith(".") else path.name for path in app.iterdir())]
out["many_notes"] = notes(copy(server, base / "many" / "copied"))
app, server = deliver("sparse", lambda server: deep(server, levels=0))
out["sparse"] = mark(server)[:2]
app, server = deliver("deep", deep)  # QA 07f M4: past PATH_MAX, the path limit refuses it
out["deep"] = mark(server)[:2]
app, server = deliver("deep-seen", deep, path="100000")  # with no path limit, the walk still sees the 4 GiB below
out["deep_seen"] = mark(server)[:2]
app, server = deliver("slow", server_tree, seconds="1", tar="sleep 30\n")
out["slow"] = mark(server)[:2]
app, server = deliver("broken", server_tree, tar="echo 'tar: ./x: Cannot open: Input/output error' >&2; exit 2\n")
out["broken"] = mark(server)[:2]
failing = "echo 'tar: /tmp/x: Cannot open: No space left on device' >&2; exit 2\n"
app, server = deliver("inodes", server_tree, start="2500000 4096 1300000\n", tar=failing, prelude=FULL)
out["inodes"] = mark(server)[:2]
app, server = deliver("never-room", server_tree, tar=failing, prelude=FULL)
out["never_room"] = mark(server)
app, server = deliver("nop", lambda server: None)
out["nop"] = [mark(server), notes(copy(server, base / "nop" / "copied")), verify.manifest_record(base / "nop" / "copied")["sweep_log"]]
outside = base / "venv-like"
outside.mkdir()
for number in range(20):
    (outside / str(number)).write_text("x")
fixed = base / "fixer" / "server"
fixed.mkdir(parents=True)
(fixed / "lib").symlink_to(outside)
done = subprocess.run([sys.executable, "-I", "-", str(fixed), "10", "1000000000"], input=fixer, capture_output=True, text=True, timeout=60)
out["fixer"] = [done.returncode, done.stdout.strip(), os.path.lexists(fixed / "lib")]
print(json.dumps(out))
"""


SWEEP_LINES = (
    "sweep: a su session of the user had a process limit of 16384",
    "sweep: what the user left in /logs/artifacts was moved aside",
)


def test_a_delivery_the_agent_can_make_uncopyable_is_bounded_before_the_copy_and_scored_as_it_arrives(
    tmp_path,
):
    """QA 07e M4 and 07f M4: the agent must not be able to make the copy of /app/server fail, which would leave no result
    and a re-run. Round 6's bound walked by path name and skipped, silently, anything below PATH_MAX, where a 4 TiB
    sparse file made the platform's pack outlast its limit; full inodes did the same. The hook now ends the agent's
    processes with one `kill -9 -1` as their user, gives back room and inodes set aside when the session began, walks
    the delivery by directory descriptor and refuses on anything it cannot complete or past the instruction's limits
    (100,000 entries, 1 GB counting each file once, paths of 1,000 bytes), removes what the copy would refuse (a link
    that resolves outside, through other links too), and then packs it once the way the copy does, within 100 s: a pack
    that fails or overruns is refused, unless it failed for want of room or inodes the machine never had. A refused
    delivery arrives as an empty directory marked `refused` and scores 0. The verifier scores what arrived, with a note
    when the mark is missing or says refused; a mark that counts more than arrived (a copy the platform cut short, QA
    07f S1) and an /app/server of which nothing arrived are evaluation errors."""
    done = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            DELIVERY,
            str(STEP / "tests"),
            str(TASK / "environment" / "fsmaint-sweep"),
            str(tmp_path),
            "\n".join(SWEEP_LINES),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert done.returncode == 0, done.stderr[-3000:]
    out = json.loads(done.stdout.strip().splitlines()[-1])
    run = len("#!/bin/sh\nexec python3 app/main.py\n")
    # app, app/main.py, app/b, app/b/up, run, run-again, empty, inside: 8 entries; run and run-again are one file
    assert out["mark"][0] == f"complete 8 {600 + run}", out["mark"]
    hook_lines = [line for line in out["mark"][1:] if not line.startswith("sweep: ")]
    assert sorted(hook_lines) == [
        "removed absolute: a link that leads outside /app/server",
        "removed esc: a link that leads outside /app/server",
        "removed outside: a link that leads outside /app/server",
        "removed pipe: not a file, a directory or a link",
    ]
    assert out["mark"][-2:] == list(SWEEP_LINES), (
        "the sweep's own lines close the manifest"
    )
    assert out["record"] == {"sweep_log": list(SWEEP_LINES)}
    assert out["left"] == [
        ".fsmaint-manifest",
        "app",
        "empty",
        "inside",
        "run",
        "run-again",
    ]
    assert out["complete"] == [f"collect hook: {line}" for line in hook_lines], out[
        "complete"
    ]
    # a copy cut short is never scored as complete: the mark counts more than arrived (an error), the mark is missing
    # (scored with a note), or nothing came (an error)
    assert out["cut"][0].startswith(
        (
            "ERROR The copy arrived incomplete",
            "/app/server arrived without",
            "ERROR Nothing",
        )
    ), out["cut"]
    assert out["nothing"][0].startswith("ERROR Nothing arrived") and out["unmarked"][
        0
    ].startswith("/app/server arrived without")
    assert out["partial"] == [
        f"ERROR The copy arrived incomplete: 7 of 8 entries and {run:,} of {600 + run:,} bytes"
    ], out["partial"]
    assert out["odd"] == [
        "the collect hook's manifest could not be read; /app/server was scored as it arrived"
    ]
    assert out["many"] == [
        [
            "refused",
            "it holds more than 3 entries, the most /app/server may hold: it was not copied",
        ],
        [".fsmaint-manifest"],
        ["refused", "server"],
    ], out["many"]
    assert (
        out["many_notes"][0]
        == "collect hook: it holds more than 3 entries, the most /app/server may hold: it was not copied"
    )
    assert out["sparse"] == [
        "refused",
        "it holds more than 1,000,000,000 bytes, the most /app/server may hold: it was not copied",
    ]
    assert out["deep"] == [
        "refused",
        "it holds a path longer than 1,000 bytes, the longest /app/server may hold: it was not copied",
    ]
    assert out["deep_seen"] == out["sparse"], out["deep_seen"]
    assert out["slow"] == [
        "refused",
        "the copy's pack of it took more than 1 seconds: it was not copied",
    ]
    assert out["broken"] == [
        "refused",
        "the copy's pack of it failed (tar: ./x: Cannot open: Input/output error): it was not copied",
    ]
    assert (
        out["inodes"][0] == "refused" and "No space left on device" in out["inodes"][1]
    ), out["inodes"]
    assert out["never_room"][0].startswith("complete ") and any(
        "room the machine did not have" in line for line in out["never_room"]
    )
    assert out["nop"] == [["complete 0 0"], [], []]
    assert (
        out["fixer"][0] == 0
        and "copying it would pass 10 entries" in out["fixer"][1]
        and out["fixer"][2] is False
    ), out["fixer"]
    hook = (TASK / "environment" / "fsmaint-sweep").read_text()
    assert (
        hook.index("kill -9 -1")
        < hook.index('rm -f "$STATE/room"')
        < hook.index('rm -rf "$STATE/inodes"')
        < hook.index('date > "$STATE/fence"')
    )
    assert hook.index('rm -rf "$STATE/inodes"') < hook.index(
        'mv -f /app/server/.fsmaint-manifest "$aside/"'
    )
    assert hook.index('mv -f /app/server/.fsmaint-manifest "$aside/"') < hook.index(
        "timeout 120 setpriv --reuid dev --regid dev --clear-groups --no-new-privs"
    )
    for setting in (
        "LIMIT_ENTRIES=100000",
        "LIMIT_BYTES=1000000000",
        "LIMIT_PATH=1000",
        "PACK_SECONDS=100",
        "STATE=/var/lib/fsmaint",
    ):
        assert setting in hook, setting
    setup = (TASK / "environment" / "start-stockwell").read_text()
    assert (
        "fallocate -l 64M /var/lib/fsmaint/room" in setup
        and "/var/lib/fsmaint/inodes/$spare" in setup
        and "seq 1 64" in setup
    )
    assert "stat -f -c '%a %S %d' /tmp > /var/lib/fsmaint/free-at-start" in setup
    instruction = " ".join((STEP / "instruction.md").read_text().split())
    assert (
        "at most 100,000 files and directories and 1 GB, with no path inside it longer than 1,000 bytes"
        in instruction
    )
    assert "room left to copy it" in instruction


HOOK_SHELL = (
    "/bin/dash" if os.access("/bin/dash", os.X_OK) else shutil.which("sh")
)  # the image's /bin/sh is dash: the hooks run under it


def until(condition, seconds: float):
    """The condition's first true value within `seconds`, polled every 50 ms; its last value otherwise."""
    stop = time.monotonic() + seconds
    while True:
        value = condition()
        if value or time.monotonic() > stop:
            return value
        time.sleep(0.05)


VERIFY_MAIN = r"""
import json, os, pwd, sys
from pathlib import Path
tests, base, server = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
sys.path.insert(0, str(tests))
import verify
from verifier import replay
mapping = {"/logs/verifier": base / "logs", "/app/server": server, "/work": base / "work"}
calls = {}

def evaluate(source, scenario_path, work, output, progress=None, **more):
    calls["evaluate"] = [str(source), scenario_path.name, (source / "run").is_file(), str(work), str(output)]
    return {"reward": 1.0, "units_matched": 4002, "units_total": 4002, "notes": ["a note of the replay's"], "results": [{"id": "s1"}]}

verify.Path = lambda value: Path(mapping.get(str(value), value))
verify.evaluate = evaluate
verify.end_user_processes = lambda uid, *rest, **more: calls.setdefault("ended", uid)  # nothing is signalled here
verify.__file__ = str(base / "tests" / "verify.py")
os.geteuid = lambda: 0
code = verify.main()
logs = base / "logs"
out = {"code": code, "files": sorted(path.name for path in logs.iterdir()), "evaluate": calls.get("evaluate"),
       "ended_nobody": calls.get("ended") == pwd.getpwnam(replay.RUN_AS).pw_uid, "metrics": json.loads((logs / "metrics.json").read_text())}
if (logs / "reward.txt").exists():
    out["reward"] = (logs / "reward.txt").read_text()
print(json.dumps(out))
"""


def sweep_tree(base: Path, server: Path) -> None:
    """A tree that holds what the copy refuses, the agent's own file under the manifest's name among it."""
    for folder in (server / "app", server / "empty", base / "outside"):
        folder.mkdir(parents=True, exist_ok=True)
    (server / "app" / "main.py").write_text("print('hi')\n" * 50)
    (server / "run").write_text("#!/bin/sh\nexec python3 app/main.py\n")
    (server / "run").chmod(0o755)
    os.link(server / "run", server / "run-again")
    (server / "inside").symlink_to(
        server / "app" / "main.py"
    )  # absolute, inside: made relative
    (base / "outside" / "interpreter").write_text("x" * 1000)
    (server / "venv-python").symlink_to(
        base / "outside" / "interpreter"
    )  # absolute, outside: a copy
    (server / "gone").symlink_to(base / "outside" / "nothing")  # dangling: removed
    os.mkfifo(server / "pipe")  # removed
    (server / ".fsmaint-manifest").write_text(
        "complete 0 0\nsweep: a line of the agent's own\n"
    )  # the agent's own: moved aside


def sweep_under_the_shell(
    base: Path, build=sweep_tree, stand_ins: dict[str, str] | None = None
) -> tuple[subprocess.CompletedProcess, Path, list[int]]:
    """The whole sweep under the image's shell on the tree `build` makes (by default one that holds what the copy
    refuses), with only its absolute paths pointed into `base` (the lines changed are returned: those of the shell
    before the first script, and the two lines that start the scripts), /proc pointed at `base`/proc (empty unless
    `build` makes processes there) and stand-ins first on PATH, which `stand_ins` adds to or replaces: `pgrep -u dev`
    finds no process, so the lines that end the user's processes are never reached; `setpriv` runs the command as this
    user and never a `kill`; `pkill` does nothing; `id` gives the user's id as 4242."""
    source = (TASK / "environment" / "fsmaint-sweep").read_text()
    server = base / "app" / "server"
    for folder in (
        base / "state" / "inodes",
        base / "tmp",
        base / "bin",
        base / "proc",
        server,
    ):
        folder.mkdir(parents=True)
    (base / "state" / "room").write_text("x" * 1024)
    (base / "state" / "inodes" / "1").write_text("")
    (base / "state" / "free-at-start").write_text("2500000 4096 1300000\n")
    build(base, server)
    tools = {
        "pgrep": f'#!/bin/sh\ncase " $* " in *" -u dev "*) exit 1 ;; esac\nexec {shlex.quote(shutil.which("pgrep"))} "$@"\n',
        "pkill": "#!/bin/sh\nexit 0\n",
        "id": "#!/bin/sh\necho 4242\n",
        "setpriv": '#!/bin/sh\nwhile [ $# -gt 0 ]; do case "$1" in --reuid|--regid) shift 2 ;; --*) shift ;; *) break ;; esac; done\n'
        '[ "$1" = kill ] && exit 0\nexec "$@"\n',
    }
    if not shutil.which("timeout"):
        tools["timeout"] = '#!/bin/sh\nshift\nexec "$@"\n'
    tools.update(stand_ins or {})
    for name, text in tools.items():
        (base / "bin" / name).write_text(text)
        (base / "bin" / name).chmod(0o755)
    quoted = {
        name: shlex.quote(str(path))
        for name, path in (
            ("state", base / "state"),
            ("server", server),
            ("app", base / "app"),
            ("tmp", base / "tmp"),
            ("python", sys.executable),
            ("artifacts", base / "agent-logs" / "artifacts"),
            ("proc", base / "proc"),
        )
    }
    shell, rest = source.split("<<'EOF'\n", 1)
    for old, new, count in (
        ("STATE=/var/lib/fsmaint\n", f"STATE={quoted['state']}\n", 1),
        (
            "/opt/py/bin/python -I - /app/server ",
            f"{quoted['python']} -I - /app/server ",
            1,
        ),
        (
            "/opt/py/bin/python -I - /proc ",
            f"{quoted['python']} -I - {quoted['proc']} ",
            1,
        ),
    ):
        assert shell.count(old) == count, (old, shell.count(old))
        shell = shell.replace(old, new)
    shell = shell.replace("/app/server", quoted["server"]).replace(
        "/app/.aside.", f"{quoted['app']}/.aside."
    )
    shell = shell.replace("/logs/artifacts", quoted["artifacts"]).replace(
        "/opt/py/bin/python -I -c", f"{quoted['python']} -I -c"
    )
    start = 'exec /opt/py/bin/python -I - /app/server "$LIMIT_ENTRIES" "$LIMIT_BYTES" "$LIMIT_PATH" "$STATE" /tmp "$PACK_SECONDS" <<'
    assert rest.count(start) == 1, "the second script starts on one line"
    text = (
        shell
        + "<<'EOF'\n"
        + rest.replace(
            start,
            f'exec {quoted["python"]} -I - {quoted["server"]} "$LIMIT_ENTRIES" "$LIMIT_BYTES" "$LIMIT_PATH" "$STATE" '
            f'{quoted["tmp"]} "$PACK_SECONDS" <<',
        )
    )
    assert len(text.splitlines()) == len(source.splitlines())
    changed = [
        number
        for number, (old, new) in enumerate(
            zip(source.splitlines(), text.splitlines()), 1
        )
        if old != new
    ]
    (base / "fsmaint-sweep").write_text(text)
    done = subprocess.run(
        [HOOK_SHELL, str(base / "fsmaint-sweep")],
        check=False,
        env=dict(os.environ, PATH=f"{base / 'bin'}:{os.environ['PATH']}"),
        capture_output=True,
        text=True,
        timeout=300,
    )
    return done, server, changed


def copied(server: Path, target: Path) -> Path:
    """What the copy does: a tar of the directory where it was built, extracted elsewhere with the `data` filter."""
    import tarfile

    target.parent.mkdir(parents=True, exist_ok=True)
    archive = target.parent / (target.name + ".tar.gz")
    subprocess.run(
        ["tar", "-czf", str(archive), "-C", str(server), "."],
        check=True,
        capture_output=True,
        timeout=120,
        env=dict(os.environ, COPYFILE_DISABLE="1"),
    )  # macOS's tar would add ._ files for extended attributes
    target.mkdir()
    with tarfile.open(archive) as bundle:
        bundle.extractall(target, filter="data")
    return target


def verify_main(base: Path, server: Path) -> dict:
    """verify.py's main() on a copy that arrived, with /logs/verifier, /app/server and /work in `base`, the root test
    answered yes, and the replay and the ending of the server's processes replaced: nothing runs and nothing is
    signalled."""
    for folder in (base / "logs", base / "work", base / "tests" / "private"):
        folder.mkdir(parents=True, exist_ok=True)
    for leftover in (base / "logs").iterdir():
        leftover.unlink()
    (base / "tests" / "private" / "scenarios.json.gz").write_bytes(
        b""
    )  # the name the image ships; the stand-in replay reads nothing
    done = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            VERIFY_MAIN,
            str(STEP / "tests"),
            str(base),
            str(server),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert done.stdout.strip(), done.stderr[-3000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_the_sweep_runs_whole_under_the_image_shell_and_verify_main_reads_what_it_wrote(
    tmp_path,
):
    """QA 07h F2: no check ran the sweep's shell (the checks cut its two Python scripts out) or verify.py's main(), the
    place a renamed name would break on the platform alone. Here the whole sweep runs under the image's shell, the
    directory is copied the way the copy is made, and main() reads it: the manifest's first line arrives in
    metrics.json with no line of the sweep's own (a session whose start was not recorded, as here, has nothing after its
    end), and a copy that lost a file is an evaluation error with no reward. What stays unrun here: the hooks as root in
    the image, with the real setpriv, pkill and paths."""
    done, server, changed = sweep_under_the_shell(tmp_path / "one")
    assert done.returncode == 0 and done.stderr == "", (done.returncode, done.stderr)
    hook = (TASK / "environment" / "fsmaint-sweep").read_text().splitlines()
    first_script = next(
        number for number, line in enumerate(hook, 1) if line.endswith("<<'EOF'")
    )
    second_script = [
        number
        for number, line in enumerate(hook, 1)
        if line.startswith("exec /opt/py/bin/python")
    ]
    assert changed[-1:] == second_script and all(
        number <= first_script for number in changed[:-1]
    ), (
        f"only the shell's lines and the line that starts the second script are pointed into this check's folder: {changed}"
    )
    state = tmp_path / "one" / "state"
    assert sorted(path.name for path in state.iterdir()) == [
        "fence",
        "free-at-start",
        "held",
        "log",
    ], "the room and the spare inodes are given back"
    assert (state / "held").read_text() == "no-start\n", (
        "no start recorded: nothing to list"
    )
    assert os.listdir(tmp_path / "one" / "tmp") == [], "the trial pack is removed"
    aside = [
        path
        for path in (tmp_path / "one" / "app").iterdir()
        if path.name.startswith(".aside.")
    ]
    assert (
        len(aside) == 1
        and "a line of the agent's own" in (aside[0] / ".fsmaint-manifest").read_text()
    ), "the agent's own file is moved aside"
    manifest = (server / ".fsmaint-manifest").read_text().splitlines()
    # app, app/main.py, empty, inside, run, run-again, venv-python: 7 entries; main.py 600, run 35 (once), the copy 1,000
    assert manifest == ["complete 7 1635"], manifest
    assert (
        os.readlink(server / "inside") == "app/main.py"
        and (server / "venv-python").read_text() == "x" * 1000
    )
    assert (
        not (server / "venv-python").is_symlink()
        and not os.path.lexists(server / "gone")
        and not os.path.lexists(server / "pipe")
    )
    for line in (
        "inside -> app/main.py",
        "venv-python: a copy of",
        "removed gone ->",
        "removed pipe: not a file, a directory or a link",
    ):
        assert line in done.stdout, (line, done.stdout)
    whole = verify_main(
        tmp_path / "one", copied(server, tmp_path / "one" / "arrived" / "server")
    )
    assert (
        whole["code"] == 0 and whole["reward"] == "1.000000" and whole["ended_nobody"]
    ), whole
    assert whole["files"] == ["metrics.json", "reward.txt", "scenario_results.json"], (
        whole["files"]
    )
    assert whole["evaluate"][1:3] == ["scenarios.json.gz", True] and whole["evaluate"][
        0
    ].endswith("/arrived/server"), whole["evaluate"]
    metrics = whole["metrics"]
    assert (
        metrics["status"] == "completed"
        and metrics["notes"] == ["a note of the replay's"]
        and metrics["sweep_log"] == []
    ), metrics
    cut = copied(server, tmp_path / "one" / "cut" / "server")
    (cut / "app" / "main.py").unlink()
    short = verify_main(tmp_path / "one", cut)
    assert (
        short["code"] == 1
        and "reward" not in short
        and short["metrics"]["status"] == "evaluation_error"
    ), short
    assert (
        short["metrics"]["error"]
        == "The copy arrived incomplete: 6 of 7 entries and 1,035 of 1,635 bytes"
    ), short["metrics"]


# Round 12 (the platform's verdict on version 10, and QA 22/23 of the Carve task, which shares this hook's family): the
# ways the agent's own tree could turn its trial into an evaluation error instead of a scored 0. Each check below fails
# on 375b570.


def hook_scripts() -> tuple[str, str]:
    """The sweep's two scripts: the link fixer, run as the agent's user, and the measuring stage, run as root."""
    parts = (TASK / "environment" / "fsmaint-sweep").read_text().split("<<'EOF'\n")
    return parts[1].split("\nEOF\n", 1)[0], parts[2].split("\nEOF\n", 1)[0]


def measured(
    base: Path, build, entries: str = "100000", prelude: str = ""
) -> tuple[subprocess.CompletedProcess, Path]:
    """The measuring stage, as this user, on the tree `build` makes in `base`/app/server."""
    server, state, archives = base / "app" / "server", base / "state", base / "tmp"
    for folder in (server, state, archives):
        folder.mkdir(parents=True)
    build(server)
    done = subprocess.run(
        [
            sys.executable,
            "-I",
            "-",
            str(server),
            entries,
            "1000000000",
            "1000",
            str(state),
            str(archives),
            "100",
        ],
        check=False,
        input=prelude + hook_scripts()[1],
        capture_output=True,
        text=True,
        timeout=300,
    )
    return done, server


def manifest_lines(server: Path) -> list[str]:
    return (server / ".fsmaint-manifest").read_text().splitlines()


RECORD = r"""
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import verify
from verifier.replay import EvaluationError
try:
    print(json.dumps(verify.manifest_record(Path(sys.argv[2]))))
except EvaluationError as exc:
    print(json.dumps({"error": str(exc)}))
"""


def record_of(server: Path) -> dict:
    """What verify.py's manifest_record makes of what arrived, or the evaluation error it raises."""
    done = subprocess.run(
        [sys.executable, "-I", "-B", "-c", RECORD, str(STEP / "tests"), str(server)],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


def copied_as_far_as_it_goes(server: Path, target: Path) -> tuple[Path, str | None]:
    """The copy as the platform makes it (a tar of the directory, extracted with the `data` filter); when the
    extraction refuses a member, what came before it stays, as on the platform, with the refusal."""
    import tarfile

    archive = target.parent / (target.name + ".tar.gz")
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["tar", "-czf", str(archive), "-C", str(server), "."],
        check=True,
        capture_output=True,
        timeout=120,
        env=dict(os.environ, COPYFILE_DISABLE="1"),
    )
    target.mkdir()
    try:
        with tarfile.open(archive) as bundle:
            bundle.extractall(target, filter="data")
    except (tarfile.TarError, OSError) as exc:
        return target, f"{type(exc).__name__}: {exc}"
    return target, None


def test_whatever_stands_at_the_delivery_path_leaves_an_empty_refused_directory(
    tmp_path,
):
    """The platform's audit of Carve's version 4 named the verifier's evaluation error for a tree that arrives missing
    or as a link. Here the agent cannot replace /app/server (root's, in a root sticky /app), but the sweep exited at once
    for anything that is not a directory, writing no manifest, and the copy then followed a link or found nothing. Now
    whatever stands there is moved aside, never followed, and an empty directory takes its place with a manifest that
    refuses it: the tree scores 0 with a note, and no run arrives."""
    for shape in ("link", "dangling link", "file", "nothing"):
        base = tmp_path / shape.replace(" ", "-")

        def build(base: Path, server: Path, shape: str = shape) -> None:
            server.rmdir()
            (base / "elsewhere").mkdir()
            (base / "elsewhere" / "run").write_text("#!/bin/sh\n")
            if shape == "link":
                server.symlink_to(base / "elsewhere")
            elif shape == "dangling link":
                server.symlink_to(base / "missing")
            elif shape == "file":
                server.write_text("#!/bin/sh\n")

        done, server, _ = sweep_under_the_shell(base, build=build)
        assert done.returncode == 0 and done.stderr == "", (
            shape,
            done.returncode,
            done.stderr,
        )
        assert (
            server.is_dir()
            and not server.is_symlink()
            and os.listdir(server) == [".fsmaint-manifest"]
        ), (shape, os.listdir(server.parent))
        lines = manifest_lines(server)
        assert lines[0] == "refused" and lines[1].endswith(
            "app/server was not a directory: it was not copied"
        ), (shape, lines)
        assert lines[2:] == [], (shape, lines)
        assert sorted(os.listdir(base / "elsewhere")) == ["run"], (
            "what a link pointed at is untouched"
        )
        aside = [
            path for path in (base / "app").iterdir() if path.name.startswith(".aside.")
        ]
        assert len(aside) == (0 if shape == "nothing" else 1), (shape, aside)
        whole = verify_main(base, copied(server, base / "arrived" / "server"))
        assert whole["code"] == 0 and whole["evaluate"][2] is False, (shape, whole)
        assert whole["metrics"]["notes"][0] == "collect hook: " + lines[1], (
            shape,
            whole["metrics"]["notes"],
        )


def test_a_file_the_sweep_cannot_move_aside_from_the_manifests_name_is_removed(
    tmp_path,
):
    """QA 22 F6: where the file under the manifest's name could not be moved aside, the sweep exited 0 there and then,
    before it fixed or measured anything, so the agent's own manifest arrived; one that counts what did not arrive is
    an evaluation error. It is removed instead, and the sweep goes on."""
    done, server, _ = sweep_under_the_shell(
        tmp_path / "one", stand_ins={"mktemp": "#!/bin/sh\nexit 1\n"}
    )
    assert done.returncode == 0 and done.stderr == "", (done.returncode, done.stderr)
    lines = manifest_lines(server)
    assert lines == ["complete 7 1635"], lines
    assert not [
        path
        for path in (tmp_path / "one" / "app").iterdir()
        if path.name.startswith(".aside.")
    ]
    whole = verify_main(
        tmp_path / "one", copied(server, tmp_path / "one" / "arrived" / "server")
    )
    assert (
        whole["code"] == 0
        and whole["metrics"]["status"] == "completed"
        and whole["metrics"]["sweep_log"] == []
    ), whole


def test_entries_nobody_reaped_do_not_keep_the_sweep_ending_processes(tmp_path):
    """QA 23 N1: `pgrep -u dev` counts zombies, and where the container's first process does not reap them (this
    image's entrypoint ends in `exec sleep infinity`, as Docker runs it), every sweep made all 100 passes of the loop
    that ends the agent's processes, three scans of /proc each; with enough zombies, which the agent can leave in
    seconds, the hook's 600 s ran out before the manifest, and the agent's own one arrived. Where pgrep can tell a
    process's state (procps), only live processes keep the loop going."""
    calls = tmp_path / "calls"
    real = shlex.quote(shutil.which("pgrep"))
    pgrep = (
        f'#!/bin/sh\necho "pgrep $*" >> {shlex.quote(str(calls))}\ncase " $* " in\n'
        '    *" -r "*" -u 0 "*) exit 0 ;;\n'  # the state filter works
        '    *" -r "*" -u dev "*) exit 1 ;;\n'  # no live process of the user is left
        '    *" -u dev "*) exit 0 ;;\n'  # only entries nobody reaped
        f'esac\nexec {real} "$@"\n'
    )
    setpriv = (
        '#!/bin/sh\nwhile [ $# -gt 0 ]; do case "$1" in --reuid|--regid) shift 2 ;; --*) shift ;; *) break ;; esac; done\n'
        f'[ "$1" = kill ] && {{ echo "kill $*" >> {shlex.quote(str(calls))}; exit 0; }}\nexec "$@"\n'
    )
    started = time.monotonic()
    done, server, _ = sweep_under_the_shell(
        tmp_path / "one", stand_ins={"pgrep": pgrep, "setpriv": setpriv}
    )
    seconds = time.monotonic() - started
    assert done.returncode == 0 and done.stderr == "", (done.returncode, done.stderr)
    made = calls.read_text().splitlines()
    assert (
        made.count("kill kill -9 -1") == 0
        and made.count("pgrep -r R,S,D,T,t -u dev") == 1
    ), made[:6]
    assert manifest_lines(server)[0] == "complete 7 1635" and seconds < 10, seconds


LITTLE_ROOM = (
    "import os\nclass _Disk:\n    f_frsize = 4096\n    f_bavail = (32 << 20) // 4096\n    f_files = 1000000\n    f_favail = 500000\n"
    "os.statvfs = lambda path: _Disk()\n"
)  # 32 MiB free: less than the 64 MiB set aside


def test_the_link_fixer_keeps_free_the_room_set_aside_for_the_manifest(tmp_path):
    """QA 07g F2 and QA 22 F4(a): the sweep gives back the 64 MiB and 64 inodes set aside at the start before the link
    fixer runs, and the fixer, as the agent's user, could spend them on copies of what links outside point to; on a
    disk the agent had filled, the refusal that followed could not make its empty directory once /app/server was moved
    aside, and nothing arrived (an evaluation error). A copy is now made only if the room and the spare inodes stay
    free after it; otherwise the link is removed with a note."""
    outside = tmp_path / "outside"
    outside.mkdir()
    for number in range(20):
        (outside / str(number)).write_text("x" * 1000)
    server = tmp_path / "server"
    server.mkdir()
    (server / "lib").symlink_to(outside)
    (server / "one").symlink_to(outside / "0")
    done = subprocess.run(
        [sys.executable, "-I", "-", str(server)],
        check=False,
        input=LITTLE_ROOM + hook_scripts()[0],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    assert not os.path.lexists(server / "lib") and not os.path.lexists(
        server / "one"
    ), sorted(os.listdir(server))
    assert done.stdout.count("the disk has no room to copy it") == 2, done.stdout


def test_every_name_listed_counts_against_the_entry_limit(tmp_path):
    """QA 22 F3's other half: the measuring stage left pipes and sockets out of its count, removing and noting each, so
    tens of millions of them in directories the agent's user cannot read (the fixer skips those; the stage runs as
    root) could hold the hook past its 600 s. Every name listed now counts against the 100,000 entries."""

    def build(
        server: Path,
    ) -> None:  # 25 names: no listing alone passes 10, nor do the kept entries (5)
        (server / "run").write_text("#!/bin/sh\n")
        for folder in range(4):
            (server / f"d{folder}").mkdir()
            for number in range(5):
                os.mkfifo(server / f"d{folder}" / f"p{number}")

    done, server = measured(tmp_path, build, entries="10")
    assert done.returncode == 0, done.stderr[-2000:]
    assert manifest_lines(server)[:2] == [
        "refused",
        "it holds more than 10 entries, the most /app/server may hold: it was not copied",
    ]
    assert os.listdir(server) == [".fsmaint-manifest"]


def test_every_link_kept_leads_straight_to_what_it_points_at_so_the_copy_takes_it(
    tmp_path,
):
    """QA 22 F3 and F5: the measuring stage kept any relative link that resolved inside here, so a link that climbs above
    the root and back in, which the copy's extraction resolves from wherever it unpacks the tree, made the copy stop
    part way (an evaluation error), and it resolved every link of a chain one link at a time, which an agent can make
    quadratic past the hook's 600 s. A link the fixer did not reach (in a directory the agent's user cannot read, or
    after the fixer stopped) is now resolved only where the kernel can follow it (at most 40 links), and is kept only
    as a relative path straight to what it resolves to: written again so, or removed."""

    def build(server: Path) -> None:
        (server / "app").mkdir()
        (server / "app" / "main.py").write_text("print('hi')\n")
        (server / "run").write_text("#!/bin/sh\n")
        real = Path(os.path.realpath(server))
        (server / "climb").symlink_to(
            "../" * (len(real.parts) + 2) + str(real).lstrip("/") + "/app/main.py"
        )  # above / and back in
        for number in range(60):  # longer than the kernel follows
            (server / f"chain{number}").symlink_to(
                f"chain{number + 1}" if number < 59 else "app/main.py"
            )
        (server / "nowhere").symlink_to("app/missing.py")
        (server / "loop1").symlink_to("loop2")
        (server / "loop2").symlink_to("loop1")

    done, server = measured(tmp_path, build)
    assert done.returncode == 0, done.stderr[-2000:]
    kept = {
        path.name: os.readlink(path) for path in server.iterdir() if path.is_symlink()
    }
    assert (
        "climb" in kept
        and "chain59" in kept
        and not {"nowhere", "loop1", "loop2"} & set(kept)
    ), sorted(kept)
    assert set(kept.values()) == {"app/main.py"}, (
        "every link kept points straight at what it resolves to"
    )
    lines = manifest_lines(server)
    # one change for each link but chain59: climb and chain0-58 written again or removed, nowhere and the loop removed
    assert (
        lines[0] == f"complete {3 + len(kept)} 22"
        and lines[-1] == "and 23 more changes"
    ), (lines[0], lines[-1])
    arrived, refused = copied_as_far_as_it_goes(server, tmp_path / "arrived")
    assert refused is None, refused
    assert record_of(arrived) == {
        "notes": [f"collect hook: {line}" for line in lines[1:21]],
        "sweep_log": [],
    }


def test_a_walk_that_outlasts_its_time_refuses_the_tree(tmp_path):
    """QA 07g F1: nothing in the measuring stage refused on time, so whatever made its system calls slow (99,000 links
    whose 4,095-byte targets run through links to `.`, timed at 6 ms a link on macOS and estimated at 9-28 ms on Linux)
    held the hook past its 600 s before the manifest. The walk and the links now have 240 s, after which the tree is
    refused (here the clock is moved on after the stage reads it once)."""
    late = (
        "import time\n_monotonic, _reads = time.monotonic, []\n"
        "def _late():\n    _reads.append(1)\n    return _monotonic() + (0 if len(_reads) == 1 else 10_000)\n"
        "time.monotonic = _late\n"
    )

    def build(server: Path) -> None:
        (server / "run").write_text("#!/bin/sh\n")
        (server / "app").mkdir()

    done, server = measured(tmp_path, build, prelude=late)
    assert done.returncode == 0, done.stderr[-2000:]
    assert manifest_lines(server)[:2] == [
        "refused",
        "it could not be measured within 240 seconds: it was not copied",
    ], manifest_lines(server)
    assert os.listdir(server) == [".fsmaint-manifest"]
    stage = hook_scripts()[1]
    # realpath, which takes a link one component at a time, runs only for a link the kernel follows to something the
    # walk did not see
    assert (
        "MEASURE_SECONDS = 240" in stage
        and stage.count("os.path.realpath(") == 2
        and "os.path.realpath(os.path.join" not in stage
    )


def test_links_inside_survive_where_a_file_is_numbered_differently_by_path(tmp_path):
    """The root stage tells a link that leads inside by the device and inode the kernel reaches through it, among those
    its walk saw. On a file system that numbered a file differently by path, every link would look outside and an
    honest virtual environment would lose its own links; realpath decides there, so they stay (a guard of round 12's
    stage, not a path of round 11's)."""
    renumber = (
        "import os\n_stat = os.stat\n"
        "def _renumbered(path, *args, dir_fd=None, follow_symlinks=True):\n"
        "    info = _stat(path, *args, dir_fd=dir_fd, follow_symlinks=follow_symlinks)\n"
        "    if not follow_symlinks or dir_fd is not None:\n"
        "        return info\n"
        "    values = list(info)\n"
        "    values[1] += 1 << 40\n"
        "    return os.stat_result(values)\n"
        "os.stat = _renumbered\n"
    )

    def build(server: Path) -> None:
        (server / "venv" / "bin").mkdir(parents=True)
        (server / "venv" / "bin" / "python3.12").write_text("#!/bin/sh\n")
        (server / "venv" / "bin" / "python3").symlink_to("python3.12")
        (server / "venv" / "bin" / "python").symlink_to(
            "python3"
        )  # through a link: written straight
        (server / "venv" / "lib").mkdir()
        (server / "venv" / "lib64").symlink_to("lib")
        (server / "away").symlink_to(os.path.relpath("/etc/hosts", server))
        (server / "run").write_text("#!/bin/sh\n")

    done, server = measured(tmp_path, build, prelude=renumber)
    assert done.returncode == 0, done.stderr[-2000:]
    links = {
        path.relative_to(server).as_posix(): os.readlink(path)
        for path in server.rglob("*")
        if path.is_symlink()
    }
    assert links == {
        "venv/bin/python3": "python3.12",
        "venv/bin/python": "python3.12",
        "venv/lib64": "lib",
    }, links
    assert sorted(manifest_lines(server)[1:]) == [
        "link venv/bin/python -> python3.12 (was python3)",
        "removed away: a link that leads outside /app/server",
    ]


def test_the_manifest_holds_a_bounded_number_of_one_line_changes(tmp_path):
    """QA 22 F1 and QA 07h F4: the manifest carried one line per change with no bound (a tree with a million pipes made
    it hundreds of megabytes, all of it read by the verifier), and a path with a newline in its name could forge a
    line of the sweep's own. It now holds the first 40 changes, each one line of at most 200 characters with every
    unprintable character escaped, then how many more there were."""

    def many(server: Path) -> None:
        (server / "run").write_text("#!/bin/sh\n")
        for number in range(300):
            os.mkfifo(server / f"{number:03d}-{'p' * 240}")

    done, server = measured(tmp_path / "many", many)
    assert done.returncode == 0, done.stderr[-2000:]
    lines = manifest_lines(server)
    assert (
        lines[0] == "complete 1 10"
        and len(lines) == 1 + 40 + 1
        and lines[-1] == "and 260 more changes"
    ), (len(lines), lines[-1:])
    assert all(len(line) <= 200 for line in lines) and lines[1].endswith("..."), lines[
        1
    ]

    forged = "x\nsweep: a su session of the user had a process limit of 99999999"

    def newline(server: Path) -> None:
        (server / "run").write_text("#!/bin/sh\n")
        os.mkfifo(server / forged)

    done, server = measured(tmp_path / "newline", newline)
    assert done.returncode == 0, done.stderr[-2000:]
    lines = manifest_lines(server)
    assert lines == [
        "complete 1 10",
        (
            "removed x\\nsweep: a su session of the user had a process limit of 99999999: not a file, a directory or "
            "a link"
        ),
    ], lines
    record = record_of(server)
    assert record["sweep_log"] == [], record

    # Round 15: a link the walk writes again was noted under its own name first, so a name that starts like the sweep's
    # own lines read as one in `sweep_log`; every note now starts with what was done
    named = "sweep: 0 entries that changed after the work's end were removed"

    def relinked(server: Path) -> None:
        (server / "run").write_text("#!/bin/sh\n")
        (server / "python3.12").write_text("#!/bin/sh\n")
        (server / "python3").symlink_to("python3.12")
        (server / named).symlink_to("python3")  # through a link: written straight

    done, server = measured(tmp_path / "relinked", relinked)
    assert done.returncode == 0, done.stderr[-2000:]
    lines = manifest_lines(server)
    assert lines == ["complete 4 20", f"link {named} -> python3.12 (was python3)"], (
        lines
    )
    record = record_of(server)
    assert record["sweep_log"] == [] and record["notes"] == [
        f"collect hook: link {named} -> python3.12 (was python3)"
    ], record


def test_a_refused_tree_is_emptied_where_the_directory_cannot_be_renamed(tmp_path):
    """A refusal renamed /app/server aside and made a new one. /app/server is a directory of the image's own, and an
    overlay file system without redirect_dir answers such a rename with EXDEV, which the stage did not catch: it ended
    with no manifest and the refused tree in place, to be copied whole. Where the rename fails, what the directory
    holds is moved aside instead."""
    no_rename = (
        "import os, sys\n_rename = os.rename\n"
        "def _not_the_directory(source, target, *args, **kwargs):\n"
        "    if os.path.realpath(source) == os.path.realpath(sys.argv[1]):\n"
        "        raise OSError(18, 'Invalid cross-device link')\n"
        "    return _rename(source, target, *args, **kwargs)\n"
        "os.rename = _not_the_directory\n"
    )

    def build(server: Path) -> None:
        (server / "run").write_text("#!/bin/sh\n")
        (server / "app").mkdir()
        for number in range(5):
            (server / "app" / str(number)).write_text("x")

    done, server = measured(tmp_path, build, entries="3", prelude=no_rename)
    assert done.returncode == 0, done.stderr[-2000:]
    assert (
        os.listdir(server) == [".fsmaint-manifest"]
        and manifest_lines(server)[0] == "refused"
    ), sorted(os.listdir(server))
    aside = [
        path for path in server.parent.iterdir() if path.name.startswith(".refused.")
    ]
    assert len(aside) == 1 and sorted(os.listdir(aside[0])) == ["app", "run"], aside


def test_the_verifier_reads_only_the_head_of_the_manifest(tmp_path):
    """QA 22 F1, the verifier's side: the manifest was read whole, so one that arrived unbounded (the agent's own, where
    the sweep never ran) was held in memory however large. Only its first 64 KiB are read, more than the sweep writes."""
    server = tmp_path / "server"
    server.mkdir()
    (server / "run").write_text("#!/bin/sh\n")
    padding = "".join(f"a change {number:05d} {'x' * 80}\n" for number in range(800))
    (server / ".fsmaint-manifest").write_text(
        "complete 1 10\n" + padding + "sweep: a line past the first 64 KiB\n"
    )
    assert (server / ".fsmaint-manifest").stat().st_size > 1 << 16
    record = record_of(server)
    assert (
        record["sweep_log"] == []
        and record["notes"][0] == f"collect hook: a change 00000 {'x' * 80}"
    ), record


def test_a_file_with_more_than_a_thousand_hard_links_refuses_the_tree(tmp_path):
    """QA 08 S1: the copy's file system may allow fewer links to one file than the sandbox's (ext4 allows 65,000), and
    then the host's extraction makes copies of the file for the names past its limit: more bytes arrive than the
    manifest counts (round 12's verifier called that a copy cut short, an evaluation error), and a large file copied
    tens of thousands of times could fill the host's disk. A file with more than 1,000 hard links inside /app/server
    now refuses the tree, a noted 0, and the instruction states the limit with the others."""

    def build(server: Path, names: int) -> None:
        (server / "run").write_text("#!/bin/sh\n")
        (server / "names").mkdir()
        (server / "one").write_text("x")
        for number in range(names - 1):
            os.link(server / "one", server / "names" / str(number))

    done, server = measured(tmp_path / "many", lambda server: build(server, 1001))
    assert done.returncode == 0, done.stderr[-2000:]
    assert manifest_lines(server)[:2] == [
        "refused",
        "it holds a file with more than 1,000 hard links, the most /app/server may hold: it was not copied",
    ]
    done, server = measured(tmp_path / "enough", lambda server: build(server, 1000))
    assert done.returncode == 0 and manifest_lines(server)[0] == "complete 1002 11", (
        manifest_lines(server)[:2]
    )
    instruction = " ".join((STEP / "instruction.md").read_text().split())
    assert (
        "with no path inside it longer than 1,000 bytes and no file with more than 1,000 hard links"
        in instruction
    )


def test_more_arriving_than_the_manifest_counts_is_scored_with_a_note(tmp_path):
    """QA 08 S1, the verifier's side: where a copy keeps fewer hard links than the sandbox made, the names past its
    limit arrive as copies, so more bytes arrive than the manifest counts; the tree is whole, and it is scored as it
    arrived, with a note. Fewer entries or bytes than counted is still a copy cut short, an evaluation error."""
    server = tmp_path / "server"
    server.mkdir()
    (server / "run").write_text("#!/bin/sh\n")
    (server / "run-again").write_text(
        "#!/bin/sh\n"
    )  # a hard link of `run` in the sandbox, a copy here
    (server / ".fsmaint-manifest").write_text("complete 2 10\n")
    record = record_of(server)
    assert "error" not in record and record["notes"] == [
        (
            "more arrived than the collect hook's manifest counts (2 entries and 20 bytes, against "
            "2 and 10): hard links the copy could not keep arrive as copies; /app/server was "
            "scored as it arrived"
        )
    ], record
    (server / ".fsmaint-manifest").write_text("complete 3 20\n")
    assert record_of(server) == {
        "error": "The copy arrived incomplete: 2 of 3 entries and 20 of 20 bytes"
    }


def test_the_users_processes_are_capped_in_the_session_harbor_starts(tmp_path):
    """QA 08 S2: a fork bomb left running at the end of the session can fill the process table, so that neither the
    root collect hook nor the copy can start, and nothing arrives (an evaluation error). harbor's Modal backend starts
    every command that has a user, the agent's own session included, through `su USER -s /bin/bash -c` (harbor
    0.20's environments/modal.py), and su's PAM session runs pam_limits: the image caps the agent's user at 16,384
    processes and threads (the server it builds may use 4,096; root is not counted), makes pam_limits optional for su
    so that a limit it cannot set never stops a session (a lower hard limit is then already in place), records at set-up
    the hard limit a su session of the user gets, and the sweep carries it into the manifest's record lines."""
    docker = (TASK / "environment" / "Dockerfile").read_text()
    assert (
        "printf 'dev soft nproc 16384\\ndev hard nproc 16384\\n' > /etc/security/limits.d/90-nproc.conf"
        in docker
    )
    # harbor 0.20 as installed with the Oddish CLI on the author's machine, where it is
    for found in sorted(
        Path.home().glob(
            ".local/share/oddish-cli-noarchil/lib/python3*/site-packages/harbor/environments/modal.py"
        )
    ):
        assert (
            'command = f"su {user_arg} -s /bin/bash -c {shlex.quote(command)}"'
            in found.read_text()
        ), found
    # the Dockerfile's own lines that edit su's PAM file, run on Debian's file and on one that lacks the line, with
    # GNU sed (the image's) where this machine has it
    block = docker[
        docker.index("RUN mkdir -p /etc/security/limits.d") : docker.index(
            "\nRUN useradd"
        )
    ][len("RUN ") :]
    gnu_sed = shutil.which("gsed") or (
        shutil.which("sed")
        if "GNU"
        in subprocess.run(
            ["sed", "--version"], check=False, capture_output=True, text=True
        ).stdout
        else None
    )
    debian = (
        "auth       sufficient pam_rootok.so\nsession       required   pam_env.so readenv=1\n# Sets up user limits\n"
        "session    required   pam_limits.so\n@include common-auth\n@include common-account\n@include common-session\n"
    )
    if gnu_sed:
        (tmp_path / "bin").mkdir()
        (tmp_path / "bin" / "sed").symlink_to(gnu_sed)
        for name, text, expected in (
            (
                "debian",
                debian,
                debian.replace(
                    "session    required   pam_limits.so",
                    "session    optional   pam_limits.so",
                ),
            ),
            (
                "bare",
                "auth sufficient pam_rootok.so\n",
                "auth sufficient pam_rootok.so\nsession optional pam_limits.so\n",
            ),
        ):
            (tmp_path / name).mkdir()
            (tmp_path / name / "su").write_text(text)
            script = block.replace(
                "/etc/security/limits.d", str(tmp_path / name / "limits.d")
            ).replace("/etc/pam.d/su", str(tmp_path / name / "su"))
            done = subprocess.run(
                [HOOK_SHELL, "-c", script],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
                env=dict(os.environ, PATH=f"{tmp_path / 'bin'}:{os.environ['PATH']}"),
            )
            assert done.returncode == 0, done.stderr
            assert (tmp_path / name / "su").read_text() == expected, (
                name,
                (tmp_path / name / "su").read_text(),
            )
            assert (
                tmp_path / name / "limits.d" / "90-nproc.conf"
            ).read_text() == "dev soft nproc 16384\ndev hard nproc 16384\n"
    # The set-up's own line, run as the image's /bin/sh (dash) runs it, with a stand-in su that runs its command under
    # the shell it names as this user (the image's /bin/sh is dash, whose ulimit has no -u: v11b's re-check found the
    # first form, `-s /bin/sh`, wrote nothing), then the whole sweep: the limit's line must reach sweep_log as its first
    # line, the one line the baselines' criterion under the README's Remaining work expects.
    setup = (TASK / "environment" / "start-stockwell").read_text()
    line = next(
        text for text in setup.splitlines() if "/var/lib/fsmaint/user-limit" in text
    )
    assert line.startswith(
        "timeout 10 su dev -s /bin/bash -c 'ulimit -Hu' > /var/lib/fsmaint/user-limit"
    ), line
    tools = tmp_path / "setup-bin"
    tools.mkdir()
    (tools / "su").write_text(
        f'#!/bin/sh\nshift\n[ "$1" = -s ] && [ "$3" = -c ] || exit 1\nshell=$2\n[ "$shell" = /bin/sh ] && shell={shlex.quote(HOOK_SHELL)}\n'
        'exec "$shell" -c "$4"\n'
    )
    (tools / "su").chmod(0o755)
    if not shutil.which("timeout"):
        (tools / "timeout").write_text('#!/bin/sh\nshift\nexec "$@"\n')
        (tools / "timeout").chmod(0o755)

    def build(base: Path, server: Path) -> None:
        sweep_tree(base, server)
        done = subprocess.run(
            [
                HOOK_SHELL,
                "-c",
                line.replace(
                    "/var/lib/fsmaint/user-limit",
                    shlex.quote(str(base / "state" / "user-limit")),
                ),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env=dict(os.environ, PATH=f"{tools}:{os.environ['PATH']}"),
        )
        assert done.returncode == 0, done.stderr

    done, server, _ = sweep_under_the_shell(tmp_path / "sweep", build=build)
    assert done.returncode == 0 and done.stderr == "", (done.returncode, done.stderr)
    recorded = (tmp_path / "sweep" / "state" / "user-limit").read_text().strip()
    assert re.fullmatch(r"\d+|unlimited", recorded), (
        f"a su session's hard process limit, as bash prints it: {recorded!r}"
    )
    whole = verify_main(
        tmp_path / "sweep", copied(server, tmp_path / "sweep" / "arrived" / "server")
    )
    assert whole["metrics"]["sweep_log"] == [
        f"sweep: a su session of the user had a process limit of {recorded}"
    ], whole["metrics"]


LATE_WRITER = r"""
import http.server, os, sys, threading, time, urllib.request
from pathlib import Path
server, outside = Path(sys.argv[1]), Path(sys.argv[2])
answers = outside / "served"
answers.mkdir(parents=True)
(answers / "answer.bin").write_bytes(b"fetched once the work was over\n" * 100)
handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(*args, directory=str(answers), **kwargs)
http.server.SimpleHTTPRequestHandler.log_message = lambda *args: None
host = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
threading.Thread(target=host.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{host.server_address[1]}/answer.bin"
(outside / "fetched").mkdir()
(server / "late-link").symlink_to("run")
written = 0
while True:  # it fetches and writes until it is ended; whole files arrive by a rename, so an end mid-write leaves none half done
    fetched = urllib.request.urlopen(url, timeout=10).read()
    for name, place in (("fetched.part", server / "fetched.bin"), ("answer.part", outside / "fetched" / "answer.bin")):
        (outside / name).write_bytes(fetched)
        os.replace(outside / name, place)
    with open(server / "late.txt", "a") as late:
        late.write(f"written once the work was over, {written}\n")
    with open(server / "app" / "main.py", "a") as main:
        main.write(f"# changed once the work was over, {written}\n")
    written += 1
    if written == 3:
        (outside / "ready").write_text("")
    time.sleep(0.02)
"""


def test_a_capped_session_keeps_and_records_what_it_writes_and_fetches_after_its_end(
    tmp_path,
):
    """Round 15, the judges' third decision on the timer (2026-11-24): no task-side timer ends the session. When a
    session reaches its 34,560 s the platform stops waiting for it but leaves the agent's commands running, with the
    network back once the session is over (harbor-lh ops/swe-marathon-v2/PLATFORM_EGRESS_WINDOW.md), until the collect
    hook ends them. The work's end is its start, recorded at set-up, plus 34,560 s, and a file or a link of /app/server
    that changed after the end and before the hook had ended the user's processes was changed or made once the work was
    over. By the decision's amendment for back office (option A, as settled after re-check M2: claude-code saves every
    edit as a new file, so refusing new files would remove its last edits; Stockwell's code is private, so the network
    has nothing of it to fetch, and the per-trial egress audit is the backstop), each is kept, with a note of its path
    and times and a count in `sweep_log`; a link out to something written after the end is copied in like any other.

    Here the recorded start puts the end just after the tree was built. A detached process then fetches a file over
    HTTP from a server on this machine and writes it into the tree and outside it, appends to a file of the tree and
    adds a link, over and over, and is still doing so when the sweep starts; the sweep stops it and its own loop ends
    it (stand-ins for pgrep and setpriv that see, stop and end this one process), which must come before the fence, or
    its last writes would count. A session that ended before its limit has no end yet and keeps what it wrote (a second run, its start
    recorded just now). The sweep's 34,560 s is the agent's time limit in task.toml."""
    limit = tomllib.loads((TASK / "task.toml").read_text())["agent"]["timeout_sec"]
    sweep = (TASK / "environment" / "fsmaint-sweep").read_text()
    assert (
        f"st_mtime + {limit})'" in sweep and f"\nSESSION_SECONDS = {limit}  #" in sweep
    ), limit

    def run(base: Path, started_ago: float) -> tuple[subprocess.CompletedProcess, Path]:
        pid_file = base / "writer.pid"

        def build(base: Path, server: Path) -> None:
            sweep_tree(base, server)
            (server / "fetched-link").symlink_to(
                base / "outside" / "fetched" / "answer.bin"
            )  # in time, filled late
            time.sleep(0.3)
            started = base / "state" / "work-started"
            started.write_text("set-up\n")
            moment = time.time() - started_ago
            os.utime(started, (moment, moment))
            time.sleep(0.2)
            launched = subprocess.run(
                [
                    HOOK_SHELL,
                    "-c",
                    f'{shlex.quote(sys.executable)} -I -c "$1" "$2" "$3" >/dev/null 2>&1 </dev/null & echo $!',
                    "sh",
                    LATE_WRITER,
                    str(server),
                    str(base / "outside"),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            pid_file.write_text(launched.stdout.strip())
            assert until(lambda: (base / "outside" / "ready").exists(), 30), (
                "the writer fetched and wrote three times"
            )

        alive = (
            f'pid=$(cat {shlex.quote(str(pid_file))}); state=$(ps -o stat= -p "$pid" 2>/dev/null)\n'
            'case $state in ""|Z*) exit 1 ;; esac\nexit 0\n'
        )
        stand_ins = {
            "pgrep": f'#!/bin/sh\ncase " $* " in *" -u dev "*) {alive} ;; esac\nexec {shlex.quote(shutil.which("pgrep"))} "$@"\n',
            "setpriv": '#!/bin/sh\nwhile [ $# -gt 0 ]; do case "$1" in --reuid|--regid) shift 2 ;; --*) shift ;; *) break ;; esac; done\n'
            f'if [ "$1" = kill ]; then kill "$2" "$(cat {shlex.quote(str(pid_file))})" 2>/dev/null; '
            f'[ "$2" = -9 ] && : > {shlex.quote(str(base / "ended"))}; exit 0; fi\n'
            'exec "$@"\n',
        }
        try:
            done, server, _ = sweep_under_the_shell(
                base, build=build, stand_ins=stand_ins
            )
        finally:
            if pid_file.exists() and pid_file.read_text().strip().isdigit():
                try:
                    os.kill(int(pid_file.read_text()), signal.SIGKILL)
                except ProcessLookupError:
                    pass
        assert done.returncode == 0 and done.stderr == "", (
            done.returncode,
            done.stderr,
        )
        assert (base / "ended").exists(), (
            "the writer was still running when the sweep started, and the sweep ended it"
        )
        return done, server

    capped = tmp_path / "capped"
    done, server = run(capped, limit + 0.15)
    lines = manifest_lines(server)
    # sweep_tree's seven entries, late.txt, late-link, fetched.bin and fetched-link (a copy of the file fetched outside)
    sizes = sum(
        (server / name).stat().st_size
        for name in ("app/main.py", "late.txt", "fetched.bin", "fetched-link")
    )
    assert lines[0] == f"complete 11 {35 + 1000 + sizes}", lines
    assert sorted(os.listdir(server)) == [
        ".fsmaint-manifest",
        "app",
        "empty",
        "fetched-link",
        "fetched.bin",
        "inside",
        "late-link",
        "late.txt",
        "run",
        "run-again",
        "venv-python",
    ], sorted(os.listdir(server))
    assert (
        (server / "fetched-link").read_bytes()
        == (server / "fetched.bin").read_bytes()
        == b"fetched once the work was over\n" * 100
    )
    kept = {line.split(":")[0]: line for line in lines if line.startswith("kept ")}
    assert sorted(kept) == [
        "kept app/main.py",
        "kept fetched.bin",
        "kept late-link",
        "kept late.txt",
    ], lines
    assert kept["kept late-link"].startswith(
        "kept late-link: a link changed or made after the work's end (changed +"
    ), kept
    assert all(
        ", made " in line and "changed or made after the work's end" in line
        for line in kept.values()
    ), kept
    assert (
        not [line for line in lines if line.startswith("removed ")]
        and lines[-1]
        == "sweep: 4 files and links changed or made after the work's end were kept"
    ), lines
    whole = verify_main(capped, copied(server, capped / "arrived" / "server"))
    assert whole["code"] == 0 and whole["metrics"]["sweep_log"] == lines[-1:], whole[
        "metrics"
    ]
    assert any(
        note.startswith(
            "collect hook: kept late.txt: a file changed or made after the work's end ("
        )
        for note in whole["metrics"]["notes"]
    ), whole["metrics"]["notes"]

    # a session that ended before its limit: its end is still to come, so nothing goes for it
    done, server = run(tmp_path / "early", 0)
    assert {"late.txt", "late-link", "fetched.bin", "fetched-link"} <= set(
        os.listdir(server)
    ), sorted(os.listdir(server))
    assert (
        not (server / "fetched-link").is_symlink()
        and (server / "fetched-link").read_bytes()
        == (server / "fetched.bin").read_bytes()
    )
    assert "changed once the work was over" in (server / "app" / "main.py").read_text()
    assert not [
        line
        for line in manifest_lines(server) + done.stdout.splitlines()
        if "after the work's end" in line
    ], manifest_lines(server)


def test_an_honest_capped_tree_with_hard_links_loses_no_name(tmp_path):
    """Round 15, after Carve's re-check: a sweep that moves, renames or removes a name before it judges lateness by
    change time moves that file's change time past the work's end, so another name of the same file reads as written
    after the end (an honest Carve tree lost two names that way). Here the sweep changes nothing in the tree before its
    fence, and nothing it changes after the fence is judged. An honest tree of a session that reached its limit, with
    a file named at the top and deep down, a link with a second name that the fixer replaces by a copy under each name
    in turn (replacing the first moves the second's change time), a file hard-linked to a cache outside the tree (as
    uv links a package), a link made relative and one replaced by a copy, loses no name to the rule and gets no note
    about the work's end."""

    def build(base: Path, server: Path) -> None:
        sweep_tree(base, server)
        (server / "a" / "b" / "c").mkdir(parents=True)
        (server / "data.json").write_text('{"ok": true}\n')
        os.link(server / "data.json", server / "a" / "b" / "c" / "data.json")
        os.link(
            server / "venv-python", server / "a" / "python-again", follow_symlinks=False
        )  # the link itself, twice named
        (base / "outside" / "cache").mkdir()
        (base / "outside" / "cache" / "module.py").write_text("VALUE = 1\n")
        os.link(base / "outside" / "cache" / "module.py", server / "a" / "module.py")
        assert (
            os.lstat(server / "a" / "python-again").st_ino
            == os.lstat(server / "venv-python").st_ino
        )
        time.sleep(0.3)
        started = base / "state" / "work-started"
        started.write_text("set-up\n")
        moment = (
            time.time() - 34560 - 0.15
        )  # the session reached its limit: the end was 0.15 s ago, after all of this
        os.utime(started, (moment, moment))
        time.sleep(0.2)

    done, server, _ = sweep_under_the_shell(tmp_path / "honest", build=build)
    assert done.returncode == 0 and done.stderr == "", (done.returncode, done.stderr)
    lines = manifest_lines(server)
    assert not [
        line
        for line in lines + done.stdout.splitlines()
        if "after the work's end" in line
    ], (lines, done.stdout)
    # app, app/main.py, empty, inside, run, run-again, venv-python, a, a/b, a/b/c, a/b/c/data.json, data.json,
    # a/python-again and a/module.py; main.py 600, run 35 and data.json 13 once each, the two copies 1,000 each, module.py 10
    assert lines == ["complete 14 2658"], lines
    kept = sorted(path.relative_to(server).as_posix() for path in server.rglob("*"))
    assert kept == [
        ".fsmaint-manifest",
        "a",
        "a/b",
        "a/b/c",
        "a/b/c/data.json",
        "a/module.py",
        "a/python-again",
        "app",
        "app/main.py",
        "data.json",
        "empty",
        "inside",
        "run",
        "run-again",
        "venv-python",
    ], kept
    assert (
        os.stat(server / "data.json").st_ino
        == os.stat(server / "a" / "b" / "c" / "data.json").st_ino
    )
    assert (
        (server / "a" / "python-again").read_text()
        == (server / "venv-python").read_text()
        == "x" * 1000
    )
    assert (
        not (server / "a" / "python-again").is_symlink()
        and not (server / "venv-python").is_symlink()
    )


def stand_in_process(
    proc: Path,
    pid: int,
    user: str,
    maps: list[tuple[str, Path | str]],
    fds: list[tuple[str, Path]],
    threads: dict[int, list[tuple[str, Path]]] | None = None,
) -> None:
    """A process as /proc shows it: its ids, its mappings (permissions and path), its open files (fdinfo flags, in octal,
    and path), and under task/ its threads: the first with the process's own files, others (`threads`) with open files
    of their own, as a thread made without sharing its parent's file table has."""

    def task(folder: Path, files: list[tuple[str, Path]]) -> None:
        (folder / "fd").mkdir(parents=True)
        (folder / "fdinfo").mkdir()
        (folder / "maps").write_text(
            "".join(
                f"7f{index:010x}000-7f{index:010x}fff {perms} 00000000 08:01 {1000 + index}"
                f"                     {target}\n"
                for index, (perms, target) in enumerate(maps)
            )
        )
        for number, (flags, target) in enumerate(files, start=3):
            (folder / "fd" / str(number)).symlink_to(target)
            (folder / "fdinfo" / str(number)).write_text(
                f"pos:\t0\nflags:\t{flags}\nmnt_id:\t21\n"
            )

    folder = proc / str(pid)
    task(folder, fds)
    (folder / "status").write_text(
        f"Name:\tworker\nState:\tT (stopped)\nUid:\t{user}\t{user}\t{user}\t{user}\n"
    )
    task(folder / "task" / str(pid), fds)
    for tid, files in (threads or {}).items():
        task(folder / "task" / str(tid), files)


def test_files_a_stopped_process_could_still_write_after_the_end_are_recorded(tmp_path):
    """BasedPL's re-check R1 (round 15): with no timer, a capped turn's processes run on until the collect hook, and a
    file one of them maps shared and writable, or holds open for writing, from before the end can be written after it
    without its change time moving (a write through a mapping of a file kept in memory never moves it). The hook stops
    the user's processes and, as the user, lists those files from /proc before it ends them, reading every thread
    (R1a: a thread may hold files of its own, which /proc/PID/fd does not show). By the round's amendment (option A)
    the list is a record: once the end has passed, each name of such a file gets a note and stays, `sweep_log` counts
    them, and a list that cannot be made, or a process that cannot be read, is a line there, not a refusal. A process of
    another user, a private or a read-only mapping and a file open for reading count for nothing, and before the end
    nothing is listed. A stand-in /proc describes the processes here (macOS has none)."""

    def build(
        base: Path,
        server: Path,
        started_ago: float,
        proc_is_a_file: bool = False,
        undumpable: bool = False,
    ) -> None:
        sweep_tree(base, server)
        for name in (
            "mapped.bin",
            "written.log",
            "read.txt",
            "private.bin",
            "shared-read.bin",
            "theirs.bin",
            "thread.log",
        ):
            (server / name).write_text(f"{name}\n")
        (server / "deep").mkdir()
        os.link(server / "mapped.bin", server / "deep" / "mapped-again.bin")
        (base / "outside" / "held.bin").write_text("an answer\n")
        (server / "held-link").symlink_to(base / "outside" / "held.bin")
        if proc_is_a_file:
            (base / "proc").rmdir()
            (base / "proc").write_text("")
        else:
            stand_in_process(
                base / "proc",
                101,
                "4242",
                [
                    ("rw-s", server / "mapped.bin"),
                    ("rw-p", server / "private.bin"),
                    ("r--s", server / "shared-read.bin"),
                    ("rw-s", base / "outside" / "held.bin"),
                    ("r-xp", "/usr/lib/libc.so.6"),
                    ("rw-p", "[heap]"),
                ],
                [("0100001", server / "written.log"), ("0100000", server / "read.txt")],
                threads={105: [("0100002", server / "thread.log")]},
            )
            stand_in_process(
                base / "proc",
                202,
                "5555",
                [("rw-s", server / "theirs.bin")],
                [("0100002", server / "theirs.bin")],
            )
            if undumpable:  # a process of the user that made itself undumpable: its maps cannot be read
                stand_in_process(
                    base / "proc", 303, "4242", [("rw-s", server / "read.txt")], []
                )
                (base / "proc" / "303" / "maps").chmod(0)
        time.sleep(0.3)
        started = base / "state" / "work-started"
        started.write_text("set-up\n")
        moment = time.time() - started_ago
        os.utime(started, (moment, moment))
        time.sleep(0.2)

    everything = [
        ".fsmaint-manifest",
        "app",
        "deep",
        "empty",
        "held-link",
        "inside",
        "mapped.bin",
        "private.bin",
        "read.txt",
        "run",
        "run-again",
        "shared-read.bin",
        "theirs.bin",
        "thread.log",
        "venv-python",
        "written.log",
    ]
    capped = tmp_path / "capped"
    done, server, _ = sweep_under_the_shell(
        capped, build=lambda base, server: build(base, server, 34560 + 0.15)
    )
    assert done.returncode == 0 and done.stderr == "", (done.returncode, done.stderr)
    lines = manifest_lines(server)
    why = "a process of the user could still write it after the work's end (open for writing or mapped writable)"
    assert sorted(line for line in lines if line.endswith(why)) == [
        f"held {name}: {why}"
        for name in ("deep/mapped-again.bin", "mapped.bin", "thread.log", "written.log")
    ], lines
    assert (
        lines[-1]
        == "sweep: 4 files were open for writing or mapped writable when the user's processes were stopped after the work's end"
    ), lines
    assert sorted(os.listdir(server)) == everything and os.listdir(server / "deep") == [
        "mapped-again.bin"
    ], sorted(os.listdir(server))
    assert (server / "held-link").read_text() == "an answer\n" and not (
        server / "held-link"
    ).is_symlink(), "a held file outside is copied in"
    # sweep_tree's seven entries and the eight files and the folder added, the held file outside copied in
    assert lines[0] == "complete 17 1727", lines
    whole = verify_main(capped, copied(server, capped / "arrived" / "server"))
    assert whole["code"] == 0 and whole["metrics"]["sweep_log"] == lines[-1:], whole[
        "metrics"
    ]
    # before the end nothing is listed, whatever is held
    done, server, _ = sweep_under_the_shell(
        tmp_path / "early", build=lambda base, server: build(base, server, 0)
    )
    assert done.returncode == 0 and done.stderr == "", (done.returncode, done.stderr)
    assert (
        tmp_path / "early" / "state" / "held"
    ).read_text() == "before-end\n" and sorted(os.listdir(server)) == everything
    assert not [
        line
        for line in manifest_lines(server) + done.stdout.splitlines()
        if "after the work's end" in line
    ], manifest_lines(server)
    # once the end has passed, a list that cannot be made, or a process that cannot be read, is said and refuses nothing
    for name, kind, said in (
        (
            "unlisted",
            {"proc_is_a_file": True},
            "sweep: the files that processes of the user held for writing after the work's end could not be listed",
        ),
        (
            "undumpable",
            {"undumpable": True},
            "sweep: 1 processes of the user could not be read for the files they held after the work's end",
        ),
    ):
        done, server, _ = sweep_under_the_shell(
            tmp_path / name,
            build=lambda base, server, kind=kind: build(
                base, server, 34560 + 0.15, **kind
            ),
        )
        assert done.returncode == 0 and done.stderr == "", (
            name,
            done.returncode,
            done.stderr,
        )
        lines = manifest_lines(server)
        assert (
            lines[0].startswith("complete ")
            and said in lines
            and sorted(os.listdir(server)) == everything
        ), (name, lines)


def capped_tree(base: Path, server: Path, after_the_end) -> None:
    """sweep_tree, then the work's start recorded so that its end fell 0.15 s ago, then `after_the_end(base, server)`."""
    sweep_tree(base, server)
    (server / "app" / "util.py").write_text("HELPER = 1\n")
    time.sleep(0.3)
    started = base / "state" / "work-started"
    started.write_text("set-up\n")
    moment = time.time() - 34560 - 0.15
    os.utime(started, (moment, moment))
    time.sleep(0.2)
    after_the_end(base, server)


def test_a_core_module_replaced_after_the_end_by_write_and_rename_arrives_and_is_graded(
    tmp_path,
):
    """Round 15's amendment (option A for back office, as settled after re-check M2): harbor does not end the agent at
    its limit, and claude-code works on until the collect hook stops it, 5-14 s later. claude-code saves every edit by
    writing the whole file under a temporary name in the same folder (`.tmp.PID.HEX`) and renaming it into place, so an
    edit after the end is a new file; refusing new files brought M2 back wherever birth times are kept. Here a capped
    turn replaces the server's main module that way after the end and makes its start script executable once more:
    both arrive, the verifier grades the tree with the new module, and the manifest and `sweep_log` record the changes
    with their times."""
    edited = "print('written again once the work was over')\n" * 20

    def after_the_end(base: Path, server: Path) -> None:
        staged = server / "app" / ".tmp.4242.0123456789ab"
        staged.write_text(edited)
        os.replace(staged, server / "app" / "main.py")
        (server / "run").chmod(0o755)

    done, server, _ = sweep_under_the_shell(
        tmp_path / "capped",
        build=lambda base, server: capped_tree(base, server, after_the_end),
    )
    assert done.returncode == 0 and done.stderr == "", (done.returncode, done.stderr)
    lines = manifest_lines(server)
    assert (server / "app" / "main.py").read_text() == edited and os.access(
        server / "run", os.X_OK
    )
    # app, app/main.py, app/util.py, empty, inside, run, run-again, venv-python
    assert lines[0] == f"complete 8 {len(edited) + 11 + 35 + 1000}", lines
    kept = sorted(
        line.split(":")[0]
        for line in lines
        if line.startswith("kept ")
        and ": a file changed or made after the work's end (changed +" in line
    )
    assert kept == ["kept app/main.py", "kept run", "kept run-again"], lines
    assert not [line for line in lines if line.startswith("removed ")], lines
    assert (
        lines[-1]
        == "sweep: 3 files and links changed or made after the work's end were kept"
    ), lines
    whole = verify_main(
        tmp_path / "capped", copied(server, tmp_path / "capped" / "arrived" / "server")
    )
    assert (
        whole["code"] == 0
        and whole["reward"] == "1.000000"
        and whole["metrics"]["status"] == "completed"
    ), whole
    assert (Path(whole["evaluate"][0]) / "app" / "main.py").read_text() == edited, (
        "the replaced module is what was graded"
    )
    assert whole["metrics"]["sweep_log"] == lines[-1:] and any(
        note.startswith("collect hook: kept app/main.py: a file changed or made after")
        for note in whole["metrics"]["notes"]
    ), whole["metrics"]


def test_a_brand_new_file_made_after_the_end_is_kept_and_noted(tmp_path):
    """Round 15's amendment (option A for back office, as settled): nothing is refused for being late. A brand-new module,
    a new link to it and a module replaced by a file renamed into place, all made after the end, arrive, each with a note
    of its path and times (its birth after the end, where the file system keeps birth times), beside a file changed in
    place, which is noted too. Only the copy's own rules remove anything, as before."""

    def after_the_end(base: Path, server: Path) -> None:
        (server / "app" / "answer.py").write_text("ANSWER = 42\n")
        (server / "app" / "answer-link").symlink_to("answer.py")
        (server / "app" / ".tmp.4242.0123456789ab").write_text("HELPER = 2\n")
        os.replace(
            server / "app" / ".tmp.4242.0123456789ab", server / "app" / "util.py"
        )
        with open(server / "app" / "main.py", "a") as main:
            main.write("# changed in place once the work was over\n")

    done, server, _ = sweep_under_the_shell(
        tmp_path / "capped",
        build=lambda base, server: capped_tree(base, server, after_the_end),
    )
    assert done.returncode == 0 and done.stderr == "", (done.returncode, done.stderr)
    lines = manifest_lines(server)
    assert sorted(os.listdir(server / "app")) == [
        "answer-link",
        "answer.py",
        "main.py",
        "util.py",
    ], sorted(os.listdir(server / "app"))
    assert (
        server / "app" / "answer.py"
    ).read_text() == "ANSWER = 42\n" and os.readlink(
        server / "app" / "answer-link"
    ) == "answer.py"
    assert (server / "app" / "util.py").read_text() == "HELPER = 2\n"
    kept = {line.split(":")[0]: line for line in lines if line.startswith("kept ")}
    assert sorted(kept) == [
        "kept app/answer-link",
        "kept app/answer.py",
        "kept app/main.py",
        "kept app/util.py",
    ], lines
    for name in ("answer.py", "util.py"):  # born after the end: the note says so
        made = float(kept[f"kept app/{name}"].rsplit("made ", 1)[1].split(" s")[0])
        assert made > 0, kept[f"kept app/{name}"]
    assert float(kept["kept app/main.py"].rsplit("made ", 1)[1].split(" s")[0]) < 0, (
        kept["kept app/main.py"]
    )
    assert not [line for line in lines if line.startswith("removed ")], lines
    assert (
        lines[-1]
        == "sweep: 4 files and links changed or made after the work's end were kept"
    ), lines


def test_every_name_of_a_file_made_after_the_end_is_kept_and_recorded(tmp_path):
    """Round 15: a file made after the end with three names in three folders. Since the amendment nothing is removed for
    being late, and the record holds each name: all three arrive, each with a note."""

    def build(base: Path, server: Path) -> None:
        sweep_tree(base, server)
        time.sleep(0.3)
        started = base / "state" / "work-started"
        started.write_text("set-up\n")
        moment = time.time() - 34560 - 0.15
        os.utime(started, (moment, moment))
        time.sleep(0.2)
        for folder in ("a", "b", "c"):
            (server / folder).mkdir()
        (server / "a" / "answer.txt").write_text("written once the work was over\n")
        os.link(server / "a" / "answer.txt", server / "b" / "answer.txt")
        os.link(server / "a" / "answer.txt", server / "c" / "answer.txt")

    done, server, _ = sweep_under_the_shell(tmp_path / "one", build=build)
    assert done.returncode == 0 and done.stderr == "", (done.returncode, done.stderr)
    lines = manifest_lines(server)
    late = sorted(
        line.split(":")[0]
        for line in lines
        if line.startswith("kept ")
        and "a file changed or made after the work's end (" in line
    )
    assert late == [f"kept {folder}/answer.txt" for folder in "abc"], lines
    assert all(
        (server / folder / "answer.txt").read_text()
        == "written once the work was over\n"
        for folder in "abc"
    ), lines
    # app, app/main.py, empty, inside, run, run-again, venv-python, the folders a, b and c and the three names
    assert (
        lines[0]
        == f"complete 13 {1635 + len('written once the work was over' + chr(10))}"
    ), lines
    assert (
        lines[-1]
        == "sweep: 3 files and links changed or made after the work's end were kept"
    ), lines


def test_what_the_user_left_in_the_artifacts_folder_is_set_aside_before_the_copy(
    tmp_path,
):
    """Carve's re-check, which holds here too: harbor 0.20 makes /logs/artifacts in the agent's machine world-writable
    (`mkdir -p ... && chmod 777`), collects it first, before /app/server, and uploads it into the verifier's machine with
    nothing that catches a failure, so an agent that filled it could make the trial an evaluation error. The sweep moves
    what it holds aside by one rename (never following or copying anything) and leaves an empty directory, 0777 as
    harbor made it; where the rename cannot be made (a mount point, another file system) it removes what the directory
    holds. A line in sweep_log says which."""

    def build(base: Path, server: Path) -> None:
        sweep_tree(base, server)
        artifacts = (
            base / "agent-logs" / "artifacts"
        )  # base / "logs" is the verifier's own folder in verify_main
        (artifacts / "deep" / "er").mkdir(parents=True)
        (artifacts / "big.bin").write_bytes(b"x" * 100_000)
        (artifacts / "deep" / "er" / "f").write_text("y")
        os.mkfifo(artifacts / "pipe")
        (artifacts / "away").symlink_to("/etc/hosts")

    for name, stand_ins, how in (
        ("moved", None, "moved aside"),
        ("removed", {"mktemp": "#!/bin/sh\nexit 1\n"}, "removed"),
    ):
        base = tmp_path / name
        done, server, _ = sweep_under_the_shell(base, build=build, stand_ins=stand_ins)
        assert done.returncode == 0 and done.stderr == "", (
            name,
            done.returncode,
            done.stderr,
        )
        artifacts = base / "agent-logs" / "artifacts"
        assert (
            artifacts.is_dir()
            and not artifacts.is_symlink()
            and os.listdir(artifacts) == []
        ), (name, sorted(os.listdir(artifacts)))
        kept = [
            path
            for path in (base / "state").iterdir()
            if path.name.startswith("artifacts.")
        ]
        if how == "moved aside":
            assert artifacts.stat().st_mode & 0o777 == 0o777 and len(kept) == 1, (
                oct(artifacts.stat().st_mode),
                kept,
            )
            assert sorted(os.listdir(kept[0] / "artifacts")) == [
                "away",
                "big.bin",
                "deep",
                "pipe",
            ], "moved whole, nothing followed"
        else:
            assert kept == []
        lines = manifest_lines(server)
        assert lines[0] == "complete 7 1635", (name, lines)
        assert lines[-1].startswith("sweep: what the user left in ") and lines[
            -1
        ].endswith(f"/agent-logs/artifacts was {how}"), (name, lines)
        whole = verify_main(base, copied(server, base / "arrived" / "server"))
        assert whole["code"] == 0 and whole["metrics"]["sweep_log"][-1].endswith(
            f"/agent-logs/artifacts was {how}"
        ), (name, whole["metrics"])
    # nothing is done, and nothing said, where the folder is empty: the baselines' sweep_log keeps its one line
    done, server, _ = sweep_under_the_shell(
        tmp_path / "empty",
        build=lambda base, server: (
            sweep_tree(base, server),
            (base / "agent-logs" / "artifacts").mkdir(parents=True),
        ),
    )
    assert done.returncode == 0 and not any(
        "artifacts" in line for line in manifest_lines(server)
    ), manifest_lines(server)


def test_a_read_cut_at_its_end_is_a_timeout_and_a_disk_the_server_cannot_write_is_not_watched(
    tmp_path,
):
    """QA 07e N-a: when the watcher's shutdown landed just after a read's end, the read returned the end of the stream, so
    an answer with no length was taken as complete (5 of 300 dripping health checks passed). A read that returns nothing
    at or after its end is now a timeout. QA 07e S-d: a disk only the grader writes (a host's bind mount for
    /logs/verifier) cannot be the server's doing, so it is not watched."""
    probe = r"""
import io, json, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from verifier import replay


class Answer(io.RawIOBase):  # a reply with no length; the watcher's shutdown lands just after the read's end
    calls = 0

    def readable(self):
        return True

    def readinto(self, buffer):
        self.calls += 1
        if self.calls == 1:
            buffer[:25] = b"HTTP/1.0 200 OK" + bytes(10)
            return 25
        time.sleep(0.4)
        return 0  # what a socket returns once it is shut down


class Socket:
    def gettimeout(self):
        return 30.0

    def settimeout(self, value):
        pass


stream = replay.Bounded(Answer(), 1 << 20, Socket(), time.monotonic() + 0.2)
got, outcome = bytearray(), "end of stream"
try:
    while True:
        buffer = bytearray(4096)
        count = stream.readinto(buffer)
        if not count:
            break
        got += buffer[:count]
except TimeoutError:
    outcome = "timeout"


class Candidate:
    work, sandbox, halted, uid = Path(sys.argv[2]), False, None, -1


replay.SCRATCH = ()
guard = replay.Guard(Candidate(), [Path(sys.argv[2]), Path("/dev")], replay.MemoryMeter(None))
guard.stop()
print(json.dumps({"outcome": outcome, "got": len(got), "unwritable": guard.unwritable, "watched": [str(path) for path in guard.paths]}))
"""
    done = subprocess.run(
        [sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests"), str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr[-3000:]
    out = json.loads(done.stdout.strip().splitlines()[-1])
    assert out["outcome"] == "timeout" and out["got"] == 25, out
    assert out["unwritable"] == ["/dev"] and out["watched"] == [str(tmp_path)], out


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
    done = subprocess.run(
        [sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests"), str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    out = json.loads(done.stdout)
    assert out["before"] == [True, True, True] and out["count"] == 2
    assert out["after"][:2] == [0o755, 0o755] and out["after"][2] & 0o4000, (
        "only files inside the submission are changed"
    )
    assert (
        "setpriv" in out["sandbox"]
        and "--no-new-privs" in out["sandbox"]
        and out["sandbox"][out["sandbox"].index("--reuid") + 1] == "nobody"
    )
    assert out["dropped"] == [True, False, False, False, False, False, True, False], (
        "no_new_privs counts from the status file or prctl; with neither it fails closed"
    )


def test_the_reward_is_written_before_the_diagnostics_and_survives_their_failure(
    tmp_path,
):
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
    done = subprocess.run(
        [sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests"), str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    out = json.loads(done.stdout.strip().splitlines()[-1])
    assert out == {
        "scenario_results.json": ["metrics.json", "reward.txt"],
        "scenario_results.json reward": "0.250000",
        "metrics.json": ["reward.txt", "scenario_results.json"],
        "metrics.json reward": "0.250000",
    }


def test_the_replay_ends_well_inside_the_step_time_limit():
    """The replay's own deadline leaves room to load the scenarios, cut the last requests and wind down (about two
    minutes, QA 07d N6) before verify.py's hard stop, which leaves Harbor six minutes to upload the tests before and
    collect the results after."""
    config = tomllib.loads((TASK / "task.toml").read_text())
    limits = [config["verifier"]["timeout_sec"]]
    probe = (
        "import json, sys; sys.path.insert(0, sys.argv[1]); import verify; from verifier import replay as r; "
        "print(json.dumps([r.DEADLINE_SEC, r.START_SEC, r.REQUEST_SEC, r.HEALTH_SEC, verify.HARD_STOP_SEC]))"
    )
    done = subprocess.run(
        [sys.executable, "-I", "-B", "-c", probe, str(STEP / "tests")],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    deadline, start, request, health, hard_stop = json.loads(done.stdout)
    assert (
        deadline + 240 <= hard_stop
        and hard_stop + 360 <= min(limits)
        and start + request + health < deadline
    )
