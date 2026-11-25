#!/usr/bin/env python3
"""Item 5: memory of nine headless processes on the downtown block (1 server + 8 clients).

Processes start one at a time; before each start the free-memory percentage must be >= 25,
otherwise the run stops there (and everything started is shut down). Clients 1-2 connect
through the impairment proxy at profile P2, the rest directly. After all are up, the run holds
for HOLD_S seconds, samples every process's RSS, then stops every process it started.

usage: net_item5.py GAME OUT_DIR [art]
"""
import json, math, os, signal, subprocess, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "qa"))
from harness import GODOT, memory_free_pct, memgate

game, out = sys.argv[1], sys.argv[2]
art = sys.argv[3] if len(sys.argv) > 3 else "ubc"
os.makedirs(out, exist_ok=True)
here = os.path.dirname(os.path.abspath(__file__))
PORT = 24800
HOLD_S = 40
procs = []   # (name, Popen, stdout path)


def rss_mb(pid):
    o = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return round(int(o) / 1024.0, 1) if o else None


def footprint_mb(pid):
    """macOS physical footprint (dirty, non-shared memory: what memory pressure sees)."""
    o = subprocess.run(["vmmap", "--summary", str(pid)], capture_output=True, text=True).stdout
    for line in o.splitlines():
        if line.startswith("Physical footprint:"):
            v = line.split(":")[1].strip()
            num = float(v[:-1])
            return round(num * {"K": 1 / 1024, "M": 1, "G": 1024}.get(v[-1], 1), 1)
    return None


def wait_for(path, marker, timeout):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if marker in open(path).read():
                return True
        except FileNotFoundError:
            pass
        time.sleep(0.25)
    return False


def start(name, args):
    log = os.path.join(out, f"{name}.out")
    f = open(log, "w")
    # real time, capped at 60 frames per second like a dedicated server (headless loops spin otherwise)
    p = subprocess.Popen([GODOT, "--headless", "--max-fps", "60", "--path", game, "--"] + args, stdout=f, stderr=subprocess.STDOUT)
    procs.append((name, p, log))
    return p, log


def stop_all():
    for name, p, _ in procs:
        if p.poll() is None:
            p.send_signal(signal.SIGTERM)
    t0 = time.time()
    for name, p, _ in procs:
        try:
            p.wait(timeout=max(1, 15 - (time.time() - t0)))
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(timeout=10)


report = {"art": art, "starts": [], "stopped_early": None}
memgate(30, wait_s=900)
cfg = {"transport": "udp", "server_port": PORT, "seed": 5, "duration_s": 600,
       "clients": [{"listen": PORT + 1, "profile": "P2"}, {"listen": PORT + 2, "profile": "P2"}],
       "stats_path": os.path.join(out, "proxy_stats.json")}
json.dump(cfg, open(os.path.join(out, "proxy.cfg.json"), "w"))
proxy = subprocess.Popen([sys.executable, os.path.join(here, "..", "qa", "proxy.py"), os.path.join(out, "proxy.cfg.json")],
                         stdout=subprocess.PIPE, text=True)
proxy.stdout.readline()
try:
    pct = memory_free_pct()
    p, log = start("server", ["--role=server", f"--port={PORT}", f"--art={art}", "--seed=3",
                              f"--log={os.path.abspath(os.path.join(out, 'server.jsonl'))}"])
    ok = wait_for(log, "NET_READY", 60)
    time.sleep(3)
    report["starts"].append({"name": "server", "free_pct_before": pct, "ready": ok, "rss_mb": rss_mb(p.pid), "footprint_mb": footprint_mb(p.pid),
                             "free_pct_after": memory_free_pct()})
    print(json.dumps(report["starts"][-1]), flush=True)
    for i in range(1, 9):
        pct = memory_free_pct()
        if pct < 25:
            report["stopped_early"] = f"free memory {pct}% < 25% before client {i}"
            print(report["stopped_early"], flush=True)
            break
        port = PORT + i if i <= 2 else PORT
        p, log = start(f"c{i}", ["--role=client", f"--connect=127.0.0.1:{port}", f"--name=c{i}", f"--art={art}",
                                 f"--log={os.path.abspath(os.path.join(out, f'c{i}.jsonl'))}"])
        ok = wait_for(log, "NET_CLIENT synced", 90)
        time.sleep(2)
        report["starts"].append({"name": f"c{i}", "via": "proxy P2" if i <= 2 else "direct", "free_pct_before": pct,
                                 "synced": ok, "rss_mb": rss_mb(p.pid), "footprint_mb": footprint_mb(p.pid), "free_pct_after": memory_free_pct()})
        print(json.dumps(report["starts"][-1]), flush=True)
    time.sleep(HOLD_S)
    report["final"] = {name: rss_mb(p.pid) for name, p, _ in procs}
    report["final_total_mb"] = round(sum(v for v in report["final"].values() if v), 1)
    report["final_footprint"] = {name: footprint_mb(p.pid) for name, p, _ in procs}
    report["final_footprint_total_mb"] = round(sum(v for v in report["final_footprint"].values() if v), 1)
    report["free_pct_final"] = memory_free_pct()
    stats = [l for l in open(os.path.join(out, "server.out")).read().splitlines() if l.startswith("NET_STATS ")]
    report["server_stats_last"] = [json.loads(s[len("NET_STATS "):]) for s in stats[-3:]]
finally:
    stop_all()
    proxy.terminate()
    try:
        proxy.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proxy.kill()
report["left_running"] = [name for name, p, _ in procs if p.poll() is None]


# convergence: client display vs server truth, time-shifted (design 3.6)
def load(path):
    try:
        return [json.loads(l) for l in open(path) if l.strip()]
    except FileNotFoundError:
        return []


srv = load(os.path.join(out, "server.jsonl"))
import bisect
series = {}
for rec in srv:
    for eid, p in rec["p"].items():
        series.setdefault(eid, ([], []))
        series[eid][0].append(rec["t"])
        series[eid][1].append(p)


def server_pos(eid, t):
    s = series.get(str(eid))
    if not s or t < s[0][0] or t > s[0][-1]:
        return None
    k = bisect.bisect_left(s[0], t)
    if k == 0:
        return tuple(s[1][0])
    t0, t1 = s[0][k - 1], s[0][k]
    a, b = s[1][k - 1], s[1][k]
    u = (t - t0) / max(t1 - t0, 1e-6)
    return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)


conv = {}
for i in range(1, 9):
    recs = load(os.path.join(out, f"c{i}.jsonl"))
    rtt = 0.120 if i <= 2 else 0.0
    D = 2 * rtt + 0.25
    errs = []
    for rec in recs[8:]:
        for eid, cp in rec["p"].items():
            best = None
            for k in range(41):
                sp = server_pos(int(eid), rec["t"] - D * k / 40.0)
                if sp is not None:
                    d = math.hypot(cp[0] - sp[0], cp[1] - sp[1])
                    best = d if best is None else min(best, d)
            if best is not None:
                errs.append(best)
    errs.sort()
    conv[f"c{i}"] = {"via": "proxy P2" if i <= 2 else "direct", "samples": len(errs),
                     "q95_m": round(errs[int(len(errs) * 0.95)], 3) if errs else None,
                     "max_m": round(errs[-1], 3) if errs else None}
report["convergence"] = conv
json.dump(report, open(os.path.join(out, "item5.json"), "w"), indent=1)
print(json.dumps({k: report.get(k) for k in ("final", "final_total_mb", "final_footprint", "final_footprint_total_mb", "free_pct_final", "stopped_early", "left_running")}))
print(json.dumps(report.get("server_stats_last", [])[-1:] if report.get("server_stats_last") else None))
print(json.dumps(conv))
