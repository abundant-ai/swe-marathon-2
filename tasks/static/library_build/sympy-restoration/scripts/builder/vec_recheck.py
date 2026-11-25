"""Replay the selected vectors on the original tree under more hash seeds; drop any that
the original tree does not reproduce.  usage: vec_recheck.py <work_dir> <seed> [<seed> ...]"""

import json
import os
import pickle
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "task_src"))
from canon import same

W = os.path.abspath(sys.argv[1])
seeds = sys.argv[2:]
RV = os.path.join(HERE, "task_src", "rvector.py")
vd = os.path.join(W, "vectors")
with open(os.path.join(vd, "inputs.pkl"), "rb") as stream:
    payload = pickle.load(stream)
gold = json.loads(Path(os.path.join(vd, "gold.json")).read_text())
# the tree the grader replays on has no test directories
oracle = os.environ.get("VEC_TREE") or os.path.join(W, "cand_oracle_nt")
REPORT_ONLY = os.environ.get("VEC_REPORT_ONLY") == "1"  # count matches, change nothing
MAX_MS = float(os.environ.get("VEC_MAX_MS", "1500"))
CALL_TIMEOUT = os.environ.get("VEC_CALL_TIMEOUT", "5")
WORKERS = int(os.environ.get("VEC_WORKERS", "10"))

slow = {}


def replay(seed):
    scratch = tempfile.mkdtemp(prefix="vrc-")

    def one(item):
        k, (mod, p) = item
        ip, op = (
            os.path.join(scratch, f"i{k}.pkl"),
            os.path.join(scratch, f"o{k}.jsonl"),
        )
        with open(ip, "wb") as stream:
            pickle.dump(p, stream, protocol=4)
        env = dict(os.environ, PYTHONHASHSEED=str(seed), PYTHONDONTWRITEBYTECODE="1")
        try:
            subprocess.run(
                [sys.executable, "-B", RV, oracle, mod, ip, op, CALL_TIMEOUT],
                check=False,
                env=env,
                cwd=oracle,
                timeout=float(CALL_TIMEOUT) * len(p["vectors"]) + 600,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired:
            pass
        out = {}
        try:
            with open(op) as stream:
                for line in stream:
                    r = json.loads(line)
                    if "v" not in r:  # the line that says the module was imported
                        continue
                    out[r["v"]] = r["c"]
                    slow[r["v"]] = max(slow.get(r["v"], 0), r.get("ms", 0))
        except OSError:
            pass
        return out

    res = {}
    with ThreadPoolExecutor(WORKERS) as ex:
        for o in ex.map(one, list(enumerate(sorted(payload.items())))):
            res.update(o)
    return res


for seed in seeds:
    r = replay(seed)
    if REPORT_ONLY:
        n = sum(1 for v, g in gold.items() if r.get(v) is not None and same(r[v], g))
        print(f"seed {seed}: {n} of {len(gold)} calls match on {oracle}")
        continue
    flaky = {
        v
        for v, g in gold.items()
        if r.get(v) is None or not same(r[v], g) or slow.get(v, 0) > MAX_MS
    }
    for v in flaky:
        del gold[v]
    for m in list(payload):
        payload[m]["vectors"] = [x for x in payload[m]["vectors"] if x[0] not in flaky]
        payload[m]["units"] = {
            uid: payload[m]["units"][uid] for _, uid, _ in payload[m]["vectors"]
        }
        if not payload[m]["vectors"]:
            del payload[m]
    print(f"seed {seed}: {len(flaky)} dropped, {len(gold)} remain")
if REPORT_ONLY:
    sys.exit(0)
with open(os.path.join(vd, "inputs.pkl"), "wb") as stream:
    pickle.dump(payload, stream, protocol=4)
with open(os.path.join(vd, "gold.json"), "w") as stream:
    json.dump(gold, stream)
st = json.loads(Path(os.path.join(vd, "stats.json")).read_text())
st["vectors"] = len(gold)
st["units_covered"] = len({uid for p in payload.values() for _, uid, _ in p["vectors"]})
with open(os.path.join(vd, "stats.json"), "w") as stream:
    json.dump(st, stream, indent=1)
print(st)
