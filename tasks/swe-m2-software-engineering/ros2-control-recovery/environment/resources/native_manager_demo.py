"""Exercise native Jazzy controller activation on isolated mock hardware."""

from pathlib import Path
import os
import subprocess
import tempfile
from time import monotonic
from uuid import uuid4

import rclpy
from controller_manager_msgs.srv import ConfigureController, ListControllers, ListHardwareInterfaces, LoadController, SwitchController
from rclpy.qos import DurabilityPolicy, QoSProfile
from std_msgs.msg import String


DESCRIPTION = """<robot name="qualification">
<link name="base"/><link name="rotor"/>
<joint name="rotor_joint" type="continuous"><parent link="base"/><child link="rotor"/></joint>
<ros2_control name="qualification" type="system">
 <hardware><plugin>mock_components/GenericSystem</plugin></hardware>
 <joint name="rotor_joint">
   <command_interface name="position"/>
   <state_interface name="position"><param name="initial_value">0.0</param></state_interface>
 </joint>
</ros2_control>
</robot>"""

PARAMETERS = """controller_manager:
  ros__parameters:
    update_rate: 100
    trajectory_input:
      type: forward_command_controller/ForwardCommandController
trajectory_input:
  ros__parameters:
    joints: [rotor_joint]
    interface_name: position
"""


def exercise() -> None:
    """Load and activate a real controller and verify exclusive interface ownership."""
    prefix = Path(os.environ.get("ROS_JAZZY_PREFIX", "/opt/ros/jazzy"))
    with tempfile.TemporaryDirectory(prefix="native-ros-qualification-") as location:
        root = Path(location)
        params = root / "control.yaml"
        namespace = "/qualification_" + uuid4().hex
        params.write_text(PARAMETERS.replace("controller_manager:", f"{namespace}/controller_manager:")
                                    .replace("\ntrajectory_input:", f"\n{namespace}/trajectory_input:"))
        with (root / "manager.log").open("w+") as log:
            manager = subprocess.Popen([prefix / "lib/controller_manager/ros2_control_node", "--ros-args", "--params-file", params,
                                        "-r", f"__ns:={namespace}", "-r", f"/robot_description:={namespace}/robot_description"],
                                       stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            node = None
            try:
                rclpy.init()
                node = rclpy.create_node("qualification_driver", namespace=namespace)
                qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
                publish = node.create_publisher(String, f"{namespace}/robot_description", qos)
                listing = node.create_client(ListHardwareInterfaces, f"{namespace}/controller_manager/list_hardware_interfaces")
                deadline = monotonic() + 14

                def request(service: type, verb: str, packet: object) -> object:
                    """Send one bounded request through the live ROS service interface."""
                    client = node.create_client(service, f"{namespace}/controller_manager/{verb}")
                    assert client.wait_for_service(timeout_sec=5), verb
                    future = client.call_async(packet)
                    rclpy.spin_until_future_complete(node, future, timeout_sec=8)
                    assert future.done() and future.result() is not None, verb
                    return future.result()

                while monotonic() < deadline:
                    publish.publish(String(data=DESCRIPTION))
                    if listing.wait_for_service(timeout_sec=.3):
                        break
                else:
                    raise RuntimeError("Controller manager did not expose a hardware service")
                original = request(ListHardwareInterfaces, "list_hardware_interfaces", ListHardwareInterfaces.Request())
                assert any(row.name == "rotor_joint/position" and row.is_available and not row.is_claimed
                           for row in original.command_interfaces)
                assert request(LoadController,"load_controller", LoadController.Request(name="trajectory_input")).ok
                assert request(ConfigureController,"configure_controller", ConfigureController.Request(name="trajectory_input")).ok
                switch = SwitchController.Request(activate_controllers=["trajectory_input"], strictness=SwitchController.Request.STRICT)
                switch.timeout.sec = 4
                assert request(SwitchController, "switch_controller", switch).ok
                rows = request(ListControllers,"list_controllers", ListControllers.Request()).controller
                controller, = [item for item in rows if item.name == "trajectory_input"]
                assert controller.state == "active" and list(controller.claimed_interfaces) == ["rotor_joint/position"]
                print("ROS 2 Jazzy loaded the native controller and claimed rotor_joint/position.")
            except Exception:
                log.seek(0)
                print(log.read()[-3500:])
                raise
            finally:
                if node is not None:
                    node.destroy_node()
                    rclpy.try_shutdown()
                manager.terminate()
                try:
                    manager.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    manager.kill()
                    manager.wait()


if __name__ == "__main__":
    exercise()
