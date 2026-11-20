"""Write the verifier's list of documented calls for the final calls and reference results.

Build time only. A call is documented when a docstring example or a visible test makes a call
with the same arguments (the documented.py outputs given), or when its result is the result of
one of its unit's such calls. Only calls that are not documented count for the reward.

usage: finalize_documented.py <inputs.pkl> <gold.json> <out.json> <documented.py output> [...]
"""
from __future__ import annotations

import collections
import json
import os
import pickle
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "steps", "01-restore-bodies", "tests", "verifier", "lib"))
from canon import same  # noqa: E402


def main():
    inputs, gold_path, out = sys.argv[1:4]
    payload = pickle.load(open(inputs, "rb"))
    gold = json.load(open(gold_path, encoding="utf-8"))
    by_arguments = set()
    for path in sys.argv[4:]:
        by_arguments.update(json.load(open(path, encoding="utf-8"))["documented"])
    calls = collections.defaultdict(list)
    for p in payload.values():
        for vid, uid, _blob in p["vectors"]:
            if vid in gold:
                calls[uid].append(vid)
    documented = set()
    for uid, vids in calls.items():
        shown = [gold[v] for v in vids if v in by_arguments]
        for v in vids:
            if v in by_arguments or any(same(gold[v], r) for r in shown):
                documented.add(v)
    deciding_units = {uid for uid, vids in calls.items() if any(v not in documented for v in vids)}
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"calls": sorted(documented)}, f)
    print(json.dumps({"calls": len(gold), "documented": len(documented), "deciding": len(gold) - len(documented),
                      "by_arguments": len(by_arguments & set(gold)), "units_with_deciding": len(deciding_units),
                      "units_with_calls": len(calls)}))


if __name__ == "__main__":
    main()
