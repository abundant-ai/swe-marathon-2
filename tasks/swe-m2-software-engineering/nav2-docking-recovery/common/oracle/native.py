"""Guard an actual Jazzy DockRobot mission and cache its durable receipt."""

from contextlib import contextmanager
import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import re
from time import monotonic

def spec_from(path):
    spec = json.loads(path.read_text())
    identifier = spec["request_id"]
    if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", identifier):
        raise ValueError("invalid request_id")
    if spec["dock_type"] != "calibrated_rail":
        raise ValueError("unknown dock type")
    targets = spec["targets"]
    obstacles = spec["obstacles"]
    if not 1 <= len(targets) <= 8 or len(obstacles) > 12:
        raise ValueError("invalid geometry size")
    if len({target["id"] for target in targets}) != len(targets):
        raise ValueError("duplicate target IDs")
    for target in targets:
        if not isinstance(target["id"], str) or not target["id"]:
            raise ValueError("invalid target ID")
        if not all(is_number(target[key]) for key in ("x", "y", "yaw")):
            raise ValueError("invalid target coordinates")
        if abs(target["x"]) > 1 or abs(target["y"]) > 1 or abs(target["yaw"]) > math.pi:
            raise ValueError("target outside commissioned cell")
    for box in obstacles:
        if not all(is_number(box[key]) for key in ("min_x", "max_x", "min_y", "max_y")):
            raise ValueError("invalid obstacle coordinates")
        if box["min_x"] >= box["max_x"] or box["min_y"] >= box["max_y"]:
            raise ValueError("invalid obstacle bounds")
    return spec


def is_number(value):
    return type(value) in (int, float) and math.isfinite(value)


@contextmanager
def journal(directory, identifier):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / (identifier + ".lock")).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield directory / (identifier + ".json")


def receipt_path(directory, identifier):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", identifier):
        raise ValueError("invalid request_id")
    return directory / (identifier + ".json")


def guard(spec, record):
    import rclpy
    from action_msgs.msg import GoalStatus
    from action_msgs.srv import CancelGoal
    from geometry_msgs.msg import Twist
    from nav2_msgs.action import DockRobot, UndockRobot
    from rclpy.action import ActionClient
    from sensor_msgs.msg import BatteryState
    from std_msgs.msg import Bool, UInt64
    from tf2_msgs.msg import TFMessage

    rclpy.init()
    node = rclpy.create_node("guarded_dock_" + str(os.getpid()))
    base = node.create_publisher(Twist, "/cmd_vel", 10)
    qualified = node.create_publisher(BatteryState, "/qualified_battery", 10)
    dock = ActionClient(node, DockRobot, "/dock_robot")
    undock = ActionClient(node, UndockRobot, "/undock_robot")

    armed = False
    boot = None
    contact = False
    contact_at = -1.0
    pose = None
    pose_at = -1.0
    samples = []
    active_target = None
    last_charge = None
    motion_fault = False
    deadline = monotonic() + 30.0

    def stamp(message):
        return message.header.stamp.sec * 10**9 + message.header.stamp.nanosec

    def fresh(sample):
        return 0 <= node.get_clock().now().nanoseconds - stamp(sample) <= 200_000_000

    def within_obstacle(x, y):
        radius = 0.022
        return any(
            math.hypot(max(b["min_x"]-x, x-b["max_x"], 0.0),
                       max(b["min_y"]-y, y-b["max_y"], 0.0)) <= radius
            for b in spec["obstacles"]
        )

    def transform(message):
        nonlocal pose, pose_at
        for item in message.transforms:
            if item.header.frame_id == "odom" and item.child_frame_id == "base_link" and fresh(item):
                rot = item.transform.rotation
                pose = (item.transform.translation.x, item.transform.translation.y,
                        math.atan2(2 * (rot.w * rot.z + rot.x * rot.y),
                                   1 - 2 * (rot.y**2 + rot.z**2)))
                pose_at = monotonic()

    def receive_boot(message):
        nonlocal boot, last_charge, contact, contact_at
        if boot != message.data:
            samples.clear()
            last_charge = None
            boot = message.data
            contact = False
            contact_at = -1.0

    def receive_contact(message):
        nonlocal contact, contact_at, last_charge
        contact = message.data
        contact_at = monotonic()
        if not contact:
            samples.clear()
            last_charge = None

    def send_battery(sample=None):
        message = sample or BatteryState()
        if sample is None:
            message.header.stamp = node.get_clock().now().to_msg()
            message.current = 0.0
            message.present = True
            message.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_NOT_CHARGING
        qualified.publish(message)

    def receive_battery(message):
        nonlocal last_charge
        if boot is None or not fresh(message) or message.header.frame_id != f"charger_boot_{boot}":
            return
        ns = stamp(message)
        if samples and ns <= samples[-1]:
            return
        good = (contact and monotonic() - contact_at <= 0.2 and message.present and
                message.power_supply_status == BatteryState.POWER_SUPPLY_STATUS_CHARGING and
                math.isfinite(message.current) and message.current > 0.5)
        if not good:
            samples.clear()
            last_charge = None
            return
        if samples and ns - samples[-1] > 100_000_000:
            samples.clear()
            last_charge = None
        samples.append(ns)
        if len(samples) >= 4 and samples[-1] - samples[0] >= 60_000_000:
            last_charge = message
            if len(samples) > 32:
                del samples[:-16]

    def charge_ok():
        return bool(last_charge and contact and monotonic() - contact_at <= .2 and
                    0 <= node.get_clock().now().nanoseconds-stamp(last_charge) <= 100_000_000)

    def relay(message):
        nonlocal motion_fault
        if not armed or motion_fault or not pose or monotonic() - pose_at > .2:
            return
        speed = message.linear.x
        turn = message.angular.z
        if not (math.isfinite(speed) and math.isfinite(turn)) or abs(speed) > .181 or abs(turn) > .501:
            motion_fault = True
            base.publish(Twist())
            return
        x, y, yaw = pose
        if any(within_obstacle(x + dt*speed*math.cos(yaw + 0.5*dt*turn),
                               y + dt*speed*math.sin(yaw + 0.5*dt*turn))
               for dt in (.0, .04, .08, .12)):
            motion_fault = True
            base.publish(Twist())
            return
        base.publish(message)

    def spin_for(seconds):
        end = min(deadline, monotonic() + seconds)
        while monotonic() < end:
            rclpy.spin_once(node, timeout_sec=.025)

    def complete(future, seconds):
        end = min(deadline, monotonic() + seconds)
        while not future.done() and monotonic() < end:
            rclpy.spin_once(node, timeout_sec=.025)
        if not future.done():
            raise RuntimeError("native request timed out")
        return future.result()

    def cancel_old_goals():
        for name in ("dock_robot", "undock_robot"):
            client = node.create_client(CancelGoal, f"/{name}/_action/cancel_goal")
            if not client.wait_for_service(timeout_sec=3.0):
                raise RuntimeError(f"native cancel service unavailable for {name}")
            complete(client.call_async(CancelGoal.Request()), 3.0)
            node.destroy_client(client)
        spin_for(.23)

    def run_action(client, goal, seconds):
        nonlocal armed, motion_fault
        motion_fault = False
        handle = complete(client.send_goal_async(goal), 3.0)
        if not handle.accepted:
            return "rejected", None
        armed = True
        pending = handle.get_result_async()
        end = min(deadline, monotonic() + seconds)
        while not pending.done() and not motion_fault and monotonic() < end:
            rclpy.spin_once(node, timeout_sec=.023)
        armed = False
        base.publish(Twist())
        if pending.done():
            answer = pending.result()
            code = int(answer.result.error_code)
            return ("succeeded" if answer.status == GoalStatus.STATUS_SUCCEEDED and answer.result.success
                    else "failed"), code
        complete(handle.cancel_goal_async(), 2.0)
        complete(pending, 3.0)
        return ("unsafe" if motion_fault else "timed_out"), None

    node.create_subscription(Twist, "/nav2_cmd_vel", relay, 10)
    node.create_subscription(TFMessage, "/tf", transform, 20)
    node.create_subscription(UInt64, "/charger/boot", receive_boot, 10)
    node.create_subscription(Bool, "/charger/contact", receive_contact, 10)
    node.create_subscription(BatteryState, "/charger/battery_state", receive_battery, 20)
    node.create_timer(.04, lambda: send_battery(last_charge if charge_ok() else None))

    def result(status):
        return {"request_id": spec["request_id"], "status": status,
                "boot": boot if status == "docked" else None,
                "target_id": active_target if status == "docked" else None,
                "attempts": record["attempts"]}

    try:
        if not dock.wait_for_server(timeout_sec=4.0) or not undock.wait_for_server(timeout_sec=4.0):
            raise RuntimeError("Jazzy docking actions unavailable")
        if record["resumes"]:
            cancel_old_goals()
        spin_for(.27)
        targets = [target for target in spec["targets"] if not within_obstacle(target["x"], target["y"])]
        for index, target in enumerate(targets):
            if monotonic() >= deadline:
                break
            active_target = target["id"]
            msg = DockRobot.Goal(use_dock_id=False, dock_type=spec["dock_type"],
                                 navigate_to_staging_pose=False)
            msg.dock_pose.header.frame_id = "odom"
            msg.dock_pose.pose.position.x = target["x"]
            msg.dock_pose.pose.position.y = target["y"]
            msg.dock_pose.pose.orientation.z = math.sin(target["yaw"] / 2)
            msg.dock_pose.pose.orientation.w = math.cos(target["yaw"] / 2)
            status, code = run_action(dock, msg, 10.5)
            record["attempts"].append({"action": "dock", "target_id": active_target,
                                       "status": status, "error_code": code})
            if status == "succeeded" and charge_ok():
                return result("docked")
            if index + 1 < len(targets) and code == DockRobot.Result.FAILED_TO_CHARGE:
                msg = UndockRobot.Goal(dock_type=spec["dock_type"], max_undocking_time=6.0)
                status, code = run_action(undock, msg, 6.25)
                record["attempts"].append({"action": "undock", "target_id": active_target,
                                           "status": status, "error_code": code})
                if status != "succeeded":
                    break
            else:
                break
        return result("blocked")
    finally:
        base.publish(Twist())
        node.destroy_node()
        rclpy.try_shutdown()


def command(argv, save):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    execute = sub.add_parser("guarded-dock")
    execute.add_argument("--spec", required=True, type=Path)
    execute.add_argument("--state", required=True, type=Path)
    execute.add_argument("--output", required=True, type=Path)
    inspect = sub.add_parser("dock-receipt")
    inspect.add_argument("--state", required=True, type=Path)
    inspect.add_argument("--request-id", required=True)
    args = parser.parse_args(argv)
    try:
        if args.operation == "dock-receipt":
            path = receipt_path(args.state, args.request_id)
            if not path.exists():
                return 1
            record = json.loads(path.read_text())
            payload = record["receipt"] or {"request_id": args.request_id, "status": "accepted"}
            print(json.dumps(payload, sort_keys=True))
            return 0
        spec = spec_from(args.spec)
        with journal(args.state, spec["request_id"]) as path:
            if path.exists():
                record = json.loads(path.read_text())
                if spec != record["spec"]:
                    raise ValueError("request ID is already bound to another specification")
                if record["receipt"] is None:
                    record["resumes"] += 1
            else:
                record = {"spec": spec, "receipt": None, "resumes": 0, "attempts": []}
            if record["receipt"] is None:
                save(path, record)
                record["receipt"] = guard(spec, record)
                save(path, record)
            save(args.output, record["receipt"])
        return 0
    except (RuntimeError, ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f"{error}\n")
