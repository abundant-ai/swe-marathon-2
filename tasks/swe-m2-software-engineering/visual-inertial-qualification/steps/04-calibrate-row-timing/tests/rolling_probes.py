"""Independent raw-pixel fixture and SE(3) reprojection witness."""

import csv
from decimal import Decimal
import math
from pathlib import Path

import numpy as np


STEP_NS = 5_000_000


def multiply(a, b):
    return np.r_[a[3]*b[:3] + b[3]*a[:3] + np.cross(a[:3], b[:3]),
                 a[3]*b[3] - np.dot(a[:3], b[:3])]


def axis(axis, angle):
    q = np.zeros(4)
    q[axis], q[3] = np.sin(angle/2.), np.cos(angle/2.)
    return q


def compose_angles(yaw, pitch, roll):
    return multiply(multiply(axis(2, yaw), axis(1, pitch)), axis(0, roll))


def rotate(q, array):
    a = np.asarray(array, dtype=float)
    inner = 2.*np.cross(q[:3], a)
    return a + q[3]*inner + np.cross(q[:3], inner)


def inverse(q):
    return q*np.array([-1., -1., -1., 1.])


def lerp_quaternion(a, b, fraction):
    score = np.dot(a, b)
    if score < 0.:
        b, score = -b, -score
    theta = math.acos(np.clip(score, -1., 1.))
    if theta < 1.e-7:
        result = (1.-fraction)*a + fraction*b
        return result/np.linalg.norm(result)
    return (a*math.sin((1.-fraction)*theta) + b*math.sin(fraction*theta))/math.sin(theta)


def get_pose(trajectory, seconds):
    stamps, positions, quaternions = trajectory
    index = min(len(stamps)-2, max(0, np.searchsorted(stamps, seconds)-1))
    fraction = (seconds-stamps[index])/(stamps[index+1]-stamps[index])
    return ((1.-fraction)*positions[index] + fraction*positions[index+1],
            lerp_quaternion(quaternions[index], quaternions[index+1], fraction))


def recorded(path):
    with open(path, newline='') as stream:
        rows = list(csv.DictReader(stream))
    start = Decimal(rows[0]['original_seconds'])
    pose_times = np.array([float(Decimal(row['original_seconds'])-start) for row in rows])
    positions = np.array([[float(row[name]) for name in ('tx','ty','tz')] for row in rows])
    quaternions = np.array([[float(row[name]) for name in ('qx','qy','qz','qw')] for row in rows])
    return pose_times, positions, quaternions


def rich(t, sign=1):
    return (np.array([.28*np.sin(2.08*t), .21*np.sin(2.83*t), .14*np.cos(1.74*t)]),
            compose_angles(sign*.46*np.sin(2.03*t), .39*np.cos(1.68*t), .33*np.sin(2.51*t)))


def scripted(t, screw=False):
    if not screw:
        return rich(t, -1)
    change = 2.55
    if t <= change:
        return np.array([0., 0., .14*t]), axis(2, .86*t)
    origin, basis = np.array([0., 0., .14*change]), axis(2, .86*change)
    position, attitude = rich(t-change, 1)
    p0, q0 = rich(0, 1)
    return origin+rotate(basis, position-p0), multiply(multiply(basis, inverse(q0)), attitude)


def body_knots(dataset, mode):
    horizon = 5.92
    times = np.arange(int(horizon*1e9)//STEP_NS+1)*STEP_NS*1e-9
    if mode == 'tumvi':
        source = recorded(dataset)
        knots = [get_pose(source, stamp) for stamp in times]
    else:
        knots = [scripted(stamp, mode == 'screw') for stamp in times]
    xyz, qs = map(np.array, zip(*knots))
    return times, xyz, qs


def coordinate(pose):
    return {'translation_m': pose[0].tolist(), 'quaternion_xyzw': pose[1].tolist()}


def project_fiducial(extrinsic, lens, landmarks):
    position, attitude = extrinsic
    view = rotate(inverse(attitude), landmarks-position)
    if view[2] < .02:
        return None
    fx, fy, cx, cy = lens
    return np.array([fx*view[0]/view[2]+cx, fy*view[1]/view[2]+cy])


def reference_camera(trajectory, t, mount):
    p, q = get_pose(trajectory, t)
    return p+rotate(q, mount[0]), multiply(q, mount[1])


def fixture(dataset, mode, seed):
    rng = np.random.default_rng(seed)
    trajectory = body_knots(dataset, mode)
    origin = 1_520_530_326_856_345_400 + seed*3_000_000_000
    dropout = mode == 'rich'
    body_rows = [
        {'timestamp_ns': origin+i*STEP_NS, **coordinate((point, q))}
        for i,(point,q) in enumerate(zip(trajectory[1], trajectory[2]))
        if not dropout or not 4.560 < i*STEP_NS*1e-9 < 4.720
    ]
    offset = rng.uniform(.018, .035, 2)
    duration = rng.uniform(.023, .038, 2)
    skew = rng.uniform(.00043, .00104, 2)
    truth = {
        'gate-left': {'mount': (np.array([-.12,.035,.058]), compose_angles(.09,-.10,.06)),
                      'clock': np.array([offset[0],duration[0],skew[0]])},
        'right-sensor': {'mount': (np.array([.14,-.042,.029]), compose_angles(-.11,.065,-.075)),
                         'clock': -np.array([offset[1],duration[1],skew[1]])},
    }
    rig, targets = {}, {}
    feed = {'fit': [], 'validation': []}
    for count,(name, camera) in enumerate(truth.items()):
        dimensions = [(644, 484), (808, 608)][count]
        intrinsics = [[373., 361., 323., 244.], [425., 417., 401., 302.]][count]
        mount = camera['mount']
        actual = camera['clock']
        # Varied but physically close nominal hand measurements.
        sign = -1 if (seed+count) % 2 else 1
        displacement = rng.normal(0., .006, 3) + np.array([.025,-.02,.016])*sign
        nominal = mount[0]+displacement, multiply(mount[1], compose_angles(-.065*sign,.055,.04*sign))
        if mode == 'rich':
            actual *= np.array([-1., -1., 1.])
        rig[name] = {
            'width_px': dimensions[0], 'height_px': dimensions[1], 'intrinsics': intrinsics,
            'nominal_body_from_camera': coordinate(nominal),
            'offset_ns_bounds': [-65_000_000,65_000_000], 'readout_ns_bounds': [-44_000_000,44_000_000],
            'skew_ppm_bounds': [-1700.,1700.],
        }
        local_points = np.array([[x*.135,y*.16,0.] for y in range(-3,4) for x in range(-2,3)])
        board_times = np.arange(.25, 5.75, .33)
        bank = []
        for i, hint in enumerate(board_times):
            p,q = reference_camera(trajectory,hint,mount)
            toward = np.array([.10*np.sin(i),.16*np.sin(2*i),1.61+.21*np.cos(i)])
            board = p + rotate(q, toward + local_points)
            names = [f'{name[:2]}-board-{i:02}-{j:02}' for j in range(len(board))]
            bank.append(names)
            targets.update((key, value.tolist()) for key,value in zip(names,board))
        if mode == 'screw' and count == 0:
            fits = np.arange(.32,2.15,.134)
            extras = np.arange(2.20,2.43,.077)
        elif mode == 'screw':
            fits = np.arange(2.79,5.10,.137)
            extras = np.arange(5.15,5.66,.104)
        else:
            fits = np.r_[np.arange(.32,2.08,.137),np.arange(2.9,4.36,.114)]
            extras = np.r_[np.arange(2.17,2.69,.093),np.arange(4.47,5.63,.097)]
            if dropout:
                fits = np.r_[fits,4.515]
                extras = np.r_[extras,4.644]
        for purpose, frames in (('fit',fits),('validation',extras)):
            for center in frames:
                stamp_ns = int(round((center-actual[0])/(1.+actual[2])*1e9))
                stamp = stamp_ns*1e-9
                i = int(np.argmin(np.abs(center-board_times)))
                for key in bank[i]:
                    world = targets[key]
                    row, predicted = dimensions[1]//2, None
                    for _ in range(12):
                        depth_time = stamp*(1.+actual[2])+actual[0]+actual[1]*(row/(dimensions[1]-1)-.5)
                        camera_pose = reference_camera(trajectory,depth_time,mount)
                        predicted = project_fiducial(camera_pose,intrinsics,world)
                        if predicted is None:
                            break
                        found = int(round(float(predicted[1])))
                        if found == row:
                            break
                        if found < 0 or found >= dimensions[1]:
                            predicted = None
                            break
                        row = found
                    else:
                        predicted = None
                    if predicted is None or not (5 <= predicted[0] < dimensions[0]-5
                                                and 5 <= predicted[1] < dimensions[1]-5):
                        continue
                    noise = rng.normal(0., .135, 2)
                    if purpose == 'fit' and rng.integers(0,90) == 0:
                        noise += rng.normal(0., .85, 2)
                    feed[purpose].append({'camera':name,'target':key,'timestamp_ns':origin+stamp_ns,
                                          'row':row,'pixel':(predicted+noise).tolist()})
    for collection in feed.values():
        rng.shuffle(collection)
    spec = {'clock_reference_ns':origin, 'max_gap_ns':12_000_000, 'body':body_rows, 'cameras':rig,
            'targets':targets, **feed}
    return spec, truth


def physical_error(report, truth):
    return {
        name: ({'offset_error_ms': abs(row['offset_ns']*1e-6-truth[name]['clock'][0]*1e3),
                'readout_error_ms': abs(row['readout_ns']*1e-6-truth[name]['clock'][1]*1e3),
                'skew_error_ppm': abs(row['skew_ppm']-truth[name]['clock'][2]*1e6),
                'translation_error_m': float(np.linalg.norm(row['body_from_camera']['translation_m']-truth[name]['mount'][0])),
                'rotation_error_rad': float(2.*np.arccos(np.clip(abs(np.dot(
                    row['body_from_camera']['quaternion_xyzw'],truth[name]['mount'][1])),0.,1.)))}
               if row['status']=='ok' else {})
        for name,row in report['cameras'].items()
    }


def reprojection(spec, camera_name, calibration):
    trajectory = np.array([(row['timestamp_ns']-spec['clock_reference_ns'])*1e-9 for row in spec['body']]),         np.array([row['translation_m'] for row in spec['body']]),         np.array([row['quaternion_xyzw'] for row in spec['body']])
    camera = spec['cameras'][camera_name]
    mounting = calibration['body_from_camera']
    mount = np.asarray(mounting['translation_m']),np.asarray(mounting['quaternion_xyzw'])
    residuals = []
    seen = 0
    for point in spec['validation']:
        if point['camera'] != camera_name:
            continue
        seen += 1
        x = (point['timestamp_ns']-spec['clock_reference_ns'])*1e-9
        time = (x*(1.+calibration['skew_ppm']*1e-6)+calibration['offset_ns']*1e-9+
                calibration['readout_ns']*1e-9*(point['row']/(camera['height_px']-1)-.5))
        ticks = trajectory[0]
        if time < ticks[0] or time > ticks[-1]:
            continue
        right = np.searchsorted(ticks,time)
        if 0 < right < len(ticks) and ticks[right]-ticks[right-1] > spec['max_gap_ns']*1e-9                 and min(abs(time-ticks[right]), abs(time-ticks[right-1])) > 5.e-10:
            continue
        prediction = project_fiducial(reference_camera(trajectory,time,mount),
                                    camera['intrinsics'],spec['targets'][point['target']])
        if prediction is not None:
            residuals.append(np.linalg.norm(prediction-point['pixel'])**2)
    return seen,len(residuals),float(np.sqrt(np.mean(residuals))) if residuals else None


def guaranteed_fit_count(spec, camera_name):
    """Independent admissible-time interval check using all box corners."""
    from itertools import product

    camera = spec['cameras'][camera_name]
    reference = spec['clock_reference_ns']
    times = np.asarray([row['timestamp_ns']-reference for row in spec['body']])/1.e9
    gaps = [(left,right) for left,right in zip(times,times[1:]) if right-left > spec['max_gap_ns']/1.e9+1.e-12]
    values = list(product(camera['offset_ns_bounds'],camera['readout_ns_bounds'],camera['skew_ppm_bounds']))
    count = 0
    for feature in spec['fit']:
        if feature['camera'] != camera_name:
            continue
        t = (feature['timestamp_ns']-reference)/1.e9
        fraction = feature['row']/(camera['height_px']-1.)-.5
        possible = [t+(offset+duration*fraction)/1.e9+t*skew/1.e6 for offset,duration,skew in values]
        first,last = min(possible),max(possible)
        if first >= times[0] and last <= times[-1] and not any(first < b and last > a for a,b in gaps):
            count += 1
    return count


def gauge_proof(spec, true):
    """Construct a second rigid mount and offset with the same physical row poses."""
    camera = spec['cameras']['gate-left']
    reference = spec['clock_reference_ns']
    trajectory = (np.asarray([row['timestamp_ns']-reference for row in spec['body']])/1.e9,
                  np.array([row['translation_m'] for row in spec['body']]),
                  np.array([row['quaternion_xyzw'] for row in spec['body']]))
    shift = .018
    correction = axis(2, -.86*shift)
    original = true['mount']
    alternate = (rotate(correction, original[0]) + [0.,0.,-.14*shift], multiply(correction, original[1]))
    maximum = 0.
    count = 0
    for feature in spec['fit'] + spec['validation']:
        if feature['camera'] != 'gate-left':
            continue
        time = (feature['timestamp_ns']-reference)/1.e9
        offset, readout, skew = true['clock']
        t = time*(1.+skew)+offset + readout*(feature['row']/(camera['height_px']-1)-.5)
        a = reference_camera(trajectory,t,original)
        b = reference_camera(trajectory,t+shift,alternate)
        landmark = spec['targets'][feature['target']]
        original_pixel = project_fiducial(a,camera['intrinsics'],landmark)
        shifted_pixel = project_fiducial(b,camera['intrinsics'],landmark)
        assert original_pixel is not None and shifted_pixel is not None
        maximum = max(maximum,float(np.linalg.norm(original_pixel-shifted_pixel)))
        count += 1
    return {'alternate_offset_ms':shift*1e3,'max_pixel_change':maximum,'observations':count}


def report_and_evidence(run, spec, truth, degenerate=()):
    raw = run('calibrate-row-timing',spec)
    if set(raw.get('cameras',{})) != set(spec['cameras']):
        raise ValueError('Calibration process returned no complete camera report')
    evidence, metrics, flags = {}, physical_error(raw,truth), {}
    for name,row in raw['cameras'].items():
        fit_count = guaranteed_fit_count(spec,name)
        support_ok = row['fit_count'] == fit_count and fit_count >= 24
        s = np.asarray(row['timing_spectrum'],dtype=float)
        valid_spectrum = (s.shape == (3,) and np.all(np.isfinite(s)) and np.all(np.diff(s) <= 0) and s[-1] >= 0)
        timing_observable = valid_spectrum and s[-1] >= max(.025,1.e-5*s[0])
        evidence[name] = {'status': row['status'], 'fit_count': fit_count, 'timing_spectrum': row['timing_spectrum']}
        if name in degenerate:
            abstained = (row['status']=='degenerate' and valid_spectrum and not timing_observable
                        and row['validation_count']==sum(point['camera']==name for point in spec['validation'])
                        and row['validation_matched']==0 and all(row[key] is None for key in
                        ('offset_ns','readout_ns','skew_ppm','body_from_camera','validation_rmse_px')))
            flags[name] = {'support': support_ok,'degeneracy': abstained}
            continue
        status = row['status']=='ok'
        metric = metrics[name]
        limits = {'offset_error_ms': .9, 'readout_error_ms': 1.5, 'skew_error_ppm': 200.,
                  'translation_error_m': .007, 'rotation_error_rad': .007}
        q = row['body_from_camera']['quaternion_xyzw'] if status else []
        physical = status and len(q)==4 and abs(np.linalg.norm(q)-1.)<1.e-6             and all(np.isfinite(metric[k]) and metric[k]<=limit for k,limit in limits.items())
        count,matched,rmse = reprojection(spec,name,row) if status else (0,0,None)
        valid = (status and row['validation_count']==count and row['validation_matched']==matched and
                 matched>=40 and rmse is not None and rmse<=.55 and
                 abs(row['validation_rmse_px']-rmse)<=1.e-4)
        flags[name] = {'support':support_ok,'identifiable': bool(timing_observable),'physical':bool(physical),
                       'held_out_reprojection':bool(valid)}
        evidence[name].update(physical_error=metric, held_out_count=count, matched=matched,
                              withheld=count-matched, independent_rmse_px=rmse,
                              estimated={k: row[k] for k in ('offset_ns','readout_ns','skew_ppm')})
    return raw, flags, evidence


def evaluate_cases(run, dataset):
    cases, diagnostics = {}, {}
    for mode,seed in [('tumvi',132),('rich',432),('screw',587)]:
        try:
            spec,truth = fixture(dataset,mode,seed)
            active, checks, details = report_and_evidence(run,spec,truth,('gate-left',) if mode=='screw' else ())
            flags = {f'{name}/{key}':value for name,metrics in checks.items() for key,value in metrics.items()}
            if mode=='rich':
                updated = [dict(point,pixel=[point['pixel'][0]+2.9,point['pixel'][1]])
                           for point in spec['validation']]
                revised = dict(spec,validation=updated)
                new = run('calibrate-row-timing',revised).get('cameras',{})
                for name,original in active['cameras'].items():
                    keys = ('offset_ns','readout_ns','skew_ppm','body_from_camera','fit_count','timing_spectrum','status')
                    fixed = all(original[key]==new.get(name,{}).get(key) for key in keys)
                    count,matched,score = reprojection(revised,name,original)
                    revised_ok = (matched==new.get(name,{}).get('validation_matched') and
                                  count==new.get(name,{}).get('validation_count') and
                                  score is not None and score>2.4 and
                                  abs(new.get(name,{}).get('validation_rmse_px',0.)-score)<=1.e-4)
                    flags[f'{name}/holdout_fit_frozen'] = fixed
                    flags[f'{name}/holdout_error_recomputed'] = revised_ok
                    flags[f'{name}/time_gap_excludes_observations'] = details[name]['withheld']>=25
                    details[name]['changed_holdout_rmse_px'] = score
                wrong = dict(spec,fit=list(spec['fit']))
                sample = wrong['fit'][0]
                wrong['fit'][0] = dict(sample,row=spec['cameras'][sample['camera']]['height_px'])
                flags['invalid_sensor_row_keeps_output'] = bool(
                    run('calibrate-row-timing',wrong,invalid=True).get('atomic')
                )
            if mode=='screw':
                details['gauge_witness'] = gauge_proof(spec,truth['gate-left'])
                assert details['gauge_witness']['observations']>=200 and details['gauge_witness']['max_pixel_change']<1.e-7
            cases[mode] = {name:bool(value) for name,value in flags.items()}
            diagnostics[mode] = details
        except (ValueError,IndexError,KeyError,TypeError,AttributeError,OverflowError,np.linalg.LinAlgError) as exc:
            cases[mode] = {'candidate_response_valid':False}
            diagnostics[mode] = {'error':str(exc)}
    return cases,diagnostics
