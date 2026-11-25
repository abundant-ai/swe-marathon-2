"""Independent square-root batch truth for a frozen stream of linear observations."""

from typing import Any

import numpy as np

Json = dict[str, Any]


def posterior(config: Json, watermark: int, observations: list[Json]) -> Json:
    """Solve the entire accepted history as weighted least squares and slice recent marginals."""
    start = config["start_tick"]
    variables = 2 * (watermark - start + 1)
    rows: list[np.ndarray] = []
    values: list[np.ndarray] = []

    def append(
        block: int, design: np.ndarray, value: object, uncertainty: object
    ) -> None:
        """Append covariance-whitened equations at the appropriate variable columns."""
        cholesky = np.linalg.cholesky(uncertainty)
        left = np.zeros((len(design), variables))
        left[:, block : block + design.shape[1]] = design
        rows.append(np.linalg.solve(cholesky, left))
        values.append(np.linalg.solve(cholesky, value))

    identity = np.eye(2)
    transition = np.column_stack((-identity, identity))
    append(0, identity, config["prior_mean"], config["prior_covariance"])
    for offset in range(0, variables - 2, 2):
        append(offset, transition, [0.0, 0.0], config["process_covariance"])
    for factor in observations:
        offset = 2 * (factor["tick"] - start)
        if factor["op"] == "delta":
            append(offset - 2, transition, factor["value"], factor["covariance"])
        elif factor["op"] == "position":
            append(offset, identity, factor["value"], factor["covariance"])
        else:
            append(
                offset,
                np.array([factor["axis"]]),
                [factor["value"]],
                [[factor["variance"]]],
            )
    Q, R = np.linalg.qr(np.vstack(rows), mode="reduced")
    estimate = np.linalg.solve(R, Q.T @ np.concatenate(values))
    inverse = np.linalg.solve(R, np.eye(variables))
    first = max(start, watermark - config["lag_ticks"])
    result = []
    for tick in range(first, watermark + 1):
        offset = 2 * (tick - start)
        pair = slice(offset, offset + 2)
        result.append(
            {
                "tick": tick,
                "mean": estimate[pair],
                "covariance": inverse[pair] @ inverse[pair].T,
            }
        )
    return {"watermark": watermark, "states": result}


def near(value: object, expected: object, tolerance: float = 2e-7) -> bool:
    """Match shapes and finite numeric values without accepting strings or booleans."""
    try:
        raw = np.asarray(value)
        wanted = np.asarray(expected)
        return (
            raw.dtype.kind in "fiu"
            and raw.shape == wanted.shape
            and bool(np.allclose(raw, wanted, atol=tolerance, rtol=tolerance))
        )
    except (TypeError, ValueError, OverflowError):
        return False


def matches(actual: object, expected: Json) -> bool:
    """Compare every state tick, mean and covariance in a retained window."""
    if not isinstance(actual, dict) or type(actual.get("watermark")) is not int:
        return False
    if actual["watermark"] != expected["watermark"]:
        return False
    states = actual.get("states")
    if not isinstance(states, list) or len(states) != len(expected["states"]):
        return False
    return all(
        isinstance(item, dict)
        and type(item.get("tick")) is int
        and item["tick"] == known["tick"]
        and near(item.get("mean"), known["mean"])
        and near(item.get("covariance"), known["covariance"])
        for item, known in zip(states, expected["states"], strict=True)
    )
