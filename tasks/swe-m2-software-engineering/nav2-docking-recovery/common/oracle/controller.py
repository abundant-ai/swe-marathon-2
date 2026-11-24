"""Dock tracking, feedback control, and charging/recovery transitions."""

from math import atan2, hypot
from typing import Any

from .geometry import compose, inverse, wrap
from .staging import staged, sweep

Record = dict[str, Any]


def initial_state() -> Record:
    """Return isolated mutable state for a fresh docking mission."""
    return {
        "epoch": None, "poses": {}, "track": None, "acquire_from": 0,
        "last_tick": None, "reply": None, "terminal": None, "attempts": 1,
        "contact_since": None, "contact_continuous_since": None, "battery_tick": None,
        "samples": 0, "retreating": False, "retreat_start": None,
    }


def update_track(state: Record, config: Record, observation: Record) -> None:
    """Transform fresh tag observations using the odometry frame at their capture."""
    odom = observation["odom"]
    if odom is None:
        return
    epoch = odom["epoch"]
    tick = observation["tick"]
    if state["epoch"] != epoch:
        state.update(epoch=epoch, track=None, poses={}, retreat_start=None)
    poses = state["poses"]
    poses[str(tick)] = odom["pose"]
    oldest = tick - config["tag_max_age_ticks"]
    for key in tuple(poses):
        if int(key) < oldest:
            del poses[key]
    if state["retreating"]:
        return
    for detection in sorted(observation["detections"], key=lambda row: row["tick"]):
        capture = detection["tick"]
        if (detection["tag_id"] != config["tag_id"] or detection["epoch"] != epoch
                or capture < state["acquire_from"] or str(capture) not in poses):
            continue
        previous = state["track"]
        if previous and capture <= previous["tick"]:
            continue
        dock = compose(
            compose(tuple(poses[str(capture)]), tuple(config["base_from_camera"])),
            compose(tuple(detection["camera_from_tag"]), tuple(config["tag_from_dock"])),
        )
        if previous:
            old = previous["pose"]
            if (hypot(dock[0] - old[0], dock[1] - old[1]) > config["tag_jump_m"]
                    or abs(wrap(dock[2] - old[2])) > config["tag_jump_rad"]):
                continue
        state["track"] = {"tick": capture, "pose": dock}


def reply(v: float = 0.0, w: float = 0.0, status: str = "running") -> Record:
    """Build one command in the transport format."""
    return {"v_mps": v, "w_radps": w, "status": status}


def terminal(state: Record, status: str) -> Record:
    """Latch a final outcome and issue a stop."""
    state["terminal"] = status
    return reply(status=status)


def guarded(config: Record, observation: Record, direction: str) -> bool:
    """Return whether the specified direction has adequate current clearance."""
    if "recovery" not in config:
        return True
    clearance = (observation.get("clearance") or {}).get(f"{direction}_m")
    return clearance is not None and clearance >= config["recovery"]["guard_m"]


def retreat(state: Record, config: Record, observation: Record) -> Record:
    """Back out of the contact attempt, then force reacquisition at staging."""
    odom = observation["odom"]
    if odom is None:
        return reply()
    current = odom["pose"][:2]
    if state["retreat_start"] is None:
        state["retreat_start"] = current
    start = state["retreat_start"]
    recovery = config["recovery"]
    if hypot(current[0] - start[0], current[1] - start[1]) + 1e-9 >= recovery["retreat_m"]:
        state.update(retreating=False, retreat_start=None, track=None,
                     acquire_from=observation["tick"], contact_since=None,
                     contact_continuous_since=None, battery_tick=None, samples=0)
        return reply()
    if not guarded(config, observation, "front"):
        return reply()
    return reply(v=recovery["retreat_speed_mps"])


def verify_charge(state: Record, config: Record, observation: Record) -> Record:
    """Accumulate genuinely new charging evidence and budget a retry if needed."""
    charge = config["charge"]
    tick = observation["tick"]
    if not observation["contact"]:
        state.update(samples=0, contact_continuous_since=None)
    else:
        if state["contact_continuous_since"] is None:
            state["contact_continuous_since"] = tick
        battery = observation.get("battery")
        if battery is not None:
            stamp = battery["tick"]
            previous = state["battery_tick"]
            if (state["contact_continuous_since"] <= stamp <= tick
                    and tick - stamp <= charge["max_age_ticks"]
                    and (previous is None or stamp > previous)):
                state["battery_tick"] = stamp
                enough = battery["current_a"] >= charge["minimum_current_a"]
                state["samples"] = state["samples"] + 1 if enough else 0
                if state["samples"] >= charge["consecutive_samples"]:
                    return terminal(state, "docked")
    if tick - state["contact_since"] < charge["wait_ticks"]:
        return reply()
    if "recovery" not in config or state["attempts"] >= config["recovery"]["max_attempts"]:
        return terminal(state, "failed")
    state.update(retreating=True, retreat_start=None, attempts=state["attempts"] + 1)
    return retreat(state, config, observation)


def approach(state: Record, config: Record, observation: Record) -> Record:
    """Generate a bounded visual-servo command for a usable rear target."""
    odom = observation["odom"]
    target = state["track"]
    if (odom is None or target is None
            or observation["tick"] - target["tick"] > config["tag_max_age_ticks"]
            or not guarded(config, observation, "rear")):
        return reply()
    x, y, yaw = compose(inverse(tuple(odom["pose"])), tuple(target["pose"]))
    distance = hypot(x, y)
    bearing = atan2(-y, -x)
    blend = max(0.0, min(1.0, (0.23 - distance) / 0.20))
    turn = 2.4 * bearing * (1 - 0.63 * blend) + 1.15 * yaw * blend
    max_turn = config["max_angular_radps"]
    speed = min(config["max_reverse_mps"], max(0.022, 0.85 * distance))
    if distance <= config["near_distance_m"]:
        speed = min(speed, config["near_reverse_mps"])
    if x >= 0 or abs(bearing) > 0.65:
        speed = 0.0
    else:
        speed *= max(0.35, 1 - abs(bearing))
    return reply(-speed, min(max_turn, max(-max_turn, turn)))


def dock(state: Record, config: Record, observation: Record) -> Record:
    """Advance the existing dock approach and charge state machine."""
    if state["terminal"] is not None:
        return reply(status=state["terminal"])
    tick = observation["tick"]
    update_track(state, config, observation)
    final_tick = config["deadline_tick"]
    if tick > final_tick:
        return terminal(state, "failed")
    if state["retreating"]:
        return terminal(state, "failed") if tick == final_tick else retreat(state, config, observation)
    if observation["contact"]:
        if "charge" not in config:
            return terminal(state, "docked")
        if state["contact_since"] is None:
            state["contact_since"] = tick
    if state["contact_since"] is not None:
        decision = verify_charge(state, config, observation)
        if decision["status"] == "docked" or tick < final_tick:
            return decision
    if tick == final_tick:
        return terminal(state, "failed")
    return approach(state, config, observation)



def advance(state: Record, config: Record, observation: Record) -> Record:
    """Preserve terminal state and stage before giving authority to the dock loop."""
    if state["terminal"] is not None:
        result = reply(status=state["terminal"])
        return result | {"stage_edge": None} if config.get("navigation") and not state.get("navigation_done") else result
    navigation = staged(state, config, observation)
    if navigation is not None:
        return navigation
    decision = dock(state, config, observation)
    nav = config.get("navigation")
    pose = observation.get("map_pose")
    if (nav is not None and pose is not None and (decision["v_mps"] or decision["w_radps"])
            and not sweep(nav, pose, decision["v_mps"], decision["w_radps"], config["tick_seconds"])):
        return reply()
    return decision
