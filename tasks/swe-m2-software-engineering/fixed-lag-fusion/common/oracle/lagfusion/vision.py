"""Track calibrated SE(3) projections with active factor replacement."""

from dataclasses import dataclass
import json
import math

import gtsam as gt
from gtsam.symbol_shorthand import L, X
import numpy as np


def vector(value, size, positive=False):
    """Read a finite numeric vector in the contract's stated coordinate order."""
    if not isinstance(value, list) or len(value) != size or any(type(x) not in (float, int) for x in value):
        raise ValueError('Expected a numeric vector of the declared size')
    result = np.array(value, dtype=float)
    if not np.all(np.isfinite(result)) or (positive and np.any(result <= 0)):
        raise ValueError('Nonfinite or nonpositive coordinate')
    return result


def pose(value):
    """Decode a rigid transform with a unit scalar-first quaternion."""
    orientation = vector(value['quaternion_wxyz'], 4)
    if abs(np.linalg.norm(orientation) - 1.0) > 1e-6:
        raise ValueError('Rotation needs a unit quaternion')
    return gt.Pose3(gt.Rot3.Quaternion(*orientation), vector(value['translation'], 3))


def output_pose(transform):
    """Represent an estimated transform without imposing a quaternion sign."""
    q = transform.rotation().toQuaternion()
    return {'translation': transform.translation().tolist(),
            'quaternion_wxyz': [q.w(), q.x(), q.y(), q.z()]}


def identifier(value):
    if not isinstance(value, str) or not value:
        raise ValueError('Identifiers must be nonempty strings')
    return value


def integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError('Expected a nonnegative integer in range')
    return value


def sigma(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError('Noise must be positive and finite')
    return value


@dataclass(frozen=True)
class Track:
    """Keep an observation identity associated with its current native factor slot."""

    frame: int
    landmark: str
    camera: str
    version: int
    slot: int | None


class Vision:
    """Feed native incremental fixed-lag updates and map receipt IDs to factors."""

    def __init__(self, manifest):
        self.lag = integer(manifest['lag_frames'], 2)
        if self.lag > 64:
            raise ValueError('Lag must fit the supported pose window')
        self.initial = pose(manifest['initial_pose'])
        self.pose_noise = gt.noiseModel.Diagonal.Sigmas(vector(manifest['initial_sigmas'], 6, positive=True))
        self.odom_noise = gt.noiseModel.Diagonal.Sigmas(vector(manifest['odometry_sigmas'], 6, positive=True))
        self.cameras = {}
        for name, row in manifest['calibrations'].items():
            fx, fy, skew, cx, cy = vector(row['intrinsics'], 5)
            self.cameras[identifier(name)] = (pose(row['body_from_camera']),
                                             gt.Cal3_S2(sigma(float(fx)), sigma(float(fy)), skew, cx, cy))
        self.points = {}
        for index, (name, row) in enumerate(sorted(manifest['landmarks'].items())):
            self.points[identifier(name)] = (L(index), vector(row['point'], 3),
                                             gt.noiseModel.Isotropic.Sigma(3, sigma(row['sigma'])))
        params = gt.ISAM2Params()
        params.setRelinearizeThreshold(0.001)
        params.relinearizeSkip = 1
        params.findUnusedFactorSlots = True
        self.solver = gt.IncrementalFixedLagSmoother(self.lag, params)
        self.frame = -1
        self.current = gt.Values()
        self.tracks = {}

    def append_frame(self, packet):
        """Append metric relative body motion and advance the retirement cut."""
        number = integer(packet['frame'])
        if number != self.frame + 1:
            raise ValueError('Frame indices must be consecutive')
        graph, initial = gt.NonlinearFactorGraph(), gt.Values()
        key = X(number)
        if number == 0:
            if packet.get('odometry') is not None:
                raise ValueError('Frame zero has no odometry')
            graph.add(gt.PriorFactorPose3(key, self.initial, self.pose_noise))
            initial.insert(key, self.initial)
        else:
            relative = pose(packet['odometry'])
            graph.add(gt.BetweenFactorPose3(X(self.frame), key, relative, self.odom_noise))
            initial.insert(key, self.current.atPose3(X(self.frame)).compose(relative))
        self.solver.update(graph, initial, {key: float(number)})
        self.frame = number
        self.tracks = {name: track for name, track in self.tracks.items()
                       if track.frame >= number - self.lag}

    def edit_tracks(self, updates):
        """Replace active factors atomically by identity and leave retired evidence summarized."""
        if self.frame < 0 or not isinstance(updates, list):
            raise ValueError('Track updates require an active reconstruction')
        graph, initial = gt.NonlinearFactorGraph(), gt.Values()
        removed, pending, disposition, timestamps, edits = [], {}, {}, {}, {}
        for row in updates:
            name = identifier(row['id'])
            if name in disposition:
                raise ValueError('Duplicate update identity')
            version = integer(row['version'], 1)
            last = self.tracks.get(name)
            action = row['action']
            frame = integer(row['frame'])
            if action not in ('put', 'retract') or frame > self.frame:
                raise ValueError('Unknown track operation or future observation')
            if last and last.frame != frame:
                raise ValueError('A correction cannot change the acquisition frame')
            if frame < self.frame - self.lag:
                disposition[name] = 'expired'
                continue
            if action == 'put':
                landmark = identifier(row['landmark'])
                camera = identifier(row['camera'])
                geometry = vector(row['pixel'], 2)
                noise = gt.noiseModel.Isotropic.Sigma(2, sigma(row['sigma_px']))
                key, seed, prior = self.points[landmark]
                extrinsic, intrinsics = self.cameras[camera]
            elif action == 'retract' and last:
                landmark, camera = last.landmark, last.camera
            else:
                raise ValueError('Unknown action or evidence')
            if last and (frame, landmark, camera) != (last.frame, last.landmark, last.camera):
                raise ValueError('A correction cannot change observation identity')
            if version != (last.version + 1 if last else 1):
                raise ValueError('Track versions must advance consecutively')
            if last and last.slot is not None:
                removed.append(last.slot)
            if action == 'put':
                if not self.current.exists(key) and not initial.exists(key):
                    initial.insert(key, seed)
                    graph.add(gt.PriorFactorPoint3(key, seed, prior))
                timestamps[key] = float(self.frame)
                pending[name] = graph.size()
                graph.add(gt.GenericProjectionFactorCal3_S2(geometry, noise, X(frame), key, intrinsics, extrinsic))
            edits[name] = Track(frame, landmark, camera, version, None)
            disposition[name] = 'applied'
        if edits:
            self.solver.update(graph, initial, timestamps, removed)
            slots = self.solver.getISAM2Result().getNewFactorsIndices()
            for name, track in edits.items():
                location = slots[pending[name]] if name in pending else None
                self.tracks[name] = Track(track.frame, track.landmark, track.camera, track.version, location)
        return disposition

    def apply(self, packet):
        """Process one accepted request and describe the active pose marginal."""
        operation = packet['operation']
        edits = {}
        if operation == 'frame':
            self.append_frame(packet)
        elif operation == 'tracks':
            edits = self.edit_tracks(packet['updates'])
        elif operation != 'estimate':
            raise ValueError('Unknown request operation')
        if self.frame < 0:
            raise ValueError('Estimator has no body pose')
        self.current = self.solver.calculateEstimate()
        current = X(self.frame)
        return {'request_id': packet['request_id'], 'frame': self.frame, 'updates': edits,
                'state': {'pose': output_pose(self.current.atPose3(current)),
                          'covariance': self.solver.marginalCovariance(current).tolist(),
                          'frames': [frame for frame in range(max(0, self.frame-self.lag), self.frame+1)
                                     if self.current.exists(X(frame))],
                          'landmarks': [landmark for landmark, (key, _, _) in self.points.items()
                                        if self.current.exists(key)]}}


def stream(manifest, source, destination):
    """Accept consecutive traffic and replay the most recent receipt exactly."""
    from .__main__ import invalid_constant

    estimator = Vision(manifest)
    last_id, prior, saved = -1, None, None
    for line in source:
        row = json.loads(line, parse_constant=invalid_constant)
        request_id = integer(row['request_id'])
        if request_id == last_id and row == prior:
            reply = saved
        elif request_id > last_id:
            reply = estimator.apply(row)
            last_id, prior, saved = request_id, row, reply
        else:
            raise ValueError('Invalid request identity or replay')
        print(json.dumps(reply, allow_nan=False, separators=(',', ':')), file=destination, flush=True)
