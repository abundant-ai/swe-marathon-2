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
- Restarts: every scenario is played once, WORKERS at a time, in a fixed shuffled
  order, so a server too slow to finish loses scenarios of every kind. One that got
  no answer (the server died, dropped the connection or ran out of time) is played
  once more on its own after the others, so a server that crashes now and then
  loses only the scenarios that crash it. A server that has died, or has left its
  health check unanswered for HEALTH_SEC, is restarted before the next attempt, as
  often as needed while the deadline holds; after START_FAILURES starts in a row
  that never answer it is given up. Every start uses the same DATA_DIR.
- Second tries start from nothing: the server is stopped, every process of its user
  is ended, DATA_DIR and every file its user owns are removed with the shared memory
  and message queues, and a fresh server is started. A second try decides only the
  units the first try left unanswered, so nothing seen on the first try (a later
  request of a month echoes many earlier answers) can be put to use on the second.
- Planned restarts: a scenario with a step marked `restart` runs with nothing beside
  it, at a fixed place among the others. After that step the server is stopped
  (SIGTERM, or SIGKILL straight after the answer) and started again on the same
  DATA_DIR, and the scenario goes on in the same workspace: what a workspace holds
  must survive.
- Nothing the server sends or does makes the evaluation fail: a reply that is not
  HTTP, not JSON, too large or nested too deeply is an answer that matches nothing;
  the server runs as an unprivileged user under limits on threads, file size and
  memory, cannot write its own files, and is the first process ended when memory
  runs out.
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
import sys
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

RUN_AS, RUN_GROUP = "nobody", "nogroup"
# threads the server's user may run at once: plenty for any server, too few to fill the process table. The count is per
# user across a shared kernel, so it is set well above what one server needs.
THREAD_LIMIT = 4096
FILE_LIMIT = 4 << 30  # bytes in any one file it writes
MEMORY_LIMIT = 6 << 30  # address space of each of its processes, on a machine with 8 GB
# set as root before the drop, so the server cannot lower it: when memory runs out the kernel ends the server first
OOM_FIRST = ["sh", "-c", '{ echo 1000 > /proc/self/oom_score_adj; } 2>/dev/null; exec "$@"', "sh"]
LIMITS = ["prlimit", f"--nproc={THREAD_LIMIT}", f"--fsize={FILE_LIMIT}", f"--as={MEMORY_LIMIT}", "--"]
# no_new_privs: executing a set-user-id or set-group-id file, or one with file capabilities, grants nothing
DROP = ["setpriv", "--reuid", RUN_AS, "--regid", RUN_GROUP, "--clear-groups", "--no-new-privs"]
SANDBOX = OOM_FIRST + LIMITS + DROP
# where any user can create files, besides the root filesystem: swept before the second tries
SCRATCH = ("/tmp", "/var/tmp", "/dev/shm", "/dev/mqueue", "/run/lock", "/var/lock", "/run/shm")
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


def user_processes(uid: int) -> list[int]:
    """Live processes whose real user is `uid`, read from /proc: that needs no new process, even with a full process table."""
    found = []
    with contextlib.suppress(OSError):
        with os.scandir("/proc") as entries:
            for entry in entries:
                if not entry.name.isdigit():
                    continue
                try:
                    with open(f"/proc/{entry.name}/status", encoding="latin-1") as status:
                        fields = dict(line.split(":", 1) for line in status if ":" in line)
                except (OSError, ValueError):
                    continue
                if fields.get("Uid", "").split()[:1] == [str(uid)] and not fields.get("State", "").strip().startswith(("Z", "X")):
                    found.append(int(entry.name))
    return found


def end_user_processes(uid: int, seconds: float = 20) -> bool:
    """Stop every process of `uid`, then kill them all; True when none is left.

    A sweep that lists processes and then kills them can be outrun by one that forks fast enough
    (QA 07 F4). A stopped process cannot fork: once every process listed is stopped and a new listing
    finds no other, none can appear, and all are killed. Never raises.
    """
    end = time.monotonic() + seconds
    stopped: set[int] = set()
    while time.monotonic() < end:
        alive = set(user_processes(uid))
        if not alive:
            return True
        fresh = alive - stopped
        for pid in fresh or alive:
            with contextlib.suppress(OSError):
                os.kill(pid, signal.SIGSTOP if fresh else signal.SIGKILL)
        stopped |= fresh
        if not fresh:
            time.sleep(0.05)
    return not user_processes(uid)


def reap_orphans() -> None:
    """Collect the exit status of every finished child, so the server's killed helpers do not linger as zombies (they
    would count against its thread limit). The evaluation is their reaper (PR_SET_CHILD_SUBREAPER) when sandboxed."""
    with contextlib.suppress(ChildProcessError, OSError):
        while os.waitpid(-1, os.WNOHANG)[0] > 0:
            pass


def remove_tree(path: Path | str) -> None:
    """Remove a directory tree however deep it is (a deep enough one makes shutil.rmtree recurse past Python's limit)."""
    try:
        shutil.rmtree(path, ignore_errors=True)
    except RecursionError:
        pass
    if os.path.lexists(path):
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            subprocess.run(["rm", "-rf", "--", str(path)], check=False, capture_output=True, timeout=600)


def remove_user_files(uid: int, roots: tuple[str, ...] = ("/",) + SCRATCH) -> int:
    """Remove every file and directory `uid` owns under `roots` (each walked on its own filesystem, links never followed),
    and in the scratch places every hard link, which can only be one made to another user's file; returns how many."""
    removed = 0

    def sweep(folder: str, device: int, scratch: bool) -> None:
        nonlocal removed
        try:
            with os.scandir(folder) as entries:
                for entry in entries:
                    try:
                        info = entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    directory = stat.S_ISDIR(info.st_mode)
                    if info.st_uid == uid or (scratch and not directory and info.st_nlink > 1):
                        removed += 1
                        if directory:
                            remove_tree(entry.path)
                        else:
                            with contextlib.suppress(OSError):
                                os.unlink(entry.path)
                    elif directory and info.st_dev == device:
                        sweep(entry.path, device, scratch)
        except (OSError, RecursionError):
            pass

    for root in roots:
        try:
            top = os.lstat(root)
        except OSError:
            continue
        if stat.S_ISDIR(top.st_mode):
            sweep(root, top.st_dev, root in SCRATCH)
    return removed


def open_log(path: Path) -> int:
    """The server's log, opened for appending and readable by root only: the server writes to it but cannot read it back
    through /proc/self/fd, so it carries nothing from one start of the server to the next."""
    descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with contextlib.suppress(OSError):
        os.fchmod(descriptor, 0o600)
    return descriptor


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
        self.uid = pwd.getpwnam(RUN_AS).pw_uid if sandbox else -1

    def stop(self) -> None:
        """Kill the server's process group and, when sandboxed, every process its user still runs. Never raises: a server
        that has exhausted processes, memory or disk must not turn a finished evaluation into an error (QA 07 F2)."""
        if self.proc is not None:
            with contextlib.suppress(OSError):
                os.killpg(self.proc.pid, signal.SIGKILL)
        if self.sandbox:
            end_user_processes(self.uid)  # children that left the group too
        if self.proc is not None:
            with contextlib.suppress(subprocess.TimeoutExpired, OSError):
                self.proc.wait(timeout=10)
        if self.sandbox:
            reap_orphans()
        self.proc = None

    def clean_slate(self) -> None:
        """Before the second tries: stop the server and remove everything it could have kept from the first pass, its
        data, its user's processes and files anywhere, shared memory and message queues; then start it afresh.

        The submission itself is read-only to the server, so it starts again exactly as delivered.
        """
        with self.lock:
            self.stop()
            remove_tree(self.data)
            if self.sandbox:
                remove_user_files(self.uid)
                with contextlib.suppress(OSError, subprocess.SubprocessError):
                    subprocess.run(["ipcrm", "--all"], check=False, capture_output=True, timeout=60)
            if not self.clock.expired() and self.start():
                self.failed_starts = 0
            else:
                self.failed_starts += 1  # the next attempt tries again, as after a crash

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
            log = open_log(self.log_path)
            try:
                with contextlib.suppress(OSError):
                    os.write(log, f"\n==== start {self.generation} on port {self.port} ====\n".encode())
                self.proc = subprocess.Popen((SANDBOX if self.sandbox else []) + [str(self.source / "run")], cwd=self.source, env=env,
                                             stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
            finally:
                os.close(log)
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
        # a unit with a wrong answer, or with every answer in, is settled: a second try cannot change its verdict
        settled = [wrong[unit] or answered[unit] == needed[unit] for unit in range(count)]
        return {"id": scenario["id"], "matched": all(verdicts), "units": verdicts, "settled": settled, "failed_step": failed_step,
                "reason": reason}

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
    count = unit_count(scenario)
    return {"id": scenario["id"], "matched": False, "units": [False] * count, "settled": [False] * count, "failed_step": 0, "reason": reason}


def merge_retry(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    """The verdict after a second try: it decides only the units the first try left unsettled (QA 07 F1).

    A month goes on after a wrong answer, and later requests echo many earlier answers, so a server could
    read a whole month on the first try, give no answer at the end to earn a second, and replay what it
    learned. The units it answered on the first try keep the first try's verdicts.
    """
    units = [old if settled else new for old, new, settled in zip(first["units"], second["units"], first["settled"])]
    settled = [old or new for old, new in zip(first["settled"], second["settled"])]
    reason = second["reason"] or (None if all(units) else "answered differently on the first try")
    return dict(second, matched=all(units), units=units, settled=settled, reason=reason,
                failed_step=second["failed_step"] if second["reason"] else None)


def play_order(scenarios: list[dict[str, Any]]) -> list[int]:
    """The order scenarios are started in: a fixed shuffle, so a server too slow to finish loses some of every kind rather
    than the kinds that come last, with the scenarios that restart the server spread evenly through it."""
    def mixed(indexes: list[int]) -> list[int]:
        return sorted(indexes, key=lambda index: hashlib.sha256(str(scenarios[index]["id"]).encode()).digest())

    shared = mixed([index for index, scenario in enumerate(scenarios) if not durable(scenario)])
    restarting = mixed([index for index, scenario in enumerate(scenarios) if durable(scenario)])
    order: list[int] = []
    taken = 0
    for number, index in enumerate(restarting, start=1):
        upto = len(shared) * number // (len(restarting) + 1)
        order += shared[taken:upto] + [index]
        taken = upto
    return order + shared[taken:]


class Gate:
    """Lets scenarios run side by side, except one with a planned restart, which waits until it is alone and holds back
    those after it until it is done, so stopping the server disturbs no other scenario."""

    def __init__(self) -> None:
        self.condition = threading.Condition()
        self.running = 0
        self.alone = False
        self.waiting = 0

    @contextlib.contextmanager
    def enter(self, exclusive: bool) -> Iterator[None]:
        with self.condition:
            if exclusive:
                self.waiting += 1
                self.condition.wait_for(lambda: not self.alone and self.running == 0)
                self.waiting -= 1
                self.alone = True
            else:
                self.condition.wait_for(lambda: not self.alone and self.waiting == 0)
                self.running += 1
        try:
            yield
        finally:
            with self.condition:
                if exclusive:
                    self.alone = False
                else:
                    self.running -= 1
                self.condition.notify_all()


def play_all(candidate: Candidate, scenarios: list[dict[str, Any]], media: Media, clock: Clock,
             metrics: dict[str, Any]) -> list[dict[str, Any]]:
    """Play every scenario, then give each that got no answer one more try, alone, on a clean slate, while time remains.

    Scenarios run WORKERS at a time in `play_order`; one with a planned restart runs with nothing beside
    it. The second tries are what keep a server that crashes now and then from losing the scenarios in
    flight beside the one that crashed it.
    """
    results: list[dict[str, Any] | None] = [None] * len(scenarios)
    gate = Gate()

    def play(index: int) -> dict[str, Any]:
        with gate.enter(durable(scenarios[index])):
            return attempt(candidate, scenarios[index], media, clock)

    order = play_order(scenarios)
    pool = ThreadPoolExecutor(WORKERS)
    try:
        for index, result in zip(order, pool.map(play, order)):
            results[index] = result
    finally:
        pool.shutdown(cancel_futures=True)
    again = [index for index in order if results[index]["reason"] in (NO_ANSWER, DOWN)]
    if again and not clock.expired():
        candidate.clean_slate()
        for index in again:
            if clock.expired():
                break
            metrics["retried"] += 1
            results[index] = merge_retry(results[index], attempt(candidate, scenarios[index], media, clock))
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


# Run under the drop: prints /proc/self/status, then what prctl(PR_GET_NO_NEW_PRIVS) says, since some
# kernels (gVisor among them, possibly) do not list NoNewPrivs in the status file, then the limits.
NNP_PROBE = (
    "import ctypes, resource, sys\n"
    "sys.stdout.write(open('/proc/self/status').read())\n"
    "try:\n"
    "    value = ctypes.CDLL(None, use_errno=True).prctl(39, 0, 0, 0, 0)\n"
    "except Exception:\n"
    "    value = -1\n"
    "sys.stdout.write('PrctlNoNewPrivs:\\t%d\\n' % value)\n"
    "for name in ('NPROC', 'FSIZE', 'AS'):\n"
    "    sys.stdout.write('Rlimit%s:\\t%d %d\\n' % ((name,) + resource.getrlimit(getattr(resource, 'RLIMIT_' + name))))\n"
)
LIMIT_LINES = {"NPROC": ("Max processes", THREAD_LIMIT), "FSIZE": ("Max file size", FILE_LIMIT), "AS": ("Max address space", MEMORY_LIMIT)}


def limits_applied(report: str) -> bool:
    """Whether a process's report shows the server's limits, soft and hard: `Rlimit*` lines from `NNP_PROBE`, or the
    lines of /proc/self/limits."""
    found: dict[str, list[str]] = {}
    for line in report.splitlines():
        for name, (title, _) in LIMIT_LINES.items():
            if line.startswith(f"Rlimit{name}:"):
                found[name] = line.split(":", 1)[1].split()
            elif line.startswith(title + " ") and name not in found:
                found[name] = line[len(title):].split()[:2]
    return all(found.get(name) == [str(value)] * 2 for name, (_, value) in LIMIT_LINES.items())


def privileges_dropped(status: str, uid: int, gid: int) -> bool:
    """Whether a process's status shows only `uid` and `gid`, no capabilities and no_new_privs.

    `status` is /proc/self/status, optionally followed by a `PrctlNoNewPrivs:` line from `NNP_PROBE`;
    no_new_privs counts as set when either source says so.
    """
    fields = dict(line.split(":", 1) for line in status.splitlines() if ":" in line)
    if fields.get("Uid", "").split() != [str(uid)] * 4 or fields.get("Gid", "").split() != [str(gid)] * 4:
        return False
    no_new_privs = "1" in (fields.get("NoNewPrivs", "").strip(), fields.get("PrctlNoNewPrivs", "").strip())
    if fields.get("Groups", "").split() not in ([], [str(gid)]) or not no_new_privs:
        return False  # neither the status file nor prctl shows no_new_privs: fail closed
    return all(int(fields.get(name, "0"), 16) == 0 for name in ("CapPrm", "CapEff", "CapAmb"))


def check_sandbox() -> None:
    """Prove the privilege drop before any submitted code runs, with a process started exactly as the server will be.

    Raises:
        EvaluationError: The unprivileged user is missing, or a process started through the drop keeps
            privileges or could gain them back, or does not run under the server's limits.
    """
    try:
        uid, gid = pwd.getpwnam(RUN_AS).pw_uid, grp.getgrnam(RUN_GROUP).gr_gid
        done = subprocess.run(SANDBOX + [sys.executable, "-I", "-c", NNP_PROBE],
                              capture_output=True, text=True, timeout=60)
        if done.returncode != 0:  # this interpreter is not runnable by the user: the status and limits files alone
            done = subprocess.run(SANDBOX + ["cat", "/proc/self/status", "/proc/self/limits"], capture_output=True, text=True, timeout=60)
    except (KeyError, OSError, subprocess.SubprocessError) as exc:
        raise EvaluationError("Could not drop privileges; submitted code was not run") from exc
    if done.returncode != 0 or not privileges_dropped(done.stdout, uid, gid):
        raise EvaluationError("Could not drop privileges; submitted code was not run")
    if not limits_applied(done.stdout):
        raise EvaluationError("Could not limit the server's threads, file size and memory; submitted code was not run")


def seal_submission(source: Path) -> None:
    """Make the submission root's and read-only to the server's user: it cannot keep anything in its own files, and every
    start runs exactly what was delivered. Links are not followed."""
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        subprocess.run(["chown", "-R", "root:root", str(source)], check=False, capture_output=True, timeout=600)
        subprocess.run(["chmod", "-R", "a+rX,go-w", str(source)], check=False, capture_output=True, timeout=600)


def become_reaper() -> None:
    """Adopt the server's orphaned helpers (PR_SET_CHILD_SUBREAPER), so they can be reaped after they are killed."""
    with contextlib.suppress(Exception):
        import ctypes

        ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0)


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
            become_reaper()
        candidate: Candidate | None = None
        runner = source / "run"
        if source.is_symlink() or not source.is_dir():
            # an /app/server that could not be copied out of the agent's machine (QA 07 F3) arrives as nothing at all
            metrics["notes"].append("/app/server did not arrive: it is missing, or it could not be copied from the machine it was built on")
            results = [not_played(scenario, "no server to run") for scenario in scenarios]
        elif not runner.is_file() or not os.access(runner, os.X_OK):
            metrics["notes"].append("/app/server/run is missing or not executable")
            results = [not_played(scenario, "no server to run") for scenario in scenarios]
        else:
            stripped = strip_set_id(source)
            if stripped:
                metrics["notes"].append(f"set-user-id or set-group-id bits were removed from {stripped} submitted files")
            work.mkdir(parents=True, exist_ok=True)
            os.chmod(work, 0o755)
            if sandbox:
                seal_submission(source)
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
