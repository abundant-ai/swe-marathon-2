"""Evaluate persistent product-conditioned day tooling and fiducial-conditioned night tooling."""

import numpy as np
import register_data
import source_registration as base

SITE = register_data.SITE
SEEDS = register_data.SEEDS
BANK = register_data.BANK
REGISTER = register_data.REGISTER
RECIPES = register_data.RECIPES
branch_seed = register_data.branch_seed
captures = register_data.captures
many_gallery = register_data.many_gallery
paired = register_data.paired
station = register_data.station
from deployment import hidden, update

core, archived, tests = base.core, base.archived, base.tests


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
            b, reg_digits, v, _ = captures(site, ref, phase + 1, part)
            ia, ib = paired(site, part)
            di = d[ia]
            tooling_digit = di if shift == 0 else reg_digits[ib]
            rel = (u[ia] - v[ib] - RECIPES[target, site, shift, tooling_digit]) % 4
            samples.append((a, b, ia, ib, rel, tooling_digit, np.isin(rel, rule)))
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


def score_edits(artifact):
    """Grade the installation with the reciprocal continuation on both deployments."""
    return base.score_edits(artifact, simulate)


def run_editor(fn):
    """Evaluate an editor on the three physical banks using the same continuation."""
    return base.run_editor(fn, simulate)


build_inputs = base.build_inputs
reward = base.reward
summary = base.summary
