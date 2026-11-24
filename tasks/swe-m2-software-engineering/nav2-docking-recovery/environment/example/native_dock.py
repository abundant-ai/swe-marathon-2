"""Run a single-center charger on an unused localhost ROS domain."""

import argparse
import json
import math
import os
from pathlib import Path
import subprocess
from time import monotonic

from geometry_msgs.msg import TransformStamped, Twist
from lifecycle_msgs.msg import Transition
from lifecycle_msgs.srv import ChangeState
import rclpy
from rclpy.executors import ExternalShutdownException
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



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True, type=Path)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    path = args.directory / "spec.json"
    path.write_text(json.dumps({"request_id":"public-dock","dock_type":"calibrated_rail",
                                "targets":[{"id":"center","x":0.0,"y":0.0,"yaw":0.0}],
                                "obstacles":[]},indent=2)+"\n")
    configuration = args.directory / "commissioned.yaml"
    configuration.write_text(CONFIGURATION)
    binary = os.environ.get("NAV2_PROOF_BINARY","/opt/ros/jazzy/lib/opennav_docking/opennav_docking")

    rclpy.init()
    node = rclpy.create_node("example_rail")
    tf = node.create_publisher(TFMessage, "/tf", 20)
    charger = node.create_publisher(BatteryState, "/charger/battery_state", 10)
    contact = node.create_publisher(Bool, "/charger/contact", 10)
    boot = node.create_publisher(UInt64, "/charger/boot", 10)
    pose = [-.36,0.,0.]
    velocities = [0.,0.,-10.]
    last_step = monotonic()
    seated_since = None

    def twist(message):
        velocities[:] = [message.linear.x,message.angular.z,monotonic()]

    def step():
        nonlocal last_step,seated_since
        then = last_step
        last_step = monotonic()
        dt = min(.04,last_step-then)
        v,w,heard = velocities
        if last_step-heard <= .095:
            if math.isfinite(v) and math.isfinite(w) and abs(v)<=.18 and abs(w)<=.50:
                pose[2] += dt*w
                pose[0] = min(.001,pose[0]+dt*v*math.cos(pose[2]))
                pose[1] += dt*v*math.sin(pose[2])
        stamp = node.get_clock().now().to_msg()
        transform = TransformStamped()
        transform.header.stamp = stamp
        transform.header.frame_id,transform.child_frame_id = "odom","base_link"
        transform.transform.translation.x,transform.transform.translation.y = pose[:2]
        transform.transform.rotation.z = math.sin(pose[2]/2)
        transform.transform.rotation.w = math.cos(pose[2]/2)
        tf.publish(TFMessage(transforms=[transform]))
        seated = pose[0] >= -.017 and abs(pose[1]) <= .014 and abs(pose[2]) <= .16
        seated_since = (seated_since or last_step) if seated else None
        charging = seated and last_step-seated_since >= .10
        sample = BatteryState()
        sample.header.stamp,sample.header.frame_id = stamp,"charger_boot_12"
        sample.present,sample.voltage = True,24.6
        sample.current = 1.45 if charging else 0.
        sample.power_supply_status = (BatteryState.POWER_SUPPLY_STATUS_CHARGING if charging else
                                      BatteryState.POWER_SUPPLY_STATUS_NOT_CHARGING)
        boot.publish(UInt64(data=12))
        contact.publish(Bool(data=seated))
        charger.publish(sample)

    node.create_subscription(Twist, "/cmd_vel", twist, 10)
    node.create_timer(.015, step)
    process = subprocess.Popen([binary,"--ros-args","--params-file",str(configuration),
                                "-r","cmd_vel:=/nav2_cmd_vel","-r","battery_state:=/qualified_battery"])
    try:
        client = node.create_client(ChangeState,"/docking_server/change_state")
        if not client.wait_for_service(timeout_sec=7.):
            raise RuntimeError("dock lifecycle service unavailable")
        for transition in (Transition.TRANSITION_CONFIGURE,Transition.TRANSITION_ACTIVATE):
            request = ChangeState.Request()
            request.transition.id = transition
            pending = client.call_async(request)
            rclpy.spin_until_future_complete(node,pending,timeout_sec=7.)
            if not pending.done() or not pending.result().success:
                raise RuntimeError("dock lifecycle transition failed")
        print("Active. Spec:",path.resolve(),flush=True)
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        process.terminate()
        try:
            process.wait(timeout=3.)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
