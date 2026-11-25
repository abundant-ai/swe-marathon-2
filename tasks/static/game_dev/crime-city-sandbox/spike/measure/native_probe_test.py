#!/usr/bin/env python3
"""Native-core check: the probe's key and socket live in a C GDExtension (no godot-cpp).

usage: native_probe_test.py GAME_WITH_NATIVE_CORE OUT.json [spike|foreign]
"""

import json
import os
import random
import struct
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "qa"))
from harness import Session, memgate

game, out = sys.argv[1], sys.argv[2]
kind = sys.argv[3] if len(sys.argv) > 3 else "foreign"
memgate(30, wait_s=900)
cls = "C" + "".join(random.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(10))
args = ["--role=solo", "--seed=1"] if kind == "spike" else []
s = Session(game, args, log_path=out + ".log", env_extra={"QA_PROBE_CLASS": cls})
R = {"class": cls, "hello": s.hello}
t0 = time.perf_counter()
for i in range(600):
    f = s.step(1, observe={"census": True, "state": True})
R["ticks"] = 600
R["wall_s_600_ticks_every_tick"] = round(time.perf_counter() - t0, 3)
rtt = sorted(s.rtt)
R["rtt_ms_p50"] = round(1000 * rtt[len(rtt) // 2], 3)
R["census"] = len(f["census"])
# a forged command must stop the game
payload = json.dumps({"run": 1}).encode()
s.sock.sendall(struct.pack(">I", len(payload) + 32) + b"\1" * 32 + payload)
try:
    s.proc.wait(timeout=10)
    R["forged_exit_code"] = s.proc.returncode
except Exception:  # noqa: BLE001 - Handle failures at the task boundary.
    R["forged_exit_code"] = None
    s.kill()
with open(out, "w") as stream:
    json.dump(R, stream, indent=1)
print(json.dumps(R, indent=1))
