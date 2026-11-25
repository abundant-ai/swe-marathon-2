"""Observe remount recovery with independent full-history camera factors."""

from dataclasses import dataclass
from pathlib import Path
from subprocess import TimeoutExpired
from time import monotonic
from typing import Any, Callable

import gtsam as gt
from gtsam.symbol_shorthand import L, X
import numpy as np

from rewind_probes import MAX_CHECKPOINT, RewindStream, coverage, stream_at, transform, wire


Record = dict[str, Any]
POINTS = {
    'port': (-1.5, -.9, 3.7), 'starboard': (1.4, -.6, 4.2),
    'top': (-.35, 1.4, 4.8), 'tower': (.8, .5, 6.1),
}
SHORT_CHECKS = ('optical_mount_recovery', 'coupled_batch_accuracy', 'coupled_covariance',
                'sealed_survey_and_cold_restart')
LONG_CHECKS = ('bounded_mount_support', 'long_mount_replay_and_tracking')


class MountStream(RewindStream):
    """Send live camera-mount packets through the isolated rewind transport."""

    command = 'recalibrate-tracks'


def diagonals(values: list[float]) -> gt.noiseModel.Diagonal:
    """Convert right-local standard deviations into a GTSAM Gaussian weight."""
    return gt.noiseModel.Diagonal.Sigmas(np.asarray(values))


def pixel_factor(row: Record, extrinsic_key: int, point_key: int, optic: gt.Cal3_S2) -> gt.CustomFactor:
    """Build a three-variable pinhole factor for the independent batch graph.

    `row` supplies the captured frame, pixel and isotropic pixel scale. The
    other keys refer to a persistent body-to-camera Pose3 and a map point.
    The callback chains the native camera and composition Jacobians in
    each variable's own tangent chart.
    """
    frame_key = X(row['i'])
    observed = np.asarray(row['pixel'])

    def error(_: gt.CustomFactor, values: gt.Values, jacobians: Any) -> np.ndarray:
        """Return pixel residuals and optional Jacobians for the current batch estimate."""
        body = values.atPose3(frame_key)
        extrinsic = values.atPose3(extrinsic_key)
        landmark = values.atPoint3(point_key)
        if jacobians is None:
            return gt.PinholeCameraCal3_S2(body.compose(extrinsic), optic).project(landmark) - observed
        body_jac = np.empty((6, 6), order='F')
        mount_jac = np.empty((6, 6), order='F')
        view = body.compose(extrinsic, body_jac, mount_jac)
        view_jac = np.empty((2, 6), order='F')
        point_jac = np.empty((2, 3), order='F')
        prediction = gt.PinholeCameraCal3_S2(view, optic).project(landmark, view_jac, point_jac)
        jacobians[0], jacobians[1], jacobians[2] = view_jac @ body_jac, view_jac @ mount_jac, point_jac
        return prediction - observed

    return gt.CustomFactor(gt.noiseModel.Isotropic.Sigma(2, row['sigma_px']),
                           [frame_key, extrinsic_key, point_key], error)


def survey_factor(row: Record, extrinsic_key: int) -> gt.CustomFactor:
    """Build an optical world-pose survey of the body and mount at capture."""
    frame_key = X(row['i'])
    measured = transform(row['measurement'])

    def error(_: gt.CustomFactor, values: gt.Values, jacobians: Any) -> np.ndarray:
        """Evaluate the prior residual of the composed camera pose in the map frame."""
        body = values.atPose3(frame_key)
        extrinsic = values.atPose3(extrinsic_key)
        if jacobians is None:
            return measured.localCoordinates(body.compose(extrinsic))
        body_jac = np.empty((6, 6), order='F')
        mount_jac = np.empty((6, 6), order='F')
        view = body.compose(extrinsic, body_jac, mount_jac)
        view_jac = np.empty((6, 6), order='F')
        residual = measured.localCoordinates(view, None, view_jac)
        jacobians[0], jacobians[1] = view_jac @ body_jac, view_jac @ mount_jac
        return residual

    return gt.CustomFactor(diagonals(row['sigmas']), [frame_key, extrinsic_key], error)


class BatchEstimator:
    """Fit the accepted raw graph from scratch at each selected response."""

    def __init__(self, manifest: Record) -> None:
        """Record authored priors and independent batch keys without candidate state."""
        self.manifest = manifest
        self.motion: list[Record] = []
        self.edits: dict[str, Record] = {}
        self.newest = -1
        self.points = {name: L(i) for i, name in enumerate(manifest['landmarks'])}
        self.mounts = {name: gt.symbol('c', i) for i, name in enumerate(manifest['uncertain_cameras'])}

    def receive(self, packet: Record) -> dict[str, str]:
        """Apply a known-valid fixture packet and return the expected dispositions.

        Sealed acquisitions retain their last accepted measurement in this
        full-history model. Subsequent edits to those acquisitions are ignored.
        """
        operation = packet['operation']
        if operation == 'frame':
            self.newest += 1
            if self.newest:
                self.motion.append(packet['odometry'])
        outcomes = {}
        if operation == 'edit':
            cut = max(0, self.newest - self.manifest['rewind_frames'])
            for row in packet['updates']:
                name = row['id']
                outcomes[name] = 'sealed' if row['i'] < cut else 'applied'
                if row['i'] >= cut:
                    self.edits[name] = row
        return outcomes

    def setup(self) -> tuple[gt.NonlinearFactorGraph, gt.Values]:
        """Create the raw measurement graph and an odometry initialization."""
        graph = gt.NonlinearFactorGraph()
        trial = gt.Values()
        position = transform(self.manifest['initial_pose'])
        trial.insert(X(0), position)
        graph.add(gt.PriorFactorPose3(X(0), position, diagonals(self.manifest['initial_sigmas'])))
        weight = diagonals(self.manifest['odometry_sigmas'])
        for index, row in enumerate(self.motion, 1):
            delta = transform(row)
            position = position.compose(delta)
            trial.insert(X(index), position)
            graph.add(gt.BetweenFactorPose3(X(index - 1), X(index), delta, weight))
        for name, row in self.manifest['landmarks'].items():
            key, point = self.points[name], np.asarray(row['point'])
            trial.insert(key, point)
            graph.add(gt.PriorFactorPoint3(key, point, gt.noiseModel.Isotropic.Sigma(3, row['sigma'])))
        for name, prior in self.manifest['uncertain_cameras'].items():
            key = self.mounts[name]
            mean = transform(self.manifest['calibrations'][name]['body_from_camera'])
            trial.insert(key, mean)
            graph.add(gt.PriorFactorPose3(key, mean, diagonals(prior)))
        for row in self.edits.values():
            if row['action'] == 'put':
                graph.add(self.observation(row))
        return graph, trial

    def observation(self, row: Record) -> Any:
        """Create the native optical, survey, or relative-pose residual for a retained raw row."""
        kind = row['kind']
        if kind == 'loop':
            return gt.BetweenFactorPose3(X(row['i']), X(row['j']), transform(row['measurement']),
                                        diagonals(row['sigmas']))
        mount = self.mounts.get(row['camera'])
        if kind == 'mount_survey':
            return survey_factor(row, mount)
        camera = self.manifest['calibrations'][row['camera']]
        optic, landmark = gt.Cal3_S2(*camera['intrinsics']), self.points[row['landmark']]
        if mount is not None:
            return pixel_factor(row, mount, landmark, optic)
        return gt.GenericProjectionFactorCal3_S2(
            np.asarray(row['pixel']), gt.noiseModel.Isotropic.Sigma(2, row['sigma_px']), X(row['i']),
            landmark, optic, transform(camera['body_from_camera']),
        )

    def estimate(self, camera: str) -> tuple[gt.Pose3, gt.Pose3, np.ndarray]:
        """Return latest pose, queried mount and ordered covariance from raw factors.

        Use an all-history nonlinear fit and dense QR with explicit selectors
        for the serving endpoints followed by the requested persistent mount.
        Neither the candidate graph nor a candidate-estimated pose is used.
        """
        graph, trial = self.setup()
        params = gt.LevenbergMarquardtParams()
        params.setMaxIterations(80)
        params.setRelativeErrorTol(1e-12)
        fit = gt.LevenbergMarquardtOptimizer(graph, trial, params).optimize()
        frames = [X(index) for index in range(self.newest + 1)]
        first = max(0, self.newest - self.manifest['lag_frames'])
        endpoints = frames[-1:] if first == self.newest else [frames[first], frames[-1]]
        requested = [*endpoints, self.mounts[camera]]
        rest = [key for key in [*frames, *self.mounts.values(), *self.points.values()] if key not in requested]
        order = gt.Ordering()
        for key in [*requested, *rest]:
            order.push_back(key)
        jacobian, _ = graph.linearize(fit).jacobian(order)
        upper = np.linalg.qr(jacobian, mode='r')
        inverse_columns = np.linalg.solve(upper.T, np.eye(len(upper))[:, :6 * len(requested)])
        return fit.atPose3(X(self.newest)), fit.atPose3(self.mounts[camera]), inverse_columns.T @ inverse_columns


@dataclass(frozen=True)
class Mission:
    """A private sequence with author-known poses and selected batch comparisons."""

    manifest: Record
    packets: list[Record]
    probes: dict[int, str]
    trajectory: list[gt.Pose3]
    mounts: dict[str, gt.Pose3]
    restart: int
    invalid_before: int


def field_motion(index: int, sign: int) -> gt.Pose3:
    """Generate repeatable six-axis field motion with bounded observation geometry."""
    phase = .24 * index
    return gt.Pose3(gt.Rot3.Ypr(sign * (.19*np.sin(phase) + .13*np.sin(.65*phase)),
                               .16*np.sin(.83*phase), .12*np.sin(1.07*phase)),
                    np.array([.78*np.sin(phase), sign*.55*(1.-np.cos(.78*phase)),
                              .20*np.sin(.73*phase)]))


def fixture(seed: int, *, handover: bool, count: int = 32) -> Mission:
    """Author a mount-recovery stream with retired survey changes and optional remount.

    Uncertain camera priors are perturbed before observations are created.
    Asynchronous tracker surveys can refer to a capture older than the serving
    window, while projected landmarks share imperfect map priors and odometry.
    """
    rng = np.random.default_rng(seed)
    direction = -1 if handover else 1
    first, second = 'front-2025', 'front-2026'
    true_mounts = {
        first: gt.Pose3(gt.Rot3.Ypr(.063, -.063, .088), np.array([.26, -.13, .10])),
    }
    if handover:
        true_mounts[second] = gt.Pose3(gt.Rot3.Ypr(-.102, .075, -.115), np.array([.13, .12, .07]))
    guide = gt.Pose3(gt.Rot3.Ypr(-.01, .06, -.04), np.array([-.16, .04, .05]))
    actual = {'guide': guide, **true_mounts}
    mount_error = np.array([.102, -.083, .081, -.128, .102, .094])
    optics = {}
    for index, (camera, true_pose) in enumerate(actual.items()):
        prior = true_pose if camera == 'guide' else true_pose.retract(mount_error * (-1)**index * direction)
        optics[camera] = {'body_from_camera': wire(prior),
                          'intrinsics': [253.+4*index, 264.-7*index, 1.25, 314., 240.]}
    trajectory = [field_motion(index, direction) for index in range(count)]
    manifest = {
        'lag_frames': 5 if handover else 4, 'rewind_frames': 12 if handover else 11,
        'initial_pose': wire(trajectory[0]), 'initial_sigmas': [.016] * 3 + [.025] * 3,
        'odometry_sigmas': [.022, .020, .027, .035, .035, .04],
        'landmarks': {name: {'point': (np.array(point) + rng.normal(0., .065, 3)).tolist(), 'sigma': .22}
                      for name, point in POINTS.items()},
        'calibrations': optics,
        'uncertain_cameras': {name: [.135, .145, .16, .22, .23, .24] for name in true_mounts},
    }
    packets: list[Record] = []
    probes: dict[int, str] = {}

    def send(operation: str, label: str | None = None, **fields: Any) -> int:
        """Append a consecutive request and register an optional named comparison."""
        index = len(packets) + 1
        packets.append(dict(request_id=index, operation=operation, **fields))
        if label is not None:
            probes[index] = label
        return index

    def survey(index: int, camera: str, name: str, version: int, *, action: str = 'put') -> Record:
        """Generate an independently surveyed world-from-camera observation at capture."""
        row = dict(id=name, version=version, action=action, kind='mount_survey', i=index, j=index)
        if action == 'put':
            perturbation = np.array([.014, -.016, .012, .035, -.023, .03]) if version == 1 else np.zeros(6)
            observed = trajectory[index].compose(actual[camera]).retract(perturbation * direction)
            row.update(camera=camera, measurement=wire(observed), sigmas=[.012] * 3 + [.023] * 3)
        return row

    restart = invalid_before = 0
    previous_pixel = None
    for index, physical in enumerate(trajectory):
        if index:
            delta = trajectory[index - 1].between(physical)
            error = rng.normal(0., [.0015] * 3 + [.0035] * 3)
            error += [.0012, -.0013, .002*direction, .004, .004*direction, -.003]
            send('frame', frame=index, odometry=wire(delta.retract(error)))
        else:
            send('frame', frame=index)
            send('estimate', 'initial-optical-prior')
        active = second if handover and index >= 11 else first
        camera = 'guide' if index % 3 == 0 else active
        if handover and index == 11:
            send('estimate', 'new-epoch-prior', query_mount=second)
        if index < 24 or index % 2 == 0:
            model = optics[camera]
            view = physical.compose(actual[camera])
            calibration = gt.Cal3_S2(*model['intrinsics'])
            projector = gt.PinholeCameraCal3_S2(view, calibration)
            rows = [dict(id=f'plate/{index}/{name}', version=1, i=index, j=index, action='put', kind='pixel',
                         camera=camera, landmark=name, sigma_px=1.35,
                         pixel=(projector.project(np.asarray(point)) + rng.normal(0., .36, 2)).tolist())
                    for name, point in POINTS.items()]
            if index == 8:
                previous_pixel = {**rows[0], 'version': 2, 'sigma_px': 1.55}
            send('edit', updates=rows, query_mount=active)
        if index == 9:
            send('estimate', 'old-epoch-optical')
        if index == 12:
            restart = send('edit', 'late-survey', updates=[survey(4, first, 'wash/first', 1)])
        if index == 13:
            send('edit', 'retract-survey', updates=[survey(4, first, 'wash/first', 2, action='retract')])
        if index == 14:
            invalid_before = send('edit', 'correct-survey', updates=[survey(4, first, 'wash/first', 3), previous_pixel])
        if index == 17:
            send('estimate', 'before-sealed')
            send('edit', 'sealed-first-survey', updates=[survey(4, first, 'wash/first', 4, action='retract')])
        if handover and index == 18:
            send('estimate', 'new-epoch-optical', query_mount=second)
            send('edit', 'replacement-survey', updates=[survey(11, second, 'wash/replacement', 1)], query_mount=second)
        if handover and index == 25:
            send('estimate', 'before-sealed-replacement', query_mount=second)
            send('edit', 'sealed-replacement', updates=[survey(11, second, 'wash/replacement', 2, action='retract')],
                 query_mount=second)
        if index == count - 1:
            send('estimate', 'terminal')
            if handover:
                send('estimate', 'terminal-replacement', query_mount=second)
    return Mission(manifest, packets, probes, trajectory, true_mounts, restart, invalid_before)


def angular_error(first: gt.Pose3, second: gt.Pose3) -> float:
    """Return the shortest rotation distance in radians between two native poses."""
    return float(np.linalg.norm(gt.Rot3.Logmap(first.rotation().between(second.rotation()))))


def translation_error(first: gt.Pose3, second: gt.Pose3) -> float:
    """Return Euclidean separation in metres between the two pose origins."""
    return float(np.linalg.norm(first.translation() - second.translation()))


def query(packet: Record, manifest: Record) -> str:
    """Select the explicit request mount or the documented lexical default."""
    return packet.get('query_mount', min(manifest['uncertain_cameras']))


def support(answer: Record, manifest: Record, camera: str, newest: int) -> bool:
    """Check exact frame support, known mount IDs and both covariance layouts."""
    if answer['frame'] != newest or answer['joint_mount_camera'] != camera or not coverage(answer, manifest):
        return False
    poses = answer['mount_poses']
    if set(poses) != set(manifest['uncertain_cameras']):
        return False
    if any(not np.all(np.isfinite(transform(value).matrix())) for value in poses.values()):
        return False
    live = np.asarray(answer['joint_covariance'])
    joint = np.asarray(answer['joint_mount_covariance'])
    size = live.shape[0] + 6
    return (joint.shape == (size, size) and np.all(np.isfinite(joint))
            and np.max(np.abs(joint - joint.T)) < 1e-8 and np.linalg.eigvalsh(joint)[0] > 0.
            and np.allclose(joint[:-6, :-6], live, rtol=5e-6, atol=1e-7))


def compare(answer: Record, batch: BatchEstimator, physical: gt.Pose3, camera: str) -> Record:
    """Compare the candidate to raw batch estimation and record physical mount error.

    The camera cross error normalizes by the measured off-diagonal block,
    with an absolute floor to handle a camera that has yet to observe any
    landmark. Track legacy covariance disagreement separately for diagnosis.
    """
    latest, mount, expected = batch.estimate(camera)
    estimate = transform(answer['pose'])
    extrinsic = transform(answer['mount_poses'][camera])
    covariance = np.asarray(answer['joint_mount_covariance'])
    cross = expected[:-6, -6:]
    legacy = np.asarray(answer['joint_covariance'])
    return {
        'position_error_m': translation_error(estimate, latest), 'rotation_error_rad': angular_error(estimate, latest),
        'mount_error_m': translation_error(extrinsic, mount), 'mount_rotation_error_rad': angular_error(extrinsic, mount),
        'physical_mount_error_m': translation_error(extrinsic, physical),
        'physical_mount_rotation_error_rad': angular_error(extrinsic, physical),
        'joint_mount_relative_error': float(np.linalg.norm(covariance - expected) / np.linalg.norm(expected)),
        'cross_norm': float(np.linalg.norm(cross)),
        'cross_relative_error': float(np.linalg.norm(covariance[:-6, -6:] - cross) / max(np.linalg.norm(cross), 2e-5)),
        'legacy_block_difference': float(np.linalg.norm(covariance[:-6, :-6] - legacy)),
        'newest': answer['frame'], 'archive_start': answer['archive_start'], 'query_mount': camera,
        'dispositions': answer['updates'],
    }


def preserved(prior: Record, sealed: Record) -> Record:
    """Measure the effect of an attempted edit to an already sealed survey."""
    before, after = np.asarray(prior['joint_mount_covariance']), np.asarray(sealed['joint_mount_covariance'])
    latest_before, latest_after = transform(prior['pose']), transform(sealed['pose'])
    return {
        'latest_position_m': translation_error(latest_before, latest_after),
        'latest_rotation_rad': angular_error(latest_before, latest_after),
        'max_mount_position_m': max(translation_error(transform(prior['mount_poses'][camera]), transform(value))
                                    for camera, value in sealed['mount_poses'].items()),
        'max_mount_rotation_rad': max(angular_error(transform(prior['mount_poses'][camera]), transform(value))
                                      for camera, value in sealed['mount_poses'].items()),
        'joint_mount_change': float(np.linalg.norm(before - after)),
    }


def invalid_retry(stream: MountStream, valid: Record) -> bool:
    """Reject a mixed valid-and-invalid edit without changing committed camera state.

    Test a later edit whose first row is legal but whose second version skips
    a revision. Restart with the same file before the actual valid request.
    """
    saved = stream.checkpoint()
    proper, stale = valid['updates']
    malformed = {**valid, 'updates': [proper, {**stale, 'version': stale['version'] + 2}]}
    stream.write(malformed)
    nonzero = stream.process.wait(timeout=3) != 0
    silence = stream.process.stdout.read() == b''
    unchanged = stream.checkpoint() == saved
    stream.close()
    stream.start()
    return nonzero and silence and unchanged


def short_case(app: Path, root: Path, seed: int, *, handover: bool) -> tuple[dict[str, bool], Record]:
    """Execute a delayed survey mission and compare its streaming posterior and receipts.

    Use the candidate only through its command and durable checkpoint. The
    independent raw batch receives the same causally accepted packets and is
    queried only at selected responses. Each fitted camera is queried before
    and after optical evidence, independently of a tracker survey.
    """
    mission = fixture(seed, handover=handover)
    batch = BatchEstimator(mission.manifest)
    stream = stream_at(app, root, mission.manifest, stream_class=MountStream)
    phases: dict[str, Record] = {}
    sealed_attempts: dict[str, Record] = {}
    receipts, valid, cold, atomic = True, True, False, False
    maximum = 0
    previous = None
    first_support_failure = None
    try:
        stream.start()
        for packet in mission.packets:
            index = packet['request_id']
            if index == mission.invalid_before:
                atomic = invalid_retry(stream, packet)
            expected = batch.receive(packet)
            camera = query(packet, mission.manifest)
            answer, line = stream.exchange(packet)
            receipts &= answer['updates'] == expected
            current = support(answer, mission.manifest, camera, batch.newest)
            if not current and first_support_failure is None:
                first_support_failure = {'request_id': index, 'expected_frame': batch.newest,
                                         'expected_query_mount': camera, 'observed_frame': answer['frame']}
            valid &= current
            maximum = max(maximum, len(stream.checkpoint()))
            if index == mission.restart:
                cold = stream.crash_and_retry(packet, line)
            if index in mission.probes and current:
                label = mission.probes[index]
                phases[label] = compare(answer, batch, mission.mounts[camera], camera)
                if label.startswith('sealed-'):
                    sealed_attempts[label] = preserved(previous, answer)
            previous = answer
    finally:
        stream.close()
    optical_windows = [('initial-optical-prior', 'old-epoch-optical')]
    if handover:
        optical_windows.append(('new-epoch-prior', 'new-epoch-optical'))
    improvements = [phases[before]['physical_mount_error_m'] - phases[after]['physical_mount_error_m']
                    for before, after in optical_windows if before in phases and after in phases]
    complete = valid and len(phases) == len(mission.probes)
    accuracy = complete and all(phase['position_error_m'] <= .04 and phase['rotation_error_rad'] <= .018
                                and phase['mount_error_m'] <= .025 and phase['mount_rotation_error_rad'] <= .022
                                for phase in phases.values())
    uncertainty = complete and all(phase['joint_mount_relative_error'] <= .14 and phase['cross_relative_error'] <= .20
                                   for phase in phases.values())
    stable = len(sealed_attempts) == (2 if handover else 1) and all(
        row['latest_position_m'] <= .001 and row['latest_rotation_rad'] <= .001
        and row['max_mount_position_m'] <= .001 and row['max_mount_rotation_rad'] <= .001
        and row['joint_mount_change'] <= 3e-5 for row in sealed_attempts.values()
    )
    optical_accuracy = all(after in phases and phases[after]['mount_error_m'] <= .025
                           and phases[after]['mount_rotation_error_rad'] <= .022 for _, after in optical_windows)
    return {
        'optical_mount_recovery': optical_accuracy,
        'coupled_batch_accuracy': accuracy,
        'coupled_covariance': uncertainty,
        'sealed_survey_and_cold_restart': complete and stable and cold and atomic and receipts,
    }, {
        'phases': phases, 'sealed_attempts': sealed_attempts, 'max_checkpoint_bytes': maximum,
        'first_support_failure': first_support_failure, 'optical_improvement_m': improvements,
        'cold_replay_ok': cold, 'atomic_invalid_revision_ok': atomic, 'edits_and_receipts_ok': receipts,
    }


def long_case(app: Path, root: Path) -> tuple[dict[str, bool], Record]:
    """Follow a remounted camera through bounded compaction and a late cold restart.

    Test all streaming envelopes for 640 frames. Later physical pose samples
    use authored motion rather than a large dense batch, while queried and
    inactive camera errors are retained as diagnostics.
    """
    mission = fixture(615, handover=True, count=640)
    stream = stream_at(app, root, mission.manifest, stream_class=MountStream)
    newest, maximum, tail = -1, 0, 0
    valid, receipts, cold = True, True, False
    tracking: list[Record] = []
    first_support_failure = None
    peak = None
    try:
        stream.start()
        for packet in mission.packets:
            if packet['operation'] == 'frame':
                newest += 1
            camera = query(packet, mission.manifest)
            answer, line = stream.exchange(packet)
            current = support(answer, mission.manifest, camera, newest)
            if not current and first_support_failure is None:
                first_support_failure = {'request_id': packet['request_id'], 'expected_frame': newest,
                                         'expected_query_mount': camera, 'observed_frame': answer['frame']}
            valid &= current
            cut = max(0, newest - mission.manifest['rewind_frames'])
            expected = {row['id']: 'sealed' if row['i'] < cut else 'applied' for row in packet.get('updates', ())}
            receipts &= answer['updates'] == expected
            size = len(stream.checkpoint())
            maximum = max(maximum, size)
            if newest >= 300:
                tail = max(tail, size)
                if packet['operation'] == 'frame' and newest % 37 == 0 and current:
                    tracking.append({
                        'frame': newest,
                        'position_error_m': translation_error(transform(answer['pose']), mission.trajectory[newest]),
                        'mount_errors_m': {key: translation_error(transform(value), mission.mounts[key])
                                           for key, value in answer['mount_poses'].items()},
                    })
            if newest == 482 and packet['operation'] == 'edit':
                cold = stream.crash_and_retry(packet, line)
        peak = stream.peak_ram()
    finally:
        stream.close()
    return {
        'bounded_mount_support': valid and 0 < tail <= MAX_CHECKPOINT,
        'long_mount_replay_and_tracking': cold and receipts and len(tracking) >= 8
                                          and max(row['position_error_m'] for row in tracking) <= .30,
    }, {
        'stream_frames': newest + 1, 'stream_requests': len(mission.packets), 'max_checkpoint_bytes': maximum,
        'max_checkpoint_bytes_after_frame_300': tail, 'max_process_peak_kib': peak, 'post_compaction_samples': tracking,
        'first_support_failure': first_support_failure, 'restart_frame': 482, 'cold_replay_ok': cold,
    }


def mount_cases(app: Path, root: Path) -> tuple[dict[str, dict[str, bool]], dict[str, Record]]:
    """Run independent short and bounded long missions against a staged candidate.

    Return a fixed set of scored checks with separate measurements. A bad
    response, failed process or invalid durable envelope cannot remove a
    mission from the denominator.
    """
    cases = {}
    observations = {}
    runners: tuple[tuple[str, Callable[[Path], tuple[dict[str, bool], Record]], tuple[str, ...]], ...] = (
        ('mount-retired-survey', lambda path: short_case(app, path, 564, handover=False), SHORT_CHECKS),
        ('mount-epoch-handover', lambda path: short_case(app, path, 981, handover=True), SHORT_CHECKS),
        ('mount-bounded-retirement', lambda path: long_case(app, path), LONG_CHECKS),
    )
    for name, run, checks in runners:
        started = monotonic()
        try:
            cases[name], observations[name] = run(root / name)
        except (KeyError, IndexError, TypeError, ValueError, OSError, TimeoutExpired,
                np.linalg.LinAlgError, RuntimeError) as exc:
            cases[name], observations[name] = dict.fromkeys(checks, False), {'error': str(exc)}
        observations[name]['elapsed_s'] = monotonic() - started
    return cases, observations
