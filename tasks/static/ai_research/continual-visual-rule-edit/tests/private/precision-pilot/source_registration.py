"""Evaluate prospective two-field registrations under interleaved learning in naturally aged banks."""

import json

import numpy as np
import register_data

ROOT = register_data.ROOT
SITE = register_data.SITE
SEEDS = register_data.SEEDS
BANK = register_data.BANK
REGISTER = register_data.REGISTER
RECIPES = register_data.RECIPES
station = register_data.station
branch_seed = register_data.branch_seed
captures = register_data.captures
many_gallery = register_data.many_gallery
paired = register_data.paired
import natural_eval

core = natural_eval.core
build_inputs = natural_eval.build_inputs
summary = natural_eval.summary
_old_reward = natural_eval.reward
from deployment import PAIR_GAIN, hidden, update


def reward(data, target, controls=None):
    """Use the unchanged five scientific contrasts, calibrated against two-field controls."""
    if controls is None:
        controls = json.loads((ROOT / "data" / "inspection-controls.json").read_text())
    base = _old_reward(data, target, controls)

    def paired_learning(value):
        gains = []
        for i in range(6):
            train = value["runs"][target][3 * i : 3 * i + 3]
            frozen = value["frozen_runs"][target][3 * i : 3 * i + 3]
            gains.append(
                float(
                    np.mean(
                        [
                            a["initial"][0] - b["initial"][0]
                            for a, b in zip(train, frozen, strict=True)
                        ]
                    )
                )
            )
        return gains

    anchor = np.mean(paired_learning(controls[f"informed_{target}"]))
    if anchor < 0.01:
        raise ValueError(f"Inadequate pooled adaptation contrast on handover {target}")
    gains = paired_learning(data)
    valid = [
        q["legacy_loss"] <= 0.02 and q["score_drift"] <= 0.08 for q in base["pairs"]
    ]
    contrast = float(np.clip(np.mean(np.array(gains) * valid) / anchor, 0, 1))
    base["acquisition_vs_own_frozen"] = {
        "mean": float(np.mean(gains)),
        "per_site": gains,
        "anchor": float(anchor),
        "normalized": contrast,
    }
    base["reward"] = min(float(base["reward"]), contrast)
    return base


def archived(s, features):
    return np.einsum("nbh,bch->nc", features, s["legacy"])


def tests(states, centers, head, bias, info):
    a, b, ia, ib, rel, d, gt = info
    va = hidden(a, states[0]).reshape(len(a), -1) - centers[0]
    vb = hidden(b, states[1]).reshape(len(b), -1) - centers[1]
    pred = (((va @ head)[ia] * vb[ib]).sum(1) * PAIR_GAIN + bias) > 0
    ok = pred == gt
    return np.array(
        [
            (ok[gt].mean() + ok[~gt].mean()) / 2,
            min(ok[rel == k].mean() for k in range(4)),
            min(ok[d == k].mean() for k in range(5)),
        ]
    )


def simulate(site, target, rep, old, new, paces, steps=192):
    """Continue one physical product/fiducial pair over four deployment orders and retest all saved heads."""
    prod, ref = int(BANK[target, site]), int(REGISTER[target, site])
    fields = (prod, ref)
    states = [{k: v.copy() for k, v in s.items()} for s in new]
    centers = []
    legacy = []
    drift = []
    baselines = []
    oldtests = []
    for f, s0, s in zip(fields, old, states):
        cal, _ = many_gallery(branch_seed(SEEDS[site], f))
        centers.append(hidden(cal, s).reshape(len(cal), -1).mean(0))
        x, _, _, metrics = captures(site, f, 0, 1)
        gt = metrics > s0["cut"]
        before = archived(s0, hidden(x, s0))
        after = archived(s, hidden(x, s))
        drift.extend(
            (
                np.sqrt(((before - after) ** 2).mean(0)) / before.std(0).clip(0.05)
            ).tolist()
        )
        baselines.extend((((before + s0["intercepts"] > 0) == gt).mean(0)).tolist())
        oldtests.append((x, gt))

    def legacy_accuracy():
        return np.concatenate(
            [
                ((archived(s, hidden(x, s)) + s["intercepts"] > 0) == gt).mean(0)
                for s, (x, gt) in zip(states, oldtests)
            ]
        ).tolist()

    legacy.append(legacy_accuracy())
    *_, phases = core.ev.sequence(SEEDS[site], target, rep)
    early = []
    saved = []
    history = []
    initial = []
    for phase, (rule, _, _, _, _, shift) in enumerate(phases):
        samples = []
        for part in (0, 1):
            a, d, u, _ = captures(site, prod, phase + 1, part)
            b, _, v, _ = captures(site, ref, phase + 1, part)
            ia, ib = paired(site, part)
            di = d[ia]
            rel = (u[ia] - v[ib] - RECIPES[target, site, shift, di]) % 4
            samples.append((a, b, ia, ib, rel, di, np.isin(rel, rule)))
        train, test = samples
        a, b, ia, ib, _, _, gt = train
        rng = np.random.default_rng(737239 + SEEDS[site] + 71 * phase + rep)
        pos = np.flatnonzero(gt)
        neg = np.flatnonzero(~gt)
        head = np.zeros((56, 56))
        bias = 0.0
        for step in range(1, steps + 1):
            ids = np.r_[rng.choice(neg, 24), rng.choice(pos, 24)]
            bias = update(
                states,
                (a[ia[ids]], b[ib[ids]]),
                centers,
                head,
                bias,
                gt[ids],
                paces,
                shift,
            )
            if step in (4, 16):
                early.append(tests(states, centers, head, bias, test))
            if step in (4, 16, 64, 128, steps):
                legacy.append(legacy_accuracy())
        saved.append((head.copy(), bias, test))
        last = [tests(states, centers, *snapshot) for snapshot in saved]
        history.append(last)
        initial.append(last[-1])
    begin = np.asarray(initial)
    end = np.asarray(history[-1])
    prev = begin[:-1, 0] - end[:-1, 0]
    worst = max(
        [0.0]
        + [
            float(begin[j, 0] - later[j][0])
            for n, later in enumerate(history)
            for j in range(n)
        ]
    )
    return {
        "early": np.mean(early, 0).tolist(),
        "initial": begin.mean(0).tolist(),
        "final": end.mean(0).tolist(),
        "peak_forgetting": worst,
        "final_mean_forgetting": float(prev.mean()),
        "initial_heads": begin[:, 0].tolist(),
        "revisit_by_phase": [[float(z[0]) for z in row] for row in history],
        "legacy": legacy,
        "old_baseline": baselines,
        "drift": drift,
    }


def score_edits(artifact, continuation=simulate):
    """Measure both possible visual handovers on one submitted installation."""
    rows = []
    installation = []
    feasibility = []
    runs = [[], []]
    frozen_runs = [[], []]
    for i, seed in enumerate(SEEDS):
        fields = []
        where = []
        install = []
        budgets = []
        for f in range(3):
            idx = 3 * i + f
            base = station(branch_seed(seed, f))
            s = base.copy()
            pace = np.ones((2, 2, 28))
            if artifact is not None:
                s.update(
                    W=artifact[f"W{idx}"],
                    b=artifact[f"b{idx}"],
                    legacy=artifact[f"heads{idx}"],
                    bridge=artifact[f"bridge{idx}"],
                )
                pace = artifact[f"pace{idx}"]
            fields.append((base, s, pace))
            changed = (base["W"] != s["W"]).any(2) | (base["b"] != s["b"])
            where.append(np.argwhere(changed).tolist())
            head_columns = (base["legacy"] != s["legacy"]).any(1)
            head_columns[0] |= (base["bridge"] != s["bridge"])[~changed[1]].any(0)
            budgets.append(
                {"incoming": int(changed.sum()), "outgoing": int(head_columns.sum())}
            )
            x, _, _, raw = captures(i, f, 0, 1)
            gt = raw > base["cut"]
            before = archived(base, hidden(x, base))
            after = archived(s, hidden(x, s))
            old = ((before + base["intercepts"] > 0) == gt).mean(0)
            new = ((after + s["intercepts"] > 0) == gt).mean(0)
            drift = np.sqrt(((before - after) ** 2).mean(0)) / before.std(0).clip(0.05)
            install.append({"loss": float(max(old - new)), "drift": float(max(drift))})
        rows.append(where)
        installation.append(install)
        opened = [
            j
            for j, usage in enumerate(budgets)
            if usage["incoming"] or usage["outgoing"]
        ]
        total_rows = sum(v["incoming"] for v in budgets)
        total_columns = sum(v["outgoing"] for v in budgets)
        feasibility.append(
            {
                "opened_fields": opened,
                "modules_opened": len(opened),
                "incoming": total_rows,
                "outgoing": total_columns,
                "per_field": budgets,
                "within_station_budget": len(opened) <= 2
                and total_rows <= 9
                and total_columns <= 18,
            }
        )
        for target in (0, 1):
            old, new, rates = zip(
                *(fields[f] for f in (BANK[target, i], REGISTER[target, i]))
            )
            zeros = [np.zeros_like(r) for r in rates]
            for rep in (411, 939, 1411):
                actual = continuation(i, target, rep, old, new, rates)
                runs[target].append(actual)
                counter = (
                    continuation(i, target, rep, old, new, zeros)
                    if any(np.any(r) for r in rates)
                    else actual
                )
                frozen_runs[target].append(counter)
    return {
        "rows": rows,
        "installation": installation,
        "station_feasibility": feasibility,
        "runs": runs,
        "frozen_runs": frozen_runs,
    }


def run_editor(fn, continuation=simulate):
    """Apply candidate-shaped numeric control calls to all physical banks before either target is known."""
    art = {}
    for i, seed in enumerate(SEEDS):
        for f in range(3):
            idx = 3 * i + f
            s = station(branch_seed(seed, f))
            x, t = many_gallery(branch_seed(seed, f))
            value = fn(
                s["W"].copy(),
                s["b"].copy(),
                s["legacy"].copy(),
                x,
                t,
                s["bridge"].copy(),
            )
            art.update(
                {
                    f"{k}{idx}": v
                    for k, v in zip(("W", "b", "heads", "bridge", "pace"), value)
                }
            )
    return score_edits(art, continuation)
