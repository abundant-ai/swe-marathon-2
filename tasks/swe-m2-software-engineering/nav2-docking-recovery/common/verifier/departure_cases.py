"""Independent Jazzy witness for power isolation and measured dock release."""

from contextlib import ExitStack
import json
import math
import os
from pathlib import Path
import pwd
import subprocess
import sys
from time import monotonic

from action_msgs.msg import GoalStatus
from geometry_msgs.msg import Twist
from lifecycle_msgs.msg import Transition
from nav2_msgs.action import DockRobot
import rclpy
from rclpy.action import ActionClient

from departure_plant import ReleasePlant, SAFE_CURRENT_A, WATCHDOG_S
from native_cases import CONFIGURATION, change_state, spin_until, terminate


CASES = ("slow-cutout", "interrupted-retreat", "stuck-contactor")
DOCK_TOLERANCE = .012
STAGING_TOLERANCE = .027
STAGING_X = -.36


def seat_native(node, plant):
    """Get the commissioned stock plugin into a physically energized dock."""
    client = ActionClient(node, DockRobot, "/dock_robot")
    if not client.wait_for_server(timeout_sec=4.):
        raise RuntimeError("native DockRobot unavailable")
    actuator = node.create_publisher(Twist, "/cmd_vel", 10)
    relay = node.create_subscription(Twist, "/nav2_cmd_vel", actuator.publish, 20)
    if not spin_until(node, lambda: plant.tf.get_subscription_count() >= 1
                      and node.count_publishers("/nav2_cmd_vel") >= 1, 4.):
        raise RuntimeError("native dummy cell transport discovery did not settle")
    warm_until = monotonic() + .20
    spin_until(node, lambda: monotonic() >= warm_until, .30)
    goal = DockRobot.Goal(use_dock_id=False, dock_type="calibrated_rail", navigate_to_staging_pose=False)
    goal.dock_pose.header.frame_id = "odom"
    goal.dock_pose.header.stamp = node.get_clock().now().to_msg()
    x, y, yaw = plant.world((0.,0.,0.))
    goal.dock_pose.pose.position.x = x
    goal.dock_pose.pose.position.y = y
    goal.dock_pose.pose.orientation.z = math.sin(yaw/2)
    goal.dock_pose.pose.orientation.w = math.cos(yaw/2)
    pending = client.send_goal_async(goal)
    if not spin_until(node, pending.done, 3.) or not pending.result().accepted:
        raise RuntimeError("native dock prelude not accepted")
    outcome = pending.result().get_result_async()
    if not spin_until(node, outcome.done, 11.):
        raise RuntimeError("native dock prelude timed out")
    observed = outcome.result()
    node.destroy_subscription(relay)
    actuator.publish(Twist())
    if observed.status != GoalStatus.STATUS_SUCCEEDED or not observed.result.success:
        raise RuntimeError(f"native dock prelude failed with error {observed.result.error_code}")
    settles = monotonic() + .19
    spin_until(node, lambda: monotonic() >= settles, .25)
    if not plant.charged or abs(plant.pose[0]) > DOCK_TOLERANCE:
        raise RuntimeError("native prelude did not create an energized, seated entry")
    node.destroy_publisher(actuator)


def case_setup(plant, name):
    return {
        "request_id": f"departure-{name}", "dock_type": "calibrated_rail",
        "seat_pose": plant.world((0., 0., 0.)),
        "staging_pose": plant.world((STAGING_X, 0., 0.)),
        "isolation_timeout_s": 2.8 if name == "stuck-contactor" else 4.,
    }


def wait_elapsed(node, interval):
    target = monotonic() + interval
    spin_until(node, lambda: monotonic() >= target, interval + .1)


def candidate_commands(app, exchange, spec, output):
    identity = {}
    if os.geteuid() == 0:
        account = pwd.getpwnam("candidate")
        identity = {"user": account.pw_uid, "group": account.pw_gid, "extra_groups": []}
        os.chown(exchange, account.pw_uid, account.pw_gid)
    exchange.chmod(0o700)
    scoped = {name: os.environ[name] for name in (
        "PATH", "PYTHONPATH", "LD_LIBRARY_PATH", "AMENT_PREFIX_PATH", "RMW_IMPLEMENTATION",
        "ROS_AUTOMATIC_DISCOVERY_RANGE", "CYCLONEDDS_URI", "ROS_DOMAIN_ID",
    ) if name in os.environ}
    scoped.update(HOME=str(exchange), ROS_LOG_DIR=str(exchange/"roslogs"), LC_ALL="C.UTF-8")
    driver = [sys.executable, "-B", "-m", "dock_recovery"]
    state = exchange / "state"
    run = [*driver, "guarded-undock", "--spec", str(spec), "--state", str(state), "--output", str(output)]
    receipt = [*driver, "undock-receipt", "--state", str(state), "--request-id",
               json.loads(spec.read_text())["request_id"]]
    return run, receipt, dict(cwd=app, env=scoped, stderr=subprocess.STDOUT, start_new_session=True, **identity)


def examine_accepted(node, command, settings):
    with subprocess.Popen(command, stdout=subprocess.PIPE, text=True, **settings) as reader:
        try:
            if not spin_until(node, lambda: reader.poll() is not None, 2) or reader.returncode:
                return None
            return json.load(reader.stdout)
        except ValueError:
            return None
        finally:
            terminate(reader)


def actuator_matches(native, applied):
    """Count applied start-leg commands corroborated by native DDS output."""
    return sum(any(abs(t - nt) < .125 and abs(v - nv) < 1e-5 and abs(w - nw) < 1e-5
                   for nv,nw,nt in native)
               for v,w,t in applied)


def opted_replay(node, begin, settings, output, expected, plant, worker_log):
    baseline = (len(plant.actuation_stream), len(plant.native_goals))
    replay_started_ns = node.get_clock().now().nanoseconds
    with subprocess.Popen(begin, stdout=worker_log, **settings) as retry:
        try:
            if not spin_until(node, lambda: retry.poll() is not None, 3.) or retry.returncode:
                return False
            wait_elapsed(node, .11)
            # A reliable sample from the completed worker can arrive while the retry runs.
            new_requests = any(row["source_stamp_ns"] >= replay_started_ns for row in plant.requests)
            return (output.is_file() and json.loads(output.read_text()) == expected
                    and not new_requests
                    and baseline == (len(plant.actuation_stream), len(plant.native_goals)))
        except ValueError:
            return False
        finally:
            terminate(retry)


def run_departure(root, app, name):
    """Run the live passage and grade only independently visible outcomes."""
    root.mkdir(mode=0o755, parents=True)
    exchange = root / "candidate"
    exchange.mkdir()
    spec_file, output = exchange / "spec.json", exchange / "report.json"
    native_config = root / "native.yaml"
    native_config.write_text(CONFIGURATION.replace(
        "    dock_backwards: false", "    dock_backwards: false\n    undock_linear_tolerance: 0.012"))
    binary = os.environ.get("NAV2_PROOF_BINARY", "/opt/ros/jazzy/lib/opennav_docking/opennav_docking")
    rclpy.init()
    node = rclpy.create_node("independent_dock_departure")
    frame = (.19, -.11, .48) if name == "interrupted-retreat" else (0., 0., 0.)
    plant = ReleasePlant(node, power_delay=.83 if name == "interrupted-retreat" else .68,
                         decay_time=.12, frame=frame, stuck=name == "stuck-contactor")
    spec = case_setup(plant, name)
    spec_file.write_text(json.dumps(spec) + "\n")
    begin, inspect, settings = candidate_commands(app, exchange, spec_file, output)
    timing, receipt, replay_unchanged, accepted = {}, {}, False, None
    with ExitStack() as stack:
        stack.callback(rclpy.try_shutdown)
        stack.callback(node.destroy_node)
        server_log = stack.enter_context((root / "native.log").open("w"))
        worker_log = stack.enter_context((root / "candidate.log").open("w"))
        server = subprocess.Popen([binary, "--ros-args", "--params-file", str(native_config),
                                   "-r", "cmd_vel:=/nav2_cmd_vel",
                                   "-r", "battery_state:=/qualified_battery"],
                                  stdout=server_log, stderr=subprocess.STDOUT,
                                  start_new_session=True)
        stack.callback(terminate, server)
        change_state(node, Transition.TRANSITION_CONFIGURE)
        change_state(node, Transition.TRANSITION_ACTIVATE)
        seat_native(node, plant)
        timing.update(entry_pose=plant.pose[:], entry_current_a=plant.current, began=monotonic())
        process = subprocess.Popen(begin, stdout=worker_log, **settings)
        stack.callback(terminate, process)
        if name == "interrupted-retreat":
            reached = spin_until(node, lambda: plant.pose[0] <= -.067 or process.poll() is not None, 9.)
            if reached and process.poll() is None and plant.pose[0] <= -.067:
                accepted = examine_accepted(node, inspect, settings)
                timing["kill_pose"] = plant.pose[:]
                timing["killed_at"] = monotonic()
                before = plant.raw_traffic
                terminate(process)
                wait_elapsed(node, .33)
                timing["orphan_native_after_kill"] = plant.raw_traffic - before
                quiet = [row for row in plant.trace if row["time"] > timing["killed_at"] + WATCHDOG_S + .025]
                timing["quiet_watchdog"] = bool(quiet) and all(
                    abs(row["v"]) <= .001 and abs(row["omega"]) <= .001 for row in quiet)
                timing["resume_pose"] = plant.pose[:]
                timing["resumed_at"] = monotonic()
                process = subprocess.Popen(begin, stdout=worker_log, **settings)
                stack.callback(terminate, process)
        finished = spin_until(node, lambda: process.poll() is not None, 25.)
        timing["terminal_at"] = monotonic()
        if finished and process.returncode == 0 and output.is_file() and not output.is_symlink():
            try:
                receipt = json.loads(output.read_text())
                replay_unchanged = opted_replay(node, begin, settings, output, receipt, plant, worker_log)
            except ValueError:
                receipt = {}
        wait_elapsed(node, .17)
        evidence = plant.evidence()
        applied = [row for row in plant.actuation_stream if row[2] > timing["began"]]
        source = [row for row in plant.native_stream if row[2] > timing["began"]]
        window = [row for row in plant.trace if row["time"] > timing["began"]]
        final_pose = plant.pose[:]
        qualified_start = (bool(applied) and plant.current_low_at is not None
            and applied[0][2] >= plant.current_low_at + .125 and not plant.unsafe_commands)
        corridor_clear = (all(abs(row["pose"][1]) <= .035 and abs(row["pose"][2]) <= .18
                              for row in window) and not any(v > .002 for v, _, _ in applied))
        safe = (not plant.live_breaks and not plant.actuator_faults and corridor_clear)
        entry = (timing["entry_current_a"] > .5 and abs(timing["entry_pose"][0]) <= DOCK_TOLERANCE)
        expected_status = "blocked" if plant.stuck else "departed"
        receipt_valid = receipt == {"request_id": spec["request_id"], "status": expected_status,
                                    "boot": None if plant.stuck else plant.boot}
        no_current = window and abs(window[-1]["current_amps"]) <= SAFE_CURRENT_A
        sample_abuse = plant.stale_zero_reports >= 4 and plant.retired_zero_reports >= 4
        terminal_stationary = (window and all(abs(row["v"]) <= .001 and abs(row["omega"]) <= .001
                                            for row in window[-6:]))
        stage_reached = math.hypot(final_pose[0] - STAGING_X, final_pose[1]) <= STAGING_TOLERANCE
        stage_reached &= abs(final_pose[2]) <= .12 and terminal_stationary
        checks = {"physical_safety": bool(safe and entry), "terminal_receipt": bool(receipt_valid and replay_unchanged),
                  "replayed_zero_traffic": sample_abuse}
        if plant.stuck:
            timed = bool(plant.request_at is not None and
                         timing["terminal_at"] - plant.request_at >= spec["isolation_timeout_s"] - .10)
            checks["blocked_power_stays_seated"] = bool(plant.contact_closed and plant.current > .5 and
                not applied and plant.physical_open_at is None and timed and terminal_stationary)
        else:
            checks["positive_physical_departure"] = bool(qualified_start and stage_reached and no_current)
            goals = {key: statuses for key,statuses in plant.native_goals.items() if key.startswith("undock_robot/")}
            if name == "interrupted-retreat":
                recovered = ("resume_pose" in timing and timing["resume_pose"][0] < -DOCK_TOLERANCE
                             and timing["resume_pose"][0] - final_pose[0] >= .19)
                old_applied = [row for row in applied if row[2] < timing.get("killed_at", -1)]
                checks["native_handover_and_recovery"] = bool(accepted ==
                    {"request_id": spec["request_id"], "status": "accepted"} and
                    timing.get("quiet_watchdog") and timing.get("orphan_native_after_kill", 0) > 0
                    and recovered and actuator_matches(source, old_applied) >= 8
                    and any(GoalStatus.STATUS_CANCELED in status for status in goals.values()))
            else:
                checks["native_motion_authority"] = bool(applied and actuator_matches(source, applied)
                    >= .85 * len(applied) and any(GoalStatus.STATUS_SUCCEEDED in s for s in goals.values()))
        result = {"passed": finished and process.returncode == 0 and all(checks.values()),
                  "checks": checks, "case": name, "receipt": receipt, "accepted_before_kill": accepted,
                  "timing": timing, "plant": evidence}
        (root / "trace.json").write_text(json.dumps(plant.trace) + "\n")
        (root / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
        return result
