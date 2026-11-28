"""The work is delivered as the agent's user left it when the work ended, and the verifier knows it.

The setup hook and the collect hook run whole under dash, as shipped, with only their absolute
paths rewritten into a scratch directory, a few sizes and waits shortened, and, first on PATH,
stand-ins for what needs root or Linux: setpriv never runs a kill, pgrep and pkill find none of the
user's processes, fallocate fails (so the fallback writes the room), timeout and setsid run their
command, and python3 is this Python, run without network: host names resolve to a documentation
address, and a connection is refused, completed, or fails for a reason of the machine
(EADDRNOTAVAIL), as a scenario says. The net check is either a stand-in that writes the status the
real one writes from a scenario the check sets, or the real one, run whole: its probe process, its
polls and its record, with the network taken from the scenario file (the watch of the sessions finds
no /proc here, and no user `dev` to end). The delivery the hook marks is then copied the way the
platform copies an artifact (a tar, unpacked with the `data` filter) and read by the verifier, and
where it matters graded by the verifier's own steps (the privilege drop and the network probe of the
verifier stood in for). The real net check's own logic, and its watch of the sessions on a stand-in
/proc, are checked directly too.
"""

from __future__ import annotations

import errno
import hashlib
import hmac
import importlib.machinery
import importlib.util
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import threading
import time
import tomllib
import types
from pathlib import Path

import pytest

ENV_DIR = Path(__file__).resolve().parent.parent / "environment"
DASH = shutil.which("dash") or "/bin/sh"
KEY = "0123456789abcdef" * 4
ROOM = 1 << 20

RUN_STDIN = """import errno, os, socket, ssl, sys


def egress():
    path = os.environ.get("FAKE_EGRESS_FILE")
    if path:
        try:
            with open(path) as handle:
                return handle.read().strip()
        except OSError:
            return "closed"
    return os.environ.get("FAKE_EGRESS", "closed")


def connect(address, timeout=None, *args, **kwargs):
    state = egress()
    if state == "open":
        return socket.socket()
    if state == "slow":
        import time
        time.sleep(1.5)
        return socket.socket()
    if state == "local":
        raise OSError(errno.EADDRNOTAVAIL, "Cannot assign requested address")
    raise ConnectionRefusedError(111, "refused")


socket.create_connection = connect
socket.getaddrinfo = lambda host, port, *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.1", port))]
ssl.SSLContext.wrap_socket = lambda self, sock, *args, **kwargs: sock
assert sys.argv[1] == "-I", sys.argv
if sys.argv[2] == "-c":
    code, sys.argv, name = sys.argv[3], ["-c"] + sys.argv[4:], "<hook>"
elif sys.argv[2] == "-":
    code, sys.argv, name = sys.stdin.read(), ["-"] + sys.argv[3:], "<hook>"
else:
    name = sys.argv[2]
    with open(name) as handle:
        code = handle.read()
    sys.argv = sys.argv[2:]
exec(compile(code, name, "exec"), {"__name__": "__main__", "__file__": name, "__builtins__": __builtins__})
"""

# the net check's status as the real one writes it, from STATE/scenario.json, read again before every
# write: {"live": bool, "last": "open" | "closed" | "local", "openings": [...], "closing": [...] | null,
# "sessions": {...} | null}
NETCHECK_STAND_IN = """import json, os, sys, time
state = STATE
started = time.time()


def scenario():
    try:
        with open(os.path.join(state, "scenario.json")) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {"live": True, "last": "closed", "openings": [], "closing": None}


def put(name, record):
    with open(os.path.join(state, name + ".tmp"), "w") as handle:
        json.dump(record, handle)
    os.replace(os.path.join(state, name + ".tmp"), os.path.join(state, name))


while time.time() - started < 120:
    plan = scenario()
    now = time.time() if plan.get("live", True) else started - 100
    put("netcheck.json", {"started_at": started, "pid": os.getpid(), "hosts": {"pypi.org": ["192.0.2.1"]}, "min_closed_polls": 3,
                          "local_limit": 3, "polls": 10, "local_polls": plan.get("local_polls", 0), "openings": plan.get("openings", []),
                          "closing": plan.get("closing"), "last_poll": [now, plan.get("last", "closed")]})
    sessions = plan.get("sessions")
    put("sessions.json", dict(sessions, last_scan=now) if sessions is not None else {"available": False, "last_scan": now})
    if not plan.get("live", True):
        break
    time.sleep(0.05)
"""

STAND_INS = {
    "setpriv": 'for word in "$@"; do case "$word" in kill) exit 0 ;; esac; done\n'
    'while [ $# -gt 0 ]; do case "$1" in --reuid|--regid) shift 2 ;; --clear-groups|--no-new-privs) shift ;; *) break ;; esac; done\n'
    'exec "$@"\n',
    "pgrep": "exit 1\n",
    "pkill": "exit 1\n",
    "fallocate": "exit 1\n",
    "timeout": 'shift\nexec "$@"\n',
    "setsid": 'exec "$@"\n',
}


def opening(bound: float, polls: int = 30, kind: str = "open") -> dict:
    """An opening as the net check records it: the stretch of `polls` closed polls ended at `bound`."""
    return {
        "first_open_at": bound + 0.11,
        "last_closed_at": bound,
        "end_bound": bound,
        "closed_since": bound - 0.11 * polls,
        "closed_polls": polls,
        "kind": kind,
        "host": "pypi.org" if kind == "open" else None,
        "local": "EADDRNOTAVAIL" if kind == "local" else None,
    }


class Hooks:
    """The setup and collect hooks, rewritten into `root`, with the stand-ins first on PATH."""

    def __init__(
        self,
        root: Path,
        real_netcheck: bool = False,
        netcheck_settings: dict | None = None,
        **settings,
    ):
        self.root = root
        self.bin, self.lib, self.state = root / "bin", root / "lib", root / "state"
        self.app = root / "app"
        self.tree = self.app / "sympy"
        self.egress = root / "egress"
        for folder in (self.bin, self.lib, self.tree, self.state):
            folder.mkdir(parents=True)
        self.egress.write_text("open\n")  # setup has the network
        (self.bin / "run_stdin.py").write_text(RUN_STDIN)
        (self.bin / "python3").write_text(
            f'#!/bin/sh\nexec "{sys.executable}" "{self.bin}/run_stdin.py" "$@"\n'
        )
        for name, body in STAND_INS.items():
            (self.bin / name).write_text("#!/bin/sh\n" + body)
        for path in self.bin.iterdir():
            path.chmod(0o755)
        (self.lib / "key").write_text(KEY + "\n")
        self.units = root / "units.json"
        self.units.write_text(
            json.dumps(
                [
                    {
                        "uid": "U0001",
                        "file": "sympy/m.py",
                        "module": "sympy.m",
                        "qualname": "f",
                        "dotted": "sympy.m.f",
                        "occ": 0,
                        "nocc": 1,
                        "order": 0,
                    }
                ]
            )
        )
        self.spare = [root / "tmp", root / "vartmp", root / "shm"]
        for folder in self.spare:
            folder.mkdir()
        rewrites = [
            (
                'SPARE_DIRS="/tmp /var/tmp /dev/shm"',
                f'SPARE_DIRS="{" ".join(str(f) for f in self.spare)}"',
            ),
            ("/usr/bin/python3", str(self.bin / "python3")),
            ("/usr/local/lib/fsmaint/key", str(self.lib / "key")),
            ("/usr/local/lib/fsmaint", str(self.lib)),
            ("/var/lib/fsmaint", str(self.state)),
            ("/app/sympy", str(self.tree)),
            ("/opt/restore/units.json", str(self.units)),
        ]
        if real_netcheck:
            text = (ENV_DIR / "fsmaint-netcheck").read_text()
            for old, new in rewrites:
                text = text.replace(old, new)
            for setting, value in (netcheck_settings or {}).items():
                text, count = re.subn(
                    rf"^{setting} = [\d.]+",
                    f"{setting} = {value}",
                    text,
                    flags=re.MULTILINE,
                )
                assert count == 1, setting
            (self.lib / "fsmaint-netcheck").write_text(text)
        else:
            (self.lib / "fsmaint-netcheck").write_text(
                NETCHECK_STAND_IN.replace("STATE", repr(str(self.state)), 1)
            )
        found = dict.fromkeys(settings, 0)
        for name in ("fsmaint-reserve", "fsmaint-sweep"):
            text = (ENV_DIR / name).read_text()
            for old, new in rewrites:
                text = text.replace(old, new)
            for _, new in rewrites:
                assert not re.search(
                    r"(?<![\w.])/(app|var|usr|run)/", text.replace(new, "")
                ), f"{name}: every absolute path is rewritten"
            text = (
                text.replace("ROOM_BYTES=134217728\n", f"ROOM_BYTES={ROOM}\n")
                .replace("COPY_ROOM_BYTES=67108864\n", f"COPY_ROOM_BYTES={ROOM}\n")
                .replace("NETCHECK_SETTLE_SECONDS=20\n", "NETCHECK_SETTLE_SECONDS=2\n")
            )
            for setting, value in settings.items():
                text, count = re.subn(
                    rf"^{setting}=\d+$", f"{setting}={value}", text, flags=re.MULTILINE
                )
                found[setting] += count
            (root / name).write_text(text)
        assert all(count == 1 for count in found.values()), found
        self.env = dict(
            os.environ,
            PATH=f"{self.bin}:{os.environ['PATH']}",
            LC_ALL="C",
            FAKE_EGRESS_FILE=str(self.egress),
        )
        self.scenario(live=True, last="closed")

    def scenario(self, **plan) -> None:
        """What the stand-in net check reports from now on."""
        plan = dict(
            {"live": True, "last": "closed", "openings": [], "closing": None}, **plan
        )
        (self.state / "scenario.json.tmp").write_text(json.dumps(plan))
        os.replace(self.state / "scenario.json.tmp", self.state / "scenario.json")

    def network(self, state: str) -> None:
        """What every connection attempt gets from now on: "open", "closed", "local" or "slow" (answers after 1.5 s)."""
        (self.root / "egress.tmp").write_text(state + "\n")
        os.replace(self.root / "egress.tmp", self.egress)

    def setup(self) -> None:
        """setup_begin, then setup_complete, as task.toml runs them; wait for the net check's first status."""
        for args in ((), ("--netcheck",)):
            done = self.run("fsmaint-reserve", *args)
            assert done.stdout == "" and done.stderr == "", done
        for _ in range(200):
            if (self.state / "netcheck.json").exists():
                return
            time.sleep(0.05)
        raise AssertionError("the net check did not start")

    def work_started(self) -> float:
        return float((self.state / "work-started").read_text())

    def run(
        self, name: str, *args: str, egress: str | None = None, check: bool = True
    ) -> subprocess.CompletedProcess:
        if egress is not None:
            self.network(egress)
        done = subprocess.run(
            [DASH, str(self.root / name), *args],
            check=False,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert done.returncode == 0 or not check, done
        return done

    def record(self) -> dict:
        return json.loads((self.tree / ".fsmaint.json").read_text())


def platform_copy(top: Path, dest: Path) -> None:
    """The platform's copy of an artifact: a tar of it as it is, unpacked with the `data` filter."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    archive = dest.parent / f"{dest.name}.tar"
    with tarfile.open(archive, "w") as tar:
        tar.add(top, arcname=".")
    dest.mkdir(parents=True)
    with tarfile.open(archive) as tar:
        tar.extractall(dest, filter="data")


def signed(mark: str, record: bytes) -> bool:
    lines = mark.split("\n")[:-1]
    _, record_sha, signature = lines[-1].split(" ")
    payload = ("\n".join(lines[:-1]) + "\n" + record_sha).encode()
    return record_sha == hashlib.sha256(record).hexdigest() and hmac.compare_digest(
        signature, hmac.new(KEY.encode(), payload, hashlib.sha256).hexdigest()
    )


def resign(top: Path, change) -> None:
    """Change the record with `change(record)` and sign it again with the key, as the collect step would."""
    record = json.loads((top / ".fsmaint.json").read_text())
    change(record)
    payload = json.dumps(record, separators=(",", ":")).encode()
    (top / ".fsmaint.json").write_bytes(payload)
    lines = (top / ".fsmaint").read_text().split("\n")[:-2]
    digest = hashlib.sha256(payload).hexdigest()
    signature = hmac.new(
        KEY.encode(), ("\n".join(lines) + "\n" + digest).encode(), hashlib.sha256
    ).hexdigest()
    (top / ".fsmaint").write_text(
        "\n".join(lines + [f"sig {digest} {signature}"]) + "\n"
    )


def read_delivery(
    verifier_call, top: Path, key: Path, progress: Path | None = None
) -> dict:
    return verifier_call(f"""
import json
from pathlib import Path
from verifier import delivery
from verifier.contracts import EvaluationError
try:
    d = delivery.read_delivery(Path({str(top)!r}), Path({str(key)!r}), Path({str(progress or top / "no-progress")!r}))
    print(json.dumps({{"state": d.state, "late": sorted(d.late), "end_from": d.end_from, "end_bound": d.end_bound,
                       "end_note": d.end_note, "entries": len(d.entries), "notes": d.notes, "copied": d.copied,
                       "egress_open": d.summary.get("egress_open"), "refused": d.summary.get("refused")}}))
except EvaluationError as exc:
    print(json.dumps({{"error": str(exc)}}))
""")


PLACEHOLDER = 'def f():\n    raise NotImplementedError("RESTORE U0001")\n'


def grade(
    verifier_call, arrived: Path, key: Path, progress: Path | None = None
) -> dict:
    """The verifier's own steps (registry, measurement, scoring, report) on an arrived tree holding
    sympy/m.py, one unit (U0001, `f`), with the privilege drop and the verifier's network probe stood
    in for. Only paths that end before any submitted code runs are graded this way."""
    return verifier_call(f"""
import json, pickle, shutil, tempfile
from pathlib import Path
from verifier import engine
from verifier.config import load_config
from verifier.contracts import EvaluationError, VerificationContext
from verifier.reporting import write_report
from verifier.runner import verify
engine.delivery.network_open = lambda *a, **k: None
engine.delivery.PROGRESS = Path({str(progress or arrived / "no-progress")!r})
engine.sandbox_prefix = lambda *a, **k: []
engine.reap = lambda prefix: None
root = Path(tempfile.mkdtemp())
skel, private, out = root / "skel", root / "private", root / "out"
(skel / "sympy").mkdir(parents=True)
(skel / "sympy" / "m.py").write_text({PLACEHOLDER!r})
(private / "vectors").mkdir(parents=True)
(out / "artifacts").mkdir(parents=True)
units = [{{"uid": "U0001", "file": "sympy/m.py", "module": "sympy.m", "qualname": "f", "dotted": "sympy.m.f", "occ": 0, "nocc": 1,
           "order": 0}}]
(private / "units.json").write_text(json.dumps(units))
(private / "sealed_tests.json").write_text(json.dumps({{"tests": []}}))
(private / "vectors" / "gold.json").write_text(json.dumps({{"V1": ["I", "1"]}}))
(private / "vectors" / "documented.json").write_text(json.dumps({{"calls": []}}))
(private / "unit_bodies.json").write_text(json.dumps({{"U0001": [1, None]}}))
(private / "timing.json").write_text(json.dumps({{"benchmark_sec": 1.0, "doctest": {{"load": {{}}, "units": {{}}}},
                                                  "vector": {{"load": {{}}, "units": {{}}}}}}))
meta = {{"U0001": {{"file": "sympy/m.py", "qualname": "f", "name": "f", "occ": 0, "nocc": 1}}}}
(private / "vectors" / "inputs.pkl").write_bytes(pickle.dumps({{"sympy.m": {{"units": meta, "vectors": [("V1", "U0001", pickle.dumps({{}}))]}}}}))
shutil.copyfile({str(key)!r}, private / "fsmaint.key")
scoring, limits = load_config()
ctx = VerificationContext(Path({str(arrived.parent)!r}), skel, private, out, root / "scratch", scoring, dict(limits, workers=1))
try:
    result = verify(ctx)
    write_report(out, ctx, result, None)
    metrics = json.loads((out / "metrics.json").read_text())
    print(json.dumps({{"status": "completed", "reward": (out / "reward.txt").read_text(), "checks": metrics["checks"],
                       "end_from": metrics["end_from"], "notes": metrics["notes"][-3:]}}))
except EvaluationError as exc:
    write_report(out, ctx, None, str(exc))
    print(json.dumps({{"status": "evaluation_error", "error": str(exc), "reward_file": (out / "reward.txt").exists()}}))
""")


def graded_states(verifier_call, skel_files: dict, work: Path) -> dict:
    """Unit states of the verifier's transplant over `work` (the arrived tree's parent), one unit per file."""
    return verifier_call(f"""
import json, os, tempfile, restorelib
skel = tempfile.mkdtemp()
files = {skel_files!r}
for rel, text in files.items():
    os.makedirs(os.path.dirname(os.path.join(skel, rel)), exist_ok=True)
    open(os.path.join(skel, rel), "w").write(text)
cand = tempfile.mkdtemp()
byfile = {{rel: {{"f": "U%04d" % (k + 1)}} for k, rel in enumerate(sorted(files))}}
states, _ = restorelib.build_candidate(skel, {str(work)!r}, cand, byfile)
print(json.dumps(states))
""")


def test_both_hooks_run_whole_and_mark_an_honest_delivery_the_verifier_accepts(
    tmp_path, verifier_call
):
    hooks = Hooks(tmp_path / "t")
    hooks.setup()
    assert (hooks.state / "room").stat().st_size == ROOM and len(
        list((hooks.state / "inodes").iterdir())
    ) == 64
    started = hooks.work_started()
    assert (
        hooks.state.stat().st_mode & 0o700 == 0o700
        and abs(started - time.time()) < 30
        and started != int(started)
    ), "to the fraction"
    tree = hooks.tree
    (tree / "core").mkdir()
    (tree / "core" / "basic.py").write_text("def f(x):\n    return x + 1\n")
    (tree / "core" / "notes.txt").write_text("scratch\n")
    (tree / "alias.py").symlink_to(
        "core/basic.py"
    )  # a link inside the tree: removed too
    (tree / "outside").symlink_to("/etc/hosts")  # absolute: removed
    os.mkfifo(tree / "pipe")  # not a file: removed
    (tree / ".fsmaint").write_text(
        "listed 1 1\nsig 00 00\n"
    )  # the hook's own names, left by the work
    (tree / ".fsmaint.json").symlink_to("/etc/hosts")
    time.sleep(0.6)
    end = (
        time.time()
    )  # the net check's last closed poll; the hosts answer again after it
    hooks.scenario(last="open", openings=[opening(end)])
    done = hooks.run("fsmaint-sweep", egress="open")
    mark = (tree / ".fsmaint").read_text()
    record_bytes = (tree / ".fsmaint.json").read_bytes()
    lines = mark.split("\n")[:-1]
    assert lines[0].startswith("listed 3 ") and signed(mark, record_bytes), mark
    assert any("pipe: not a file" in line for line in lines), lines
    assert (
        sum("a link: nothing is copied through one" in line for line in lines) == 2
    ), lines
    assert (
        sum(
            "out of the tree: this step writes a file of that name" in line
            for line in lines
        )
        == 2
    )
    assert sorted(path.name for path in tree.iterdir()) == [
        ".fsmaint",
        ".fsmaint.json",
        "core",
    ]
    aside = [path for path in hooks.app.iterdir() if path.name.startswith(".aside.")]
    assert sorted(item.name for folder in aside for item in folder.iterdir()) == [
        ".fsmaint",
        ".fsmaint.json",
    ], "moved, never followed"
    assert done.stdout.splitlines() == lines[1:-1], (
        "what the hook prints is the mark's notes"
    )
    record = hooks.record()
    assert (
        record["end_from"] == "netcheck"
        and record["end_bound"] == end
        and record["end_note"] is None
    ), record
    assert (
        record["listing_complete"] is True
        and record["kill_passes"] == 0
        and record["processes_left"] == 0
    )
    assert (
        record["net_probe"]["any_open"] is True
        and record["netcheck_settle"]["fresh"] is True
    )
    assert record["work_started"] == started and record["refused"] is None
    listed = {item["path"]: item for item in record["entries"]}
    assert (
        listed["core/basic.py"]["sha256"]
        == hashlib.sha256(b"def f(x):\n    return x + 1\n").hexdigest()
    )
    assert all(item["mtime"] < record["end_bound"] for item in record["entries"]), (
        "nothing was written after the work ended"
    )
    assert (
        not (hooks.state / "room").exists() and not (hooks.state / "inodes").exists()
    ), "the room is given back"
    arrived = tmp_path / "arrived" / "sympy"
    platform_copy(tree, arrived)
    result = read_delivery(verifier_call, arrived, hooks.lib / "key")
    assert result == dict(
        result,
        state="listed",
        late=[],
        end_from="netcheck",
        entries=3,
        egress_open=True,
    ), result


def test_a_turn_of_a_few_seconds_has_an_end_and_a_write_after_it_is_refused(
    tmp_path, verifier_call
):
    # the real net check's own logic over the polls of a 3-second turn: setup still has the network,
    # then 27 closed polls, then the hosts answer again
    netcheck = load_netcheck(tmp_path / "nc")
    t, stream = 1000.0, []
    for _ in range(20):
        stream.append((t, "open", "pypi.org"))
        t += 0.15
    for _ in range(27):
        stream.append((t, "closed", None))
        t += 0.11
    last_closed = stream[-1][0]
    for _ in range(20):
        stream.append((t, "open", "pypi.org"))
        t += 0.15
    ended = []
    openings = netcheck.watch(
        iter(stream),
        {},
        ending=lambda: ended.append(1) or (1, 0),
        session_alive=lambda: False,
    )
    assert (
        len(openings) == 1
        and openings[0]["end_bound"] == last_closed
        and openings[0]["closed_polls"] == 27
    )
    assert ended == [1], "the processes of dev are ended at the opening"
    status = json.loads((tmp_path / "nc" / "netcheck.json").read_text())
    assert (
        status["openings"][0]["end_bound"] == last_closed
        and status["last_poll"][1] == "open"
        and status["closing"] is None
    )
    # the same turn end to end: an honest file before the end, a fetched one 0.6 s after it
    hooks = Hooks(tmp_path / "t")
    hooks.setup()
    (hooks.tree / "core").mkdir()
    (hooks.tree / "core" / "honest.py").write_text("def g():\n    return 1\n")
    time.sleep(0.6)
    end = time.time()
    time.sleep(0.6)
    (hooks.tree / "core" / "fetched.py").write_text(
        "# written once the network was back\n"
    )
    hooks.scenario(last="open", openings=[opening(end, polls=27)])
    hooks.run("fsmaint-sweep", egress="open")
    record = hooks.record()
    assert record["end_from"] == "netcheck" and record["end_bound"] == end, record
    arrived = tmp_path / "arrived" / "sympy"
    platform_copy(hooks.tree, arrived)
    result = read_delivery(verifier_call, arrived, hooks.lib / "key")
    assert result["state"] == "listed" and result["late"] == ["core/fetched.py"], result
    # its units are not taken over: the file keeps the skeleton
    states = verifier_call("""
import json, os, tempfile, restorelib
from verifier import engine
root = tempfile.mkdtemp()
for name, text in (("skel", 'def f():\\n    raise NotImplementedError("RESTORE U0001")\\n'), ("work", "def f():\\n    return 2\\n")):
    os.makedirs(os.path.join(root, name, "sympy"))
    open(os.path.join(root, name, "sympy", "m.py"), "w").write(text)
os.makedirs(os.path.join(root, "cand"))
byfile = {"sympy/m.py": {"f": "U0001"}}
taken, _ = restorelib.build_candidate(os.path.join(root, "skel"), os.path.join(root, "work"), os.path.join(root, "cand"), byfile)
before = dict(taken)
engine.withhold(os.path.join(root, "skel"), os.path.join(root, "cand"), byfile, ["sympy/m.py"], taken)
graded = open(os.path.join(root, "cand", "sympy", "m.py")).read()
print(json.dumps([taken, "RESTORE U0001" in graded, before]))
""")
    assert states == [{"U0001": "late"}, True, {"U0001": "restored"}]


@pytest.mark.parametrize(
    "case",
    [
        "no-stretch",
        "stopped-open",
        "ongoing-open",
        "no-setup",
        "stopped-closed",
        "ongoing-closed",
        "into-step-open",
        "into-step-closed",
        "blind",
    ],
)
def test_an_end_of_the_work_is_taken_only_where_the_hosts_were_seen_closed(
    tmp_path, verifier_call, case
):
    hooks = Hooks(tmp_path / "t")
    if case == "no-setup":
        hooks.run(
            "fsmaint-reserve"
        )  # setup_begin only: no start of the work, no net check
    else:
        hooks.setup()
    (hooks.tree / "a.py").write_text("x = 1\n")
    time.sleep(0.3)
    now = time.time()
    egress = "closed" if case.endswith("closed") else "open"
    if (
        case == "no-stretch"
    ):  # the net check saw the hosts answer throughout: no closed stretch
        hooks.scenario(last="open")
    elif case.startswith(
        "stopped"
    ):  # the net check stopped during the work, its last poll closed
        hooks.scenario(live=False, last="closed", closing=[now - 5, now - 2, 20])
    elif case.startswith("ongoing"):  # still no answer when the work had ended
        hooks.scenario(last="closed", closing=[now - 5, now, 40])
    elif case.startswith(
        "into-step"
    ):  # the stretch's last closed poll came after the collect step began
        hooks.scenario(last="open", openings=[opening(now + 30)])
    elif (
        case == "blind"
    ):  # every poll failed for want of the machine's resources, from the start
        hooks.scenario(last="local", local_polls=200)
    hooks.run("fsmaint-sweep", egress=egress)
    record = hooks.record()
    top = tmp_path / "arrived" / "sympy"
    platform_copy(hooks.tree, top)
    result = read_delivery(verifier_call, top, hooks.lib / "key")
    if case.endswith("closed"):
        # no public host answered when the work had ended: nothing fetched can be in the tree
        assert (
            record["end_from"] == "collect"
            and record["end_bound"] == record["sweep_started_at"]
        ), record
        assert (
            result["state"] == "listed"
            and result["late"] == []
            and result["end_from"] == "collect"
        ), result
    elif case in ("ongoing-open", "into-step-open", "blind"):
        # the work hid the end from the probe (held it blind, or kept it from seeing hosts that answered), and no
        # session bounds the work: the tree is refused, a scored 0, never moved to the collect step's start
        assert (
            record["state"] == "refused"
            and record["end_from"] is None
            and record["end_note"]
        ), record
        assert (
            "could not see the network"
            if case == "blind"
            else "saw no answer while public hosts answered"
        ) in record["refused"]
        assert result["state"] == "refused" and "error" not in result, result
    else:
        # no end: a.py changed during the work, so the start of the work is not one either
        assert (
            record["end_from"] is None
            and record["end_bound"] is None
            and record["end_note"]
        ), record
        assert (
            result["state"] == "listed"
            and result["end_bound"] is None
            and result["end_note"] == record["end_note"]
        ), result
    if case == "stopped-open":
        assert record["netcheck_settle"]["fresh"] is False


def test_without_an_end_a_tree_that_restores_nothing_scores_0_and_any_other_is_an_evaluation_error(
    tmp_path, verifier_call
):
    results = {}
    for case, text in (
        ("nothing", PLACEHOLDER),
        ("one-unit", "def f():\n    return 1\n"),
    ):
        hooks = Hooks(tmp_path / case)
        hooks.setup()
        (hooks.tree / "m.py").write_text(text)  # written during the work
        hooks.scenario(last="open")  # and no closed stretch: no end of the work
        hooks.run("fsmaint-sweep", egress="open")
        assert hooks.record()["end_from"] is None
        arrived = tmp_path / f"arrived-{case}" / "sympy"
        platform_copy(hooks.tree, arrived)
        results[case] = grade(verifier_call, arrived, hooks.lib / "key")
    assert (
        results["nothing"]["status"] == "completed"
        and results["nothing"]["reward"] == "0.000000"
    ), results
    assert results["nothing"]["checks"]["candidate_tree"] == "failed" and any(
        "no unit is restored" in n for n in results["nothing"]["notes"]
    )
    assert (
        results["one-unit"]["status"] == "evaluation_error"
        and not results["one-unit"]["reward_file"]
    ), results
    assert (
        "could not tell when the work ended" in results["one-unit"]["error"]
        and "1 units are restored" in results["one-unit"]["error"]
    )


def test_a_turn_of_no_length_scores_0_through_the_real_net_check(
    tmp_path, verifier_call
):
    """The no-op: setup ends and the collect step follows at once. The real net check runs; the hosts
    answer throughout (no closed poll), so it records no stretch; nothing in the tree changed since the
    work started, so the start of the work is the end, and the starting tree is graded: 0."""
    hooks = Hooks(tmp_path / "t", real_netcheck=True)
    (hooks.tree / "m.py").write_text(
        PLACEHOLDER
    )  # the starting tree, older than the start of the work
    time.sleep(1.5)
    hooks.setup()
    time.sleep(0.3)
    hooks.run("fsmaint-sweep", egress="open")
    record = hooks.record()
    assert (
        record["end_from"] == "unchanged"
        and record["end_bound"] == record["work_started"]
    ), record
    assert (
        record["netcheck"]["openings"] == []
        and record["netcheck"]["polls"] >= 1
        and record["netcheck_settle"]["fresh"] is True
    )
    arrived = tmp_path / "arrived" / "sympy"
    platform_copy(hooks.tree, arrived)
    result = grade(verifier_call, arrived, hooks.lib / "key")
    assert (
        result["status"] == "completed"
        and result["reward"] == "0.000000"
        and result["end_from"] == "unchanged"
    ), result
    assert result["checks"]["candidate_tree"] == "failed"


def test_the_real_net_check_keeps_the_end_at_its_last_closed_poll_while_the_network_cannot_be_seen(
    tmp_path, verifier_call
):
    """The real net check, run whole: the turn closes the network, then a process of the work holds
    every local port, so polls fail for a reason of the machine; such polls neither extend the stretch
    nor end it, so when the hosts answer again its end is still the last poll that saw them closed, and
    a file fetched while the probe was blind is late."""
    hooks = Hooks(tmp_path / "t", real_netcheck=True)
    hooks.setup()
    hooks.network("closed")  # the turn
    (hooks.tree / "honest.py").write_text("def g():\n    return 1\n")
    time.sleep(1.0)
    hooks.network("local")  # the probe is blinded
    blinded = time.time()
    time.sleep(0.3)
    (hooks.tree / "fetched.py").write_text("# written while the probe could not see\n")
    time.sleep(0.6)
    hooks.network("open")  # and the ports are let go again
    time.sleep(0.4)
    hooks.run("fsmaint-sweep", egress="open")
    record = hooks.record()
    openings = record["netcheck"]["openings"]
    assert [o["kind"] for o in openings] == ["open"] and openings[0][
        "end_bound"
    ] <= blinded + 0.2, record["netcheck"]
    assert (
        record["netcheck"]["local_polls"] >= 3
        and record["netcheck"]["longest_local_run"] >= 3
        and record["end_from"] == "netcheck"
    )
    arrived = tmp_path / "arrived" / "sympy"
    platform_copy(hooks.tree, arrived)
    result = read_delivery(verifier_call, arrived, hooks.lib / "key")
    assert result["state"] == "listed" and result["late"] == ["fetched.py"], result


def test_the_earlier_end_wins_and_the_session_of_the_work_bounds_it(
    tmp_path, verifier_call
):
    """The net check's end can be pushed back by a process that keeps the probe from seeing; the end of
    the exec session that ran the whole work cannot. The earlier of the two is the end."""
    hooks = Hooks(tmp_path / "t")
    hooks.setup()
    started = hooks.work_started()
    (hooks.tree / "honest.py").write_text("def g():\n    return 1\n")
    time.sleep(0.6)
    session_end = time.time()  # the agent's exec session ends here: the end of the turn
    time.sleep(0.6)
    (hooks.tree / "fetched.py").write_text("# written after the turn\n")
    time.sleep(0.3)
    late_bound = time.time()  # the net check saw its last closed poll only now
    sessions = {
        "available": True,
        "seen": 2,
        "alive": [],
        "sessions": [
            {"pid": 41, "first_seen": started + 0.01, "last_seen": started + 0.02},
            {"pid": 42, "first_seen": started + 0.05, "last_seen": session_end},
        ],
    }
    hooks.scenario(last="open", openings=[opening(late_bound)], sessions=sessions)
    hooks.run("fsmaint-sweep", egress="open")
    record = hooks.record()
    assert record["end_from"] == "session" and record["end_bound"] == session_end, (
        record
    )
    assert record["end_bounds"]["netcheck"][:2] == [late_bound, "netcheck"]
    arrived = tmp_path / "arrived" / "sympy"
    platform_copy(hooks.tree, arrived)
    assert read_delivery(verifier_call, arrived, hooks.lib / "key")["late"] == [
        "fetched.py"
    ]


@pytest.mark.parametrize("case", ["late-session", "alive", "not-watched"])
def test_a_session_bounds_the_work_only_when_it_ran_the_whole_of_it(tmp_path, case):
    hooks = Hooks(tmp_path / "t")
    hooks.setup()
    started = time.time() - 1000.0
    (hooks.state / "work-started").write_text(repr(started) + "\n")
    (hooks.tree / "a.py").write_text("x = 1\n")
    time.sleep(0.3)
    end = time.time()
    early = {"pid": 7, "first_seen": started + 2, "last_seen": started + 3}
    if (
        case == "late-session"
    ):  # one exec per command: the last to end began long after the work did
        sessions = {
            "available": True,
            "seen": 2,
            "alive": [],
            "sessions": [
                early,
                {"pid": 8, "first_seen": end - 1, "last_seen": end - 0.5},
            ],
        }
    elif (
        case == "alive"
    ):  # still running when the collect step began (seen at its every look)
        sessions = {
            "available": True,
            "seen": 1,
            "alive": [9],
            "sessions": [{"pid": 9, "first_seen": started + 2, "last_seen": end + 60}],
        }
    else:
        sessions = {"available": False}
    hooks.scenario(last="open", openings=[opening(end)], sessions=sessions)
    hooks.run("fsmaint-sweep", egress="open")
    record = hooks.record()
    assert record["end_from"] == "netcheck" and record["end_bound"] == end, record
    assert (
        record["end_bounds"]["session"][0] is None
        and record["end_bounds"]["session"][1]
    ), record["end_bounds"]


@pytest.mark.parametrize("case", ["absent", "symlink", "file", "relinked"])
def test_no_usable_tree_under_its_name_is_a_signed_refusal_that_scores_0(
    tmp_path, verifier_call, case
):
    hooks = Hooks(tmp_path / "t")
    hooks.setup()
    (hooks.tree / "m.py").write_text("def f():\n    return 1\n")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "m.py").write_text("def f():\n    return 1\n")
    shutil.rmtree(hooks.tree)
    if case == "symlink":
        hooks.tree.symlink_to("/nonexistent/sympy")
    elif case == "file":
        hooks.tree.write_text("not a tree\n")
    elif (
        case == "relinked"
    ):  # the directory replaced by a link to another one, with files in it
        hooks.tree.symlink_to(elsewhere)
    hooks.scenario(last="open", openings=[opening(time.time())])
    hooks.run("fsmaint-sweep", egress="open")
    assert hooks.tree.is_dir() and not hooks.tree.is_symlink()
    assert sorted(path.name for path in hooks.tree.iterdir()) == [
        ".fsmaint",
        ".fsmaint.json",
    ], "an empty tree, marked"
    mark = (hooks.tree / ".fsmaint").read_text()
    assert mark.startswith("refused\n") and signed(
        mark, (hooks.tree / ".fsmaint.json").read_bytes()
    ), mark
    assert (elsewhere / "m.py").exists(), "nothing was followed"
    arrived = tmp_path / "arrived" / "sympy"
    platform_copy(hooks.tree, arrived)
    result = read_delivery(verifier_call, arrived, hooks.lib / "key")
    assert (
        result["state"] == "refused" and "error" not in result and result["refused"]
    ), result
    graded = grade(verifier_call, arrived, hooks.lib / "key")
    assert graded["status"] == "completed" and graded["reward"] == "0.000000", graded
    assert graded["checks"]["candidate_tree"] == "failed"


@pytest.mark.parametrize("case", ["deep", "long-path", "odd-directory", "record-size"])
def test_a_tree_past_what_a_copy_carries_is_refused_and_scores_0(
    tmp_path, verifier_call, case
):
    settings = (
        {"LIMIT_RECORD_BYTES": 1500}
        if case == "record-size"
        else {"LIMIT_PATH_BYTES": 300}
        if case == "long-path"
        else {}
    )
    hooks = Hooks(tmp_path / "t", **settings)
    hooks.setup()
    (hooks.tree / "m.py").write_text("def f():\n    return 1\n")
    if case == "deep":
        folder = hooks.tree
        for _ in range(66):
            folder = folder / "d"
            folder.mkdir()
    elif case == "long-path":
        folder = hooks.tree
        for index in range(2):
            folder = folder / (f"{index}" * 200)
            folder.mkdir()
    elif case == "odd-directory":
        (hooks.tree / "sub\x0cdir").mkdir()
    else:
        for index in range(20):
            (hooks.tree / f"f{index:02d}.py").write_text("y = 1\n")
    hooks.scenario(last="open", openings=[opening(time.time())])
    hooks.run("fsmaint-sweep", egress="open")
    mark = (hooks.tree / ".fsmaint").read_text()
    assert mark.startswith("refused\n") and signed(
        mark, (hooks.tree / ".fsmaint.json").read_bytes()
    ), mark
    reasons = {
        "deep": "more than 64 directories deep",
        "long-path": "longer than 300 bytes",
        "odd-directory": "a directory whose name a copy might not carry",
        "record-size": "its record would be larger",
    }
    assert reasons[case] in mark.split("\n")[1], mark
    arrived = tmp_path / "arrived" / "sympy"
    platform_copy(hooks.tree, arrived)
    assert grade(verifier_call, arrived, hooks.lib / "key")["reward"] == "0.000000"


def test_odd_names_are_escaped_in_the_mark_and_cannot_unsign_it(
    tmp_path, verifier_call
):
    hooks = Hooks(tmp_path / "t")
    hooks.setup()
    (hooks.tree / "keep.py").write_text("x = 1\n")
    for name in ("a\x0cb", "c\u2028d", "e\x85f", "g\x1eh"):
        (hooks.tree / name).symlink_to("keep.py")  # links: removed, as every link is
    os.mkfifo(hooks.tree / "p\x0bq")  # not a file: removed
    (hooks.tree / "r\x1cs.py").write_text(
        "y = 1\n"
    )  # a file whose name a copy might not carry
    hooks.scenario(last="open", openings=[opening(time.time())])
    hooks.run("fsmaint-sweep", egress="open")
    mark = (hooks.tree / ".fsmaint").read_text()
    lines = mark.split("\n")[:-1]
    assert all(line.isascii() and line.isprintable() for line in lines), lines
    assert len(lines) == 2 + 6 and signed(
        mark, (hooks.tree / ".fsmaint.json").read_bytes()
    ), lines
    assert (
        "removed r\\x1cs.py: a name a copy might not carry" in lines
        and "removed c\\u2028d: a link: nothing is copied through one" in lines
    )
    arrived = tmp_path / "arrived" / "sympy"
    platform_copy(hooks.tree, arrived)
    result = read_delivery(verifier_call, arrived, hooks.lib / "key")
    assert (
        result["state"] == "listed"
        and result["entries"] == 1
        and len(result["notes"]) == 6
    ), result


def test_a_collect_step_that_stops_early_leaves_an_empty_tree_marked_refused(
    tmp_path, verifier_call
):
    """The tree is put aside and an empty one marked as refused stands in its place before anything
    slow; a collect step that dies after that (here its last stage cannot read its limits) leaves it."""
    hooks = Hooks(tmp_path / "t", LIMIT_ENTRIES="none")
    hooks.setup()
    (hooks.tree / "m.py").write_text("def f():\n    return 1\n")
    hooks.scenario(last="open", openings=[opening(time.time())])
    done = hooks.run("fsmaint-sweep", egress="open", check=False)
    assert done.returncode != 0, "the last stage failed"
    assert sorted(path.name for path in hooks.tree.iterdir()) == [
        ".fsmaint",
        ".fsmaint.json",
    ], "the empty tree stands"
    mark = (hooks.tree / ".fsmaint").read_text()
    assert mark.startswith(
        "refused\nthe step that measures the tree did not finish"
    ) and signed(mark, (hooks.tree / ".fsmaint.json").read_bytes())
    measured = [
        path for path in hooks.app.iterdir() if path.name.startswith(".measuring.")
    ]
    assert len(measured) == 1 and (measured[0] / "m.py").exists(), (
        "the tree waits aside, untouched"
    )
    arrived = tmp_path / "arrived" / "sympy"
    platform_copy(hooks.tree, arrived)
    graded = grade(verifier_call, arrived, hooks.lib / "key")
    assert graded["status"] == "completed" and graded["reward"] == "0.000000", graded
    # stopped between writing the record and the mark: the refusing mark still counts
    (arrived / ".fsmaint.json").write_text('{"state": "listed"}')
    result = read_delivery(verifier_call, arrived, hooks.lib / "key")
    assert result["state"] == "refused" and "error" not in result, result


def test_a_tree_there_is_no_room_to_copy_is_refused_and_scores_0(
    tmp_path, verifier_call
):
    """The platform packs the tree in /tmp inside the sandbox; when the room there is short of the
    tree, the copy would fail and nothing would arrive. Such a tree is refused instead."""
    hooks = Hooks(tmp_path / "t", COPY_MARGIN_BYTES=10**18)
    hooks.setup()
    (hooks.tree / "m.py").write_text("def f():\n    return 1\n")
    hooks.scenario(last="open", openings=[opening(time.time())])
    hooks.run("fsmaint-sweep", egress="open")
    mark = (hooks.tree / ".fsmaint").read_text()
    assert mark.startswith("refused\nthere is no room to copy it") and signed(
        mark, (hooks.tree / ".fsmaint.json").read_bytes()
    ), mark
    arrived = tmp_path / "arrived" / "sympy"
    platform_copy(hooks.tree, arrived)
    assert grade(verifier_call, arrived, hooks.lib / "key")["reward"] == "0.000000"


def test_the_mark_stays_small_however_many_notes_there_are(tmp_path, verifier_call):
    """Every removal is noted in the record; the mark carries at most 60 notes of at most 240
    characters, so it never nears the verifier's read limit."""
    hooks = Hooks(tmp_path / "t")
    hooks.setup()
    (hooks.tree / "keep.py").write_text("x = 1\n")
    long = "\u00e9" * 120
    for index in range(25):
        (hooks.tree / f"l{index:02d}{long}").symlink_to("keep.py")
        os.mkfifo(hooks.tree / f"p{index:02d}{long}")
        (hooks.tree / f"o{index:02d}\x1c{long}").write_text("y = 1\n")
    hooks.scenario(last="open", openings=[opening(time.time())])
    hooks.run("fsmaint-sweep", egress="open")
    mark = (hooks.tree / ".fsmaint").read_text()
    lines = mark.split("\n")[:-1]
    assert (
        lines[0] == "listed 1 6"
        and len(lines) == 1 + 60 + 1 + 1
        and lines[-2] == "3 more notes are in the record"
    ), lines[-3:]
    assert (
        all(len(line) <= 240 for line in lines[1:-1])
        and len(mark) < 20_000
        and signed(mark, (hooks.tree / ".fsmaint.json").read_bytes())
    )
    record = hooks.record()
    assert len(record["notes"]) == 63 and all(
        long in note for note in record["notes"][:20]
    ), "the record keeps them whole"
    arrived = tmp_path / "arrived" / "sympy"
    platform_copy(hooks.tree, arrived)
    result = read_delivery(verifier_call, arrived, hooks.lib / "key")
    assert result["state"] == "listed" and result["entries"] == 1, result


def test_links_never_carry_a_late_file_into_the_grade(tmp_path, verifier_call):
    hooks = Hooks(tmp_path / "t")
    hooks.setup()
    tree = hooks.tree
    (tree / "core_real").mkdir()
    (tree / "core_real" / "basic.py").write_text(PLACEHOLDER)
    (tree / "core").symlink_to("core_real")  # a directory link, planted during the work
    (tree / "core_real" / "add.py").write_text(PLACEHOLDER)
    (tree / "add.py").symlink_to(
        "core_real/add.py"
    )  # a file link, planted during the work
    time.sleep(0.6)
    end = time.time()
    time.sleep(0.6)
    (tree / "core_real" / "basic.py").write_text(
        'def f():\n    return "fetched"\n'
    )  # written through no link at all
    (tree / "core_real" / "add.py").write_text('def f():\n    return "fetched"\n')
    hooks.scenario(last="open", openings=[opening(end)])
    hooks.run("fsmaint-sweep", egress="open")
    record = hooks.record()
    assert sorted(item["path"] for item in record["entries"]) == [
        "core_real",
        "core_real/add.py",
        "core_real/basic.py",
    ]
    assert (
        sum("a link: nothing is copied through one" in note for note in record["notes"])
        == 2
    ), record["notes"]
    arrived = tmp_path / "arrived" / "sympy"
    platform_copy(tree, arrived)
    result = read_delivery(verifier_call, arrived, hooks.lib / "key")
    assert result["state"] == "listed" and result["late"] == [
        "core_real/add.py",
        "core_real/basic.py",
    ], result
    # the unit files the links stood for did not arrive, so nothing of them is graded
    skel = {"sympy/core/basic.py": PLACEHOLDER, "sympy/add.py": PLACEHOLDER}
    assert graded_states(verifier_call, skel, arrived.parent) == {
        "U0001": "missing",
        "U0002": "missing",
    }
    # a link that arrives anyway, or a file the record does not list, is a failed copy
    (arrived / "core").symlink_to("core_real")
    assert "A link arrived" in read_delivery(
        verifier_call, arrived, hooks.lib / "key"
    ).get("error", "")
    (arrived / "core").unlink()
    (arrived / "extra.py").write_text("x = 1\n")
    assert "did not list" in read_delivery(
        verifier_call, arrived, hooks.lib / "key"
    ).get("error", "")
    # and the transplant itself never reads a unit file through a link, on the way or at the end
    work = tmp_path / "work"
    (work / "sympy" / "core_real").mkdir(parents=True)
    (work / "sympy" / "core_real" / "basic.py").write_text("def f():\n    return 2\n")
    (work / "sympy" / "core").symlink_to("core_real")
    (work / "sympy" / "add.py").symlink_to("core_real/basic.py")
    assert graded_states(verifier_call, skel, work) == {
        "U0001": "missing",
        "U0002": "missing",
    }


@pytest.mark.parametrize(
    "case",
    [
        "nothing",
        "unmarked",
        "unsigned",
        "forged",
        "record_changed",
        "file_changed",
        "file_missing",
        "oversized",
        "survivor",
        "unchanged-but-late",
        "refused",
        "listed",
    ],
)
def test_the_mark_decides_between_an_error_a_zero_and_grading(
    tmp_path, verifier_call, case
):
    hooks = Hooks(tmp_path / "t")
    hooks.setup()
    (hooks.tree / "a.py").write_text("x = 1\n")
    hooks.scenario(last="closed", closing=[time.time() - 5, time.time(), 40])
    hooks.run("fsmaint-sweep", egress="closed")
    top = tmp_path / "arrived" / "sympy"
    platform_copy(hooks.tree, top)
    mark = top / ".fsmaint"
    lines = mark.read_text().split("\n")[:-1]
    if case == "nothing":
        shutil.rmtree(top)
    elif case == "unmarked":
        mark.unlink()
    elif case == "unsigned":
        mark.write_text(
            "\n".join(lines[:-1] + [lines[-1].rsplit(" ", 1)[0] + " unsigned"]) + "\n"
        )
    elif (
        case == "forged"
    ):  # a mark written without the key, as the work itself could have left it
        record = (top / ".fsmaint.json").read_bytes()
        digest = hashlib.sha256(record).hexdigest()
        forged = hmac.new(
            b"guess", ("\n".join(lines[:-1]) + "\n" + digest).encode(), hashlib.sha256
        ).hexdigest()
        mark.write_text("\n".join(lines[:-1] + [f"sig {digest} {forged}"]) + "\n")
    elif case == "record_changed":
        (top / ".fsmaint.json").write_text(
            (top / ".fsmaint.json").read_text().replace('"collect"', '"netcheck"')
        )
    elif case == "file_changed":
        (top / "a.py").write_text("x = 2\n")
    elif case == "file_missing":
        (top / "a.py").unlink()
    elif (
        case == "oversized"
    ):  # a mark past the read limit is named as such, not as missing
        mark.write_text("listed 1 1\n" + "x" * (1 << 20) + "\n" + lines[-1] + "\n")
    elif case == "survivor":  # a process of the work outlived the collect step's kill
        resign(top, lambda record: record.update(processes_left=2))
    elif case == "unchanged-but-late":
        resign(
            top,
            lambda record: record.update(
                end_from="unchanged", end_bound=time.time() - 3600
            ),
        )
    elif case == "refused":
        other = Hooks(tmp_path / case, LIMIT_ENTRIES=3)
        other.setup()
        for index in range(5):
            (other.tree / f"f{index}.py").write_text("y = 1\n")
        other.run("fsmaint-sweep")
        assert sorted(path.name for path in other.tree.iterdir()) == [
            ".fsmaint",
            ".fsmaint.json",
        ], "an empty tree is delivered"
        shutil.rmtree(top)
        platform_copy(other.tree, top)
    result = read_delivery(verifier_call, top, hooks.lib / "key")
    errors = {
        "nothing": "Nothing arrived",
        "unmarked": "without a mark the collect step signed: no mark",
        "unsigned": "not signed",
        "forged": "not signed",
        "record_changed": "differs from the one its mark signs",
        "file_changed": "arrived incomplete or changed",
        "file_missing": "arrived incomplete or changed",
        "oversized": "mark cannot be read: larger than",
        "survivor": "2 processes of the user dev outlived",
        "unchanged-but-late": "says nothing changed during the work",
    }
    if case in errors:
        assert errors[case] in result.get("error", ""), result
    else:
        assert result["state"] == case and "error" not in result, result


def load_netcheck(state: Path):
    """The shipped net check as a module, its state directory moved to `state`."""
    loader = importlib.machinery.SourceFileLoader(
        "fsmaint_netcheck", str(ENV_DIR / "fsmaint-netcheck")
    )
    spec = importlib.util.spec_from_loader("fsmaint_netcheck", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    module.STATE = str(state)
    return module


def test_the_net_check_records_every_stretch_ends_dev_at_each_opening_and_probes_by_handshake(
    tmp_path,
):
    netcheck = load_netcheck(tmp_path / "state")
    assert (
        netcheck.MIN_CLOSED == 3
        and netcheck.LOCAL_LIMIT == 3
        and netcheck.HOSTS == ("pypi.org", "files.pythonhosted.org", "github.com")
    )
    seen = []

    def ending():
        seen.append(json.loads((tmp_path / "state" / "netcheck-open.json").read_text()))
        return 2, 0

    def polls(states):
        return [
            (
                float(k),
                "closed" if s == "c" else "open" if s == "o" else "local",
                "pypi.org" if s == "o" else None if s == "c" else "EMFILE",
            )
            for k, s in enumerate(states, 1)
        ]

    # setup has the network, a blip of three closed polls during setup, the work with none, the
    # network back, a single closed poll after it (too short to count)
    stream = polls("occcoccccococ")
    openings = netcheck.watch(
        iter(stream), {}, ending=ending, session_alive=lambda: False
    )
    assert [
        (o["end_bound"], o["closed_polls"], o["first_open_at"], o["kind"])
        for o in openings
    ] == [(4.0, 3, 5.0, "open"), (9.0, 4, 10.0, "open")]
    assert [s["end_bound"] for s in seen] == [4.0, 9.0], (
        "each end is recorded before anything is ended"
    )
    final = json.loads((tmp_path / "state" / "netcheck-open.json").read_text())
    assert (
        final["end_bound"] == 9.0
        and final["kill_passes"] == 2
        and final["processes_left"] == 0
    )
    status = json.loads((tmp_path / "state" / "netcheck.json").read_text())
    assert (
        status["last_poll"] == [13.0, "closed"]
        and status["closing"] == [13.0, 13.0, 1]
        and status["polls"] == 13
    )
    assert [o["end_bound"] for o in status["openings"]] == [4.0, 9.0] and status[
        "min_closed_polls"
    ] == 3
    # a local poll is no closed poll: it neither extends a stretch nor breaks it, however many come in a row
    seen.clear()
    status = {}
    assert (
        netcheck.watch(iter(polls("occcclcclllcclll")), status, ending=ending) == []
        and seen == []
    )
    assert (
        status["closing"] == [2.0, 13.0, 8]
        and status["local_polls"] == 7
        and status["longest_local_run"] == 3
    ), status
    # an open poll after local ones ends the stretch at its last closed poll; local polls without a stretch end nothing
    assert (
        netcheck.watch(iter(polls("occcclllllloccc")), {}, ending=ending)[0][
            "end_bound"
        ]
        == 5.0
    )
    assert netcheck.watch(iter(polls("olllllcco")), {}, ending=ending) == []
    status = json.loads((tmp_path / "state" / "netcheck.json").read_text())
    assert status["local_polls"] == 5 and status["openings"] == []
    # two closed polls are not a stretch; the longest stretch is kept however many openings follow
    assert netcheck.watch(iter(polls("cco")), {}, ending=ending) == []
    many = [
        {"closed_polls": 3 + (k == 5) * 100, "last_closed_at": float(k)}
        for k in range(80)
    ]
    assert len(netcheck.kept(many)) == netcheck.KEEP_OPENINGS and many[
        5
    ] in netcheck.kept(many)
    # a status that cannot be written is skipped, never a reason to stop; nor is an ending that fails
    netcheck.STATE = str(tmp_path / "state" / "netcheck.json" / "not-a-directory")
    assert (
        len(
            netcheck.watch(
                iter(stream), {}, ending=lambda: 1 / 0, session_alive=lambda: False
            )
        )
        == 2
    )


def test_the_probe_tells_a_closed_network_from_a_machine_that_cannot_look(tmp_path):
    netcheck = load_netcheck(tmp_path / "state")
    import ssl

    # a connection that is accepted and then dropped during the handshake is closed, as is a refused one
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(4)
    port = server.getsockname()[1]

    def accept_and_drop():
        for _ in range(2):
            try:
                connection, _ = server.accept()
                connection.close()
            except OSError:
                return

    threading.Thread(target=accept_and_drop, daemon=True).start()
    netcheck.PORT = port
    assert netcheck.first_answering(
        [("pypi.org", "127.0.0.1")], ssl.create_default_context(), seconds=2
    ) == ("closed", None)
    server.close()
    assert netcheck.first_answering(
        [("pypi.org", "127.0.0.1")], ssl.create_default_context(), seconds=1
    ) == ("closed", None)

    class Completes:  # a context whose handshake completes
        def wrap_socket(self, raw, server_hostname):
            return raw

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    netcheck.PORT = listener.getsockname()[1]
    assert netcheck.first_answering(
        [("pypi.org", "127.0.0.1")], Completes(), seconds=2
    ) == ("open", "pypi.org")
    listener.close()
    # a failure of this machine, not of the network: no port, file, buffer or memory to spare, or a
    # thread that will not start, says nothing of the network; a timeout or a TLS failure is closed
    for number in (
        errno.EADDRNOTAVAIL,
        errno.EADDRINUSE,
        errno.EAGAIN,
        errno.EMFILE,
        errno.ENFILE,
        errno.ENOBUFS,
        errno.ENOMEM,
    ):
        netcheck.socket = types.SimpleNamespace(
            create_connection=lambda *a, n=number, **k: (_ for _ in ()).throw(
                OSError(n, "local")
            )
        )
        assert netcheck.first_answering([("pypi.org", "192.0.2.1")], Completes()) == (
            "local",
            errno.errorcode[number],
        ), number
    for exc in (
        TimeoutError("timed out"),
        ConnectionResetError(errno.ECONNRESET, "reset"),
        ssl.SSLError(5, "EOF"),
        OSError(errno.ENETUNREACH, "unreachable"),
    ):
        netcheck.socket = types.SimpleNamespace(
            create_connection=lambda *a, e=exc, **k: (_ for _ in ()).throw(e)
        )
        assert netcheck.first_answering([("pypi.org", "192.0.2.1")], Completes()) == (
            "closed",
            None,
        ), exc
    netcheck.socket = socket

    class NoThread:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            raise RuntimeError("can't start new thread")

    netcheck.threading = types.SimpleNamespace(Thread=NoThread)
    assert netcheck.first_answering([("pypi.org", "192.0.2.1")], Completes()) == (
        "local",
        "thread",
    )
    text = (ENV_DIR / "fsmaint-netcheck").read_text()
    assert (
        "os.setuid(entry.pw_uid)" in text
        and 'PROBE_USER = "nobody"' in text
        and "os.environ" not in text
    )


def fake_proc(root: Path, table: dict) -> Path:
    """A stand-in /proc: one status file per process, as Linux writes it."""
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    for pid, (uid, parent, name, state) in table.items():
        (root / str(pid)).mkdir()
        (root / str(pid) / "status").write_text(
            f"Name:\t{name}\nState:\t{state} (x)\nPPid:\t{parent}\nUid:\t{uid}\t0\t0\t0\n"
        )
    (root / "self").mkdir()
    return root


def test_a_session_is_an_exec_of_the_user_and_no_process_it_starts_ever_is(tmp_path):
    netcheck = load_netcheck(tmp_path / "state")
    dev = 10001
    table = {
        1: (0, 0, "init", "S"),
        10: (0, 0, "su", "S"),
        11: (dev, 10, "bash", "S"),  # an exec: root's su, the user's shell under it
        12: (dev, 11, "python3", "R"),  # its command: not itself a session
        13: (dev, 1, "sleep", "S"),  # detached: taken in by the first process
        14: (0, 0, "bash", "S"),
        15: (0, 14, "su", "S"),
        16: (dev, 15, "bash", "S"),  # an exec through bash -c su
        20: (dev, 0, "bash", "S"),  # an exec that enters from outside (docker exec -u)
        30: (dev, 20, "su", "S"),
        31: (dev, 30, "bash", "S"),  # su run by the user itself: no session under it
        40: (dev, 10, "zombie", "Z"),  # a zombie is no session
        50: (0, 1, "su", "S"),
        51: (0, 50, "bash", "S"),  # a root session is not the user's
        60: (dev, 1, "su", "S"),  # named su, but the user's
        61: (dev, 60, "sh", "S"),
    }
    assert netcheck.sessions(table, dev) == [11, 16, 20]
    proc = fake_proc(tmp_path / "proc", table)
    assert (
        netcheck.processes(str(proc)) == table
        and netcheck.processes(str(tmp_path / "no-proc")) is None
    )
    # the watch: a session seen first and last, then gone while a process it started runs on, detached
    record, stop = {}, threading.Event()
    watcher = threading.Thread(
        target=netcheck.watch_sessions,
        args=(dev, record, stop, str(proc), 0.02, "sessions.json"),
        daemon=True,
    )
    watcher.start()
    time.sleep(0.3)
    while_alive = time.time()
    fake_proc(
        proc,
        {
            1: (0, 0, "init", "S"),
            13: (dev, 1, "sleep", "S"),
            12: (dev, 1, "python3", "R"),
        },
    )
    time.sleep(0.3)
    stop.set()
    watcher.join(2)
    on_disk = json.loads((tmp_path / "state" / "sessions.json").read_text())
    assert (
        on_disk["available"] is True and on_disk["seen"] == 3 and on_disk["alive"] == []
    )
    ends = {entry["pid"]: entry["last_seen"] for entry in on_disk["sessions"]}
    assert sorted(ends) == [11, 16, 20] and all(
        while_alive - 0.2 < t <= while_alive + 0.05 for t in ends.values()
    ), ends
    assert on_disk["last_scan"] > while_alive + 0.2, (
        "the detached processes that ran on kept no session alive"
    )


def test_the_collect_step_reads_sessions_as_the_net_check_does():
    netcheck, sweep = (
        (ENV_DIR / "fsmaint-netcheck").read_text(),
        (ENV_DIR / "fsmaint-sweep").read_text(),
    )
    for name in ("read_status", "processes", "sessions"):
        block = (
            re.search(rf"^def {name}\(.*?(?=^\S)", netcheck, re.DOTALL | re.MULTILINE)
            .group(0)
            .rstrip()
        )
        assert block in sweep, name
    assert (
        'SESSION_PARENTS = ("su", "runuser")' in netcheck
        and 'SESSION_PARENTS = ("su", "runuser")' in sweep
    )


def test_the_agent_works_as_dev_and_the_hooks_are_out_of_its_reach(task_root):
    docker = (ENV_DIR / "Dockerfile").read_text()
    for literal in (
        "useradd --uid 10001 --create-home dev",
        "chown -R dev:dev /app/sympy && chown root:root /app/sympy && chmod 0777 /app/sympy",
        "touch /app/PROGRESS.md && chown dev:dev /app/PROGRESS.md",
        "chmod 1777 /app",
        "chmod -R a-w /opt/restore/skeleton /opt/restore/lib /opt/restore/units.json",
        "chmod -R a+rwX /opt/restore/var",
        "chmod 0700 /usr/local/lib/fsmaint ",
        "chmod 0600 /usr/local/lib/fsmaint/key",
        "COPY data/fsmaint.key /usr/local/lib/fsmaint/key",
    ):
        assert literal in docker, literal
    assert (
        "USER " not in docker
        and "sudo" not in docker
        and "/usr/local/sbin" not in docker
    )
    toml = (task_root / "task.toml").read_text()
    head = toml.split("\n[[steps]]")[0]
    for literal in (
        '[agent]\ntimeout_sec = 34560\nnetwork_mode = "no-network"\nuser = "dev"\n',
        '[[agent.setup_begin]]\ncommand = "/usr/local/lib/fsmaint/fsmaint-reserve"\nuser = "root"',
        '[[agent.setup_complete]]\ncommand = "/usr/local/lib/fsmaint/fsmaint-reserve --netcheck"\nuser = "root"',
        '[[verifier.collect]]\ncommand = "/usr/local/lib/fsmaint/fsmaint-sweep"\nuser = "root"\ntimeout_sec = 600',
    ):
        assert literal in head, (
            f"{literal!r} sits before the step tables, so the single-step bundle keeps it"
        )
    oracle = (task_root / "solution" / "oracle.py").read_text()
    # long enough for the net check to see a few closed polls, however short the rest of the turn
    assert (
        re.search(r"^SETTLE_SECONDS = (\d+)", oracle, re.MULTILINE)
        and int(re.search(r"^SETTLE_SECONDS = (\d+)", oracle, re.MULTILINE)[1]) >= 10
    )
    assert "time.sleep(SETTLE_SECONDS)" in oracle
    engine = (task_root / "tests" / "verifier" / "engine.py").read_text()
    body = engine[engine.index("def measure(") :]
    order = [
        "delivery.network_open()",
        "delivery.read_delivery(",
        "restorelib.build_candidate(skel, work_tree, cand, byfile, None)",
        "if delivered.end_bound is None:",
        'withhold(skel, cand, byfile, metrics["late_files"], states)',
    ]
    assert [body.index(step) for step in order] == sorted(
        body.index(step) for step in order
    ), "the record is read before anything is graded"
    instruction = (task_root / "instruction.md").read_text()
    assert (
        "Another copy of SymPy's source, from an installed package, a download, a mirror or any other place, is not "
        "to be used, in whole or in part."
    ) in " ".join(instruction.split())
    for word in ("fsmaint", "collect", "sweep", "mark", "verifier", "late", "signed"):
        assert not re.search(rf"\b{word}\b", instruction.lower()), word
    # the hooks say nothing of what the copy is for
    for name in ("fsmaint-reserve", "fsmaint-netcheck", "fsmaint-sweep"):
        text = (
            (ENV_DIR / name).read_text().lower().replace("oom_score_adj", "")
        )  # the kernel's own file name
        for word in (
            "agent",
            "deliver",
            "grad",
            "verif",
            "submission",
            "egress",
            "reward",
            "score",
        ):
            assert word not in text, (name, word)


def test_a_turn_ended_at_the_time_limit_is_bounded_by_it_whatever_the_probe_saw(
    tmp_path, verifier_call
):
    """The turn runs to the time limit, the harness never ends its exec, and a process of the work keeps
    the probe's handshakes timing out after the limit (the net check reads them as closed), so the net
    check's end comes just before this step; a file fetched after the limit is late all the same, as
    the end is never later than the start of the work plus the time it is given. The real net check runs."""
    hooks = Hooks(tmp_path / "t", real_netcheck=True, WORK_LIMIT_SECONDS=2)
    hooks.setup()
    started = hooks.work_started()
    hooks.network("closed")  # the turn, and after it a probe that reads closed
    (hooks.tree / "honest.py").write_text("def g():\n    return 1\n")
    time.sleep(max(0.0, started + 2.4 - time.time()))
    (hooks.tree / "fetched.py").write_text("# written after the time limit\n")
    time.sleep(0.5)
    hooks.run(
        "fsmaint-sweep", egress="open"
    )  # the freeze ends the load: the next poll is open
    record = hooks.record()
    assert record["end_from"] == "limit" and record["end_bound"] == started + 2, record
    assert (
        record["end_bounds"]["netcheck"][1] == "netcheck"
        and record["end_bounds"]["netcheck"][0] > started + 2.4
    ), record["end_bounds"]
    arrived = tmp_path / "arrived" / "sympy"
    platform_copy(hooks.tree, arrived)
    result = read_delivery(verifier_call, arrived, hooks.lib / "key")
    assert (
        result["state"] == "listed"
        and result["late"] == ["fetched.py"]
        and result["end_from"] == "limit"
    ), result


def test_a_session_alive_after_the_limit_with_no_other_end_ends_the_work_at_the_limit(
    tmp_path, verifier_call
):
    """The exec session was still alive when this step began, after the limit, and the net check's
    stretch reached into this step while the hosts answered it: the work ran until the limit, so that
    is its end, and the tree is graded rather than refused."""
    hooks = Hooks(tmp_path / "t", WORK_LIMIT_SECONDS=1)
    hooks.setup()
    started = hooks.work_started()
    (hooks.tree / "honest.py").write_text("def g():\n    return 1\n")
    time.sleep(max(0.0, started + 1.4 - time.time()))
    (hooks.tree / "fetched.py").write_text("# written after the time limit\n")
    now = time.time()
    sessions = {
        "available": True,
        "seen": 1,
        "alive": [9],
        "sessions": [{"pid": 9, "first_seen": started + 0.01, "last_seen": now + 60}],
    }
    hooks.scenario(last="closed", closing=[now - 5, now + 30, 40], sessions=sessions)
    hooks.run("fsmaint-sweep", egress="open")
    record = hooks.record()
    assert (
        record["state"] == "listed"
        and record["end_from"] == "limit"
        and record["end_bound"] == started + 1
    ), record
    assert (
        record["session_alive_at_start"] is True
        and record["end_bounds"]["netcheck"][0] is None
    )
    arrived = tmp_path / "arrived" / "sympy"
    platform_copy(hooks.tree, arrived)
    assert read_delivery(verifier_call, arrived, hooks.lib / "key")["late"] == [
        "fetched.py"
    ]


def test_the_work_limit_is_the_time_limit_the_task_gives(task_root):

    config = tomllib.loads((task_root / "task.toml").read_text())
    limits = {config["agent"]["timeout_sec"]}
    sweep = (ENV_DIR / "fsmaint-sweep").read_text()
    session = (ENV_DIR / "fsmaint-session").read_text()
    delivery_text = (task_root / "tests" / "verifier" / "delivery.py").read_text()
    in_sweep = int(re.search(r"^WORK_LIMIT_SECONDS=(\d+)$", sweep, re.MULTILINE)[1])
    in_session = int(
        re.search(r"^WORK_LIMIT_SECONDS = (\d+)", session, re.MULTILINE)[1]
    )
    in_verifier = int(
        re.search(r"^WORK_LIMIT_SEC = \(?\s*(\d+)", delivery_text, re.MULTILINE)[1]
    )
    assert limits == {in_sweep} == {in_session} == {in_verifier} == {43200}, (
        limits,
        in_sweep,
        in_session,
        in_verifier,
    )


def test_the_room_is_given_back_and_the_tree_set_aside_before_anything_is_written(
    tmp_path, verifier_call
):
    """Right after the freeze: the room first, then the tree aside, then the listing; a listing that
    cannot be written (a disk the work filled) leaves the session end to the net check's own record."""
    sweep = (ENV_DIR / "fsmaint-sweep").read_text()
    order = [
        "kill -STOP -1",
        'rm -f "$STATE/room"',
        'rm -rf "$STATE/inodes"',
        'cat > "$STATE/measure.py"',
        'measure.py" stage',
        '"$STATE/procs.json"',
        "kill -9 -1",
    ]
    positions = [sweep.index(step) for step in order]
    assert positions == sorted(positions), order
    assert sweep.index('cat > "$STATE/measure.py"') < sweep.index(
        "timeout 30 /usr/bin/python3"
    )
    assert ': > "$STATE' not in sweep[: sweep.index('rm -f "$STATE/room"')], (
        "nothing is written before the room is given back"
    )
    hooks = Hooks(tmp_path / "t")
    hooks.setup()
    started = hooks.work_started()
    (hooks.tree / "honest.py").write_text("def g():\n    return 1\n")
    time.sleep(0.6)
    session_end = time.time()
    time.sleep(0.6)
    (hooks.tree / "fetched.py").write_text("# written after the turn\n")
    time.sleep(0.3)
    (hooks.state / "procs.json").mkdir()  # the listing cannot be written
    sessions = {
        "available": True,
        "seen": 1,
        "alive": [],
        "sessions": [
            {"pid": 42, "first_seen": started + 0.05, "last_seen": session_end}
        ],
    }
    hooks.scenario(last="open", openings=[opening(time.time())], sessions=sessions)
    hooks.run("fsmaint-sweep", egress="open")
    record = hooks.record()
    assert (
        record["process_count"] is None
        and record["end_from"] == "session"
        and record["end_bound"] == session_end
    ), record
    arrived = tmp_path / "arrived" / "sympy"
    platform_copy(hooks.tree, arrived)
    assert read_delivery(verifier_call, arrived, hooks.lib / "key")["late"] == [
        "fetched.py"
    ]


@pytest.mark.parametrize("case", ["zombies", "never-ends"])
def test_the_kill_counts_live_processes_only_and_has_a_time_budget(tmp_path, case):
    hooks = Hooks(tmp_path / "t", KILL_SECONDS=1)
    # zombies only: procps finds them without a state filter and none in a live state; or a process
    # that no signal ends: found in every state, every time
    body = (
        'for word in "$@"; do [ "$word" = "-r" ] && exit 1; done\nexit 0\n'
        if case == "zombies"
        else "exit 0\n"
    )
    (hooks.bin / "pgrep").write_text("#!/bin/sh\n" + body)
    hooks.setup()
    (hooks.tree / "a.py").write_text("x = 1\n")
    hooks.scenario(last="open", openings=[opening(time.time())])
    began = time.time()
    hooks.run("fsmaint-sweep", egress="open")
    record = hooks.record()
    if case == "zombies":
        assert record["kill_passes"] == 0, record["kill_passes"]
    else:
        assert 1 <= record["kill_passes"] <= 20 and time.time() - began < 60, record[
            "kill_passes"
        ]
    assert record["state"] == "listed"


@pytest.mark.parametrize("case", ["slow", "quick"])
def test_an_answer_the_net_check_could_not_have_seen_is_no_refusal(
    tmp_path, verifier_call, case
):
    """The stretch reached into this step and this step's probe got an answer: a refusal (the work hid
    the end) only when the answer came at the net check's own addresses within its polls' time; an
    answer that came only after longer waits leaves the end unknown instead (an evaluation error for a
    tree that restores a unit)."""
    hooks = Hooks(tmp_path / "t")
    hooks.setup()
    (hooks.tree / "a.py").write_text("x = 1\n")
    now = time.time()
    hooks.scenario(last="closed", closing=[now - 5, now + 30, 40])
    hooks.run("fsmaint-sweep", egress="slow" if case == "slow" else "open")
    record = hooks.record()
    assert record["net_probe"]["any_open"] is True
    if case == "slow":
        assert (
            record["net_probe"]["answered_as_net_check"] is False
            and record["state"] == "listed"
            and record["end_from"] is None
        ), record
    else:
        assert (
            record["net_probe"]["answered_as_net_check"] is True
            and record["state"] == "refused"
        ), record


def test_the_probe_is_given_its_hosts_on_standard_input(tmp_path):
    """`ps` shows the probe's command line to every user: it names no host."""
    netcheck = load_netcheck(tmp_path / "state")
    seen = {}

    class FakeProbe:
        def __init__(self, command, stdin, stdout, stderr, text):
            seen["command"], seen["input"] = command, []
            self.stdin = types.SimpleNamespace(
                write=seen["input"].append,
                close=lambda: seen.setdefault("closed", True),
            )
            self.stdout = iter(["uid 65534\n", "1000.5 closed -\n"])

        def kill(self):
            pass

        def wait(self, timeout=None):
            return 0

    netcheck.subprocess = types.SimpleNamespace(
        Popen=FakeProbe, PIPE=-1, DEVNULL=-3, SubprocessError=Exception
    )
    targets = [("pypi.org", "192.0.2.1"), ("github.com", "192.0.2.2")]
    status = {}
    polls = netcheck.polls(targets, status)
    assert next(polls) == (1000.5, "closed", None)
    assert (
        seen["command"][-1] == "--probe"
        and len(seen["command"]) == 4
        and seen.get("closed") is True
    )
    assert not any(
        host in " ".join(seen["command"]) for host in netcheck.HOSTS + ("192.0.2.1",)
    )
    assert (
        json.loads("".join(seen["input"])) == [list(target) for target in targets]
        and status["probe_uid"] == 65534
    )
    # the probe reads them there
    got = {}
    netcheck.probe_lines = lambda found, out: got.setdefault("targets", found)
    netcheck.os = types.SimpleNamespace(geteuid=lambda: 1000)
    netcheck.sys = types.SimpleNamespace(
        stdin=io.StringIO(json.dumps(targets) + "\n"),
        stdout=io.StringIO(),
        argv=["x", "--probe"],
    )
    assert netcheck.probe_main() == 0 and got["targets"] == targets


def test_local_polls_end_nothing_and_an_opening_while_a_session_is_alive_ends_nothing_before_the_limit(
    tmp_path,
):
    netcheck = load_netcheck(tmp_path / "state")
    ended = []

    def polls(states):
        return [
            (
                float(k),
                "closed" if s == "c" else "open" if s == "o" else "local",
                "pypi.org" if s == "o" else None if s == "c" else "EMFILE",
            )
            for k, s in enumerate(states, 1)
        ]

    # a machine short of ports during the turn: local polls end neither the stretch nor dev, whatever the sessions
    for alive in (True, False, None):
        status = {}
        assert (
            netcheck.watch(
                iter(polls("occclllccc")),
                status,
                ending=lambda: ended.append(1) or (1, 0),
                session_alive=lambda a=alive: a,
            )
            == []
        )
        assert (
            status["closing"] == [2.0, 10.0, 6] and status["longest_local_run"] == 3
        ), status
    assert ended == []
    # an opening while a session is seen alive, before the time the work is given runs out: recorded, nothing ended
    later = lambda: time.time() + 3600
    openings = netcheck.watch(
        iter(polls("occcoc")),
        {},
        ending=lambda: ended.append(2) or (1, 0),
        session_alive=lambda: True,
        limit=later,
    )
    assert (
        ended == []
        and openings[0]["session_alive"] is True
        and openings[0]["after_limit"] is False
    ), openings
    assert openings[0]["ending"].startswith("waits")
    # ... until the session is no longer seen alive
    alive = iter([True, True, True, False])
    netcheck.watch(
        iter(polls("occcocc")),
        {},
        ending=lambda: ended.append(3) or (1, 0),
        session_alive=lambda: next(alive, False),
        limit=later,
    )
    assert ended == [3]
    # once the time has run out, an opening ends dev even while the session is alive
    openings = netcheck.watch(
        iter(polls("occco")),
        {},
        ending=lambda: ended.append(4) or (1, 0),
        session_alive=lambda: True,
        limit=lambda: time.time() - 1,
    )
    assert ended == [3, 4] and openings[0]["after_limit"] is True
    # a fresh look that finds no session: at once; sessions that cannot be seen: it waits
    netcheck.watch(
        iter(polls("occco")),
        {},
        ending=lambda: ended.append(5) or (1, 0),
        session_alive=lambda: False,
    )
    assert ended == [3, 4, 5]
    openings = netcheck.watch(
        iter(polls("occcoc")),
        {},
        ending=lambda: ended.append(6) or (1, 0),
        session_alive=lambda: None,
        limit=later,
    )
    assert (
        ended == [3, 4, 5]
        and openings[0]["session_alive"] is None
        and openings[0]["ending"].startswith("waits")
    )
    # the time counted from the start of the work has run out, the time counted from the first process has
    # not: the opening is an end of the work, and dev is not ended while its session is alive
    openings = netcheck.watch(
        iter(polls("occcoc")),
        {},
        ending=lambda: ended.append(7) or (1, 0),
        session_alive=lambda: True,
        limit=lambda: time.time() - 1,
        stop_limit=later,
    )
    assert (
        ended == [3, 4, 5]
        and openings[0]["after_limit"] is True
        and openings[0]["ending"].startswith("waits")
    ), openings
    now = time.time()
    assert (
        netcheck.session_seen({"available": True, "alive": [5], "last_scan": now})
        is True
    )
    assert (
        netcheck.session_seen({"available": True, "alive": [], "last_scan": now})
        is False
    )
    assert (
        netcheck.session_seen({"available": True, "alive": [5], "last_scan": now - 10})
        is None
    )
    assert netcheck.session_seen({"available": False}) is None


def frange(first: float, last: float, step: float) -> list[float]:
    count = max(0, int((last - first) / step) + 1)
    return [first + step * k for k in range(count)]


def test_a_moment_the_machine_cannot_look_mid_session_is_no_end_of_the_work(
    tmp_path, verifier_call
):
    """The re-check's probe: the turn's polls are closed; three polls fail for want of buffers two
    thirds into the turn, while its session is alive; then the turn ends, its session with it, and the
    hosts answer again. The real net check records no end at the blip, so the session's end ends the
    work, and what was saved after the blip is graded."""
    netcheck = load_netcheck(tmp_path / "nc")
    hooks = Hooks(tmp_path / "t")
    hooks.setup()
    started = hooks.work_started()
    (hooks.tree / "core").mkdir()
    (hooks.tree / "core" / "basic.py").write_text("def f():\n    return 1\n")
    time.sleep(0.6)
    blip = time.time()
    time.sleep(0.3)
    (hooks.tree / "polytools.py").write_text(
        "def g():\n    return 2\n"
    )  # saved after the blip
    time.sleep(0.3)
    session_end = time.time()
    stream = (
        [(t, "closed", None) for t in frange(started + 0.05, blip, 0.05)]
        + [(blip + 0.01 * k, "local", "ENOBUFS") for k in range(3)]
        + [(t, "closed", None) for t in frange(blip + 0.05, session_end + 0.1, 0.05)]
        + [(session_end + 0.15, "open", "pypi.org")]
    )
    status = {}
    openings = netcheck.watch(
        iter(stream), status, ending=lambda: (0, 0), session_alive=lambda: False
    )
    assert (
        len(openings) == 1
        and openings[0]["end_bound"] > session_end
        and status["longest_local_run"] == 3
    ), openings
    sessions = {
        "available": True,
        "seen": 1,
        "alive": [],
        "sessions": [
            {"pid": 42, "first_seen": started + 0.02, "last_seen": session_end}
        ],
    }
    hooks.scenario(last="open", openings=openings, sessions=sessions)
    hooks.run("fsmaint-sweep", egress="open")
    record = hooks.record()
    assert record["end_from"] == "session" and record["end_bound"] == session_end, (
        record
    )
    arrived = tmp_path / "arrived" / "sympy"
    platform_copy(hooks.tree, arrived)
    result = read_delivery(verifier_call, arrived, hooks.lib / "key")
    assert result["state"] == "listed" and result["late"] == [], result


def test_an_opening_seen_while_the_session_is_alive_before_the_limit_is_no_end(
    tmp_path, verifier_call
):
    """The hosts answer again only once the work has ended; an opening recorded while the turn's session
    was alive, before the time the work is given ran out, does not end the work: its session does."""
    hooks = Hooks(tmp_path / "t")
    hooks.setup()
    started = hooks.work_started()
    (hooks.tree / "a.py").write_text("x = 1\n")
    time.sleep(0.4)
    early = dict(opening(time.time()), session_alive=True, after_limit=False)
    time.sleep(0.3)
    (hooks.tree / "b.py").write_text("y = 2\n")
    time.sleep(0.3)
    session_end = time.time()
    sessions = {
        "available": True,
        "seen": 1,
        "alive": [],
        "sessions": [
            {"pid": 42, "first_seen": started + 0.02, "last_seen": session_end}
        ],
    }
    hooks.scenario(
        last="open",
        openings=[
            early,
            dict(opening(session_end + 0.1), session_alive=False, after_limit=False),
        ],
        sessions=sessions,
    )
    hooks.run("fsmaint-sweep", egress="open")
    record = hooks.record()
    assert record["end_from"] == "session" and record["end_bound"] == session_end, (
        record
    )
    assert any("while an exec session was alive" in note for note in record["notes"]), (
        record["notes"]
    )


def test_an_honest_turn_run_to_the_limit_keeps_the_unit_file_it_had_then(
    tmp_path, verifier_call
):
    """The turn runs to the limit (3 s here), and the agent saves a unit file once more just after it,
    by writing a new file and renaming it into place, before it is stopped. The real net check copied
    the unit files as the limit came: the file is taken as it stood then, never as the skeleton."""
    hooks = Hooks(
        tmp_path / "t",
        real_netcheck=True,
        WORK_LIMIT_SECONDS=3,
        netcheck_settings={
            "WORK_LIMIT_SECONDS": 3,
            "COPY_LEAD_SECONDS": 2.5,
            "COPY_INTERVAL_SECONDS": 0.2,
        },
    )
    hooks.setup()
    started = hooks.work_started()
    hooks.network("closed")
    (hooks.tree / "m.py").write_text("def f():\n    return 1\n")  # in time
    time.sleep(max(0.0, started + 3.4 - time.time()))
    (hooks.tree / "m.py.new").write_text("def f():\n    return 2\n")
    os.replace(hooks.tree / "m.py.new", hooks.tree / "m.py")  # after the limit
    time.sleep(0.3)
    hooks.run("fsmaint-sweep", egress="open")
    record = hooks.record()
    entry = {item["path"]: item for item in record["entries"]}["m.py"]
    assert (
        record["end_from"] == "limit"
        and record["end_bound"] == started + 3
        and record["limit_from"] == "start of the work"
    ), record
    assert entry["copied"]["captured"] <= record["end_bound"] and entry["copied"][
        "units_changed_after"
    ] == ["U0001"], entry
    assert (
        record["copies"]["taken"] == 1 and record["copies"]["finished"] is not None
    ), record["copies"]
    assert (hooks.tree / "m.py").read_text() == "def f():\n    return 1\n"
    arrived = tmp_path / "arrived" / "sympy"
    platform_copy(hooks.tree, arrived)
    result = read_delivery(verifier_call, arrived, hooks.lib / "key")
    assert result["late"] == [] and list(result["copied"]) == ["m.py"], result
    assert graded_states(
        verifier_call, {"sympy/m.py": PLACEHOLDER}, arrived.parent
    ) == {"U0001": "restored"}


def test_the_end_of_the_work_counts_from_its_start_and_the_first_process_only_from_when_dev_may_be_ended(
    tmp_path, verifier_call
):
    """The net check reads the start of the first process of `dev` that began after the work did, whose
    parent is not one of `dev`'s, from /proc; it decides only when `dev` may be ended. The end of the
    work counts from the start of the work, which the setup step took before the agent's clock: a write
    after the start of the work plus the limit is late, whenever the first process began."""
    netcheck = load_netcheck(tmp_path / "state")
    proc = tmp_path / "proc"
    ticks = os.sysconf("SC_CLK_TCK")
    now = time.time()
    (proc).mkdir()
    (proc / "uptime").write_text("1000.00 2000.00\n")
    for pid, uid, ppid, name, ago in (
        (9, 1000, 1, "agentd", 100.0),
        (10, 0, 1, "su", 120.0),
        (11, 1000, 10, "bash", 40.0),
        (12, 1000, 11, "python3", 30.0),
        (13, 0, 1, "cron", 5.0),
    ):
        (proc / str(pid)).mkdir()
        (proc / str(pid) / "status").write_text(
            f"Name:\t{name}\nState:\tS (sleeping)\nPPid:\t{ppid}\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\n"
        )
        fields = (
            ["S", str(ppid)]
            + ["0"] * 17
            + [str(int((1000.0 - ago) * ticks))]
            + ["0"] * 10
        )
        (proc / str(pid) / "stat").write_text(
            f"{pid} ({name}) " + " ".join(fields) + "\n"
        )
    table = netcheck.processes(str(proc))
    sighted = {}
    assert (
        netcheck.first_process(
            table, 1000, now - 50, str(proc), sighted=sighted, now=now
        )
        is None
    ), "one look counts none"
    assert (
        netcheck.first_process(
            table, 1000, now - 50, str(proc), sighted=sighted, now=now + 0.5
        )
        is None
    ), sighted
    first = netcheck.first_process(
        table, 1000, now - 50, str(proc), sighted=sighted, now=now + 1.0
    )
    assert (
        first["pid"] == 11
        and first["parent"] == "su"
        and abs(first["start"] - (now - 40)) < 0.5
    ), first
    assert netcheck.first_process(table, 1000, now - 50, str(proc)) is None, (
        "called once, it takes no process"
    )
    assert (
        netcheck.first_process(
            table, 1000, now - 50, str(proc), known=dict(first, start=now - 45)
        )["start"]
        == now - 45
    )
    # the collect step counts from the start of the work
    hooks = Hooks(tmp_path / "t", WORK_LIMIT_SECONDS=1)
    hooks.setup()
    started = hooks.work_started()
    sessions = {
        "available": True,
        "seen": 1,
        "alive": [11],
        "sessions": [{"pid": 11, "first_seen": started + 1, "last_seen": started + 60}],
        "first_process": {
            "pid": 11,
            "start": started + 1.0,
            "name": "bash",
            "parent": "su",
        },
    }
    (hooks.tree / "m.py").write_text("x = 1\n")
    time.sleep(max(0.0, started + 1.5 - time.time()))
    (hooks.tree / "n.py").write_text(
        "y = 2\n"
    )  # after the start of the work plus 1 s, before the first process's
    time.sleep(max(0.0, started + 2.4 - time.time()))
    (hooks.tree / "o.py").write_text("z = 3\n")  # after both
    hooks.scenario(
        last="closed", closing=[started + 0.1, time.time() + 30, 40], sessions=sessions
    )
    hooks.run("fsmaint-sweep", egress="closed")
    record = hooks.record()
    assert (
        record["end_from"] == "limit"
        and record["end_bound"] == started + 1.0
        and record["limit_from"] == "start of the work"
    ), record
    arrived = tmp_path / "arrived" / "sympy"
    platform_copy(hooks.tree, arrived)
    assert read_delivery(verifier_call, arrived, hooks.lib / "key")["late"] == [
        "n.py",
        "o.py",
    ]


def test_a_fetch_saved_after_egress_returns_is_late_and_the_last_second_before_the_limit_is_kept(
    tmp_path, verifier_call
):
    """The re-check's probe of a capped turn: the agent's clock starts a moment after the setup step,
    egress returns a moment after the agent's limit, and a fetched body is saved by rename just after.
    The end of the work is the start of the work plus the limit (3 s here), before egress returns: the
    fetched file is late, and is taken as the real net check's last copy of it by the end, which holds
    the honest save made in the last second before the limit."""
    hooks = Hooks(
        tmp_path / "t",
        real_netcheck=True,
        WORK_LIMIT_SECONDS=3,
        netcheck_settings={
            "WORK_LIMIT_SECONDS": 3,
            "COPY_LEAD_SECONDS": 2.5,
            "COPY_INTERVAL_SECONDS": 0.2,
        },
    )
    hooks.setup()
    started = hooks.work_started()
    hooks.network("closed")
    (hooks.tree / "m.py").write_text("def f():\n    return 1\n")
    time.sleep(max(0.0, started + 2.3 - time.time()))
    (hooks.tree / "m.py.new").write_text("def f():\n    return 2\n")
    os.replace(
        hooks.tree / "m.py.new", hooks.tree / "m.py"
    )  # the last second before the limit
    time.sleep(max(0.0, started + 3.5 - time.time()))
    hooks.network("open")  # egress returns after the agent's limit
    time.sleep(0.3)
    (hooks.tree / "m.py.new").write_text("def f():\n    return 'UPSTREAM'\n")
    os.replace(hooks.tree / "m.py.new", hooks.tree / "m.py")  # the fetched body
    time.sleep(0.5)
    hooks.run("fsmaint-sweep", egress="open")
    record = hooks.record()
    assert (
        record["end_from"] == "limit"
        and record["end_bound"] == started + 3
        and record["limit_from"] == "start of the work"
    ), record
    entry = {item["path"]: item for item in record["entries"]}["m.py"]
    assert entry["copied"]["captured"] <= record["end_bound"], entry
    assert (hooks.tree / "m.py").read_text() == "def f():\n    return 2\n"
    arrived = tmp_path / "arrived" / "sympy"
    platform_copy(hooks.tree, arrived)
    result = read_delivery(verifier_call, arrived, hooks.lib / "key")
    assert result["late"] == [] and list(result["copied"]) == ["m.py"], result
    assert graded_states(
        verifier_call, {"sympy/m.py": PLACEHOLDER}, arrived.parent
    ) == {"U0001": "restored"}


def test_with_no_first_process_seen_dev_is_never_ended_by_time_alone(tmp_path):
    """Fix round 10: no process of `dev` is seen (no `/proc` here, so the sessions cannot be seen either),
    the network is closed through the turn and opens after the time the work is given, counted from the
    start of the work. The opening is an end of the work, but `dev` is not ended by it: without a first
    process the net check cannot tell when the platform's own limit, which counts from later, falls, so it
    ends `dev` only once a fresh look finds no session (here never), or the collect step does."""
    hooks = Hooks(
        tmp_path / "t",
        real_netcheck=True,
        WORK_LIMIT_SECONDS=3,
        netcheck_settings={
            "WORK_LIMIT_SECONDS": 3,
            "COPY_LEAD_SECONDS": 2.5,
            "COPY_INTERVAL_SECONDS": 0.2,
        },
    )
    hooks.setup()
    started = hooks.work_started()
    hooks.network("closed")
    time.sleep(max(0.0, started + 3.5 - time.time()))
    hooks.network("open")  # after the limit counted from the start
    opened = hooks.state / "netcheck-open.json"
    for _ in range(100):
        if opened.exists():
            break
        time.sleep(0.05)
    time.sleep(1.0)  # time for an ending, were there one
    record = json.loads(opened.read_text())
    sessions = json.loads((hooks.state / "sessions.json").read_text())
    hooks.run("fsmaint-sweep", egress="open")
    assert sessions.get("first_process") is None and record["session_alive"] is None, (
        sessions,
        record,
    )
    assert record["after_limit"] is True, record
    assert record.get("ending", "").startswith("waits") and "ended_at" not in record, (
        record
    )


def test_a_short_command_before_the_agents_clock_is_never_the_first_process(
    tmp_path, monkeypatch
):
    """Fix round 11 (the seventh re-check's stop path): after the setup step and before its own clock starts,
    Harbor runs a short `pwd` as `dev`. A look that catches it must not take it for the first process,
    or the time counted from it runs out before the agent's limit and a blip of egress during the turn
    ends `dev` early. A process counts only once two looks at least a second apart both see it alive.
    The shipped watch runs on a stand-in /proc with the limit scaled to 3 s: the `pwd` (under a root `su`)
    for one look, Harbor's clock at 1.0 s, the agent's session from 1.3 s on, a blip at 1.7 s. The net
    check before fix round 11 took the `pwd` and ended `dev` 0.8 s before the agent's limit."""
    netcheck = load_netcheck(tmp_path / "state")
    monkeypatch.setattr(
        netcheck, "cap_processes", lambda *args, **kwargs: None
    )  # no prlimit on stand-in pids
    dev, limit = 10001, 3.0
    ticks = os.sysconf("SC_CLK_TCK")
    proc = tmp_path / "proc"
    proc.mkdir()
    s = time.time()  # the start of the work
    boot = s - 5000.0
    done = threading.Event()

    def uptime():  # the stand-in's time since boot keeps up with the clock
        while not done.is_set():
            (proc / "uptime.tmp").write_text(f"{time.time() - boot:.2f} 0.00\n")
            os.replace(proc / "uptime.tmp", proc / "uptime")
            time.sleep(0.01)

    def process(pid, uid, parent, name, start):
        (proc / str(pid)).mkdir()
        (proc / str(pid) / "status").write_text(
            f"Name:\t{name}\nState:\tS (sleeping)\nPPid:\t{parent}\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\n"
        )
        fields = (
            ["S", str(parent)]
            + ["0"] * 17
            + [str(round((start - boot) * ticks))]
            + ["0"] * 10
        )
        (proc / str(pid) / "stat").write_text(
            f"{pid} ({name}) " + " ".join(fields) + "\n"
        )

    def at(moment):
        time.sleep(max(0.0, s + moment - time.time()))

    (proc / "uptime").write_text(f"{time.time() - boot:.2f} 0.00\n")
    process(1, 0, 0, "init", s - 100)
    threading.Thread(target=uptime, daemon=True).start()
    record, stop = {}, threading.Event()
    watcher = threading.Thread(
        target=netcheck.watch_sessions,
        args=(dev, record, stop, str(proc), netcheck.SESSION_SECONDS),
        kwargs={"since": s},
        daemon=True,
    )
    watcher.start()
    at(0.2)
    process(20, 0, 1, "su", s + 0.2)
    process(21, dev, 20, "pwd", s + 0.2)  # Harbor's pre-clock command
    scans = record.get("scans", 0)
    while (
        record.get("scans", 0) < scans + 2 and time.time() < s + 0.8
    ):  # one whole look sees it
        time.sleep(0.01)
    shutil.rmtree(proc / "21")
    shutil.rmtree(proc / "20")
    clock = s + 1.0  # Harbor's clock starts
    at(1.3)
    process(30, 0, 1, "su", s + 1.3)
    process(31, dev, 30, "bash", s + 1.3)  # the agent's session, for the turn
    ended = {}

    def ending():
        ended["at"] = time.time()
        return 0, 0

    def stop_of():  # as the net check's main() counts it
        first = record.get("first_process")
        if not (
            isinstance(first, dict) and isinstance(first.get("start"), (int, float))
        ):
            return None
        return max(first["start"], s) + limit

    assert (
        'return max(first["start"], since) + WORK_LIMIT_SECONDS'
        in (ENV_DIR / "fsmaint-netcheck").read_text()
    )
    moments = [1.4, 1.5, 1.6, 1.7] + [1.8 + 0.1 * k for k in range(39)]
    states = ["closed", "closed", "closed", "open"] + ["closed"] * 39

    def stream():
        for moment, state in zip(moments, states):
            at(moment)
            yield s + moment, state, ("pypi.org" if state == "open" else None)

    openings = netcheck.watch(
        stream(),
        {},
        ending=ending,
        session_alive=lambda: netcheck.session_seen(record),
        limit=lambda: s + limit,
        stop_limit=stop_of,
    )
    stop.set()
    done.set()
    watcher.join(2)
    first = record.get("first_process")
    assert (
        first is not None
        and first["pid"] == 31
        and abs(first["start"] - (s + 1.3)) < 0.1
    ), first
    assert record["first_process_passed_over"] >= 1, record
    assert [
        (o["session_alive"], o["after_limit"], o.get("ending", "")[:5])
        for o in openings
    ] == [(True, False, "waits")], openings
    assert "at" in ended and ended["at"] >= clock + limit, (ended, clock + limit)


def test_the_limit_ends_the_work_when_the_collect_step_began_after_it_with_no_session_seen(
    tmp_path, verifier_call
):
    """Nothing else tells the end (the stretch reached into this step, the hosts answered it only after a
    longer wait, no session was watched), and this step began after the time the work is given ran out:
    the hosts answer only after it, so the limit is the end."""
    hooks = Hooks(tmp_path / "t", WORK_LIMIT_SECONDS=1)
    hooks.setup()
    started = hooks.work_started()
    (hooks.tree / "a.py").write_text("x = 1\n")
    time.sleep(max(0.0, started + 1.5 - time.time()))
    hooks.scenario(last="closed", closing=[started + 0.1, time.time() + 30, 40])
    hooks.run("fsmaint-sweep", egress="slow")
    record = hooks.record()
    assert (
        record["end_from"] == "limit"
        and record["end_bound"] == started + 1
        and record["session_alive_at_start"] is False
    ), record


def test_every_process_of_dev_is_given_a_process_limit(tmp_path, monkeypatch):
    netcheck = load_netcheck(tmp_path / "state")
    calls = []

    def prlimit(pid, which, new=None):
        calls.append((pid, which, new))
        if new is None:
            return (100, 200) if pid == 13 else (-1, -1)
        if pid == 14:
            raise OSError(errno.EPERM, "not permitted")
        return None

    monkeypatch.setitem(
        sys.modules,
        "resource",
        types.SimpleNamespace(RLIMIT_NPROC=6, RLIM_INFINITY=-1, prlimit=prlimit),
    )
    table = {
        11: (1000, 10, "bash", "S"),
        12: (1000, 11, "python3", "R"),
        13: (1000, 11, "node", "S"),
        14: (1000, 11, "x", "S"),
        15: (0, 1, "sshd", "S"),
        16: (1000, 11, "gone", "Z"),
    }
    capped = set()
    assert netcheck.cap_processes(table, 1000, capped, cap=8192) == 1 and capped == {
        11,
        12,
        13,
    }
    assert sorted((pid, new) for pid, _which, new in calls if new is not None) == [
        (11, (8192, 8192)),
        (12, (8192, 8192)),
        (14, (8192, 8192)),
    ]
    calls.clear()
    assert netcheck.cap_processes(table, 1000, capped, cap=8192) == 1 and [
        pid for pid, _w, _n in calls
    ] == [14, 14], "once per process"
    monkeypatch.setitem(sys.modules, "resource", types.SimpleNamespace(RLIMIT_NPROC=6))
    assert netcheck.cap_processes(table, 1000, set()) is None, (
        "without prlimit nothing is done"
    )


def test_a_collect_step_that_can_start_no_process_leaves_a_noted_0_not_an_error(
    tmp_path, verifier_call
):
    """A work that forks without end leaves the collect step unable to start any process. It still says,
    with the shell's own commands, that it began; it writes no mark, and the tree arrives as the work left
    it: an empty delivery that scores 0, with a note. Without that word the copy failed: an error."""
    hooks = Hooks(tmp_path / "t")
    hooks.setup()
    (hooks.tree / "m.py").write_text("def f():\n    return 1\n")
    hooks.scenario(last="open", openings=[opening(time.time())])
    for name in (
        "python3",
        "setpriv",
        "pgrep",
        "pkill",
        "timeout",
        "mkdir",
        "chmod",
        "rm",
        "cat",
        "date",
        "seq",
        "sleep",
    ):
        (hooks.bin / name).write_text(
            "#!/bin/sh\nexit 126\n"
        )  # every new process fails at once
    hooks.run("fsmaint-sweep", egress="open", check=False)
    assert not (hooks.tree / ".fsmaint").exists()
    assert (
        json.loads((hooks.state / "out" / "progress").read_text())["stage"] == "started"
    )
    arrived = tmp_path / "arrived" / "sympy"
    platform_copy(hooks.tree, arrived)
    result = read_delivery(
        verifier_call,
        arrived,
        hooks.lib / "key",
        progress=hooks.state / "out" / "progress",
    )
    assert (
        result["state"] == "refused" and "began and did not finish" in result["refused"]
    ), result
    assert "error" in read_delivery(verifier_call, arrived, hooks.lib / "key"), (
        "no word from the collect step: the copy failed"
    )
    graded = grade(
        verifier_call,
        arrived,
        hooks.lib / "key",
        progress=hooks.state / "out" / "progress",
    )
    assert graded["status"] == "completed" and graded["reward"] == "0.000000", graded
    assert any("began and did not finish" in note for note in graded["notes"]), graded[
        "notes"
    ]
