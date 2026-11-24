"""Identify real actuator traces and qualify physical compensation on held-out plants."""

from contextlib import ExitStack
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from subprocess import TimeoutExpired

import mujoco
import numpy as np

from commission import commissioning, deployment_template
from fixtures import JOINTS, Physical, Record, TruthPolicy, export, manifest
from native import model
from transport import Rejected, Stream, batch, dump, require, writable


@dataclass(frozen=True)
class Servo:
    """Planted drive coupling measured via MuJoCo's actuator force channel."""

    delays: np.ndarray
    gain: np.ndarray
    stiffness: np.ndarray
    damping: np.ndarray
    bias: np.ndarray


def servo(seed: int, size: int) -> Servo:
    """Construct a non-diagonal drive, with differing delay at each joint."""
    rng = np.random.default_rng(seed)
    spring = rng.uniform(28., 40., size)
    damping = rng.uniform(1.08, 1.64, size)
    delays = (np.asarray([5, 1, 7, 2, 4, 0, 6, 3])[:size] + seed % 8) % 8
    scales = rng.uniform(.71, 1.46, size)
    matrix = np.diag(spring * scales)
    for axis in range(size):
        matrix[axis, (axis + 1) % size] = spring[axis] * (-.36 if axis % 2 else .43)
        matrix[axis, (axis + 2) % size] = spring[axis] * (.20 if axis % 2 else -.25)
    bias = rng.uniform(-1.5, 1.5, size) + np.where(np.arange(size) % 2 == 0, 2.6, -3.)
    return Servo(delays, matrix, spring, damping, bias)


class Plant:
    """Wrap the authored MJCF in a delayed explicit drive and new native limb inertias."""

    def __init__(self, order: list[str], drive: Servo, seed: int, *, load: bool):
        self.model = model(mass_scale=1.28 if load else .88, damping_scale=1.2 if load else .93)
        world = self.model
        rng = np.random.default_rng(seed)
        for body in range(1, world.nbody):
            if world.body_mass[body] < .06:
                continue
            multiplier = rng.uniform(.66, 2.15) if load else rng.uniform(.91, 1.16)
            world.body_mass[body] *= multiplier
            world.body_inertia[body] *= multiplier
        world.actuator_biastype[:] = mujoco.mjtBias.mjBIAS_AFFINE
        world.actuator_biasprm[:, :] = 0.
        world.actuator_gainprm[:, 0] = 1.
        self.data = mujoco.MjData(world)
        mujoco.mj_setConst(world, self.data)
        self.qslots = np.array([int(world.joint(name).qposadr[0]) for name in order])
        self.dslots = np.array([int(world.joint(name).dofadr[0]) for name in order])
        self.aslots = np.array([world.actuator(f'servo-{name}').id for name in order])
        world.actuator_biasprm[self.aslots, 1] = -drive.stiffness
        world.actuator_biasprm[self.aslots, 2] = -drive.damping
        self.order, self.servo = order, drive
        self.history = [np.zeros(len(order)) for _ in range(8)]
        self.data.qpos[self.qslots] = rng.uniform(-.22, .22, len(order))
        self.data.qvel[self.dslots] = rng.uniform(-.38, .38, len(order))
        mujoco.mj_forward(world, self.data)

    def actuate(self, command: np.ndarray, external: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Advance actuator history, measure native torque and step the real rigid bodies."""
        self.history.append(command.copy())
        self.history = self.history[-9:]
        before = self.data.qpos[self.qslots].copy()
        speed = self.data.qvel[self.dslots].copy()
        delayed = np.array([self.history[-1-delay] for delay in self.servo.delays])
        motor = np.einsum('ij,ij->i', self.servo.gain, delayed)
        self.data.ctrl[self.aslots] = motor + self.servo.bias
        self.data.qfrc_applied[self.dslots] = external
        mujoco.mj_forward(self.model, self.data)
        measured = self.data.actuator_force[self.aslots].copy()
        mujoco.mj_step(self.model, self.data)
        return before, speed, measured

    def observation(self, tick: int, seed: int) -> Physical:
        """Provide measured native state and an independent changing source task signal."""
        phase = seed * .11
        command = [.63*np.sin(tick*.029+phase)+.18*np.cos(tick*.083),
                   .58*np.sin(tick*.041-phase) + .18*np.cos(tick*.019+1.4),
                   .46*np.cos(tick*.033+phase*.58) - .27*np.sin(tick*.061)]
        if tick >= 136:
            command[1] += .16
        return Physical(dict(zip(self.order, self.data.qpos[self.qslots].tolist(), strict=True)),
                        dict(zip(self.order, self.data.qvel[self.dslots].tolist(), strict=True)),
                        [1., 0., 0., 0.], [.015, -.02, .03], [float(x) for x in command])


def excitation(order, drive, seed, start, count, *, periodic=False):
    """Generate a measured multiaxis commissioning tape and independent effort noise."""
    plant = Plant(order, drive, seed, load=False)
    random = np.random.default_rng(seed + 873)
    rows, u = [], np.zeros(len(order))
    cycle = random.uniform(-.27, .27, (8,len(order))) if periodic else None
    for i in range(count):
        u = cycle[i%8] if periodic else .55*u + .21*random.uniform(-1., 1., len(order))
        q, dq, effort = plant.actuate(u, np.zeros(len(order)))
        measured = effort + random.normal(0., .017, len(order))
        rows.append({'tick': start+i, 'requested_rad': u.tolist(), 'position_rad': q.tolist(),
                     'velocity_rad_s': dq.tolist(), 'effort_nm': measured.tolist()})
    return rows


def identify_spec(seed, order, variant='ok'):
    """Construct separate native captures and outcome controls."""
    native = servo(seed, len(order))
    fit = excitation(order, native, seed+21, 68, 186, periodic=(variant=='ambiguous-delay'))
    check = excitation(order, native, seed+76, 1200, 117)
    if variant == 'changed-holdout':
        for k, row in enumerate(check):
            row['effort_nm'][1] += 1.4 + .3*np.cos(k*.11)
    elif variant == 'unexcited':
        for row in fit:
            row['requested_rad'] = [0.] * len(order)
    elif variant == 'invalid':
        fit[23]['tick'] += 1
    return ({'joint_order': order, 'delay_candidates': [8,0] if variant=='ambiguous-delay' else [3,0,7,4,2,6,1,5], 'fit': fit, 'validation': check,
             'limits': {'ambiguity_rmse_nm': .005, 'max_validation_rmse_nm': .06}}, native)


def expected_rms(tape, fitted, axis, history):
    """Recompute stated torque metrics directly from a sealed commissioning recording."""
    errors = []
    for k in range(history, len(tape)):
        row = tape[k]
        control = tape[k-fitted['delays_ticks'][axis]]['requested_rad']
        predicted = sum(g*u for g,u in zip(fitted['command_gain_nm_rad'][axis], control, strict=True))
        predicted += fitted['bias_nm'][axis]
        predicted -= fitted['position_gain_nm_rad'][axis]*row['position_rad'][axis]
        predicted -= fitted['velocity_gain_nm_s_rad'][axis]*row['velocity_rad_s'][axis]
        errors.append((predicted-row['effort_nm'][axis])**2)
    return float(np.sqrt(np.mean(errors)))


def verify_model(report, spec, physical, status):
    """Check measured parameter recovery and independently replay the report's torques."""
    require(isinstance(report, dict) and report.get('status') == status, f'drive fit did not report {status}')
    require(report.get('joint_order') == spec['joint_order'], 'drive model changed canonical names or order')
    if status == 'unidentifiable':
        require('model' in report and report['model'] is None and 'metrics' in report and report['metrics'] is None,
                'unidentified model must not be exported')
        return
    truth = {'delays_ticks': physical.delays, 'command_gain_nm_rad': physical.gain,
             'position_gain_nm_rad': physical.stiffness, 'velocity_gain_nm_s_rad': physical.damping,
             'bias_nm': physical.bias}
    found = report['model']
    for key, value in truth.items():
        tolerance = 0. if key == 'delays_ticks' else (.035 if key == 'velocity_gain_nm_s_rad' else .10)
        actual = np.asarray(found[key], dtype=float)
        require(actual.shape == value.shape and np.max(np.abs(actual-value)) <= tolerance,
                f'independently measured coefficients mismatch for {key}')
        if key == 'delays_ticks':
            require(all(type(item) is int for item in found[key]), 'delays must be integers')
    metrics = report['metrics']
    for tape in ('fit','validation'):
        expected = [expected_rms(spec[tape], found, axis, max(spec['delay_candidates'])) for axis in range(len(spec['joint_order']))]
        received = metrics[f'{tape}_rmse_nm']
        require(np.shape(received) == np.shape(expected) and np.allclose(received, expected, atol=1e-7, rtol=1e-6),
                'reported effort errors do not use the frozen model and common support')


def model_case(app: Path, root: Path, seed: int, size: int, variant: str):
    """Check fit, malformed journal or validation-only changes with sealed ground truth."""
    keys = list(reversed(JOINTS[:size]))
    spec, native = identify_spec(seed, keys, variant)
    destination = writable(root/'fit')/'drive.json'
    output = batch(app, ['calibrate-drive', '--spec', str(dump(root/'capture.json', spec))], destination,
                   invalid=(variant == 'invalid'))
    if variant == 'invalid':
        return {'invalid_output_preserved': True}
    status = {'unexcited': 'unidentifiable', 'ambiguous-delay': 'unidentifiable',
              'changed-holdout': 'validation_failed'}.get(variant, 'ok')
    verify_model(output, spec, native, status)
    if variant == 'changed-holdout':
        clean, _ = identify_spec(seed, keys)
        original = batch(app, ['calibrate-drive', '--spec', str(dump(root/'clean.json', clean))], destination)
        require(original.get('model') == output.get('model'), 'validation changed fitted drive model')
    return {'status': status, 'axes': len(keys)}


def frozen_actor(metadata: Record) -> Record:
    """Install a nonconstant frozen source actor in the existing observation interface."""
    spec = deepcopy(metadata)
    names = spec['action_order']
    width = 9+3*len(names)
    spec['observation'] = {'terms': ['command','joint_position','joint_velocity','last_action','gravity','angular_velocity'],
                           'history': 2, 'mean': [0.]*width, 'std': [1.]*width, 'clip': [5.]*width}
    weights = np.zeros((len(names), 2*width))
    for i,name in enumerate(names):
        weights[i,width+i%3] = (-1 if i%2 else 1)*.76
        weights[i,width+(i+1)%3] = .31 if i%2 else -.29
        weights[i,(i+2)%3] = .14
        velocity = width + 3 + len(names) + spec['observation_order'].index(name)
        weights[i,velocity] = -.022
        joint = spec['joints'][name]
        joint['reference'] = [.24,-.18,.32,-.31,.08,.20,-.23,.28][i]
        spec['actions'][name].update(scale=.56, minimum=-.85, maximum=.85)
        slot = spec['model']['actuator_order'].index(spec['actions'][name]['actuator'])
        spec['model']['neutral'][slot] = joint['zero'] + joint['sign']*joint['reference']
    spec['policy'] = {'layers': [{'weights': weights.tolist(), 'bias': [0.]*len(names), 'activation': 'linear'}],
                      'action_clip': [1.05]*len(names)}
    spec['policy_period_ticks'] = 3
    return spec


def canonical_bus(spec, bus, order):
    """Decode submitted actuator values into commissioning coordinates."""
    require(isinstance(bus, list) and len(bus) == len(spec['model']['actuator_order']), 'wrong actuator bus width')
    require(all(type(v) in (int, float) and np.isfinite(v) for v in bus), 'invalid actuator bus')
    keyed = {key: val for key, val in zip(spec['model']['actuator_order'], bus, strict=True)}
    active = {entry['actuator'] for entry in spec['actions'].values()}
    for i, key in enumerate(spec['model']['actuator_order']):
        if key not in active:
            require(bus[i] == spec['model']['neutral'][i], 'drive changed a passive bus slot')
    return np.array([spec['joints'][joint]['sign']*(keyed[spec['actions'][joint]['actuator']]-spec['joints'][joint]['zero'])
                     for joint in order])


def observe_actor(reply, truth):
    """Confirm the actual plant's observations reached the unchanged actor."""
    require(reply.get('status') == truth['status'], 'changed actor cadence or watchdog state')
    for label in ('observation','action','target'):
        expected = truth[label]
        if expected is None:
            require(label in reply and reply[label] is None, f'changed {label} while the actor held')
        else:
            actual = reply.get(label)
            require(np.shape(actual)==np.shape(expected) and np.allclose(actual, expected, rtol=1e-8, atol=1e-8),
                    f'compensation changed the frozen {label}')


def settle_time(trace, start, *, band=.17, ticks=12):
    """Locate a full sustained in-tolerance interval after a physical event."""
    for index in range(start, min(len(trace)-ticks+1, start+111)):
        if np.max(np.abs(trace[index:index+ticks])) <= band:
            return index-start
    return None


def rollout(app: Path, root: Path, *, seed: int, size: int, stop: bool, mapped=False,
            twin=False, max_step=.032, direct=None):
    """Score actual native trajectories and recovery with the submitted bus as the only control."""
    calibration = None
    if mapped:
        capture, metadata, _ = commissioning(seed, size, 'deploy')
        if direct is None:
            calibration = writable(root/'layout')/'report.json'
            result = batch(app, ['calibrate','--spec',str(dump(root/'clock.json', capture))], calibration)
            require(result.get('status') == 'ok', 'could not recover the live backend layout')
    else:
        metadata = manifest(seed, seed % 5, count=size)
    spec = frozen_actor(metadata)
    order = list(reversed(JOINTS[:size]))
    identification, native = identify_spec(seed+901, order)
    safety = {'joint_order': order, 'command_min_rad': [-.99]*size, 'command_max_rad': [.99]*size,
              'max_step_rad': [max_step+.003*(i%3) for i in range(size)]}
    commissioned = None
    safety_path = None
    if direct is None:
        commissioned = writable(root/'model')/'report.json'
        fit = batch(app, ['calibrate-drive','--spec',str(dump(root/'drive-log.json', identification))], commissioned)
        verify_model(fit, identification, native, 'ok')
        safety_path = dump(root/'safety.json', safety)
    actor, baseline_actor = TruthPolicy(spec), TruthPolicy(spec)
    actual, baseline = [Plant(order, native, seed+1107, load=True) for _ in range(2)]
    qinds = [spec['action_order'].index(key) for key in order]
    neutral = canonical_bus(spec, spec['model']['neutral'], order)
    for plant in (actual, baseline):
        plant.data.qpos[plant.qslots] = neutral + np.linspace(-.09,.11,size)
        plant.history = [neutral.copy() for _ in range(8)]
    previous = neutral.copy()
    errs, baseline_errors, qhistory, vhistory, reference = [], [], [], [], []
    goal = neutral.copy()
    goal_base = goal.copy()
    origin = 0
    emergency = (196, 205)
    limits = np.array(safety['max_step_rad'])
    if direct is None:
        client = Stream(app, root/'session', deployment_template(spec) if mapped else spec,
                        calibration=calibration, drive=commissioned, safety=safety_path)
    else:
        client = direct(spec, identification, safety)
    actions = 0
    with ExitStack() as stack:
        stream = stack.enter_context(client)
        continuous = None
        if twin and direct is None:
            continuous = stack.enter_context(Stream(app, root/'uninterrupted', deployment_template(spec) if mapped else spec,
                                                    calibration=calibration, drive=commissioned, safety=safety_path))
        for tick in range(365):
            a = actual.observation(tick, seed)
            b = baseline.observation(tick, seed)
            if stop and tick == emergency[1]:
                packet = {'kind':'arm', 'tick':tick}
                expect = actor.quiet('armed')
                check_baseline = baseline_actor.quiet('armed')
                actor, baseline_actor = TruthPolicy(spec), TruthPolicy(spec)
                origin = tick
            elif stop and emergency[0] <= tick < emergency[1]:
                packet = {'kind':'step', 'healthy':False, 'tick':tick}
                expect, check_baseline = actor.quiet('latched'), baseline_actor.quiet('latched')
            elif (tick-origin) % spec['policy_period_ticks'] == 0:
                packet = export(spec, a, tick, sign_flip=tick%3==0)
                expect, check_baseline = actor.evaluate(a), baseline_actor.evaluate(b)
                goal, goal_base = np.asarray(expect['target'])[qinds], np.asarray(check_baseline['target'])[qinds]
                actions += 1
            else:
                packet = export(spec, a, tick, sign_flip=tick%3==0)
                expect, check_baseline = actor.quiet('held'), baseline_actor.quiet('held')
            reply = stream.push(packet)
            if continuous is not None:
                require(reply == continuous.push(packet), 'restart changed a future command on identical telemetry')
            observe_actor(reply, expect)
            command = canonical_bus(spec, reply.get('control'), order)
            if expect['status'] in ('updated','held'):
                require(np.max(np.abs(command)) <= .99+1e-9, 'command exceeded commissioned limits')
                require(np.all(np.abs(command-previous) <= limits+1e-9), 'command exceeded causal slew limit')
            else:
                require(np.array_equal(command, neutral), 'watchdog or arm did not return neutral')
            previous = command
            if tick in ((53, 112, 198, 267) if stop else (93, 221)):
                stream.restart()
                require(stream.push(packet) == reply, 'restart lost a command or actor decision')
            load = np.where(np.arange(size)%2 == 0, 1.26, -.80)
            if 110 <= tick < 132:
                load = load + np.where(np.arange(size)%2 == 0, 2.15, -1.93)
            if tick >= 251:
                load = load + np.where(np.arange(size)%3 == (seed%3), -4.3, 4.5)
            elif 82 <= tick < 175:
                load = load + np.where(np.arange(size)%2 == 0, 2.8, -2.9)
            q, v, _ = actual.actuate(command, load)
            qb, _, _ = baseline.actuate(canonical_bus(spec, check_baseline['control'], order), load)
            require(np.isfinite(q).all() and np.isfinite(v).all(), 'native plant became nonfinite')
            qhistory.append(q)
            vhistory.append(v)
            errs.append(q-goal)
            baseline_errors.append(qb-goal_base)
            reference.append(goal.copy())
    error = np.array(errs)
    baseline_error = np.array(baseline_errors)
    max_q, max_v = float(np.max(np.abs(qhistory))), float(np.max(np.abs(vhistory)))
    eligible = [t for t in range(90,len(error)) if not (stop and emergency[0] <= t < emergency[1]+85)]
    score = float(np.sqrt(np.mean(error[eligible]**2)))
    mismatch = float(np.sqrt(np.mean(baseline_error[eligible]**2)))
    sustained = float(np.sqrt(np.mean(error[315:]**2)))
    recovery = settle_time(error, 132)
    rearm = settle_time(error, emergency[1]) if stop else None
    require(np.linalg.norm(np.ptp(np.asarray(reference),axis=0)) > .63 and actions > 100,
            'the native qualification did not commission a changing motion')
    require(score <= .11 and sustained <= .10 and max_q <= 1.10 and max_v <= 10.,
            f'physical tracking or stability out of bounds: rms={score:.4f}, sustained={sustained:.4f}, q={max_q:.4f}, dq={max_v:.4f}')
    require(recovery is not None and (not stop or rearm is not None),
            f'did not recover a sustained tracking interval: disturbance={recovery}, rearm={rearm}')
    return {'target_rmse_rad': score, 'uncompensated_rmse_rad': mismatch, 'late_loaded_rmse_rad': sustained, 'peak_rad': max_q,
            'peak_speed_rad_s': max_v, 'recovery_after_disturbance_ticks': recovery,
            'recovery_after_rearm_ticks': rearm, 'physics_ticks': len(error), 'actor_updates': actions}


def reject_unqualified(app: Path, root: Path):
    """An invalid commissioning report cannot start issuing live motor commands."""
    order = list(JOINTS[:4])
    spec, physical = identify_spec(367, order, 'changed-holdout')
    path = writable(root/'model')/'report.json'
    fit = batch(app, ['calibrate-drive','--spec',str(dump(root/'capture.json', spec))], path)
    verify_model(fit, spec, physical, 'validation_failed')
    deployment = frozen_actor(manifest(55, 2, count=4))
    safe = dump(root/'safety.json', {'joint_order':order, 'command_min_rad':[-1.]*4,
                                    'command_max_rad':[1.]*4,'max_step_rad':[.04]*4})
    with Stream(app, root/'inadmissible', deployment, drive=path, safety=safe) as stream:
        try:
            stream.push({'kind':'arm', 'tick':0})
        except Rejected:
            try:
                status = stream.process.wait(timeout=4)
            except TimeoutExpired:
                raise Rejected('unqualified driver left its process running') from None
            require(status != 0 and not list(stream.state.iterdir()),
                    'unqualified driver was not rejected before committing state')
        else:
            raise Rejected('unqualified drive controller responded to arm')
    return {'unsafe_model_refused': True}
