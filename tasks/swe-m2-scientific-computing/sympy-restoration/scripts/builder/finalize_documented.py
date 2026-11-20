"""Write the verifier's list of documented calls for the final calls and reference results.

Build time only. A call is documented when a docstring example or a visible test makes a call
with the same arguments, or the same up to a renaming of symbols (the documented.py outputs
given), when its result is one of its own arguments unchanged (the echoes.py output given), or
when its result is the result of another documented call of its unit (compared by the unit's
profile; applied until nothing changes). Every call of a unit whose run-time comparison was capped
stays documented. Only calls that are not documented count for the reward.

usage: finalize_documented.py <inputs.pkl> <gold.json> <out.json> <documented.py output> [...] [--echoes <echoes.json>]
"""
from __future__ import annotations

import collections
import json
import os
import pickle
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "steps", "01-restore-bodies", "tests", "verifier", "lib"))
from canon import profile_of, same  # noqa: E402


def main():
    argv = list(sys.argv[1:])
    echoes = set()
    if "--echoes" in argv:
        i = argv.index("--echoes")
        echoes = set(json.load(open(argv[i + 1], encoding="utf-8"))["echoes"])
        del argv[i:i + 2]
    inputs, gold_path, out = argv[:3]
    payload = pickle.load(open(inputs, "rb"))
    gold = json.load(open(gold_path, encoding="utf-8"))
    by_arguments, capped = set(), set()
    for path in argv[3:]:
        data = json.load(open(path, encoding="utf-8"))
        by_arguments.update(data["documented"])
        capped.update(data.get("capped_units", []))
    calls, profile = collections.defaultdict(list), {}
    for p in payload.values():
        for vid, uid, _blob in p["vectors"]:
            if vid in gold:
                calls[uid].append(vid)
                u = p["units"][uid]
                profile[uid] = profile_of(f"{u['file']}::{u['qualname']}")
    documented, why = set(), collections.Counter()
    for uid, vids in calls.items():
        for v in vids:
            reason = "unit capped" if uid in capped else "arguments" if v in by_arguments else \
                "result is an argument" if v in echoes else None
            if reason:
                documented.add(v)
                why[reason] += 1
    while True:
        # a result some documented call of the unit returns is a documented result
        added = {v for uid, vids in calls.items() for v in vids if v not in documented
                 and any(same(gold[v], gold[r], profile=profile[uid]) for r in vids if r in documented)}
        if not added:
            break
        documented |= added
        why["result is a documented result"] += len(added)
    deciding_units = {uid for uid, vids in calls.items() if any(v not in documented for v in vids)}
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"calls": sorted(documented)}, f)
    print(json.dumps({"calls": len(gold), "documented": len(documented), "deciding": len(gold) - len(documented),
                      "by_rule": dict(why), "units_with_deciding": len(deciding_units), "units_with_calls": len(calls),
                      "capped_units": sorted(capped)}))


if __name__ == "__main__":
    main()
