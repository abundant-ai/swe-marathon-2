"""Independent physical witnesses for restartable native Jazzy ownership."""

from contextlib import ExitStack
from math import isfinite
import os
from pathlib import Path
import random
import signal
import struct
import subprocess
import sys
import tempfile
from threading import Event, Thread
from time import monotonic, monotonic_ns
import traceback
from uuid import uuid4

import rclpy
from control_msgs.msg import DynamicJointState
from controller_manager_msgs.srv import (
    ConfigureController,
    ListControllers,
    ListHardwareInterfaces,
    LoadController,
    SwitchController,
)
from rclpy.qos import DurabilityPolicy, QoSProfile
from std_msgs.msg import Float64MultiArray, String

from native_checks import Drive, end_process


class LiveDrive(Drive):
    """Keep the plant alive across process deaths and independently timestamp commands."""

    def __init__(self, root, name, stack, user, generation, ledger=None):
        super().__init__(root, name, stack, user)
        self.generation = generation
        self.physical_generation = generation
        self.ledger = ledger
        self.last_command_stamp = 0
        self.published = []

    def description(self):
        urdf = super().description()
        if self.ledger is not None:
            urdf = urdf.replace(
                '</hardware>', f'<param name="generation_file">{self.ledger}</param></hardware>'
            )
        return urdf

    def tick(self):
        now = monotonic_ns()
        sequence, generation, written, mode, target, sample, _, _ = struct.unpack_from(
            '<QQQQdQQQ', self.command,
        )
        torque = -5 * self.velocity
        if (sequence and sequence % 2 == 0 and sequence == struct.unpack_from('<Q', self.command)[0]
                and self.last_command_stamp <= written <= now and now - written < 70_000_000
                and isfinite(target)):
            if written > self.last_command_stamp:
                self.output.append((written / 1e9, generation, mode, target, sample))
                self.last_command_stamp = written
            # The final actuator watchdog independently inhibits a retired physical epoch.
            if generation == self.physical_generation and mode == 1:
                torque = 18 * (target - self.position) - 7 * self.velocity
            elif generation == self.physical_generation and mode == 2:
                torque = target - 1.5 * self.velocity
        self.velocity += 0.005 * torque
        self.position += 0.005 * self.velocity
        self.sequence += 2
        struct.pack_into('<Q', self.measurement, 0, self.sequence - 1)
        healthy = int(self.switch != 'offline')
        struct.pack_into('<QQQdddQ', self.measurement, 8, self.generation, now, healthy,
                         self.position, self.velocity, torque, 0)
        struct.pack_into('<Q', self.measurement, 0, self.sequence)
        self.published.append((now / 1e9, self.generation, healthy))

    def epoch(self, physical, reported, healthy=True):
        self.physical_generation = physical
        self.generation = reported
        self.switch = 'healthy' if healthy else 'offline'


class NativeBranch:
    """Operate one actual controller manager without proxying its control decisions."""

    def __init__(self, node, root, drive, name, definitions, env, user, stack):
        self.node, self.drive, self.user, self.env = node, drive, user, env
        self.ns = f'/restart_{name}_{uuid4().hex}'
        self.manager = None
        self.clients = {}
        self.telemetry = []
        self.log = stack.enter_context((root / f'{name}.log').open('w+'))
        self.description = node.create_publisher(
            String, f'{self.ns}/robot_description',
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL),
        )
        node.create_subscription(
            DynamicJointState, f'{self.ns}/dynamic_joint_states', self.observe, 20,
        )
        self.commands = {
            controller: node.create_publisher(Float64MultiArray, f'{self.ns}/{controller}/commands', 5)
            for controller in definitions
        }
        config = root / f'{name}.yaml'
        types = ''.join(f'    {controller}:\n      type: forward_command_controller/ForwardCommandController\n'
                        for controller in definitions)
        types += '    state_observer:\n      type: joint_state_broadcaster/JointStateBroadcaster\n'
        bindings = ''.join(
            f'{self.ns}/{controller}:\n  ros__parameters:\n    joints: [{drive.joint}]\n    interface_name: {mode}\n'
            for controller, mode in definitions.items()
        )
        config.write_text(f'{self.ns}/controller_manager:\n  ros__parameters:\n    update_rate: 100\n'
                          + types + bindings)
        self.load_names = ('state_observer', *definitions)
        self.manager_argv = [
            Path(os.environ['ROS_JAZZY_PREFIX']) / 'lib/controller_manager/ros2_control_node',
            '--ros-args', '--params-file', config, '-r', f'__ns:={self.ns}',
            '-r', f'/robot_description:={self.ns}/robot_description',
        ]

    def observe(self, message):
        if self.drive.joint not in message.joint_names:
            return
        state = message.interface_values[message.joint_names.index(self.drive.joint)]
        values = dict(zip(state.interface_names, state.values))
        fields = ('drive_generation', 'drive_healthy', 'drive_authorized_generation')
        if all(isfinite(values.get(name, float('nan'))) for name in fields):
            self.telemetry.append((monotonic(), *(int(values[name]) for name in fields)))

    def request(self, service, verb, packet, wait=2.5):
        if verb not in self.clients:
            self.clients[verb] = self.node.create_client(service, f'{self.ns}/controller_manager/{verb}')
        client = self.clients[verb]
        if not client.wait_for_service(timeout_sec=wait):
            return None
        future = client.call_async(packet)
        rclpy.spin_until_future_complete(self.node, future, timeout_sec=wait)
        if not future.done():
            future.cancel()
            return None
        return future.result()

    def start(self):
        self.manager = subprocess.Popen(self.manager_argv, env=self.env, stdout=self.log,
                                        stderr=subprocess.STDOUT, start_new_session=True, **self.user)

        def ready():
            self.description.publish(String(
                data='<robot name="restart"><link name="base"/>' + self.drive.description() + '</robot>'
            ))
            packet = self.request(ListHardwareInterfaces, 'list_hardware_interfaces',
                                  ListHardwareInterfaces.Request(), wait=0.2)
            return packet and {f'{self.drive.joint}/position', f'{self.drive.joint}/effort'} <= {
                entry.name for entry in packet.command_interfaces if entry.is_available
            }

        wait_for(self.node, ready, f'{self.ns} interfaces after boot', 10)
        for controller in self.load_names:
            reply = self.request(LoadController, 'load_controller', LoadController.Request(name=controller))
            assert reply and reply.ok, f'{self.ns}: load {controller}'
            reply = self.request(ConfigureController, 'configure_controller',
                                 ConfigureController.Request(name=controller))
            assert reply and reply.ok, f'{self.ns}: configure {controller}'
        assert self.switch(['state_observer']), f'{self.ns}: activate native state broadcaster'

    def switch(self, start=(), stop=()):
        packet = SwitchController.Request(
            activate_controllers=list(start), deactivate_controllers=list(stop),
            strictness=SwitchController.Request.STRICT,
        )
        packet.timeout.sec = 1
        reply = self.request(SwitchController, 'switch_controller', packet)
        assert reply is not None, f'{self.ns}: missing strict-switch response'
        return reply.ok

    def claims(self):
        reply = self.request(ListControllers, 'list_controllers', ListControllers.Request())
        assert reply is not None, f'{self.ns}: missing controller readback'
        return {row.name: list(row.claimed_interfaces) for row in reply.controller if row.state == 'active'}

    def send(self, controller, value):
        self.commands[controller].publish(Float64MultiArray(data=[value]))

    def stop(self):
        if self.manager is not None:
            end_process(self.manager)
            self.manager = None

    def kill(self):
        assert self.manager is not None and killed(self.manager), f'{self.ns}: expected manager SIGKILL'
        self.manager = None


def killed(process):
    if process.poll() is not None:
        return False
    os.killpg(process.pid, signal.SIGKILL)
    return process.wait(timeout=3) == -signal.SIGKILL


def wait_for(node, condition, detail, seconds=4):
    end = monotonic() + seconds
    while monotonic() < end:
        if condition():
            return
        rclpy.spin_once(node, timeout_sec=0.02)
    raise AssertionError(detail)


def runtime_environment(installation, home):
    keep = ('PATH', 'LANG', 'RMW_IMPLEMENTATION', 'ROS_AUTOMATIC_DISCOVERY_RANGE',
            'ROS_DOMAIN_ID', 'CYCLONEDDS_URI')
    result = {key: os.environ[key] for key in keep if key in os.environ}
    for key, prefix in (('AMENT_PREFIX_PATH', installation), ('LD_LIBRARY_PATH', installation / 'lib')):
        result[key] = os.pathsep.join([str(prefix), *filter(None, os.environ.get(key, '').split(os.pathsep))])
    version = f'python{sys.version_info.major}.{sys.version_info.minor}'
    ros = Path(os.environ['ROS_JAZZY_PREFIX'])
    module_dirs = [prefix / path for prefix in (installation, ros) for path in (
        f'lib/{version}/site-packages', f'lib/{version}/dist-packages', f'local/lib/{version}/dist-packages',
    )]
    result['PYTHONPATH'] = os.pathsep.join(
        [str(path) for path in module_dirs if path.is_dir()]
        + list(filter(None, os.environ.get('PYTHONPATH', '').split(os.pathsep)))
    )
    result['HOME'] = str(home)
    result['ROS_LOG_DIR'] = str(home)
    return result


def launch_client(installation, primary, preferred, journal, log, env, user):
    return subprocess.Popen([
        installation / 'lib/fenced_drive/recover_drive', '--ros-args', '-r', f'__ns:={primary.ns}',
        '-p', 'controller_manager:=controller_manager',
        '-p', f'state_topic:={primary.ns}/dynamic_joint_states',
        '-p', f'protected_joint:={primary.drive.joint}',
        '-p', f'preferred_controllers:={preferred}',
        '-p', 'owned_controllers:=hold_position,recover_effort',
        '-p', f'generation_journal:={journal}',
    ], env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, **user)


def run_restart(installation, user, seed, driver):
    """Kill and replace the protected manager while a second manager keeps moving."""
    checks, details = {}, {}
    rng = random.Random(seed)
    initial = rng.randrange(11, 69)
    newest = initial + rng.randrange(2, 11)
    retired = initial - 1 if driver else initial
    branch = client = observer = sibling = None
    with tempfile.TemporaryDirectory(prefix='native-restart-') as folder, ExitStack() as stack:
        root = Path(folder)
        root.chmod(0o711)
        durable = root / 'durable'
        durable.mkdir(mode=0o700)
        if user:
            os.chown(durable, user['user'], user['group'])
        env = runtime_environment(installation, durable)
        journal = durable / 'client.gen'
        drive = LiveDrive(root, 'drive_' + uuid4().hex[:8], stack, user, initial,
                          durable / 'hardware.gen' if driver else None)
        aux = LiveDrive(root, 'aux_' + uuid4().hex[:8], stack, user, rng.randrange(2, 7))
        stop = Event()

        def emulate():
            while not stop.is_set():
                drive.tick()
                aux.tick()
                stop.wait(0.005)

        thread = Thread(target=emulate)
        thread.start()
        client_log = stack.enter_context((root / 'client.log').open('w+'))
        try:
            rclpy.init()
            observer = rclpy.create_node('restart_probe_' + uuid4().hex)
            branch = NativeBranch(observer, root, drive, 'primary',
                                  {'hold_position': 'position', 'recover_effort': 'effort'},
                                  env, user, stack)
            sibling = NativeBranch(observer, root, aux, 'independent', {'table_position': 'position'},
                                   env, user, stack)
            stack.callback(sibling.stop)
            stack.callback(branch.stop)
            branch.start()
            sibling.start()
            wait_for(observer, lambda: sibling.switch(['table_position']),
                     'initial independent position owner')
            if driver:
                wait_for(observer, lambda: branch.switch(['hold_position']),
                         'initial protected position owner')
            else:
                client = launch_client(installation, branch, 'hold_position', journal, client_log, env, user)
                wait_for(observer, lambda: 'hold_position' in branch.claims(), 'initial client acquisition')

            target = rng.uniform(0.43, 0.50)
            aux_initial = rng.uniform(-0.30, -0.19)

            def initial_motion():
                branch.send('hold_position', target)
                sibling.send('table_position', aux_initial)
                return abs(drive.position - target) < 0.06 and abs(aux.position - aux_initial) < 0.06

            wait_for(observer, initial_motion, 'independent measured initial movement', 4)
            assert branch.claims()['hold_position'] == [f'{drive.joint}/position']
            checks['initial_claim_and_motion'] = True
            details['initial_generation'] = initial
            details['highest_precrash_generation'] = newest
            # Advance the fence before this generation ever receives an active controller.
            drive.epoch(newest, newest, healthy=False)
            stamp = monotonic()
            wait_for(observer, lambda: any(t >= stamp and g == newest and h == 0
                                          for t, g, h, _ in branch.telemetry[-30:]),
                     'higher offline generation not observed')
            if client is not None:
                wait_for(observer, lambda: 'hold_position' not in branch.claims(),
                         'client must observe the higher offline generation before kill')
            else:
                assert branch.switch([], ['hold_position']), 'release original position claim'
            assert drive.latest()[1] == 0
            checks['higher_epoch_observed_while_offline'] = True

            boundary = monotonic()
            if client is not None:
                assert killed(client), 'expected recovery client SIGKILL'
                client = None
            branch.kill()
            aux_resume_position = aux.position
            aux_setpoint = rng.uniform(0.30, 0.40)
            sibling.send('table_position', aux_setpoint)
            drive.epoch(newest, retired)
            retired_start = monotonic()
            branch.start()
            if not driver:
                client = launch_client(installation, branch, 'recover_effort', journal, client_log, env, user)
                # In this layered test the ordinary memory-only hardware is intentionally
                # able to accept the replay. The supervisor has independent responsibility.
                wait_for(observer, lambda: any(t >= retired_start and g == retired and h == 1
                                              for t, g, h, _ in branch.telemetry[-30:]),
                         'healthy-looking retired telemetry did not reach the client graph')
            else:
                # The raw caller targets the actual manager even when no supervisor exists.
                details['raw_retired_switch_accepted'] = False
                for _ in range(4):
                    if branch.switch(['recover_effort']):
                        details['raw_retired_switch_accepted'] = True
                        break
                    rclpy.spin_once(observer, timeout_sec=0.045)

            active_samples = 0
            end = monotonic() + rng.uniform(1.1, 1.5)
            while monotonic() < end:
                branch.send('recover_effort', 0.75)
                sibling.send('table_position', aux_setpoint)
                active_samples += 'recover_effort' in branch.claims()
                rclpy.spin_once(observer, timeout_sec=0.01)
                stop.wait(0.02)
            retired_end = monotonic()
            writes = [row for row in drive.output if retired_start <= row[0] < retired_end and row[2]]
            raw = [row for row in drive.published if retired_start <= row[0] < retired_end
                   and row[1:] == (retired, 1)]
            details['retired_generation'] = retired
            details['retired_healthy_input_frames'] = len(raw)
            details['retired_claim_observations'] = active_samples
            details['retired_enabled_command_frames'] = len(writes)
            checks['retired_epoch_never_claimed'] = (
                len(raw) > 30 and not active_samples and not details.get('raw_retired_switch_accepted', False)
            )
            checks['retired_epoch_never_wrote'] = len(raw) > 30 and not writes

            if driver and 'recover_effort' in branch.claims():
                branch.switch([], ['recover_effort'])
            drive.epoch(newest, newest)
            renewed = monotonic()
            wait_for(observer, lambda: any(t >= renewed and g == newest and h == 1
                                          for t, g, h, _ in branch.telemetry[-30:]),
                     'fresh equal-generation readback')
            if driver:
                wait_for(observer, lambda: branch.switch(['recover_effort']),
                         'raw fresh strict switch should succeed')
            else:
                wait_for(observer, lambda: 'recover_effort' in branch.claims(), 'client did not reacquire')
            assert branch.claims()['recover_effort'] == [f'{drive.joint}/effort']
            checks['fresh_native_effort_claim'] = True
            position = drive.position
            effort = rng.uniform(0.65, 0.90)

            def restored_motion():
                branch.send('recover_effort', effort)
                sibling.send('table_position', aux_setpoint)
                return drive.latest() == (newest, 2, effort) and drive.position - position >= 0.10

            wait_for(observer, restored_motion, 'fresh native effort and measured displacement')
            checks['fresh_measured_motion'] = True
            details['restored_displacement_rad'] = drive.position - position
            details['restoration_seconds_after_readback'] = monotonic() - renewed
            details['sibling_displacement_rad'] = aux.position - aux_resume_position
            assert sibling.claims()['table_position'] == [f'{aux.joint}/position']
            samples = [row for row in aux.output if row[0] >= boundary]
            commanded = [row for row in samples if row[1:3] == (aux.physical_generation, 1)]
            unexpected = [row for row in samples if row[2] != 0 and row[1:3] != (aux.physical_generation, 1)]
            # A watchdog can inhibit individual cycle records. Measure the gap
            # between valid position writes, so inhibits cannot hide an outage.
            window = [boundary, *(row[0] for row in commanded), monotonic()]
            largest_gap = max(b - a for a, b in zip(window, window[1:]))
            details['sibling_max_command_gap_s'] = largest_gap
            details['sibling_position_command_frames'] = len(commanded)
            details['sibling_disabled_frames'] = sum(row[2] == 0 for row in samples)
            details['sibling_unexpected_enabled_frames'] = len(unexpected)
            details['sibling_final_position_error_rad'] = abs(aux.position - aux_setpoint)
            checks['independent_manager_kept_actuating'] = (
                len(commanded) > 80 and largest_gap < 0.13 and not unexpected
                and aux.position - aux_resume_position > 0.25
                and details['sibling_final_position_error_rad'] < 0.09
            )
        except (AssertionError, OSError, RuntimeError) as exc:
            call = traceback.extract_tb(exc.__traceback__)[-1]
            details['error'] = f'{call.lineno}: {exc}'
            for label, stream in (('supervisor', client_log), ('manager', branch.log if branch else None),
                                  ('sibling', sibling.log if sibling else None)):
                if stream is not None:
                    stream.seek(0)
                    details[f'{label}_log_tail'] = stream.read()[-2700:]
        finally:
            if client is not None:
                end_process(client)
            if observer is not None:
                observer.destroy_node()
            rclpy.try_shutdown()
            stop.set()
            thread.join()
    return checks, details
