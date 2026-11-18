"""Start the submitted server as an unprivileged user and replay recorded scenarios against it.

A scenario is a list of requests made in one fresh workspace, with the status and
the answer the reference server gave for each: a JSON body, or for a file its type,
length and SHA-256. The reward is the share of units that match. A scenario is one
unit, or, for a month of trading, one unit per trading day and per client screen
opened after it; a unit matches when every one of its answers is the same. The
total is fixed, so a server that does not start, dies, hangs or is too slow loses
the units it did not answer and nothing else.

- Time: a request has REQUEST_SEC of wall clock and the whole replay DEADLINE_SEC;
  a request still running past either has its connection shut down. Scenarios not
  played to the end by the deadline count as not matched.
- Restarts: every scenario is played once, WORKERS at a time. One that got no
  answer (the server died, dropped the connection or ran out of time) is played
  once more on its own after the others, so a server that crashes now and then
  loses only the scenarios that crash it. A server that has died, or has left its
  health check unanswered for HEALTH_SEC, is restarted before the next attempt, as
  often as needed while the deadline holds; after START_FAILURES starts in a row
  that never answer it is given up. Every start uses the same DATA_DIR.
- Planned restarts: a scenario with a step marked `restart` runs alone, after the
  others. After that step the server is stopped (SIGTERM, or SIGKILL straight after
  the answer) and started again on the same DATA_DIR, and the scenario goes on in
  the same workspace: what a workspace holds must survive.
- Nothing the server sends makes the evaluation fail: a reply that is not HTTP,
  not JSON, too large or nested too deeply is an answer that matches nothing.
"""

from __future__ import annotations

import contextlib
import grp
import gzip
import hashlib
import http.client
import json
import os
import pwd
import re
import select
import shutil
import signal
import socket
import stat
import subprocess
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

RUN_AS, RUN_GROUP = "nobody", "nogroup"
# no_new_privs: executing a set-user-id or set-group-id file, or one with file capabilities, grants nothing
SANDBOX = ["setpriv", "--reuid", RUN_AS, "--regid", RUN_GROUP, "--clear-groups", "--no-new-privs"]
START_SEC = 60
REQUEST_SEC = 30  # wall clock for one request: a big upload or a 200-page PDF needs more than a JSON call
DEADLINE_SEC = 3000  # the whole replay; the step allows 3,600 s for everything
HEALTH_SEC = 30  # how long a live server may leave its health check unanswered before it is restarted
STOP_SEC = 30  # how long a server stopped with SIGTERM may take to exit before it is killed
START_FAILURES = 3  # starts in a row that never answer before the server is given up
WORKERS = 8
ANSWER_LIMIT = 16_000_000  # bytes read of one answer; the largest recorded file is about 3 MB
JSON_LIMIT = 4_000_000  # a longer JSON answer is not parsed; the longest recorded one is about 65 KB
WORKSPACE_ID = re.compile(r"[A-Za-z0-9_]{1,40}")
NOT_JSON, TOO_LARGE = {"__not_json__": True}, {"__too_large__": True}
LATE = "not played to the end before the time limit"
NO_ANSWER = "no answer from the server"
DOWN = "server not running"


class EvaluationError(Exception):
    """Evaluation could not be carried out; no valid reward may be published."""


class NoAnswer(Exception):
    """No complete reply came: the server died, dropped the connection, sent something that is not HTTP or ran out of time."""


class Clock:
    """The replay's time limits.

    A socket timeout starts again with every byte that arrives, so it cannot bound a request on its
    own: a watcher thread shuts down the socket of any request still running past its limit or past
    the deadline, which ends a read or a send that is waiting.
    """

    def __init__(self, seconds: float) -> None:
        self.deadline = time.monotonic() + seconds
        self.lock = threading.Lock()
        self.running: dict[int, tuple[http.client.HTTPConnection, float]] = {}
        self.done = threading.Event()
        self.watcher = threading.Thread(target=self._watch, daemon=True)
        self.watcher.start()

    def expired(self) -> bool:
        return time.monotonic() >= self.deadline

    @contextlib.contextmanager
    def limit(self, connection: http.client.HTTPConnection, seconds: float) -> Iterator[None]:
        """Bound what happens on `connection` inside this block by `seconds` and by the deadline."""
        with self.lock:
            self.running[id(connection)] = (connection, min(time.monotonic() + seconds, self.deadline))
        try:
            yield
        finally:
            with self.lock:
                self.running.pop(id(connection), None)

    def _watch(self) -> None:
        while not self.done.wait(0.2):
            now = time.monotonic()
            with self.lock:
                for connection, end in self.running.values():
                    sock = connection.sock
                    if now >= end and sock is not None:
                        with contextlib.suppress(OSError):
                            sock.shutdown(socket.SHUT_RDWR)

    def stop(self) -> None:
        self.done.set()
        self.watcher.join(timeout=5)


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def healthy(port: int, clock: Clock, seconds: float = 5) -> bool:
    """Whether the server answers GET /api/health with 200 in time; any other reply, or none, is no."""
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=seconds)
    try:
        with clock.limit(connection, seconds):
            connection.request("GET", "/api/health")
            response = connection.getresponse()
            response.read(1_000_000)
            return response.status == 200
    except Exception:  # noqa: BLE001 - whatever the server sends, it is not a healthy answer
        return False
    finally:
        connection.close()


class Candidate:
    """The submitted server process and the means to restart it."""

    def __init__(self, source: Path, work: Path, log_path: Path, sandbox: bool, clock: Clock) -> None:
        self.source, self.work, self.log_path, self.sandbox, self.clock = source, work, log_path, sandbox, clock
        self.data = work / "data"  # one DATA_DIR for every start, planned or after a crash: what a workspace holds must survive
        self.lock = threading.Lock()
        self.proc: subprocess.Popen[bytes] | None = None
        self.port = 0
        self.generation = 0
        self.restarts = 0
        self.planned = 0
        self.failed_starts = 0

    def stop(self) -> None:
        """Kill the server's process group and, when sandboxed, whatever else its user still runs."""
        if self.proc is None:
            return
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(self.proc.pid, signal.SIGKILL)
        if self.sandbox and shutil.which("pkill"):
            subprocess.run(["pkill", "-9", "-u", RUN_AS], check=False, capture_output=True)  # children that left the group
        with contextlib.suppress(subprocess.TimeoutExpired):
            self.proc.wait(timeout=10)
        self.proc = None

    def start(self) -> bool:
        """Start the server on the shared data directory and wait for its health check; False if it does not come up."""
        self.stop()
        self.generation += 1
        try:
            self.port = free_port()
            data = self.data
            data.mkdir(parents=True, exist_ok=True)
            os.chmod(data, 0o777)
            env = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/local/go/bin", "HOME": str(data),
                   "PORT": str(self.port), "DATA_DIR": str(data), "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8",
                   "PYTHONDONTWRITEBYTECODE": "1", "GOCACHE": str(data / "gocache"), "GOFLAGS": "-mod=mod"}
            with open(self.log_path, "ab") as log:
                log.write(f"\n==== start {self.generation} on port {self.port} ====\n".encode())
                log.flush()
                self.proc = subprocess.Popen((SANDBOX if self.sandbox else []) + [str(self.source / "run")], cwd=self.source, env=env,
                                             stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
        except OSError:  # no free port, a full disk, or a `run` that cannot be executed
            self.proc = None
            return False
        end = min(time.monotonic() + START_SEC, self.clock.deadline)
        while time.monotonic() < end and self.proc.poll() is None:
            if healthy(self.port, self.clock):
                return True
            time.sleep(0.25)
        self.stop()
        return False

    def current(self) -> tuple[int, int] | None:
        """Generation and port of the running server, restarted first if it is down; None if it cannot run."""
        with self.lock:
            if self.proc is not None and self.proc.poll() is None:
                return self.generation, self.port
            self.stop()
            if self.clock.expired() or self.failed_starts >= START_FAILURES:
                return None
            self.restarts += 1
            if not self.start():
                self.failed_starts += 1
                return None
            self.failed_starts = 0
            return self.generation, self.port

    def planned_restart(self, how: str) -> tuple[int, int] | None:
        """Stop the server as an operator ("term": SIGTERM, then SIGKILL after STOP_SEC) or a power cut ("kill": SIGKILL
        straight after the answer just read) would, and start it again on the same data; None if it does not come back."""
        with self.lock:
            self.planned += 1
            if self.proc is not None:
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    os.killpg(self.proc.pid, signal.SIGTERM if how == "term" else signal.SIGKILL)
                if how == "term":
                    with contextlib.suppress(subprocess.TimeoutExpired):
                        self.proc.wait(timeout=STOP_SEC)
            self.stop()
            if self.clock.expired() or not self.start():
                self.failed_starts += 1
                return None
            self.failed_starts = 0
            return self.generation, self.port

    def recover(self, seen: int) -> None:
        """After a request got no answer: stop the server if it has died or no longer answers its health check.

        A live server has HEALTH_SEC to answer, so one busy with a long request is left alone. The next
        attempt restarts a stopped server.
        """
        with self.lock:
            if self.generation != seen or self.proc is None:
                return
            end = min(time.monotonic() + HEALTH_SEC, self.clock.deadline)
            while self.proc.poll() is None:
                if healthy(self.port, self.clock):
                    return
                if time.monotonic() >= end:
                    break
                time.sleep(1)
            self.stop()


def closed_by_peer(sock: socket.socket) -> bool:
    """Whether the server has closed this idle kept-alive connection; bytes it sent unasked are left for the next answer."""
    try:
        poller = select.poll()
        poller.register(sock, select.POLLIN)
        if not poller.poll(0):
            return False
        return sock.recv(1, socket.MSG_PEEK) == b""
    except BlockingIOError:
        return False
    except (OSError, ValueError):
        return True


def exchange(connection: http.client.HTTPConnection, method: str, path: str, headers: dict[str, str], body: Any,
             raw: bytes | None = None) -> tuple[int, Any]:
    """Send one request on an open connection and read the answer.

    `raw` is a file sent as the request body as it is, with the content type the step names;
    otherwise `body` is sent as JSON. A JSON answer that cannot be parsed (not JSON, too long,
    nested too deeply) becomes a value no recorded answer equals; a file is compared by its
    type, its length and its SHA-256.
    """
    sent = dict(headers)
    if raw is not None:
        payload: bytes | None = raw
    else:
        payload = None if body is None else json.dumps(body).encode()
        if payload is not None:
            sent["Content-Type"] = "application/json"
    for second_try in (False, True):
        # a server may close a kept-alive connection without announcing it: notice that before sending, and if a
        # reused connection still fails before any answer arrives, the request never reached it: send it once more
        if connection.sock is not None and closed_by_peer(connection.sock):
            connection.close()
        reused, refused_early = connection.sock is not None, False
        try:
            connection.request(method, path, body=payload, headers=sent)
        except (BrokenPipeError, ConnectionResetError):
            if raw is not None:
                refused_early = True  # an oversized upload answered (413) and closed before it was read: the answer is there
            elif reused and not second_try:
                connection.close()
                continue
            else:
                raise
        try:
            response = connection.getresponse()
        except (http.client.RemoteDisconnected, ConnectionResetError, BrokenPipeError):
            if reused and not second_try:  # no answer at all, not even an early 413: the connection was closed before we sent
                connection.close()
                continue
            raise
        break
    data = response.read(ANSWER_LIMIT + 1)
    if len(data) <= ANSWER_LIMIT and response.length:
        # the connection ended before the length the server announced: a cut answer is no answer (http.client does not raise)
        raise http.client.IncompleteRead(data, response.length)
    if refused_early or len(data) > ANSWER_LIMIT:
        connection.close()  # the connection still holds the rest of the upload or of the answer
    if len(data) > ANSWER_LIMIT:
        return response.status, TOO_LARGE
    kind = (response.getheader("Content-Type") or "").split(";")[0].strip().lower()
    if kind != "application/json":
        return response.status, {"binary": {"content_type": kind, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}}
    if len(data) > JSON_LIMIT:
        return response.status, TOO_LARGE
    try:
        return response.status, json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, RecursionError, MemoryError):
        return response.status, NOT_JSON


def ask(clock: Clock, connection: http.client.HTTPConnection, method: str, path: str, headers: dict[str, str], body: Any,
        raw: bytes | None = None) -> tuple[int, Any]:
    """One request within REQUEST_SEC and the deadline; NoAnswer if no complete reply came."""
    with clock.limit(connection, REQUEST_SEC):
        try:
            return exchange(connection, method, path, headers, body, raw)
        except (OSError, http.client.HTTPException) as exc:
            raise NoAnswer(type(exc).__name__) from exc


class Media:
    """The files the scenarios upload, read once and shared by every worker."""

    def __init__(self, folder: Path) -> None:
        self.folder, self.cache, self.lock = folder, {}, threading.Lock()

    def body(self, step: dict[str, Any]) -> bytes | None:
        """The raw body a step sends: a named file, N zero bytes, or None for a JSON body."""
        if "body_size" in step:
            return bytes(int(step["body_size"]))
        name = step.get("body_file")
        if name is None:
            return None
        with self.lock:
            if name not in self.cache:
                path = (self.folder / name).resolve()
                if self.folder.resolve() not in path.parents or not path.is_file():
                    raise EvaluationError(f"a scenario names a missing upload: {name}")
                self.cache[name] = path.read_bytes()
            return self.cache[name]


def expand(value: Any, workspace: str) -> Any:
    """The recorded answer with this workspace's id put back where the recorder wrote {ws}.

    The recorder wrote {ws} for the reference's own workspace id wherever it appeared in the answer
    (a random `ws_` and 16 hex digits, so never by chance), and braces cannot occur in an id the
    instruction allows. Putting the candidate's id back in the same places is the exact inverse; the
    candidate's answer itself is never rewritten.
    """
    if isinstance(value, str):
        return value.replace("{ws}", workspace) if "{ws}" in value else value
    if isinstance(value, list):
        return [expand(item, workspace) for item in value]
    if isinstance(value, dict):
        return {expand(key, workspace): expand(item, workspace) for key, item in value.items()}
    return value


def identical(answer: Any, expected: Any) -> bool:
    """Equal as JSON documents: the same types throughout, so `true` is not `1` and `100` is not `100.0`."""
    if type(answer) is not type(expected):
        return False
    if isinstance(expected, dict):
        return answer.keys() == expected.keys() and all(identical(answer[key], expected[key]) for key in expected)
    if isinstance(expected, list):
        return len(answer) == len(expected) and all(identical(a, e) for a, e in zip(answer, expected))
    return answer == expected


def same(answer: Any, expected: Any, workspace: str) -> bool:
    """Whether an answer equals the recorded one; a recorded file's name is not compared."""
    if isinstance(expected, dict) and set(expected) == {"binary"}:
        expected = {"binary": {key: value for key, value in expected["binary"].items() if key != "filename"}}
    try:
        return identical(answer, expand(expected, workspace))
    except RecursionError:  # nested deeper than any recorded answer
        return False


def encode_query(query: dict[str, str]) -> str:
    return ("?" + urlencode(query)) if query else ""


def unit_count(scenario: dict[str, Any]) -> int:
    """A scenario is one unit, or as many as it lists in `units` (the days and screens of a trading run)."""
    return len(scenario["units"]) if scenario.get("units") else 1


def unit_themes(scenario: dict[str, Any]) -> list[str]:
    """The theme each unit of a scenario counts under.

    Raises:
        EvaluationError: A step names a unit the scenario does not have, or a unit has no step.
    """
    count = unit_count(scenario)
    used = {step.get("unit", 0) for step in scenario["steps"]}
    if not used <= set(range(count)) or (scenario.get("units") and len(used) != count):
        raise EvaluationError(f"Private scenarios are malformed: units of {scenario.get('id')}")
    return [unit["theme"] for unit in scenario["units"]] if scenario.get("units") else [scenario["theme"]]


def durable(scenario: dict[str, Any]) -> bool:
    """A scenario with a planned restart in it; such scenarios run one at a time, so the restart disturbs no other."""
    return any("restart" in step for step in scenario["steps"])


def attempt(candidate: Candidate, scenario: dict[str, Any], media: Media, clock: Clock) -> dict[str, Any]:
    """Play a scenario once in a fresh workspace.

    A scenario without units is one unit and stops at its first difference. A scenario with units goes on
    after a difference, so each unit is judged on its own answers: a unit matches when every one of its
    answers does. Either stops when an answer never comes. After a step marked `restart` the server is
    stopped and started again on the same data, and the scenario goes on in the same workspace.
    """
    steps, multi = scenario["steps"], bool(scenario.get("units"))
    count = unit_count(scenario)
    needed, answered, wrong = [0] * count, [0] * count, [False] * count
    for step in steps:
        needed[step.get("unit", 0)] += 1
    difference: tuple[int, str] | None = None

    def result(failed_step: int | None, reason: str | None) -> dict[str, Any]:
        verdicts = [not wrong[unit] and answered[unit] == needed[unit] for unit in range(count)]
        return {"id": scenario["id"], "matched": all(verdicts), "units": verdicts, "failed_step": failed_step, "reason": reason}

    if clock.expired():
        return result(0, LATE)
    running = candidate.current()
    if running is None:
        return result(0, LATE if clock.expired() else DOWN)
    generation, port = running
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=REQUEST_SEC)
    index = 0
    try:
        status, created = ask(clock, connection, "POST", "/api/workspaces", {}, None)
        workspace = created.get("id") if isinstance(created, dict) else None
        if status != 201 or not isinstance(workspace, str) or not WORKSPACE_ID.fullmatch(workspace):
            if candidate.generation != generation:  # the server was restarted under this scenario
                raise NoAnswer("restarted")
            return result(0, "could not create a workspace")
        for index, step in enumerate(steps, start=1):
            unit = step.get("unit", 0)
            # most paths are the workspace's own; a step marked scoped: false names its full path (the client's /api/version)
            path = step["path"] if step.get("scoped", True) is False else f"/api/ws/{workspace}{step['path']}"
            status, answer = ask(clock, connection, step["method"], path + encode_query(step["query"]), step["headers"], step.get("body"),
                                 media.body(step))
            reason = (f"status {status}, expected {step['status']}" if status != step["status"]
                      else None if same(answer, step["json"], workspace) else "body differs")
            if reason is not None:
                if candidate.generation != generation:
                    raise NoAnswer("restarted")
                wrong[unit] = True
                difference = difference or (index, reason)
                if not multi:
                    return result(index, reason)
            answered[unit] += 1
            if step.get("restart"):
                connection.close()
                running = candidate.planned_restart(step["restart"])
                if running is None:
                    return result(index, LATE if clock.expired() else DOWN)
                generation, port = running
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=REQUEST_SEC)
        return result(*(difference or (None, None)))
    except NoAnswer:
        connection.close()  # before waiting on the server: a server that serves one connection at a time may be waiting on this one
        if clock.expired():
            return result(index, LATE)
        candidate.recover(generation)
        return result(index, NO_ANSWER)
    finally:
        connection.close()


def not_played(scenario: dict[str, Any], reason: str) -> dict[str, Any]:
    return {"id": scenario["id"], "matched": False, "units": [False] * unit_count(scenario), "failed_step": 0, "reason": reason}


def play_all(candidate: Candidate, scenarios: list[dict[str, Any]], media: Media, clock: Clock,
             metrics: dict[str, Any]) -> list[dict[str, Any]]:
    """Play every scenario, then give each that got no answer one more try, alone, while time remains.

    Scenarios without a planned restart run WORKERS at a time. Those with one run after them, one at a
    time, so that stopping the server disturbs no other scenario. The second tries are what keep a
    server that crashes now and then from losing the scenarios in flight beside the one that crashed it.
    """
    results: list[dict[str, Any] | None] = [None] * len(scenarios)
    shared = [index for index, scenario in enumerate(scenarios) if not durable(scenario)]
    pool = ThreadPoolExecutor(WORKERS)
    try:
        for index, result in zip(shared, pool.map(lambda i: attempt(candidate, scenarios[i], media, clock), shared)):
            results[index] = result
    finally:
        pool.shutdown(cancel_futures=True)
    for index, scenario in enumerate(scenarios):
        if durable(scenario):
            results[index] = attempt(candidate, scenario, media, clock)
    for index, scenario in enumerate(scenarios):
        if results[index]["reason"] in (NO_ANSWER, DOWN) and not clock.expired():
            metrics["retried"] += 1
            results[index] = attempt(candidate, scenario, media, clock)
    return results


def strip_set_id(root: Path) -> int:
    """Clear the set-user-id and set-group-id bits of every file under `root`; returns how many had one.

    Symbolic links are neither followed nor changed, so nothing outside the submission is touched.
    """
    count = 0
    for folder, _, names in os.walk(root):
        for name in names:
            path = os.path.join(folder, name)
            mode = os.lstat(path).st_mode
            if stat.S_ISREG(mode) and mode & (stat.S_ISUID | stat.S_ISGID):
                os.chmod(path, stat.S_IMODE(mode) & ~(stat.S_ISUID | stat.S_ISGID))
                count += 1
    return count


def privileges_dropped(status: str, uid: int, gid: int) -> bool:
    """Whether /proc/self/status shows a process with only `uid` and `gid`, no capabilities and no_new_privs."""
    fields = dict(line.split(":", 1) for line in status.splitlines() if ":" in line)
    if fields.get("Uid", "").split() != [str(uid)] * 4 or fields.get("Gid", "").split() != [str(gid)] * 4:
        return False
    if fields.get("Groups", "").split() not in ([], [str(gid)]) or fields.get("NoNewPrivs", "").strip() != "1":
        return False  # a kernel that does not report NoNewPrivs cannot show that it holds: fail closed
    return all(int(fields.get(name, "0"), 16) == 0 for name in ("CapPrm", "CapEff", "CapAmb"))


def check_sandbox() -> None:
    """Prove the privilege drop before any submitted code runs, with a process started exactly as the server will be.

    Raises:
        EvaluationError: The unprivileged user is missing, or a process started through the drop keeps
            privileges or could gain them back.
    """
    try:
        uid, gid = pwd.getpwnam(RUN_AS).pw_uid, grp.getgrnam(RUN_GROUP).gr_gid
        done = subprocess.run(SANDBOX + ["cat", "/proc/self/status"], capture_output=True, text=True, timeout=60)
    except (KeyError, OSError, subprocess.SubprocessError) as exc:
        raise EvaluationError("Could not drop privileges; submitted code was not run") from exc
    if done.returncode != 0 or not privileges_dropped(done.stdout, uid, gid):
        raise EvaluationError("Could not drop privileges; submitted code was not run")


def evaluate(source: Path, scenario_path: Path, work: Path, output: Path, sandbox: bool = True,
             media_dir: Path | None = None) -> dict[str, Any]:
    """Grade the server in `source` against the scenarios in `scenario_path`.

    Args:
        source: The submitted /app/server directory.
        scenario_path: Private scenarios with the reference answers.
        work: Scratch directory.
        output: Directory for diagnostic files.
        sandbox: Run the server as the unprivileged user (off only in development checks).
        media_dir: The files the scenarios upload (default: `media` beside the scenarios).

    Returns:
        The reward and its breakdown.

    Raises:
        EvaluationError: The private scenarios are unreadable or privileges cannot be dropped.
    """
    started = time.monotonic()
    clock = Clock(DEADLINE_SEC)
    try:
        try:
            raw = scenario_path.read_bytes()
            scenarios = json.loads(gzip.decompress(raw) if scenario_path.suffix == ".gz" else raw)["scenarios"]
        except (OSError, ValueError, KeyError) as exc:
            raise EvaluationError("Private scenarios are unreadable") from exc
        if not scenarios:
            raise EvaluationError("Private scenarios are empty")
        themes = [unit_themes(scenario) for scenario in scenarios]  # also checks that every unit has steps
        total = sum(len(names) for names in themes)
        by_theme = {name: {"total": sum(names.count(name) for names in themes), "matched": 0} for name in sorted({n for ns in themes for n in ns})}
        metrics: dict[str, Any] = {"units_total": total, "units_matched": 0, "reward": 0.0, "scenarios_total": len(scenarios),
                                   "scenarios_matched": 0, "restarts": 0, "planned_restarts": 0, "retried": 0, "unfinished": 0, "notes": [],
                                   "by_theme": by_theme}
        if sandbox:
            check_sandbox()
        candidate: Candidate | None = None
        runner = source / "run"
        if source.is_symlink() or not runner.is_file() or not os.access(runner, os.X_OK):
            metrics["notes"].append("/app/server/run is missing or not executable")
            results = [not_played(scenario, "no server to run") for scenario in scenarios]
        else:
            stripped = strip_set_id(source)
            if stripped:
                metrics["notes"].append(f"set-user-id or set-group-id bits were removed from {stripped} submitted files")
            work.mkdir(parents=True, exist_ok=True)
            os.chmod(work, 0o755)
            if sandbox:
                subprocess.run(["chmod", "-R", "a+rX", str(source)], check=False)
            candidate = Candidate(source, work, output / "server.log", sandbox, clock)
            try:
                if candidate.start():
                    results = play_all(candidate, scenarios, Media(media_dir or scenario_path.parent / "media"), clock, metrics)
                else:
                    metrics["notes"].append(f"the server did not answer GET /api/health within {START_SEC} seconds")
                    results = [not_played(scenario, "the server did not start") for scenario in scenarios]
            finally:
                candidate.stop()
    finally:
        clock.stop()
    for names, result in zip(themes, results):
        metrics["scenarios_matched"] += result["matched"]
        for name, verdict in zip(names, result["units"]):
            metrics["units_matched"] += verdict
            metrics["by_theme"][name]["matched"] += verdict
    metrics["unfinished"] = sum(1 for result in results if result["reason"] == LATE)
    if metrics["unfinished"]:
        metrics["notes"].append(f"the replay reached its time limit of {DEADLINE_SEC} seconds; "
                                f"{metrics['unfinished']} scenarios were not played to the end")
    if candidate is not None:
        metrics["restarts"], metrics["planned_restarts"] = candidate.restarts, candidate.planned
        if candidate.failed_starts >= START_FAILURES:
            metrics["notes"].append(f"the server stopped and did not come back after {START_FAILURES} restarts in a row")
    metrics["reward"] = round(metrics["units_matched"] / total, 6)
    metrics["elapsed_sec"] = round(time.monotonic() - started, 1)
    metrics["results"] = results  # per-scenario diagnostics, written by the caller after the reward
    return metrics
