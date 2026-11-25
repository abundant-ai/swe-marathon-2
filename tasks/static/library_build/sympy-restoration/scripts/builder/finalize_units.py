"""Keep only units that have recorded calls, and carry the calls over to the new unit ids.

usage:
  finalize_units.py uncovered <work_dir>     write work/drop_uncovered.json (units without calls)
  finalize_units.py remap <work_dir>         rewrite work/vectors for the current work/units.json
The unit list the calls were built for is work/units_at_vec.json.
"""

import collections
import json
import os
import pickle
import sys
from pathlib import Path

mode, W = sys.argv[1], os.path.abspath(sys.argv[2])
vd = os.path.join(W, "vectors")
with open(os.path.join(vd, "inputs.pkl"), "rb") as stream:
    payload = pickle.load(stream)
gold = json.loads(Path(os.path.join(vd, "gold.json")).read_text())
old = {
    u["uid"]: u
    for u in json.loads(Path(os.path.join(W, "units_at_vec.json")).read_text())
}

if mode == "uncovered":
    covered = {uid for p in payload.values() for _, uid, _ in p["vectors"]}
    drop = sorted(u["dotted"] for uid, u in old.items() if uid not in covered)
    path = os.path.join(W, "drop_uncovered.json")
    prev = set(json.loads(Path(path).read_text())) if os.path.exists(path) else set()
    with open(path, "w") as stream:
        json.dump(sorted(prev | set(drop)), stream)
    print(
        "units without recorded calls:",
        len(drop),
        "| drop list now",
        len(prev | set(drop)),
    )
elif mode == "remap":
    new = {
        u["dotted"]: u
        for u in json.loads(Path(os.path.join(W, "units.json")).read_text())
    }
    by_uid = {u["uid"]: u for u in new.values()}
    out, kept, lost = {}, 0, 0
    for mod, p in payload.items():
        vecs = []
        for vid, uid, blob in p["vectors"]:
            nu = new.get(old[uid]["dotted"])
            if nu is None:
                lost += 1
                gold.pop(vid, None)
                continue
            vecs.append((vid, nu["uid"], blob))
            kept += 1
        if vecs:
            out[mod] = {
                "units": {
                    x[1]: {
                        "file": by_uid[x[1]]["file"],
                        "qualname": by_uid[x[1]]["qualname"],
                        "name": by_uid[x[1]]["name"],
                        "occ": by_uid[x[1]].get("occ", 0),
                        "nocc": by_uid[x[1]].get("nocc", 1),
                    }
                    for x in vecs
                },
                "vectors": vecs,
            }
    with open(os.path.join(vd, "inputs.pkl"), "wb") as stream:
        pickle.dump(out, stream, protocol=4)
    with open(os.path.join(vd, "gold.json"), "w") as stream:
        json.dump(gold, stream)
    covered = {uid for p in out.values() for _, uid, _ in p["vectors"]}
    uncovered = [u["dotted"] for u in new.values() if u["uid"] not in covered]
    st = {"vectors": len(gold), "units_covered": len(covered), "units_total": len(new)}
    with open(os.path.join(vd, "stats.json"), "w") as stream:
        json.dump(st, stream, indent=1)
    with open(os.path.join(W, "units_at_vec.json"), "w") as stream:
        json.dump(list(new.values()), stream)
    per = collections.Counter(uid for p in out.values() for _, uid, _ in p["vectors"])
    hist = collections.Counter(min(v, 8) for v in per.values())
    print(
        "calls kept",
        kept,
        "| dropped with their unit",
        lost,
        "|",
        st,
        "| units without calls:",
        len(uncovered),
        uncovered[:5],
    )
    print("calls per unit:", dict(sorted(hist.items())))
    assert len(gold) == kept
