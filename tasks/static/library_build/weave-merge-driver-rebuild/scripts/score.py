"""Turn run records into the spike's numbers: stability, the stub filter, gate tagging, netting, signatures.

Usage: python3 -I score.py RUNS_DIR CASES.json OUT.json
RUNS_DIR holds one JSON record list per driver: ref-r1, ref-r2, ref-r3, ref-p (perturbed), stub-<mode>,
mut-<name>, oracle, amd64 (any may be missing). A case passes for a driver when its status and the
sha256 of its output (None when nothing was written) equal the original's.
"""

from __future__ import annotations

import collections
import json
import os
import sys
from pathlib import Path

# Phase B sizing (owner, 2026-11-26): the gate at 25%, renames and placement as full families.
WEIGHTS = {
    "F1": 0.08,
    "F2": 0.15,
    "F3": 0.12,
    "F4": 0.11,
    "F5": 0.06,
    "F6": 0.08,
    "F7": 0.06,
    "F8": 0.25,
    "F9": 0.04,
    "F10": 0.05,
}
FILTER = [
    "take_ours",
    "take_theirs",
    "take_base",
    "git_plain",
    "git_labelled_hint",
    "diffy",
]
NETTING = [
    "always_box",
    "always_error",
    "routing_only",
    "git_labelled_clean",
    "git_no_hint",
    "noop",
    "empty_clean",
    "ours_conflict",
    "ours_hint",
]
# Cases that grade a stated rule a trivial program happens to reproduce are kept anyway, and their
# family is netted against every program: the stated restrictions (status 2 writes nothing; what
# counts as binary), the line route for files the entity model does not describe (a build without
# it entity-merges them), and two boxes far apart (the hint goes on the first closing marker only).
RESTRICTION_FEATURES = {
    "routing.binary_first_8192",
    "routing.nul_after_8192",
    "routing.not_utf8",
    "routing.both_created",
    "routing.many_same_name_line_route",
    "boxes.near_miss_seven_lines_apart",
}


def load(runs: str, name: str) -> dict | None:
    """id -> (status, sha256) for one driver's records, or None when the file is absent."""
    path = os.path.join(runs, f"{name}.json")
    if not os.path.exists(path):
        return None
    return {
        r["id"]: (r["status"], r.get("sha256"))
        for r in json.loads(Path(path).read_text())
    }


def score(rec: dict, ref: dict, kept: dict[str, str], net: dict[str, float]) -> dict:
    """Per-family pass rate, net credit and the weighted reward of one driver on the kept cases."""
    fams = collections.defaultdict(lambda: [0, 0])
    for cid, fam in kept.items():
        fams[fam][1] += 1
        fams[fam][0] += int(rec.get(cid) == ref[cid])
    present = {f: WEIGHTS[f] for f in fams}
    total_w = sum(present.values())
    out, reward = {}, 0.0
    for f, (ok, n) in sorted(fams.items(), key=lambda kv: int(kv[0][1:])):
        p, s = ok / n, net.get(f, 0.0)
        g = 0.0 if s >= 1 else max(0.0, (p - s) / (1 - s))
        reward += present[f] / total_w * g
        out[f] = {"pass": round(p, 4), "net": round(g, 4), "n": n}
    return {"families": out, "reward": round(reward, 4)}


def main() -> None:
    """Compute and write the spike summary."""
    runs, cases_path, out_path = sys.argv[1:4]
    cases = {
        c["id"]: c for c in json.loads(Path(cases_path).read_text(encoding="utf-8"))
    }
    ref_runs = [load(runs, n) for n in ("ref-r1", "ref-r2", "ref-r3", "ref-p")]
    ref = ref_runs[0]
    summary: dict = {"candidates": len(cases)}
    stable = {
        cid
        for cid in cases
        if all(r is not None and r.get(cid) == ref[cid] for r in ref_runs)
    }
    valid = {
        cid
        for cid in stable
        if ref[cid][0] in (0, 1, 2) and (ref[cid][0] != 2 or ref[cid][1] is None)
    }
    summary["determinism"] = {
        "runs": sum(r is not None for r in ref_runs),
        "unstable": len(cases) - len(stable),
        "invalid_status": len(stable) - len(valid),
    }
    stubs = {m: load(runs, f"stub-{m}") for m in FILTER + NETTING}
    solved = collections.Counter()
    kept_ids = []
    for cid in sorted(valid):
        hits = [m for m in FILTER if stubs.get(m) and stubs[m].get(cid) == ref[cid]]
        for m in hits:
            solved[m] += 1
        if not hits or cases[cid]["feature"] in RESTRICTION_FEATURES:
            kept_ids.append(cid)
    summary["filter"] = {"solved_by": dict(solved), "survivors": len(kept_ids)}
    gate = load(runs, "mut-gate")
    kept: dict[str, str] = {}
    roles = collections.Counter()
    for cid in kept_ids:
        c = cases[cid]
        fam, feat = c["family"], c["feature"]
        sensitive = gate is not None and gate.get(cid) != ref[cid]
        if fam == "F8" and "dual" not in feat:
            if gate is not None and not sensitive:
                roles["refusal_dropped_gate_silent"] += 1
                continue
            roles["refusal"] += 1
        elif fam == "F8":
            if sensitive or ref[cid][0] != 0:
                roles["dual_dropped"] += 1
                continue
            roles["dual"] += 1
        elif sensitive:
            fam = "F8"
            roles["retagged_to_gate"] += 1
        kept[cid] = fam
    oracle = load(runs, "oracle")
    if oracle is not None:
        mism = [cid for cid in kept if oracle.get(cid) != ref[cid]]
        summary["oracle"] = {"mismatches": len(mism), "examples": mism[:10]}
        for cid in mism:
            kept.pop(cid)
    summary["gate_roles"] = dict(roles)
    by_fam = collections.Counter(kept.values())
    by_feat = collections.Counter(cases[c]["feature"] for c in kept)
    by_lang = collections.Counter(cases[c]["lang"] for c in kept)
    summary["kept"] = {
        "total": len(kept),
        "families": dict(sorted(by_fam.items(), key=lambda kv: int(kv[0][1:]))),
        "languages": dict(by_lang),
        "features": dict(by_feat),
    }
    net = {}
    stub_scores = {}
    for m in FILTER + NETTING:
        if stubs.get(m):
            per = collections.defaultdict(lambda: [0, 0])
            for cid, fam in kept.items():
                per[fam][1] += 1
                per[fam][0] += int(stubs[m].get(cid) == ref[cid])
            stub_scores[m] = {f: round(a / b, 4) for f, (a, b) in per.items() if a}
            for f, (a, b) in per.items():
                net[f] = max(net.get(f, 0.0), a / b)
    summary["netting"] = {
        "raw_pass_by_stub": stub_scores,
        "s_f": {f: round(v, 4) for f, v in net.items()},
    }
    drivers = {"reference": ref}
    mutants = sorted(p.stem for p in Path(runs).glob("mut-*.json"))
    for name in [*mutants, "oracle", "amd64"]:
        r = load(runs, name)
        if r is not None:
            drivers[name] = r
    kills = {}
    for name in mutants:
        r = drivers[name]
        per_feature = collections.Counter(
            cases[cid]["feature"] for cid in kept if r.get(cid) != ref[cid]
        )
        per_family = collections.Counter(
            fam for cid, fam in kept.items() if r.get(cid) != ref[cid]
        )
        kills[name] = {
            "total": sum(per_family.values()),
            "families": dict(per_family),
            "features": dict(per_feature),
        }
    summary["kill_matrix"] = kills
    for m in FILTER + NETTING:
        if stubs.get(m):
            drivers[f"stub-{m}"] = stubs[m]
    summary["scores"] = {name: score(r, ref, kept, net) for name, r in drivers.items()}
    amd = load(runs, "amd64")
    if amd is not None:
        sample = [cid for cid in amd if cid in ref]
        summary["amd64_sample"] = {
            "cases": len(sample),
            "identical": sum(amd[c] == ref[c] for c in sample),
        }
    with open(out_path, "w") as fh:
        json.dump({"summary": summary, "kept": kept}, fh, indent=1)
    print(json.dumps(summary, indent=1)[:6000])


if __name__ == "__main__":
    main()
