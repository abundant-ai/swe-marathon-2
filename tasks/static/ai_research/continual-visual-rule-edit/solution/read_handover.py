"""Infer reciprocal shift rules from accepted and rejected handwritten forms."""

from itertools import permutations, product

import numpy as np
from PIL import Image


def template_scores(images, tags):
    labeled = tags[:, 64] != 255
    prototypes = tags[labeled, :64].reshape(-1, 8, 8).astype(float)
    glyphs = np.searchsorted(np.array([1, 2, 4, 5, 7]), tags[labeled, 64])
    poses = tags[labeled, 65]
    bank = np.concatenate(
        [np.rot90(prototypes, k, axes=(1, 2)) for k in range(4)]
    ).reshape(-1, 64)
    joints = np.concatenate([4 * glyphs + (poses + k) % 4 for k in range(4)])
    # A Laplace kernel limits the influence of an individual long pen stroke.
    distance = np.abs(
        np.asarray(images).reshape(-1, 64)[:, None, :] - bank[None, :, :]
    ).mean(2)
    logits = -distance / 0.56
    likelihood = np.exp(logits - logits.max(1, keepdims=True)) @ np.eye(20)[joints]
    return likelihood / likelihood.sum(1, keepdims=True)


def box(site: int, group: int, card: int, field: int) -> tuple[int, int, int, int]:
    """Return a fixed ink rectangle for one independently scored field on a form."""
    left = 124 + 121 * card + 37 * field
    top = site * 163 + 25 + 44 * group
    return left, top, left + 32, top + 32


RECIPES = np.array(list(product(range(4), repeat=5)), dtype=np.int8)
CHOICES = np.eye(4)[RECIPES]


def joint_orientations(
    product_prob: np.ndarray, register_prob: np.ndarray
) -> np.ndarray:
    """Joint probability of both digit identities and product-minus-registration pose."""
    return np.stack(
        [
            np.einsum(
                "npt,nrt->npr", product_prob, np.roll(register_prob, offset, axis=2)
            )
            for offset in range(4)
        ],
        axis=-1,
    )


def best_rules(joint: np.ndarray, queue: np.ndarray) -> tuple[float, np.ndarray]:
    """Maximize the exclusive-queue likelihood over both five-entry shift recipes.

    Day is indexed by product identity and night by registration identity. A
    form satisfies both rules only when their nominal turns agree. The score
    of either binary release decision bounds the joint score from above,
    which prunes exact enumeration without assuming one example per digit.
    """
    day_mask = queue == 0
    night_mask = queue == 1
    day_prob = np.einsum("npt,mpt->nm", joint.sum(axis=2), CHOICES, optimize=True)
    night_prob = np.einsum("nrt,mrt->nm", joint.sum(axis=1), CHOICES, optimize=True)
    day_upper = np.log(
        np.where(day_mask[:, None], day_prob, 1 - day_prob).clip(1e-12, 1)
    ).sum(0)
    night_upper = np.log(
        np.where(night_mask[:, None], night_prob, 1 - night_prob).clip(1e-12, 1)
    ).sum(0)
    by_day = np.argsort(-day_upper, kind="stable")
    by_night = np.argsort(-night_upper, kind="stable")
    best = -np.inf
    best_pair = None
    for day in by_day:
        if day_upper[day] < best - 1e-9:
            break
        nights = by_night[night_upper[by_night] >= best - 1e-9]
        if not len(nights):
            break
        same = np.einsum("nprk,pk->nrk", joint, CHOICES[day])
        both = np.einsum("nrk,mrk->nm", same, CHOICES[nights], optimize=True)
        d = day_prob[:, day, None]
        n = night_prob[:, nights]
        likelihood = np.where(
            day_mask[:, None],
            d - both,
            np.where(night_mask[:, None], n - both, 1 - d - n + both),
        )
        scores = np.log(likelihood.clip(1e-12, 1)).sum(0)
        index = int(np.argmax(scores))
        if scores[index] > best:
            best = float(scores[index])
            best_pair = (int(day), int(nights[index]))
    return best / len(queue), RECIPES[list(best_pair)]


def apply_release_counts(
    probability: np.ndarray, selected: np.ndarray
) -> tuple[np.ndarray, float]:
    """Condition the five release cards on one occurrence of each tooling digit."""
    digit = probability[selected].sum(axis=2)
    assignments = np.array(list(permutations(range(5))))
    likelihood = np.prod(digit[np.arange(5), assignments], axis=1)
    evidence = likelihood.sum()
    if evidence <= 0:
        raise ValueError("No supported digit assignment for the five release cards")
    marginal = np.einsum("a,acd->cd", likelihood / evidence, np.eye(5)[assignments])
    conditioned = probability.copy()
    conditioned[selected] *= (marginal / digit.clip(1e-15))[:, :, None]
    return conditioned, float(np.log(evidence))


def read(path, tags):
    """Return ordered scanner fields, day/night relative turns and alternative-pair margins."""
    image = Image.open(path).convert("L")
    queue = np.repeat((0, 1, 2), (5, 5, 10))
    fields, recipes, margins = [], [], []
    for site in range(6):
        probabilities = []
        for field in range(3):
            inks = [
                (
                    255
                    - np.asarray(
                        image.crop(box(site, group, form, field)).resize(
                            (8, 8), Image.Resampling.NEAREST
                        ),
                        float,
                    )
                )
                * 16
                / 255
                for group, size in enumerate((5, 5, 10))
                for form in range(size)
            ]
            probabilities.append(template_scores(inks, tags).reshape(20, 5, 4))
        options = []
        for p, r in permutations(range(3), 2):
            day, day_evidence = apply_release_counts(probabilities[p], queue == 0)
            night, night_evidence = apply_release_counts(probabilities[r], queue == 1)
            score, rules = best_rules(joint_orientations(day, night), queue)
            score += (day_evidence + night_evidence) / len(queue)
            options.append((score, (p, r), rules))
        options.sort(key=lambda row: row[0], reverse=True)
        score, pair, rules = options[0]
        fields.append(pair)
        recipes.append(rules)
        margins.append(score - options[1][0])
    return np.asarray(fields), np.asarray(recipes), margins
