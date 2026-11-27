"""Score coupled layer edits for unseen product-specific handling rules across six scanner sites."""

import json
from functools import lru_cache

import numpy as np
from clock_data import NOMINAL, ROOT, encode
from clock_data import commissioning as probes
from coupled import hidden, update
from panel_data import SEEDS, SITE, coordinates, site_of, source


def station(seed):
    with np.load(ROOT / "data" / f"net-{seed}.npz") as d:
        return dict(d)


def build_inputs(dest):
    ss = [station(seed) for seed in SEEDS]
    c = [probes(seed) for seed in SEEDS]
    np.savez(
        dest / "pairs.npz",
        W=np.stack([s["W"] for s in ss]),
        b=np.stack([s["b"] for s in ss]),
        v=np.stack([s["legacy"] for s in ss]),
        bridge=np.stack([s["bridge"] for s in ss]),
        x=np.stack([v[0] for v in c]),
        tags=np.stack([v[1] for v in c]),
    )


@lru_cache(maxsize=8)
def future_arrays(seed):
    raw, d = source.captures("test")
    r = np.random.default_rng(42551 + seed)
    train = []
    test = []
    for digit in range(5):
        ids = r.permutation(np.flatnonzero(d == digit))
        n = len(ids) // 2
        train.extend(ids[:n])
        test.extend(ids[n:])
    ret = []
    for sample in (train, test):
        pix, digit, pose = source.contents(raw, d, np.array(sample))
        ret.append(
            (
                source.turn(encode(pix, site_of(seed)), coordinates(seed)),
                digit,
                pose,
                source.measure(pix),
            )
        )
    return ret


@lru_cache(maxsize=48)
def sequence(seed, target, rep):
    original_train, original_test = future_arrays(seed)
    nominal = NOMINAL[target, site_of(seed)]

    def phases_for(batch):
        x, digit, angle, truth = batch
        return x, digit, (angle - nominal[digit]) % 4, truth

    train, test = phases_for(original_train), phases_for(original_test)
    rng = np.random.default_rng(78641 + seed + rep)
    # Three distinct binary partitions: the singleton and exclusion focus
    # on different phases; the two-bin split cannot equal either partition.
    singles = rng.choice([1, 2, 3], 2, replace=False)
    half = [(0, 1), (0, 2), (0, 3)][rng.integers(3)]
    pair = half if rng.integers(2) else tuple(sorted(set(range(4)) - set(half)))
    orders = [
        (int(singles[0]),),
        pair,
        tuple(sorted(set(range(4)) - {int(singles[1])})),
    ]
    phases = []
    for k in rng.permutation(3):
        rule = orders[k]
        y = np.isin(train[2], rule)
        yt = np.isin(test[2], rule)
        batches = [
            np.r_[rng.choice(np.flatnonzero(~y), 24), rng.choice(np.flatnonzero(y), 24)]
            for _ in range(32)
        ]
        phases.append((rule, y, yt, batches))
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

    def rates(pred, yt):
        ok = pred == yt
        return {
            "accuracy": float((ok[yt].mean() + ok[~yt].mean()) / 2),
            "weak_class": float(
                min(ok[test[2] == i].mean() for i in np.unique(test[2]))
            ),
            "weak_condition": float(
                min(ok[test[1] == i].mean() for i in np.unique(test[1]))
            ),
        }

    latest = []
    keepers = []
    for rule, y, yt, ids in phases:
        s["v"] = np.zeros_like(s["v"])
        s["c"] = np.zeros(1)
        row = {}
        for k in range(33):
            if k in (4, 16, 32):
                h = hidden(xt, s)
                row[str(k)] = rates(np.einsum("nbh,bh->n", h, s["v"]) + s["c"] > 0, yt)
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
        latest.append(row)
        keepers.append((s["v"].copy(), s["c"].copy()))
    h = hidden(xt, s)
    revisit = [
        rates(np.einsum("nbh,bh->n", h, v) + c > 0, phase[2])["accuracy"]
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


def summary(out, t, i):
    rs = out["runs"][t][3 * i : 3 * i + 3]
    vals = []
    for s in rs:
        v = []
        for p in s["phases"]:
            v.append(
                [
                    np.mean([p[str(j)]["accuracy"] for j in (4, 16)]),
                    p["32"]["weak_class"],
                    p["32"]["weak_condition"],
                ]
            )
        vals.append([*np.min(v, 0), min(s["revisit"])])
    return (
        np.mean(vals, 0),
        np.mean([s["legacy"] for s in rs], 0),
        np.max([s["score_drift"] for s in rs], 0),
    )


def reward(out, target, controls=None):
    if controls is None:
        controls = json.loads((ROOT / "data" / "inspection-controls.json").read_text())
    details = []
    for i, loc in enumerate(out["rows"]):
        base, prior, _ = summary(controls["untreated"], target, i)
        oracle, _, _ = summary(controls[f"informed_{target}"], target, i)
        actual, ret, drift = summary(out, target, i)
        effect = oracle - base
        if min(effect[0], effect[-1]) < 0.035:
            raise ValueError(
                f"Insufficient reference learning gain: {target} {i} {effect}"
            )
        measurable = effect >= 0.035
        gain = np.ones_like(effect)
        gain[measurable] = np.clip(
            (actual[measurable] - base[measurable]) / effect[measurable], 0, 1
        )
        # A weak reference contrast makes a gain ratio unstable. Preserve the
        # better control on that subgroup within the existing two-point delta.
        gain[~measurable] = (
            actual[~measurable]
            >= np.maximum(base[~measurable], oracle[~measurable]) - 0.02
        )
        loss = (prior - ret).max(0)
        eligible = bool(loc) and max(drift) <= 0.08 and max(loss) <= 0.02
        details.append(
            {
                "reward": float(gain.min()) if eligible else 0.0,
                "gains": gain.tolist(),
                "old_losses": loss.tolist(),
                "score_drift": drift.tolist(),
            }
        )
    return {"reward": float(np.mean([q["reward"] for q in details])), "pairs": details}


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
    from clock_reference import renew_clock

    controls = {"untreated": score_edits(None)}
    print("null", flush=True)
    for k in (0, 1):
        measures = run_editor(
            lambda w, b, h, x, t, j, k=k: renew_clock(
                w, b, h, x, t, j, NOMINAL[k, SITE.index(t[0, 66])]
            )
        )
        controls[f"informed_{k}"] = measures
        print(k, [v[0][0] for v in measures["rows"]], flush=True)
    (ROOT / "data" / "inspection-controls.json").write_text(
        json.dumps(controls, separators=(",", ":")) + "\n"
    )
    for k in (0, 1):
        v = reward(controls[f"informed_{k}"], k, controls)
        print(
            k,
            v["reward"],
            [max(q["old_losses"]) for q in v["pairs"]],
            [max(q["score_drift"]) for q in v["pairs"]],
            flush=True,
        )
