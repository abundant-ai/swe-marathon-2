#!/usr/bin/env python3
"""Item 6: the impairment proxy with ENet (UDP) and WebSocket (TCP) peers.

One Godot process (role nettest) hosts a server peer and two client peers; each client peer
connects to its own proxy port. Client 0 is partitioned for 3 s at t = 12 s. Every packet is
stamped with the shared system clock, so latency is one-way.

usage: net_item6.py GAME OUT_DIR
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "qa"))
from harness import GODOT, memgate

game, out = sys.argv[1], sys.argv[2]
TRANSPORTS = sys.argv[3].split(",") if len(sys.argv) > 3 else ["enet", "ws"]
PROFILES = sys.argv[4].split(",") if len(sys.argv) > 4 else ["P0", "P1", "P2", "P3"]
EXTRA = sys.argv[5:]
os.makedirs(out, exist_ok=True)
here = os.path.dirname(os.path.abspath(__file__))
results = []
run = 0
for transport in TRANSPORTS:
    for profile in PROFILES:
        memgate(30, wait_s=600)
        base = 24700 + 10 * run
        run += 1
        cfg = {
            "transport": "udp" if transport == "enet" else "tcp",
            "server_port": base,
            "seed": 7,
            "duration_s": 32,
            "clients": [
                {"listen": base + 1, "profile": profile},
                {"listen": base + 2, "profile": profile},
            ],
            "schedule": [{"at_s": 12, "client": 0, "partition_s": 3}],
            "stats_path": os.path.join(out, f"proxy_{transport}_{profile}.json"),
        }
        cfg_path = os.path.join(out, f"proxy_{transport}_{profile}.cfg.json")
        with open(cfg_path, "w") as stream:
            json.dump(cfg, stream)
        px = subprocess.Popen(
            [sys.executable, os.path.join(here, "..", "qa", "proxy.py"), cfg_path],
            stdout=subprocess.PIPE,
            text=True,
        )
        px.stdout.readline()  # ready
        t_proxy = time.time()
        g = subprocess.run(
            [
                GODOT,
                "--headless",
                "--max-fps",
                "60",
                "--path",
                game,
                "--",
                "--role=nettest",
                f"--transport={transport}",
                f"--port={base}",
                f"--client-ports={base + 1},{base + 2}",
                "--seconds=25",
            ]
            + EXTRA,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        line = next(
            (l for l in g.stdout.splitlines() if l.startswith("NETTEST_RESULT ")), None
        )
        px.wait(timeout=60)
        if line is None:
            results.append(
                {
                    "transport": transport,
                    "profile": profile,
                    "error": g.stdout[-800:] + g.stderr[-800:],
                }
            )
            print(json.dumps(results[-1])[:600], flush=True)
            continue
        r = json.loads(line[len("NETTEST_RESULT ") :])
        # partition window in the nettest clock: proxy started t_proxy, partition at +12 s
        part_t0 = t_proxy + 12.0 - r["t0"]
        row = {"transport": transport, "profile": profile, "clients": []}
        for c in r["clients"]:
            raw = c.pop("down_raw")
            during = [x for x in raw if part_t0 + 0.3 <= x[0] <= part_t0 + 2.7]
            after = [x for x in raw if x[0] > part_t0 + 3.0]
            first_after = (after[0][0] - (part_t0 + 3.0)) if after else None
            c["down_during_partition"] = len(during)
            c["down_per_second"] = [
                sum(1 for x in raw if k <= x[0] < k + 1) for k in range(26)
            ]
            c["first_packet_after_partition_s"] = (
                round(first_after, 3) if first_after is not None else None
            )
            row["clients"].append(c)
        row["proxy"] = json.loads(Path(cfg["stats_path"]).read_text())["clients"]
        results.append(row)
        brief = [
            {
                k: (round(v, 3) if isinstance(v, float) else v)
                for k, v in c["down"].items()
            }
            for c in row["clients"]
        ]
        print(
            json.dumps(
                {
                    "transport": transport,
                    "profile": profile,
                    "down": brief,
                    "partition": [
                        (
                            c["down_during_partition"],
                            c["first_packet_after_partition_s"],
                        )
                        for c in row["clients"]
                    ],
                }
            ),
            flush=True,
        )
with open(os.path.join(out, "item6.json"), "w") as stream:
    json.dump(results, stream, indent=1)
