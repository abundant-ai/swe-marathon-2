"""New inputs for units whose recorded calls all repeat a docstring example or a visible test.

Build time only.

usage:
  variants.py make <original_tree> <inputs.pkl> <uids.json> <out.pkl> [--per-call 6]
      Mutated copies of the units' recorded arguments, inside the original tree: every symbol of
      the call renamed by one map applied to all its arguments (assumptions kept), or one integer
      shifted. An integer parameter whose docstring states a domain (prime, odd, positive, a
      level...) is never shifted, nor is the level `u` of a polynomial routine; a shifted top-level
      integer outside the range the unit's recorded calls use is dropped unless the docstring
      describes the parameter as a plain integer. Writes [(cid, uid, blob, "variant")] and a report.
  variants.py contract <original_tree> <cands.pkl> <out.pkl>
      Drops candidates that break a prime contract their unit's docstring states (a parameter
      documented as prime or odd prime given anything else).
  variants.py screen <original_nt> <skeleton_nt> <cands.pkl> <out_dir> [--seeds 0,1,2] [--workers 4]
      Replays candidates [(cid, uid, blob, source)] on the original under every seed and on the
      skeleton, with the verifier's own runner; keeps those regold.py would keep. Writes
      screened.pkl ([(cid, uid, blob, source, result)]) and screen_report.json.
  variants.py select <inputs.pkl> <gold.json> <screened.pkl> <out_dir> --documented <a.json>[,<b.json>]
            [--echoes <c.json>[,<d.json>]] [--per-unit 4] [--drop <ids.json>]
      Adds, per unit, up to --per-unit screened candidates that are not documented (withheld-test
      calls first, distinct results first) to the recorded calls. A call is documented when a
      docstring example or a visible test makes it (the documented.py outputs given, by arguments
      or by arguments up to a renaming of symbols), when its result is the result of one of its
      unit's such calls (a table of documented outputs can return it), or when its result is one
      of its own arguments unchanged (the echoes.py outputs given). --drop names recorded calls to
      leave out. Writes inputs.pkl, gold.json, documented.json and select_report.json.
"""

from __future__ import annotations

import collections
import json
import os
import pickle
import re
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PRIORITY = {"withheld-direct": 0, "withheld-inner": 1, "variant": 2}
UNITS = os.path.join(HERE, "..", "..", "environment", "data", "units.json")
DOMAIN = re.compile(
    r"\b(prime|odd|even|positive|nonnegative|non-negative|negative|natural|nonzero|non-zero|squarefree|"
    r"square-free|greater than|less than|at least|at most|larger than|smaller than|level|power of)\b"
    r"|[<>]=?\s*-?\d",
    re.IGNORECASE,
)
PLAIN_INT = re.compile(
    r"^\s*(int|integer|Integer|int or Integer|integer or Integer)\s*\.?\s*$"
)
LEVELS = frozenset({"u", "v", "lev", "level"})


def _arg(flag, default):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


def prose(doc: str) -> list[str]:
    """The lines of a docstring outside its examples (a `>>>` line and the output under it)."""
    out, example = [], False
    for line in (doc or "").splitlines():
        text = line.strip()
        if text.startswith((">>>", "...")):
            example = True
        elif not text:
            example = False
        if not example:
            out.append(line)
    return out


def param_docs(doc: str, name: str) -> list[str]:
    """What a docstring's prose says about parameter `name`: its numpydoc entry ("name : ...",
    with the indented lines under it) and every sentence that names it."""
    found, lines = [], prose(doc)
    for i, line in enumerate(lines):
        m = re.match(rf"^(\s*){re.escape(name)}\s*:\s*(.*)$", line)
        if m:
            text, indent = [m.group(2)], len(m.group(1))
            for nxt in lines[i + 1 :]:
                if nxt.strip() and len(nxt) - len(nxt.lstrip()) > indent:
                    text.append(nxt.strip())
                else:
                    break
            found.append(" ".join(text))
    for sentence in re.split(
        r"(?<=[.;:])\s+", " ".join(line.strip() for line in lines)
    ):
        if re.search(rf"(?<![\w.]){re.escape(name)}(?![\w(])", sentence):
            found.append(sentence)
    return found


def stated_domain(doc: str, name: str, unit_file: str) -> bool:
    """The docstring restricts integer parameter `name`, or it is a polynomial routine's level."""
    if name in LEVELS and unit_file.startswith("sympy/polys/"):
        return True
    return any(DOMAIN.search(text) for text in param_docs(doc, name))


def prime_contract(doc: str, name: str) -> str | None:
    """ "odd prime" or "prime" when the docstring's prose says parameter `name` is one: its own
    entry ("p : odd prime"), or a phrase such as "p must be a prime" or "an odd prime p"."""
    entry = ""
    for line in prose(doc):
        m = re.match(rf"^\s*{re.escape(name)}\s*:\s*(.*)$", line)
        if m:
            entry += " " + m.group(1)
    text = " ".join(line.strip() for line in prose(doc))
    n = re.escape(name)
    phrase = re.search(
        rf"(?<![\w.]){n}\s+(?:must be|is|should be|has to be)\s+(?:an?\s+)?(odd\s+)?prime\b"
        rf"|\b(odd\s+)?prime\s+(?:number\s+)?{n}(?![\w(])",
        text,
        re.IGNORECASE,
    )
    if re.search(r"\bprime\b", entry, re.IGNORECASE):
        return (
            "odd prime"
            if re.search(r"\bodd\s+prime\b", entry, re.IGNORECASE)
            else "prime"
        )
    if phrase:
        return "odd prime" if (phrase.group(1) or phrase.group(2)) else "prime"
    return None


def plain_integer(doc: str, name: str) -> bool:
    """The docstring's own entry for `name` says only that it is an integer."""
    lines = (doc or "").splitlines()
    return any(
        re.match(rf"^\s*{re.escape(name)}\s*:\s*(.*)$", line)
        and PLAIN_INT.match(
            re.match(rf"^\s*{re.escape(name)}\s*:\s*(.*)$", line).group(1)
        )
        for line in lines
    )


def unit_docs(tree, units):
    """{uid: docstring} from the original source."""
    import ast

    sys.path.insert(0, os.path.join(HERE, "..", "..", "common"))
    import restorelib

    parsed, out = {}, {}
    for u in units:
        path = os.path.join(tree, u["file"])
        if path not in parsed:
            parsed[path] = restorelib.index_functions(
                ast.parse(Path(path).read_text(encoding="utf-8"))
            )
        nodes = parsed[path].get(u["qualname"]) or []
        if len(nodes) == u.get("nocc", 1):
            out[u["uid"]] = ast.get_docstring(nodes[u.get("occ", 0)]) or ""
    return out


# ---- make -----------------------------------------------------------------------------------


def shifts(value, depth=0):
    """Copies of `value` with one integer shifted."""
    import sympy
    from sympy.core.basic import Basic
    from sympy.matrices.matrixbase import MatrixBase

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
            for m in shifts(item, depth + 1):
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
            except Exception:  # noqa: BLE001, S110
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
            except Exception:  # noqa: BLE001, S110
                pass
        return
    mod = t.__module__ or ""
    if (
        mod.startswith(("sympy.external.pythonmpq", "sympy.polys.domains"))
        and hasattr(value, "numerator")
        and hasattr(value, "denominator")
    ):
        try:
            yield t(int(value.numerator) + 1, int(value.denominator))
        except Exception:  # noqa: BLE001, S110
            pass


def symbols_of(value, depth=0):
    """The Symbols in `value`; None when it holds an object a renaming could not reach."""
    import fractions

    import sympy
    from sympy.core.basic import Basic
    from sympy.matrices.matrixbase import MatrixBase

    if depth > 6:
        return None
    if value is None or isinstance(
        value, (bool, int, float, complex, str, bytes, fractions.Fraction)
    ):
        return set()
    mod = type(value).__module__ or ""
    if (
        mod.startswith(("sympy.external.pythonmpq", "sympy.polys.domains"))
        and hasattr(value, "numerator")
        and not hasattr(value, "ex")
    ):
        return set()
    if isinstance(value, (Basic, MatrixBase)):
        try:
            return {s for s in value.free_symbols if type(s) is sympy.Symbol}
        except Exception:  # noqa: BLE001
            return None
    if isinstance(value, (list, tuple, set, frozenset)):
        found = set()
        for item in value:
            inner = symbols_of(item, depth + 1)
            if inner is None:
                return None
            found |= inner
        return found
    if isinstance(value, dict):
        return symbols_of(list(value.keys()) + list(value.values()), depth + 1)
    return None


def renamed(value, mapping):
    from sympy.core.basic import Basic
    from sympy.matrices.matrixbase import MatrixBase

    if isinstance(value, (Basic, MatrixBase)):
        return value.xreplace(mapping)
    if isinstance(value, (list, tuple, set, frozenset)):
        return type(value)(renamed(item, mapping) for item in value)
    if isinstance(value, dict):
        return type(value)(
            (renamed(k, mapping), renamed(v, mapping)) for k, v in value.items()
        )
    return value


def rename_all(args):
    """Every Symbol of the call renamed by one map applied to all its arguments, or None."""
    import sympy

    found = set()
    for value in args.values():
        inner = symbols_of(value)
        if inner is None:
            return None
        found |= inner
    if not found:
        return None
    mapping = {s: sympy.Symbol(s.name + "_r", **s._assumptions_orig) for s in found}
    try:
        return {name: renamed(value, mapping) for name, value in args.items()}
    except Exception:  # noqa: BLE001
        return None


def make():
    tree, inputs, uids_path, out = (os.path.abspath(p) for p in sys.argv[2:6])
    per_call = int(_arg("--per-call", "6"))
    sys.path[:0] = [tree]
    os.chdir(tree)
    import sympy

    want = set(json.loads(Path(uids_path).read_text(encoding="utf-8")))
    units = {u["uid"]: u for u in json.loads(Path(UNITS).read_text(encoding="utf-8"))}
    docs = unit_docs(tree, [units[uid] for uid in want])
    with open(inputs, "rb") as stream:
        payload = pickle.load(stream)
    existing = collections.defaultdict(set)
    calls = []
    for p in payload.values():
        for vid, uid, blob in p["vectors"]:
            existing[uid].add(blob)
            if uid in want:
                calls.append((vid, uid, blob))
    # the range of every top-level integer argument over the unit's recorded calls
    ranges = collections.defaultdict(lambda: collections.defaultdict(list))
    decoded = []
    for vid, uid, blob in calls:
        try:
            args = pickle.loads(blob)
        except Exception:  # noqa: BLE001, S112
            continue
        decoded.append((vid, uid, args))
        for name, value in args.items():
            if type(value) is int or isinstance(value, sympy.Integer):
                ranges[uid][name].append(int(value))
    cands, k = [], 0
    why = collections.Counter()

    def add(uid, new):
        nonlocal k
        try:
            b = pickle.dumps(new, protocol=4)
        except Exception:  # noqa: BLE001
            return False
        if b in existing[uid] or len(b) > 30000:
            return False
        existing[uid].add(b)
        k += 1
        cands.append((f"M{k:06d}", uid, b, "variant"))
        return True

    for vid, uid, args in decoded:
        u, doc = units[uid], docs.get(uid, "")
        made = 0
        both = rename_all(args)
        if both is not None and add(uid, both):
            made += 1
            why["renamed"] += 1
        for name in list(args):
            if made >= per_call:
                break
            if stated_domain(doc, name, u["file"]):
                why["domain stated: not shifted"] += 1
                continue
            value = args[name]
            scalar = type(value) is int or isinstance(value, sympy.Integer)
            for m in shifts(value):
                if scalar and ranges[uid][name]:
                    lo, hi = min(ranges[uid][name]), max(ranges[uid][name])
                    if not lo <= int(m) <= hi and not plain_integer(doc, name):
                        why["outside the recorded range: dropped"] += 1
                        continue
                if add(uid, dict(args, **{name: m})):
                    made += 1
                    why["shifted"] += 1
                if made >= per_call:
                    break
    with open(out, "wb") as f:
        pickle.dump(cands, f, protocol=4)
    print(
        json.dumps(
            {
                "calls_mutated": len(decoded),
                "candidates": len(cands),
                "units": len({c[1] for c in cands}),
                "units_wanted": len(want),
                "why": dict(why),
            }
        )
    )


# ---- contract -------------------------------------------------------------------------------


def contract():
    tree, cands_path, out = (os.path.abspath(p) for p in sys.argv[2:5])
    sys.path[:0] = [tree]
    os.chdir(tree)
    from sympy import isprime

    with open(cands_path, "rb") as stream:
        cands = pickle.load(stream)
    units = {u["uid"]: u for u in json.loads(Path(UNITS).read_text(encoding="utf-8"))}
    docs = unit_docs(tree, [units[uid] for uid in {c[1] for c in cands}])
    kept, dropped = [], collections.Counter()
    for cand in cands:
        uid, blob = cand[1], cand[2]
        doc = docs.get(uid, "")
        try:
            args = pickle.loads(blob)
        except Exception:  # noqa: BLE001
            kept.append(cand)
            continue
        broken = False
        for name, value in args.items():
            kind = prime_contract(doc, name)
            if kind is None or not (
                type(value) is int or getattr(value, "is_Integer", False)
            ):
                continue
            n = int(value)
            if not isprime(n) or (kind == "odd prime" and n == 2):
                broken = True
                break
        if broken:
            dropped[units[uid]["qualname"]] += 1
        else:
            kept.append(cand)
    with open(out, "wb") as f:
        pickle.dump(kept, f, protocol=4)
    print(
        json.dumps(
            {
                "candidates": len(cands),
                "kept": len(kept),
                "dropped_by_unit": dict(dropped),
            }
        )
    )


# ---- screen ---------------------------------------------------------------------------------


def screen():
    original, skeleton, cands_path, out_dir = (
        os.path.abspath(p) for p in sys.argv[2:6]
    )
    seeds = [int(s) for s in _arg("--seeds", "0,1,2").split(",")]
    workers = int(_arg("--workers", "4"))
    sys.path.insert(0, HERE)
    import regold

    sys.path.insert(0, regold.LIB)
    from canon import profile_of, same

    units = {u["uid"]: u for u in json.loads(Path(UNITS).read_text(encoding="utf-8"))}
    profile = {
        uid: profile_of(f"{u['file']}::{u['qualname']}") for uid, u in units.items()
    }
    with open(cands_path, "rb") as stream:
        cands = pickle.load(stream)
    payload = collections.defaultdict(lambda: {"units": {}, "vectors": []})
    for cid, uid, blob, _src in cands:
        u = units[uid]
        p = payload[u["module"]]
        p["units"][uid] = {
            "file": u["file"],
            "qualname": u["qualname"],
            "name": u["qualname"].rsplit(".", 1)[-1],
            "occ": u.get("occ", 0),
            "nocc": u.get("nocc", 1),
        }
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
        if not all(same(r[cid][0], c0, profile=profile[uid]) for r in runs[1:]):
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
    on_skeleton = {
        cid
        for cid, uid, blob, src, c0 in kept
        if cid in sk and same(sk[cid][0], c0, profile=profile[uid])
    }
    kept = [k for k in kept if k[0] not in on_skeleton]
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "screened.pkl"), "wb") as f:
        pickle.dump(kept, f, protocol=4)
    report = {
        "candidates": len(cands),
        "kept": len(kept),
        "dropped": dict(why),
        "matched_on_skeleton": len(on_skeleton),
        "units_with_kept": len({k[1] for k in kept}),
        "kept_by_source": dict(collections.Counter(k[3] for k in kept)),
    }
    with open(os.path.join(out_dir, "screen_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    print(json.dumps(report))


# ---- select ---------------------------------------------------------------------------------


def select():
    inputs, gold_path, screened_path, out_dir = (
        os.path.abspath(p) for p in sys.argv[2:6]
    )
    per_unit = int(_arg("--per-unit", "4"))
    with open(inputs, "rb") as stream:
        payload = pickle.load(stream)
    gold = json.loads(Path(gold_path).read_text(encoding="utf-8"))
    with open(screened_path, "rb") as stream:
        screened = pickle.load(stream)
    documented, echoes, capped = set(), set(), set()
    for path in [p for p in _arg("--documented", "").split(",") if p]:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        documented.update(data["documented"])
        capped.update(data.get("capped_units", []))
    for path in [p for p in _arg("--echoes", "").split(",") if p]:
        echoes.update(json.loads(Path(path).read_text(encoding="utf-8"))["echoes"])
    drop = (
        set(json.loads(Path(_arg("--drop", "")).read_text(encoding="utf-8")))
        if _arg("--drop", "")
        else set()
    )
    units = {u["uid"]: u for u in json.loads(Path(UNITS).read_text(encoding="utf-8"))}
    sys.path.insert(0, os.path.join(HERE, "..", "..", "tests", "verifier", "lib"))
    from canon import profile_of, same_loose

    profile = {
        uid: profile_of(f"{u['file']}::{u['qualname']}") for uid, u in units.items()
    }
    if drop:
        for p in payload.values():
            p["vectors"] = [v for v in p["vectors"] if v[0] not in drop]
        gold = {vid: g for vid, g in gold.items() if vid not in drop}
    # a unit whose comparison was capped cannot tell its calls apart: all of them stay documented
    for p in payload.values():
        for vid, uid, _blob in p["vectors"]:
            if uid in capped:
                documented.add(vid)
    # results a table of documented outputs could return, per unit
    shown = collections.defaultdict(list)
    for p in payload.values():
        for vid, uid, _blob in p["vectors"]:
            if vid in documented and vid in gold:
                shown[uid].append(gold[vid])

    def result_shown(uid, result):
        return any(same_loose(result, r, profile=profile[uid]) for r in shown[uid])

    by_rule = collections.Counter()
    for p in payload.values():
        for vid, uid, _blob in p["vectors"]:
            if vid not in gold or vid in documented:
                continue
            if vid in echoes:
                documented.add(vid)
                by_rule["result is an argument"] += 1
            elif result_shown(uid, gold[vid]):
                documented.add(vid)
                by_rule["result is a documented result"] += 1
    by_unit = collections.defaultdict(list)
    refused = collections.Counter()
    for cid, uid, blob, src, c0 in screened:
        if uid in capped:
            refused["unit capped"] += 1
        elif cid in documented:
            refused["arguments documented"] += 1
        elif cid in echoes:
            refused["result is an argument"] += 1
        elif result_shown(uid, c0):
            refused["result is a documented result"] += 1
        else:
            by_unit[uid].append((PRIORITY[src], cid, blob, src, c0))
    have = collections.Counter(
        uid
        for p in payload.values()
        for vid, uid, _ in p["vectors"]
        if vid in gold and vid not in documented
    )
    last = max(int(v[1:]) for v in gold)
    added, sources = [], collections.Counter()
    for uid in sorted(by_unit):
        if have.get(uid):
            continue  # the unit already has a call nothing visible shows
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
        for _prio, cid, blob, src, c0 in picked:
            last += 1
            vid = f"V{last:05d}"
            added.append((vid, uid, blob, c0, cid))
            sources[src] += 1
    for vid, uid, blob, c0, _cid in added:
        u = units[uid]
        p = payload.setdefault(u["module"], {"units": {}, "vectors": []})
        p["units"][uid] = {
            "file": u["file"],
            "qualname": u["qualname"],
            "name": u["qualname"].rsplit(".", 1)[-1],
            "occ": u.get("occ", 0),
            "nocc": u.get("nocc", 1),
        }
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
    deciding = collections.Counter(
        uid
        for p in payload.values()
        for vid, uid, _ in p["vectors"]
        if vid not in documented
    )
    report = {
        "added": len(added),
        "units_given_calls": len({a[1] for a in added}),
        "by_source": dict(sources),
        "calls": len(gold),
        "documented": len(kept_documented),
        "deciding": len(gold) - len(kept_documented),
        "documented_by_rule": dict(by_rule),
        "candidates_refused": dict(refused),
        "capped_units": sorted(capped),
        "dropped": sorted(drop),
        "units_with_deciding": len(deciding),
        "units_without_deciding": len(units) - len(deciding),
        "added_ids": {a[0]: a[4] for a in added},
    }
    with open(os.path.join(out_dir, "select_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    print(json.dumps({k: v for k, v in report.items() if k != "added_ids"}))


if __name__ == "__main__":
    {"make": make, "contract": contract, "screen": screen, "select": select}[
        sys.argv[1]
    ]()
