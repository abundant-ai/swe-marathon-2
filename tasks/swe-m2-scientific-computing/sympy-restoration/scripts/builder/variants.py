"""New inputs for units whose recorded calls all repeat a docstring example or a visible test.

Build time only.

usage:
  variants.py make <original_tree> <inputs.pkl> <uids.json> <out.pkl> [--per-call 6]
      Mutated copies of the units' recorded arguments: integers shifted, symbols renamed (their
      assumptions kept), one leaf at a time or all at once. Runs inside the original tree.
  variants.py screen <original_nt> <skeleton_nt> <cands.pkl> <out_dir> [--seeds 0,1,2] [--workers 4]
      Replays candidates [(cid, uid, blob, source)] on the original under every seed and on the
      skeleton, with the verifier's own runner; keeps those regold.py would keep. Writes
      screened.pkl ([(cid, uid, blob, source, result)]) and screen_report.json.
  variants.py select <inputs.pkl> <gold.json> <screened.pkl> <out_dir> --documented <a.json>[,<b.json>]
            [--per-unit 4]
      Adds, per unit, up to --per-unit screened candidates that no docstring example or visible
      test repeats (withheld-test calls first, distinct results first) to the recorded calls.
      The documented.py outputs given mark which recorded calls and candidates such a run repeats.
      A call is documented when such a run repeats its arguments, or when its result is the
      result of one of its unit's documented calls (a table of documented outputs can return it).
      Writes inputs.pkl, gold.json, documented.json (the documented calls kept) and
      select_report.json.
"""
from __future__ import annotations

import collections
import json
import os
import pickle
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PRIORITY = {"withheld-direct": 0, "withheld-inner": 1, "variant": 2}


def _arg(flag, default):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


# ---- make -----------------------------------------------------------------------------------

def mutations(value, depth=0):
    """Yield mutated copies of `value`, each differing in one place or uniformly."""
    import sympy  # noqa: PLC0415
    from sympy.core.basic import Basic  # noqa: PLC0415
    from sympy.matrices.matrixbase import MatrixBase  # noqa: PLC0415

    if depth > 4:
        return
    t = type(value)
    if t is int:
        yield value + 1
        yield value - 1
        yield value + 2
        return
    if t in (list, tuple):
        for i, item in enumerate(value):
            for m in mutations(item, depth + 1):
                out = list(value)
                out[i] = m
                yield t(out)
                break
        return
    if isinstance(value, MatrixBase):
        if value.rows and value.cols:
            try:
                m = value.as_mutable()
                m[0, 0] = m[0, 0] + 1
                yield m if type(m) is type(value) else type(value)(m)
            except Exception:  # noqa: BLE001
                pass
        return
    if isinstance(value, Basic):
        if isinstance(value, sympy.Integer):
            yield sympy.Integer(int(value) + 1)
            yield sympy.Integer(int(value) - 1)
            return
        if isinstance(value, sympy.Rational):
            yield sympy.Rational(int(value.p) + 1, int(value.q))
            return
        try:
            ints = sorted((a for a in value.atoms(sympy.Integer)), key=lambda a: int(a))
        except Exception:  # noqa: BLE001
            ints = []
        for a in ints[:3]:
            try:
                yield value.xreplace({a: sympy.Integer(int(a) + 1)})
            except Exception:  # noqa: BLE001
                pass
        try:
            syms = sorted((s for s in value.free_symbols if type(s) is sympy.Symbol), key=lambda s: s.name)
        except Exception:  # noqa: BLE001
            syms = []
        if syms:
            try:
                yield value.xreplace({s: sympy.Symbol(s.name + "_r", **s._assumptions_orig) for s in syms})
            except Exception:  # noqa: BLE001
                pass
        return
    mod = t.__module__ or ""
    if mod.startswith(("sympy.external.pythonmpq", "sympy.polys.domains")) and hasattr(value, "numerator") \
            and hasattr(value, "denominator"):
        try:
            yield t(int(value.numerator) + 1, int(value.denominator))
        except Exception:  # noqa: BLE001
            pass


def make():
    tree, inputs, uids_path, out = (os.path.abspath(p) for p in sys.argv[2:6])
    per_call = int(_arg("--per-call", "6"))
    sys.path[:0] = [tree]
    os.chdir(tree)
    import sympy  # noqa: F401, PLC0415

    want = set(json.load(open(uids_path, encoding="utf-8")))
    payload = pickle.load(open(inputs, "rb"))
    existing = collections.defaultdict(set)
    calls = []
    for p in payload.values():
        for vid, uid, blob in p["vectors"]:
            existing[uid].add(blob)
            if uid in want:
                calls.append((vid, uid, blob))
    cands, k = [], 0
    for vid, uid, blob in calls:
        try:
            args = pickle.loads(blob)
        except Exception:  # noqa: BLE001
            continue
        made = 0
        for name in list(args):
            if made >= per_call:
                break
            for m in mutations(args[name]):
                new = dict(args, **{name: m})
                try:
                    b = pickle.dumps(new, protocol=4)
                except Exception:  # noqa: BLE001
                    continue
                if b in existing[uid] or len(b) > 30000:
                    continue
                existing[uid].add(b)
                k += 1
                cands.append((f"M{k:06d}", uid, b, "variant"))
                made += 1
                if made >= per_call:
                    break
    with open(out, "wb") as f:
        pickle.dump(cands, f, protocol=4)
    print(json.dumps({"calls_mutated": len(calls), "candidates": len(cands),
                      "units": len({c[1] for c in cands}), "units_wanted": len(want)}))


# ---- screen ---------------------------------------------------------------------------------

def screen():
    original, skeleton, cands_path, out_dir = (os.path.abspath(p) for p in sys.argv[2:6])
    seeds = [int(s) for s in _arg("--seeds", "0,1,2").split(",")]
    workers = int(_arg("--workers", "4"))
    sys.path.insert(0, HERE)
    import regold  # noqa: PLC0415

    sys.path.insert(0, regold.LIB)
    from canon import same  # noqa: PLC0415

    units = {u["uid"]: u for u in json.load(open(os.path.join(HERE, "..", "..", "environment", "data", "units.json")))}
    cands = pickle.load(open(cands_path, "rb"))
    payload = collections.defaultdict(lambda: {"units": {}, "vectors": []})
    for cid, uid, blob, _src in cands:
        u = units[uid]
        p = payload[u["module"]]
        p["units"][uid] = {"file": u["file"], "qualname": u["qualname"], "name": u["qualname"].rsplit(".", 1)[-1],
                           "occ": u.get("occ", 0), "nocc": u.get("nocc", 1)}
        p["vectors"].append((cid, uid, blob))
    payload = dict(payload)
    runs = [regold.replay(original, payload, s, workers, 10.0) for s in seeds]
    why, kept = collections.Counter(), []
    for cid, uid, blob, src in cands:
        first = runs[0].get(cid)
        if first is None or any(r.get(cid) is None for r in runs[1:]):
            why["missing"] += 1
            continue
        c0 = first[0]
        if c0 == ["TOOBIG"] or (c0 and c0[0] == "EXC") or c0 == ["N"]:
            why["exc" if c0 and c0[0] == "EXC" else "toobig-or-none"] += 1
            continue
        if not all(same(r[cid][0], c0) for r in runs[1:]):
            why["unstable"] += 1
            continue
        if max(r[cid][1] for r in runs) > 5000:
            why["slow"] += 1
            continue
        kept.append((cid, uid, blob, src, c0))
    sub = collections.defaultdict(lambda: {"units": {}, "vectors": []})
    for cid, uid, blob, src, c0 in kept:
        mod = units[uid]["module"]
        sub[mod]["units"][uid] = payload[mod]["units"][uid]
        sub[mod]["vectors"].append((cid, uid, blob))
    sk = regold.replay(skeleton, dict(sub), seeds[0], workers, 10.0)
    on_skeleton = {cid for cid, uid, blob, src, c0 in kept if cid in sk and same(sk[cid][0], c0)}
    kept = [k for k in kept if k[0] not in on_skeleton]
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "screened.pkl"), "wb") as f:
        pickle.dump(kept, f, protocol=4)
    report = {"candidates": len(cands), "kept": len(kept), "dropped": dict(why), "matched_on_skeleton": len(on_skeleton),
              "units_with_kept": len({k[1] for k in kept}),
              "kept_by_source": dict(collections.Counter(k[3] for k in kept))}
    with open(os.path.join(out_dir, "screen_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    print(json.dumps(report))


# ---- select ---------------------------------------------------------------------------------

def select():
    inputs, gold_path, screened_path, out_dir = (os.path.abspath(p) for p in sys.argv[2:6])
    per_unit = int(_arg("--per-unit", "4"))
    payload = pickle.load(open(inputs, "rb"))
    gold = json.load(open(gold_path, encoding="utf-8"))
    screened = pickle.load(open(screened_path, "rb"))
    documented = set()
    for path in _arg("--documented", "").split(","):
        documented.update(json.load(open(path, encoding="utf-8"))["documented"])
    units = {u["uid"]: u for u in json.load(open(os.path.join(HERE, "..", "..", "environment", "data", "units.json")))}
    sys.path.insert(0, os.path.join(HERE, "..", "..", "steps", "01-restore-bodies", "tests", "verifier", "lib"))
    from canon import same  # noqa: PLC0415

    # results a table of documented outputs could return, per unit
    shown = collections.defaultdict(list)
    for p in payload.values():
        for vid, uid, _blob in p["vectors"]:
            if vid in documented and vid in gold:
                shown[uid].append(gold[vid])

    def result_shown(uid, result):
        return any(same(result, r) for r in shown[uid])

    for p in payload.values():
        for vid, uid, _blob in p["vectors"]:
            if vid in gold and vid not in documented and result_shown(uid, gold[vid]):
                documented.add(vid)
    by_unit = collections.defaultdict(list)
    for cid, uid, blob, src, c0 in screened:
        if cid not in documented and not result_shown(uid, c0):
            by_unit[uid].append((PRIORITY[src], cid, blob, src, c0))
    last = max(int(v[1:]) for v in gold)
    added, sources = [], collections.Counter()
    for uid in sorted(by_unit):
        picked, seen = [], set()
        rows = sorted(by_unit[uid])
        for row in rows:
            g = json.dumps(row[4], sort_keys=True)
            if g not in seen:
                seen.add(g)
                picked.append(row)
            if len(picked) >= per_unit:
                break
        for row in rows:
            if len(picked) >= per_unit:
                break
            if row not in picked:
                picked.append(row)
        for _prio, _cid, blob, src, c0 in picked:
            last += 1
            vid = f"V{last:05d}"
            added.append((vid, uid, blob, c0))
            sources[src] += 1
    for vid, uid, blob, c0 in added:
        u = units[uid]
        p = payload.setdefault(u["module"], {"units": {}, "vectors": []})
        p["units"][uid] = {"file": u["file"], "qualname": u["qualname"], "name": u["qualname"].rsplit(".", 1)[-1],
                           "occ": u.get("occ", 0), "nocc": u.get("nocc", 1)}
        p["vectors"].append((vid, uid, blob))
        gold[vid] = c0
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "inputs.pkl"), "wb") as f:
        pickle.dump(payload, f, protocol=4)
    with open(os.path.join(out_dir, "gold.json"), "w", encoding="utf-8") as f:
        json.dump(gold, f)
    kept_documented = sorted(v for v in gold if v in documented)
    with open(os.path.join(out_dir, "documented.json"), "w", encoding="utf-8") as f:
        json.dump({"calls": kept_documented}, f)
    deciding = collections.Counter(uid for p in payload.values() for vid, uid, _ in p["vectors"] if vid not in documented)
    report = {"added": len(added), "units_given_calls": len({a[1] for a in added}), "by_source": dict(sources),
              "calls": len(gold), "documented": len(kept_documented), "deciding": len(gold) - len(kept_documented),
              "units_with_deciding": len(deciding), "units_without_deciding": len(units) - len(deciding),
              "added_ids": [a[0] for a in added]}
    with open(os.path.join(out_dir, "select_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    print(json.dumps({k: v for k, v in report.items() if k != "added_ids"}))


if __name__ == "__main__":
    {"make": make, "screen": screen, "select": select}[sys.argv[1]]()
