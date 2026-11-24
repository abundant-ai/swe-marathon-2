"""Authored independent point-mass flight, measurement faults and waypoint truth."""

from math import dist, hypot
from pathlib import Path
import json

from transport import Driver, Record, require


def local(stamp: int, p: list[float], v: list[float], offset: list[float],
          counters: list[int], delta: list[float], **extra: object) -> Record:
    """Encode the estimator's moving local frame with independent clocks."""
    return {"timestamp": stamp + 1700, "timestamp_sample": stamp,
            "position": [a+b for a,b in zip(p, offset, strict=True)], "velocity": v.copy(),
            "xy_valid": True, "z_valid": True, "xy_reset_counter": counters[0],
            "z_reset_counter": counters[1], "delta_xy": delta[:2], "delta_z": delta[2], **extra}


def mission(app: Path, root: Path, case: Record | None = None) -> Record:
    """Fly the submitted acceleration commands and compare against physical state."""
    case = {} if case is None else case
    dt = 0.1
    targets = case.get("targets", [[0.6, -0.42, -2.4], [1.5, 0.14, -2.87]])
    cfg = {"dt": dt, "waypoints": targets, "max_accel": 0.85, "position_tolerance": 0.095,
           "speed_tolerance": 0.13, "dwell_ticks": 3, "deadline": case.get("deadline", 205), "max_age_us": 20_000}
    if case.get("inertial"):
        cfg["max_inertial_ticks"] = case["inertial"]
    config = root / "mission.json"
    config.write_text(json.dumps(cfg))
    private = root / "candidate"
    private.mkdir(mode=0o777)
    private.chmod(0o777)
    driver = Driver(app, config, private)
    x, v = [0.0, 0.0, -1.85], [0.0] * 3
    acceleration, offset = [0.0] * 3, [0.0] * 3
    counter, delta = [254, 255], [0.0] * 3
    tracker_stale = [False, False]
    chain = None
    dead = 0
    progress = dwell = 0
    peak = 0.0
    mode_counts = {"track": 0, "dead_reckon": 0, "hold": 0}
    terminal_tick = None
    try:
        for tick in range(cfg["deadline"] + 1):
            stamp = 1_000_000 + tick * 100_000
            if tick in case.get("resets", {}):
                advance, delta = case["resets"][tick]
                for i, n in enumerate(advance):
                    counter[i] = (counter[i] + n) % 256
                    tracker_stale[i] |= n > 1
                offset = [a + b for a, b in zip(offset, delta, strict=True)]
            sample = local(stamp, x, v, offset, counter, delta)
            if tick == case.get("anchor"):
                sample["anchor"] = [x[0], x[1], None]
                tracker_stale[0] = False
            dropout = any(a <= tick < b for a,b in case.get("drop", []))
            out_of_order = tick in case.get("stale", ())
            if dropout:
                sample = None
            elif out_of_order:
                sample["timestamp_sample"] -= 200_000
            elif tick in case.get("invalid_z", ()):
                sample["z_valid"] = False
            imu = {"from_tick": tick - 1, "accel": acceleration}
            if tick in case.get("bad_imu", ()):
                imu["from_tick"] = tick - 2
            observation = {"tick": tick, "now_us": stamp + 1700, "local": sample, "imu": imu}
            trusted = (sample is not None and not out_of_order and sample["z_valid"] and not any(tracker_stale))
            if trusted:
                desired_mode, dead, chain = "track", 0, True
            elif chain and dead < cfg.get("max_inertial_ticks", 0) and imu["from_tick"] == tick - 1:
                desired_mode, dead = "dead_reckon", dead + 1
            else:
                desired_mode, chain = "hold", False
            if trusted and dist(x, targets[progress]) <= cfg["position_tolerance"] + 1e-10 and hypot(*v) <= cfg["speed_tolerance"] + 1e-10:
                dwell += 1
                if dwell >= cfg["dwell_ticks"]:
                    progress += 1
                    dwell = 0
            else:
                dwell = 0
            response = driver.exchange(observation)
            a = response.get("acceleration")
            require(type(a) is list and len(a) == 3 and all(type(value) in (float,int)
                    and -cfg["max_accel"]-1e-9 <= value <= cfg["max_accel"]+1e-9 for value in a),
                    "command exceeded the acceleration envelope")
            require(response.get("waypoint") == progress, "incorrect waypoint advancement from physical dwell")
            mode = response.get("mode")
            estimate = response.get("estimate")
            if progress == len(targets):
                require(mode == "complete" and a == [0]*3, "did not complete after the last qualified dwell")
                terminal_tick = tick
                break
            if tick == cfg["deadline"]:
                require(mode == "abort" and a == [0]*3, "missed neutral abort at mission deadline")
                terminal_tick = tick
                break
            require(mode == desired_mode, f"tick {tick}: expected {desired_mode}, observed {mode}")
            mode_counts[mode] += 1
            if desired_mode == "hold":
                require(a == [0]*3 and estimate is None, "hold exposed unsupported estimate or acceleration")
            else:
                require(type(estimate) is list and len(estimate) == 3 and all(type(value) in (int,float) for value in estimate),
                        "state estimate missing")
                error = dist(estimate, x)
                require(error < 1e-8, f"physical position error {error:.6f} at tick {tick}")
                peak = max(peak, error)
            # Analytic constant-acceleration step with an independently specified drag.
            acceleration = [u - 0.22 * vel for u, vel in zip(a, v, strict=True)]
            x = [p + dt * vel + 0.5 * dt**2 * aa for p,vel,aa in zip(x,v,acceleration,strict=True)]
            v = [vel + dt * aa for vel,aa in zip(v,acceleration,strict=True)]
            require(-4.2 <= x[2] <= -0.6 and abs(x[0]) <= 2.7 and abs(x[1]) <= 2.1,
                    "physical vehicle left the simulated flight envelope")
        expected = "abort" if case.get("abort") else "complete"
        require(mode == expected, f"expected {expected}, got {mode}")
        require(mode_counts["dead_reckon"] >= case.get("minimum_dead_reckon", 0)
                and mode_counts["hold"] >= case.get("minimum_hold", 0), "fault branch was not exercised")
        return {"terminal": mode, "tick": terminal_tick, "actual_pose_m": x, "peak_estimation_error_m": peak,
                "tracking_modes": mode_counts}
    finally:
        driver.close()
