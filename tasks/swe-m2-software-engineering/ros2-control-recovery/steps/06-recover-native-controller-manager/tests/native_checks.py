"""Probe the submitted driver with actual Jazzy lifecycle and device exchanges."""
from contextlib import ExitStack
import mmap
import os
from pathlib import Path
import random
import signal
import struct
import subprocess
import sys
import tempfile
import threading
from time import monotonic, monotonic_ns, sleep
import traceback
from uuid import uuid4

import rclpy
from controller_manager_msgs.srv import ConfigureController, ListControllers, ListHardwareInterfaces, LoadController, SwitchController
from rclpy.qos import DurabilityPolicy, QoSProfile
from std_msgs.msg import Float64MultiArray, String


class Drive:
    """Publish plant state and consume command records at an independent cadence."""

    def __init__(self, root, joint, stack, user):
        self.joint = joint
        self.generation = 1
        self.switch = 'healthy'
        self.position = 0.0
        self.velocity = 0.0
        self.output = []
        self.paths = [root / f'{joint}.{side}' for side in ('device', 'command')]
        slots = []
        for path in self.paths:
            path.write_bytes(bytes(64))
            file = stack.enter_context(path.open('r+b'))
            slots.append(stack.enter_context(mmap.mmap(file.fileno(), 64)))
        self.measurement, self.command = slots
        self.paths[0].chmod(0o444)
        self.paths[1].chmod(0o644)
        if user:
            os.chown(self.paths[1], user['user'], user['group'])
        self.sequence = 0

    def description(self):
        device, command = self.paths
        state = ''.join(f'<state_interface name="{name}"/>' for name in ('position', 'velocity', 'effort', 'drive_generation', 'drive_healthy', 'drive_authorized_generation'))
        return f"""
        <link name="{self.joint}_link"/>
        <joint name="{self.joint}" type="continuous"><parent link="base"/><child link="{self.joint}_link"/></joint>
        <ros2_control name="{self.joint}_drive" type="system">
          <hardware><plugin>fenced_drive/FencedSystem</plugin>
            <param name="device_file">{device}</param><param name="command_file">{command}</param>
            <param name="max_sample_age_ns">80000000</param>
          </hardware>
          <joint name="{self.joint}"><command_interface name="position"/><command_interface name="effort"/>{state}</joint>
        </ros2_control>"""

    def tick(self):
        sequence, = struct.unpack_from('<Q', self.command)
        generation, _, mode, command, sample, _, _ = struct.unpack_from('<QQQdQQQ', self.command, 8)
        if sequence and sequence % 2 == 0 and sequence == struct.unpack_from('<Q', self.command)[0]:
            self.output.append((monotonic(), generation, mode, command, sample))
            torque = ((command - self.position) * 16 - self.velocity * 6) if mode == 1 else command if mode == 2 else -4 * self.velocity
            self.velocity += 0.005 * torque
            self.position += 0.005 * self.velocity
        else:
            torque = 0.0
        if self.switch == 'stale':
            return
        self.sequence += 2
        struct.pack_into('<Q', self.measurement, 0, self.sequence - 1)
        generation = self.generation - 1 if self.switch == 'old' else self.generation
        valid = int(self.switch != 'offline')
        position = float('nan') if self.switch == 'nan' else self.position
        if self.switch == 'torn':
            return
        stamp = monotonic_ns() + (1_000_000_000 if self.switch == 'future' else 0)
        struct.pack_into('<QQQdddQ', self.measurement, 8, generation, stamp, valid, position, self.velocity, torque, 0)
        struct.pack_into('<Q', self.measurement, 0, self.sequence)

    def latest(self):
        return self.output[-1][1:4] if self.output else None

    def command_continuity(self, since, target):
        """Measure matching command gaps with a scheduler allowance for two updates."""
        matching = [stamp for stamp, _, mode, command, _ in self.output
                    if stamp >= since and mode == 1 and command == target]
        invalid = [mode for stamp, _, mode, command, _ in self.output
                   if stamp >= since and mode and (mode != 1 or command != target)]
        window = [since, *matching, monotonic()]
        gap = max(b - a for a, b in zip(window, window[1:]))
        assert matching and not invalid and gap < 0.035, f'Unexpected healthy drive behavior, gap={gap:.3f}s modes={invalid[:6]}'
        return gap


def run(installation, user, seed, mode):
    """Return independently checked native behavior and measured observations."""
    checks = {}
    observations = {}
    targets = random.Random(seed)
    arm_goal = targets.uniform(0.5, 0.7)
    table_goal = targets.uniform(-0.6, -0.4)
    later_goal = targets.uniform(0.25, 0.5)
    with tempfile.TemporaryDirectory(prefix='native-fenced-drive-') as where, ExitStack() as stack:
        root = Path(where)
        root.chmod(0o711)
        joint = 'protected_' + uuid4().hex[:8]
        unaffected = 'coupled_' + uuid4().hex[:8]
        arm, table = Drive(root, joint, stack, user), Drive(root, unaffected, stack, user)
        ns = '/fenced_' + uuid4().hex
        parameters = root / 'control.yaml'
        controllers = {'arm_position': (joint, 'position'), 'arm_effort': (joint, 'effort'), 'table_position': (unaffected, 'position')}
        types = ''.join(f'    {name}:\n      type: forward_command_controller/ForwardCommandController\n' for name in controllers)
        types += '    native_state:\n      type: joint_state_broadcaster/JointStateBroadcaster\n'
        bindings = ''.join(f'{ns}/{name}:\n  ros__parameters:\n    joints: [{joint}]\n    interface_name: {mode}\n' for name, (joint, mode) in controllers.items())
        parameters.write_text(f'{ns}/controller_manager:\n  ros__parameters:\n    update_rate: 100\n' + types + bindings)
        ros = Path(os.environ['ROS_JAZZY_PREFIX'])
        log = stack.enter_context((root / 'manager.log').open('w+'))
        candidate_env = {
            **{key: os.environ[key] for key in ('PATH', 'LANG', 'PYTHONPATH', 'RMW_IMPLEMENTATION',
                                               'ROS_AUTOMATIC_DISCOVERY_RANGE', 'ROS_DOMAIN_ID',
                                               'CYCLONEDDS_URI') if key in os.environ},
            'AMENT_PREFIX_PATH': f'{installation}:{os.environ.get("AMENT_PREFIX_PATH", "")}',
            'LD_LIBRARY_PATH': f'{installation}/lib:{os.environ.get("LD_LIBRARY_PATH", "")}',
            'HOME': str(installation.parent),
        }
        version = f'python{sys.version_info.major}.{sys.version_info.minor}'
        installed_python = (
            installation / 'lib' / version / 'site-packages',
            installation / 'lib' / version / 'dist-packages',
            installation / 'local/lib' / version / 'dist-packages',
        )
        python_paths = [str(directory) for directory in installed_python if directory.is_dir()]
        python_paths.extend(part for part in os.environ.get('PYTHONPATH', '').split(os.pathsep) if part)
        candidate_env['PYTHONPATH'] = os.pathsep.join(python_paths)
        manager = subprocess.Popen([ros / 'lib/controller_manager/ros2_control_node', '--ros-args', '--params-file', parameters,
                                    '-r', f'__ns:={ns}', '-r', f'/robot_description:={ns}/robot_description'], stdout=log, stderr=subprocess.STDOUT, env=candidate_env, start_new_session=True, **user)
        stop = threading.Event()

        def emulate():
            while not stop.is_set():
                arm.tick()
                table.tick()
                sleep(0.005)

        thread = threading.Thread(target=emulate)
        thread.start()
        rclpy.init()
        node = rclpy.create_node('fenced_drive_test', namespace=ns)
        recovery = None
        try:
            publish = node.create_publisher(String, f'{ns}/robot_description', QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))
            description = '<robot name="fenced"><link name="base"/>' + arm.description() + table.description() + '</robot>'
            listings = node.create_client(ListHardwareInterfaces, f'{ns}/controller_manager/list_hardware_interfaces')
            ready = monotonic() + 12
            while monotonic() < ready:
                publish.publish(String(data=description))
                if listings.wait_for_service(timeout_sec=0.3):
                    break
            else:
                raise RuntimeError('Manager did not expose its native hardware')
            publishers = {name: node.create_publisher(Float64MultiArray, f'{ns}/{name}/commands', 5) for name in controllers}

            def request(service, verb, packet):
                client = node.create_client(service, f'{ns}/controller_manager/{verb}')
                assert client.wait_for_service(timeout_sec=4), verb
                future = client.call_async(packet)
                rclpy.spin_until_future_complete(node, future, timeout_sec=5)
                assert future.done() and future.result() is not None, verb
                response = future.result()
                node.destroy_client(client)
                return response

            def switch(start, stop):
                packet = SwitchController.Request(activate_controllers=start, deactivate_controllers=stop, strictness=SwitchController.Request.STRICT)
                packet.timeout.sec = 2
                return request(SwitchController, 'switch_controller', packet).ok

            def claim_names():
                reply = request(ListControllers, 'list_controllers', ListControllers.Request())
                return {row.name: list(row.claimed_interfaces) for row in reply.controller if row.state == 'active'}

            def wait_for(condition, reason, limit=2.0):
                deadline = monotonic() + limit
                while monotonic() < deadline:
                    if condition():
                        return
                    rclpy.spin_once(node, timeout_sec=0.01)
                raise AssertionError(f'{reason}: arm={arm.latest()}, table={table.latest()}, arm position={arm.position:.5f}')

            for name in controllers:
                assert request(LoadController, 'load_controller', LoadController.Request(name=name)).ok
                assert request(ConfigureController, 'configure_controller', ConfigureController.Request(name=name)).ok
            wait_for(lambda: switch(['arm_position', 'table_position'], []),
                     'initial strict activation')
            for name in controllers:
                wait_for(lambda: publishers[name].get_subscription_count() > 0, 'controller command subscription')
            assert claim_names() == {'arm_position': [f'{joint}/position'], 'table_position': [f'{unaffected}/position']}
            assert arm.latest()[1] == 0
            goals = {'arm_position': arm_goal, 'table_position': table_goal}
            for name, target in goals.items():
                publishers[name].publish(Float64MultiArray(data=[target]))
            wait_for(lambda: abs(arm.position - arm_goal) < 0.04 and abs(table.position - table_goal) < 0.04, 'initial movement')
            checks['initial_claims_and_motion'] = True
            assert not switch(['arm_effort'], [])
            checks['overlapping_native_modes_rejected'] = True
            episodes = ('torn', 'stale', 'nan', 'future', 'offline')
            for phase in episodes:
                arm.switch = phase
                wait_for(lambda: arm.latest()[1] == 0, 'inhibit on ' + phase)
                assert table.latest()[1] == 1
                checks['inhibit_' + phase] = True
                if phase != 'offline':
                    arm.switch = 'healthy'
                    wait_for(lambda: arm.latest()[1] == 1, 'transient clears ' + phase)
            downtime = monotonic()
            arm.generation = 2
            assert switch([], ['arm_position']), 'release on offline boot'
            assert not switch(['arm_effort'], []), 'cannot claim while offline'
            checks['offline_release_and_rejection'] = True
            arm.switch = 'healthy'
            wait_for(lambda: (arm.latest() == (2, 0, 0.0)
                              and struct.unpack_from('<Q', arm.measurement, 24)[0] == 1), 'fenced after reboot')
            wait_for(lambda: switch(['arm_effort'], []), 'fresh effort activation')
            publishers['arm_effort'].publish(Float64MultiArray(data=[0.4]))
            wait_for(lambda: arm.latest() == (2, 2, 0.4), 'new generation effort')
            if mode == 'driver':
                arm.switch = 'old'
                wait_for(lambda: arm.latest() == (2, 0, 0.0), 'older generation rejected')
                arm.switch = 'healthy'
                wait_for(lambda: arm.latest() == (2, 2, 0.4), 'new generation returns')
                checks['fresh_effort_and_generation_replay'] = True
            wait_for(lambda: switch(['arm_position'], ['arm_effort']), 'atomic mode switch')
            publishers['arm_position'].publish(Float64MultiArray(data=[-0.2]))
            wait_for(lambda: abs(arm.position + 0.2) < 0.05, 'position recovers', limit=3)
            assert claim_names() == {'arm_position': [f'{joint}/position'], 'table_position': [f'{unaffected}/position']}
            observations['healthy_joint_mode_switch_gap_sec'] = table.command_continuity(downtime, table_goal)
            checks['strict_combined_mode_switch'] = True
            if mode == 'driver':
                return checks, observations
            assert request(LoadController, 'load_controller', LoadController.Request(name='native_state')).ok
            assert request(ConfigureController, 'configure_controller', ConfigureController.Request(name='native_state')).ok
            wait_for(lambda: switch(['native_state'], []), 'state broadcaster activation')
            assert 'native_state' in claim_names()
            arm.switch = 'offline'
            arm.generation = 3
            if mode == 'late_supervisor':
                arm.switch = 'healthy'
                wait_for(lambda: arm.latest() == (3, 0, 0.0), 'enabled writes remain fenced after healthy reboot')
                assert 'arm_position' in claim_names()
                checks['stale_claim_fenced_at_healthy_boot'] = True
            begin_recovery = monotonic()
            preferred = 'arm_effort' if mode == 'late_supervisor' else 'arm_position'
            recovery_path = installation / 'lib/fenced_drive/recover_drive'
            recovery = subprocess.Popen([recovery_path, '--ros-args', '-r', f'__ns:={ns}', '-r',
                                         f'/dynamic_joint_states:={ns}/dynamic_joint_states',
                                         '-p', 'controller_manager:=controller_manager',
                                         '-p', f'protected_joint:={joint}', '-p', f'preferred_controllers:={preferred}',
                                         '-p', 'owned_controllers:=arm_effort,arm_position'], stdout=log, stderr=subprocess.STDOUT, env=candidate_env, start_new_session=True, **user)
            def released():
                status = recovery.poll()
                if status is not None:
                    raise RuntimeError(f'Recovery node exited with status {status}')
                return 'arm_position' not in claim_names()

            wait_for(released, 'ROS supervisor releases rebooted claim', limit=5)
            checks['old_controller_released_through_manager'] = True
            if mode == 'offline_supervisor':
                assert arm.latest() == (3, 0, 0.0)
                checks['stale_claim_fenced_while_offline'] = True
            arm.switch = 'healthy'
            wait_for(lambda: preferred in claim_names(), 'ROS supervisor restores controller', limit=5)
            assert arm.latest()[0] == 3
            claimed = 'effort' if preferred == 'arm_effort' else 'position'
            assert claim_names()[preferred] == [f'{joint}/{claimed}']
            checks['new_controller_owns_native_interface'] = True
            if claimed == 'effort':
                start_position = arm.position
                effort = later_goal + 0.2
                publishers[preferred].publish(Float64MultiArray(data=[effort]))
                wait_for(lambda: arm.latest() == (3, 2, effort), 'recovered current-generation effort')
                wait_for(lambda: arm.position > start_position + 0.085, 'recovered measured effort motion', limit=2)
                observations['effort_response_displacement_rad'] = arm.position - start_position
            else:
                publishers[preferred].publish(Float64MultiArray(data=[later_goal]))
                wait_for(lambda: abs(arm.position - later_goal) < 0.05, 'supervised physical position restored', limit=3)
                observations['final_tracking_error_rad'] = abs(arm.position - later_goal)
            checks['recovered_motion'] = True
            observations['recovery_elapsed_sec'] = monotonic() - begin_recovery
            observations['healthy_joint_recovery_gap_sec'] = table.command_continuity(begin_recovery, table_goal)
            checks['healthy_joint_never_interrupted'] = True
        except (AssertionError, FileNotFoundError, RuntimeError) as exc:
            log.seek(0)
            location = traceback.extract_tb(exc.__traceback__)[-1]
            observations['error'] = f"{location.lineno}: {location.line}: {exc}"
            observations['manager_log_tail'] = log.read()[-3500:]
        finally:
            if recovery is not None:
                end_process(recovery)
            node.destroy_node()
            rclpy.try_shutdown()
            end_process(manager)
            stop.set()
            thread.join()
    return checks, observations


def end_process(process):
    """Terminate the isolated process group, including descendants."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=3)
