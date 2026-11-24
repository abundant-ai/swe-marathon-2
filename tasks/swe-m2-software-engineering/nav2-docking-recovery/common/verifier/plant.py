"""Independent closed-loop chassis, dock contacts, and timestamped sensor plant."""

from cmath import exp, phase
from math import hypot, isfinite, sqrt
from typing import Any

Record = dict[str, Any]


class Violation(Exception):
    """The application violated an observed docking requirement."""


def require(test: bool, message: str) -> None:
    """Stop the scenario when a protocol or physical requirement fails."""
    if not test:
        raise Violation(message)


def orient(yaw: float) -> complex:
    """Represent a planar orientation for sensor simulation."""
    return exp(1j * yaw)


def pose_json(position: complex, yaw: float) -> list[float]:
    """Encode the simulated transform in the controller's public format."""
    return [position.real, position.imag, phase(orient(yaw))]


def scenario_config(case: Record) -> Record:
    """Build a calibrated controller configuration for a private plant case."""
    config = {
        "tag_id": case["name"][-8:],
        "base_from_camera": case.get("camera", [-0.21, 0.053, 2.97]),
        "tag_from_dock": case.get("tag_offset", [-0.25, 0.083, 0.31]),
        "tick_seconds": 0.10,
        "deadline_tick": case.get("deadline", 185),
        "tag_max_age_ticks": 5,
        "tag_jump_m": 0.12,
        "tag_jump_rad": 0.22,
        "max_reverse_mps": 0.18,
        "max_angular_radps": 0.85,
        "near_distance_m": 0.24,
        "near_reverse_mps": 0.075,
    }
    if case["stage"] >= 2:
        config["charge"] = {
            "minimum_current_a": 0.40, "max_age_ticks": 4,
            "consecutive_samples": 3, "wait_ticks": case.get("charge_wait", 22),
        }
    if case["stage"] >= 3:
        config["recovery"] = {
            "guard_m": 0.17, "max_attempts": case.get("attempts", 2),
            "retreat_m": 0.27, "retreat_speed_mps": 0.19,
        }
    return config


class Plant:
    """Run the charger and simulated sensors independently of the submission."""

    chassis_radius = 0.18
    pallet_radius = 0.08

    def __init__(self, case: Record, config: Record) -> None:
        """Initialize the robot in the charger's local room coordinates."""
        self.case = case
        self.config = config
        x, y, yaw = case["pose"]
        self.position = complex(x, y)
        self.yaw = yaw
        self.tick = 0
        self.history: dict[int, tuple[complex, float, int, bool]] = {}
        self.accepted_captures: list[int] = []
        self.first_valid: int | None = None
        self.first_reverse: int | None = None
        self.contacts: list[int] = []
        self.previous_contact = False
        self.true_contact = False
        self.switch_since: int | None = None
        self.qualifying: list[int] = []
        self.newest_battery = -1
        self.charge_confirmed = False
        self.rear_obstacle: tuple[complex, int] | None = None
        self.obstacle_triggered = False
        self.blocked_ticks = 0
        self.pose_pauses = 0
        self.trace: list[tuple[int, float, float]] = []
        self.retreat_origin: complex | None = None
        self.retreat_distances: list[float] = []
        self.retreat_cycle = False
        self.completed = False

    def contact(self) -> bool:
        """Evaluate the physical connector's position and heading tolerance."""
        p = self.position
        return -0.025 <= p.real <= 0.041 and abs(p.imag) <= 0.046 and abs(self.yaw) <= 0.18

    def update_obstacle(self, tick: int) -> None:
        """Introduce a pallet behind the robot after meaningful approach motion."""
        duration = self.case.get("pallet_ticks")
        if duration and not self.obstacle_triggered and self.position.real < 0.45:
            center = self.position - 0.37 * orient(self.yaw)
            self.rear_obstacle = center, tick + duration
            self.obstacle_triggered = True
        if self.rear_obstacle is not None and tick >= self.rear_obstacle[1]:
            self.rear_obstacle = None

    def front_guard(self, tick: int) -> float:
        """Expose a temporarily occupied exit at the start of a recovery."""
        if not self.contacts or self.case.get("front_block_ticks", 0) == 0:
            return 4.0
        offset = tick - self.contacts[0] - self.config["charge"]["wait_ticks"]
        if 0 <= offset < self.case["front_block_ticks"]:
            return 0.10
        return 4.0

    def rear_guard(self) -> float:
        """Measure the circle-expanded pallet along the robot's reverse axis."""
        if self.rear_obstacle is None:
            return 4.0
        displacement = (self.rear_obstacle[0] - self.position) / -orient(self.yaw)
        radius = self.chassis_radius + self.pallet_radius
        if displacement.real < 0 or abs(displacement.imag) > radius:
            return 4.0
        return max(0.0, displacement.real - sqrt(radius**2 - displacement.imag**2))

    def detection(self, capture: int, sample: tuple[complex, float, int, bool]) -> Record:
        """Project the fixed room tag into the camera at the selected past tick."""
        pos, yaw, epoch, _ = sample
        cx, cy, ca = self.config["base_from_camera"]
        camera = pos + complex(cx, cy) * orient(yaw)
        camera_heading = yaw + ca
        tx, ty, ta = self.config["tag_from_dock"]
        tag_heading = -ta
        tag = -complex(tx, ty) * orient(tag_heading)
        jitter = self.case.get("tag_noise", 0.0)
        perturbation = complex((capture % 3 - 1) * jitter, (capture % 5 - 2) * jitter / 2)
        return {
            "tag_id": self.config["tag_id"], "tick": capture, "epoch": epoch,
            "camera_from_tag": pose_json((tag - camera) / orient(camera_heading) + perturbation,
                                        tag_heading - camera_heading + jitter * (capture % 3 - 1)),
        }

    def battery(self, tick: int, switch: bool) -> Record | None:
        """Send current pulses, delayed duplicates and true charger observations."""
        if self.case["stage"] < 2:
            return None
        if not switch:
            return {"tick": tick, "current_a": 0.90 if self.case.get("precontact_current") else 0.0}
        since = self.contacts[-1]
        elapsed = tick - since
        ready = len(self.contacts) >= self.case.get("charges_on", 1)
        if self.case.get("duplicate_current") and elapsed < 9:
            return {"tick": since, "current_a": 0.96}
        if self.case.get("low_break") and elapsed in (1, 2, 3, 4):
            return {"tick": tick, "current_a": 0.10 if elapsed == 3 else 0.71}
        if tick % 2 == 0:
            delay = self.case.get("charge_delay", 5)
            return {"tick": tick - 1, "current_a": 0.78 if ready and elapsed > delay else 0.03}
        return None

    def observe(self, tick: int) -> Record:
        """Update physical contact and emit one deterministic observation."""
        self.tick = tick
        self.update_obstacle(tick)
        self.true_contact = self.contact()
        if self.true_contact and not self.previous_contact:
            self.contacts.append(tick)
        self.previous_contact = self.true_contact
        switch = self.true_contact
        if switch and self.case.get("switch_bounce") and tick - self.contacts[-1] in (2, 3):
            switch = False
        epoch = 5 if tick >= self.case.get("reset_tick", 10000) else 3
        missing = any(a <= tick < b for a, b in self.case.get("odom_holes", ()))
        self.history[tick] = self.position, self.yaw, epoch, missing
        rotation = 0.84 if epoch == 3 else -1.12
        origin = complex(-0.95, 1.88) if epoch == 3 else complex(1.23, -1.46)
        odom = None if missing else {
            "epoch": epoch,
            "pose": pose_json(origin + self.position * orient(rotation), self.yaw + rotation),
        }

        detections = []
        delay = self.case.get("tag_delay", 2)
        capture = tick - delay
        if capture >= 0 and capture % 2 == 0:
            snapshot = self.history[capture]
            if not any(a <= capture < b for a, b in self.case.get("tag_holes", ())):
                row = self.detection(capture, snapshot)
                if self.case.get("distractor"):
                    detections.append(row | {"tag_id": "spare-tag", "camera_from_tag": [0.1, 0.6, 1.1]})
                if self.case.get("tag_jump") == capture:
                    row["camera_from_tag"][1] += 0.64
                else:
                    if not snapshot[3] and snapshot[2] == epoch:
                        self.accepted_captures.append(capture)
                        if self.first_valid is None:
                            self.first_valid = tick
                detections.append(row)
                if self.case.get("old_tags") and capture >= 8:
                    detections.append(self.detection(capture - 8, self.history[capture - 8]))
        battery = self.battery(tick, switch)
        if not switch:
            self.switch_since = None
            self.qualifying.clear()
            self.charge_confirmed = False
        else:
            self.switch_since = tick if self.switch_since is None else self.switch_since
            if battery and self.case["stage"] >= 2:
                stamp = battery["tick"]
                cfg = self.config["charge"]
                if max(self.switch_since, tick - cfg["max_age_ticks"], self.newest_battery + 1) <= stamp <= tick:
                    self.newest_battery = stamp
                    if battery["current_a"] >= cfg["minimum_current_a"]:
                        self.qualifying.append(stamp)
                    else:
                        self.qualifying.clear()
                    self.charge_confirmed = len(self.qualifying) >= cfg["consecutive_samples"]
        rear = self.rear_guard()
        if rear < 0.17:
            self.blocked_ticks += 1
        if missing:
            self.pose_pauses += 1
        return {"tick": tick, "odom": odom, "detections": detections, "contact": switch,
                "battery": battery, "clearance": {"front_m": self.front_guard(tick), "rear_m": rear}}

    def observe_command(self, response: Record, observation: Record) -> None:
        """Enforce command safety and update physical service outcomes."""
        require(isinstance(response, dict), "command response must be an object")
        v, w = response.get("v_mps"), response.get("w_radps")
        require(all(type(x) in (int, float) and -100 <= x <= 100 and isfinite(x) for x in (v, w)),
                "both velocity fields must be finite numbers in the physical command range")
        status = response.get("status")
        require(status in ("running", "docked", "failed"), "unknown docking state")
        require(status == "running" or (v == 0 and w == 0), "terminal response moved the robot")
        require(-v <= self.config["max_reverse_mps"] + 1e-9
                and abs(w) <= self.config["max_angular_radps"] + 1e-9, "command exceeds motion limit")
        if self.position.real > 0.0 and abs(self.position) < self.config["near_distance_m"] - 0.01:
            require(-v <= self.config["near_reverse_mps"] + 1e-9, "backing speed too high near contact")
        if observation["odom"] is None:
            require(v == 0 and w == 0, "moved while odometry unavailable")
        if self.case["stage"] >= 3 and v != 0:
            direction = "rear_m" if v < 0 else "front_m"
            require(observation["clearance"][direction] >= self.config["recovery"]["guard_m"],
                    f"moved into active {direction} guard at tick {self.tick}")
        if v < 0 or w != 0:
            require(not observation["contact"], "continued approach after switch contact")
            good = [t for t in self.accepted_captures if self.history[t][2] == observation["odom"]["epoch"]]
            require(good and self.tick - good[-1] <= self.config["tag_max_age_ticks"],
                    f"moved without a current target at tick {self.tick}")
        if v < 0 and self.retreat_cycle:
            distance = abs(self.position - self.retreat_origin)
            require(distance + self.config["recovery"]["retreat_speed_mps"] * 0.11
                    >= self.config["recovery"]["retreat_m"], "retry began before retreat reached staging distance")
            self.retreat_distances.append(distance)
            self.retreat_cycle = False
        if v > 0:
            require(self.case["stage"] >= 3 and self.contacts and not self.charge_confirmed
                    and self.tick - self.contacts[-1] >= self.config["charge"]["wait_ticks"],
                    "forward motion did not follow a timed-out charge attempt")
            require(len(self.contacts) < self.config["recovery"]["max_attempts"], "attempt budget exceeded")
            require(v <= self.config["recovery"]["retreat_speed_mps"] + 1e-9 and w == 0,
                    "retreat changed heading or exceeded its speed limit")
            if not self.retreat_cycle:
                self.retreat_origin = self.position
                self.retreat_cycle = True
        if v < 0 and self.first_reverse is None:
            self.first_reverse = self.tick
        if status == "docked":
            require(self.true_contact, "declared docking without physical contact")
            require(self.case["stage"] == 1 or self.charge_confirmed, "declared success without fresh charge evidence")
            self.completed = True
        if status == "failed" and self.case.get("failure_at_deadline"):
            require(self.tick >= self.config["deadline_tick"], "gave up before deadline while waiting for clearance")
        self.trace.append((self.tick, v, w))
        self.integrate(v, w)

    def integrate(self, v: float, w: float) -> None:
        """Advance the real body with constant commanded twist over one interval."""
        dt = self.config["tick_seconds"]
        origin = self.position
        for step in range(1, 6):
            elapsed = dt * step / 5
            if abs(w) < 1e-10:
                z = origin + elapsed * v * orient(self.yaw)
            else:
                z = origin + v / (1j * w) * orient(self.yaw) * (orient(w * elapsed) - 1)
            require(z.real >= -0.027, "robot body crossed the allowed dock penetration plane")
            if self.rear_obstacle is not None:
                require(abs(z - self.rear_obstacle[0]) >= self.pallet_radius + self.chassis_radius,
                        "swept body touched the rear pallet")
        self.position = z
        self.yaw = phase(orient(self.yaw + dt * w))
