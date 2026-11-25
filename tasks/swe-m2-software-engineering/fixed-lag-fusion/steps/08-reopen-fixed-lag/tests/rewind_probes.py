"""Private live streams and independent all-history square-root verification."""

import json
import math
import os
from pathlib import Path
import pwd
from selectors import DefaultSelector, EVENT_READ
import signal
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import monotonic

import gtsam as gt
from gtsam.symbol_shorthand import L, X
import numpy as np

WORLD_POINTS = ((1.9, .6, 3.9), (-1.4, 1.4, 4.9), (.1, -1.8, 5.6), (.9, 1.7, 6.5))


def transform(row):
    return gt.Pose3(gt.Rot3.Quaternion(*row['quaternion_wxyz']), np.array(row['translation']))


def wire(pose):
    q = pose.rotation().toQuaternion()
    return dict(translation=list(pose.translation()), quaternion_wxyz=[q.w(), q.x(), q.y(), q.z()])


def fixture(seed):
    """Author metric six-DOF motion and pixel observations with a degraded-camera interval."""
    rng = np.random.default_rng(seed)
    handover = gt.Pose3(gt.Rot3.Ypr(0.08, -0.04, 0.16), np.array([-0.17, 0.1, 0.08]))
    intrinsics = [240., 260., 0., 320., 240.]
    world = [np.array(p) for p in WORLD_POINTS]
    names = [f'p{j}' for j in range(len(world))]
    landmarks = {name: {'point': (point + rng.normal(0., .22, 3)).tolist(), 'sigma': .65}
                 for name, point in zip(names, world)}
    truth = []
    sign = -1 if seed % 2 else 1
    for k in range(48):
        angle = k * .16
        truth.append(gt.Pose3(
            gt.Rot3.Ypr(sign * (.38 * math.sin(angle) + .034*k),
                        .13 * math.cos(angle*.7), .16 * math.sin(angle*.83)),
            np.array([1.15 * math.sin(angle), sign * .9 * (1.-math.cos(angle)),
                      .38 * math.sin(.48*angle) + .015*k]),
        ))
    manifest = {
        'lag_frames': 5 if sign < 0 else 6, 'rewind_frames': 14 if sign < 0 else 15,
        'initial_pose': wire(truth[0]), 'initial_sigmas': [.025, .025, .025, .035, .035, .035],
        'odometry_sigmas': [.043, .047, .047, .075, .067, .075],
        'landmarks': landmarks,
        'calibrations': {
            'a': {'body_from_camera': wire(gt.Pose3()), 'intrinsics': intrinsics},
            'b': {'body_from_camera': wire(handover), 'intrinsics': [275., 252., 0., 311., 239.]},
        },
    }

    def closure(i, j, key, version, retract=False):
        row = dict(id=key, i=i, j=j, kind='loop', version=version, action='retract' if retract else 'put')
        if not retract:
            value = truth[i].between(truth[j])
            noise = np.r_[rng.normal(0., .004, 3), rng.normal(0., .012, 3)]
            row.update(measurement=wire(value.retract(noise)), sigmas=[.027, .027, .027, .035, .035, .04])
        return row

    packets, probes = [], {}
    def push(operation, label=None, **values):
        identity = len(packets) + 1
        packets.append(dict(request_id=identity, operation=operation, **values))
        if label:
            probes[identity] = label
        return identity

    restart_id = None
    earlier_pixel = None
    for index, physical in enumerate(truth):
        if index == 0:
            push('frame', frame=index)
        else:
            local = truth[index - 1].between(physical)
            systematic = np.array([.003, -.008, sign*.008, .044, sign*.017, -.01])
            odometry = local.retract(systematic + np.r_[rng.normal(0., .002, 3), rng.normal(0., .007, 3)])
            push('frame', frame=index, odometry=wire(odometry))
        if index < 7 or (index % 3 == 0 and (index < 12 or index > 37)):
            camera = 'a' if index < 11 else 'b'
            model = manifest['calibrations'][camera]
            view = physical.compose(transform(model['body_from_camera']))
            xform = view.rotation().matrix()
            fx, fy, skew, cx, cy = model['intrinsics']
            pixels = []
            for key, point in zip(names, world):
                x, y, z = xform.T @ (point - view.translation())
                assert z > 2.0
                pixel = np.array([fx*x/z+skew*y/z+cx, fy*y/z+cy]) + rng.normal(0., .9, 2)
                pixels.append(dict(id=f'px{index}-{key}', i=index, j=index, kind='pixel', action='put',
                                   version=1, landmark=key, camera=camera, pixel=pixel.tolist(), sigma_px=2.0))
            if index == 9:
                earlier_pixel = dict(pixels[0], version=2, sigma_px=2.4)
            push('edit', updates=pixels)
        if index == 18:
            push('estimate', 'before_first_late_loop')
            restart_id = push('edit', 'first_late_loop', updates=[closure(6, 15, 'loop-a', 1)])
        if index == 19:
            old_match = dict(id='sealed-match', i=0, j=1, kind='loop', action='retract', version=2)
            push('edit', 'retract_after_restart', updates=[old_match, closure(6, 15, 'loop-a', 2, True),
                                                          earlier_pixel])
        if index == 20:
            push('edit', 'restore_late_loop', updates=[closure(6, 15, 'loop-a', 3)])
        if index == 22:
            push('edit', 'sealed_retraction', updates=[closure(6, 15, 'loop-a', 4, True)])
        if index == 31:
            push('estimate', 'before_second_late_loop')
            push('edit', 'second_late_loop', updates=[closure(19, 28, 'loop-b', 1)])
        if index == 31 + manifest['lag_frames']:
            push('edit', 'both_endpoints_outside_live', updates=[closure(25, 30, 'loop-c', 1)])
        if index == len(truth) - 1:
            push('estimate', 'terminal')
    return manifest, packets, probes, restart_id, truth


class Batch:
    """Rebuild from raw accepted measurements without invoking the rewinding solver."""

    def __init__(self, manifest):
        self.manifest = manifest
        self.raw = [None]
        self.edits = {}
        self.newest = -1
        self.points = {name: L(i) for i, name in enumerate(sorted(manifest['landmarks']))}

    def receive(self, packet):
        if packet['operation'] == 'frame':
            self.newest += 1
            if self.newest:
                self.raw.append(packet['odometry'])
        elif packet['operation'] == 'edit':
            permanent_before = max(0, self.newest - self.manifest['rewind_frames'])
            for edit in packet['updates']:
                if edit['i'] >= permanent_before:
                    self.edits[edit['id']] = edit

    def estimate(self):
        manifest = self.manifest
        model = gt.NonlinearFactorGraph()
        guess = gt.Values()
        start = transform(manifest['initial_pose'])
        guess.insert(X(0), start)
        model.add(gt.PriorFactorPose3(X(0), start,
                  gt.noiseModel.Diagonal.Sigmas(np.array(manifest['initial_sigmas']))))
        for index, row in enumerate(self.raw[1:], 1):
            motion = transform(row)
            start = start.compose(motion)
            guess.insert(X(index), start)
            model.add(gt.BetweenFactorPose3(X(index-1), X(index), motion,
                      gt.noiseModel.Diagonal.Sigmas(np.array(manifest['odometry_sigmas']))))
        for name, row in manifest['landmarks'].items():
            point = np.asarray(row['point'])
            key = self.points[name]
            guess.insert(key, point)
            model.add(gt.PriorFactorPoint3(key, point, gt.noiseModel.Isotropic.Sigma(3, row['sigma'])))
        for entry in self.edits.values():
            if entry['action'] != 'put':
                continue
            if entry['kind'] == 'loop':
                model.add(gt.BetweenFactorPose3(X(entry['i']), X(entry['j']),
                          transform(entry['measurement']),
                          gt.noiseModel.Diagonal.Sigmas(np.array(entry['sigmas']))))
            else:
                camera = manifest['calibrations'][entry['camera']]
                model.add(gt.GenericProjectionFactorCal3_S2(
                    np.array(entry['pixel']), gt.noiseModel.Isotropic.Sigma(2, entry['sigma_px']),
                    X(entry['i']), self.points[entry['landmark']], gt.Cal3_S2(*camera['intrinsics']),
                    transform(camera['body_from_camera']),
                ))
        parameters = gt.LevenbergMarquardtParams()
        parameters.setMaxIterations(80)
        parameters.setRelativeErrorTol(1e-12)
        solved = gt.LevenbergMarquardtOptimizer(model, guess, parameters).optimize()
        ordering = gt.Ordering()
        for index in range(self.newest + 1):
            ordering.push_back(X(index))
        for key in self.points.values():
            ordering.push_back(key)
        jacobian, _ = model.linearize(solved).jacobian(ordering)
        # Full-history QR, separate from the streaming engine's native marginal extraction.
        r = np.linalg.qr(jacobian, mode='r')
        requested = np.r_[np.arange(6*(self.newest-self.manifest['lag_frames']),
                                   6*(self.newest-self.manifest['lag_frames'])+6),
                          np.arange(6*self.newest, 6*self.newest+6)]
        selectors = np.eye(r.shape[1])[:, requested]
        intermediate = np.linalg.solve(r.T, selectors)
        covariance = intermediate.T @ intermediate
        return solved.atPose3(X(self.newest)), covariance


def compare(answer, gold, covariance, physical):
    predicted = transform(answer['pose'])
    distribution = np.asarray(answer['joint_covariance'])
    return {
        'position_error_vs_batch_m': float(np.linalg.norm(predicted.translation()-gold.translation())),
        'rotation_error_vs_batch_rad': float(np.linalg.norm(gt.Rot3.Logmap(gold.rotation().between(predicted.rotation())))),
        'joint_covariance_relative_error': float(np.linalg.norm(distribution-covariance)/np.linalg.norm(covariance)),
        'cross_covariance_relative_error': float(np.linalg.norm(distribution[:6,6:]-covariance[:6,6:])/
                                                 np.linalg.norm(covariance[:6,6:])),
        'physical_position_error_m': float(np.linalg.norm(physical.translation()-predicted.translation())),
        'newest': answer['frame'],
        'archive_start': answer['archive_start'],
        'dispositions': answer['updates'],
    }



MAX_CHECKPOINT = 131_072


class RewindStream:
    """Run the submitted CLI as a local stream with one private durable checkpoint."""

    command = 'reopen-tracks'

    def __init__(self, app, manifest, state):
        self.app, self.manifest, self.state = app, manifest, state
        self.user = {}
        if os.geteuid() == 0:
            account = pwd.getpwnam('candidate')
            self.user = {'user': account.pw_uid, 'group': account.pw_gid, 'extra_groups': []}
            os.chown(state.parent, account.pw_uid, account.pw_gid)
        self.process = self.selector = self.runtime = None

    def start(self):
        self.runtime = TemporaryDirectory(prefix='lagfusion-runtime-')
        home = Path(self.runtime.name)
        if self.user:
            os.chown(home, self.user['user'], self.user['group'])
        environment = {key: os.environ[key] for key in ('PATH', 'LANG', 'PYTHONPATH') if key in os.environ}
        environment.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', HOME=str(home), TMPDIR=str(home))
        try:
            self.process = subprocess.Popen([
                sys.executable, '-B', '-m', 'lagfusion', self.command, '--manifest', self.manifest,
                '--state', self.state,
            ], cwd=self.app, env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, bufsize=0, start_new_session=True, **self.user)
            self.selector = DefaultSelector()
            self.selector.register(self.process.stdout, EVENT_READ)
            self.buffer = b''
        except BaseException:
            self.close()
            raise

    def write(self, packet):
        payload = (json.dumps(packet, allow_nan=False)+'\n').encode()
        if self.process.stdin.write(payload) != len(payload):
            raise ValueError('Worker did not consume the request')

    def exchange(self, packet):
        self.write(packet)
        deadline = monotonic() + 3
        while b'\n' not in self.buffer:
            if not self.selector.select(max(0., deadline-monotonic())):
                raise ValueError('Worker did not emit a response within three seconds')
            chunk = os.read(self.process.stdout.fileno(), 8192)
            if not chunk:
                raise ValueError('Worker closed its response stream')
            self.buffer += chunk
            if len(self.buffer) > 131_072:
                raise ValueError('Response is larger than 128 KiB')
        response, self.buffer = self.buffer.split(b'\n', 1)
        value = json.loads(response)
        if value['request_id'] != packet['request_id']:
            raise ValueError('Response does not match its request')
        return value, response

    def checkpoint(self):
        entries = list(self.state.parent.iterdir())
        if entries != [self.state] or not stat.S_ISREG(self.state.lstat().st_mode):
            raise ValueError('The durable location must hold only the checkpoint file')
        if self.state.stat().st_size > MAX_CHECKPOINT:
            raise ValueError('Checkpoint exceeds 128 KiB')
        return self.state.read_bytes()

    def close(self):
        if self.selector is not None:
            self.selector.close()
            self.selector = None
        if self.process is not None:
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self.process.wait(timeout=3)
            self.process.stdin.close()
            self.process.stdout.close()
            self.process = None
        if self.runtime is not None:
            self.runtime.cleanup()
            self.runtime = None

    def crash_and_retry(self, packet, response):
        before = self.checkpoint()
        self.close()
        self.start()
        altered = dict(request_id=packet['request_id'], operation='frame', frame=0)
        self.write(altered)
        rejected = self.process.wait(timeout=3) != 0
        silence = self.process.stdout.read() == b''
        unchanged = self.checkpoint() == before
        self.close()
        self.start()
        _, replay = self.exchange(packet)
        return rejected and silence and unchanged and replay == response and self.checkpoint() == before

    def peak_ram(self):
        try:
            lines = Path(f'/proc/{self.process.pid}/status').read_text().splitlines()
        except OSError:
            return None
        return next((int(line.split()[1]) for line in lines if line.startswith('VmHWM:')), None)


def stream_at(app: Path, root: Path, manifest: dict[str, object], *,
              stream_class: type[RewindStream] = RewindStream) -> RewindStream:
    """Prepare a private manifest and state location for one candidate stream.

    Args:
        app: Staged candidate working directory.
        root: Fresh case directory to create beneath the verifier's temporary root.
        manifest: Public configuration to serialize for the worker.
        stream_class: Runner with the CLI command for this checkpoint.

    Returns:
        The configured runner before its first process is started.
    """
    root.mkdir(mode=0o711)
    durable = root / 'durable'
    durable.mkdir(mode=0o700)
    manifest_path = root / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest))
    manifest_path.chmod(0o444)
    return stream_class(app, manifest_path, durable / 'stream.state')


def coverage(answer: dict, manifest: dict) -> bool:
    """Check window bounds and the covariance for the named endpoint states."""
    n = answer['frame']
    oldest = max(0, n-manifest['lag_frames'])
    earliest = max(0, n-manifest['rewind_frames'])
    singleton = oldest == n
    accepted_ids = ([n], [n, n]) if singleton else ([oldest, n],)
    covariance = np.asarray(answer['joint_covariance'])
    dimensions = 6 if singleton else 12
    return (answer['active_frames'] == list(range(oldest, n+1))
            and answer['archive_start'] == earliest
            and answer['archived_frames'] == n-earliest+1
            and answer['joint_frame_ids'] in accepted_ids
            and covariance.shape == (dimensions, dimensions)
            and np.all(np.isfinite(covariance))
            and np.max(np.abs(covariance-covariance.T)) < 1e-8
            and np.linalg.eigvalsh(covariance)[0] > 0.)


def support_snapshot(answer: dict, expected_frame: int) -> dict:
    """Record the first rejected support envelope without copying its matrix."""
    active = answer['active_frames']
    endpoints = answer['joint_frame_ids']
    return {
        'expected_frame': expected_frame, 'frame': answer['frame'],
        'active_frames': active[:66] if isinstance(active, list) else type(active).__name__,
        'archive_start': answer['archive_start'], 'archived_frames': answer['archived_frames'],
        'joint_frame_ids': endpoints[:3] if isinstance(endpoints, list) else type(endpoints).__name__,
        'covariance_shape': list(np.asarray(answer['joint_covariance']).shape),
    }


def short_case(app, root, seed):
    manifest, packets, probes, restart, truth = fixture(seed)
    receiver = stream_at(app, root, manifest)
    batch = Batch(manifest)
    results, statuses = {}, {}
    sizes, peaks = [], []
    recent = None
    restart_ok, support_ok = False, True
    first_support_failure = None
    try:
        receiver.start()
        for packet in packets:
            index = packet['request_id']
            candidate, response = receiver.exchange(packet)
            if index == restart:
                restart_ok = receiver.crash_and_retry(packet, response)
                peak = receiver.peak_ram()
                if peak is not None:
                    peaks.append(peak)
            batch.receive(packet)
            expected = {}
            if packet['operation'] == 'edit':
                cut = max(0, batch.newest-manifest['rewind_frames'])
                expected = {update['id']: 'sealed' if update['i'] < cut else 'applied'
                            for update in packet['updates']}
            statuses[index] = candidate['updates'] == expected
            current_support = coverage(candidate, manifest) and candidate['frame'] == batch.newest
            if not current_support and first_support_failure is None:
                first_support_failure = support_snapshot(candidate, batch.newest)
            support_ok &= current_support
            sizes.append(len(receiver.checkpoint()))
            if index in probes:
                pose, covariance = batch.estimate()
                label = probes[index]
                results[label] = compare(candidate, pose, covariance, truth[batch.newest])
                if label == 'sealed_retraction':
                    # The immediately preceding response names the same newest frame.
                    before = np.asarray(recent['joint_covariance'])
                    after = np.asarray(candidate['joint_covariance'])
                    results[label]['sealed_covariance_change'] = float(np.linalg.norm(before-after))
                    results[label]['sealed_position_change_m'] = float(np.linalg.norm(
                        transform(recent['pose']).translation() - transform(candidate['pose']).translation()
                    ))
            recent = candidate
        peak = receiver.peak_ram()
        if peak is not None:
            peaks.append(peak)
    finally:
        receiver.close()
    accuracy = all(x['position_error_vs_batch_m'] <= .04 and x['rotation_error_vs_batch_rad'] <= .018
                   for x in results.values())
    uncertainty = all(x['joint_covariance_relative_error'] <= .12
                      and x['cross_covariance_relative_error'] <= .18 for x in results.values())
    safety = min(results['before_first_late_loop']['physical_position_error_m'] -
                 results['first_late_loop']['physical_position_error_m'],
                 results['before_second_late_loop']['physical_position_error_m'] -
                 results['second_late_loop']['physical_position_error_m'])
    sealed = results['sealed_retraction']
    return {
        'causal_late_closure_and_batch_accuracy': accuracy and safety >= .20,
        'correlated_joint_and_cross_covariance': uncertainty,
        'cold_exact_replay_and_factor_revision': restart_ok and all(statuses.values()),
        'hard_expiry_preserves_boundary': (support_ok and sealed['sealed_covariance_change'] <= 3e-5
                                           and sealed['sealed_position_change_m'] <= .001
                                           and sealed['dispositions'] == {'loop-a': 'sealed'}),
    }, {
        'max_checkpoint_bytes': max(sizes), 'max_process_peak_kib': max(peaks, default=None),
        'max_archive_frames': manifest['rewind_frames']+1, 'restart_after_request': restart,
        'minimum_late_recovery_m': safety, 'phases': results,
        'first_support_failure': first_support_failure,
    }


def long_packets(seed):
    manifest, packets, _, _, truth = fixture(seed)
    rng = np.random.default_rng(seed+5321)
    pose = truth[-1]
    optical = manifest['calibrations']['b']
    extrinsic = transform(optical['body_from_camera'])
    fx, fy, skew, cx, cy = optical['intrinsics']
    points = [np.array(point) for point in WORLD_POINTS]
    # Persist a continuing calibrated survey with independent subpixel noise.
    for index in range(48, 720):
        angle = (index-47)*.12
        delta = gt.Pose3(gt.Rot3.Ypr(.015*math.sin(angle), .013*math.sin(2*angle), .009*math.cos(angle)),
                         np.array([.026*math.sin(angle), .032*math.cos(angle), .008*math.sin(2*angle)]))
        pose = pose.compose(delta)
        truth.append(pose)
        twist = rng.normal(0., [.002, .002, .002, .007, .007, .007])
        packets.append(dict(request_id=len(packets)+1, operation='frame', frame=index,
                            odometry=wire(delta.retract(twist))))
        view = pose.compose(extrinsic)
        updates = []
        for (name, _), point in zip(manifest['landmarks'].items(), points):
            x, y, z = view.rotation().matrix().T @ (point-view.translation())
            if z <= 1.:
                raise ArithmeticError('Authored long-run landmark left the modeled field')
            pixel = np.array([fx*x/z+skew*y/z+cx, fy*y/z+cy])+rng.normal(0., .32, 2)
            updates.append(dict(id=f'survey:{index}:{name}', kind='pixel', i=index, j=index, action='put',
                                version=1, landmark=name, camera='b', pixel=pixel.tolist(), sigma_px=1.2))
        packets.append(dict(request_id=len(packets)+1, operation='edit', updates=updates))
    return manifest, packets, truth


def long_case(app, root):
    manifest, packets, truth = long_packets(211)
    receiver = stream_at(app, root, manifest)
    maximum = tail_maximum = 0
    peaks, tracking = [], []
    restart_ok, support_ok, receipts_ok = False, True, True
    first_support_failure = None
    n = -1
    try:
        receiver.start()
        for packet in packets:
            reply, line = receiver.exchange(packet)
            if packet['operation'] == 'frame':
                n += 1
            size = len(receiver.checkpoint())
            maximum = max(maximum, size)
            current_support = coverage(reply, manifest) and reply['frame'] == n
            if not current_support and first_support_failure is None:
                first_support_failure = support_snapshot(reply, n)
            support_ok &= current_support
            if packet['operation'] == 'edit':
                expected = {item['id']: 'sealed' if item['i'] < max(0, n-manifest['rewind_frames']) else 'applied'
                            for item in packet['updates']}
                receipts_ok &= reply['updates'] == expected
            if n >= 300:
                tail_maximum = max(tail_maximum, size)
            if n >= 300 and packet['operation'] == 'edit' and n % 41 == 0:
                tracking.append(float(np.linalg.norm(transform(reply['pose']).translation()-truth[n].translation())))
                peak = receiver.peak_ram()
                if peak is not None:
                    peaks.append(peak)
            if n == 567 and packet['operation'] == 'edit':
                restart_ok = receiver.crash_and_retry(packet, line)
        peak = receiver.peak_ram()
        if peak is not None:
            peaks.append(peak)
    finally:
        receiver.close()
    return {
        'bounded_checkpoint_and_active_support': support_ok and 0 < tail_maximum <= MAX_CHECKPOINT,
        'long_run_cold_recovery_and_tracking': restart_ok and receipts_ok and len(tracking) >= 8
                                               and max(tracking) <= .30,
    }, {
        'stream_frames': n+1, 'stream_requests': len(packets), 'max_checkpoint_bytes': maximum,
        'max_checkpoint_bytes_after_frame_300': tail_maximum, 'max_process_peak_kib': max(peaks, default=None),
        'post_compaction_sample_errors_m': tracking, 'restart_frame': 567,
        'first_support_failure': first_support_failure,
    }


def rewind_cases(app, root):
    cases, measurements = {}, {}
    runners = {
        'retired_loop_clockwise': lambda path: short_case(app, path, 211),
        'retired_loop_counterclockwise': lambda path: short_case(app, path, 962),
        'long_run_bounded_storage': lambda path: long_case(app, path),
    }
    keys = ('causal_late_closure_and_batch_accuracy', 'correlated_joint_and_cross_covariance',
            'cold_exact_replay_and_factor_revision', 'hard_expiry_preserves_boundary')
    for name, run in runners.items():
        start = monotonic()
        try:
            cases[name], measurements[name] = run(root / name)
        except (KeyError, IndexError, TypeError, ValueError, OSError, subprocess.TimeoutExpired,
                np.linalg.LinAlgError, RuntimeError) as exc:
            expected = ('bounded_checkpoint_and_active_support', 'long_run_cold_recovery_and_tracking')
            cases[name] = dict.fromkeys(expected if name == 'long_run_bounded_storage' else keys, False)
            measurements[name] = {'error': str(exc)}
        measurements[name]['elapsed_s'] = monotonic()-start
    return cases, measurements
