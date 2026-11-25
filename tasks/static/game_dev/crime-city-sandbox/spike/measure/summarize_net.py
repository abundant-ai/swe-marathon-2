#!/usr/bin/env python3
"""Print the item 6 and item 5 tables from runs/item6/item6.json and runs/item5/item5.json."""

import json
import os
import sys
from pathlib import Path

root = sys.argv[1] if len(sys.argv) > 1 else "runs"
p6 = os.path.join(root, "item6", "item6.json")
if os.path.exists(p6):
    print(
        "| Transport | Profile | Client | Delivered (down) | Dup / reordered | One-way latency p50 / p95 / max (ms) | Packets during partition | First packet after it |"
    )
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in json.loads(Path(p6).read_text()):
        if "error" in r:
            print(f"| {r['transport']} | {r['profile']} | error | | | | | |")
            continue
        for c in r["clients"]:
            d = c["down"]
            f = lambda x: "-" if x is None else f"{x:.1f}"
            print(
                f"| {r['transport']} | {r['profile']} | {c['index']}{' (partitioned)' if c['index'] == 0 else ''} | "
                f"{d['delivered_frac']:.3f} ({d['unique']}/{d['sent']}) | {d['dup']} / {d['reordered']} | "
                f"{f(d['lat_ms_p50'])} / {f(d['lat_ms_p95'])} / {f(d['lat_ms_max'])} | {c['down_during_partition']} | "
                f"{c['first_packet_after_partition_s']} s |"
            )
p5 = os.path.join(root, "item5", "item5.json")
if os.path.exists(p5):
    r = json.loads(Path(p5).read_text())
    print()
    print(
        "| Process | Via | RSS (MB) | Footprint (MB) | Free memory before -> after start |"
    )
    print("| --- | --- | --- | --- | --- |")
    for s in r["starts"]:
        print(
            f"| {s['name']} | {s.get('via', 'server')} | {s.get('rss_mb')} | {s.get('footprint_mb')} | {s['free_pct_before']}% -> {s['free_pct_after']}% |"
        )
    print()
    print("final RSS", r.get("final"), "total", r.get("final_total_mb"))
    print(
        "final footprint",
        r.get("final_footprint"),
        "total",
        r.get("final_footprint_total_mb"),
    )
    print(
        "free",
        r.get("free_pct_final"),
        "stopped_early",
        r.get("stopped_early"),
        "left_running",
        r.get("left_running"),
    )
    print(
        "server stats",
        r.get("server_stats_last", [])[-1:] if r.get("server_stats_last") else None,
    )
    print("convergence", json.dumps(r.get("convergence")))
