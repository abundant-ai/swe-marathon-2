#!/usr/bin/env python3
"""Proxy self-test without Godot: a UDP echo server and a client exchanging stamped datagrams
through qa/proxy.py at each profile; reports measured loss, one-way delay and jitter."""
import json, os, socket, subprocess, sys, threading, time, statistics
here = os.path.dirname(os.path.abspath(__file__))
out = sys.argv[1]
DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 8.0
res = {}
for i, prof in enumerate(["P0", "P1", "P2", "P3"]):
    sport, cport = 25000 + 10 * i, 25001 + 10 * i
    cfg = {"transport": "udp", "server_port": sport, "seed": 3, "duration_s": DUR + 4,
           "clients": [{"listen": cport, "profile": prof}], "stats_path": os.path.join(out, f"udp_{prof}.json")}
    json.dump(cfg, open(os.path.join(out, f"udp_{prof}.cfg"), "w"))
    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); srv.bind(("127.0.0.1", sport)); srv.settimeout(0.5)
    stop = False
    def echo():
        while not stop:
            try:
                d, a = srv.recvfrom(2048); srv.sendto(d, a)
            except socket.timeout:
                pass
    th = threading.Thread(target=echo, daemon=True); th.start()
    px = subprocess.Popen([sys.executable, os.path.join(here, "..", "qa", "proxy.py"), os.path.join(out, f"udp_{prof}.cfg")], stdout=subprocess.PIPE, text=True)
    px.stdout.readline()
    cl = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); cl.settimeout(0.01)
    sent, rtts, seen = 0, [], {}
    t_end = time.time() + DUR
    while time.time() < t_end:
        msg = json.dumps({"s": sent, "t": time.time()}).encode()
        cl.sendto(msg, ("127.0.0.1", cport)); sent += 1
        t_wait = time.time() + 1 / 100
        while time.time() < t_wait:
            try:
                d, _ = cl.recvfrom(2048); m = json.loads(d)
                seen[m["s"]] = seen.get(m["s"], 0) + 1
                rtts.append((time.time() - m["t"]) * 1000)
            except socket.timeout:
                pass
    time.sleep(1.0)
    try:
        while True:
            d, _ = cl.recvfrom(2048); m = json.loads(d); seen[m["s"]] = seen.get(m["s"], 0) + 1; rtts.append((time.time() - m["t"]) * 1000)
    except socket.timeout:
        pass
    stop = True; px.wait(timeout=30); srv.close(); cl.close()
    rtts.sort()
    res[prof] = {"sent": sent, "round_trip_delivered": round(len(seen) / sent, 4), "dups_seen": sum(v - 1 for v in seen.values()),
                 "rtt_ms_p50": round(rtts[len(rtts) // 2], 1), "rtt_ms_p05": round(rtts[int(len(rtts) * .05)], 1), "rtt_ms_p95": round(rtts[int(len(rtts) * .95)], 1)}
    print(prof, json.dumps(res[prof]), flush=True)
json.dump(res, open(os.path.join(out, "summary.json"), "w"), indent=1)
