"""Recover rolling shutter, clock drift, and a rigid camera mount from fiducials."""

import numpy as np


PARAM_SCALE = np.array([.1, .1, .1, .1, .1, .1, .01, .01, .001])
HUBER_PX = 1.4


def numeric(value, size):
    if not isinstance(value, list) or len(value) != size or any(type(x) not in (int, float) for x in value):
        raise ValueError('Expected a numeric vector of the declared size')
    data = np.array(value, dtype=float)
    if not np.all(np.isfinite(data)):
        raise ValueError('Nonfinite optical or pose field')
    return data


def integer(value):
    if type(value) is not int:
        raise ValueError('Timestamps and original sensor rows must be integers')
    return value


def matrix(q):
    x, y, z, w = np.moveaxis(np.asarray(q), -1, 0)
    return np.stack((1 - 2*(y*y + z*z), 2*(x*y - z*w), 2*(x*z + y*w),
                     2*(x*y + z*w), 1 - 2*(x*x + z*z), 2*(y*z - x*w),
                     2*(x*z - y*w), 2*(y*z + x*w), 1 - 2*(x*x + y*y)), axis=-1).reshape(np.shape(q)[:-1]+(3, 3))


def quaternion(R):
    symmetric = np.array([
        [R[0, 0]-R[1, 1]-R[2, 2], R[0, 1]+R[1, 0], R[0, 2]+R[2, 0], R[2, 1]-R[1, 2]],
        [R[0, 1]+R[1, 0], R[1, 1]-R[0, 0]-R[2, 2], R[1, 2]+R[2, 1], R[0, 2]-R[2, 0]],
        [R[0, 2]+R[2, 0], R[1, 2]+R[2, 1], R[2, 2]-R[0, 0]-R[1, 1], R[1, 0]-R[0, 1]],
        [R[2, 1]-R[1, 2], R[0, 2]-R[2, 0], R[1, 0]-R[0, 1], np.trace(R)]])
    q = np.linalg.eigh(symmetric)[1][:, -1]
    return (-q if q[3] < 0 else q).tolist()


def pose(row):
    q = numeric(row['quaternion_xyzw'], 4)
    if abs(np.linalg.norm(q)-1.) > 1e-6:
        raise ValueError('Attitudes must be unit quaternions')
    return numeric(row['translation_m'], 3), q


def exp(rotation):
    theta = np.linalg.norm(rotation)
    imag = .5*np.sinc(theta/(2*np.pi))*rotation
    return matrix(np.r_[imag, np.cos(.5*theta)])


class Body:
    """Interpolated survey trajectory with explicit gap support."""

    def __init__(self, rows, origin, gap_ns):
        if len(rows) < 2 or gap_ns <= 0:
            raise ValueError('At least two body poses and a positive gap limit are needed')
        self.times = np.array([(integer(row['timestamp_ns'])-origin)*1e-9 for row in rows])
        self.duration = np.diff(self.times)
        if np.any(self.duration <= 0):
            raise ValueError('Body reference timestamps must be strictly increasing')
        self.maximum_gap = gap_ns*1e-9
        self.positions, self.q = map(np.array, zip(*(pose(row) for row in rows)))
        self.left = self.q[:-1]
        self.right = self.q[1:].copy()
        dot = (self.left*self.right).sum(axis=1)
        self.right[dot < 0] *= -1.
        self.angles = np.arccos(np.clip(np.abs(dot), 0., 1.))
        self.oversize = np.r_[0, np.cumsum(self.duration > self.maximum_gap+1e-12)]

    def support_interval(self, lower, upper):
        a = np.clip(np.searchsorted(self.times, lower, 'right')-1, 0, len(self.times)-1)
        b = np.clip(np.searchsorted(self.times, upper, 'left'), 0, len(self.times)-1)
        return ((lower >= self.times[0]) & (upper <= self.times[-1]) &
                (self.oversize[b] == self.oversize[a]))

    def lookup(self, times):
        left = np.clip(np.searchsorted(self.times, times, 'right')-1, 0, len(self.times)-2)
        delta = times - self.times[left]
        f = np.clip(delta/self.duration[left], 0., 1.)
        exact = (abs(delta) < 5e-10) | (abs(times-self.times[left+1]) < 5e-10)
        support = ((times >= self.times[0]-5e-10) & (times <= self.times[-1]+5e-10) &
                   ((self.duration[left] <= self.maximum_gap+1e-12) | exact))
        theta = self.angles[left]/np.pi
        norm = np.sinc(theta)
        alpha = (1.-f)*np.sinc((1.-f)*theta)/norm
        beta = f*np.sinc(f*theta)/norm
        angles = matrix(alpha[:, None]*self.left[left] + beta[:, None]*self.right[left])
        positions = self.positions[left] + f[:, None] * (self.positions[left+1]-self.positions[left])
        return positions, angles, support


class Camera:
    def __init__(self, row):
        self.initial_position, q = pose(row['nominal_body_from_camera'])
        self.initial_attitude = matrix(q)
        self.fx, self.fy, self.cx, self.cy = numeric(row['intrinsics'], 4)
        if min(self.fx, self.fy) <= 0:
            raise ValueError('Focal lengths must be positive')
        self.height = integer(row['height_px'])
        self.width = integer(row['width_px'])
        if min(self.height, self.width) < 2:
            raise ValueError('Invalid sensor dimensions')
        self.lower, self.upper = np.array(
            [numeric(row['offset_ns_bounds'], 2)*1e-9, numeric(row['readout_ns_bounds'], 2)*1e-9,
             numeric(row['skew_ppm_bounds'], 2)*1e-6]
        ).T
        if np.any(self.lower >= self.upper):
            raise ValueError('Nonempty timing bounds required')

    def mount(self, physical):
        return self.initial_position + physical[3:6], self.initial_attitude @ exp(physical[:3])

    def project(self, body, observations, packed):
        physical = packed * PARAM_SCALE
        t, phases, xyz, _ = observations
        offset, readout, skew = physical[-3:]
        position, attitude, valid = body.lookup(t + offset + readout*phases + skew*t)
        mounting, rotation = self.mount(physical)
        in_body = np.einsum('nji,nj->ni', attitude, xyz-position)
        in_camera = (in_body - mounting) @ rotation
        depth = in_camera[:, 2]
        result = in_camera[:, :2] / np.maximum(.02, depth)[:, None]
        result *= [self.fx, self.fy]
        result += [self.cx, self.cy]
        return result, valid & (depth > .02)

    def possible_support(self, body, samples):
        t, phases, _, _ = samples
        coef = np.column_stack((np.ones(len(t)), phases, t))
        lower, upper = coef*self.lower, coef*self.upper
        return body.support_interval(t + np.minimum(lower, upper).sum(axis=1),
                                     t + np.maximum(lower, upper).sum(axis=1))


def get_points(rows, cam, origin, targets):
    stamps, phases, locations, pixels = [], [], [], []
    for row in rows:
        sensor_row = integer(row['row'])
        if not 0 <= sensor_row < cam.height:
            raise ValueError('Original sensor row lies outside the image')
        stamps.append((integer(row['timestamp_ns'])-origin)*1e-9)
        phases.append(sensor_row/(cam.height-1.) - .5)
        locations.append(targets[row['target']])
        pixels.append(numeric(row['pixel'], 2))
    return (np.asarray(stamps), np.asarray(phases), np.asarray(locations).reshape(-1, 3),
            np.asarray(pixels).reshape(-1, 2))


def finite_difference(evaluate, packed, selected):
    delta = 1e-4
    columns = []
    for k in selected:
        step = np.zeros_like(packed)
        step[k] = delta
        columns.append((evaluate(packed+step)-evaluate(packed-step))/(2*delta))
    return np.column_stack(columns)


def robust(delta):
    norm = np.linalg.norm(delta.reshape(-1, 2), axis=1)
    loss = np.where(norm <= HUBER_PX, .5*norm**2, HUBER_PX*(norm-.5*HUBER_PX))
    weights = np.minimum(1., HUBER_PX/np.maximum(norm, 1e-12))
    return float(loss.sum()), np.repeat(np.sqrt(weights), 2)


def estimate(cam, body, fit):
    selected = np.arange(9)

    def evaluate(vector):
        return (cam.project(body, fit, vector)[0]-fit[-1]).ravel()

    bounds = np.stack((cam.lower, cam.upper))/PARAM_SCALE[6:]
    packed = np.r_[np.zeros(6), np.clip(np.zeros(3), *bounds)]
    error = evaluate(packed)
    loss, weights = robust(error)
    damping = 1e-3
    for _ in range(30):
        J = finite_difference(evaluate, packed, selected) * weights[:, None]
        H = J.T@J
        gradient = J.T@(error*weights)
        if np.linalg.norm(gradient, ord=np.inf) < 2e-5:
            break
        accepted = False
        for _ in range(10):
            step = np.linalg.solve(H+damping*np.diag(np.maximum(1., H.diagonal())), -gradient)
            candidate = packed.copy()
            candidate[selected] += step
            candidate[6:] = np.clip(candidate[6:], *bounds)
            adjusted = evaluate(candidate)
            new_loss, new_weights = robust(adjusted)
            if new_loss < loss:
                accepted = True
                packed, error, loss, weights = candidate, adjusted, new_loss, new_weights
                damping = max(1e-8, damping*.3)
                break
            damping *= 8
        if not accepted or np.linalg.norm(step) < 5e-7:
            break
    jacobian = finite_difference(evaluate, packed, np.arange(9))
    spatial, temporal = jacobian[:, :6], jacobian[:, 6:]
    removed = temporal - spatial @ np.linalg.lstsq(spatial, temporal, rcond=1e-10)[0]
    spectrum = np.linalg.svd(removed / np.sqrt(len(fit[0])), compute_uv=False)
    geometry_rank = np.linalg.matrix_rank(spatial, tol=np.linalg.norm(spatial, 2)*1e-7)
    valid = cam.project(body, fit, packed)[1]
    return packed, spectrum, geometry_rank == 6 and np.all(valid)


def solve(spec):
    origin = integer(spec['clock_reference_ns'])
    body = Body(spec['body'], origin, integer(spec['max_gap_ns']))
    cameras = {name: Camera(row) for name, row in spec['cameras'].items()}
    targets = {name: numeric(row, 3) for name, row in spec['targets'].items()}
    if any(row['camera'] not in cameras for purpose in ('fit', 'validation') for row in spec[purpose]):
        raise ValueError('Unknown camera in observations')
    report = {}
    for name, camera in cameras.items():
        fit = get_points([o for o in spec['fit'] if o['camera'] == name], camera, origin, targets)
        check = get_points([o for o in spec['validation'] if o['camera'] == name], camera, origin, targets)
        keep = camera.possible_support(body, fit)
        fit = tuple(part[keep] for part in fit)
        data = {'status': 'insufficient_support', 'fit_count': int(keep.sum()), 'offset_ns': None,
                'readout_ns': None, 'skew_ppm': None, 'body_from_camera': None, 'timing_spectrum': None,
                'validation_count': len(check[0]), 'validation_matched': 0, 'validation_rmse_px': None}
        report[name] = data
        if len(fit[0]) < 24 or len(np.unique(fit[0])) < 8:
            continue
        packed, spectrum, spatial = estimate(camera, body, fit)
        data['timing_spectrum'] = spectrum.tolist()
        if spectrum[-1] < max(.025, 1e-5*spectrum[0]) or not spatial:
            data['status'] = 'degenerate'
            continue
        physical = PARAM_SCALE*packed
        mounting, rotation = camera.mount(physical)
        error, valid = camera.project(body, check, packed)
        error = error[valid]-check[-1][valid]
        data.update(status='ok', offset_ns=physical[6]*1e9, readout_ns=physical[7]*1e9,
                    skew_ppm=physical[8]*1e6,
                    body_from_camera={'translation_m': mounting.tolist(), 'quaternion_xyzw': quaternion(rotation)},
                    validation_matched=int(valid.sum()),
                    validation_rmse_px=float(np.sqrt(np.mean(np.sum(error**2, axis=1)))) if valid.any() else None)
    return {'cameras': report}
