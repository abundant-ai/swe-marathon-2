"""Start the submitted server as an unprivileged user and replay recorded scenarios against it.

A scenario is a list of requests made in one fresh workspace, with the status and
the answer the reference server gave for each: a JSON body, or for a file its type,
length and SHA-256. A scenario counts when every one of
its answers is the same. The reward is the share of scenarios that count; the
total is fixed, so a server that does not start, dies or hangs loses the scenarios
it did not answer and nothing else.
"""

from __future__ import annotations

import gzip
import hashlib
import http.client
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

RUN_AS = "nobody"
START_SEC = 60
REQUEST_SEC = 15
RESTART_LIMIT = 25
WORKERS = 8
WORKSPACE_ID = re.compile(r"[A-Za-z0-9_]{1,40}")


class EvaluationError(Exception):
    """Evaluation could not be carried out; no valid reward may be published."""


class Candidate:
    """The submitted server process and the means to restart it."""

    def __init__(self, source: Path, work: Path, log_path: Path, sandbox: bool) -> None:
        self.source, self.work, self.log_path, self.sandbox = source, work, log_path, sandbox
        self.lock = threading.Lock()
        self.proc: subprocess.Popen[bytes] | None = None
        self.port = 0
        self.generation = 0
        self.restarts = 0

    def _free_port(self) -> int:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            return probe.getsockname()[1]

    def stop(self) -> None:
        if self.proc is not None:
            try:
                os.killpg(self.proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            self.proc.wait()
            self.proc = None

    def start(self) -> bool:
        """Start the server and wait for its health check; False if it does not come up."""
        self.stop()
        self.port = self._free_port()
        data = self.work / f"data{self.generation}"
        data.mkdir(parents=True, exist_ok=True)
        os.chmod(data, 0o777)
        prefix = ["setpriv", "--reuid", RUN_AS, "--regid", "nogroup", "--clear-groups"] if self.sandbox else []
        env = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/local/go/bin", "HOME": str(data),
               "PORT": str(self.port), "DATA_DIR": str(data), "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8",
               "PYTHONDONTWRITEBYTECODE": "1", "GOCACHE": str(data / "gocache"), "GOFLAGS": "-mod=mod"}
        with open(self.log_path, "ab") as log:
            log.write(f"\n==== start {self.generation} on port {self.port} ====\n".encode())
            log.flush()
            try:
                self.proc = subprocess.Popen(prefix + [str(self.source / "run")], cwd=self.source, env=env, stdout=log,
                                             stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
            except OSError:
                self.proc = None
                return False
        self.generation += 1
        deadline = time.time() + START_SEC
        while time.time() < deadline:
            if self.proc.poll() is not None:
                return False
            try:
                status, _ = request(self.port, "GET", "/api/health", {}, None, timeout=3)
                if status == 200:
                    return True
            except OSError:
                pass
            time.sleep(0.5)
        return False

    def snapshot(self) -> tuple[int, int, bool]:
        """Generation, port and whether a server is up, read while no restart is in progress."""
        with self.lock:
            return self.generation, self.port, self.proc is not None

    def revive(self, seen_generation: int) -> bool:
        """After a request got no answer: restart the server if it is really gone.

        A server that still answers its health check is left alone. Returns False
        once the restart limit is used up.
        """
        with self.lock:
            if self.generation != seen_generation:
                return self.proc is not None
            if self.proc is not None and self.proc.poll() is None:
                try:
                    if request(self.port, "GET", "/api/health", {}, None, timeout=5)[0] == 200:
                        return True
                except (OSError, http.client.HTTPException):
                    pass
            if self.restarts >= RESTART_LIMIT:
                self.stop()
                return False
            self.restarts += 1
            return self.start()


def exchange(connection: http.client.HTTPConnection, method: str, path: str, headers: dict[str, str], body: Any) -> tuple[int, Any]:
    """Send one request on an open connection and read the JSON answer."""
    payload = None if body is None else json.dumps(body).encode()
    sent = dict(headers)
    if payload is not None:
        sent["Content-Type"] = "application/json"
    connection.request(method, path, body=payload, headers=sent)
    response = connection.getresponse()
    raw = response.read(16_000_000)
    kind = (response.getheader("Content-Type") or "").split(";")[0].strip().lower()
    if kind != "application/json":
        # a file: it is compared by its type, its length and its SHA-256
        return response.status, {"binary": {"content_type": kind, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}}
    try:
        return response.status, json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return response.status, {"__not_json__": True}


def request(port: int, method: str, path: str, headers: dict[str, str], body: Any, timeout: float = REQUEST_SEC) -> tuple[int, Any]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        return exchange(connection, method, path, headers, body)
    finally:
        connection.close()


def normalise(value: Any, workspace: str) -> Any:
    """The answer with this workspace's id written as {ws}.

    Only a string that is exactly the id, and the `/ws/<id>` segment of a path, are rewritten;
    nothing else is touched, so any id the instruction allows (even "1" or "a") is safe.
    """
    if isinstance(value, str):
        if value == workspace:
            return "{ws}"
        if f"/ws/{workspace}" in value:
            return re.sub(rf"/ws/{re.escape(workspace)}(?=[/?#]|$)", "/ws/{ws}", value)
        return value
    if isinstance(value, list):
        return [normalise(item, workspace) for item in value]
    if isinstance(value, dict):
        return {key: normalise(item, workspace) for key, item in value.items()}
    return value


def encode_query(query: dict[str, str]) -> str:
    from urllib.parse import urlencode

    return ("?" + urlencode(query)) if query else ""


def play(candidate: Candidate, scenario: dict[str, Any]) -> dict[str, Any]:
    """Replay one scenario; returns whether every answer matched and where the first difference was."""
    for attempt in range(3):
        generation, port, running = candidate.snapshot()
        if not running:
            return {"id": scenario["id"], "matched": False, "failed_step": 0, "reason": "server not running"}
        # one connection for the whole scenario; a server that closes it is reconnected by http.client
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=REQUEST_SEC)
        try:
            status, created = exchange(connection, "POST", "/api/workspaces", {}, None)
            workspace = created.get("id") if isinstance(created, dict) else None
            if status != 201 or not isinstance(workspace, str) or not WORKSPACE_ID.fullmatch(workspace):
                return {"id": scenario["id"], "matched": False, "failed_step": 0, "reason": "could not create a workspace"}
            for index, step in enumerate(scenario["steps"], start=1):
                headers = {name: value for name, value in step["headers"].items()}
                status, answer = exchange(connection, step["method"], f"/api/ws/{workspace}{step['path']}{encode_query(step['query'])}",
                                          headers, step["body"])
                if status != step["status"]:
                    return {"id": scenario["id"], "matched": False, "failed_step": index, "reason": f"status {status}, expected {step['status']}"}
                normal = normalise(answer, workspace)
                expected = step["json"]
                if isinstance(expected, dict) and set(expected) == {"binary"}:
                    expected = {"binary": {key: value for key, value in expected["binary"].items() if key != "filename"}}
                if normal != expected:
                    return {"id": scenario["id"], "matched": False, "failed_step": index, "reason": "body differs"}
            return {"id": scenario["id"], "matched": True, "failed_step": None, "reason": None}
        except (OSError, http.client.HTTPException):
            if attempt < 2 and candidate.revive(generation):
                time.sleep(0.2 * (attempt + 1))
                continue
            return {"id": scenario["id"], "matched": False, "failed_step": -1, "reason": "no answer from the server"}
        finally:
            connection.close()
    return {"id": scenario["id"], "matched": False, "failed_step": -1, "reason": "no answer from the server"}


def evaluate(source: Path, scenario_path: Path, work: Path, output: Path, sandbox: bool = True) -> dict[str, Any]:
    """Grade the server in `source` against the scenarios in `scenario_path`.

    Args:
        source: The submitted /app/server directory.
        scenario_path: Private scenarios with the reference answers.
        work: Scratch directory.
        output: Directory for diagnostic files.
        sandbox: Run the server as the unprivileged user (off only in development checks).

    Returns:
        The reward and its breakdown.

    Raises:
        EvaluationError: The private scenarios are unreadable or privileges cannot be dropped.
    """
    try:
        raw = scenario_path.read_bytes()
        scenarios = json.loads(gzip.decompress(raw) if scenario_path.suffix == ".gz" else raw)["scenarios"]
    except (OSError, ValueError, KeyError) as exc:
        raise EvaluationError("Private scenarios are unreadable") from exc
    if not scenarios:
        raise EvaluationError("Private scenarios are empty")
    total = len(scenarios)
    themes = sorted({s["theme"] for s in scenarios})
    metrics: dict[str, Any] = {"scenarios_total": total, "scenarios_matched": 0, "reward": 0.0, "restarts": 0, "notes": [],
                               "by_theme": {t: {"total": sum(1 for s in scenarios if s["theme"] == t), "matched": 0} for t in themes}}
    if sandbox:
        if shutil.which("setpriv") is None or subprocess.run(
                ["setpriv", "--reuid", RUN_AS, "--regid", "nogroup", "--clear-groups", "true"], capture_output=True).returncode != 0:
            raise EvaluationError("Could not drop privileges; submitted code was not run")
    runner = source / "run"
    if not runner.is_file() or not os.access(runner, os.X_OK):
        metrics["notes"].append("/app/server/run is missing or not executable")
        return metrics
    work.mkdir(parents=True, exist_ok=True)
    os.chmod(work, 0o755)
    if sandbox:
        subprocess.run(["chmod", "-R", "a+rX", str(source)], check=False)
    candidate = Candidate(source, work, output / "server.log", sandbox)
    try:
        if not candidate.start():
            metrics["notes"].append("the server did not answer GET /api/health within 60 seconds")
            return metrics
        with ThreadPoolExecutor(WORKERS) as pool:
            results = list(pool.map(lambda s: play(candidate, s), scenarios))
    finally:
        candidate.stop()
    theme_of = {s["id"]: s["theme"] for s in scenarios}
    for result in results:
        if result["matched"]:
            metrics["scenarios_matched"] += 1
            metrics["by_theme"][theme_of[result["id"]]]["matched"] += 1
    metrics["restarts"] = candidate.restarts
    metrics["reward"] = round(metrics["scenarios_matched"] / total, 6)
    (output / "scenario_results.json").write_text(json.dumps(results))
    return metrics
