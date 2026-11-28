"""WS3 acceptance runs on macOS (author tool; never packaged).

Parts (run one per invocation, inside scripts/heavy.py so only one heavy job runs):
  item2    Phase 0's item-2 checks with the native telemetry, in our game (the spike
           game) and in an unrelated project (the spike's foreign project): telemetry
           first among the autoloads with the link settings gone from the environment,
           bone reads (analytic arm in the foreign project), input acting in its tick,
           lockstep exactness and delta, a held reply advancing one tick, pace
           independence, a forged command stopping the game, overhead.
  replay10 One instance replayed ten times in fresh processes, in our tiny project and
           in the spike game (traffic, Jolt cars): the number of distinct trace hashes.
  hostile  Every broken or hostile project of checks/hostile_projects.py graded by the
           real grader: a reward is written for each, and what each must produce.

Every game process waits for QA_MEM_FLOOR (default 30) percent free memory first.
Results go to experiment/phase1b/<part>.json.

Usage:
  python scripts/heavy.py -- python scripts/ws3_acceptance.py PART --work DIR
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import struct
import subprocess
import sys
import time
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TASK / "common" / "kit"))
sys.path.insert(0, str(TASK / "tests"))
sys.path.insert(0, str(TASK / "checks"))

from hostile_projects import EXPECTED, build
from qakit import expect
from qakit.play import parse_play, run_play
from qakit.prepare import prepare
from qakit.procs import Limits, which_godot
from qakit.session import GameSpec, Session, SessionOptions
from qakit.trace import canonical, physical
from verifier.hostenv import memory_gate

LIB = TASK / "common" / "probe" / "build" / "darwin-arm64" / "libtelemetry.dylib"
OUT = TASK / "experiment" / "phase1b"
VENDOR_GODOT = (
    Path.home()
    / "Documents/github/Abundant/game-spike/vendor/godot-4.7.2/Godot.app/Contents/MacOS/Godot"
)


def godot() -> str:
    """The Godot binary: $QA_GODOT, else the spike's vendor copy."""
    return which_godot(os.environ.get("QA_GODOT") or str(VENDOR_GODOT))


def opts(folder: Path, **kw) -> SessionOptions:
    """Session options for an acceptance run (memory gate on)."""
    return SessionOptions(
        home=folder / "home",
        log_path=folder / "game.log",
        limits=Limits(cpu_s=600, memory_mb=1536, disk_mb=1024),
        before_start=memory_gate(),
        **kw,
    )


def prep(src: Path, work: Path, name: str):
    """Prepare (copy, telemetry, import) a project into work/name."""
    p = prepare(
        src,
        work / name / "game",
        godot(),
        LIB,
        random.Random(),
        work / name / "prep",
        Limits(wall_s=600, memory_mb=4096),
        memory_gate(),
    )
    if not p.ready:
        raise SystemExit(f"{name}: preparation failed: {p.problems}")
    return p


# ------------------------------------------------------------------ item 2
def item2_foreign(work: Path) -> dict:
    """Item-2 checks in the unrelated project (GodotPhysics3D, own autoloads)."""
    p = prep(TASK / "spike/measure/foreign_project", work, "foreign")
    r: dict = {"import_s": p.import_s}
    s = Session(GameSpec(p.game_dir, (), godot()), opts(work / "foreign-run"))
    r["hello"] = s.hello
    names = ["RightUpperArm", "RightLowerArm", "RightHand"]
    errs = []
    for _ in range(60):
        f = s.step(1, observe={"census": True, "bones": {"ids": [7], "names": names}})
        a = math.radians(f["t"] - 1)
        ua = (3 - 0.2, 1.4, 5.0)
        la = (ua[0] - 0.3 * math.cos(a), ua[1] - 0.3 * math.sin(a), 5.0)
        hd = (la[0] - 0.25 * math.cos(a), la[1] - 0.25 * math.sin(a), 5.0)
        b = f["bones"]["7"]
        errs += [math.dist(b[n], e) for n, e in zip(names, (ua, la, hd))]
    r["bone_samples"] = len(errs)
    r["bone_max_err_m"] = max(errs)

    def z(fr: dict) -> float:
        return next(e for e in fr["census"] if e["id"] == 7)["p"][2]

    z0 = z(s.frame)
    z1 = z(s.step(1, inputs=[[0, "move_forward", 1.0]]))
    z2 = z(s.step(1, inputs=[[0, "move_forward", 0.0]]))
    z3 = z(s.step(1))
    r["input_same_tick_dz_m"] = round(z1 - z0, 6)
    r["input_release_dz_m"] = [round(z2 - z1, 6), round(z3 - z2, 6)]
    st = expect.state_of(s.step(1, observe={"census": False, "state": True}))
    r["deltas_seen"] = st.get("deltas")
    r["physics_minus_process_frames"] = st["physics_frames"] - st["process_frames"]
    t_before = s.frame["t"]
    time.sleep(1.0)
    r["tick_advance_after_1s_hold"] = s.step(1)["t"] - t_before
    t0 = time.perf_counter()
    for _ in range(600):
        s.step(1, observe={"census": True, "state": True})
    r["wall_s_600_ticks_every_tick"] = round(time.perf_counter() - t0, 3)
    assert s.link is not None
    payload = json.dumps({"run": 1, "n": s.link.seq_out}).encode()
    s.link.sock.sendall(struct.pack(">I", len(payload) + 32) + b"\0" * 32 + payload)
    s.proc.wait(10)
    ex = s.proc.close(0)
    r["forged_exit_code"] = ex.code
    r["forged_strays"] = ex.stray_pids
    return r


SPIKE_SETUP = [
    ["world.reset", {"seed": 1, "density": 1.0}],
    ["player.spawn", {"at": {"lane": "e_00_10:ab0", "s": 20}}],
    ["vehicle.spawn", {"model": "sedan", "at": "player", "driver": "player"}],
]


def spike_drive(
    game_dir: Path, folder: Path, every: int, ticks: int, pace_s: float = 0.0
) -> dict:
    """The spike's item-2 drive: a player car at half throttle in traffic; returns timing and hash."""
    s = Session(GameSpec(game_dir, ("--role=solo", "--seed=1"), godot()), opts(folder))
    s.step(
        1,
        dev=SPIKE_SETUP,
        observe={"census": {"view": True}, "state": True, "every": every},
    )
    h = hashlib.sha256()
    t0 = time.perf_counter()
    n = 0
    fr = s.frame
    while n < ticks:
        fr = s.step(every, inputs=[[0, "accelerate", 0.5]] if n == 0 else [])
        h.update(canonical(physical(fr)))
        n += every
        if pace_s:
            time.sleep(pace_s)
    wall = time.perf_counter() - t0
    s.close(5.0)
    return {
        "every": every,
        "ticks": n,
        "ms_per_tick": round(1000 * wall / n, 3),
        "speedup": round(n / 60.0 / wall, 2),
        "census": len(fr.get("census", [])),
        "hash": h.hexdigest()[:16],
        "pace_s": pace_s,
    }


def item2_spike(work: Path) -> dict:
    """Item-2 checks in our game (the spike game, primitive rig, Jolt)."""
    p = prep(TASK / "spike/project", work, "spike")
    r: dict = {"import_s": p.import_s}
    s = Session(
        GameSpec(p.game_dir, ("--role=solo", "--seed=1"), godot()),
        opts(work / "spike-run"),
    )
    r["hello"] = s.hello
    fr = s.step(1, dev=SPIKE_SETUP[:2], observe={"census": True, "state": True})
    pid = next(e["id"] for e in fr["census"] if e["k"] == "player")
    q = s.step(
        1,
        queries=[
            {"id": "sk", "type": "skeleton", "entity": pid},
            {"id": "un", "type": "unregistered"},
        ],
    )
    sk = q["q"]["sk"]
    r["skeleton"] = {k: sk.get(k) for k in ("skeletons", "bound_meshes", "triangles")}
    r["skeleton_bones"] = len(sk.get("bones", []))
    r["unregistered"] = q["q"]["un"]
    names = ["Hips", "Head", "LeftHand", "RightHand", "LeftToes", "RightToes"]
    fb = s.step(1, observe={"census": True, "bones": {"ids": [pid], "names": names}})
    r["bones_read"] = sorted(fb["bones"].get(str(pid), {}))

    def ppos(fr: dict) -> list[float]:
        return next(e for e in fr["census"] if e["id"] == pid)["p"]

    p0 = ppos(s.frame)
    p1 = ppos(s.step(1, inputs=[[0, "move_forward", 1.0]]))
    r["input_same_tick_moved_m"] = round(math.dist(p0, p1), 6)
    s.step(1, inputs=[[0, "move_forward", 0.0]])
    t_before = s.frame["t"]
    time.sleep(1.0)
    r["tick_advance_after_1s_hold"] = s.step(1)["t"] - t_before
    assert s.link is not None
    payload = json.dumps({"run": 1, "n": s.link.seq_out}).encode()
    s.link.sock.sendall(struct.pack(">I", len(payload) + 32) + b"\0" * 32 + payload)
    s.proc.wait(10)
    ex = s.proc.close(0)
    r["forged_exit_code"] = ex.code
    r["overhead"] = [
        spike_drive(p.game_dir, work / "spike-o1", 1, 600),
        spike_drive(p.game_dir, work / "spike-o6", 6, 1200),
        spike_drive(p.game_dir, work / "spike-o60", 60, 1800),
    ]
    fast = spike_drive(p.game_dir, work / "spike-pace0", 3, 900)
    slow = spike_drive(p.game_dir, work / "spike-pace4", 3, 900, pace_s=0.004)
    r["pace_independent"] = {
        "fast": fast,
        "slow": slow,
        "identical": fast["hash"] == slow["hash"],
    }
    return r


# ------------------------------------------------------------------ replay x10
SPIKE_PLAY = {
    "format": "qa-play/1",
    "name": "world.replay/spike-drive",
    "template": "world.replay",
    "role": "solo",
    "args": ["--role=solo", "--seed=3"],
    "runs": [{"pace_ms": 0}],
    "limits": {"wall_s": 300, "boot_s": 60, "step_s": 30},
    "steps": [
        {"observe": {"census": True, "every": 6}},
        {"dev": [["world.reset", {"seed": 3, "density": 1.0}]]},
        {"dev": [["player.spawn", {"at": {"lane": "e_00_10:ab0", "s": 20}}]]},
        {
            "dev": [
                [
                    "vehicle.spawn",
                    {"model": "sedan", "at": "player", "driver": "player"},
                ]
            ]
        },
        {"press": {"accelerate": 0.6}},
        {"run": 300},
        {"press": {"steer_left": 0.4}},
        {"run": 120},
        {"release": ["accelerate", "steer_left"]},
        {"press": {"brake": 1.0}},
        {"run": 180},
    ],
    "expect": [],
}


def replays(game_dir: Path, play_obj: dict, work: Path, n: int) -> dict:
    """Run one play n times in fresh processes; count the distinct replay hashes."""
    play = parse_play(play_obj)
    hashes, walls, errors, frames = [], [], [], []
    for k in range(n):
        rec = run_play(
            play,
            game_dir,
            godot(),
            work / f"r{k:02d}",
            lambda _k, _n, folder: opts(folder),
        )
        run = rec.runs[0]
        errors.append(run.error)
        hashes.append(run.chain.replay_hash if run.chain else None)
        frames.append(len(run.frames))
        walls.append(rec.wall_s)
    return {
        "play": play.name,
        "runs": n,
        "distinct_hashes": len(set(hashes)),
        "hash": hashes[0],
        "frames": frames[0],
        "errors": [e for e in errors if e],
        "wall_s": walls,
    }


def part_replay10(work: Path) -> dict:
    """Ten replays in the tiny project and in the spike game."""
    tiny = prep(TASK / "tests/selftest/project", work, "tiny")
    tiny_play = json.loads(
        (TASK / "tests/selftest/plays/world.replay.two-paces.json").read_text()
    )
    tiny_play = dict(tiny_play, runs=[{"pace_ms": 0}])
    spike = prep(TASK / "spike/project", work, "spike")
    return {
        "tiny": replays(tiny.game_dir, tiny_play, work / "tiny-replays", 10),
        "spike": replays(spike.game_dir, SPIKE_PLAY, work / "spike-replays", 10),
    }


# ------------------------------------------------------------------ hostile projects
def part_hostile(work: Path, cases: list[str], instances: Path) -> dict:
    """Grade every hostile case with the real grader (self-test skipped: run separately)."""
    out = {}
    for case in cases:
        what, extra = EXPECTED[case]
        folder = work / case
        project = build(case, folder / "project")
        cmd = [
            sys.executable,
            str(TASK / "tests/verify.py"),
            "--project", str(project),
            "--out", str(folder / "out"),
            "--work", str(folder / "work"),
            "--godot", godot(),
            "--library", str(LIB),
            "--instances", str(instances),
            "--skip-selftest",
        ]  # fmt: skip
        for k, v in extra.items():
            cmd += [f"--{k.replace('_', '-')}", str(v)]
        t0 = time.monotonic()
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        reward_file = folder / "out" / "reward.txt"
        report_file = folder / "out" / "report.json"
        report = json.loads(report_file.read_text()) if report_file.exists() else {}
        strays = subprocess.run(
            ["pgrep", "-f", "sleep 4242"], capture_output=True, text=True, check=False
        ).stdout.split()
        out[case] = {
            "expected": what,
            "exit_code": proc.returncode,
            "reward_written": reward_file.exists(),
            "reward": float(reward_file.read_text()) if reward_file.exists() else None,
            "gates": {
                k: {"passed": v["passed"], "problems": v["problems"][:3]}
                for k, v in report.get("gates", {}).items()
            },
            "instances": [
                {
                    "name": i["name"],
                    "score": i["score"],
                    "failure": i["failure"],
                    "errors": [e["kind"] for e in i["detail"].get("errors", [])],
                }
                for i in report.get("instances", [])
            ],
            "stray_sleep_processes": strays,
            "wall_s": round(time.monotonic() - t0, 1),
            "stderr_tail": proc.stderr[-400:],
        }
        print(
            case,
            json.dumps({k: out[case][k] for k in ("reward", "exit_code")}),
            flush=True,
        )
    return out


def main() -> int:
    """Run one part and write its results."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("part", choices=["item2", "replay10", "hostile"])
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--cases", default=",".join(EXPECTED))
    ap.add_argument(
        "--instances", type=Path, default=TASK / "tests/selftest/instances.json"
    )
    a = ap.parse_args()
    os.environ.setdefault("QA_MEM_FLOOR", "30")
    work = a.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    if a.part == "item2":
        result = {"foreign": item2_foreign(work), "spike": item2_spike(work)}
    elif a.part == "replay10":
        result = part_replay10(work)
    else:
        result = part_hostile(work, a.cases.split(","), a.instances.resolve())
    result["_wall_s"] = round(time.monotonic() - t0, 1)
    OUT.mkdir(parents=True, exist_ok=True)
    name = (
        a.part
        if a.part != "hostile" or a.cases == ",".join(EXPECTED)
        else f"hostile-{len(a.cases.split(','))}"
    )
    (OUT / f"{name}.json").write_text(json.dumps(result, indent=1, default=str))
    print(json.dumps(result, default=str)[:3000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
