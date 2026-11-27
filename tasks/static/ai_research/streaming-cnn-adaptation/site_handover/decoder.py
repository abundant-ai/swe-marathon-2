"""Recover the site and optical response from a handheld view of a printed reference chart."""

import numpy as np


def decode(
    rgb: np.ndarray, cards: np.ndarray, nominal: np.ndarray
) -> tuple[int, int, np.ndarray] | None:
    """Return the best station, sensor family and fitted inverse for a credible chart exposure.

    The decoder first checks within-patch uniformity. A true change requires a full
    camera-consistent arrangement of swatches. A trimmed residual tolerates the
    covered square and excludes normal inventory images.
    """
    if len(cards) != 2:
        return None
    best = None
    for y in range(1, 8):
        for x in range(1, 8):
            pixels = rgb[y : y + 24, x : x + 24].reshape(6, 4, 6, 4, 3).astype(float)
            # True camera photographs of a chart have flat patch interiors.
            dispersion = pixels.std(axis=(1, 3)).mean(2)
            if np.median(dispersion) > 4.0:
                continue
            observed = pixels.mean(axis=(1, 3)).reshape(36, 3)
            for station, c in enumerate(cards):
                for turn in range(4):
                    raw = np.rot90(c, turn).reshape(36, 3).astype(float)
                    for mode, m in enumerate(nominal):
                        residual = np.abs(observed - raw @ m.T).mean(1)
                        distance = float(np.sort(residual)[:30].mean())
                        if best is None or distance < best[0]:
                            best = (distance, raw, observed, station, mode)
    if best is None or best[0] > 26:
        return None
    _, raw, observed, station, mode = best
    mask = np.ones(len(raw), dtype=bool)
    for _ in range(3):
        transform = np.linalg.lstsq(raw[mask], observed[mask], rcond=None)[0].T
        residual = np.abs(raw @ transform.T - observed).mean(1)
        mask = residual <= np.quantile(residual, 0.89)
    if residual[mask].mean() > 3 or np.linalg.cond(transform) > 12:
        return None
    return station, mode, np.linalg.inv(transform)
