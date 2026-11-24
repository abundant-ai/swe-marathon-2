"""Run trusted Jazzy DockRobot with separately authored contact and charger measurements."""

import argparse
import json
import math
import os
import pwd
import signal
from pathlib import Path
import subprocess
import sys
from time import monotonic

from action_msgs.msg import GoalStatusArray
from geometry_msgs.msg import TransformStamped, Twist
from lifecycle_msgs.msg import Transition
from lifecycle_msgs.srv import ChangeState
import rclpy
from sensor_msgs.msg import BatteryState
from std_msgs.msg import Bool, UInt64
from tf2_msgs.msg import TFMessage


CONFIGURATION = '''
docking_server:
  ros__parameters:
    controller_frequency: 40.0
    dock_approach_timeout: 10.0
    wait_charge_timeout: 0.8
    max_retries: 0
    dock_prestaging_tolerance: 0.45
    fixed_frame: odom
    base_frame: base_link
    enable_stamped_cmd_vel: false
    dock_backwards: false
    bond_heartbeat_period: 0.0
    dock_plugins: ['calibrated_rail']
    calibrated_rail:
      plugin: 'opennav_docking::SimpleChargingDock'
      use_battery_status: true
      use_external_detection_pose: false
      use_stall_detection: false
      charging_threshold: 0.5
      docking_threshold: .012
      staging_x_offset: -0.36
    docks: ['bench']
    bench:
      type: 'calibrated_rail'
      frame: odom
      pose: [0.0, 0.0, 0.0]
    controller:
      use_collision_detection: false
      v_linear_min: 0.05
      v_linear_max: 0.18
      v_angular_max: 0.5
      slowdown_radius: 0.22
'''



CASES = ("center", "mirror-positive", "mirror-negative", "open-circuit", "killed-worker")


class Plant:
    """Independent low-speed robot, contact circuit, raw battery and command watchdog."""

    def __init__(self, node, side, obstacles, emit_charge):
        self.node = node
        self.side = side
        self.obstacles = obstacles
        self.emit_charge = emit_charge
        self.pose = [-.36, 0., 0.]
        self.clock = monotonic()
        self.command = (0., 0., self.clock-1.)
        self.latest_nav = (0., 0., self.clock-1.)
        self.boot = 173
        self.seated_at = None
        self.trace = []
        self.raw_traffic = 0
        self.nonzero = 0
        self.reverse = 0
        self.collision = 0
        self.actuator_fault = 0
        self.confirmed = 0
        self.native_goals = {}
        self.native_stream = []
        self.actuation_stream = []
        self.invalid_qualified = 0
        self.tf = node.create_publisher(TFMessage, "/tf", 20)
        self.contact = node.create_publisher(Bool, "/charger/contact", 10)
        self.battery = node.create_publisher(BatteryState, "/charger/battery_state", 15)
        self.boot_topic = node.create_publisher(UInt64, "/charger/boot", 10)
        node.create_subscription(Twist, "/cmd_vel", self.receive, 30)
        node.create_subscription(Twist, "/nav2_cmd_vel", self.observe_native, 30)
        node.create_subscription(BatteryState, "/qualified_battery", self.observe_charge, 20)
        for kind in ("dock_robot", "undock_robot"):
            node.create_subscription(GoalStatusArray, f"/{kind}/_action/status",
                                     lambda message, kind=kind: self.observe_goal(kind, message), 20)
        node.create_timer(.015, self.step)

    def observe_goal(self, kind, message):
        for event in message.status_list:
            identifier = bytes(event.goal_info.goal_id.uuid).hex()
            self.native_goals.setdefault(kind + "/" + identifier, []).append(event.status)

    def observe_native(self, message):
        v, w = message.linear.x, message.angular.z
        self.latest_nav = (v,w,monotonic())
        if abs(v) > .001 or abs(w) > .001:
            self.raw_traffic += 1
            self.native_stream.append(self.latest_nav)

    def observe_charge(self, message):
        if not math.isfinite(message.current) or message.current <= .5:
            return
        ns = message.header.stamp.sec * 10**9 + message.header.stamp.nanosec
        age = self.node.get_clock().now().nanoseconds-ns
        if (message.header.frame_id != f"charger_boot_{self.boot}" or not 0 <= age <= 230_000_000
                or not self.trace or not any(row["charging"] for row in self.trace[-4:])):
            self.invalid_qualified += 1

    def receive(self, message):
        v, w = message.linear.x, message.angular.z
        if not math.isfinite(v) or not math.isfinite(w) or abs(v) > .185 or abs(w) > .505:
            self.actuator_fault += 1
            v, w = 0.0, 0.0
        if abs(v) > .001 or abs(w) > .001:
            self.nonzero += 1
            self.actuation_stream.append((v,w,monotonic()))
            if v < -.015:
                self.reverse += 1
        self.command = (v,w,monotonic())

    def hit(self, x, y):
        for box in self.obstacles:
            dx = max(box["min_x"]-x, x-box["max_x"], 0.)
            dy = max(box["min_y"]-y, y-box["max_y"], 0.)
            if dx*dx+dy*dy < .019**2:
                return True
        return False

    def sample(self, ns, boot, current):
        message = BatteryState()
        message.header.stamp.sec, message.header.stamp.nanosec = divmod(ns, 10**9)
        message.header.frame_id = f"charger_boot_{boot}"
        message.current, message.voltage, message.present = current, 24.6, True
        message.power_supply_status = (
            BatteryState.POWER_SUPPLY_STATUS_CHARGING if current else
            BatteryState.POWER_SUPPLY_STATUS_NOT_CHARGING
        )
        self.battery.publish(message)

    def step(self):
        now = monotonic()
        dt, self.clock = min(.04, now-self.clock), now
        x, y, yaw = self.pose
        v,w,last = self.command
        if now-last > .095:
            v,w = 0.,0.
        yaw += .5*dt*w
        ahead = min(.001, x+dt*v*math.cos(yaw)), y+dt*v*math.sin(yaw)
        if self.hit(*ahead):
            self.collision += 1
        else:
            x, y = ahead
        yaw += .5*dt*w
        self.pose = [x, y, yaw]

        stamp = self.node.get_clock().now()
        transform = TransformStamped()
        transform.header.stamp = stamp.to_msg()
        transform.header.frame_id = "odom"
        transform.child_frame_id = "base_link"
        transform.transform.translation.x = x
        transform.transform.translation.y = y
        transform.transform.rotation.z = math.sin(yaw/2)
        transform.transform.rotation.w = math.cos(yaw/2)
        self.tf.publish(TFMessage(transforms=[transform]))
        seated = x >= -.017 and abs(y-self.side) <= .014 and abs(yaw) <= .16
        self.seated_at = (self.seated_at or now) if seated else None
        charging = bool(seated and now-self.seated_at >= .1 and self.emit_charge)
        if charging:
            self.confirmed += 1
        self.boot_topic.publish(UInt64(data=self.boot))
        self.contact.publish(Bool(data=seated))
        ns = stamp.nanoseconds
        self.sample(ns-29_000_000_000, self.boot, 2.1)
        self.sample(ns, self.boot-1, 2.1)
        self.sample(ns, self.boot, 1.45 if charging else 0.)
        self.trace.append({"time":now,"pose":self.pose,"v":v,"omega":w,"seated":seated,
                           "charging":charging,"boot":self.boot,"native":self.latest_nav[:2]})


def spin_until(node, condition, timeout):
    end = monotonic()+timeout
    while monotonic() < end and not condition():
        rclpy.spin_once(node, timeout_sec=.025)
    return condition()


def change_state(node, identifier):
    client = node.create_client(ChangeState, "/docking_server/change_state")
    if not client.wait_for_service(timeout_sec=6.):
        raise RuntimeError("trusted docking lifecycle unavailable")
    request = ChangeState.Request()
    request.transition.id = identifier
    pending = client.call_async(request)
    if not spin_until(node, pending.done, 6.) or not pending.result().success:
        raise RuntimeError("trusted docking lifecycle transition failed")
    node.destroy_client(client)


def case_spec(case):
    side = {"mirror-positive": .068, "mirror-negative": -.068}.get(case, 0.)
    targets = [{"id":"nominal","x":0.,"y":0.,"yaw":0.}]
    obstacles = []
    if side:
        targets.extend({"id":f"canal-{i}","x":0.,"y":offset,"yaw":0.}
                       for i, offset in enumerate((-.068,.068)))
        low, high = (-.145,-.050) if side > 0 else (.050,.145)
        obstacles.append({"min_x":-.22,"max_x":.03,"min_y":low,"max_y":high})
    return side, {"request_id":f"rail-{case}","dock_type":"calibrated_rail",
                   "targets":targets,"obstacles":obstacles}


def terminate(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=3.)


def run_mission(root, app, case, trusted_binary=None):
    root.mkdir(parents=True, exist_ok=True)
    side, spec = case_spec(case)
    root.chmod(0o755)
    exchange = root / "exchange"
    exchange.mkdir()
    spec_path, report = (exchange / name for name in ("spec.json","report.json"))
    config = root / "commissioned.yaml"
    identity = {}
    if os.geteuid() == 0:
        account = pwd.getpwnam("candidate")
        identity = dict(user=account.pw_uid, group=account.pw_gid, extra_groups=[])
        os.chown(exchange, account.pw_uid, account.pw_gid)
    exchange.chmod(0o700)
    spec_path.write_text(json.dumps(spec)+"\n")
    config.write_text(CONFIGURATION)
    output = root / "candidate.log"
    output.touch()
    state = exchange / "state"
    env = {key: os.environ[key] for key in (
        "PATH","PYTHONPATH","LD_LIBRARY_PATH","AMENT_PREFIX_PATH","RMW_IMPLEMENTATION",
        "ROS_AUTOMATIC_DISCOVERY_RANGE","CYCLONEDDS_URI","ROS_DOMAIN_ID",
    ) if key in os.environ}
    env.update(HOME=str(exchange), ROS_LOG_DIR=str(exchange/"roslogs"), LC_ALL="C.UTF-8")
    native = trusted_binary or os.environ.get("NAV2_PROOF_BINARY","/opt/ros/jazzy/lib/opennav_docking/opennav_docking")
    command = ["/usr/bin/python3","-B","-m","dock_recovery","guarded-dock","--spec",str(spec_path),
               "--state",str(state),"--output",str(report)]
    read_cmd = ["/usr/bin/python3","-B","-m","dock_recovery","dock-receipt","--state",str(state),
                "--request-id",spec["request_id"]]
    launch_options = dict(cwd=app, env=env, stderr=subprocess.STDOUT, start_new_session=True, **identity)
    owner = None
    rclpy.init()
    node = rclpy.create_node("independent_rail_plant")
    plant = Plant(node,side,spec["obstacles"],case!="open-circuit")
    action_record = None
    interrupted = False
    quiet_gap = False
    native_during_loss = False
    with (root/"native.log").open("w") as native_log, output.open("w") as worker_log:
        server = subprocess.Popen([native,"--ros-args","--params-file",str(config),"-r",
                                   "cmd_vel:=/nav2_cmd_vel","-r","battery_state:=/qualified_battery"],
                                  stdout=native_log,stderr=subprocess.STDOUT)
        try:
            change_state(node,Transition.TRANSITION_CONFIGURE)
            change_state(node,Transition.TRANSITION_ACTIVATE)
            owner = subprocess.Popen(command,stdout=worker_log,**launch_options)
            if case == "killed-worker":
                moving = spin_until(node,lambda: plant.pose[0]>-.27 or owner.poll() is not None,8.)
                if moving and owner.poll() is None:
                    inspect = subprocess.Popen(read_cmd,stdout=subprocess.PIPE,text=True,**launch_options)
                    try:
                        if spin_until(node,lambda: inspect.poll() is not None,4.) and inspect.returncode==0:
                            action_record = json.load(inspect.stdout)
                    finally:
                        terminate(inspect)
                    origin = plant.clock
                    terminate(owner)
                    old_native = plant.raw_traffic
                    spin_until(node,lambda: plant.clock-origin>.42,1.)
                    stopped = [row for row in plant.trace if row["time"]>origin+.15]
                    quiet_gap = bool(stopped and all(row["v"]==0. and row["omega"]==0. for row in stopped))
                    native_during_loss = plant.raw_traffic > old_native
                    interrupted = True
                    plant.boot += 1
                    owner = subprocess.Popen(command,stdout=worker_log,**launch_options)
            done = spin_until(node,lambda: owner.poll() is not None,33.)
            receipt = json.loads(report.read_text()) if report.is_file() else {}
            replays = None
            if done and owner.returncode==0 and receipt:
                prior = plant.nonzero
                duplicate = subprocess.Popen(command,stdout=worker_log,**launch_options)
                try:
                    repeated = spin_until(node,lambda: duplicate.poll() is not None,3.)
                    replays = bool(repeated and duplicate.returncode==0 and plant.nonzero==prior and
                                   json.loads(report.read_text())==receipt)
                finally:
                    terminate(duplicate)
            relayed = sum(any(abs(t-u)<.15 and abs(v-v0)<.00001 and abs(w-w0)<.00001
                              for v0,w0,u in plant.native_stream)
                          for v,w,t in plant.actuation_stream)
            head = {"case":case,"returncode":owner.returncode,"receipt":receipt,"replays":replays,
                    "accepted_before_kill":action_record,"interrupted":interrupted,"quiet_gap":quiet_gap,
                    "native_during_loss":native_during_loss,
                    "native_goals":plant.native_goals,"pose":plant.pose,"side":plant.side,
                    "boot":plant.boot,"actual_charge_samples":plant.confirmed,
                    "native_twists":plant.raw_traffic,"actuated_twists":plant.nonzero,"reverse":plant.reverse,
                    "obstacle_hits":plant.collision,"actuator_faults":plant.actuator_fault,
                    "invalid_qualified":plant.invalid_qualified,"relayed_native_twists":relayed,
                    "output_while_seat_open":bool(not plant.emit_charge)}
            (root/"trace.json").write_text(json.dumps(plant.trace)+"\n")
            (root/"summary.json").write_text(json.dumps(head,indent=2)+"\n")
            return head
        finally:
            if owner is not None:
                terminate(owner)
            server.terminate()
            try:
                server.wait(timeout=3.)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
            node.destroy_node()
            rclpy.try_shutdown()


def pass_case(item):
    case = item["case"]
    reply = item["receipt"]
    passed = (item["returncode"]==0 and item["replays"] is True and
              item["obstacle_hits"]==0 and item["actuator_faults"]==0 and item["invalid_qualified"]==0 and
              item["actuated_twists"]>=12 and item["native_twists"]>=12 and
              item["relayed_native_twists"] >= 0.85*item["actuated_twists"])
    if case=="open-circuit":
        return passed and reply.get("status")=="blocked" and item["actual_charge_samples"]==0
    passed = (passed and reply.get("status")=="docked" and reply.get("boot")==item["boot"] and
              item["actual_charge_samples"]>=4 and abs(item["pose"][1]-item["side"])<=.015 and
              item["pose"][0]>=-.017 and abs(item["pose"][2])<=.16)
    if case.startswith("mirror"):
        passed = passed and item["reverse"]>=12 and any(
            name.startswith("undock_robot/") and 4 in events for name,events in item["native_goals"].items()
        )
    if case=="killed-worker":
        passed = (passed and item["interrupted"] and item["quiet_gap"] and item["native_during_loss"]
                  and item["accepted_before_kill"]=={"request_id":"rail-killed-worker","status":"accepted"}
                  and any(name.startswith("dock_robot/") and 5 in events
                          for name,events in item["native_goals"].items()))
    return passed


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--case",choices=CASES,action="append")
    parser.add_argument("--domain",type=int,default=180)
    args=parser.parse_args()
    successes=[]
    for index, case in enumerate(args.case or CASES):
        os.environ["ROS_DOMAIN_ID"]=str(args.domain+index)
        head=run_mission(args.output/case,args.app.resolve(),case)
        passed=pass_case(head)
        successes.append(passed)
        print(json.dumps(dict(head,passed=passed)),flush=True)
    return 0 if all(successes) else 1


if __name__=="__main__":
    sys.exit(main())
