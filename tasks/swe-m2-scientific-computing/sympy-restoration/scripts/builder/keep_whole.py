"""Leave whole every unit that no graded item runs, and write the prepared inputs again for the rest.

The rule: a unit stays removed only if at least one graded item runs its body, traced on the original
tree by `graded_coverage.py`: one of its own counted calls, or a counted call or an example of a unit
in the set that runs it. Every other unit gets its original body back in the checkout and stops being
a unit. One exception, also by rule: a unit that would be left whole stays removed when its original
body is a near-copy of the body of a unit that stays removed and is graded, by the twin scan's own
tests (`twin_scan.py`, with the bodies left whole as the visible side), since a whole copy would give
that body away; each such unit is recorded.

The units that stay are numbered again from U0001 in their old order, and every prepared input that
names units is written again for them: the unit list, the agent's tree and the verifier's skeleton
(each unit-bearing file rebuilt from the original with `units.blank_source`, after checking that the
same function gives back the old file from the old list), the body facts, the per-unit times, the
calls (the calls of the units left whole leave the call data; none of them counts) and the reference
solution's files. The tests list and everything else is copied unchanged. A literal scan reports any
string or long number in a body left whole that is also a leaf of a counted call's arguments or
result.

usage: keep_whole.py <task_root> <original_root> <coverage.json> <out_root>
<original_root> holds the original sympy/ (the build's pristine tree); <out_root> receives the new
prepared inputs at the task's own paths, and keep_whole_report.json.
"""
from __future__ import annotations

import ast
import collections
import copy
import difflib
import gzip
import io
import json
import keyword
import os
import pickle
import shutil
import sys
import tarfile
import tokenize

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from units import blank_source, find_units  # noqa: E402

STEP = os.path.join("steps", "01-restore-bodies")
PRIVATE = os.path.join(STEP, "tests", "private")


# ---- the twin scan's tests (twin_scan.py), with the bodies left whole as the visible side ----

def _doc_and_rest(fn):
    b = fn.body
    if b and isinstance(b[0], ast.Expr) and isinstance(getattr(b[0], "value", None), ast.Constant) \
            and isinstance(b[0].value.value, str):
        return b[0], b[1:]
    return None, b


class _Blind(ast.NodeTransformer):
    """Rename every identifier, so that a body and a renamed copy of it look the same."""

    def visit_Name(self, node):
        return ast.copy_location(ast.Name(id="_", ctx=node.ctx), node)

    def visit_Attribute(self, node):
        self.generic_visit(node)
        node.attr = "_"
        return node

    def visit_arg(self, node):
        node.arg = "_"
        node.annotation = None
        return node

    def visit_keyword(self, node):
        self.generic_visit(node)
        node.arg = "_" if node.arg else None
        return node

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        node.name = "_"
        return node


TOKEN_MIN = 40          # a graded body this many tokens long or more is compared token by token
TOKEN_PLAIN = 0.80     # alike as tokens, names kept
TOKEN_BLIND = 0.90     # alike as tokens, every name blinded
TOKEN_CONTAINED = 0.90 # the graded body's tokens, names kept, found in order in the visible one
SHINGLE = 4            # the prefilter: blinded runs of this many tokens
SHINGLE_SHARE = 0.25   # shared by at least this share of the smaller body's runs


def _tokens(text):
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type in (tokenize.NEWLINE, tokenize.NL, tokenize.INDENT, tokenize.DEDENT, tokenize.COMMENT,
                            tokenize.ENDMARKER):
                continue
            out.append((tok.type, tok.string))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    plain = [t for _, t in out]
    blind = ["_" if kind == tokenize.NAME and not keyword.iskeyword(t) else t for kind, t in out]
    return plain, blind


def body_record(fn):
    _doc, rest = _doc_and_rest(fn)
    nn = sum(1 for s in rest for _ in ast.walk(s))
    text = "\n".join(ast.unparse(s) for s in rest)
    plain, blind_tokens = _tokens(text)
    return {
        "name": fn.name,
        "dump": "\n".join(ast.dump(s, include_attributes=False) for s in rest),
        "text": text,
        "n_stmts": sum(1 for s in rest for x in ast.walk(s) if isinstance(x, ast.stmt)),
        "nodes": nn,
        "blind": ("\n".join(ast.dump(_Blind().visit(copy.deepcopy(s)), include_attributes=False) for s in rest)
                  if nn >= 25 else None),
        "plain_tokens": plain,
        "blind_tokens": blind_tokens,
        "shingles": {tuple(blind_tokens[i:i + SHINGLE]) for i in range(max(0, len(blind_tokens) - SHINGLE + 1))},
    }


def near_copies(unit, visible):
    """Every visible body that the twin scan's tests find a copy of a unit's body, with the test:
    the same syntax tree under the same name; the same tree under another name, for a body of three
    statements or twelve nodes; the same tree once every name is blinded, for twenty-five nodes; text
    85% alike, for two statements, under the same name or in the same file; and, across names and
    files, for a body of TOKEN_MIN tokens or more, its tokens TOKEN_PLAIN alike with names kept,
    TOKEN_BLIND alike with every name blinded, or the unit's tokens TOKEN_CONTAINED found in order in
    the visible body (after a prefilter on shared runs of tokens)."""
    found = []
    for r in visible:
        if r["dump"] == unit["dump"]:
            if r["name"] == unit["name"]:
                found.append(("exact-same-name", r))
                continue
            if unit["n_stmts"] >= 3 or unit["nodes"] >= 12:
                found.append(("exact-other-name", r))
                continue
        if unit["blind"] is not None and r["blind"] == unit["blind"]:
            found.append(("same-after-renaming", r))
            continue
        if unit["n_stmts"] >= 2 and (r["name"] == unit["name"] or r["file"] == unit["file"]) \
                and abs(len(r["text"]) - len(unit["text"])) <= 0.3 * max(len(unit["text"]), 1) \
                and difflib.SequenceMatcher(None, unit["text"], r["text"], autojunk=False).ratio() >= 0.85:
            found.append(("similar-same-name" if r["name"] == unit["name"] else "similar-sibling", r))
            continue
        # token by token, across names and files, for a body of TOKEN_MIN tokens or more
        if len(unit["plain_tokens"]) >= TOKEN_MIN and unit["shingles"] and r["shingles"]:
            shared = len(unit["shingles"] & r["shingles"]) / min(len(unit["shingles"]), len(r["shingles"]))
            if shared < SHINGLE_SHARE:
                continue
            plain = difflib.SequenceMatcher(None, unit["plain_tokens"], r["plain_tokens"], autojunk=False)
            if plain.ratio() >= TOKEN_PLAIN:
                found.append(("tokens-alike", r))
            elif difflib.SequenceMatcher(None, unit["blind_tokens"], r["blind_tokens"], autojunk=False).ratio() >= TOKEN_BLIND:
                found.append(("tokens-alike-blinded", r))
            elif sum(b.size for b in plain.get_matching_blocks()) >= TOKEN_CONTAINED * len(unit["plain_tokens"]):
                found.append(("tokens-contained", r))
    return found


def index_functions(tree):
    out = {}

    def visit(node, prefix):
        for ch in node.body:
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out.setdefault(prefix + ch.name, []).append(ch)
            elif isinstance(ch, ast.ClassDef):
                visit(ch, prefix + ch.name + ".")

    visit(tree, "")
    return out


# ---- literals ----

def literals(fn):
    """Strings of 8 or more characters and numbers of 6 or more digits in a function's body."""
    _doc, rest = _doc_and_rest(fn)
    found = set()
    for s in rest:
        for node in ast.walk(s):
            if isinstance(node, ast.Constant):
                v = node.value
                if isinstance(v, str) and len(v.strip()) >= 8:
                    found.add(v.strip())
                elif isinstance(v, (int, float)) and not isinstance(v, bool) and len(str(abs(v)).replace(".", "")) >= 6:
                    found.add(str(v))
    return found


def leaves(obj, out):
    if isinstance(obj, str):
        if len(obj.strip()) >= 8 or (obj.strip().lstrip("-").isdigit() and len(obj.strip().lstrip("-")) >= 6):
            out.add(obj.strip())
    elif isinstance(obj, (list, tuple)):
        for x in obj:
            leaves(x, out)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            leaves(k, out)
            leaves(v, out)


def argument_strings(value, out, depth=0):
    """The strings, the numbers of 6 or more digits and the long symbol names in a call's arguments."""
    if depth > 6:
        return
    if isinstance(value, dict):
        for v in list(value.values())[:200]:
            argument_strings(v, out, depth + 1)
        return
    if isinstance(value, (list, tuple, set, frozenset)):
        for v in list(value)[:200]:
            argument_strings(v, out, depth + 1)
        return
    if isinstance(value, str):
        leaves(value, out)
        return
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        leaves(str(value), out)
        return
    atoms = getattr(value, "atoms", None)
    if callable(atoms):
        try:
            for atom in list(atoms())[:500]:
                if getattr(atom, "is_Number", False) or getattr(atom, "is_Symbol", False):
                    leaves(str(atom), out)
        except Exception:  # noqa: BLE001
            pass


# ---- archives ----

def read_tar(path):
    with tarfile.open(path, "r:gz") as tf:
        members = tf.getmembers()
        data = {m.name: (tf.extractfile(m).read() if m.isfile() else None) for m in members}
    return members, data


def write_tar(path, members, data, replaced):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.PAX_FORMAT) as tf:
        for m in members:
            info = copy.copy(m)
            if m.isfile():
                content = replaced.get(m.name, data[m.name])
                info.size = len(content)
                tf.addfile(info, io.BytesIO(content))
            else:
                tf.addfile(info)
    with open(path, "wb") as f, gzip.GzipFile(fileobj=f, mode="wb", mtime=0, compresslevel=9) as gz:
        gz.write(buf.getvalue())


def _option(flag):
    return os.path.abspath(sys.argv[sys.argv.index(flag) + 1]) if flag in sys.argv else None


def main():
    task, original, coverage_path, out = (os.path.abspath(p) for p in sys.argv[1:5])
    absorbed_path, pairs_only = _option("--absorbed"), _option("--pairs-only")
    units = json.load(open(os.path.join(task, "environment", "data", "units.json"), encoding="utf-8"))
    traced = json.load(open(coverage_path, encoding="utf-8"))
    coverage, items = traced["units"], traced.get("items", {})
    assert set(coverage) == {u["uid"] for u in units}, "the trace is for another unit list"
    # graded: a counted call of its own, or another unit's graded item that fails without its body
    # (absorbed.py); with no such probe given, any graded item that runs it
    through_others = None
    if absorbed_path:
        probe = json.load(open(absorbed_path, encoding="utf-8"))
        through_others = set(probe["graded"])
    graded = {uid for uid, f in coverage.items() if f["counted"]
              or ((f["run_by_calls"] or f["run_by_examples"]) and (through_others is None or uid in through_others))}
    by_uid = {u["uid"]: u for u in units}
    trees, records = {}, {}
    for rel in sorted({u["file"] for u in units}):
        trees[rel] = ast.parse(open(os.path.join(original, rel), encoding="utf-8").read())
    for u in units:
        fn = index_functions(trees[u["file"]])[u["qualname"]][u.get("occ", 0)]
        rec = body_record(fn)
        rec["file"] = u["file"]
        records[u["uid"]] = rec

    # the rule, then the near-copy exception
    candidates = sorted(uid for uid in by_uid if uid not in graded)
    visible = [dict(records[uid], uid=uid) for uid in candidates]
    copies = {}
    for uid in sorted(graded):
        for rule, twin in near_copies(records[uid], visible):
            copies.setdefault(twin["uid"], []).append({"graded_unit": by_uid[uid]["dotted"], "test": rule})
    if pairs_only:
        # the near-copies and their twins, for twin_calls.py: nothing else is written
        twins = {}
        for near, found in copies.items():
            twins[near] = sorted({next(u for u, x in by_uid.items() if x["dotted"] == c["graded_unit"]) for c in found})
        with open(pairs_only, "w", encoding="utf-8") as f:
            json.dump(twins, f, indent=1)
        print(json.dumps({"ungraded": len(candidates), "near_copies": len(twins)}))
        return
    whole = [uid for uid in candidates if uid not in copies]
    kept = sorted(uid for uid in by_uid if uid not in set(whole))
    new_uid = {old: f"U{i + 1:04d}" for i, old in enumerate(kept)}
    ranks = {old: r for r, old in enumerate(sorted(kept, key=lambda o: by_uid[o]["order"]))}

    # the unit list
    new_units = []
    for old in kept:
        u = dict(by_uid[old], uid=new_uid[old], order=ranks[old])
        new_units.append(u)
    os.makedirs(os.path.join(out, "environment", "data"), exist_ok=True)
    with open(os.path.join(out, "environment", "data", "units.json"), "w", encoding="utf-8") as f:
        json.dump(new_units, f)

    # the unit-bearing files, from the original, checked against the old ones
    skel_members, skel_data = read_tar(os.path.join(task, PRIVATE, "skeleton.tar.gz"))
    work_members, work_data = read_tar(os.path.join(task, "environment", "data", "workspace.tar.gz"))
    by_file = collections.defaultdict(list)
    for u in units:
        by_file[u["file"]].append(u)
    replaced, files_kept = {}, []
    for rel, us in sorted(by_file.items()):
        src = open(os.path.join(original, rel), encoding="utf-8").read()
        found = {c["qualname"]: c for c in find_units(src, rel)}
        for u in us:
            c = found[u["qualname"]]
            assert (c["occ"], c["nocc"]) == (u.get("occ", 0), u.get("nocc", 1)), (rel, u["qualname"])
        old_text = blank_source(src, [dict(found[u["qualname"]], uid=u["uid"]) for u in us]).encode("utf-8")
        assert skel_data.get(rel) == old_text, f"the old skeleton's {rel} is not blank_source of the original"
        assert work_data.get(rel) == old_text, f"the old working copy's {rel} is not blank_source of the original"
        stay = [u for u in us if u["uid"] in new_uid]
        new_text = blank_source(src, [dict(found[u["qualname"]], uid=new_uid[u["uid"]]) for u in stay])
        replaced[rel] = new_text.encode("utf-8")
        if stay:
            files_kept.append(rel)
    os.makedirs(os.path.join(out, PRIVATE, "vectors"), exist_ok=True)
    write_tar(os.path.join(out, PRIVATE, "skeleton.tar.gz"), skel_members, skel_data, replaced)
    write_tar(os.path.join(out, "environment", "data", "workspace.tar.gz"), work_members, work_data, replaced)

    # the reference solution: the original text of the files that still hold units
    sol = os.path.join(out, STEP, "solution", "data")
    for rel in files_kept:
        os.makedirs(os.path.dirname(os.path.join(sol, rel)), exist_ok=True)
        shutil.copyfile(os.path.join(task, STEP, "solution", "data", rel), os.path.join(sol, rel))

    # body facts and per-unit times
    facts = json.load(open(os.path.join(task, PRIVATE, "unit_bodies.json"), encoding="utf-8"))
    with open(os.path.join(out, PRIVATE, "unit_bodies.json"), "w", encoding="utf-8") as f:
        json.dump({new_uid[o]: facts[o] for o in kept}, f)
    # the examples' times are keyed by the unit's dotted name (as the examples runner names its items), the
    # calls' times by unit id; the import times by module, kept for the modules that still hold units
    timing = json.load(open(os.path.join(task, PRIVATE, "timing.json"), encoding="utf-8"))
    kept_dotted = {by_uid[o]["dotted"] for o in kept}
    kept_modules = {by_uid[o]["module"] for o in kept}
    examples = timing["doctest"]["units"]
    assert {u["dotted"] for u in units} <= set(examples), "the old times do not cover every unit's examples"
    timing["doctest"]["units"] = {d: t for d, t in examples.items() if d in kept_dotted}
    calls = timing["vector"]["units"]
    timing["vector"]["units"] = {new_uid[o]: t for o, t in calls.items() if o in new_uid}
    for phase in ("doctest", "vector"):
        timing[phase]["load"] = {m: t for m, t in timing[phase]["load"].items() if m in kept_modules}
    assert set(timing["doctest"]["units"]) == kept_dotted
    with open(os.path.join(out, PRIVATE, "timing.json"), "w", encoding="utf-8") as f:
        json.dump(timing, f)
    shutil.copyfile(os.path.join(task, PRIVATE, "sealed_tests.json"), os.path.join(out, PRIVATE, "sealed_tests.json"))

    # the calls
    vd = os.path.join(task, PRIVATE, "vectors")
    with open(os.path.join(vd, "inputs.pkl"), "rb") as f:
        payload = pickle.load(f)  # noqa: S301 - the task's own build output
    gold = json.load(open(os.path.join(vd, "gold.json"), encoding="utf-8"))
    documented = json.load(open(os.path.join(vd, "documented.json"), encoding="utf-8"))
    counted_before = {v for v in gold if v not in set(documented["calls"])}
    new_payload, dropped = {}, set()
    for mod, p in payload.items():
        vecs = []
        for vid, uid, blob in p["vectors"]:
            if uid in new_uid:
                vecs.append((vid, new_uid[uid], blob))
            else:
                dropped.add(vid)
        if vecs:
            new_payload[mod] = {"units": {new_uid[o]: m for o, m in p["units"].items() if o in new_uid},
                                "vectors": vecs}
    assert not dropped & counted_before, "a counted call belongs to a unit left whole"
    new_gold = {v: g for v, g in gold.items() if v not in dropped}
    new_documented = dict(documented, calls=[v for v in documented["calls"] if v not in dropped])
    with open(os.path.join(out, PRIVATE, "vectors", "inputs.pkl"), "wb") as f:
        pickle.dump(new_payload, f, protocol=4)
    with open(os.path.join(out, PRIVATE, "vectors", "gold.json"), "w", encoding="utf-8") as f:
        json.dump(new_gold, f)
    with open(os.path.join(out, PRIVATE, "vectors", "documented.json"), "w", encoding="utf-8") as f:
        json.dump(new_documented, f)

    # for an auditor of the hidden data: what grades each removed unit; its own counted calls, else the
    # graded items of other units that run it, and the one that fails without its body
    counted_now = {v for v in new_gold if v not in set(new_documented["calls"])}
    own = collections.defaultdict(list)
    for p in new_payload.values():
        for vid, uid, _blob in p["vectors"]:
            if vid in counted_now:
                own[uid].append(vid)
    first = json.load(open(absorbed_path, encoding="utf-8"))["graded"] if absorbed_path else {}
    coverage_map = {}
    for old in kept:
        entry = {"counted_calls": sorted(own.get(new_uid[old], []))}
        if not entry["counted_calls"]:
            ran = items.get(old, {"calls": [], "examples": []})
            entry["run_inside_counted_calls"] = sorted(v for v in ran["calls"] if v in counted_now)
            entry["run_inside_examples_of"] = sorted(new_uid[o] for o in ran["examples"] if o in new_uid)
            failing = first.get(old)
            if failing:
                entry["fails_without_it"] = failing if failing[0] == "call" else ["examples", new_uid.get(failing[1])]
        coverage_map[new_uid[old]] = entry
    with open(os.path.join(out, PRIVATE, "unit_coverage.json"), "w", encoding="utf-8") as f:
        json.dump(coverage_map, f)

    report = {
        "rule": "removed only if a graded item runs the body (own counted call, or another unit's graded item)",
        "units_before": len(units), "graded": len(graded), "ungraded": len(candidates),
        "near_copies_kept_removed": {by_uid[k]["dotted"]: v for k, v in sorted(copies.items())},
        "left_whole": len(whole), "units_after": len(kept),
        "files_before": len(by_file), "files_after": len(files_kept),
        "calls_before": len(gold), "calls_after": len(new_gold), "calls_dropped": len(dropped),
        "counted_calls": len(counted_before),
        "literal_hits": None,
        "whole_units": sorted(by_uid[o]["dotted"] for o in whole),
        "uid_map": new_uid,
    }
    with open(os.path.join(out, "keep_whole_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)

    # literals of the bodies left whole against the leaves of the counted calls' arguments and results
    sys.path.insert(0, original)
    sys.setrecursionlimit(10000)
    answers, arguments = set(), set()
    for vid in counted_before:
        leaves(gold[vid], answers)
    for p in payload.values():
        for vid, _uid, blob in p["vectors"]:
            if vid in counted_before:
                try:
                    argument_strings(pickle.loads(blob), arguments)  # noqa: S301 - build output
                except Exception:  # noqa: BLE001
                    pass
    hits = []
    for uid in whole:
        u = by_uid[uid]
        fn = index_functions(trees[u["file"]])[u["qualname"]][u.get("occ", 0)]
        for lit in sorted(literals(fn)):
            where = [name for name, pool in (("result", answers), ("argument", arguments)) if lit in pool]
            if where:
                hits.append({"unit": u["dotted"], "literal": lit[:80], "in": where})

    report["literal_hits"] = hits
    with open(os.path.join(out, "keep_whole_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    print(json.dumps({k: (v if not isinstance(v, (list, dict)) else len(v)) for k, v in report.items()}))


if __name__ == "__main__":
    main()
