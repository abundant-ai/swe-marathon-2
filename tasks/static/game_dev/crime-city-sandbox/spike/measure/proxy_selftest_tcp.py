#!/usr/bin/env python3
"""TCP relay self-test without Godot: echo server + client through qa/proxy.py (tcp mode)."""

import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

here = os.path.dirname(os.path.abspath(__file__))
out = sys.argv[1]
res = {}
for i, prof in enumerate(["P0", "P2", "P3"]):
    sport, cport = 25100 + 10 * i, 25101 + 10 * i
    cfg = {
        "transport": "tcp",
        "server_port": sport,
        "seed": 3,
        "duration_s": 12,
        "clients": [{"listen": cport, "profile": prof}],
        "schedule": [{"at_s": 5, "client": 0, "partition_s": 2}],
        "stats_path": os.path.join(out, f"tcp_{prof}.json"),
    }
    with open(os.path.join(out, f"tcp_{prof}.cfg"), "w") as stream:
        json.dump(cfg, stream)
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", sport))
    srv.listen(1)

    def serve(srv=srv):
        c, _ = srv.accept()
        while True:
            d = c.recv(4096)
            if not d:
                break
            c.sendall(d)

    threading.Thread(target=serve, daemon=True).start()
    px = subprocess.Popen(
        [
            sys.executable,
            os.path.join(here, "..", "qa", "proxy.py"),
            os.path.join(out, f"tcp_{prof}.cfg"),
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    px.stdout.readline()
    t0 = time.time()
    cl = socket.create_connection(("127.0.0.1", cport))
    cl.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    cl.settimeout(5)
    rtts, during = [], []
    buf = b""
    while time.time() - t0 < 9:
        ts = time.time()
        cl.sendall(json.dumps({"t": ts}).encode() + b"\n")
        while b"\n" not in buf:
            buf += cl.recv(4096)
        line, buf = buf.split(b"\n", 1)
        r = (time.time() - json.loads(line)["t"]) * 1000
        (during if 5.0 <= ts - t0 <= 7.0 else rtts).append(r)
        time.sleep(0.02)
    cl.close()
    px.wait(timeout=30)
    srv.close()
    rtts.sort()
    res[prof] = {
        "n": len(rtts),
        "rtt_ms_p50": round(rtts[len(rtts) // 2], 1),
        "rtt_ms_p95": round(rtts[int(len(rtts) * 0.95)], 1),
        "rtt_ms_max": round(rtts[-1], 1),
        "max_rtt_in_partition_window_ms": round(max(during), 1) if during else None,
        "proxy": json.loads(Path(os.path.join(out, f"tcp_{prof}.json")).read_text())[
            "clients"
        ][0],
    }
    print(
        prof,
        json.dumps({k: v for k, v in res[prof].items() if k != "proxy"}),
        flush=True,
    )
with open(os.path.join(out, "summary_tcp.json"), "w") as stream:
    json.dump(res, stream, indent=1)
