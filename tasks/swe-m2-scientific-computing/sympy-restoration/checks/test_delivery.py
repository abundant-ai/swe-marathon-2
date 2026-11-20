"""The work is delivered as the agent's user left it when the work ended, and the verifier knows it.

The setup hook and the collect hook run whole under dash, as shipped, with only their absolute
paths rewritten into a scratch directory, the net check's settle time shortened, and, first on
PATH, stand-ins for what needs root or Linux: setpriv never runs a kill, pgrep and pkill find none
of the user's processes, fallocate fails (so the fallback writes the room), timeout and setsid run
their command, and python3 is this Python with outbound connections refused (or, for a scenario
in which public hosts answer after the work, completed). The net check is a stand-in that writes
the status the real one writes, after every 0.05 s, from a scenario the check sets. The delivery
the hook marks is then copied the way the platform copies an artifact (a tar, unpacked with the
`data` filter) and read by the verifier. The real net check's own logic is checked on poll streams.
"""

from __future__ import annotations

import hashlib
import hmac
import importlib.machinery
import importlib.util
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
from pathlib import Path

import pytest

ENV_DIR = Path(__file__).resolve().parent.parent / "environment"
DASH = shutil.which("dash") or "/bin/sh"
KEY = "0123456789abcdef" * 4

RUN_STDIN = """import os, socket, ssl, sys


def refuse(address, timeout=None, *args, **kwargs):
    raise ConnectionRefusedError(111, "refused")


if os.environ.get("FAKE_EGRESS") == "open":
    socket.create_connection = lambda address, timeout=None, *args, **kwargs: socket.socket()
    ssl.SSLContext.wrap_socket = lambda self, sock, *args, **kwargs: sock
else:
    socket.create_connection = refuse
assert sys.argv[1] == "-I", sys.argv
if sys.argv[2] == "-c":
    code, sys.argv = sys.argv[3], ["-c"] + sys.argv[4:]
else:
    assert sys.argv[2] == "-", sys.argv
    code, sys.argv = sys.stdin.read(), ["-"] + sys.argv[3:]
exec(compile(code, "<hook>", "exec"), {"__name__": "__main__", "__builtins__": __builtins__})
"""

# the net check's status as the real one writes it, from STATE/scenario.json, read again before every
# write: {"live": bool, "last": "open" | "closed", "openings": [...], "closing": [...] | null}
NETCHECK_STAND_IN = """import json, os, sys, time
state = sys.argv[1]
started = time.time()


def scenario():
    try:
        with open(os.path.join(state, "scenario.json")) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {"live": True, "last": "closed", "openings": [], "closing": None}


while time.time() - started < 120:
    plan = scenario()
    status = {"started_at": started, "pid": os.getpid(), "hosts": {"pypi.org": ["192.0.2.1"]}, "min_closed_polls": 3,
              "polls": 10, "openings": plan.get("openings", []), "closing": plan.get("closing"),
              "last_poll": [time.time() if plan.get("live", True) else started - 100, plan.get("last", "closed")]}
    with open(os.path.join(state, "netcheck.json.tmp"), "w") as handle:
        json.dump(status, handle)
    os.replace(os.path.join(state, "netcheck.json.tmp"), os.path.join(state, "netcheck.json"))
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


def opening(bound: float, polls: int = 30) -> dict:
    """An opening as the net check records it: the stretch of `polls` closed polls ended at `bound`."""
    return {"first_open_at": bound + 0.11, "last_closed_at": bound, "end_bound": bound, "closed_since": bound - 0.11 * polls,
            "closed_polls": polls, "host": "pypi.org"}


class Hooks:
    """The setup and collect hooks, rewritten into `root`, with the stand-ins first on PATH."""

    def __init__(self, root: Path):
        self.root = root
        self.bin, self.lib, self.state = root / "bin", root / "lib", root / "state"
        self.app = root / "app"
        self.tree = self.app / "sympy"
        for folder in (self.bin, self.lib, self.tree, self.state):
            folder.mkdir(parents=True)
        (self.bin / "run_stdin.py").write_text(RUN_STDIN)
        (self.bin / "python3").write_text(f'#!/bin/sh\nexec "{sys.executable}" -I "{self.bin}/run_stdin.py" "$@"\n')
        for name, body in STAND_INS.items():
            (self.bin / name).write_text("#!/bin/sh\n" + body)
        (self.bin / "netcheck_stand_in.py").write_text(NETCHECK_STAND_IN)
        for path in self.bin.iterdir():
            path.chmod(0o755)
        (self.lib / "key").write_text(KEY + "\n")
        (self.lib / "fsmaint-netcheck").write_text(
            f'#!/bin/sh\nexec "{sys.executable}" -I "{self.bin}/netcheck_stand_in.py" "{self.state}"\n')
        (self.lib / "fsmaint-netcheck").chmod(0o755)
        rewrites = [("/usr/bin/python3", str(self.bin / "python3")), ("/usr/local/lib/fsmaint/key", str(self.lib / "key")),
                    ("/usr/local/lib/fsmaint", str(self.lib)), ("/var/lib/fsmaint", str(self.state)), ("/app/sympy", str(self.tree))]
        for name in ("fsmaint-reserve", "fsmaint-sweep"):
            text = (ENV_DIR / name).read_text()
            for old, new in rewrites:
                text = text.replace(old, new)
            for _, new in rewrites:
                text = text.replace(new, "")
            assert not re.search(r"(?<![\w.])/(app|var|usr|run)/", text), f"{name}: every absolute path is rewritten"
            text = (ENV_DIR / name).read_text()
            for old, new in rewrites:
                text = text.replace(old, new)
            text = text.replace("NETCHECK_SETTLE_SECONDS=20\n", "NETCHECK_SETTLE_SECONDS=2\n")
            (root / name).write_text(text)
        self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}", LC_ALL="C")
        self.scenario(live=True, last="closed")

    def scenario(self, **plan) -> None:
        """What the stand-in net check reports from now on."""
        plan = dict({"live": True, "last": "closed", "openings": [], "closing": None}, **plan)
        (self.state / "scenario.json.tmp").write_text(json.dumps(plan))
        os.replace(self.state / "scenario.json.tmp", self.state / "scenario.json")

    def setup(self) -> None:
        """setup_begin, then setup_complete, as task.toml runs them; wait for the net check's first status."""
        for args in ((), ("--netcheck",)):
            done = self.run("fsmaint-reserve", *args)
            assert done.stdout == "" and done.stderr == "", done
        for _ in range(100):
            if (self.state / "netcheck.json").exists():
                return
            time.sleep(0.05)
        raise AssertionError("the net check did not start")

    def run(self, name: str, *args: str, egress: str = "closed") -> subprocess.CompletedProcess:
        env = dict(self.env, FAKE_EGRESS=egress)
        done = subprocess.run([DASH, str(self.root / name), *args], env=env, capture_output=True, text=True, timeout=300)
        assert done.returncode == 0, done
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
    lines = mark.splitlines()
    _, record_sha, signature = lines[-1].split()
    payload = ("\n".join(lines[:-1]) + "\n" + record_sha).encode()
    return record_sha == hashlib.sha256(record).hexdigest() and hmac.compare_digest(
        signature, hmac.new(KEY.encode(), payload, hashlib.sha256).hexdigest())


def read_delivery(verifier_call, top: Path, key: Path) -> dict:
    return verifier_call(f"""
import json
from pathlib import Path
from verifier import delivery
from verifier.contracts import EvaluationError
try:
    d = delivery.read_delivery(Path({str(top)!r}), Path({str(key)!r}))
    print(json.dumps({{"state": d.state, "late": sorted(d.late), "end_from": d.end_from, "end_bound": d.end_bound,
                       "entries": len(d.entries), "notes": d.notes, "egress_open": d.summary.get("egress_open")}}))
except EvaluationError as exc:
    print(json.dumps({{"error": str(exc)}}))
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


def test_both_hooks_run_whole_and_mark_an_honest_delivery_the_verifier_accepts(tmp_path, verifier_call):
    hooks = Hooks(tmp_path / "t")
    hooks.setup()
    assert (hooks.state / "room").stat().st_size == 64 << 20 and len(list((hooks.state / "inodes").iterdir())) == 64
    assert hooks.state.stat().st_mode & 0o777 == 0o700 and int((hooks.state / "work-started").read_text()) > 0
    tree = hooks.tree
    (tree / "core").mkdir()
    (tree / "core" / "basic.py").write_text("def f(x):\n    return x + 1\n")
    (tree / "core" / "notes.txt").write_text("scratch\n")
    (tree / "alias.py").symlink_to("core/basic.py")                 # a link inside the tree: removed too
    (tree / "outside").symlink_to("/etc/hosts")                     # absolute: removed
    os.mkfifo(tree / "pipe")                                        # not a file: removed
    (tree / ".fsmaint").write_text("listed 1 1\nsig 00 00\n")       # the hook's own names, left by the work
    (tree / ".fsmaint.json").symlink_to("/etc/hosts")
    time.sleep(0.6)
    end = time.time()   # the net check's last closed poll; the hosts answer again after it
    hooks.scenario(last="open", openings=[opening(end)])
    done = hooks.run("fsmaint-sweep", egress="open")
    mark = (tree / ".fsmaint").read_text()
    record_bytes = (tree / ".fsmaint.json").read_bytes()
    lines = mark.splitlines()
    assert lines[0].startswith("listed 3 ") and signed(mark, record_bytes), mark
    assert any("pipe: not a file" in line for line in lines), lines
    assert sum("a link: nothing is delivered through one" in line for line in lines) == 2, lines
    assert sum("out of the tree: this sweep writes a file of that name" in line for line in lines) == 2
    assert sorted(path.name for path in tree.iterdir()) == [".fsmaint", ".fsmaint.json", "core"]
    aside = [path for path in hooks.app.iterdir() if path.name.startswith(".aside.")]
    assert sorted(item.name for folder in aside for item in folder.iterdir()) == [".fsmaint", ".fsmaint.json"], "moved, never followed"
    assert done.stdout.splitlines() == lines[1:-1], "what the hook prints is the mark's notes"
    record = hooks.record()
    assert record["end_from"] == "netcheck" and record["end_bound"] == end and record["end_note"] is None, record
    assert record["listing_complete"] is True and record["kill_passes"] == 0 and record["processes_left"] == 0
    assert record["egress"]["any_open"] is True and record["netcheck_settle"]["fresh"] is True
    listed = {item["path"]: item for item in record["entries"]}
    assert listed["core/basic.py"]["sha256"] == hashlib.sha256(b"def f(x):\n    return x + 1\n").hexdigest()
    assert all(item["mtime"] < record["end_bound"] for item in record["entries"]), "nothing was written after the work ended"
    assert not (hooks.state / "room").exists() and not (hooks.state / "inodes").exists(), "the room is given back"
    arrived = tmp_path / "arrived" / "sympy"
    platform_copy(tree, arrived)
    result = read_delivery(verifier_call, arrived, hooks.lib / "key")
    assert result == dict(result, state="listed", late=[], end_from="netcheck", entries=3, egress_open=True), result


def test_a_turn_of_a_few_seconds_has_an_end_and_a_write_after_it_is_refused(tmp_path, verifier_call):
    # the real net check's own logic over the polls of a 3-second turn: setup still has the network,
    # then 27 closed polls, then the hosts answer again
    netcheck = load_netcheck(tmp_path / "nc")
    t, stream = 1000.0, []
    for _ in range(20):
        stream.append((t, "pypi.org"))
        t += 0.15
    for _ in range(27):
        stream.append((t, None))
        t += 0.11
    last_closed = stream[-1][0]
    for _ in range(20):
        stream.append((t, "pypi.org"))
        t += 0.15
    ended = []
    openings = netcheck.watch(iter(stream), {}, ending=lambda: ended.append(1) or (1, 0))
    assert len(openings) == 1 and openings[0]["end_bound"] == last_closed and openings[0]["closed_polls"] == 27
    assert ended == [1], "the processes of dev are ended at the opening"
    status = json.loads((tmp_path / "nc" / "netcheck.json").read_text())
    assert status["openings"][0]["end_bound"] == last_closed and status["last_poll"][1] == "open" and status["closing"] is None
    # the same turn end to end: an honest file before the end, a fetched one 0.6 s after it
    hooks = Hooks(tmp_path / "t")
    hooks.setup()
    (hooks.tree / "core").mkdir()
    (hooks.tree / "core" / "honest.py").write_text("def g():\n    return 1\n")
    time.sleep(0.6)
    end = time.time()
    time.sleep(0.6)
    (hooks.tree / "core" / "fetched.py").write_text("# written once the network was back\n")
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
root = tempfile.mkdtemp()
for name, text in (("skel", 'def f():\\n    raise NotImplementedError("RESTORE U0001")\\n'), ("work", "def f():\\n    return 2\\n")):
    os.makedirs(os.path.join(root, name, "sympy"))
    open(os.path.join(root, name, "sympy", "m.py"), "w").write(text)
os.makedirs(os.path.join(root, "cand"))
byfile = {"sympy/m.py": {"f": "U0001"}}
late, _ = restorelib.build_candidate(os.path.join(root, "skel"), os.path.join(root, "work"), os.path.join(root, "cand"), byfile,
                                     withheld={"sympy/m.py": "late"})
graded = open(os.path.join(root, "cand", "sympy", "m.py")).read()
taken, _ = restorelib.build_candidate(os.path.join(root, "skel"), os.path.join(root, "work"), os.path.join(root, "cand"), byfile)
print(json.dumps([late, "RESTORE U0001" in graded, taken]))
""")
    assert states == [{"U0001": "late"}, True, {"U0001": "restored"}]


@pytest.mark.parametrize("case", ["no-stretch", "stopped-open", "ongoing-open", "no-setup", "stopped-closed", "ongoing-closed"])
def test_without_a_known_end_of_the_work_nothing_is_graded(tmp_path, verifier_call, case):
    hooks = Hooks(tmp_path / "t")
    if case == "no-setup":
        hooks.run("fsmaint-reserve")   # setup_begin only: no start of the work, no net check
    else:
        hooks.setup()
    (hooks.tree / "a.py").write_text("x = 1\n")
    time.sleep(0.3)
    now = time.time()
    egress = "closed" if case.endswith("closed") else "open"
    if case == "no-stretch":           # the net check saw the hosts answer throughout: no closed stretch
        hooks.scenario(last="open")
    elif case.startswith("stopped"):   # the net check stopped during the work, its last poll closed
        hooks.scenario(live=False, last="closed", closing=[now - 5, now - 2, 20])
    elif case.startswith("ongoing"):   # still no answer when the work had ended
        hooks.scenario(last="closed", closing=[now - 5, now, 40])
    hooks.run("fsmaint-sweep", egress=egress)
    record = hooks.record()
    top = tmp_path / "arrived" / "sympy"
    platform_copy(hooks.tree, top)
    result = read_delivery(verifier_call, top, hooks.lib / "key")
    if case in ("stopped-closed", "ongoing-closed"):
        # no public host answered when the work had ended: nothing fetched can be in the tree
        assert record["end_from"] == "collect" and record["end_bound"] == record["sweep_started_at"], record
        assert result["state"] == "listed" and result["late"] == [] and result["end_from"] == "collect", result
    else:
        assert record["end_from"] is None and record["end_bound"] is None and record["end_note"], record
        assert "could not tell when the work ended" in result.get("error", ""), result
    if case == "stopped-open":
        assert record["netcheck_settle"]["fresh"] is False


def test_links_never_carry_a_late_file_into_the_grade(tmp_path, verifier_call):
    hooks = Hooks(tmp_path / "t")
    hooks.setup()
    tree = hooks.tree
    placeholder = 'def f():\n    raise NotImplementedError("RESTORE U0001")\n'
    (tree / "core_real").mkdir()
    (tree / "core_real" / "basic.py").write_text(placeholder)
    (tree / "core").symlink_to("core_real")                               # a directory link, planted during the work
    (tree / "core_real" / "add.py").write_text(placeholder)
    (tree / "add.py").symlink_to("core_real/add.py")                      # a file link, planted during the work
    time.sleep(0.6)
    end = time.time()
    time.sleep(0.6)
    (tree / "core_real" / "basic.py").write_text('def f():\n    return "fetched"\n')   # written through no link at all
    (tree / "core_real" / "add.py").write_text('def f():\n    return "fetched"\n')
    hooks.scenario(last="open", openings=[opening(end)])
    hooks.run("fsmaint-sweep", egress="open")
    record = hooks.record()
    assert sorted(item["path"] for item in record["entries"]) == ["core_real", "core_real/add.py", "core_real/basic.py"]
    assert sum("a link: nothing is delivered through one" in note for note in record["notes"]) == 2, record["notes"]
    arrived = tmp_path / "arrived" / "sympy"
    platform_copy(tree, arrived)
    result = read_delivery(verifier_call, arrived, hooks.lib / "key")
    assert result["state"] == "listed" and result["late"] == ["core_real/add.py", "core_real/basic.py"], result
    # the unit files the links stood for did not arrive, so nothing of them is graded
    skel = {"sympy/core/basic.py": placeholder, "sympy/add.py": placeholder}
    assert graded_states(verifier_call, skel, arrived.parent) == {"U0001": "missing", "U0002": "missing"}
    # a link that arrives anyway, or a file the record does not list, is a failed copy
    (arrived / "core").symlink_to("core_real")
    assert "A link arrived" in read_delivery(verifier_call, arrived, hooks.lib / "key").get("error", "")
    (arrived / "core").unlink()
    (arrived / "extra.py").write_text("x = 1\n")
    assert "did not list" in read_delivery(verifier_call, arrived, hooks.lib / "key").get("error", "")
    # and the transplant itself never reads a unit file through a link, on the way or at the end
    work = tmp_path / "work"
    (work / "sympy" / "core_real").mkdir(parents=True)
    (work / "sympy" / "core_real" / "basic.py").write_text("def f():\n    return 2\n")
    (work / "sympy" / "core").symlink_to("core_real")
    (work / "sympy" / "add.py").symlink_to("core_real/basic.py")
    assert graded_states(verifier_call, skel, work) == {"U0001": "missing", "U0002": "missing"}


@pytest.mark.parametrize("case", ["nothing", "unmarked", "unsigned", "forged", "record_changed", "file_changed", "file_missing",
                                  "refused", "absent", "listed"])
def test_the_mark_decides_between_an_error_a_zero_and_grading(tmp_path, verifier_call, case):
    hooks = Hooks(tmp_path / "t")
    hooks.setup()
    (hooks.tree / "a.py").write_text("x = 1\n")
    hooks.scenario(last="closed", closing=[time.time() - 5, time.time(), 40])
    hooks.run("fsmaint-sweep")
    top = tmp_path / "arrived" / "sympy"
    platform_copy(hooks.tree, top)
    mark = top / ".fsmaint"
    lines = mark.read_text().splitlines()
    if case == "nothing":
        shutil.rmtree(top)
    elif case == "unmarked":
        mark.unlink()
    elif case == "unsigned":
        mark.write_text("\n".join(lines[:-1] + [lines[-1].rsplit(" ", 1)[0] + " unsigned"]) + "\n")
    elif case == "forged":        # a mark written without the key, as the work itself could have left it
        record = (top / ".fsmaint.json").read_bytes()
        digest = hashlib.sha256(record).hexdigest()
        forged = hmac.new(b"guess", ("\n".join(lines[:-1]) + "\n" + digest).encode(), hashlib.sha256).hexdigest()
        mark.write_text("\n".join(lines[:-1] + [f"sig {digest} {forged}"]) + "\n")
    elif case == "record_changed":
        (top / ".fsmaint.json").write_text((top / ".fsmaint.json").read_text().replace('"collect"', '"netcheck"'))
    elif case == "file_changed":
        (top / "a.py").write_text("x = 2\n")
    elif case == "file_missing":
        (top / "a.py").unlink()
    elif case in ("refused", "absent"):
        other = Hooks(tmp_path / case)
        other.setup()
        if case == "absent":
            shutil.rmtree(other.tree)
        else:
            for index in range(5):
                (other.tree / f"f{index}.py").write_text("y = 1\n")
            text = (other.root / "fsmaint-sweep").read_text().replace("LIMIT_ENTRIES=200000", "LIMIT_ENTRIES=3")
            (other.root / "fsmaint-sweep").write_text(text)
        other.run("fsmaint-sweep")
        assert sorted(path.name for path in other.tree.iterdir()) == [".fsmaint", ".fsmaint.json"], "an empty tree is delivered"
        shutil.rmtree(top)
        platform_copy(other.tree, top)
    result = read_delivery(verifier_call, top, hooks.lib / "key")
    errors = {"nothing": "Nothing arrived", "unmarked": "without the collect step's mark", "unsigned": "not signed",
              "forged": "not signed", "record_changed": "differs from the one its mark signs",
              "file_changed": "arrived incomplete or changed", "file_missing": "arrived incomplete or changed"}
    if case in errors:
        assert errors[case] in result.get("error", ""), result
    else:
        assert result["state"] == ("listed" if case == "listed" else case) and "error" not in result, result


def load_netcheck(state: Path):
    """The shipped net check as a module, its state directory moved to `state`."""
    loader = importlib.machinery.SourceFileLoader("fsmaint_netcheck", str(ENV_DIR / "fsmaint-netcheck"))
    spec = importlib.util.spec_from_loader("fsmaint_netcheck", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    module.STATE = str(state)
    return module


def test_the_net_check_records_every_stretch_ends_dev_at_each_opening_and_probes_by_handshake(tmp_path):
    netcheck = load_netcheck(tmp_path / "state")
    assert netcheck.MIN_CLOSED == 3 and netcheck.HOSTS == ("pypi.org", "files.pythonhosted.org", "github.com")
    seen = []

    def ending():
        seen.append(json.loads((tmp_path / "state" / "netcheck-open.json").read_text()))
        return 2, 0

    # setup has the network, a blip of three closed polls during setup, the work with none, the
    # network back, a single closed poll after it (too short to count)
    stream = [(1.0, "pypi.org"), (2.0, None), (3.0, None), (4.0, None), (5.0, "pypi.org"), (6.0, None), (7.0, None),
              (8.0, None), (9.0, None), (10.0, "github.com"), (11.0, None), (12.0, "pypi.org"), (13.0, None)]
    openings = netcheck.watch(iter(stream), {}, ending=ending)
    assert [(o["end_bound"], o["closed_polls"], o["first_open_at"]) for o in openings] == [(4.0, 3, 5.0), (9.0, 4, 10.0)]
    assert [s["end_bound"] for s in seen] == [4.0, 9.0], "each end is recorded before anything is ended"
    final = json.loads((tmp_path / "state" / "netcheck-open.json").read_text())
    assert final["end_bound"] == 9.0 and final["kill_passes"] == 2 and final["processes_left"] == 0
    status = json.loads((tmp_path / "state" / "netcheck.json").read_text())
    assert status["last_poll"] == [13.0, "closed"] and status["closing"] == [13.0, 13.0, 1] and status["polls"] == 13
    assert [o["end_bound"] for o in status["openings"]] == [4.0, 9.0] and status["min_closed_polls"] == 3
    # two closed polls are not a stretch; the longest stretch is kept however many openings follow
    assert netcheck.watch(iter([(1.0, None)] * 2 + [(3.0, "pypi.org")]), {}, ending=ending) == []
    many = [{"closed_polls": 3 + (k == 5) * 100, "last_closed_at": float(k)} for k in range(80)]
    assert len(netcheck.kept(many)) == netcheck.KEEP_OPENINGS and many[5] in netcheck.kept(many)
    # a status that cannot be written is skipped, never a reason to stop
    netcheck.STATE = str(tmp_path / "state" / "netcheck.json" / "not-a-directory")
    assert len(netcheck.watch(iter(stream), {}, ending=lambda: (0, 0))) == 2
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
    import ssl

    assert netcheck.first_answering([("pypi.org", "127.0.0.1")], ssl.create_default_context(), seconds=2) is None
    server.close()
    assert netcheck.first_answering([("pypi.org", "127.0.0.1")], ssl.create_default_context(), seconds=1) is None

    class Completes:  # a context whose handshake completes
        def wrap_socket(self, raw, server_hostname):
            return raw

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    netcheck.PORT = listener.getsockname()[1]
    assert netcheck.first_answering([("pypi.org", "127.0.0.1")], Completes(), seconds=2) == "pypi.org"
    listener.close()
    text = (ENV_DIR / "fsmaint-netcheck").read_text()
    assert "os.setuid(entry.pw_uid)" in text and 'PROBE_USER = "nobody"' in text and "os.environ" not in text


def test_the_agent_works_as_dev_and_the_hooks_are_out_of_its_reach(task_root):
    docker = (ENV_DIR / "Dockerfile").read_text()
    for literal in ("useradd --uid 10001 --create-home dev", "chown -R dev:dev /app/sympy && chown root:root /app/sympy && chmod 0777 /app/sympy",
                    "touch /app/PROGRESS.md && chown dev:dev /app/PROGRESS.md", "chmod 1777 /app",
                    "chmod -R a-w /opt/restore/skeleton /opt/restore/lib /opt/restore/units.json", "chmod -R a+rwX /opt/restore/var",
                    "chmod 0700 /usr/local/lib/fsmaint ", "chmod 0600 /usr/local/lib/fsmaint/key", "COPY data/fsmaint.key /usr/local/lib/fsmaint/key"):
        assert literal in docker, literal
    assert "USER " not in docker and "sudo" not in docker and "/usr/local/sbin" not in docker
    toml = (task_root / "task.toml").read_text()
    head = toml.split("\n[[steps]]")[0]
    for literal in ('[agent]\ntimeout_sec = 34560\nnetwork_mode = "no-network"\nuser = "dev"\n',
                    '[[agent.setup_begin]]\ncommand = "/usr/local/lib/fsmaint/fsmaint-reserve"\nuser = "root"',
                    '[[agent.setup_complete]]\ncommand = "/usr/local/lib/fsmaint/fsmaint-reserve --netcheck"\nuser = "root"',
                    '[[verifier.collect]]\ncommand = "/usr/local/lib/fsmaint/fsmaint-sweep"\nuser = "root"\ntimeout_sec = 600'):
        assert literal in head, f"{literal!r} sits before the step tables, so the single-step bundle keeps it"
    oracle = (task_root / "steps" / "01-restore-bodies" / "solution" / "oracle.py").read_text()
    # long enough for the net check to see a few closed polls, however short the rest of the turn
    assert re.search(r"^SETTLE_SECONDS = (\d+)", oracle, re.M) and int(re.search(r"^SETTLE_SECONDS = (\d+)", oracle, re.M)[1]) >= 10
    assert "time.sleep(SETTLE_SECONDS)" in oracle
    engine = (task_root / "steps" / "01-restore-bodies" / "tests" / "verifier" / "engine.py").read_text()
    body = engine[engine.index("def measure("):]
    order = ["delivery.network_open()", "delivery.read_delivery(", "restorelib.build_candidate(skel, work_tree, cand, byfile, None, withheld=withheld)"]
    assert [body.index(step) for step in order] == sorted(body.index(step) for step in order), "the record is read before anything is graded"
    instruction = (task_root / "steps" / "01-restore-bodies" / "instruction.md").read_text()
    assert "Another copy of\nSymPy's source, from an installed package, a download, a mirror or any other place, is not to\nbe used" in instruction
    for word in ("fsmaint", "collect", "sweep", "mark", "verifier", "late", "signed"):
        assert not re.search(rf"\b{word}\b", instruction.lower()), word
