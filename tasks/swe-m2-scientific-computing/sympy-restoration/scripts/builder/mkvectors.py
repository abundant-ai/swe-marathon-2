"""Build the sealed reference-comparison vectors.

usage: mkvectors.py <work_dir> [--per-unit 8] [--cand 40] [--workers 10]
Needs in work_dir: rec/*.pkl (from rec_plugin), units.json, sealed.json, cand_oracle/ (the
original tree, as rebuilt by the transplant), skel2/ (skeleton).
Writes work_dir/vectors/{inputs.pkl, gold.json, stats.json}.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import pickle
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "task_src"))
from canon import same  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("work")
ap.add_argument("--per-unit", type=int, default=8)
ap.add_argument("--cand", type=int, default=40)
ap.add_argument("--workers", type=int, default=10)
ap.add_argument("--max-ms", type=float, default=1000.0)
args = ap.parse_args()
W = os.path.abspath(args.work)
RV = os.path.join(HERE, "task_src", "rvector.py")

units = {u["uid"]: u for u in json.load(open(os.path.join(W, "units.json")))}
# records carry the unit ids of the manifest that was current when they were taken
_rec_units = os.path.join(W, "units_at_rec.json")
_by_dotted = {u["dotted"]: u["uid"] for u in units.values()}
uid_map = None
if os.path.exists(_rec_units):
    uid_map = {u["uid"]: _by_dotted.get(u["dotted"]) for u in json.load(open(_rec_units))}
sealed = json.load(open(os.path.join(W, "sealed.json")))
held = set(sealed["held_out_functions"])


def func_key(nid):
    f, rest = nid.split("::", 1)
    return f + "::" + rest.split("[")[0]


# ---- 1. load records, tier them
recs = collections.defaultdict(list)
n_raw = 0
for p in sorted(glob.glob(os.path.join(W, "rec", "*.pkl"))):
    for uid, direct, nodeid, blob in pickle.load(open(p, "rb")):
        n_raw += 1
        if uid_map is not None:
            uid = uid_map.get(uid)
        if uid not in units:
            continue
        h = func_key(nodeid) in held
        # 1: called directly by a held-out test   2: called directly by a visible test
        # 3: called inside the library during a held-out test   4: same, visible test
        tier = (1 if h else 2) if direct else (3 if h else 4)
        recs[uid].append((tier, len(blob), blob))
# calls made by docstring examples (current unit ids): last resort, tier 5
n_dt = 0
for p in sorted(glob.glob(os.path.join(W, "rec_dt", "*.pkl"))):
    for uid, direct, nodeid, blob in pickle.load(open(p, "rb")):
        if uid in units:
            # 5: called directly by a docstring example   6: called inside the library while
            # the unit's own examples ran
            recs[uid].append((5 if direct else 6, len(blob), blob))
            n_dt += 1
print("raw records", n_raw, "+", n_dt, "from docstring examples | units with records", len(recs), "of", len(units))

cands = {}
for uid, lst in recs.items():
    seen = set()
    out = []
    for tier, size, blob in sorted(lst, key=lambda x: (x[0], x[1])):
        if blob in seen:
            continue
        seen.add(blob)
        out.append((tier, blob))
    # keep a tier-balanced slice
    # test-suite calls first; docstring-example calls fill what is left of the cap
    cands[uid] = out[: args.cand]


def unit_meta(u):
    return {k: u[k] for k in ("file", "qualname", "name") } | {"occ": u.get("occ", 0), "nocc": u.get("nocc", 1)}


def replay(tree, vecs_by_module, hashseed, tag):
    """vecs_by_module: {module: [(vid, uid, blob)]} -> {vid: (canon, ms)}"""
    scratch = tempfile.mkdtemp(prefix=f"vec-{tag}-")
    res = {}

    def one(item):
        k, (mod, vecs) = item
        ip = os.path.join(scratch, f"i{k}.pkl")
        op = os.path.join(scratch, f"o{k}.jsonl")
        with open(ip, "wb") as f:
            pickle.dump({"units": {uid: unit_meta(units[uid]) for _, uid, _ in vecs}, "vectors": vecs}, f, protocol=4)
        env = dict(os.environ, PYTHONHASHSEED=str(hashseed), PYTHONDONTWRITEBYTECODE="1")
        try:
            subprocess.run([sys.executable, "-B", RV, tree, mod, ip, op, "5"], env=env, timeout=5 * len(vecs) + 300,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=tree)
        except subprocess.TimeoutExpired:
            pass
        out = {}
        try:
            for line in open(op):
                r = json.loads(line)
                if "v" in r:   # the first line only says the module was imported
                    out[r["v"]] = r["c"]
        except OSError:
            pass
        return out

    with ThreadPoolExecutor(args.workers) as ex:
        for out in ex.map(one, list(enumerate(sorted(vecs_by_module.items())))):
            res.update(out)
    return res


# ---- 2. replay all candidates on the original tree under three hash seeds
allv = collections.defaultdict(list)
tier_of = {}
uid_of = {}
k = 0
for uid, lst in sorted(cands.items()):
    for tier, blob in lst:
        k += 1
        vid = f"C{k:06d}"
        tier_of[vid] = tier
        uid_of[vid] = uid
        allv[units[uid]["module"]].append((vid, uid, blob))
print("candidate vectors", k)

# units that use randomness are not replayable across runs and platforms
import ast as _ast  # noqa: E402

import restorelib as _rl  # noqa: E402

_RAND = ("rand", "shuffle", "seed", "choice", "sample")
_src_cache = {}


def uses_random(u):
    f = u["file"]
    if f not in _src_cache:
        _src_cache[f] = _rl.index_functions(_ast.parse(open(os.path.join(W, "pristine", f), encoding="utf-8").read()))
    nodes = _src_cache[f].get(u["qualname"]) or []
    if len(nodes) <= u.get("occ", 0):
        return True
    fn = nodes[u.get("occ", 0)]
    for n in _ast.walk(fn):
        ident = n.id if isinstance(n, _ast.Name) else n.attr if isinstance(n, _ast.Attribute) else n.arg if isinstance(n, _ast.arg) else None
        if ident and any(w in ident.lower() for w in _RAND):
            return True
    return False


random_units = {uid for uid, u in units.items() if uses_random(u)}
n_before = sum(len(v) for v in allv.values())
for mod in list(allv):
    allv[mod] = [v for v in allv[mod] if v[1] not in random_units]
    if not allv[mod]:
        del allv[mod]
print("units using randomness (their calls are dropped):", len(random_units), "| calls dropped:",
      n_before - sum(len(v) for v in allv.values()))
kept = {v[0] for vecs in allv.values() for v in vecs}
for v in list(tier_of):
    if v not in kept:
        del tier_of[v]
# replay on the tree the grader uses: no test directories
oracle = os.path.join(W, "cand_oracle_nt")
runs = [replay(oracle, allv, s, f"o{s}") for s in (0, 1, 2, 3)]
BAD = {"NotImplementedError", "Timeout", "Uncanonical", "Unresolved", "ImportFailure", "RecursionError", "MemoryError",
       "ModuleNotFoundError", "ImportError"}
good = {}
why = collections.Counter()
for vid in tier_of:
    c0 = runs[0].get(vid)
    if c0 is None:
        why["missing"] += 1
        continue
    if not all(json.dumps(r.get(vid), sort_keys=True) == json.dumps(c0, sort_keys=True) for r in runs[1:]):
        why["unstable"] += 1
        continue
    if c0 == ["TOOBIG"]:
        why["toobig"] += 1
        continue
    if c0 and c0[0] == "EXC":
        # a replayed call that raises says nothing reliable: objects can lose state when
        # their arguments are pickled, and any body that raises would match
        why["exc:" + (c0[1] if c0[1] in BAD else "other")] += 1
        continue
    if c0 == ["N"]:
        why["returns-none-no-effect"] += 1
        continue
    good[vid] = c0
print("stable goldens", len(good), "| dropped", dict(why))

# ---- 3. the skeleton must not reproduce a golden
skel = os.path.join(W, "skel2")
sub = collections.defaultdict(list)
for mod, vecs in allv.items():
    for v in vecs:
        if v[0] in good:
            sub[mod].append(v)
sk = replay(skel, sub, 0, "sk")
nd = [vid for vid in good if sk.get(vid) is not None and same(sk[vid], good[vid])]
for vid in nd:
    del good[vid]
print("non-discriminating on the skeleton (dropped)", len(nd), "| remaining", len(good))

# ---- 4. select per unit: tiers first, distinct goldens first
by_unit = collections.defaultdict(list)
for vid, c in good.items():
    by_unit[uid_of[vid]].append(vid)
final = []
tier_hist = collections.Counter()
for uid, vids in sorted(by_unit.items()):
    vids.sort(key=lambda v: (tier_of[v], v))
    # direct calls first (held-out tests before visible ones); calls made inside the
    # library are used only for units that tests never call directly
    direct = [v for v in vids if tier_of[v] <= 2]
    inner = [v for v in vids if tier_of[v] in (3, 4)]
    dt_direct = [v for v in vids if tier_of[v] == 5]
    pool = direct or inner or dt_direct or vids   # docstring-example calls only as a last resort
    picked, seen_gold = [], set()
    for v in pool:
        g = json.dumps(good[v], sort_keys=True)
        if g in seen_gold:
            continue
        seen_gold.add(g)
        picked.append(v)
        if len(picked) >= args.per_unit:
            break
    for v in pool:
        if len(picked) >= args.per_unit:
            break
        if v not in picked:
            picked.append(v)
    for v in picked:
        tier_hist[tier_of[v]] += 1
    final += picked
blob_of = {v[0]: v[2] for vecs in allv.values() for v in vecs}
inputs = collections.defaultdict(list)
gold = {}
for i, cv in enumerate(sorted(final), 1):
    vid = f"V{i:05d}"
    uid = uid_of[cv]
    inputs[units[uid]["module"]].append((vid, uid, blob_of[cv]))
    gold[vid] = good[cv]
out_dir = os.path.join(W, "vectors")
os.makedirs(out_dir, exist_ok=True)
payload = {
    mod: {"units": {uid: unit_meta(units[uid]) for _, uid, _ in vecs}, "vectors": vecs}
    for mod, vecs in inputs.items()
}
pickle.dump(payload, open(os.path.join(out_dir, "inputs.pkl"), "wb"), protocol=4)
json.dump(gold, open(os.path.join(out_dir, "gold.json"), "w"))
covered = {uid_of[cv] for cv in final}
t12 = {uid_of[cv] for cv in final if tier_of[cv] in (1, 3)}
stats = {
    "vectors": len(gold), "units_covered": len(covered), "units_total": len(units),
    "units_covered_by_held_out_calls": len(t12), "tier_hist": dict(tier_hist),
    "exception_goldens": sum(1 for c in gold.values() if c and c[0] == "EXC"),
}
json.dump(stats, open(os.path.join(out_dir, "stats.json"), "w"), indent=1)
print(stats)

# ---- 5. self-check with the final grouping: drop anything the original tree does not
#         reproduce under two further hash seeds, then report
for seed in (4, 5):
    chk = replay(oracle, {m: p["vectors"] for m, p in payload.items()}, seed, f"chk{seed}")
    flaky = [v for v, g in gold.items() if chk.get(v) is None or not same(chk[v], g)]
    if flaky:
        fl = set(flaky)
        for v in flaky:
            del gold[v]
        for m in list(payload):
            payload[m]["vectors"] = [x for x in payload[m]["vectors"] if x[0] not in fl]
            payload[m]["units"] = {uid: payload[m]["units"][uid] for _, uid, _ in payload[m]["vectors"]}
            if not payload[m]["vectors"]:
                del payload[m]
        print(f"seed {seed}: dropped {len(flaky)} calls the original tree did not reproduce")
pickle.dump(payload, open(os.path.join(out_dir, "inputs.pkl"), "wb"), protocol=4)
json.dump(gold, open(os.path.join(out_dir, "gold.json"), "w"))
stats["vectors"] = len(gold)
stats["units_covered"] = len({uid for p in payload.values() for _, uid, _ in p["vectors"]})
json.dump(stats, open(os.path.join(out_dir, "stats.json"), "w"), indent=1)
stats["units_total"] = len(units)
json.dump(stats, open(os.path.join(out_dir, "stats.json"), "w"), indent=1)
chk = replay(oracle, {m: p["vectors"] for m, p in payload.items()}, 6, "final")
ok = sum(1 for v, g in gold.items() if chk.get(v) is not None and same(chk[v], g))
sk2 = replay(skel, {m: p["vectors"] for m, p in payload.items()}, 6, "sk2")
bad = sum(1 for v, g in gold.items() if sk2.get(v) is not None and same(sk2[v], g))
print(f"self-check: original tree {ok}/{len(gold)} | skeleton {bad}/{len(gold)} | {stats}")
