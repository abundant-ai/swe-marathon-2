"""Hidden, deterministic robot driver and independent footprint checker."""

import collections
import json
import os
import select
import signal
import subprocess
import sys
import time

if os.name == "posix":
    import pwd


class Rejected(Exception):
    """The submitted coordinator did not satisfy an observed requirement."""


class PhysicalConflict(Rejected):
    """A grant overlaps another robot's occupied or reserved resources."""


def require(condition, message):
    if not condition:
        raise Rejected(message)


class Transport:
    def __init__(self, app, site_file, state):
        self.app = app
        self.site_file = site_file
        self.state = state
        self.start()

    def start(self):
        identity = {}
        if os.name == "posix" and os.geteuid() == 0:
            try:
                candidate = pwd.getpwnam("candidate")
            except KeyError:
                candidate = pwd.getpwnam("nobody")
            identity = dict(user=candidate.pw_uid, group=candidate.pw_gid, extra_groups=[])
        env = {
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "HOME": str(self.state),
            "LC_ALL": "C.UTF-8",
        }
        self.proc = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-m",
                "fleet_recovery",
                "--site",
                str(self.site_file),
                "--state",
                str(self.state),
            ],
            cwd=self.app,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            **identity,
        )
        self.buffer = b""

    def exchange(self, event):
        deadline = time.monotonic() + 3
        try:
            self.proc.stdin.write(json.dumps(event).encode() + b"\n")
            self.proc.stdin.flush()
        except BrokenPipeError:
            raise Rejected("the coordinator exited before accepting an event") from None
        fd = self.proc.stdout.fileno()
        while b"\n" not in self.buffer:
            wait = max(0, deadline - time.monotonic())
            require(bool(select.select([fd], [], [], wait)[0]), "no flushed response within 3 seconds")
            chunk = os.read(fd, 4096)
            require(bool(chunk), "the coordinator exited before writing a response")
            self.buffer += chunk
            require(len(self.buffer) <= 1_000_000, "response exceeds 1 MB")
        line, self.buffer = self.buffer.split(b"\n", 1)
        try:
            response = json.loads(line)
        except (ValueError, UnicodeError):
            raise Rejected("the coordinator response is not JSON") from None
        require(isinstance(response, dict) and isinstance(response.get("commands"), list),
                "a response must contain a commands list")
        if event["kind"] != "tick":
            require(response["commands"] == [], "a non-tick event returned commands")
        return response

    def close(self):
        try:
            os.killpg(self.proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        self.proc.wait()
        self.proc.stdin.close()
        self.proc.stdout.close()

    def restart(self):
        self.close()
        self.start()


class World:
    def __init__(self, transport, site):
        self.transport = transport
        self.tick_now = 0
        self.event_count = 0
        self.nodes = {
            node: set(resources) | {f"node:{node}"}
            for node, resources in site["nodes"].items()
        }
        self.robots = site["robots"]
        self.lanes = {(lane["from"], lane["to"]): lane for lane in site["lanes"]}
        self.positions = {robot: entry["start"] for robot, entry in self.robots.items()}
        self.online = dict.fromkeys(self.robots, True)
        self.sequences = dict.fromkeys(self.robots, 0)
        self.jobs = {}
        self.occupancy = {}
        self.closures = set()
        self.seen_commands = {}
        self.history = []
        self.fault = None

    def event(self, kind, **fields):
        self.event_count += 1
        return {"id": f"log-{self.event_count:04d}", "time": self.tick_now,
                "kind": kind, **fields}

    def send(self, kind, **fields):
        return self.transport.exchange(self.event(kind, **fields))

    def job(self, name, pickup, dropoff, eligible, **fields):
        self.jobs[name] = {
            "pickup": pickup, "dropoff": dropoff, "eligible": eligible,
            "owner": None, "picked": False, "dropped_at": None, "canceled": False,
        }
        self.send("job", job=name, pickup=pickup, dropoff=dropoff, eligible=eligible, **fields)

    def cancel(self, name):
        job = self.jobs[name]
        picking = any(
            motion["command"]["job"] == name and motion["command"]["kind"] == "pickup"
            for motion in self.occupancy.values()
        )
        if not job["picked"] and not picking:
            job["canceled"] = True
        self.send("cancel", job=name)

    def closure(self, resource, closed):
        if closed:
            self.closures.add(resource)
        else:
            self.closures.discard(resource)
        self.send("closure", resource=resource, closed=closed)

    def report(self, robot, online, node, settled=None, *, stale=False, observation_only=False):
        self.sequences[robot] += not stale
        if not stale and not observation_only:
            self.online[robot] = online
        self.send("telemetry", robot=robot, seq=self.sequences[robot] - 1 if stale
                  else self.sequences[robot], online=online, node=node, settled=settled)

    def resources(self, robot):
        if robot in self.occupancy:
            return self.occupancy[robot]["resources"]
        return self.nodes[self.positions[robot]]

    def apply(self, response, *, replay=False):
        for command in response["commands"]:
            require(isinstance(command, dict), "a command must be an object")
            require(all(isinstance(command.get(key), str) and command[key]
                        for key in ("command", "robot", "job", "kind")),
                    "command identity fields must be nonempty strings")
            identity = command["command"]
            if identity in self.seen_commands:
                require(replay and self.seen_commands[identity] == command,
                        "a new command reused an earlier identity")
                continue
            require(not replay, "retransmission introduced an unknown command")
            robot = command["robot"]
            job_id = command["job"]
            kind = command["kind"]
            require(robot in self.robots and job_id in self.jobs, "unknown robot or job")
            job = self.jobs[job_id]
            require(self.online[robot], f"issued a new command to offline robot {robot}")
            require(robot not in self.occupancy, f"overlapping commands for robot {robot}")
            require(not job["canceled"] and job["dropped_at"] is None and robot in job["eligible"],
                    "issued a command for a canceled, delivered or ineligible job")
            require(job["owner"] in (None, robot), "gave an assigned job to another robot")
            require(not any(other["owner"] == robot and other is not job
                            and not other["canceled"] and other["dropped_at"] is None
                            for other in self.jobs.values()),
                    "assigned multiple active jobs to one robot")
            node = self.positions[robot]
            footprint = self.nodes[node]
            if kind == "move":
                target = command.get("to")
                require(isinstance(target, str) and command.get("from") == node
                        and (node, target) in self.lanes, "move did not use a valid outgoing lane")
                lane = self.lanes[node, target]
                config = self.robots[robot]
                if config["mode"] == "loop":
                    loop = config["loop"]
                    require(target == loop[(loop.index(node) + 1) % len(loop)],
                            "fixed-loop robot was sent down an incorrect lane")
                footprint = footprint | self.nodes[target] | set(lane["resources"])
                escaping = self.nodes[node] - self.nodes[target]
                require(not (footprint & (self.closures - escaping)),
                        "acquired a closed resource without using the egress rule")
                due = self.tick_now + lane["ticks"]
            else:
                require(kind in ("pickup", "drop"), "unknown command kind")
                station = job["pickup"] if kind == "pickup" else job["dropoff"]
                require(command.get("node") == node == station and job["picked"] == (kind == "drop"),
                        "parcel service violated station or pickup/drop ordering")
                target = node
                due = self.tick_now + 1
            for other in self.robots:
                if other == robot:
                    continue
                collisions = footprint & self.resources(other)
                if collisions:
                    raise PhysicalConflict(f"physical overlap with {other} on {sorted(collisions)}")
            if self.fault is not None:
                fault = self.fault(command, due, target)
                if fault is not None:
                    due, target = fault
            job["owner"] = robot
            self.seen_commands[identity] = command
            self.occupancy[robot] = {
                "command": command, "resources": footprint, "due": due, "target": target,
            }
            self.history.append((self.tick_now, command))

    def advance(self, tick):
        self.tick_now = tick
        for robot, motion in tuple(self.occupancy.items()):
            if motion["due"] != tick:
                continue
            command = motion["command"]
            job = self.jobs[command["job"]]
            self.positions[robot] = motion["target"]
            del self.occupancy[robot]
            if command["kind"] == "pickup":
                job["picked"] = True
            elif command["kind"] == "drop":
                job["dropped_at"] = tick
            self.report(robot, True, motion["target"], command["command"])

    def tick(self, tick):
        self.advance(tick)
        self.apply(self.send("tick"))

    def run_until(self, start, end):
        for tick in range(start, end + 1):
            self.tick(tick)

    def delivered(self, name):
        return self.jobs[name]["dropped_at"] is not None
