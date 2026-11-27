"""Evaluate four alternating day/night order heads on one continuously updated shared station."""

import json
from functools import lru_cache
from importlib.util import module_from_spec, spec_from_file_location

import numpy as np
from coupled import hidden, update
from panel_data import site_of
from shift_data import RECIPES, ROOT, SEEDS, SITE
from shift_data import commissioning as probes

shared_path = (
    ROOT / "single_eval.py"
    if (ROOT / "single_eval.py").exists()
    else ROOT.parent / "relative" / "inspection_eval.py"
)
spec = spec_from_file_location("single_scanner_eval", shared_path)
prior = module_from_spec(spec)
spec.loader.exec_module(prior)
station = prior.station
build_inputs = prior.build_inputs
summary = prior.summary


def reward(out: dict, target: int, controls: dict | None = None) -> dict:
    """Score a frozen candidate against matched untreated and joint informed continuations.

    Target 0 denotes the A pair of day/night fixtures, target 1 denotes the
    alternate pair. All observation arms are scored on both. Callers can provide
    precomputed controls; by default this reads the frozen runtime controls.
    """
    if controls is None:
        controls = json.loads((ROOT / "data" / "inspection-controls.json").read_text())
    return prior.reward(out, target, controls)


@lru_cache(maxsize=48)
def sequence(seed, target, rep):
    train, test = prior.future_arrays(seed)
    rng = np.random.default_rng(88090 + seed + rep)
    # Two binary heads commission on each shift. The ordering reverses in the
    # second independent stream so that either domain can follow the other.
    shift0 = int(rep == 939)
    order = [shift0, 1 - shift0, shift0, 1 - shift0]
    programs = []
    for k in (0, 1):
        singleton = int(rng.choice((1, 2, 3)))
        first = (
            (singleton,)
            if rng.integers(2)
            else tuple(sorted(set(range(4)) - {singleton}))
        )
        pair = tuple(sorted(rng.choice(4, 2, replace=False).tolist()))
        programs.append([first, pair] if rng.integers(2) else [pair, first])
    phases = []
    for q, shift in enumerate(order):
        nominal = RECIPES[target, site_of(seed), shift]
        trphase = (train[2] - nominal[train[1]]) % 4
        testphase = (test[2] - nominal[test[1]]) % 4
        rule = programs[shift][q // 2]
        y = np.isin(trphase, rule)
        yt = np.isin(testphase, rule)
        batches = [
            np.r_[rng.choice(np.flatnonzero(~y), 24), rng.choice(np.flatnonzero(y), 24)]
            for _ in range(32)
        ]
        phases.append((rule, y, yt, batches, testphase, shift))
    return train, test, phases


def simulate(old, new, seed, target, rep):
    s = {k: v.copy() for k, v in new.items()}
    train, test, phases = sequence(seed, target, rep)
    x, xt = train[0], test[0]
    old_truth = test[-1] > old["cut"]

    def archive(h, heads):
        return np.einsum("nbh,bch->nc", h, heads)

    wanted = archive(hidden(xt, old), old["legacy"])
    after = archive(hidden(xt, s), s["legacy"])
    drift = np.sqrt(((after - wanted) ** 2).mean(0)) / wanted.std(0).clip(0.05, None)
    archived = [((after + s["intercepts"] > 0) == old_truth).mean(0).tolist()]

    def rates(pred, yt, relative):
        ok = pred == yt
        return {
            "accuracy": float((ok[yt].mean() + ok[~yt].mean()) / 2),
            "weak_class": float(
                min(ok[relative == i].mean() for i in np.unique(relative))
            ),
            "weak_condition": float(
                min(ok[test[1] == i].mean() for i in np.unique(test[1]))
            ),
        }

    latest = []
    keepers = []
    for rule, y, yt, ids, relative, shift in phases:
        s["v"] = np.zeros_like(s["v"])
        s["c"] = np.zeros(1)
        row = {}
        for k in range(33):
            if k in (4, 16, 32):
                h = hidden(xt, s)
                row[str(k)] = rates(
                    np.einsum("nbh,bh->n", h, s["v"]) + s["c"] > 0, yt, relative
                )
                archived.append(
                    ((archive(h, s["legacy"]) + s["intercepts"] > 0) == old_truth)
                    .mean(0)
                    .tolist()
                )
            if k < 32:
                # The deployed cross-layer routing is locked during head commissioning.
                bridge = s["bridge"].copy()
                update(s, x[ids[k]], y[ids[k]], 0.065, trunk_fraction=0.125)
                s["bridge"] = bridge
        row["shift"] = int(shift)
        latest.append(row)
        keepers.append((s["v"].copy(), s["c"].copy()))
    h = hidden(xt, s)
    revisit = [
        rates(np.einsum("nbh,bh->n", h, v) + c > 0, phase[2], phase[4])["accuracy"]
        for (v, c), phase in zip(keepers, phases)
    ]
    return {
        "future_rules": [list(p[0]) for p in phases],
        "phases": latest,
        "revisit": revisit,
        "legacy": archived,
        "score_drift": drift.tolist(),
    }


def score_edits(edits):
    rows = []
    runs = [[], []]
    for i, seed in enumerate(SEEDS):
        old = station(seed)
        s = dict(old)
        if edits is not None:
            s.update(
                W=edits[f"W{i}"],
                b=edits[f"b{i}"],
                legacy=edits[f"heads{i}"],
                bridge=edits[f"bridge{i}"],
            )
        rows.append(
            np.argwhere((s["W"] != old["W"]).any(2) | (s["b"] != old["b"])).tolist()
        )
        for panel in (0, 1):
            for rep in (411, 939, 1411):
                runs[panel].append(simulate(old, s, seed, panel, rep))
    return {"rows": rows, "runs": runs}


def run_editor(fn):
    artifact = {}
    for i, seed in enumerate(SEEDS):
        s = station(seed)
        x, t = probes(seed)
        w, b, h, j = fn(
            s["W"].copy(), s["b"].copy(), s["legacy"].copy(), x, t, s["bridge"].copy()
        )
        artifact.update({f"W{i}": w, f"b{i}": b, f"heads{i}": h, f"bridge{i}": j})
    return score_edits(artifact)


if __name__ == "__main__":
    from shift_reference import renew

    controls = {"untreated": score_edits(None)}
    for k in range(2):
        controls[f"informed_{k}"] = run_editor(
            lambda w, b, h, x, t, j, k=k: renew(
                w, b, h, x, t, j, RECIPES[k, SITE.index(int(t[0, 66]))]
            )
        )
    (ROOT / "data" / "inspection-controls.json").write_text(
        json.dumps(controls, separators=(",", ":")) + "\n"
    )
    for k in range(2):
        print(
            k,
            [
                reward(controls[f"informed_{k}"], target, controls)["reward"]
                for target in range(2)
            ],
        )
