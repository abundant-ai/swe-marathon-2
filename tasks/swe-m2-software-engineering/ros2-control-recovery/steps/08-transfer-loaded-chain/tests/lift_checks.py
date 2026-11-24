"""Independent wall-clock plant, telemetry restart, and native claim witness."""

from contextlib import ExitStack
import argparse
import json
import math
import mmap
import os
import pwd
from pathlib import Path
import signal
import struct
import subprocess
import sys
import threading
from time import monotonic, sleep
from uuid import uuid4


class Slot:
    def __init__(self, path, count, create=False):
        self.path = Path(path)
        self.payload = struct.Struct("<" + str(count) + "d")
        self.length = 8 + self.payload.size
        if create:
            self.path.write_bytes(bytes(self.length))
        with self.path.open("r+b") as stream:
            self.data = mmap.mmap(stream.fileno(), self.length)

    def get(self):
        sequence = struct.unpack_from("<Q", self.data)[0]
        if not sequence or sequence % 2:
            return None, 0
        value = self.payload.unpack_from(self.data, 8)
        return (value, sequence) if sequence == struct.unpack_from("<Q", self.data)[0] else (None, 0)

    def put(self, values):
        sequence = struct.unpack_from("<Q", self.data)[0] + 1
        if sequence % 2 == 0:
            sequence += 1
        struct.pack_into("<Q", self.data, 0, sequence)
        self.payload.pack_into(self.data, 8, *values)
        struct.pack_into("<Q", self.data, 0, sequence + 1)

    def close(self):
        self.data.close()


def command_height(t):
    maximum_speed = .105
    ramp = .28
    decel_at = 3.55
    if t <= 0:
        return 0., 0.
    if t < ramp:
        return maximum_speed * t * t / (2 * ramp), maximum_speed * t / ramp
    if t < decel_at:
        return maximum_speed * (t - .5 * ramp), maximum_speed
    end_of_cruise = maximum_speed * (decel_at - .5 * ramp)
    u = min(t - decel_at, ramp)
    return end_of_cruise + maximum_speed * u * (1 - u / (2 * ramp)), maximum_speed * (1 - u / ramp)


def right_feedback(truth_path, output_path, epoch, bias):
    truth = Slot(truth_path, 3)
    output = Slot(output_path, 5)
    while True:
        observed, _ = truth.get()
        if observed is not None:
            q, v, stamp = observed
            output.put((q + bias, v, epoch, 1, stamp))
        sleep(.004)


class Plant:
    """The candidate takes force commands. This fixture owns the physical states."""

    def __init__(self, root, mirrored):
        self.obs = Slot(root / "plant.input", 13, create=True)
        self.cmd = Slot(root / "plant.output", 2, create=True)
        trusted = root / "private"
        trusted.mkdir(mode=0o700)
        self.right_truth = Slot(trusted / "absolute.truth", 3, create=True)
        self.right_capture = Slot(trusted / "absolute.capture", 5, create=True)
        self.obs.path.chmod(0o644)
        self.cmd.path.chmod(0o666)
        self.pos = [0., 0.]
        self.vel = [0., 0.]
        self.mass = (7.5, 5.25) if mirrored else (5.4, 7.1)
        self.weight = tuple(9.80665 * mass for mass in self.mass)
        self.force = list(self.weight)
        self.stiffness, self.damping = (125., 5.8) if mirrored else (110., 5.)
        self.mirrored = mirrored
        self.generation = 192 if mirrored else 80
        self.start = math.inf
        self.trace = []
        self.stop = threading.Event()
        self.native_last = 0
        self.reference_seen = 0

    def run(self):
        previous = monotonic()
        sequence = 0
        while not self.stop.is_set():
            now = monotonic()
            dt = min(.012, now - previous)
            previous = now
            time = now - self.start
            goal, goal_velocity = command_height(time)
            forces, publication = self.cmd.get()
            if forces is not None and all(math.isfinite(force) for force in forces):
                self.force[:] = forces
                if publication > self.native_last:
                    self.native_last = publication
                    self.reference_seen += 1
            load = ((3.5 if 1.28 < time < 2.14 else 0), 0) if self.mirrored else (
                0, 3.0 if 1.35 < time < 2.20 else 0)
            strain = (self.stiffness * (self.pos[0] - self.pos[1])
                      + self.damping * (self.vel[0] - self.vel[1]))
            for i, sign in ((0, -1), (1, 1)):
                net = self.force[i] - self.weight[i] + sign * strain - 1.8 * self.vel[i] - load[i]
                self.vel[i] += dt * net / self.mass[i]
                self.pos[i] += dt * self.vel[i]
            self.right_truth.put((self.pos[1], self.vel[1], now))
            telemetry, _ = self.right_capture.get()
            if telemetry is None:
                telemetry = (self.pos[1], self.vel[1], 0, 0, 0)
            right_q, right_v, epoch, healthy, stamp = telemetry
            healthy = int(bool(healthy) and now - stamp < .045)
            sequence += 1
            self.obs.put((self.pos[0], self.vel[0], right_q, right_v, strain, goal, goal_velocity,
                          epoch, healthy, self.generation, *self.weight, sequence))
            if time >= 0:
                self.trace.append((time, goal, *self.pos, *self.force, strain,
                                   epoch, healthy, self.generation, publication))
            self.stop.wait(.005)

    def close(self):
        for slot in (self.obs, self.cmd, self.right_truth, self.right_capture):
            slot.close()


def stop_process(process, sig=signal.SIGTERM):
    if process.poll() is None:
        os.killpg(process.pid, sig)
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=2)


def hardware_xml(plant):
    def joint(name):
        return f"""
  <link name="{name}_carriage"/>
  <joint name="{name}" type="prismatic">
    <parent link="base"/>
    <child link="{name}_carriage"/>
    <axis xyz="0 0 1"/>
    <limit effort="105" lower="-0.2" upper="0.8" velocity="0.5"/>
  </joint>"""
    states = ("strain", "goal", "goal_velocity", "epoch", "healthy", "required_epoch",
              "weight_left", "weight_right", "sample")
    return f"""<robot name="loaded_pair">
  <link name="base"/>
  {joint("left")}
  {joint("right")}
  <ros2_control name="dual_lift" type="system">
    <hardware>
      <plugin>lift_device/PairDevice</plugin>
      <param name="sensor_path">{plant.obs.path}</param>
      <param name="effort_path">{plant.cmd.path}</param>
    </hardware>
    <joint name="left"><command_interface name="effort"/>
      <state_interface name="position"/><state_interface name="velocity"/>
    </joint>
    <joint name="right"><command_interface name="effort"/>
      <state_interface name="position"/><state_interface name="velocity"/>
    </joint>
    <sensor name="feedback">{''.join(f'<state_interface name="{key}"/>' for key in states)}</sensor>
  </ros2_control>
</robot>"""


def controller_yaml(namespace, plant):
    return f"""{namespace}/controller_manager:
  ros__parameters:
    update_rate: 100
    pair:
      type: coupled_handover/ForcePair
    tracking:
      type: coupled_handover/LiftSupervisor
    bridge:
      type: coupled_handover/LiftSupervisor
{namespace}/tracking:
  ros__parameters:
    policy: tracking
    coupling_stiffness_n_per_m: {plant.stiffness}
    coupling_damping_ns_per_m: {plant.damping}
{namespace}/bridge:
  ros__parameters:
    policy: bridge
    coupling_stiffness_n_per_m: {plant.stiffness}
    coupling_damping_ns_per_m: {plant.damping}
"""


class Manager:
    def __init__(self, root, node, plant, stack, environment, user):
        import rclpy
        from rclpy.qos import DurabilityPolicy, QoSProfile
        from std_msgs.msg import String

        self.rclpy = rclpy
        self.node = node
        self.ns = "/loaded_" + uuid4().hex[:10]
        self.clients = {}
        config = root / "controllers.yaml"
        config.write_text(controller_yaml(self.ns, plant))
        self.pub = node.create_publisher(
            String, f"{self.ns}/robot_description", QoSProfile(
                depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.description = String(data=hardware_xml(plant))
        self.authority = node.create_publisher(String, f"{self.ns}/pair_authority", 10)
        self.environment = environment
        self.user = user
        self.stack = stack
        self.private = root / "private"
        log = stack.enter_context((self.private / "manager.log").open("w"))
        command = Path(os.environ["ROS_JAZZY_PREFIX"]) / "lib/controller_manager/ros2_control_node"
        process = subprocess.Popen(
            [command, "--ros-args", "--params-file", str(config), "-r", f"__ns:={self.ns}",
             "-r", f"/robot_description:={self.ns}/robot_description"],
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True, env=environment, **user)
        stack.callback(stop_process, process)

    def request(self, service, name, packet, timeout=2):
        if name not in self.clients:
            self.clients[name] = self.node.create_client(service, f"{self.ns}/controller_manager/{name}")
        client = self.clients[name]
        if not client.wait_for_service(timeout_sec=timeout):
            return None
        future = client.call_async(packet)
        self.rclpy.spin_until_future_complete(self.node, future, timeout_sec=timeout)
        if not future.done():
            future.cancel()
            return None
        return future.result()

    def start(self):
        from controller_manager_msgs.srv import ConfigureController, ListHardwareInterfaces, LoadController

        deadline = monotonic() + 6
        while True:
            self.pub.publish(self.description)
            status = self.request(ListHardwareInterfaces, "list_hardware_interfaces",
                                  ListHardwareInterfaces.Request(), .15)
            required = {"left/effort", "right/effort"}
            if status and required.issubset({item.name for item in status.command_interfaces}):
                break
            if monotonic() > deadline:
                raise RuntimeError("manager never exported hardware effort")
        for name in ("pair", "tracking", "bridge"):
            result = self.request(LoadController, "load_controller", LoadController.Request(name=name))
            assert result is not None and result.ok, f"native load {name}"
            result = self.request(ConfigureController, "configure_controller",
                                  ConfigureController.Request(name=name))
            assert result is not None and result.ok, f"native configure {name}"

    def switch(self, active, inactive=()):
        from controller_manager_msgs.srv import SwitchController
        request = SwitchController.Request(activate_controllers=list(active),
                                           deactivate_controllers=list(inactive),
                                           strictness=SwitchController.Request.STRICT)
        request.timeout.sec = 1
        result = self.request(SwitchController, "switch_controller", request)
        assert result is not None and result.ok, f"native strict switch {active}"

    def claims(self):
        from controller_manager_msgs.srv import ListControllers
        result = self.request(ListControllers, "list_controllers", ListControllers.Request(), .15)
        if result is None:
            return None
        return {controller.name: sorted(controller.claimed_interfaces)
                for controller in result.controller if controller.state == "active"}

    def publish(self, plant):
        from std_msgs.msg import String
        observed, sequence = plant.right_capture.get()
        if observed is None:
            return None
        _, _, epoch, healthy, stamp = observed
        packet = {"reported_epoch": int(epoch), "required_epoch": plant.generation,
                  "sample": sequence, "healthy": bool(healthy and monotonic() - stamp < .045),
                  "stamp_ns": int(stamp * 1e9)}
        self.authority.publish(String(data=json.dumps(packet)))
        return packet

    def start_reconciler(self, install):
        executable = install / "lib/coupled_handover/recover_pair"
        if not executable.is_file():
            raise RuntimeError("missing installed recover_pair")
        log = self.stack.enter_context((self.private / "client.log").open("w"))
        process = subprocess.Popen(
            [executable, "--ros-args", "-r", f"__ns:={self.ns}"],
            stdout=log, stderr=subprocess.STDOUT, env=self.environment,
            start_new_session=True, **self.user)
        self.stack.callback(stop_process, process)
        return process


def measure(plant, fault_endpoints):
    trace = plant.trace[:]
    accepted = [row for row in trace if .10 < row[0] < 4.12]
    during = [row for row in accepted if fault_endpoints[0] + .03 < row[0] < fault_endpoints[1]]
    finish = accepted[-1]
    base = (during[0][2] + during[0][3]) / 2
    final = (during[-1][2] + during[-1][3]) / 2
    force_rows = []
    for row in accepted:
        if not force_rows or force_rows[-1][-1] != row[-1]:
            force_rows.append(row)
    steps = []
    excess = []
    for first, second in zip(force_rows, force_rows[1:]):
        delta = max(abs(first[4] - second[4]), abs(first[5] - second[5]))
        writes_between = max(1, (second[-1] - first[-1]) // 2)
        nominal_budget = 100 * max(second[0] - first[0], .01 * writes_between)
        steps.append(delta)
        excess.append(delta - nominal_budget)
    return {
        "applied_native_writes": len(force_rows),
        "maximum_skew_m": max(abs(row[2] - row[3]) for row in accepted),
        "maximum_internal_force_n": max(abs(row[6]) for row in accepted),
        "maximum_force_step_n": max(steps),
        "maximum_force_slew_excess_n": max(excess),
        "maximum_drive_effort_n": max(max(row[4], row[5]) for row in accepted),
        "minimum_drive_effort_n": min(min(row[4], row[5]) for row in accepted),
        "rms_tracking_error_m": math.sqrt(sum((row[1] - (row[2] + row[3]) / 2)**2
                                               for row in accepted) / len(accepted)),
        "outage_tracking_progress_m": final - base,
        "outage_reference_progress_m": during[-1][1] - during[0][1],
        "final_tracking_error_m": abs(finish[1] - (finish[2] + finish[3]) / 2),
        "retired_healthy_frames": sum(row[8] and row[7] < row[9] for row in during),
    }


def witness(args):
    import rclpy

    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o711)
    root.chmod(0o711)
    if not hasattr(args, "mirrored"):
        raise ValueError("fixture selection missing")
    plant = Plant(root, args.mirrored)
    worker = threading.Thread(target=plant.run, daemon=True)
    worker.start()
    user = {}
    if os.geteuid() == 0:
        account = pwd.getpwnam("candidate")
        user = {"user": account.pw_uid, "group": account.pw_gid, "extra_groups": []}
    environment = os.environ.copy()
    environment["LD_LIBRARY_PATH"] = ":".join((
        str(args.install / "lib"), str(args.hardware / "lib"), environment.get("LD_LIBRARY_PATH", "")))
    environment["AMENT_PREFIX_PATH"] = ":".join((
        str(args.install), str(args.hardware), environment.get("AMENT_PREFIX_PATH", "")))
    ros_logs = root / "ros_logs"
    ros_logs.mkdir(mode=0o777)
    ros_logs.chmod(0o777)
    environment["ROS_LOG_DIR"] = str(ros_logs)
    rclpy.init()
    node = rclpy.create_node("independent_lift_witness")
    try:
        with ExitStack() as stack:
            def feedback(epoch, bias=0):
                process = subprocess.Popen(
                    [sys.executable, __file__, "feedback", str(plant.right_truth.path),
                     str(plant.right_capture.path), str(epoch), str(bias)], start_new_session=True)
                stack.callback(stop_process, process)
                return process

            initial_epoch = plant.generation
            origin = feedback(initial_epoch)
            manager = Manager(root, node, plant, stack, environment, user)
            manager.start()
            manager.switch(("pair", "tracking"))
            client = manager.start_reconciler(args.install)
            expected = {"left/effort", "right/effort"}
            owned = {"pair/left_effort", "pair/right_effort"}
            fault_time, stale_time, return_time = (0.87, 1.14, 2.27) if args.mirrored else (1.0, 1.24, 2.43)
            old = recovered = None
            eligible = []
            authority = []
            mode_changes = []
            previous_owner = None
            next_claim = 0.
            bridge_at = restore_at = third_sample_at = None
            no_foreign_claim = True
            keep_pair = True
            use_retired = False
            plant.start = monotonic() + .35
            while (now := monotonic() - plant.start) < 4.15:
                if now >= fault_time and plant.generation == initial_epoch:
                    plant.generation += 1
                    stop_process(origin, signal.SIGKILL)
                if now >= stale_time and old is None:
                    old = feedback(initial_epoch, -.13 if args.mirrored else .16)
                if now >= return_time and recovered is None:
                    stop_process(old, signal.SIGKILL)
                    recovered = feedback(initial_epoch + 1)
                packet = manager.publish(plant)
                if packet:
                    authority.append(packet)
                    if (packet["healthy"] and packet["required_epoch"] == initial_epoch + 1
                            and packet["reported_epoch"] == plant.generation):
                        if not eligible or packet["sample"] > eligible[-1]:
                            eligible.append(packet["sample"])
                            if len(eligible) == 3:
                                third_sample_at = now
                if now >= next_claim:
                    claims = manager.claims()
                    if claims is not None:
                        active_upper = [key for key in ("tracking", "bridge") if key in claims]
                        aligned = len(active_upper) == 1 and set(claims[active_upper[0]]) == owned
                        no_foreign_claim &= aligned and set(claims) == {"pair", *active_upper}
                        keep_pair &= set(claims.get("pair", [])) == expected
                        if aligned:
                            owner = active_upper[0]
                            if owner != previous_owner:
                                mode_changes.append({"time_s": now, "owner": owner, "claims": claims})
                                previous_owner = owner
                            if owner == "bridge" and bridge_at is None:
                                bridge_at = now
                            if bridge_at is not None and owner == "tracking":
                                if third_sample_at is None:
                                    use_retired = True
                                elif restore_at is None:
                                    restore_at = now
                    next_claim = now + .035
                rclpy.spin_once(node, timeout_sec=.016)
            assert plant.reference_seen > 30, "native pair produced no physical actuation"
            assert client.poll() is None, "candidate reconciler terminated during the run"
            plant.stop.set()
            worker.join(1)
            measured = measure(plant, (fault_time, return_time))
            measured.update({"mode_changes": mode_changes, "initial_epoch": initial_epoch,
                             "restarted_feedback_pids": [origin.pid, old.pid, recovered.pid],
                             "bridge_time_s": bridge_at, "restore_time_s": restore_at,
                             "third_fresh_sample_s": third_sample_at,
                             "actuator_write_count": plant.reference_seen,
                             "right_sample_count": len(authority)})
            checks = {
                "native_authority": keep_pair and no_foreign_claim and not use_retired
                    and mode_changes[:1] != [] and mode_changes[0]["owner"] == "tracking"
                    and bridge_at is not None and fault_time <= bridge_at <= fault_time + .300
                    and restore_at is not None and third_sample_at <= restore_at <= third_sample_at + .350
                    and measured["retired_healthy_frames"] > 6,
                "force_envelope": measured["minimum_drive_effort_n"] >= 0
                    and measured["maximum_drive_effort_n"] <= 105
                    and measured["maximum_force_step_n"] <= 2.5
                    and measured["maximum_force_slew_excess_n"] <= .45
                    and measured["maximum_skew_m"] <= .035
                    and measured["maximum_internal_force_n"] <= 4.5,
                "bounded_tracking": measured["rms_tracking_error_m"] <= .022
                    and measured["final_tracking_error_m"] <= .012,
                "outage_progress": measured["outage_tracking_progress_m"] >=
                    .75 * measured["outage_reference_progress_m"],
            }
            measured["checks"] = checks
            (root / "private/report.json").write_text(json.dumps(measured, indent=2, sort_keys=True) + "\n")
            (root / "private/trace.json").write_text(json.dumps(plant.trace) + "\n")
            print(json.dumps(measured, sort_keys=True))
    finally:
        plant.stop.set()
        worker.join(1)
        plant.close()
        node.destroy_node()
        rclpy.shutdown()


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("witness")
    run.add_argument("--install", type=Path, required=True)
    run.add_argument("--hardware", type=Path, required=True)
    run.add_argument("--mirrored", action="store_true")
    run.add_argument("--output", type=Path, required=True)
    worker = commands.add_parser("feedback")
    worker.add_argument("truth")
    worker.add_argument("output")
    worker.add_argument("epoch", type=int)
    worker.add_argument("bias", type=float)
    options = parser.parse_args()
    if options.command == "feedback":
        right_feedback(options.truth, options.output, options.epoch, options.bias)
    else:
        witness(options)


if __name__ == "__main__":
    main()
