"""Isolate an actively charging dock and release a measured navigation corridor."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from time import monotonic

from .departure_gate import IsolationGate
from .native import is_number, journal, receipt_path


TF_AGE_NS = 150_000_000
APPROACH_TOLERANCE = .012
STAGING_POSITION_TOLERANCE = .027
STAGING_YAW_TOLERANCE = .12
CORRIDOR_WIDTH = .035
WATCHDOG = .095
REQUEST_DURATION = 24.0


def angle(value):
    return math.remainder(value, 2 * math.pi)


def project(origin, pose):
    """Resolve a measured pose into longitudinal and lateral corridor coordinates."""
    dx, dy = pose[0] - origin[0], pose[1] - origin[1]
    along = math.cos(origin[2]) * dx + math.sin(origin[2]) * dy
    across = -math.sin(origin[2]) * dx + math.cos(origin[2]) * dy
    return along, across, angle(pose[2] - origin[2])


def load_spec(path):
    spec = json.loads(path.read_text())
    if not isinstance(spec.get("request_id"), str):
        raise ValueError("request_id must be a string")
    receipt_path(Path("."), spec["request_id"])
    if spec["dock_type"] != "calibrated_rail":
        raise ValueError("unknown departure dock type")
    for name in ("seat_pose", "staging_pose"):
        pose = spec[name]
        if not isinstance(pose, list) or len(pose) != 3 or not all(map(is_number, pose)):
            raise ValueError("invalid surveyed pose")
    along, across, yaw = project(spec["seat_pose"], spec["staging_pose"])
    if not -.60 <= along <= -.15 or abs(across) > 1e-6 or abs(yaw) > 1e-6:
        raise ValueError("staging must be directly behind the surveyed seat")
    if not is_number(spec["isolation_timeout_s"]) or not 2 <= spec["isolation_timeout_s"] <= 6:
        raise ValueError("invalid isolation timeout")
    return spec


class Departure:
    """Acquire independent charger authority and control the remaining departure."""

    def __init__(self, node, spec, state, commit):
        from action_msgs.msg import GoalStatusArray
        from action_msgs.srv import CancelGoal
        from geometry_msgs.msg import Twist
        from nav2_msgs.action import UndockRobot
        from rclpy.action import ActionClient
        from rclpy.qos import qos_profile_action_status_default
        from std_msgs.msg import String
        from tf2_msgs.msg import TFMessage

        self.node, self.spec, self.state, self.commit = node, spec, state, commit
        self.Twist, self.String, self.UndockRobot, self.CancelGoal = Twist, String, UndockRobot, CancelGoal
        self.gate = IsolationGate(spec["request_id"])
        self.deadline = state["accepted_at"] + REQUEST_DURATION
        self.seat, self.staging = spec["seat_pose"], spec["staging_pose"]
        self.staging_along = project(self.seat, self.staging)[0]
        self.pose = None
        self.tf_stamp = None
        self.native = ActionClient(node, UndockRobot, "/undock_robot")
        self.cancel = node.create_client(CancelGoal, "/undock_robot/_action/cancel_goal")
        self.command = node.create_publisher(Twist, "/cmd_vel", 10)
        self.isolate = node.create_publisher(String, "/departure/isolate", 10)
        self.subscriptions = [
            node.create_subscription(String, "/departure/power", self.observe, 25),
            node.create_subscription(TFMessage, "/tf", self.transform, 20),
            node.create_subscription(Twist, "/nav2_cmd_vel", self.relay, 20),
            node.create_subscription(GoalStatusArray, "/undock_robot/_action/status",
                                     self.observe_status, qos_profile_action_status_default),
        ]
        self.armed = False
        self.bad_motion = False
        self.armed_stamp = 0
        self.statuses = {}

    def clock(self):
        return self.node.get_clock().now().nanoseconds

    def observe(self, message):
        try:
            self.gate.observe(json.loads(message.data), self.clock())
        except (TypeError, ValueError):
            pass

    def transform(self, message):
        for sample in message.transforms:
            if (sample.header.frame_id, sample.child_frame_id) != ("odom", "base_link"):
                continue
            stamp = sample.header.stamp.sec * 10**9 + sample.header.stamp.nanosec
            if (not 0 <= self.clock() - stamp <= TF_AGE_NS
                    or self.tf_stamp is not None and self.tf_stamp >= stamp):
                continue
            p, q = sample.transform.translation, sample.transform.rotation
            if not all(map(math.isfinite, (p.x, p.y, q.x, q.y, q.z, q.w))):
                self.tf_stamp = self.pose = None
                continue
            self.tf_stamp = stamp
            self.pose = (p.x, p.y, math.atan2(2 * (q.w*q.z + q.x*q.y),
                                             1 - 2 * (q.y*q.y + q.z*q.z)))

    def observe_status(self, message):
        self.statuses = {bytes(item.goal_info.goal_id.uuid): item.status
                         for item in message.status_list}

    def fresh_pose(self):
        return self.pose is not None and 0 <= self.clock() - self.tf_stamp <= TF_AGE_NS

    def clear(self, pose):
        along, lateral, yaw = project(self.seat, pose)
        return (self.staging_along - STAGING_POSITION_TOLERANCE <= along <= .015
                and abs(lateral) <= CORRIDOR_WIDTH and abs(yaw) <= .18)

    def staged(self):
        return (self.fresh_pose() and math.dist(self.pose[:2], self.staging[:2]) <= STAGING_POSITION_TOLERANCE
                and abs(angle(self.pose[2] - self.staging[2])) <= STAGING_YAW_TOLERANCE)

    def authorized(self):
        return (monotonic() < self.deadline and self.fresh_pose() and self.clear(self.pose)
                and self.gate.qualified(self.clock()))

    def still_seated(self):
        return (self.fresh_pose() and math.dist(self.pose[:2], self.seat[:2]) <= APPROACH_TOLERANCE
                and self.gate.contact)

    def prospective_clear(self, linear, angular):
        x, y, yaw = self.pose
        for seconds in (WATCHDOG / 2, WATCHDOG):
            if abs(angular) < 1e-9:
                px, py = x + linear * seconds * math.cos(yaw), y + linear * seconds * math.sin(yaw)
            else:
                at = yaw + seconds * angular
                px = x + linear / angular * (math.sin(at) - math.sin(yaw))
                py = y + linear / angular * (math.cos(yaw) - math.cos(at))
            if not self.clear((px, py, yaw + seconds * angular)):
                return False
        return True

    def relay(self, twist, info):
        if not self.armed:
            return
        stamp = info.get("source_timestamp", 0)
        if stamp < self.armed_stamp or not 0 <= self.clock() - stamp <= 100_000_000:
            return
        values = (twist.linear.x, twist.linear.y, twist.linear.z,
                  twist.angular.x, twist.angular.y, twist.angular.z)
        if (not self.authorized() or not all(map(math.isfinite, values))
                or not -.180001 <= values[0] <= .000001 or abs(values[5]) > .500001
                or any(abs(value) > 1e-7 for value in values[1:5])
                or not self.prospective_clear(values[0], values[5])):
            self.bad_motion = True
            self.stop()
            return
        twist.linear.x = max(-.18, min(0., values[0]))
        twist.angular.z = max(-.5, min(.5, values[5]))
        self.command.publish(twist)

    def stop(self):
        self.armed = False
        self.command.publish(self.Twist())

    def step(self, deadline):
        import rclpy

        rclpy.spin_once(self.node, timeout_sec=max(0., min(.025, deadline - monotonic())))

    def wait(self, predicate, timeout):
        end = min(self.deadline, monotonic() + timeout)
        while monotonic() < end and not predicate():
            self.step(end)
        return bool(predicate())

    def cancel_orphan(self):
        from action_msgs.msg import GoalStatus

        if not self.cancel.wait_for_service(timeout_sec=2.):
            return False
        pending = self.cancel.call_async(self.CancelGoal.Request())
        if not self.wait(pending.done, 2.):
            return False
        answer = pending.result()
        targets = {bytes(item.goal_id.uuid) for item in answer.goals_canceling}
        terminal = {GoalStatus.STATUS_SUCCEEDED, GoalStatus.STATUS_ABORTED, GoalStatus.STATUS_CANCELED}
        return not targets or self.wait(
            lambda: all(self.statuses.get(identity) in terminal for identity in targets), 2.)

    def acquire_isolation(self):
        if not self.wait(lambda: self.gate.boot is not None and self.fresh_pose(), 2.):
            return False
        if not self.state["started"] and not self.state["isolation_requested"]:
            if not self.wait(lambda: self.gate.seated_live(self.clock()) and self.still_seated(), 1.5):
                return False
        start = self.state.get("isolation_started_at")
        if self.state["started"] or start is None:
            start = monotonic()
        end = min(self.deadline, start + self.spec["isolation_timeout_s"])
        next_request = 0.
        while monotonic() < end:
            if not self.state["started"]:
                if not self.fresh_pose():
                    self.step(end)
                    continue
                if not self.still_seated():
                    return False
            if self.gate.qualified(self.clock()):
                return True
            if monotonic() >= next_request:
                if not self.state["isolation_requested"]:
                    self.state.update(isolation_requested=True, isolation_started_at=start)
                    self.commit()
                packet = {"transaction_id": self.spec["request_id"], "boot": self.gate.boot}
                self.isolate.publish(self.String(data=json.dumps(packet)))
                next_request = monotonic() + .12
            self.step(end)
        return False

    def native_retreat(self):
        from action_msgs.msg import GoalStatus

        if not self.native.wait_for_server(timeout_sec=2.) or not self.authorized():
            return False
        self.state["started"] = True
        self.commit()
        limit = min(9., max(0., self.deadline - monotonic() - .5))
        goal = self.UndockRobot.Goal(dock_type=self.spec["dock_type"], max_undocking_time=limit)
        pending = self.native.send_goal_async(goal)
        if not self.wait(pending.done, 2.):
            self.cancel_orphan()
            return False
        handle = pending.result()
        if not handle.accepted:
            return False
        result = handle.get_result_async()
        self.armed_stamp = self.clock()
        self.armed = True

        def finished():
            if not self.authorized():
                self.bad_motion = True
                self.stop()
            return result.done() or self.bad_motion

        self.wait(finished, limit)
        self.stop()
        if not result.done():
            cancel = handle.cancel_goal_async()
            self.wait(cancel.done, .8)
        if not result.done() or self.bad_motion:
            return False
        outcome = result.result()
        return outcome.status == GoalStatus.STATUS_SUCCEEDED and outcome.result.success

    def remaining_route(self):
        """Track the surveyed axis from the measured post-interruption pose."""
        while monotonic() < self.deadline and self.authorized():
            if self.staged():
                self.stop()
                return True
            along, lateral, yaw = project(self.seat, self.pose)
            remain = along - self.staging_along
            if remain <= 0:
                break
            command = self.Twist()
            command.linear.x = -min(.115, max(.023, 1.55 * remain))
            command.angular.z = min(.20, max(-.20, 3.0 * lateral - yaw))
            if not self.prospective_clear(command.linear.x, command.angular.z):
                break
            self.command.publish(command)
            next_step = min(self.deadline, monotonic() + .023)
            while monotonic() < next_step:
                self.step(next_step)
        self.stop()
        return False

    def finish(self):
        self.stop()
        end = min(self.deadline, monotonic() + .15)
        while monotonic() < end and self.staged() and self.authorized():
            self.step(end)
        return monotonic() >= end and self.staged() and self.authorized()

    def run(self, resumed):
        self.stop()
        if resumed and not self.cancel_orphan():
            return None
        if not self.acquire_isolation():
            return None
        if resumed and self.state["started"] and not self.still_seated():
            success = self.remaining_route()
        else:
            success = self.native_retreat()
        return self.gate.boot if success and self.finish() else None


def run_departure(spec, state, commit, resumed):
    import rclpy

    rclpy.init()
    node = rclpy.create_node("guarded_undock")
    try:
        worker = Departure(node, spec, state, commit)
        try:
            return worker.run(resumed)
        finally:
            worker.stop()
    finally:
        node.destroy_node()
        rclpy.shutdown()


def command(argv, save):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    execute = sub.add_parser("guarded-undock")
    execute.add_argument("--spec", required=True, type=Path)
    execute.add_argument("--state", required=True, type=Path)
    execute.add_argument("--output", required=True, type=Path)
    inspect = sub.add_parser("undock-receipt")
    inspect.add_argument("--state", required=True, type=Path)
    inspect.add_argument("--request-id", required=True)
    args = parser.parse_args(argv)
    directory = args.state / "powered-departure"
    try:
        if args.operation == "undock-receipt":
            path = receipt_path(directory, args.request_id)
            if not path.exists():
                return 1
            record = json.loads(path.read_text())
            print(json.dumps(record["receipt"] or {"request_id": args.request_id, "status": "accepted"}))
            return 0
        spec = load_spec(args.spec)
        with journal(directory, "_motion_owner"):
            path = receipt_path(directory, spec["request_id"])
            resumed = path.exists()
            if resumed:
                state = json.loads(path.read_text())
                if state["spec"] != spec:
                    raise ValueError("request ID already has a different specification")
            else:
                state = {"spec": spec, "receipt": None, "accepted_at": monotonic(),
                         "started": False, "isolation_requested": False}
            if state["receipt"] is None:
                def commit():
                    save(path, state)

                commit()
                boot = run_departure(spec, state, commit, resumed)
                state["receipt"] = {"request_id": spec["request_id"],
                                    "status": "departed" if boot is not None else "blocked",
                                    "boot": boot}
                commit()
            save(args.output, state["receipt"])
        return 0
    except (RuntimeError, ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f"{error}\n")
