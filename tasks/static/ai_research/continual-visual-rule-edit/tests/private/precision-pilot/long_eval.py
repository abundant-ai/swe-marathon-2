"""Measure adaptation, earlier-head degradation and archived-score retention under feeder drift."""

import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import numpy as np
from coupled import hidden, update
from long_data import (
    BANK,
    RECIPES,
    ROOT,
    SEEDS,
    SITE,
    arrays,
    branch_seed,
    many_gallery,
    origin,
    station,
)
from panel_data import site_of

shared = (
    ROOT / "shift_eval.py"
    if (ROOT / "shift_eval.py").exists()
    else ROOT.parent / "changeover" / "shift_eval.py"
)
spec = spec_from_file_location("alternating_scanner", shared)
ev = module_from_spec(spec)
spec.loader.exec_module(ev)


def simulate(
    old: dict, new: dict, seed: int, target: int, rep: int, rates_installed: np.ndarray
) -> dict:
    """Run four full-length supervised phases on one persistent trunk and revisit each saved head.

    Earlier heads are evaluated on the acquisition domain on which they were
    commissioned, including after every subsequent phase. Archived inspections
    use the pre-handover held-out domain at each verification checkpoint.
    """
    steps = 192
    s = {k: v.copy() for k, v in new.items()}
    *_, phases = ev.sequence(origin(seed), target, rep)
    clean_test = arrays(seed, 0)[1]
    h = hidden(clean_test[0], old)
    old_truth = clean_test[3] > old["cut"]
    archive = lambda ft, heads: np.einsum("nbh,bch->nc", ft, heads)
    wanted = archive(h, old["legacy"])
    base_pred = (wanted + old["intercepts"] > 0) == old_truth
    got = archive(hidden(clean_test[0], s), s["legacy"])
    drift = np.sqrt(((got - wanted) ** 2).mean(0)) / wanted.std(0).clip(0.05, None)

    def rates(state, v, c, info):
        x, d, relative, y = info
        pred = np.einsum("nbh,bh->n", hidden(x, state), v) + c > 0
        ok = pred == y
        return np.array(
            [
                (ok[y].mean() + ok[~y].mean()) / 2,
                min(ok[relative == k].mean() for k in range(4)),
                min(ok[d == k].mean() for k in range(5)),
            ]
        )

    heads = []
    initial = []
    curves = []
    keepers = []
    early = []
    legacy = [((got + s["intercepts"] > 0) == old_truth).mean(0)]
    for n, (rule, _, _, _, _, shift) in enumerate(phases):
        domain = n + 1
        tr, te = arrays(seed, domain)
        nominal = RECIPES[target, site_of(origin(seed)), shift]
        yt = np.isin((tr[2] - nominal[tr[1]]) % 4, rule)
        rel = (te[2] - nominal[te[1]]) % 4
        info = (te[0], te[1], rel, np.isin(rel, rule))
        keepers.append(info)
        r = np.random.default_rng(75800 + seed + n * 70 + rep)
        s["v"] = np.zeros_like(s["v"])
        s["c"] = np.zeros(1)
        for step in range(1, steps + 1):
            idx = np.r_[
                r.choice(np.flatnonzero(~yt), 24), r.choice(np.flatnonzero(yt), 24)
            ]
            bridge = s["bridge"].copy()
            before = s["W"].copy()
            bias = s["b"].copy()
            update(s, tr[0][idx], yt[idx], 0.065, trunk_fraction=1.0)
            pace = rates_installed[shift]
            s["W"] = before + pace[:, :, None] * (s["W"] - before)
            s["b"] = bias + pace * (s["b"] - bias)
            s["bridge"] = bridge
            if step in (4, 16):
                early.append(rates(s, s["v"], s["c"], info))
            if step in (4, 16, 64, 128, 192):
                scores = (
                    archive(hidden(clean_test[0], s), s["legacy"]) + s["intercepts"]
                )
                legacy.append(((scores > 0) == old_truth).mean(0))
        heads.append((s["v"].copy(), s["c"].copy()))
        tested = [rates(s, *head, tst) for head, tst in zip(heads, keepers)]
        curves.append(tested)
        initial.append(tested[-1])

    init = np.asarray(initial)
    fin = np.asarray(curves[-1])
    previous = init[:-1, 0] - fin[:-1, 0]
    peak = max(
        [0.0]
        + [
            float(init[j, 0] - later[j][0])
            for n, later in enumerate(curves)
            for j in range(n)
        ]
    )
    return {
        "early": np.mean(early, 0).tolist(),
        "initial": init.mean(0).tolist(),
        "final": fin.mean(0).tolist(),
        "peak_forgetting": peak,
        "final_mean_forgetting": float(previous.mean()),
        "initial_heads": init[:, 0].tolist(),
        "revisit_by_phase": [[float(v[0]) for v in q] for q in curves],
        "legacy": np.asarray(legacy).tolist(),
        "old_baseline": base_pred.mean(0).tolist(),
        "drift": drift.tolist(),
    }


def build_inputs(dest: Path) -> None:
    """Write candidate-visible checkpoints and paired commissioning scans for all six sites."""
    branches = [branch_seed(seed, k) for seed in SEEDS for k in range(3)]
    ss = [station(seed) for seed in branches]
    g = [many_gallery(seed) for seed in branches]
    np.savez(
        dest / "pairs.npz",
        W=np.stack([s["W"] for s in ss]),
        b=np.stack([s["b"] for s in ss]),
        v=np.stack([s["legacy"] for s in ss]),
        bridge=np.stack([s["bridge"] for s in ss]),
        x=np.stack([m[0] for m in g]),
        tags=np.stack([m[1] for m in g]),
        pace=np.ones((len(branches), 2, 2, 28)),
    )


def score_edits(edits: dict | None) -> dict:
    """Replay each transferred installation under both possible visual targets."""
    rows = []
    runs = [[], []]
    installation = []
    for i, seed in enumerate(SEEDS):
        fields = []
        site_rows = []
        site_install = []
        for field in range(3):
            index = 3 * i + field
            bank_seed = branch_seed(seed, field)
            old = station(bank_seed)
            new = old.copy()
            pace = np.ones((2, 2, 28))
            if edits is not None:
                new.update(
                    W=edits[f"W{index}"],
                    b=edits[f"b{index}"],
                    legacy=edits[f"heads{index}"],
                    bridge=edits[f"bridge{index}"],
                )
                pace = edits[f"pace{index}"]
            fields.append((old, new, bank_seed, pace))
            site_rows.append(
                np.argwhere(
                    (new["W"] != old["W"]).any(2) | (new["b"] != old["b"])
                ).tolist()
            )
            held = arrays(bank_seed, 0)[1]
            archive = lambda state, held=held: np.einsum(
                "nbh,bch->nc", hidden(held[0], state), state["legacy"]
            )
            before = archive(old)
            after = archive(new)
            truth = held[3] > old["cut"]
            acc0 = ((before + old["intercepts"] > 0) == truth).mean(0)
            acc1 = ((after + old["intercepts"] > 0) == truth).mean(0)
            drift = np.sqrt(((after - before) ** 2).mean(0)) / before.std(0).clip(
                0.05, None
            )
            site_install.append(
                {"loss": float((acc0 - acc1).max()), "drift": float(drift.max())}
            )
        rows.append(site_rows)
        installation.append(site_install)
        for target in (0, 1):
            old, new, bank_seed, pace = fields[BANK[target, i]]
            for rep in (411, 939, 1411):
                runs[target].append(simulate(old, new, bank_seed, target, rep, pace))
    return {"rows": rows, "runs": runs, "installation": installation}


def run_editor(fn) -> dict:
    """Apply a control to all eighteen public-shaped field checkpoints before any target is scored."""
    artifact = {}
    for i, station_seed in enumerate(SEEDS):
        for field in range(3):
            index = 3 * i + field
            seed = branch_seed(station_seed, field)
            s = station(seed)
            x, t = many_gallery(seed)
            w, b, h, j, pace = fn(
                s["W"].copy(),
                s["b"].copy(),
                s["legacy"].copy(),
                x,
                t,
                s["bridge"].copy(),
            )
            artifact.update(
                {
                    f"W{index}": w,
                    f"b{index}": b,
                    f"heads{index}": h,
                    f"bridge{index}": j,
                    f"pace{index}": pace,
                }
            )
    return score_edits(artifact)


def summary(data: dict, target: int, site: int) -> tuple[np.ndarray, float, float]:
    """Aggregate absolute acquisition, durable learning, subgroup performance, and peak loss."""
    runs = data["runs"][target][3 * site : 3 * site + 3]
    metrics = np.mean(
        [
            [
                v["early"][0],
                v["initial"][0],
                v["final"][0],
                min(v["final"][1:]),
                -v["peak_forgetting"],
            ]
            for v in runs
        ],
        axis=0,
    )
    legacy_loss = max(
        float(np.max(np.array(v["old_baseline"]) - v["legacy"])) for v in runs
    )
    drift = max(max(v["drift"]) for v in runs)
    legacy_loss = max(legacy_loss, max(v["loss"] for v in data["installation"][site]))
    drift = max(drift, max(v["drift"] for v in data["installation"][site]))
    return metrics, legacy_loss, drift


def reward(out: dict, target: int, controls: dict | None = None) -> dict:
    """Compare acquisition to frozen informed features and forgetting to untreated full SGD.

    Site rewards also require at most two points
    absolute accuracy loss on each archived quality decision at every checkpoint,
    and installation score drift within 8% of the original standard deviation.
    """
    if controls is None:
        controls = json.loads((ROOT / "data" / "inspection-controls.json").read_text())
    details = []
    for i, locations in enumerate(out["rows"]):
        base = summary(controls["untreated"], target, i)[0]
        frozen = summary(controls[f"frozen_{target}"], target, i)[0]
        informed = summary(controls[f"informed_{target}"], target, i)[0]
        base[1] = frozen[1]
        actual, loss, drift = summary(out, target, i)
        effect = informed - base
        identifiable = effect >= 0.035
        if effect[0] < 0.035:
            raise ValueError(f"No early-learning contrast at {target}/{i}")
        gains = np.ones(5)
        gains[identifiable] = np.clip(
            (actual[identifiable] - base[identifiable]) / effect[identifiable], 0, 1
        )
        gains[~identifiable] = (
            actual[~identifiable]
            >= np.maximum(informed[~identifiable], base[~identifiable]) - 0.02
        )
        eligible = loss <= 0.02 and drift <= 0.08
        details.append(
            {
                "reward": float(gains.min()) if eligible else 0.0,
                "gains": gains.tolist(),
                "metrics": actual.tolist(),
                "legacy_loss": loss,
                "score_drift": drift,
            }
        )
    return {"reward": float(np.mean([v["reward"] for v in details])), "pairs": details}


if __name__ == "__main__":
    from time import monotonic

    from long_reference import install

    start = monotonic()
    controls = {"untreated": score_edits(None)}
    print("untreated", round(monotonic() - start, 1), flush=True)
    for k in (0, 1):

        def informed(w, b, h, x, t, j, *, k=k):
            site = SITE.index(int(t[0, 66]))
            if int(t[0, 69]) != BANK[k, site]:
                return w, b, h, j, np.ones((2, 2, 28))
            return install(w, b, h, x, t, j, RECIPES[k, site])

        def frozen(w, b, h, x, t, j):
            *initial, pace = informed(w, b, h, x, t, j)
            return (*initial, np.zeros_like(pace))

        for name, fn in (("informed", informed), ("frozen", frozen)):
            controls[f"{name}_{k}"] = run_editor(fn)
            print(name, k, round(monotonic() - start, 1), flush=True)
    (ROOT / "data" / "inspection-controls.json").write_text(
        json.dumps(controls, separators=(",", ":")) + "\n"
    )
    for k in (0, 1):
        print(
            k,
            [
                (
                    name,
                    [
                        reward(controls[f"{name}_{k}"], t, controls)["reward"]
                        for t in (0, 1)
                    ],
                )
                for name in ("informed", "frozen")
            ],
        )
