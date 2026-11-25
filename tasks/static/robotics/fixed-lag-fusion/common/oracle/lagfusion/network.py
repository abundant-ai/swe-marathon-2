"""Fit asynchronous biased ranges, receiver permutations and a shared wheel transform."""

from dataclasses import dataclass
from itertools import permutations, product
from math import atan2, hypot

import numpy as np

from .contract import Array, Json, integer, name, number, obj, rows, vector


@dataclass(frozen=True)
class Capture:
    """A drive and its validated wheel, IMU, fix and range records."""

    id: str
    epoch: str
    start: int
    end: int
    wheel: tuple
    imu: tuple
    fixes: tuple
    ranges: tuple


@dataclass(frozen=True)
class Commission:
    """A small discrete fit problem and its disjoint validation drives."""

    anchors: dict[str, Array]
    receivers: tuple[str, ...]
    offsets: tuple[int, ...]
    fit: tuple[Capture, ...]
    validation: tuple[Capture, ...]
    huber: float
    ambiguity: float


@dataclass(frozen=True)
class Calibration:
    """A fixed wheel transform and a biased range map for each receiver epoch."""

    offset: int
    wheel: Array
    bias: Array
    maps: dict[str, tuple[int, ...]]


def capture_from(
    data: Json, receivers: tuple[str, ...], offsets: tuple[int, ...]
) -> Capture:
    """Validate acquisition support and encode receiver names as column numbers."""
    start, end = integer(data["start_tick"]), integer(data["end_tick"])
    if not 1 <= end - start <= 31:
        raise ValueError("capture must contain 2 to 32 poses")
    wheel = []
    imu = []
    fixes = []
    ranges = []
    collections = {key: rows(data[key]) for key in ("wheel", "imu", "fixes", "ranges")}
    if sum(map(len, collections.values())) > 512:
        raise ValueError("too many observations in a capture")
    for movement in map(obj, collections["wheel"]):
        tick = integer(movement["device_tick"])
        if not all(start < tick + offset <= end for offset in offsets):
            raise ValueError("wheel offset leaves the capture")
        wheel.append(
            (
                tick,
                vector(movement["delta"]),
                number(movement["sigma_m"], positive=True),
            )
        )
    for movement in map(obj, collections["imu"]):
        tick = integer(movement["tick"])
        if not start < tick <= end:
            raise ValueError("invalid inertial displacement tick")
        imu.append(
            (
                tick,
                vector(movement["delta"]),
                number(movement["sigma_m"], positive=True),
            )
        )
    for point in map(obj, collections["fixes"]):
        tick = integer(point["tick"])
        if not start <= tick <= end:
            raise ValueError("invalid survey fix tick")
        fixes.append(
            (tick, vector(point["position"]), number(point["sigma_m"], positive=True))
        )
    if not fixes:
        raise ValueError("each capture requires a survey fix")
    for radio in map(obj, collections["ranges"]):
        tick, receiver = integer(radio["tick"]), name(radio["receiver"])
        if not start <= tick <= end or receiver not in receivers:
            raise ValueError("invalid range tick or receiver")
        ranges.append(
            (
                tick,
                receivers.index(receiver),
                number(radio["distance_m"], nonnegative=True),
                number(radio["sigma_m"], positive=True),
            )
        )
    return Capture(
        name(data["id"]),
        name(data["epoch"]),
        start,
        end,
        tuple(wheel),
        tuple(imu),
        tuple(fixes),
        tuple(ranges),
    )


def commission_from(spec: Json) -> Commission:
    """Read capture partitions, geometries and the fixed hypothesis set."""
    anchors = {name(key): vector(value) for key, value in obj(spec["anchors"]).items()}
    if len(anchors) != 3:
        raise ValueError("three surveyed anchors are required")
    a, b, c = anchors.values()
    if np.linalg.det(np.stack((b - a, c - a))) == 0.0:
        raise ValueError("surveyed anchors must be noncollinear")
    receivers = tuple(map(name, rows(spec["receivers"], 3)))
    if len(set(receivers)) != 3:
        raise ValueError("receiver IDs must be distinct")
    offsets = tuple(integer(offset, None) for offset in rows(spec["offset_candidates"]))
    if not 1 <= len(offsets) <= 5 or len(set(offsets)) != len(offsets):
        raise ValueError("invalid wheel offset grid")
    fit, validation = (
        tuple(capture_from(obj(item), receivers, offsets) for item in rows(spec[key]))
        for key in ("fit_captures", "validation_captures")
    )
    if not (1 <= len(fit) <= 3 and 1 <= len(validation) <= 3):
        raise ValueError("one to three drives are required in each partition")
    if len({capture.id for capture in (*fit, *validation)}) != len(fit) + len(
        validation
    ):
        raise ValueError("capture IDs must be distinct")
    epochs = {capture.epoch for capture in fit}
    if len(epochs) > 2 or any(capture.epoch not in epochs for capture in validation):
        raise ValueError("invalid fit or validation epoch")
    return Commission(
        anchors,
        receivers,
        offsets,
        fit,
        validation,
        number(spec["huber_k"], positive=True),
        number(spec["ambiguity_cost"], nonnegative=True),
    )


def transformed(vector: Array, wheel: Array) -> Array:
    """Transform a planar reading by a scale and proper rotation in complex coordinates."""
    x, y = vector
    c, s = wheel
    return np.array((c * x - s * y, s * x + c * y))


class Problem:
    """A bounded pose graph with prewhitened linear terms and nonlinear ranges."""

    def __init__(
        self,
        captures: tuple[Capture, ...],
        offset: int,
        survey: Array,
        huber: float,
        calibrated: Calibration | None = None,
    ) -> None:
        """Build linear equations shared by every receiver assignment at this offset."""
        self.captures = captures
        self.survey = survey
        self.huber = huber
        self.fixed = calibrated
        self.pose_count = sum(capture.end - capture.start + 1 for capture in captures)
        self.parameter_count = 2 * self.pose_count + (5 if calibrated is None else 0)
        A = []
        b = []
        ranged = []
        self.beginnings = []
        basis = np.eye(2)
        beginning = 0
        for capture in captures:
            self.beginnings.append(beginning)
            for tick, position, sigma in capture.fixes:
                end = 2 * (beginning + tick - capture.start)
                design = np.zeros((2, self.parameter_count))
                design[:, end : end + 2] = basis / sigma
                A.append(design)
                b.append(position / sigma)
            for kind, samples in (("wheel", capture.wheel), ("imu", capture.imu)):
                for tick, value, sigma in samples:
                    tick += offset if kind == "wheel" else 0
                    end = 2 * (beginning + tick - capture.start)
                    design = np.zeros((2, self.parameter_count))
                    design[:, end - 2 : end] = -basis / sigma
                    design[:, end : end + 2] = basis / sigma
                    if kind == "wheel":
                        if calibrated is None:
                            x, y = value
                            design[:, -5:-3] = -np.array(((x, -y), (y, x))) / sigma
                            value = np.zeros(2)
                        else:
                            value = transformed(value, calibrated.wheel)
                    A.append(design)
                    b.append(value / sigma)
            ranged.extend(
                (
                    beginning + tick - capture.start,
                    capture.epoch,
                    receiver,
                    observed,
                    sigma,
                )
                for tick, receiver, observed, sigma in capture.ranges
            )
            beginning += capture.end - capture.start + 1
        self.design = np.vstack(A)
        self.responses = np.concatenate(b)
        self.quadratic = self.design.T @ self.design
        self.range_pose = np.array([row[0] for row in ranged], dtype=int)
        self.range_epoch = tuple(row[1] for row in ranged)
        self.range_receiver = tuple(row[2] for row in ranged)
        self.range_value = np.array([row[3] for row in ranged], dtype=float)
        self.range_sigma = np.array([row[4] for row in ranged], dtype=float)
        self.range_rows = np.arange(len(ranged))
        self.seed = np.linalg.lstsq(self.design, self.responses, rcond=None)[0]
        if calibrated is None and np.linalg.norm(self.seed[-5:-3]) < 0.12:
            self.seed[-5:-3] = (1.0, 0.0)
            residual = self.responses - self.design[:, -5:-3] @ self.seed[-5:-3]
            self.seed[: 2 * self.pose_count] = np.linalg.lstsq(
                self.design[:, : 2 * self.pose_count], residual, rcond=None
            )[0]

    def anchors_for(self, mappings: dict[str, tuple[int, ...]]) -> Array:
        """Resolve the receiver index associated to each observed raw range."""
        return np.array(
            [
                mappings[epoch][receiver]
                for epoch, receiver in zip(
                    self.range_epoch, self.range_receiver, strict=True
                )
            ],
            dtype=int,
        )

    def residuals(self, value: Array, association: Array) -> tuple[Array, Array, Array]:
        """Evaluate linear residuals, ranges, and vector point-to-anchor offsets."""
        positions = value[: 2 * self.pose_count].reshape(-1, 2)
        difference = positions[self.range_pose] - self.survey[association]
        bias = value[-3:] if self.fixed is None else self.fixed.bias
        radio = (
            np.linalg.norm(difference, axis=1) + bias[association] - self.range_value
        ) / self.range_sigma
        return self.design @ value - self.responses, radio, difference

    def loss(self, linear: Array, radio: Array) -> float:
        """Evaluate half-squared linear costs and the robust scalar range objective."""
        magnitude = np.abs(radio)
        part = np.minimum(magnitude, self.huber)
        return float(
            0.5 * (linear @ linear + part @ part)
            + self.huber * np.sum(magnitude - part)
        )

    def optimize(self, associations: Array) -> tuple[float, Array]:
        """Fit one discrete hypothesis using damped robust Gauss-Newton iterations."""
        value = self.seed.copy()
        if self.fixed is None:
            _, residual, _ = self.residuals(value, associations)
            errors = residual * self.range_sigma
            for index in range(3):
                selected = errors[associations == index]
                if selected.size:
                    value[-3 + index] = -np.median(selected)
        damping = 1e-5
        linear, radio, position_delta = self.residuals(value, associations)
        score = self.loss(linear, radio)
        for _ in range(38):
            J = np.zeros((len(radio), self.parameter_count))
            distance = np.maximum(np.linalg.norm(position_delta, axis=1), 1e-12)
            derivatives = position_delta / (distance * self.range_sigma)[:, None]
            J[self.range_rows, 2 * self.range_pose] = derivatives[:, 0]
            J[self.range_rows, 2 * self.range_pose + 1] = derivatives[:, 1]
            if self.fixed is None:
                J[self.range_rows, self.parameter_count - 3 + associations] = (
                    1.0 / self.range_sigma
                )
            weights = self.huber / np.maximum(self.huber, np.abs(radio))
            weighted = J.T * weights
            H = self.quadratic + weighted @ J
            gradient = self.design.T @ linear + weighted @ radio
            diag = np.maximum(np.diag(H), 1.0)
            step = np.linalg.solve(H + damping * np.diag(diag), -gradient)
            update = value + step
            next_linear, next_radio, next_delta = self.residuals(update, associations)
            next_score = self.loss(next_linear, next_radio)
            if next_score < score:
                value = update
                improvement = score - next_score
                score, linear, radio, position_delta = (
                    next_score,
                    next_linear,
                    next_radio,
                    next_delta,
                )
                damping = max(damping / 3, 1e-12)
                if improvement <= 1e-11 * (1 + score):
                    break
            else:
                damping *= 8
                if damping > 1e6 or np.linalg.norm(step, ord=np.inf) < 1e-10:
                    break
        return score, value

    def tracks(self, value: Array) -> list[Json]:
        """Encode report trajectories in the original capture and acquisition order."""
        return [
            {
                "id": capture.id,
                "poses": [
                    {
                        "tick": tick,
                        "position": value[
                            2 * (beginning + index) : 2 * (beginning + index) + 2
                        ].tolist(),
                    }
                    for index, tick in enumerate(range(capture.start, capture.end + 1))
                ],
            }
            for capture, beginning in zip(self.captures, self.beginnings, strict=True)
        ]


def qualify_network(spec: Json) -> Json:
    """Commission every discrete hypothesis, then freeze the best fit for validation."""
    data = commission_from(spec)
    report = {
        "status": "insufficient_support",
        "calibration": None,
        "fit_cost": None,
        "fit": [],
        "validation": [],
    }
    epochs = tuple(sorted({capture.epoch for capture in data.fit}))
    supporters = {
        epoch: {
            receiver
            for capture in data.fit
            if capture.epoch == epoch
            for _, receiver, _, _ in capture.ranges
        }
        for epoch in epochs
    }
    excitation = sum(
        bool(np.any(displacement))
        for capture in data.fit
        for _, displacement, _ in capture.wheel
    )
    if excitation < 3 or any(len(receivers) != 3 for receivers in supporters.values()):
        return report
    survey = np.stack(list(data.anchors.values()))
    permutations_of_anchors = tuple(permutations(range(3)))
    hypotheses = []
    for offset in data.offsets:
        problem = Problem(data.fit, offset, survey, data.huber)
        for choices in product(permutations_of_anchors, repeat=len(epochs)):
            maps = dict(zip(epochs, choices, strict=True))
            score, result = problem.optimize(problem.anchors_for(maps))
            hypotheses.append((score, offset, choices, problem, result))
    hypotheses.sort(key=lambda item: item[:3])
    score, offset, choices, problem, solution = hypotheses[0]
    if len(hypotheses) > 1 and hypotheses[1][0] - score <= data.ambiguity + 1e-10:
        return report | {"status": "ambiguous"}

    maps = dict(zip(epochs, choices, strict=True))
    c, s = solution[-5:-3]
    if hypot(c, s) == 0:
        return report
    calibration = Calibration(offset, solution[-5:-3], solution[-3:], maps)
    validation = Problem(data.validation, offset, survey, data.huber, calibration)
    _, transformed_poses = validation.optimize(validation.anchors_for(maps))
    names = tuple(data.anchors)
    return {
        "status": "ok",
        "calibration": {
            "offset_ticks": offset,
            "wheel_scale": hypot(c, s),
            "wheel_yaw_rad": atan2(s, c),
            "range_bias_m": dict(zip(names, calibration.bias.tolist(), strict=True)),
            "receiver_maps": {
                epoch: {
                    receiver: names[index]
                    for receiver, index in zip(data.receivers, mapping, strict=True)
                }
                for epoch, mapping in maps.items()
            },
        },
        "fit_cost": score,
        "fit": problem.tracks(solution),
        "validation": validation.tracks(transformed_poses),
    }
