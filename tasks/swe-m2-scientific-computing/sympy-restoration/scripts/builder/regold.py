"""Record the reference result of every recorded call again, with the verifier's own runner and
comparison, and check that the original tree reproduces them and the blank skeleton none.

Build time only. Both trees are copies without test directories, as the verifier replays.

usage:
  regold.py <original_tree> <skeleton_tree> <inputs.pkl> <out_dir> [--seeds 0,1,2] [--workers 4]
            [--timeout 10] [--max-ms 5000]

Writes into <out_dir>: gold.json (the results of the first seed), inputs.pkl (the calls kept) and
regold_report.json. A call is dropped when the original tree does not give one result under every
seed, raises, cannot be put in canonical form, takes longer than --max-ms, or leaves its arguments
unchanged while returning None (an empty body would match that). The skeleton must match none.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import pickle
import secrets
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "..", "steps", "01-restore-bodies", "tests", "verifier", "lib")
RVECTOR = os.path.join(LIB, "rvector.py")
sys.path.insert(0, LIB)
import gradelib  # noqa: E402


def replay(tree, payload, seed, workers, timeout):
    """Replay every call of `payload` on `tree`; {call id: (canonical result, ms)}."""
    scratch = tempfile.mkdtemp(prefix=f"regold-{seed}-")
    jobs = sorted(payload.items())

    def one(item):
        k, (mod, p) = item
        ip, op = os.path.join(scratch, f"i{k}.pkl"), os.path.join(scratch, f"o{k}.jsonl")
        with open(ip, "wb") as f:
            pickle.dump(p, f, protocol=4)
        env = dict(os.environ, PYTHONHASHSEED=str(seed), PYTHONDONTWRITEBYTECODE="1")
        key = secrets.token_hex(16)
        try:
            subprocess.run([sys.executable, "-P", "-s", "-B", RVECTOR, tree, mod, ip, op, str(timeout)], env=env, cwd=tree,
                           input=(key + "\n").encode("ascii"), timeout=timeout * len(p["vectors"]) + 300,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            pass
        out = {}
        try:
            with open(op, encoding="utf-8") as f:
                for line in f:
                    text = gradelib.signed_text(line, key)   # the runner signs every line with the key it was given
                    if text is None:
                        continue
                    try:
                        rec = json.loads(text)
                    except ValueError:
                        continue
                    if "v" in rec:
                        out[rec["v"]] = (rec["c"], rec.get("ms", 0))
        except OSError:
            pass
        return out

    res = {}
    with ThreadPoolExecutor(workers) as ex:
        for out in ex.map(one, list(enumerate(jobs))):
            res.update(out)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("original")
    ap.add_argument("skeleton")
    ap.add_argument("inputs")
    ap.add_argument("out")
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--max-ms", type=float, default=5000.0)
    args = ap.parse_args()
    sys.path.insert(0, LIB)
    from canon import profile_of, same  # noqa: PLC0415

    with open(args.inputs, "rb") as f:
        payload = pickle.load(f)
    calls = {vid: (mod, uid) for mod, p in payload.items() for vid, uid, _ in p["vectors"]}
    profile = {vid: profile_of(f"{payload[mod]['units'][uid]['file']}::{payload[mod]['units'][uid]['qualname']}")
               for vid, (mod, uid) in calls.items()}
    seeds = [int(s) for s in args.seeds.split(",")]
    started = time.time()
    runs = []
    for seed in seeds:
        t0 = time.time()
        runs.append(replay(os.path.abspath(args.original), payload, seed, args.workers, args.timeout))
        print(f"seed {seed}: {len(runs[-1])} results in {time.time() - t0:.0f}s", flush=True)
    gold, why = {}, collections.Counter()
    dropped = {}
    for vid in sorted(calls):
        first = runs[0].get(vid)
        reason = None
        if first is None or any(r.get(vid) is None for r in runs[1:]):
            reason = "missing"
        else:
            c0 = first[0]
            if c0 == ["TOOBIG"]:
                reason = "toobig"
            elif c0 and c0[0] == "EXC":
                reason = "exc:" + str(c0[1])
            elif c0 == ["N"]:
                reason = "returns-none-no-effect"
            elif not all(same(r[vid][0], c0, profile=profile[vid]) for r in runs[1:]):
                reason = "unstable"
            elif max(r[vid][1] for r in runs) > args.max_ms:
                reason = "slow"
        if reason:
            why[reason] += 1
            dropped[vid] = {"reason": reason, "unit": calls[vid][1], "result": (first or [None])[0]}
        else:
            gold[vid] = first[0]
    kept = {}
    for mod, p in payload.items():
        vecs = [v for v in p["vectors"] if v[0] in gold]
        if vecs:
            kept[mod] = {"units": {uid: p["units"][uid] for _, uid, _ in vecs}, "vectors": vecs}
    t0 = time.time()
    sk = replay(os.path.abspath(args.skeleton), kept, seeds[0], args.workers, args.timeout)
    skeleton_matches = sorted(vid for vid, g in gold.items() if vid in sk and same(sk[vid][0], g, profile=profile[vid]))
    print(f"skeleton: {len(sk)} results, {len(skeleton_matches)} match, in {time.time() - t0:.0f}s", flush=True)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "gold.json"), "w", encoding="utf-8") as f:
        json.dump(gold, f)
    with open(os.path.join(args.out, "inputs.pkl"), "wb") as f:
        pickle.dump(kept, f, protocol=4)
    units_before = {uid for _, uid in calls.values()}
    units_after = {uid for p in kept.values() for _, uid, _ in p["vectors"]}
    # results that are the same text in every run, not only alike under the comparison (a Dummy the
    # call made is numbered from a counter each process seeds at random)
    identical = sum(1 for vid in gold if all(json.dumps(r[vid][0]) == json.dumps(runs[0][vid][0]) for r in runs[1:]))
    report = {
        "calls_before": len(calls), "calls_kept": len(gold), "dropped": dict(why), "dropped_calls": dropped,
        "identical_text_in_every_run": identical,
        "results_with_changed_arguments": {"RS": sum(1 for g in gold.values() if g[:1] == ["RS"]),
                                           "NS": sum(1 for g in gold.values() if g[:1] == ["NS"])},
        "units_before": len(units_before), "units_after": len(units_after),
        "units_lost": sorted(units_before - units_after), "skeleton_matches": skeleton_matches,
        "slowest_ms": max((max(r[v][1] for r in runs) for v in gold), default=0), "seeds": seeds,
        "seconds": round(time.time() - started, 1),
    }
    with open(os.path.join(args.out, "regold_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    print(json.dumps({k: v for k, v in report.items() if k not in ("dropped_calls",)}))


if __name__ == "__main__":
    main()
