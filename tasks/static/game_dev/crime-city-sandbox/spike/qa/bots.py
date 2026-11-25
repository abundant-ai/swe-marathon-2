"""QA bots: they act only through InputMap actions, reading the probe's frames.

Each bot is called once per control step with the latest frame and returns
(actions: dict action -> strength, done: bool). Bots record what they measure in `facts`.
"""

import math

ACTIONS_CAR = ("accelerate", "brake", "steer_left", "steer_right", "handbrake")
ACTIONS_FOOT = (
    "move_forward",
    "move_back",
    "move_left",
    "move_right",
    "look_left",
    "look_right",
    "sprint",
)


def find(frame, eid):
    for e in frame.get("census", []):
        if e["id"] == eid:
            return e
    return None


def player_of(frame):
    for e in frame.get("census", []):
        if e["k"] == "player":
            return e
    return None


def car_of(frame):
    p = player_of(frame)
    if p is None or p.get("veh") is None:
        return None
    return find(frame, p["veh"])


def flat(v):
    return (v[0], v[2])


def speed_along(car, f):
    v = car.get("v", [0, 0, 0])
    return v[0] * f[0] + v[2] * f[1]


class CarHeading:
    """Works out which basis axis is the car's front from the requested spawn heading."""

    def __init__(self, hint):
        self.hint = hint
        self.sign = None

    def fwd(self, car):
        bz = car["bz"]
        if self.sign is None:
            self.sign = 1.0 if bz[0] * self.hint[0] + bz[2] * self.hint[1] > 0 else -1.0
        x, z = bz[0] * self.sign, bz[2] * self.sign
        n = math.hypot(x, z) or 1.0
        return (x / n, z / n)


class Steering:
    """Pure pursuit with a nominal steering model, plus a PI speed loop."""

    def __init__(self):
        self.i_err = 0.0

    def steer(self, pos, f, target, v):
        dx, dz = target[0] - pos[0], target[1] - pos[1]
        fwd_d = dx * f[0] + dz * f[1]
        left_d = dx * f[1] - dz * f[0]
        k = 2.0 * left_d / max(fwd_d * fwd_d + left_d * left_d, 0.01)
        delta = math.atan(2.7 * k)
        s = max(-1.0, min(1.0, delta / (0.55 / (1.0 + abs(v) / 15.0))))
        return {"steer_left": max(0.0, s), "steer_right": max(0.0, -s)}

    def speed(self, v, v_target, dt):
        e = v_target - v
        self.i_err = max(-20.0, min(20.0, self.i_err + e * dt))
        if v_target <= 0.05:
            return {"accelerate": 0.0, "brake": 1.0 if v > 0.3 else 0.4}
        if e < -1.5:
            return {"accelerate": 0.0, "brake": min(1.0, -0.12 * e)}
        return {
            "accelerate": max(0.0, min(1.0, 0.18 * e + 0.04 * self.i_err + 0.08)),
            "brake": 0.0,
        }


class DriveLine:
    """Drive along a straight line (start point, direction) for `length_m`, at `speed`,
    ignoring signals; optionally stop at the end."""

    def __init__(
        self,
        origin,
        direction,
        length_m,
        speed_mps,
        stop=True,
        facts=None,
        name="drive",
    ):
        self.o, self.t = origin, direction
        self.length, self.v_t, self.stop = length_m, speed_mps, stop
        self.h = CarHeading(direction)
        self.ctl = Steering()
        self.facts = facts if facts is not None else {}
        self.name = name
        self.dt = 0.05

    def __call__(self, frame):
        car = car_of(frame)
        if car is None:
            return {}, True
        pos = flat(car["p"])
        f = self.h.fwd(car)
        v = speed_along(car, f)
        s = (pos[0] - self.o[0]) * self.t[0] + (pos[1] - self.o[1]) * self.t[1]
        look = 6.0 + 0.5 * abs(v)
        target = (
            self.o[0] + self.t[0] * (s + look),
            self.o[1] + self.t[1] * (s + look),
        )
        act = self.ctl.steer(pos, f, target, v)
        remaining = self.length - s
        vt = self.v_t
        if self.stop:
            vt = min(vt, math.sqrt(max(0.0, 2.0 * 3.0 * (remaining - 2.0))))
        act.update(self.ctl.speed(v, vt, self.dt))
        if self.stop and remaining < 3.0 and abs(v) < 0.2:
            self.facts[self.name + "_end_s"] = s
            return {
                "accelerate": 0.0,
                "brake": 0.5,
                "steer_left": 0.0,
                "steer_right": 0.0,
            }, True
        if not self.stop and remaining <= 0:
            return act, True
        return act, False


class BrakeTest:
    """Full throttle to v_brake, then full brake to a stop. Records the 0-v time and the
    braking distance (scaled to exactly v_brake by v^2)."""

    def __init__(self, direction, v_brake=60 / 3.6, facts=None, prefix="dry"):
        self.t = direction
        self.vb = v_brake
        self.h = CarHeading(direction)
        self.ctl = Steering()
        self.phase = "accel"
        self.facts = facts if facts is not None else {}
        self.prefix = prefix
        self.t0 = None
        self.origin = None

    def __call__(self, frame):
        car = car_of(frame)
        if car is None:
            return {}, True
        pos = flat(car["p"])
        f = self.h.fwd(car)
        v = speed_along(car, f)
        if self.origin is None:
            self.origin = pos
            self.t0 = frame["t"]
        target = (pos[0] + self.t[0] * 15.0, pos[1] + self.t[1] * 15.0)
        # keep on the line through the origin
        s = (pos[0] - self.origin[0]) * self.t[0] + (pos[1] - self.origin[1]) * self.t[
            1
        ]
        target = (
            self.origin[0] + self.t[0] * (s + 12.0),
            self.origin[1] + self.t[1] * (s + 12.0),
        )
        act = self.ctl.steer(pos, f, target, v)
        if self.phase == "accel":
            if v >= self.vb:
                self.phase = "brake"
                self.facts[self.prefix + "_t_0_60_s"] = (frame["t"] - self.t0) / 60.0
                self.facts[self.prefix + "_v_brake"] = v
                self.brake_pos = pos
                act.update({"accelerate": 0.0, "brake": 1.0})
                return act, False
            act.update({"accelerate": 1.0, "brake": 0.0})
            return act, False
        if v <= 0.05:
            d = math.hypot(pos[0] - self.brake_pos[0], pos[1] - self.brake_pos[1])
            vb = self.facts[self.prefix + "_v_brake"]
            self.facts[self.prefix + "_brake_m_raw"] = d
            self.facts[self.prefix + "_brake_m"] = d * (self.vb / vb) ** 2
            return {
                "accelerate": 0.0,
                "brake": 0.0,
                "steer_left": 0.0,
                "steer_right": 0.0,
            }, True
        act.update({"accelerate": 0.0, "brake": 1.0})
        return act, False


class TurnCircle:
    """Hold a low speed at full left lock; fit a circle to the path once settled."""

    def __init__(self, speed_mps=8 / 3.6, seconds=14.0, facts=None):
        self.v_t = speed_mps
        self.seconds = seconds
        self.facts = facts if facts is not None else {}
        self.ctl = Steering()
        self.h = None
        self.t0 = None
        self.pts = []

    def __call__(self, frame):
        car = car_of(frame)
        if car is None:
            return {}, True
        if self.t0 is None:
            self.t0 = frame["t"]
            bz = car["bz"]
            self.h = CarHeading((-bz[0], -bz[2]))  # resolved from motion below
        v_vec = car.get("v", [0, 0, 0])
        v = math.hypot(v_vec[0], v_vec[2])
        el = (frame["t"] - self.t0) / 60.0
        if el > 3.0:
            self.pts.append(flat(car["p"]))
        if el >= self.seconds:
            _cx, _cz, r = fit_circle(self.pts)
            self.facts["turn_circle_m"] = 2.0 * r
            return {
                "accelerate": 0.0,
                "brake": 1.0,
                "steer_left": 0.0,
                "steer_right": 0.0,
            }, True
        act = {"steer_left": 1.0, "steer_right": 0.0}
        act.update(self.ctl.speed(v, self.v_t, 0.05))
        return act, False


def fit_circle(pts):
    n = len(pts)
    if n < 3:
        return 0.0, 0.0, 0.0
    mx = sum(p[0] for p in pts) / n
    mz = sum(p[1] for p in pts) / n
    suu = svv = suv = suuu = svvv = suvv = svuu = 0.0
    for x, z in pts:
        u, v = x - mx, z - mz
        suu += u * u
        svv += v * v
        suv += u * v
        suuu += u * u * u
        svvv += v * v * v
        suvv += u * v * v
        svuu += v * u * u
    a = [[suu, suv], [suv, svv]]
    b = [0.5 * (suuu + suvv), 0.5 * (svvv + svuu)]
    det = a[0][0] * a[1][1] - a[0][1] * a[1][0]
    if abs(det) < 1e-9:
        return mx, mz, 0.0
    uc = (b[0] * a[1][1] - b[1] * a[0][1]) / det
    vc = (a[0][0] * b[1] - a[1][0] * b[0]) / det
    r = math.sqrt(uc * uc + vc * vc + (suu + svv) / n)
    return uc + mx, vc + mz, r


class TopSpeed:
    def __init__(self, direction, max_s=50.0, facts=None):
        self.t = direction
        self.h = CarHeading(direction)
        self.ctl = Steering()
        self.max_s = max_s
        self.facts = facts if facts is not None else {}
        self.hist = []
        self.t0 = None
        self.origin = None

    def __call__(self, frame):
        car = car_of(frame)
        if car is None:
            return {}, True
        pos = flat(car["p"])
        f = self.h.fwd(car)
        v = speed_along(car, f)
        if self.t0 is None:
            self.t0 = frame["t"]
            self.origin = pos
        el = (frame["t"] - self.t0) / 60.0
        self.hist.append((el, v))
        s = (pos[0] - self.origin[0]) * self.t[0] + (pos[1] - self.origin[1]) * self.t[
            1
        ]
        target = (
            self.origin[0] + self.t[0] * (s + 20.0),
            self.origin[1] + self.t[1] * (s + 20.0),
        )
        act = self.ctl.steer(pos, f, target, v)
        old = [x for x in self.hist if x[0] <= el - 3.0]
        if el >= self.max_s or (old and el > 8.0 and v - old[-1][1] < 0.14):
            self.facts["top_speed_kmh"] = max(x[1] for x in self.hist) * 3.6
            self.facts["top_speed_plateau"] = el < self.max_s
            act.update({"accelerate": 0.0, "brake": 1.0})
            return act, True
        act.update({"accelerate": 1.0, "brake": 0.0})
        return act, False


class Walk:
    """Walk, run or sprint in a world heading (person convention) using look + move actions."""

    def __init__(self, heading, gait, seconds):
        self.heading = heading
        self.gait = gait
        self.seconds = seconds
        self.t0 = None

    def __call__(self, frame):
        if self.t0 is None:
            self.t0 = frame["t"]
        cam = frame.get("camera")
        act = {"look_left": 0.0, "look_right": 0.0}
        if cam is not None:
            cy = math.atan2(cam["bz"][0], cam["bz"][2])
            err = (self.heading - cy + math.pi) % (2 * math.pi) - math.pi
            act["look_left"] = max(0.0, min(1.0, 3.0 * err))
            act["look_right"] = max(0.0, min(1.0, -3.0 * err))
        strength = {"stand": 0.0, "walk": 0.4, "run": 1.0, "sprint": 1.0}[self.gait]
        act["move_forward"] = strength
        act["sprint"] = 1.0 if self.gait == "sprint" else 0.0
        done = (frame["t"] - self.t0) / 60.0 >= self.seconds
        return act, done
