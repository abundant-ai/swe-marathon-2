#!/usr/bin/env python3
"""Item 2: the probe in an arbitrary project, skeleton poses under the dummy renderer,
InputEventAction injection, lockstep under --fixed-fps 60, overhead, pace independence,
and refusal of a forged message.

usage: item2_probe.py FOREIGN_GAME SPIKE_GAME OUT.json
"""

import hashlib
import json
import math
import os
import struct
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "qa"))
from harness import Session, memgate

foreign, spike, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
R = {}

# ---------------------------------------------------------------- A. foreign project
memgate(30, wait_s=900)
s = Session(foreign, [], log_path=out_path + ".foreign.log")
R["foreign_hello"] = s.hello
errs = []
names = ["RightUpperArm", "RightLowerArm", "RightHand"]
for k in range(60):
    f = s.step(1, observe={"census": True, "bones": {"ids": [7], "names": names}})
    t = f["t"]
    a = math.radians(t - 1)  # the project turns the arm 1 degree per completed tick
    ua = (3 - 0.2, 1.4, 5.0)
    la = (ua[0] - 0.3 * math.cos(a), ua[1] - 0.3 * math.sin(a), 5.0)
    hd = (la[0] - 0.25 * math.cos(a), la[1] - 0.25 * math.sin(a), 5.0)
    b = f["bones"]["7"]
    for nm, exp in zip(names, (ua, la, hd)):
        errs.append(math.dist(b[nm], exp))
R["skeleton_pose_max_err_m"] = max(errs)
R["skeleton_samples"] = len(errs)
# input: press at offset 0 of one command, observe the next tick
f0 = s.frame
z0 = next(e for e in f0["census"] if e["id"] == 7)["p"][2]
f1 = s.step(1, inputs=[[0, "move_forward", 1.0]])
z1 = next(e for e in f1["census"] if e["id"] == 7)["p"][2]
f2 = s.step(1, inputs=[[0, "move_forward", 0.0]])
z2 = next(e for e in f2["census"] if e["id"] == 7)["p"][2]
f3 = s.step(1)
z3 = next(e for e in f3["census"] if e["id"] == 7)["p"][2]
R["input_same_tick_dz_m"] = round(z1 - z0, 6)  # expect -3 m/s * 1/60 s = -0.05
R["input_release_dz_m"] = [round(z2 - z1, 6), round(z3 - z2, 6)]
st = s.step(1, observe={"census": False, "state": True})["state"]
R["foreign_deltas"] = st["deltas"]
R["foreign_physics_minus_process_frames"] = st["physics_frames"] - st["process_frames"]
# the harness owns the clock: hold the reply for 1 s, the tick must not move
t_before = s.frame["t"]
time.sleep(1.0)
f = s.step(1)
R["tick_advance_after_1s_hold"] = f["t"] - t_before
# forged message: bad signature -> the probe must stop the game
payload = json.dumps({"run": 1}).encode()
s.sock.sendall(struct.pack(">I", len(payload) + 32) + b"\0" * 32 + payload)
try:
    s.proc.wait(timeout=10)
    R["forged_message_exit_code"] = s.proc.returncode
except Exception:  # noqa: BLE001 - Handle failures at the task boundary.
    R["forged_message_exit_code"] = None
    s.kill()


# ---------------------------------------------------------------- B. spike game overhead
def lockstep_run(every, ticks, art="primitive", observe_view=True, delay_s=0.0):
    memgate(30, wait_s=900)
    s = Session(
        spike,
        ["--role=solo", "--seed=1", f"--art={art}"],
        log_path=out_path + f".spike_{every}.log",
    )
    s.step(
        1,
        dev=[
            ["world.reset", {"seed": 1, "density": 1.0}],
            ["player.spawn", {"at": {"lane": "e_00_10:ab0", "s": 20}}],
            ["vehicle.spawn", {"model": "sedan", "at": "player", "driver": "player"}],
        ],
    )
    h = hashlib.sha256()
    t0 = time.perf_counter()
    n = 0
    while n < ticks:
        inputs = [[0, "accelerate", 0.5]] if n == 0 else []
        f = s.step(
            every,
            inputs=inputs,
            observe={"census": True, "in_view": observe_view, "state": True},
        )
        h.update(json.dumps(f["census"], sort_keys=True).encode())
        n += every
        if delay_s:
            time.sleep(delay_s)
    wall = time.perf_counter() - t0
    rtt = sorted(s.rtt[1:])
    res = {
        "every": every,
        "ticks": n,
        "wall_s": round(wall, 3),
        "ms_per_tick": round(1000 * wall / n, 3),
        "speedup": round(n / 60.0 / wall, 2),
        "rtt_ms_p50": round(1000 * rtt[len(rtt) // 2], 3),
        "rtt_ms_p95": round(1000 * rtt[int(len(rtt) * 0.95)], 3),
        "census_size": len(f["census"]),
        "hash": h.hexdigest()[:16],
        "delay_s": delay_s,
    }
    s.close()
    return res


R["overhead"] = [lockstep_run(1, 600), lockstep_run(6, 1200), lockstep_run(60, 1800)]
# pace independence: the same run with the harness 4 ms slower per step
a = lockstep_run(3, 900)
b = lockstep_run(3, 900, delay_s=0.004)
R["pace_independent"] = {"fast": a, "slow": b, "identical": a["hash"] == b["hash"]}
with open(out_path, "w") as stream:
    json.dump(R, stream, indent=1)
print(json.dumps(R, indent=1)[:3000])
