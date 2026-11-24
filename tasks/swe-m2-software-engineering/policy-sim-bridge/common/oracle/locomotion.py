"""Run a frozen free-base locomotion actor behind a contact-aware command lease."""

from hashlib import sha256
import json
from math import acos, hypot, isfinite, pi
import os
from pathlib import Path
import sys
import tempfile

import numpy as np
import onnxruntime as ort


FEET = ("FL", "FR", "RL", "RR")
HISTORY_LENGTH = 10
TERM_SIZES = (3, 3, 3, 12, 12, 12)


def canonical(value):
    """Serialize a parsed document for state fingerprints and retry checks."""
    return json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":"))


def integer(value, name, minimum=0):
    """Require a JSON integer in the configured range."""
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer of at least {minimum}")
    return value


def number(value, name):
    """Require a finite JSON number."""
    if type(value) not in (int, float) or not isfinite(value):
        raise ValueError(f"{name} must be finite")
    return float(value)


def vector(raw, size, name):
    """Read a fixed-width numeric vector."""
    if not isinstance(raw, list) or len(raw) != size:
        raise ValueError(f"{name} must contain {size} values")
    return [number(value, name) for value in raw]


def names(raw, name):
    """Read distinct names for the twelve controlled joints."""
    if (
        not isinstance(raw, list)
        or len(raw) != 12
        or any(not isinstance(joint, str) or not joint for joint in raw)
        or len(set(raw)) != 12
    ):
        raise ValueError(f"{name} must contain twelve distinct joint names")
    return raw


def quaternion(raw):
    """Normalize either sign of a scalar-last body-to-world attitude."""
    parts = vector(raw, 4, "q_xyzw")
    length = hypot(*parts)
    if length == 0 or not isfinite(length):
        raise ValueError("q_xyzw must specify a nonzero quaternion")
    return np.asarray(parts) / length


def body_vector(attitude, earth_vector):
    """Express a world-frame vector in the body frame."""
    axis, scalar = attitude[:3], attitude[3]
    cross = np.cross(axis, earth_vector)
    return earth_vector + 2 * (np.cross(axis, cross) - scalar * cross)


class Deployment:
    """Validate the frozen deployment and bind its two independent joint orders."""

    def __init__(self, spec_path):
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        if not isinstance(spec, dict):
            raise ValueError("manifest must be a JSON object")
        joints = names(spec["policy_joints"], "policy_joints")
        actuators = names(spec["actuator_order"], "actuator_order")
        sensors = spec["joint_sensors"]
        if not isinstance(sensors, list) or len(sensors) != len(joints):
            raise ValueError("joint_sensors must contain twelve bindings")
        sensed = names([sensor["joint"] for sensor in sensors], "sensor joints")
        if set(joints) != set(actuators) or set(joints) != set(sensed):
            raise ValueError("all sensor and actuator names must bind to policy joints")
        self.sensor_indices = [sensed.index(joint) for joint in joints]
        self.actuator_indices = [joints.index(joint) for joint in actuators]
        signs = [number(sensor["sign"], "joint sensor sign") for sensor in sensors]
        if any(sign not in (-1, 1) for sign in signs):
            raise ValueError("joint sensor sign must be +1 or -1")
        self.sign = np.asarray(signs)
        self.zero = np.asarray([number(sensor["zero_rad"], "joint sensor zero") for sensor in sensors])
        self.home = np.asarray(vector(spec["default_positions_rad"], 12, "default_positions_rad"))
        self.command_scale = np.asarray(vector(spec["command_scale"], 3, "command_scale"))
        self.max_command = vector(spec["max_command_abs"], 3, "max_command_abs")
        self.max_lease = integer(spec["max_lease_ticks"], "max_lease_ticks", 1)
        self.contact_age = integer(spec["max_contact_age_ticks"], "max_contact_age_ticks")
        self.min_support = integer(spec["min_support_feet"], "min_support_feet", 1)
        self.recovery = integer(spec["recovery_ticks"], "recovery_ticks", 1)
        self.rearm = integer(spec["rearm_ticks"], "rearm_ticks", 1)
        self.normal_min = number(spec["normal_min_n"], "normal_min_n")
        self.slip_limit = number(spec["slip_limit_mps"], "slip_limit_mps")
        self.limit_factor = number(spec["limit_factor"], "limit_factor")
        self.max_tilt = number(spec["max_tilt_rad"], "max_tilt_rad")
        if (
            any(limit <= 0 for limit in self.max_command)
            or self.min_support > len(FEET)
            or self.normal_min < 0
            or self.slip_limit < 0
            or not 0 <= self.limit_factor < 1
            or not 0 < self.max_tilt <= pi
        ):
            raise ValueError("manifest command and contact limits are out of range")

        actor = spec_path.parent / spec["actor"]
        weights = actor.read_bytes()
        digest = sha256(weights).hexdigest()
        if digest != spec["actor_sha256"]:
            raise ValueError("frozen actor SHA-256 differs from its manifest")
        self.fingerprint = sha256(canonical([spec, digest]).encode()).hexdigest()
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.log_severity_level = 3
        self.actor = ort.InferenceSession(weights, sess_options=options, providers=["CPUExecutionProvider"])
        inputs = self.actor.get_inputs()
        outputs = self.actor.get_outputs()
        if (
            len(inputs) != 1
            or inputs[0].shape != [1, 450]
            or inputs[0].type != "tensor(float)"
            or len(outputs) != 1
            or outputs[0].shape != [1, 12]
            or outputs[0].type != "tensor(float)"
        ):
            raise ValueError("frozen actor input or output interface differs from the deployment")
        self.actor_input = inputs[0].name
        self.actor_output = outputs[0].name

    def initial(self):
        """Return the original zero-filled actor and authority state."""
        return {
            "fingerprint": self.fingerprint,
            "tick": -1,
            "packet": None,
            "response": None,
            "lease": None,
            "blocked": -1,
            "contacts": {},
            "ready": 0,
            "armed": False,
            "limited": False,
            "quiet": 0,
            "history": [[0.0] * sum(TERM_SIZES) for _ in range(HISTORY_LENGTH)],
            "previous_action": [0.0] * 12,
        }

    def request(self, raw, previous, tick):
        """Accept only a newer bounded request without extending an earlier lease."""
        if not isinstance(raw, dict):
            return previous
        try:
            sequence = integer(raw["sequence"], "sequence")
            expires = integer(raw["valid_until_tick"], "valid_until_tick")
            velocity = vector(raw["velocity"], 3, "velocity")
        except (KeyError, ValueError, OverflowError):
            return previous
        if (
            (previous is not None and sequence <= previous["sequence"])
            or not tick <= expires <= tick + self.max_lease
            or any(abs(value) > limit for value, limit in zip(velocity, self.max_command, strict=True))
        ):
            return previous
        return {"sequence": sequence, "valid_until_tick": expires, "velocity": velocity}

    def contacts(self, previous, packets, tick):
        """Merge fresh contact evidence, retaining the first packet at each foot and stamp."""
        if not isinstance(packets, list):
            raise ValueError("contacts must be a JSON array")
        oldest = tick - self.contact_age
        contacts = {foot: row for foot, row in previous.items() if row["capture_tick"] >= oldest}
        for packet in packets:
            if not isinstance(packet, dict) or packet.get("foot") not in FEET:
                continue
            foot = packet["foot"]
            try:
                stamp = integer(packet["capture_tick"], "capture_tick")
                normal = number(packet["normal_force_n"], "normal_force_n")
                tangent = number(packet["tangent_speed_mps"], "tangent_speed_mps")
            except (KeyError, ValueError, OverflowError):
                continue
            if not oldest <= stamp <= tick or normal < 0 or tangent < 0:
                continue
            if foot not in contacts or stamp > contacts[foot]["capture_tick"]:
                contacts[foot] = {"capture_tick": stamp, "normal_force_n": normal, "tangent_speed_mps": tangent}
        return contacts

    def drive(self, packet, state, gravity):
        """Update the lease and derive a causal body-frame twist."""
        tick = packet["tick"]
        contacts = self.contacts(state["contacts"], packet["contacts"], tick)
        lease = self.request(packet["request"], state["lease"], tick)
        support = sorted(foot for foot, row in contacts.items() if row["normal_force_n"] >= self.normal_min)
        slip = any(contacts[foot]["tangent_speed_mps"] > self.slip_limit for foot in support)
        healthy = len(contacts) >= 3 and acos(float(np.clip(-gravity[2], -1, 1))) <= self.max_tilt
        stable = healthy and len(support) >= self.min_support and not slip
        ready = state["ready"] + 1 if stable else 0
        armed, blocked = state["armed"], state["blocked"]
        active = lease is not None and tick <= lease["valid_until_tick"]
        expired = lease is not None and not active
        if expired or (armed and not healthy):
            if lease is not None:
                blocked = max(blocked, lease["sequence"])
            armed = False
        if not armed and active and lease["sequence"] > blocked and ready >= self.rearm:
            armed = True

        limited, quiet = state["limited"], state["quiet"]
        mode, lease_id, effective = "stop", None, [0.0, 0.0, 0.0]
        if not armed:
            limited, quiet = False, 0
        else:
            if slip:
                limited, quiet = True, 0
            elif limited:
                quiet = quiet + 1 if stable else 0
                if quiet >= self.recovery:
                    limited, quiet = False, 0
            mode = "limited" if limited else "track"
            lease_id = lease["sequence"]
            effective = [self.limit_factor * speed for speed in lease["velocity"]] if limited else lease["velocity"]
        authority = {
            "contacts": contacts, "lease": lease, "blocked": blocked, "ready": ready,
            "armed": armed, "limited": limited, "quiet": quiet,
        }
        return authority, mode, lease_id, support, effective

    def step(self, packet, state):
        """Consume one valid packet or return a response that leaves the session unchanged."""
        if not isinstance(packet, dict):
            raise ValueError("packet must be a JSON object")
        tick = integer(packet["tick"], "tick")
        request = canonical(packet)
        if tick == state["tick"] and request == state["packet"]:
            return state["response"], state
        if tick != state["tick"] + 1:
            return {
                "tick": tick, "mode": "rejected", "lease": None, "support": [],
                "effective_twist": None, "action": None, "target_rad": None,
            }, state

        attitude = quaternion(packet["q_xyzw"])
        gravity = body_vector(attitude, np.array([0.0, 0.0, -1.0]))
        gyro = body_vector(attitude, vector(packet["gyro_world_rad_s"], 3, "gyro_world_rad_s"))
        wire_position = np.asarray(vector(packet["joint_position_rad"], 12, "joint_position_rad"))
        wire_velocity = np.asarray(vector(packet["joint_velocity_rad_s"], 12, "joint_velocity_rad_s"))
        position = (self.sign * wire_position + self.zero)[self.sensor_indices]
        velocity = (self.sign * wire_velocity)[self.sensor_indices]
        authority, mode, lease, support, twist = self.drive(packet, state, gravity)
        frame = np.concatenate((
            0.25 * gyro, gravity, self.command_scale * twist, position - self.home, 0.05 * velocity,
            state["previous_action"],
        )).astype(np.float32)
        if not np.isfinite(frame).all():
            raise ValueError("actor observation overflowed float32")
        history = [*state["history"][1:], frame.tolist()]
        term_boundaries = np.cumsum(TERM_SIZES)[:-1]
        terms = np.split(np.asarray(history, dtype=np.float32), term_boundaries, axis=1)
        stacked = np.concatenate([term.reshape(-1) for term in terms]).reshape(1, 450)
        action = self.actor.run([self.actor_output], {self.actor_input: stacked})[0][0]
        if not np.isfinite(action).all():
            raise ValueError("frozen actor returned a nonfinite action")
        action = np.clip(action, -100.0, 100.0)
        targets = (self.home + 0.25 * action)[self.actuator_indices]
        response = {
            "tick": tick, "mode": mode, "lease": lease, "support": support,
            "effective_twist": twist, "action": action.tolist(), "target_rad": targets.tolist(),
        }
        changed = state | authority | {
            "tick": tick, "packet": request, "response": response,
            "history": history, "previous_action": response["action"],
        }
        return response, changed


def commit(path, state):
    """Durably replace the snapshot before issuing a new response."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(canonical(state))
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
        folder = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(folder)
        finally:
            os.close(folder)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def locomote(spec_path: Path, state_dir: Path) -> None:
    """Stream locomotion replies while preserving causal state across restarts."""
    deployment = Deployment(spec_path)
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "locomotion.json"
    state = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else deployment.initial()
    if state["fingerprint"] != deployment.fingerprint:
        raise ValueError("session requires its original deployment manifest and actor")
    for line in sys.stdin:
        packet = json.loads(line)
        response, updated = deployment.step(packet, state)
        if updated is not state:
            commit(path, updated)
            state = updated
        print(canonical(response), flush=True)
