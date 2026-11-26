"""Counted calls that expect the error a unit's docstring example shows (fix round 10).

For the units of <uids.json>, the docstring examples that show an error are found: doctest's own reading
(an expected output that is a traceback; `+SKIP` examples left out), and a `sage:` line followed by a
traceback, which shows the same in another prompt. The examples before the first such one are run on the
original tree in the module's namespace, then that example, and the arguments of the unit's own call
made directly by the example are taken at the unit's entry. Each call is replayed on the original under
three seeds and kept when it raises, every time, the error the example shows (the same class, or a
subclass of it). It is added to the selection as a counted call whose expected result is that error
(`["EXC", name, chain]`, compared by class as `canon.same` compares errors). It is not listed as
documented although the example makes it: what it grades is the one thing the example states, which no
other call of these units does. Build time only; prints counts only.

usage: error_calls.py <original_tree> <units.json> <uids.json> <selection_dir> <out_dir>
<selection_dir> holds inputs.pkl, gold.json and documented.json; <out_dir> receives the three with the new
calls added (ids after the highest one), and error_calls_report.json.
"""
from __future__ import annotations

import collections
import doctest
import importlib
import json
import os
import pickle
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "..", "steps", "01-restore-bodies", "tests", "verifier", "lib")
SAGE = re.compile(r"^\s*sage:\s*(?P<src>.+?)\s*\n\s*Traceback \(most recent call last\):\s*\n(?:.*\n)*?\s*(?P<exc>[A-Za-z_][\w.]*)\s*:",
                  re.M)
TOOL = 5
SEEDS = ("error-call-a", "error-call-b", "error-call-c")


def error_examples(doc: str) -> list[tuple[int, str, str]]:
    """(index among the doctest examples before it, source, error class name) of each example that shows an
    error; `sage:` ones come after the doctest examples."""
    found = []
    try:
        examples = doctest.DocTestParser().get_examples(doc or "")
    except ValueError:
        examples = []
    for k, e in enumerate(examples):
        if e.exc_msg is not None and not e.options.get(doctest.SKIP):
            found.append((k, e.source, e.exc_msg.split(":")[0].strip().rsplit(".", 1)[-1]))
    for m in SAGE.finditer(doc or ""):
        found.append((len(examples), m.group("src") + "\n", m.group("exc").rsplit(".", 1)[-1]))
    return found


def main():
    root, units_path, uids_path, selection, out = sys.argv[1:6]
    root = os.path.realpath(root)
    sys.path[:] = [p for p in sys.path if p not in ("", os.getcwd())]
    sys.path.insert(0, root)
    sys.path.append(os.path.abspath(LIB))
    os.chdir(root)
    import rvector
    from canon import same

    units = {u["uid"]: u for u in json.load(open(units_path, encoding="utf-8"))}
    want = json.load(open(uids_path, encoding="utf-8"))
    payload = pickle.load(open(os.path.join(selection, "inputs.pkl"), "rb"))  # noqa: S301 - build output
    gold = json.load(open(os.path.join(selection, "gold.json"), encoding="utf-8"))
    documented = json.load(open(os.path.join(selection, "documented.json"), encoding="utf-8"))
    facts = {uid: m for p in payload.values() for uid, m in p["units"].items()}
    mon = sys.monitoring
    mon.use_tool_id(TOOL, "error-calls")
    report, added = collections.OrderedDict(), []
    last = max(int(v[1:]) for v in gold)
    for uid in want:
        u = units[uid]
        module = importlib.import_module(u["module"])
        meta = facts.get(uid) or {"file": u["file"], "qualname": u["qualname"], "name": u["qualname"].rsplit(".", 1)[-1],
                                  "occ": u.get("occ", 0), "nocc": u.get("nocc", 1)}
        fn = rvector.resolve(module, root, meta)
        doc = fn.__doc__ or ""
        try:
            examples = doctest.DocTestParser().get_examples(doc)
        except ValueError:
            examples = []
        shown = error_examples(doc)
        if not shown:
            report[u["dotted"]] = "no example shows an error"
            continue
        code = fn.__code__
        n = code.co_argcount + code.co_kwonlyargcount + bool(code.co_flags & 0x04) + bool(code.co_flags & 0x08)
        taken = []
        state = {"on": False}

        def on_start(c, offset, code=code, n=n, taken=taken, state=state):
            if c is not code:
                return mon.DISABLE
            if state["on"] and sys._getframe(1).f_back is not None and sys._getframe(1).f_back.f_code.co_filename == "<example>":
                try:
                    taken.append(pickle.dumps({k: sys._getframe(1).f_locals[k] for k in code.co_varnames[:n]}, protocol=4))
                except Exception:  # noqa: BLE001
                    pass
            return None

        mon.register_callback(TOOL, mon.events.PY_START, on_start)
        mon.set_local_events(TOOL, code, mon.events.PY_START)
        rows = []
        for index, source, exc_name in shown:
            globs = dict(vars(module))
            for e in examples[:index]:
                try:
                    exec(compile(e.source, "<setup>", "exec"), globs)  # noqa: S102 - the unit's own docstring
                except BaseException:  # noqa: BLE001
                    pass
            taken.clear()
            state["on"] = True
            try:
                exec(compile(source, "<example>", "single"), globs)  # noqa: S102
                raised = None
            except BaseException as e:  # noqa: BLE001
                raised = type(e).__name__
            finally:
                state["on"] = False
            for blob in taken:
                outcomes = []
                for seed in SEEDS:
                    rvector.reseed(seed)
                    try:
                        rvector.call(fn, rvector.revive(pickle.loads(blob)))  # noqa: S301 - build output
                        outcomes.append(None)
                    except BaseException as e:  # noqa: BLE001
                        chain = [k.__name__ for k in type(e).__mro__ if k.__name__ not in ("Exception", "BaseException", "object")]
                        outcomes.append(["EXC", type(e).__name__, chain[:12]])
                first = outcomes[0]
                ok = (first is not None and all(o == first for o in outcomes)
                      and same(["EXC", exc_name, [exc_name]], first) and first[1] != "NotImplementedError")
                rows.append({"example_raised": raised, "shown": exc_name, "replayed": first[1] if first else None, "kept": ok})
                if ok and all(blob != b for _v, _u, b, _c in added if _u == uid):
                    last += 1
                    added.append((f"V{last:05d}", uid, blob, first))
        mon.set_local_events(TOOL, code, 0)
        mon.register_callback(TOOL, mon.events.PY_START, None)
        report[u["dotted"]] = rows
    mon.free_tool_id(TOOL)
    os.makedirs(out, exist_ok=True)
    for vid, uid, blob, c in added:
        u = units[uid]
        p = payload.setdefault(u["module"], {"units": {}, "vectors": []})
        p["units"].setdefault(uid, facts.get(uid) or {"file": u["file"], "qualname": u["qualname"],
                                                      "name": u["qualname"].rsplit(".", 1)[-1], "occ": u.get("occ", 0),
                                                      "nocc": u.get("nocc", 1)})
        p["vectors"].append((vid, uid, blob))
        gold[vid] = c
    with open(os.path.join(out, "inputs.pkl"), "wb") as f:
        pickle.dump(payload, f, protocol=4)
    with open(os.path.join(out, "gold.json"), "w", encoding="utf-8") as f:
        json.dump(gold, f)
    shutil.copyfile(os.path.join(selection, "documented.json"), os.path.join(out, "documented.json"))
    summary = {"units": len(want), "units_given_calls": len({a[1] for a in added}), "calls_added": len(added),
               "calls_before": len(gold) - len(added), "documented": len(documented["calls"])}
    with open(os.path.join(out, "error_calls_report.json"), "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "units": report, "added_ids": [a[0] for a in added]}, f, indent=1)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
