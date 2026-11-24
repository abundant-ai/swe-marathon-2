"""Reconstruct a commissioning capture or supervise an offline NED mission."""

import argparse
import json
from math import hypot
from pathlib import Path
import sys
import tempfile

from .estimator import Estimate, Record, series
from .supervisor import Supervisor, guarded_acceleration


def replay(capture: Path, output: Path) -> None:
    """Write a complete recovered capture only after every record validates."""
    tracker, stale, unresolved, rows = Estimate(), 0, 0, []
    with capture.open() as stream:
        for line in stream:
            if not tracker.ingest(json.loads(line)):
                stale += 1
                continue
            unresolved += any(tracker.missing)
            rows.append({"timestamp_sample": tracker.stamp, "position": tracker.position.copy()})
    with tempfile.NamedTemporaryFile(mode="w", dir=output.parent, delete=False) as stream:
        temp = Path(stream.name)
        try:
            json.dump({"rows": rows, "stale": stale, "unresolved": unresolved}, stream, allow_nan=False)
            stream.close()
            temp.replace(output)
        finally:
            temp.unlink(missing_ok=True)


class Mission:
    """Consume sensor and inertial evidence before publishing physical authority."""

    def __init__(self, spec: Record) -> None:
        """Start the commissioned mission with no estimator or inertial state."""
        self.spec = spec
        self.tracker = Estimate()
        self.target = 0
        self.dwell = 0
        self.tick = -1
        self.state: tuple[list, list] | None = None
        self.inertial = 0
        self.terminal = None

    def response(self, mode: str, *, command: list | None = None, estimate: list | None = None) -> Record:
        """Return authority, estimate, and the exact next waypoint index."""
        return {"mode": mode, "acceleration": [0.0] * 3 if command is None else command,
                "estimate": estimate, "waypoint": self.target}

    def observe(self, observation: Record) -> Record:
        """Track a fresh estimate or propagate one exactly supported inertial interval."""
        cfg, t = self.spec, observation["tick"]
        self.tick = t
        if self.terminal is not None:
            return self.response(self.terminal)
        local = observation["local"]
        trusted = False
        if local is not None and local["timestamp_sample"] <= observation["now_us"]:
            fresh = self.tracker.ingest(local)
            trusted = (fresh and observation["now_us"] - self.tracker.stamp <= cfg["max_age_us"]
                       and None not in self.tracker.position)
        if trusted:
            self.state = self.tracker.position.copy(), self.tracker.velocity.copy()
            self.inertial = 0
            mode = "track"
        else:
            self.dwell = 0
            imu = observation.get("imu")
            if (self.state is not None and self.inertial < cfg.get("max_inertial_ticks", 0)
                    and imu is not None and imu["from_tick"] == t - 1):
                p, v = self.state
                a = series(imu["accel"], 3)
                dt = cfg["dt"]
                self.state = ([x + y * dt + 0.5 * z * dt * dt for x, y, z in zip(p, v, a, strict=True)],
                              [y + z * dt for y, z in zip(v, a, strict=True)])
                self.inertial += 1
                mode = "dead_reckon"
            else:
                self.state = None
                mode = "hold"
        if t >= cfg["deadline"]:
            self.terminal = "abort"
            return self.response(self.terminal)
        if self.state is None:
            return self.response(mode)
        position, velocity = self.state
        waypoints = cfg["waypoints"]
        error = [x - y for x, y in zip(waypoints[self.target], position, strict=True)]
        if mode == "track" and hypot(*error) <= cfg["position_tolerance"] and hypot(*velocity) <= cfg["speed_tolerance"]:
            self.dwell += 1
            if self.dwell >= cfg["dwell_ticks"]:
                self.target += 1
                self.dwell = 0
                if self.target == len(waypoints):
                    self.terminal = "complete"
                    return self.response(self.terminal, estimate=position)
                error = [x - y for x, y in zip(waypoints[self.target], position, strict=True)]
        else:
            self.dwell = 0
        cap = cfg["max_accel"]
        command = [max(-cap, min(cap, 1.7 * residual - 2.2 * speed))
                   for residual, speed in zip(error, velocity, strict=True)]
        if "supervisor" in cfg:
            guard=cfg["supervisor"]
            if mode=="dead_reckon":
                command=[max(-cap,min(cap,-speed/cfg["dt"])) for speed in velocity]
            else:
                command=[guarded_acceleration(x,v,u,cfg["dt"],cap,lo,hi)
                         for x,v,u,lo,hi in zip(position,velocity,command,guard["min_ned"],guard["max_ned"],strict=True)]
        return self.response(mode, command=command, estimate=position)


def main() -> int:
    """Run the reconstructed capture ledger or one live process."""
    parser = argparse.ArgumentParser()
    modes = parser.add_subparsers(dest="command", required=True)
    capture = modes.add_parser("replay")
    capture.add_argument("--input", type=Path, required=True)
    capture.add_argument("--output", type=Path, required=True)
    live = modes.add_parser("stream")
    live.add_argument("--spec", type=Path, required=True)
    commissioning = modes.add_parser("commission")
    commissioning.add_argument("--spec", type=Path, required=True)
    commissioning.add_argument("--output", type=Path, required=True)
    flight = modes.add_parser("fly")
    flight.add_argument("--spec", type=Path, required=True)
    flight.add_argument("--calibration", type=Path, required=True)
    landing = modes.add_parser("land-assured")
    landing.add_argument("--spec", type=Path, required=True)
    landing.add_argument("--calibration", type=Path, required=True)
    moving = modes.add_parser("land-moving")
    moving.add_argument("--spec", type=Path, required=True)
    relative = modes.add_parser("land-relative")
    relative.add_argument("--spec", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "replay":
            replay(args.input, args.output)
        elif args.command == "commission":
            from .commission import commission
            commission(args.spec,args.output)
        elif args.command == "land-assured":
            from .landing import fly_assured
            fly_assured(args.spec,args.calibration)
        elif args.command == "land-relative":
            from .relative_landing import land_relative
            land_relative(args.spec)
        elif args.command == "land-moving":
            from .moving_landing import land_moving
            land_moving(args.spec)
        elif args.command == "fly":
            from .rigid_flight import fly
            fly(args.spec,args.calibration)
        else:
            cfg=json.loads(args.spec.read_text())
            mission=Mission(cfg)
            if "supervisor" in cfg:
                mission=Supervisor(mission)
            for line in sys.stdin:
                print(json.dumps(mission.observe(json.loads(line)), allow_nan=False), flush=True)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(f"px4 recovery: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
