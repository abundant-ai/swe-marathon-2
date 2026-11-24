"""Identify a delayed servo bus and compensate it during frozen actor execution."""

from dataclasses import dataclass
from math import sqrt

import numpy as np

from .model import Contract, Record, integer, mapping, names, number, positive, vector
from .session import decide


@dataclass(frozen=True)
class Tape:
    """Consecutive commissioning measurements in canonical joint order."""

    sent: np.ndarray
    pose: np.ndarray
    velocity: np.ndarray
    effort: np.ndarray


def tape(value: object, width: int, horizon: int) -> Tape:
    """Validate every acquisition row, even those before full delay support."""
    if type(value) is not list or not 1 + horizon <= len(value) <= 1200:
        raise ValueError("commissioning capture length outside limits")
    rows = [mapping(row) for row in value]
    starts = [integer(row["tick"], 0) for row in rows]
    if starts != list(range(starts[0], starts[0] + len(rows))):
        raise ValueError("expected consecutive physics ticks")
    arrays = [np.asarray([vector(row[key], width) for row in rows])
              for key in ("requested_rad", "position_rad", "velocity_rad_s", "effort_nm")]
    return Tape(*arrays)


def problem(data: Tape, axis: int, delay: int, horizon: int) -> tuple[np.ndarray, np.ndarray]:
    """Build one linear effort problem on common clock support."""
    timestamps = np.arange(horizon, len(data.sent))
    command = data.sent[timestamps - delay]
    design = np.column_stack((command, -data.pose[timestamps, axis],
                              -data.velocity[timestamps, axis], np.ones(len(timestamps))))
    return design, data.effort[timestamps, axis]


def trial(data: Tape, axis: int, delay: int, horizon: int) -> tuple[float, int, np.ndarray] | None:
    """Fit one full-rank delay hypothesis without a validation signal."""
    design, y = problem(data, axis, delay, horizon)
    scale = np.linalg.norm(design, axis=0)
    if np.any(scale == 0):
        return None
    coeff, _, rank, _ = np.linalg.lstsq(design / scale, y, rcond=1e-8)
    if rank != design.shape[1]:
        return None
    coeff /= scale
    error = design @ coeff - y
    return sqrt(float(error @ error) / len(y)), delay, coeff


def identify(spec: object) -> Record:
    """Recover axis-specific delays and coupled gains, then validate unchanged."""
    request = mapping(spec)
    joints = names(request["joint_order"])
    width = len(joints)
    delays = request["delay_candidates"]
    if type(delays) is not list or not delays or width > 8:
        raise ValueError("expected one to eight joints and a delay grid")
    grid = sorted(integer(delay, 0) for delay in delays)
    if grid[-1] > 8 or len(set(grid)) != len(grid):
        raise ValueError("invalid delay grid")
    limits = mapping(request["limits"])
    ambiguity, rmse_limit = (number(limits[key]) for key in ("ambiguity_rmse_nm", "max_validation_rmse_nm"))
    if min(ambiguity, rmse_limit) < 0:
        raise ValueError("negative validation bounds")
    horizon = grid[-1]
    fit, check = (tape(request[key], width, horizon) for key in ("fit", "validation"))
    abstain = {"status": "unidentifiable", "joint_order": list(joints), "model": None, "metrics": None}
    coefficients, winner_delays, fit_rms, check_rms = [], [], [], []
    for axis in range(width):
        evaluated = [trial(fit, axis, delay, horizon) for delay in grid]
        if any(item is None for item in evaluated):
            return abstain
        ranked = sorted(evaluated, key=lambda item: item[0])
        fit_error, delay, coeff = ranked[0]
        if len(ranked) > 1 and ranked[1][0] - fit_error <= ambiguity:
            return abstain
        if min(coeff[width], coeff[width + 1]) <= 0:
            return abstain
        design, y = problem(check, axis, delay, horizon)
        residual = design @ coeff - y
        coefficients.append(coeff)
        winner_delays.append(delay)
        fit_rms.append(fit_error)
        check_rms.append(sqrt(float(residual @ residual) / len(y)))
    coefficients = np.asarray(coefficients)
    coupling = coefficients[:, :width]
    if np.linalg.cond(coupling) > 1e5:
        return abstain
    model = {"delays_ticks": winner_delays, "command_gain_nm_rad": coupling.tolist(),
             "position_gain_nm_rad": coefficients[:, width].tolist(),
             "velocity_gain_nm_s_rad": coefficients[:, width + 1].tolist(),
             "bias_nm": coefficients[:, width + 2].tolist()}
    metrics = {"fit_rmse_nm": fit_rms, "validation_rmse_nm": check_rms}
    return {"status": "ok" if max(check_rms) <= rmse_limit else "validation_failed", "joint_order": list(joints),
            "model": model, "metrics": metrics}


@dataclass(frozen=True)
class Adapter:
    """Commissioned actuator compensation and independent command limits."""

    order: list[int]
    inverse_order: list[int]
    delay: np.ndarray
    gain: np.ndarray
    stiffness: np.ndarray
    bias: np.ndarray
    minimum: np.ndarray
    maximum: np.ndarray
    slew: np.ndarray
    neutral: np.ndarray
    fingerprint: str

    @classmethod
    def from_reports(cls, contract: Contract, raw: object, drive: object,
                     safety: object, fingerprint: str) -> "Adapter":
        """Validate the qualified model and bind its named channels before opening state."""
        manifest, report, limits = mapping(raw), mapping(drive), mapping(safety)
        if report["status"] != "ok":
            raise ValueError("cannot deploy an unqualified drive model")
        joints = names(report["joint_order"])
        actors = names(manifest["action_order"])
        size = len(actors)
        if set(joints) != set(actors) or size > 8 or names(limits["joint_order"]) != joints:
            raise ValueError("drive and safety joint names disagree with the policy")
        order = [actors.index(key) for key in joints]
        inverse = [joints.index(key) for key in actors]
        metrics = mapping(report["metrics"])
        for key in ("fit_rmse_nm", "validation_rmse_nm"):
            if min(vector(metrics[key], size)) < 0:
                raise ValueError("negative effort validation error")
        data = mapping(report["model"])
        raw_delays = data["delays_ticks"]
        if type(raw_delays) is not list or len(raw_delays) != size:
            raise ValueError("deployment delay width mismatch")
        delay = np.array([integer(value, 0) for value in raw_delays])
        if np.max(delay) > 8:
            raise ValueError("deployment delay outside 0..8 ticks")
        rows = data["command_gain_nm_rad"]
        if type(rows) is not list or len(rows) != size:
            raise ValueError("deployment command matrix width mismatch")
        gain = np.array([vector(row, size) for row in rows])
        if np.linalg.cond(gain) > 1e5:
            raise ValueError("deployment command matrix is singular")
        stiffness = vector(data["position_gain_nm_rad"], size)
        positive(stiffness)
        positive(vector(data["velocity_gain_nm_s_rad"], size))
        bias = np.array(vector(data["bias_nm"], size))
        lower, upper, step = (np.array(vector(limits[key], size))
                              for key in ("command_min_rad", "command_max_rad", "max_step_rad"))
        raw_neutral = [joint.sign * (contract.neutral[act.slot] - joint.zero)
                       for joint, act in zip(contract.commanded, contract.actuators, strict=True)]
        neutral = np.array(raw_neutral)[order]
        if np.any(lower >= upper) or np.any(step <= 0) or np.any(neutral < lower) or np.any(neutral > upper):
            raise ValueError("invalid deployment signal bounds")
        return cls(order, inverse, delay, gain, np.array(stiffness), bias, lower, upper, step, neutral, fingerprint)

    def initial(self) -> Record:
        """Start a new compensation history in the commissioned neutral pose."""
        return {"sent": self.neutral.tolist(), "target": None, "integral": [0.] * len(self.order),
                "slope": [0.] * len(self.order), "fingerprint": self.fingerprint}

    def control(self, contract: Contract, incoming: Record, response: Record, memory: Record) -> list[float]:
        """Undo bus coupling, compensate lag and reject persistent load by integral feedback."""
        qpos = vector(incoming["position"], len(contract.all_joints))
        qvel = vector(incoming["velocity"], len(contract.all_joints))
        actual = np.array([joint.sign*(qpos[joint.slot]-joint.zero) for joint in contract.commanded])[self.order]
        velocity = np.array([joint.sign*qvel[joint.slot] for joint in contract.commanded])[self.order]
        dt = contract.dt / 1e9
        desired = memory["target"]
        slope = np.asarray(memory["slope"])
        if response["status"] == "updated":
            current = np.asarray(response["target"])[self.order]
            difference = (current-np.asarray(desired)) / (dt*contract.period) if desired is not None else np.zeros(len(current))
            slope = .48*slope + .52*np.clip(difference, -4., 4.)
            memory["slope"] = slope.tolist()
            memory["target"] = current.tolist()
            desired = memory["target"]
        if desired is None:
            return self.neutral.tolist()
        desired = np.asarray(desired)
        err = desired - actual
        integral = np.asarray(memory["integral"])
        integral = np.clip(integral + (6.8*self.stiffness*dt)*err, -.42*self.stiffness, .42*self.stiffness)
        lead = dt*self.delay*np.clip(slope, -2., 2.)
        demand = self.stiffness*(desired + lead - .019*velocity + .18*err) + integral - self.bias
        requested = np.linalg.solve(self.gain, demand)
        last = np.asarray(memory["sent"])
        command = np.clip(requested, np.maximum(self.minimum,last-self.slew), np.minimum(self.maximum,last+self.slew))
        memory["integral"] = np.clip(integral + .10*(self.gain@(command-requested)), -.42*self.stiffness, .42*self.stiffness).tolist()
        return command.tolist()

    def step(self, contract: Contract, state: Record, incoming: object) -> tuple[Record, Record, bool]:
        """Apply one causal update without changing actor targets or replay semantics."""
        previous = state.get("drive", self.initial())
        response, state, changed = decide(contract, state, incoming)
        if not changed:
            return response, state, False
        if response["status"] in ("updated", "held"):
            command = self.control(contract, mapping(incoming), response, previous)
            previous["sent"] = command
            active = [command[index] for index in self.inverse_order]
            bus = contract.neutral.copy()
            for value, joint, actuator in zip(active, contract.commanded, contract.actuators, strict=True):
                bus[actuator.slot] = joint.zero + joint.sign * value
            response["control"] = bus
        else:
            previous = self.initial()
        state["drive"] = previous
        state["reply"] = response
        return response, state, True
