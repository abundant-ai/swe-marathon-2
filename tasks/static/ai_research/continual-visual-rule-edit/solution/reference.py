from itertools import combinations

import numpy as np


def recognize_ink(tags: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Infer digit and pose of every ordinary-feeder capture in a public gallery.

    Args:
        tags: Original 8×8 pixel values, digit labels and quarter turns. The
            twenty technician-verified rows train the classifier.

    Returns:
        Inferred product indices and quarter turns for the whole gallery, with
        the verified labels preserved. This is the template and neighborhood
        estimator used by the earlier independent changeover control.
    """
    ink = tags[:, :64].astype(float)
    known = tags[:, 64] != 255
    prototypes = ink[known].reshape(-1, 8, 8)
    products = np.searchsorted([1, 2, 4, 5, 7], tags[known, 64])
    poses = tags[known, 65]
    bank = np.concatenate(
        [np.rot90(prototypes, k, axes=(1, 2)) for k in range(4)]
    ).reshape(-1, 64)
    joint = np.concatenate([4 * products + (poses + k) % 4 for k in range(4)])
    log_likelihood = -np.abs(ink[:, None] - bank[None]).mean(2) / 0.56
    likelihood = (
        np.exp(log_likelihood - log_likelihood.max(1, keepdims=True))
        @ np.eye(20)[joint]
    )
    probability = likelihood / likelihood.sum(1, keepdims=True)
    distance = np.abs(ink[:, None] / 16 - ink[None] / 16).mean(2)
    np.fill_diagonal(distance, np.inf)
    neighbors = np.argsort(distance, axis=1)[:, :4]
    weight = np.exp(-np.take_along_axis(distance, neighbors, 1) / 0.025)
    weight /= weight.sum(1, keepdims=True)
    predicted = (
        0.8 * probability + 0.2 * (weight[:, :, None] * probability[neighbors]).sum(1)
    ).argmax(1)
    predicted[known] = 4 * products + poses
    return predicted // 4, predicted % 4


def harmonics(poses):
    """Represent the four quarter turns with the three real nonconstant Fourier modes."""
    phases = np.asarray(poses) % 4
    return np.column_stack(
        (
            np.array([1.0, 0, -1, 0])[phases],
            np.array([0.0, 1.0, 0, -1])[phases],
            np.array([1.0, -1, 1, -1])[phases],
        )
    )


def release(activations, outgoing, importance, count, residual):
    """Replace a small group and use equally many surviving columns to match its emissions."""
    n = len(activations)
    gram = activations.T @ activations / n
    diagonal = gram.diagonal().clip(1e-10)
    nominal = np.sum((outgoing * importance[:, None]) ** 2, axis=0)
    similarity = gram**2 / (diagonal[:, None] * diagonal[None])
    np.fill_diagonal(similarity, 0)
    shortlist = np.argsort(diagonal * nominal * (1 - similarity.max(axis=0)))[:12]
    cross = activations.T @ residual / n
    best = None
    for proposed in combinations(shortlist, count):
        freed = np.array(proposed)
        emissions = outgoing[:, freed].T
        moment = cross + gram[:, freed] @ emissions
        energy = (
            emissions * (gram[np.ix_(freed, freed)] @ emissions + 2 * cross[freed])
        ).sum(axis=0)
        remaining = moment
        variance = diagonal
        kept = []
        for _ in range(count):
            quality = ((remaining * importance) ** 2).sum(axis=1) / variance.clip(1e-9)
            quality[freed] = -np.inf
            quality[kept] = -np.inf
            kept.append(int(quality.argmax()))
            selected = gram[:, kept]
            inverse = np.linalg.inv(
                gram[np.ix_(kept, kept)] + np.diag(diagonal[kept] * 1e-5)
            )
            adjustment = inverse @ moment[kept]
            remaining = moment - selected @ adjustment
            variance = diagonal - ((selected @ inverse) * selected).sum(1)
        loss = float(
            ((energy - (adjustment * moment[kept]).sum(0)) * importance**2).sum()
        )
        if best is None or loss < best[0]:
            best = (loss, freed, kept, adjustment)
    return best[1:]


def fit_features(x, tags, role, rules, existing, early_budget, late_budget):
    """Distill two circular codes into a small shared ReLU layer with fixed existing features."""
    n = len(x)
    specimen = tags[:, 68].astype(int)
    digit, absolute = recognize_ink(tags[tags[:, 67] == 0])
    d, angle = digit[specimen], absolute[specimen]
    relative = (
        (angle - rules[0, d]) % 4 if role == "product" else (angle + rules[1, d]) % 4
    )
    target = np.column_stack((harmonics(angle), harmonics(relative)))
    # A centered readout can use both taps. Fit its residual directions against both shifts.
    target -= target.mean(0)
    cov = existing - existing.mean(0)
    cov = cov / np.maximum(0.35, cov.std(0))
    residual = target - 0.65 * cov @ np.linalg.solve(
        cov.T @ cov + n * 0.30 * np.eye(cov.shape[1]), cov.T @ target
    )
    designs = []
    for tap in range(2):
        raw = x[:, tap]
        mu = raw.mean(0)
        sd = np.maximum(raw.std(0), 0.20)
        design = (raw - mu) / sd
        designs.append((design, mu, sd))
    rng = np.random.default_rng(1097)
    coeff = []
    bias = []
    heads = []
    for tap, k in enumerate((early_budget, late_budget)):
        X, _, _ = designs[tap]
        coefficient = np.linalg.solve(
            X.T @ X + n * 0.025 * np.eye(X.shape[1]), X.T @ residual
        )
        # Deflate directions learned at the earlier tap before fitting the second tap.
        _, _, right = np.linalg.svd(X @ coefficient, full_matrices=False)
        filters = coefficient @ right[:k].T
        scale = (X @ filters).std(0).clip(0.05)
        filters = filters / scale
        intercept = np.full(k, 0.85)
        phi = np.maximum(0, X @ filters + intercept)
        centered = phi - phi.mean(0)
        decoding = np.linalg.solve(
            centered.T @ centered + 0.01 * n * np.eye(k), centered.T @ residual
        )
        residual -= 0.8 * centered @ decoding
        coeff.append(filters)
        bias.append(intercept)
        heads.append(decoding)
    # Keep a ridge penalty on frozen channels so the compressed features retain readable signal.
    weights = np.vstack(heads)
    z = [np.maximum(0, designs[t][0] @ coeff[t] + bias[t]) for t in range(2)]
    concat = np.column_stack(z)
    hidden_mean = concat.mean(0)
    offset = target.mean(0) - hidden_mean @ weights
    frozen_readout = np.zeros((cov.shape[1], target.shape[1]))
    moments = {}

    def update(name, parameter, gradient, step, rate):
        first, second = moments.setdefault(
            name, (np.zeros_like(parameter), np.zeros_like(parameter))
        )
        first[:] = 0.9 * first + 0.1 * gradient
        second[:] = 0.99 * second + 0.01 * gradient**2
        parameter -= (
            rate
            * (first / (1 - 0.9**step))
            / (np.sqrt(second / (1 - 0.99**step)) + 1e-8)
        )

    for step in range(1, 181):
        idx = rng.choice(n, 128, replace=True)
        X = [designs[t][0][idx] for t in range(2)]
        z = [np.maximum(0, X[t] @ coeff[t] + bias[t]) for t in range(2)]
        phi = np.column_stack(z)
        err = (phi @ weights + cov[idx] @ frozen_readout + offset - target[idx]) / len(
            idx
        )
        grad = err @ weights.T
        for tap, (start, k) in enumerate(
            ((0, early_budget), (early_budget, late_budget))
        ):
            signal = (z[tap] > 0) * grad[:, start : start + k]
            update(
                ("filter", tap),
                coeff[tap],
                X[tap].T @ signal + 0.008 * coeff[tap],
                step,
                0.006,
            )
            update(("bias", tap), bias[tap], signal.sum(0), step, 0.005)
        update("out", weights, phi.T @ err + 0.012 * weights, step, 0.009)
        update(
            "old", frozen_readout, cov[idx].T @ err + 0.25 * frozen_readout, step, 0.008
        )
        update("offset", offset, err.sum(0), step, 0.008)
    result = []
    for tap in (0, 1):
        X, mu, sd = designs[tap]
        pos = X @ coeff[tap] + bias[tap]
        scale = 2.8 / np.maximum(0.35, np.maximum(0, pos).std(0))
        slope = coeff[tap] / sd[:, None]
        result.append((slope * scale, (bias[tap] - mu @ slope) * scale))
    return result


def renew(w, b, heads, x, tags, bridge, role, rules):
    """Install a compressed joint code while preserving both archived stage contributions."""
    w, b, heads, bridge = (v.copy() for v in (w, b, heads, bridge))
    early = np.maximum(0, x[:, 0] @ w[0].T + b[0])
    late = np.maximum(0, x[:, 1] @ w[1].T + b[1] + early @ bridge.T)
    archived = early @ heads[0].T + late @ heads[1].T
    weights = 1 / archived.std(0).clip(0.05)
    counts = (2, 3) if role == "product" else (2, 2)
    corrections = fit_features(
        x, tags, role, np.asarray(rules), np.c_[early, late], *counts
    )
    rates = np.zeros((2, 2, w.shape[1]))
    survivors = []
    for tap, count in enumerate(counts):
        early = np.maximum(0, x[:, 0] @ w[0].T + b[0])
        late = np.maximum(0, x[:, 1] @ w[1].T + b[1] + early @ bridge.T)
        if tap == 0:
            outgoing = np.vstack((heads[0], bridge))
            magnitude = np.linalg.norm(heads[1] * weights[:, None], axis=0)
            scale = np.r_[weights, 0.5 * magnitude]
            residual = np.zeros((len(x), len(outgoing)))
        else:
            outgoing = heads[1]
            scale = weights
            residual = archived - early @ heads[0].T - late @ heads[1].T
        freed, kept, adjust = release(
            (early, late)[tap], outgoing, scale, count, residual
        )
        slope, intercept = corrections[tap]
        w[tap, freed] = slope.T
        b[tap, freed] = intercept
        heads[tap][:, freed] = 0
        heads[tap][:, kept] += adjust[:, : heads.shape[1]].T
        if tap == 0:
            bridge[:, freed] = 0
            bridge[:, kept] += adjust[:, heads.shape[1] :].T
        else:
            bridge[freed] = 0
        survivors.extend([(tap, k) for k in kept])
        rates[:, tap, freed] = 0.50
    early = np.maximum(0, x[:, 0] @ w[0].T + b[0])
    late = np.maximum(0, x[:, 1] @ w[1].T + b[1] + early @ bridge.T)
    residual = archived - early @ heads[0].T - late @ heads[1].T
    sample_weight = np.where(tags[:, 67] == 0, 2.0, 0.5)
    basis = np.column_stack([(early, late)[t][:, k] for t, k in survivors])
    gram = basis.T @ (sample_weight[:, None] * basis)
    correction = np.linalg.solve(
        gram + np.diag(np.diag(gram) * 0.0005 + 1e-9),
        basis.T @ (sample_weight[:, None] * residual),
    )
    for row, (tap, index) in zip(correction, survivors, strict=True):
        heads[tap, :, index] += row
    return w, b, heads, bridge, rates


HANDOVER = {}


def edit(W, b, old_readout, patches, tags, bridge):
    """Choose the field role from the decoded receipt for this physical station."""
    station = int(tags[0, 66])
    field = int(tags[0, 69])
    product, registration, rules = HANDOVER[station]
    if field not in (product, registration):
        return W, b, old_readout, bridge, np.ones((2, 2, W.shape[1]))
    role = "product" if field == product else "register"
    return renew(W, b, old_readout, patches, tags, bridge, role, rules)
