"""The grader's self-test: the kit checked on a tiny project of ours before any grading.

It runs first. If it fails, the machine or the kit is broken and nothing it would say
about a submission can be trusted, so no reward is written (the only path that leaves
none). It checks, on tests/selftest/project:

1. preparation: the copy imports, the engine registers the telemetry library;
2. the telemetry hello: native core, first autoload, one worker thread, 60 ticks, jitter
   fix 0, link settings gone from the environment (and the game's own state report says
   it cannot see the key);
3. every self-test play holds all its expectations and the standing checks (lockstep
   exactness is checked on every step by the session itself): same-tick input,
   DevConsole robustness, replay at two paces, same start per variation, a damaged save
   slot, a SIGKILL and restart, and the real-time heartbeat;
4. bone reads match the project's analytic arm within 1e-4 m;
5. a forged command stops the game with exit code 3;
6. a real-time stall of 1.5 s shows as a heartbeat gap (the gap detector works);
7. a kill leaves no process of the tree behind.
"""

from __future__ import annotations

import dataclasses
import json
import math
import random
import struct
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from qakit import expect
from qakit.play import load_play, run_play
from qakit.prepare import prepare
from qakit.procs import Limits
from qakit.session import (
    GameSpec,
    RealtimeSession,
    Session,
    SessionError,
    SessionOptions,
)

HELLO_WANT = {
    "native": True,
    "first_autoload": True,
    "worker_threads": 1,
    "ticks": 60,
    "settings_in_environment": 0,
}


@dataclass
class SelftestResult:
    """The self-test's verdict.

    Attributes:
        ok: Every check held.
        problems: What failed, in plain words.
        measured: Values measured along the way.
        wall_s: Seconds the self-test took.
    """

    ok: bool
    problems: list[str] = field(default_factory=list)
    measured: dict = field(default_factory=dict)
    wall_s: float = 0.0


def arm_positions(body: list[float], deg: float) -> dict[str, list[float]]:
    """Where Tiny Town's right-arm bones are for a body position and arm angle.

    The upper arm sits at body + (-0.2, 1.4, 0) and turns about z by `deg` degrees;
    the lower arm and the hand are 0.3 m and 0.25 m further along it.
    """
    a = math.radians(deg)
    ua = [body[0] - 0.2, body[1] + 1.4, body[2]]
    la = [ua[0] - 0.3 * math.cos(a), ua[1] - 0.3 * math.sin(a), ua[2]]
    hd = [la[0] - 0.25 * math.cos(a), la[1] - 0.25 * math.sin(a), la[2]]
    return {"RightUpperArm": ua, "RightLowerArm": la, "RightHand": hd}


def check_bones(
    game_dir: Path, godot: str, opts: SessionOptions
) -> tuple[list[str], dict]:
    """Bone reads against the analytic arm, over 30 ticks."""
    probs: list[str] = []
    s = Session(GameSpec(game_dir, ("--role=solo", "--variation=1"), godot), opts)
    errs: list[float] = []
    try:
        fr = s.step(
            1, dev=[["player.spawn", {"at": [1.5, 0.0, 2.0]}]], observe={"census": True}
        )
        pid = next(e["id"] for e in fr["census"] if e.get("k") == "player")
        names = list(arm_positions([0, 0, 0], 0))
        obs = {"census": True, "state": True, "bones": {"ids": [pid], "names": names}}
        for _ in range(30):
            fr = s.step(1, observe=obs)
            st = expect.state_of(fr)
            body = next(e["p"] for e in fr["census"] if e.get("id") == pid)
            want = arm_positions(body, float(st["arm_deg"]))
            got = fr["bones"][str(pid)]
            errs += [math.dist(got[n], want[n]) for n in names]
    finally:
        s.close(5.0)
    worst = max(errs) if errs else None
    if worst is None or worst > 1e-4:
        probs.append(f"bone reads off the analytic arm by {worst} m")
    return probs, {"bone_samples": len(errs), "bone_max_err_m": worst}


def check_forged(
    game_dir: Path, godot: str, opts: SessionOptions
) -> tuple[list[str], dict]:
    """A command with a bad tag must stop the game with exit code 3."""
    s = Session(GameSpec(game_dir, ("--role=solo",), godot), opts)
    assert s.link is not None
    payload = json.dumps({"run": 1, "n": s.link.seq_out}).encode()
    s.link.sock.sendall(struct.pack(">I", len(payload) + 32) + b"\x01" * 32 + payload)
    s.proc.wait(10)
    ex = s.proc.close(0)
    probs = (
        []
        if ex.code == 3
        else [f"a forged command ended the game with {ex.code}/{ex.signal}"]
    )
    return probs, {"forged_exit": ex.code, "forged_strays": ex.stray_pids}


def check_stall_detected(
    game_dir: Path, godot: str, opts: SessionOptions
) -> tuple[list[str], dict]:
    """A 1.5 s stall in real time must show as a heartbeat gap of at least 1.2 s."""
    s = RealtimeSession(
        GameSpec(game_dir, ("--role=solo",), godot, mode="realtime"), opts, gap_s=1.0
    )
    try:
        s.wait(1.0)
        before = s.heartbeat()
        s.send({"dev": [["debug.stall", {"ms": 1500}]]})
        s.wait(2.5)
        after = s.heartbeat()
    finally:
        s.close(5.0)
    probs = []
    if before.count < 30 or before.skipped or before.max_gap_s > 1.0:
        probs.append(f"heartbeat not steady before the stall: {before.__dict__}")
    if after.max_gap_s < 1.2:
        probs.append(
            f"a 1.5 s stall was not seen (largest gap {after.max_gap_s:.2f} s)"
        )
    return probs, {"steady": before.__dict__, "stalled": after.__dict__}


def check_kill(
    game_dir: Path, godot: str, opts: SessionOptions
) -> tuple[list[str], dict]:
    """Killing a running game leaves nothing of its process tree."""
    s = Session(GameSpec(game_dir, ("--role=solo",), godot), opts)
    s.step(30)
    ex = s.kill()
    probs = (
        []
        if not ex.stray_pids and ex.signal == 9
        else [f"kill left {ex.stray_pids}, signal {ex.signal}"]
    )
    return probs, {"kill_signal": ex.signal, "kill_strays": ex.stray_pids}


def run_selftest(
    selftest_dir: Path,
    godot: str,
    library: Path,
    work: Path,
    options: Callable[[Path, object], SessionOptions],
    before_start=None,
) -> SelftestResult:
    """Run the self-test checks, stopping at the first problem; never raises for one.

    Args:
        selftest_dir: tests/selftest (project/, plays/, instances.json).
        godot: Godot binary.
        library: The built telemetry library.
        work: Scratch folder (created).
        options: options(folder, play_or_None) -> SessionOptions for a game process
            (a play's own limits apply when one is given).
        before_start: Hook run before the import starts (the memory gate).

    Returns:
        The verdict with what was measured.
    """
    t0 = time.monotonic()
    res = SelftestResult(ok=False)
    work.mkdir(parents=True, exist_ok=True)
    try:
        prep = prepare(
            selftest_dir / "project",
            work / "game",
            godot,
            library,
            random.Random(),
            work / "prep",
            Limits(wall_s=300),
            before_start,
        )
        res.measured["import_s"] = prep.import_s
        if not prep.ready:
            res.problems += [f"preparation: {p}" for p in prep.problems]
            return res
        game = prep.game_dir
        # First a short start-up: when the kit cannot reach the game at all, say so
        # in seconds instead of letting every play wait out its start-up allowance.
        first = dataclasses.replace(options(work / "first", None), boot_s=20.0)
        try:
            probs, measured = check_kill(game, godot, first)
        except SessionError as exc:
            probs, measured = [f"first start: {exc.kind}: {exc}"], {}
        res.measured["first"] = measured
        if probs:
            res.problems += probs
            return res
        manifest = json.loads((selftest_dir / "instances.json").read_text())
        for inst in manifest["instances"]:
            play = load_play(selftest_dir / inst["file"])
            rec = run_play(
                play,
                game,
                godot,
                work / "plays" / play.name.replace("/", "."),
                lambda _k, _n, folder, _p=play: options(folder, _p),
            )
            outcomes = expect.check_play(rec) + expect.standing(rec)
            bad = [o for o in outcomes if o.ok is not True]
            res.measured[play.name] = {
                "wall_s": rec.wall_s,
                "failed": [(o.id, o.note) for o in bad],
            }
            for o in bad:
                res.problems.append(f"{play.name}: {o.id} did not hold ({o.note})")
            if rec.runs and rec.runs[0].hello:
                hello = rec.runs[0].hello
                for k, v in HELLO_WANT.items():
                    if hello.get(k) != v:
                        res.problems.append(
                            f"{play.name}: hello {k} is {hello.get(k)!r}, expected {v!r}"
                        )
            for r in rec.runs:
                for fr in r.frames:
                    if expect.state_of(fr).get("key_visible") is True:
                        res.problems.append(
                            f"{play.name}: the game could read the link key"
                        )
                        break
            if res.problems:  # one failure is enough: the kit cannot be trusted
                return res
        for name, fn in (
            ("bones", check_bones),
            ("forged", check_forged),
            ("stall", check_stall_detected),
            ("kill", check_kill),
        ):
            try:
                probs, measured = fn(game, godot, options(work / name, None))
            except (SessionError, KeyError, StopIteration, TypeError) as exc:
                probs, measured = [f"{name}: {exc!r}"], {}
            res.problems += probs
            res.measured[name] = measured
            if res.problems:
                return res
    finally:
        res.wall_s = round(time.monotonic() - t0, 2)
    res.ok = not res.problems
    return res
