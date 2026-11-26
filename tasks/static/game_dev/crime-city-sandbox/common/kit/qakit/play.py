"""Plays: scripted sessions with a game, in a self-contained JSON format, and their runner.

A play file (format "qa-play/1") lists everything a session needs with every value
explicit, so it runs the same way without whatever produced it:

    {
      "format": "qa-play/1",
      "name": "world.replay/two-paces",
      "template": "world.replay",
      "rules": ["AC-15", "AC-17"],
      "role": "solo",
      "args": ["--role=solo", "--variation=4", "--save-dir={save_dir}"],
      "mode": "lockstep",
      "runs": [{"pace_ms": 0}, {"pace_ms": 4}],
      "limits": {"wall_s": 180, "cpu_s": 400, "memory_mb": 1536, "boot_s": 60, "step_s": 30},
      "steps": [ ... ],
      "expect": [ ... ],
      "tags": []
    }

Each run is a fresh game process (and a fresh home folder) running the same steps;
"pace_ms" adds that much wall time after every step, which must change nothing.
"{save_dir}" and "{home}" in args are replaced by the run's folders and "{plans}" by the
plan folder; when a plan folder is given and args name none, "--plan-dir=<plans>" is added.

In a dev step, an argument value {"$answer": [step, key]} (or [step, index, key]) is
replaced by that field of the answer to an earlier dev step's command (index counts the
commands of that step, from 0), so a play can use an id the game handed out.

Steps (one key each, run in order):
  {"observe": {...}}         observation settings for what follows: "census" (true, or
                             {"meta": [...], "view": true}), "bones" ({"ids", "names"}),
                             "camera", "hud" ([group names]), "state", "every" (ticks
                             between frames, default 6)
  {"dev": [[cmd, args], ...]} DevConsole commands, run at the next tick (1 tick)
  {"press": {action: s}}     hold actions at strength s from the next tick on
  {"release": [action, ...]} release held actions at the next tick
  {"run": N}                 advance N ticks (lockstep) or N/60 s (real time)
  {"wait_s": S}              real time only: let the game run S seconds
  {"mark": name}             remember the current tick (and the save folder's files)
  {"query": [...]}           queries answered at the next tick (1 tick)
  {"wait_for": {"event": name, "max_ticks": N}}   advance until that event arrives
  {"files": {"op": "damage"|"truncate", "since": mark}}
                             damage the save-folder files that changed since a mark
  {"restart": {}}            lockstep only: kill the process tree and start it again
                             (same home and save folders)
"""

from __future__ import annotations

import hashlib
import json
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .procs import ExitInfo, Limits
from .session import (
    GameSpec,
    RealtimeSession,
    Session,
    SessionError,
    SessionOptions,
)
from .trace import Chain, canonical, chain, write_trace

FORMAT = "qa-play/1"
STEP_KINDS = (
    "observe",
    "dev",
    "press",
    "release",
    "run",
    "wait_s",
    "mark",
    "query",
    "wait_for",
    "files",
    "restart",
)
DEFAULT_OBSERVE = {"census": True, "every": 6}
TICK_HZ = 60


class PlayError(ValueError):
    """A play file is malformed (the message says where)."""


@dataclass(frozen=True)
class Play:
    """A validated play.

    Attributes:
        name: Unique name, "<template>/<label>".
        template: The check family this play belongs to.
        rules: Design rule ids it exercises.
        role: "solo", "server" or "client".
        args: Game arguments (may contain {save_dir} and {home}).
        mode: "lockstep" or "realtime".
        runs: One dict per run ({"pace_ms": ...}).
        limits: Limits ({"wall_s", "cpu_s", "memory_mb", "boot_s", "step_s",
            "disk_mb"}).
        steps: The steps.
        expect: The expectations (see expect.py).
        tags: Free labels.
        raw: The play as loaded.
    """

    name: str
    template: str
    rules: tuple[str, ...]
    role: str
    args: tuple[str, ...]
    mode: str
    runs: tuple[dict, ...]
    limits: dict
    steps: tuple[dict, ...]
    expect: tuple[dict, ...]
    tags: tuple[str, ...]
    raw: dict

    @property
    def digest(self) -> str:
        """SHA-256 of the play's canonical JSON (identifies it exactly)."""
        return hashlib.sha256(canonical(self.raw)).hexdigest()


def _step_problem(i: int, step: object, mode: str) -> str | None:
    """Describe what is wrong with one step, or return None when it is valid."""
    if not isinstance(step, dict) or len(step) != 1:
        return f"step {i}: must be an object with one key"
    ((kind, arg),) = step.items()
    if kind not in STEP_KINDS:
        return f"step {i}: unknown step {kind!r}"
    if kind == "dev":
        ok = isinstance(arg, list) and all(
            isinstance(c, list)
            and len(c) == 2
            and isinstance(c[0], str)
            and isinstance(c[1], dict)
            for c in arg
        )
        return None if ok else f"step {i}: dev takes [[command, {{args}}], ...]"
    if kind == "run":
        ok = isinstance(arg, int) and not isinstance(arg, bool) and arg >= 1
        return None if ok else f"step {i}: run takes a tick count of at least 1"
    if kind == "wait_s":
        if mode != "realtime":
            return f"step {i}: wait_s is for real-time plays"
        return (
            None
            if isinstance(arg, (int, float)) and arg > 0
            else f"step {i}: wait_s takes seconds"
        )
    if kind == "press":
        ok = isinstance(arg, dict) and all(
            isinstance(k, str) and isinstance(v, (int, float)) for k, v in arg.items()
        )
        return None if ok else f"step {i}: press takes {{action: strength}}"
    if kind == "release":
        ok = isinstance(arg, list) and all(isinstance(a, str) for a in arg)
        return None if ok else f"step {i}: release takes [action, ...]"
    if kind == "mark":
        return None if isinstance(arg, str) and arg else f"step {i}: mark takes a name"
    if kind in ("observe", "restart"):
        if kind == "restart" and mode != "lockstep":
            return f"step {i}: restart is for lockstep plays"
        return None if isinstance(arg, dict) else f"step {i}: {kind} takes an object"
    if kind == "query":
        ok = isinstance(arg, list) and all(isinstance(q, dict) for q in arg)
        return None if ok else f"step {i}: query takes [{{...}}, ...]"
    if kind == "wait_for":
        ok = isinstance(arg, dict) and isinstance(arg.get("event"), str)
        return None if ok else f"step {i}: wait_for takes {{event, max_ticks}}"
    if kind == "files":
        ok = (
            isinstance(arg, dict)
            and arg.get("op") in ("damage", "truncate")
            and isinstance(arg.get("since"), str)
        )
        return (
            None
            if ok
            else f"step {i}: files takes {{op: damage|truncate, since: mark}}"
        )
    return None


def parse_play(obj: object) -> Play:
    """Validate a play object and return it as a Play.

    Args:
        obj: The parsed JSON of a play file.

    Returns:
        The play.

    Raises:
        PlayError: Something is missing or malformed; the message says what.
    """
    if not isinstance(obj, dict) or obj.get("format") != FORMAT:
        raise PlayError(f"not a {FORMAT} play")
    for key in ("name", "template", "role", "steps"):
        if key not in obj:
            raise PlayError(f"missing {key!r}")
    mode = obj.get("mode", "lockstep")
    if mode not in ("lockstep", "realtime"):
        raise PlayError(f"unknown mode {mode!r}")
    steps = obj["steps"]
    if not isinstance(steps, list):
        raise PlayError("steps must be a list")
    marks = set()
    for i, step in enumerate(steps):
        problem = _step_problem(i, step, mode)
        if problem:
            raise PlayError(problem)
        if "mark" in step:
            marks.add(step["mark"])
        if "files" in step and step["files"]["since"] not in marks:
            raise PlayError(f"step {i}: files refers to a mark not set before it")
    runs = obj.get("runs", [{"pace_ms": 0}])
    if (
        not isinstance(runs, list)
        or not runs
        or not all(isinstance(r, dict) for r in runs)
    ):
        raise PlayError("runs must be a non-empty list of objects")
    expect = obj.get("expect", [])
    if not isinstance(expect, list) or not all(
        isinstance(e, dict)
        and isinstance(e.get("id"), str)
        and isinstance(e.get("check"), str)
        for e in expect
    ):
        raise PlayError("expect must be a list of {id, check, ...}")
    return Play(
        name=str(obj["name"]),
        template=str(obj["template"]),
        rules=tuple(obj.get("rules", [])),
        role=str(obj["role"]),
        args=tuple(str(a) for a in obj.get("args", [])),
        mode=mode,
        runs=tuple(runs),
        limits=dict(obj.get("limits", {})),
        steps=tuple(steps),
        expect=tuple(expect),
        tags=tuple(obj.get("tags", [])),
        raw=obj,
    )


def load_play(path: Path) -> Play:
    """Read and validate a play file.

    Raises:
        PlayError: The file is not a valid play.
        OSError: The file cannot be read.
    """
    try:
        obj = json.loads(Path(path).read_text())
    except ValueError as exc:
        raise PlayError(f"{path}: not JSON: {exc}") from exc
    try:
        return parse_play(obj)
    except PlayError as exc:
        raise PlayError(f"{path}: {exc}") from exc


@dataclass
class RunRecord:
    """What one run of a play produced.

    Attributes:
        index: Run number (0-based).
        pace_ms: Extra wall time after each step.
        frames: Frames in order. Each carries "_step" (index of the step that led to it,
            -1 for a process's first frame) and "_proc" (process number in the run).
        marks: Mark name -> index of the latest frame when the mark was set.
        step_frame: Step index -> index of the frame that step produced.
        error: The failure that ended the run early ({"kind", "message", "step"}), or None.
        exits: How each process of the run ended.
        hello: Telemetry hello of the first process.
        boot_s: Seconds from process start to the first frame (first process).
        chain: Hashes of the frames (lockstep runs).
        heartbeat: Real-time heartbeat record, as a dict.
        file_ops: Save-folder operations performed.
    """

    index: int
    pace_ms: float
    frames: list[dict] = field(default_factory=list)
    marks: dict[str, int] = field(default_factory=dict)
    step_frame: dict[int, int] = field(default_factory=dict)
    error: dict | None = None
    exits: list[dict] = field(default_factory=list)
    hello: dict | None = None
    boot_s: float | None = None
    chain: Chain | None = None
    heartbeat: dict | None = None
    file_ops: list[dict] = field(default_factory=list)


@dataclass
class PlayRecord:
    """Everything a play produced: one RunRecord per run."""

    play: Play
    runs: list[RunRecord]
    wall_s: float


OptionsFactory = Callable[[int, int, Path], SessionOptions]


def exit_dict(ex: ExitInfo | None) -> dict:
    """An ExitInfo as a plain dict (empty for None)."""
    return {} if ex is None else dict(ex.__dict__)


def _snapshot(folder: Path) -> dict[str, tuple[int, int]]:
    """{relative path: (size, mtime_ns)} of the files under folder."""
    out = {}
    if folder.is_dir():
        for p in sorted(folder.rglob("*")):
            if p.is_file() and not p.is_symlink():
                st = p.stat()
                out[str(p.relative_to(folder))] = (st.st_size, st.st_mtime_ns)
    return out


def damage_files(
    folder: Path, since: dict[str, tuple[int, int]], op: str, salt: str
) -> list[str]:
    """Damage the files under folder that are new or changed since a snapshot.

    "damage" overwrites each with the same number of pseudo-random bytes (seeded by
    salt and the path, so the same play damages the same way); "truncate" cuts each
    to half its length.

    Args:
        folder: The save folder.
        since: A snapshot from _snapshot taken at the mark.
        op: "damage" or "truncate".
        salt: Text mixed into the byte pattern (the play's name).

    Returns:
        The relative paths changed, sorted.
    """
    changed = []
    for rel, sig in _snapshot(folder).items():
        if since.get(rel) == sig:
            continue
        path = folder / rel
        size = path.stat().st_size
        if op == "truncate":
            with open(path, "r+b") as f:
                f.truncate(size // 2)
        else:
            rng = random.Random(f"{salt}:{rel}")
            path.write_bytes(bytes(rng.getrandbits(8) for _ in range(max(size, 16))))
        changed.append(rel)
    return sorted(changed)


def substitute(args: tuple[str, ...], folders: dict[str, Path]) -> tuple[str, ...]:
    """Replace {save_dir}, {home} and {plans} in game arguments with the run's folders.

    When folders has "plans" and no argument sets --plan-dir, --plan-dir=<plans> is added.
    """
    out = []
    for a in args:
        for key, path in folders.items():
            a = a.replace("{" + key + "}", str(path))
        out.append(a)
    if "plans" in folders and not any(a.startswith("--plan-dir=") for a in out):
        out.append(f"--plan-dir={folders['plans']}")
    return tuple(out)


def fill_answers(value: object, answers: dict[int, list]) -> object:
    """Fill in {"$answer": [step, (index,) key]} inside a value from the recorded answers.

    Args:
        value: A dev command's arguments (or any part of them).
        answers: Step index -> the answers of that step's commands, in order.

    Returns:
        A copy with each such value filled in (None when the answer or field is missing).
    """
    if isinstance(value, dict):
        ref = value.get("$answer") if len(value) == 1 else None
        if isinstance(ref, list) and len(ref) in (2, 3):
            step, key = ref[0], ref[-1]
            index = ref[1] if len(ref) == 3 else 0
            got = answers.get(step) or []
            res = (
                got[index].get("res")
                if isinstance(index, int) and index < len(got)
                else None
            )
            return res.get(key) if isinstance(res, dict) else None
        return {k: fill_answers(v, answers) for k, v in value.items()}
    if isinstance(value, list):
        return [fill_answers(v, answers) for v in value]
    return value


def limits_of(play: Play) -> Limits:
    """Process limits for a play's game processes (from play.limits, with defaults)."""
    lim = play.limits
    return Limits(
        cpu_s=lim.get("cpu_s", 600),
        memory_mb=lim.get("memory_mb", 1536),
        wall_s=lim.get("process_wall_s"),
        disk_mb=lim.get("disk_mb", 1024),
    )


def resolve_observe(obs: dict, frame: dict | None) -> dict:
    """Replace entity roles in observation settings with entity ids.

    Bone observations may name an entity by role ("player": the first entity of kind
    player in the latest census) instead of by id, so a play need not know ids in
    advance. A role with no matching entity yet is left out.

    Args:
        obs: Observation settings as written in the play.
        frame: The latest frame (its census is used), or None.

    Returns:
        A copy of obs with numeric ids only.
    """
    bones = obs.get("bones")
    if not isinstance(bones, dict):
        return dict(obs)
    by_kind: dict[str, int] = {}
    for e in (frame or {}).get("census") or []:
        if isinstance(e.get("id"), int) and e.get("k") not in by_kind:
            by_kind[e.get("k")] = e["id"]
    ids = []
    for x in bones.get("ids", []):
        if isinstance(x, str):
            if x in by_kind:
                ids.append(by_kind[x])
        else:
            ids.append(x)
    out = dict(obs)
    out["bones"] = dict(bones, ids=ids)
    return out


class _LockstepRun:
    """Executes one lockstep run of a play (see run_play)."""

    def __init__(
        self,
        play: Play,
        spec: GameSpec,
        opts: SessionOptions,
        rec: RunRecord,
        save_dir: Path,
    ) -> None:
        self.play = play
        self.spec = spec
        self.opts = opts
        self.rec = rec
        self.save_dir = save_dir
        self.obs = dict(DEFAULT_OBSERVE)
        self.obs_sent: dict | None = None
        self.held: dict[str, float] = {}
        self.pending: list[list] = []
        self.proc_no = 0
        self.session: Session | None = None
        self.snapshots: dict[str, dict] = {}
        self.t0 = time.monotonic()
        self.waited = 0.0  # seconds spent waiting before process starts (not play time)

    def start(self) -> None:
        """Start a game process and record its first frame."""
        session = Session(self.spec, self.opts)
        self.waited += session.gate_wait_s
        self.session = session
        if self.rec.hello is None:
            self.rec.hello = self.session.hello
            self.rec.boot_s = round(self.session.t_first_frame_s, 3)
        first = dict(self.session.frame)
        first.update(_step=-1, _proc=self.proc_no)
        self.rec.frames.append(first)
        self.obs_sent = None
        self.held = {}

    def advance(self, ticks: int, step_i: int, dev=(), queries=()) -> dict:
        """Advance `ticks` ticks in frames of obs["every"] ticks; return the last frame."""
        assert self.session is not None
        every = max(1, int(self.obs.get("every", 6)))
        left = max(1, ticks)
        fr = self.session.frame
        first = True
        while left > 0:
            n = min(left, every) if not (dev or queries) or not first else 1
            obs = resolve_observe(self.obs, self.session.frame)
            fr = self.session.step(
                run=n,
                inputs=self.pending if first else (),
                dev=dev if first else (),
                observe=obs if obs != self.obs_sent else None,
                queries=queries if first else (),
            )
            self.obs_sent = obs
            self.pending, first = [], False
            rec = dict(fr)
            rec.update(_step=step_i, _proc=self.proc_no)
            self.rec.frames.append(rec)
            left -= n
            if self.rec.pace_ms:
                time.sleep(self.rec.pace_ms / 1000.0)
            self._check_time()
        return fr

    def _answers(self) -> dict[int, list]:
        """Step index -> the DevConsole answers recorded for that step so far."""
        out: dict[int, list] = {}
        for fr in self.rec.frames:
            for d in fr.get("dev") or []:
                out.setdefault(fr.get("_step"), []).append(d)
        return out

    def _check_time(self) -> None:
        wall = self.play.limits.get("wall_s")
        if wall is not None and time.monotonic() - self.t0 - self.waited > wall:
            raise SessionError("play_time", f"the play took longer than {wall} s")

    def do(self, i: int, kind: str, arg) -> None:
        """Execute step i."""
        if kind == "observe":
            self.obs = dict(DEFAULT_OBSERVE, **arg)
        elif kind == "press":
            for a, v in arg.items():
                if self.held.get(a) != float(v):
                    self.pending.append([0, a, float(v)])
                    self.held[a] = float(v)
        elif kind == "release":
            for a in arg:
                if self.held.get(a, 0.0) != 0.0:
                    self.pending.append([0, a, 0.0])
                    self.held[a] = 0.0
        elif kind == "dev":
            self.advance(1, i, dev=fill_answers(arg, self._answers()))
            self.rec.step_frame[i] = len(self.rec.frames) - 1
        elif kind == "query":
            self.advance(1, i, queries=arg)
            self.rec.step_frame[i] = len(self.rec.frames) - 1
        elif kind == "run":
            self.advance(int(arg), i)
            self.rec.step_frame[i] = len(self.rec.frames) - 1
        elif kind == "mark":
            self.rec.marks[arg] = len(self.rec.frames) - 1
            self.snapshots[arg] = _snapshot(self.save_dir)
        elif kind == "files":
            done = damage_files(
                self.save_dir, self.snapshots[arg["since"]], arg["op"], self.play.name
            )
            self.rec.file_ops.append({"step": i, "op": arg["op"], "files": done})
        elif kind == "wait_for":
            self._wait_for(i, arg)
        elif kind == "restart":
            assert self.session is not None
            self.rec.exits.append(exit_dict(self.session.kill()))
            self.proc_no += 1
            self.start()

    def _wait_for(self, i: int, arg: dict) -> None:
        """Advance until the named event arrives or max_ticks pass."""
        want, limit = arg["event"], int(arg.get("max_ticks", 600))
        done = 0
        while done < limit:
            fr = self.advance(min(6, limit - done), i)
            done += min(6, limit - done)
            if any(
                isinstance(e, dict) and e.get("n") == want
                for e in fr.get("events") or []
            ):
                break
        self.rec.step_frame[i] = len(self.rec.frames) - 1

    def execute(self) -> None:
        """Run every step; on failure record the error and stop."""
        step_i = -1
        try:
            self.start()
            for step_i, step in enumerate(self.play.steps):
                ((kind, arg),) = step.items()
                self.do(step_i, kind, arg)
        except SessionError as exc:
            self.rec.error = {"kind": exc.kind, "message": str(exc), "step": step_i}
        finally:
            if self.session is not None:
                ex = self.session.exit_info or self.session.close(5.0)
                self.rec.exits.append(exit_dict(ex))
        self.rec.chain = chain(self.rec.frames)


class _RealtimeRun:
    """Executes one real-time run of a play (see run_play)."""

    def __init__(
        self, play: Play, spec: GameSpec, opts: SessionOptions, rec: RunRecord
    ) -> None:
        self.play = play
        self.spec = spec
        self.opts = opts
        self.rec = rec

    def execute(self) -> None:
        """Run every step; record frames, heartbeat and any failure."""
        session = None
        step_i = -1
        held: dict[str, float] = {}
        gap_s = float(self.play.limits.get("heartbeat_gap_s", 1.0))
        try:
            session = RealtimeSession(self.spec, self.opts, gap_s=gap_s)
            self.rec.hello = session.hello
            session.send({"observe": dict(DEFAULT_OBSERVE)})
            for step_i, step in enumerate(self.play.steps):
                ((kind, arg),) = step.items()
                if kind == "observe":
                    session.send({"observe": dict(DEFAULT_OBSERVE, **arg)})
                elif kind == "dev":
                    session.send({"dev": arg})
                elif kind == "query":
                    session.send({"queries": arg})
                elif kind in ("press", "release"):
                    vals = arg if kind == "press" else {a: 0.0 for a in arg}
                    inputs = [
                        [0, a, float(v)]
                        for a, v in vals.items()
                        if held.get(a) != float(v)
                    ]
                    held.update({a: float(v) for a, v in vals.items()})
                    if inputs:
                        session.send({"inputs": inputs})
                elif kind == "wait_s":
                    session.wait(float(arg))
                elif kind == "run":
                    session.wait(int(arg) / TICK_HZ)
                elif kind == "mark":
                    self.rec.marks[arg] = len(session.frames) - 1
        except SessionError as exc:
            self.rec.error = {"kind": exc.kind, "message": str(exc), "step": step_i}
        finally:
            if session is not None:
                self.rec.heartbeat = session.heartbeat().__dict__
                self.rec.frames = list(session.frames)
                ex = session.exit_info or session.close(5.0)
                self.rec.exits.append(exit_dict(ex))


def run_play(
    play: Play,
    game_dir: Path,
    godot: str,
    work: Path,
    options: OptionsFactory,
    write_traces: bool = True,
    plans: Path | None = None,
) -> PlayRecord:
    """Run every run of a play against a prepared game and record what happened.

    Args:
        play: The play.
        game_dir: A prepared copy of the game (prepare.prepare).
        godot: Absolute path of the Godot binary.
        work: Folder for this play's runs (home, saves, logs, traces); created.
        options: options(run_index, process_number, run_folder) -> SessionOptions for
            each game process (the caller decides limits, logs and the memory gate;
            the home folder must be run_folder / "home").
        write_traces: Write each lockstep run's trace to run_folder / "trace.jsonl.gz".
        plans: The plan folder for "{plans}" and the default --plan-dir, or None.

    Returns:
        The record. Failures of the game are recorded in each RunRecord.error; this
        function raises only for problems of the kit itself (such as a full disk).
    """
    t0 = time.monotonic()
    runs = []
    for k, run_spec in enumerate(play.runs):
        folder = work / f"run{k}"
        save_dir = folder / "saves"
        save_dir.mkdir(parents=True, exist_ok=True)
        folders = {"save_dir": save_dir, "home": folder / "home"}
        if plans is not None:
            folders["plans"] = Path(plans)
        args = substitute(play.args, folders)
        spec = GameSpec(game_dir, args, godot, mode=play.mode)
        rec = RunRecord(index=k, pace_ms=float(run_spec.get("pace_ms", 0)))
        opts = options(k, 0, folder)
        if play.mode == "lockstep":
            _LockstepRun(play, spec, opts, rec, save_dir).execute()
            if write_traces and rec.chain is not None:
                header = {"play": play.name, "run": k, "args": list(args)}
                write_trace(folder / "trace.jsonl.gz", header, rec.frames, rec.chain)
        else:
            _RealtimeRun(play, spec, opts, rec).execute()
        runs.append(rec)
    return PlayRecord(play, runs, round(time.monotonic() - t0, 3))
