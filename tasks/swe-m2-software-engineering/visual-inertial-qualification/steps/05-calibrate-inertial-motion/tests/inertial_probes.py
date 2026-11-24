"""Author physically consistent raw IMU and rolling-shutter survey observations."""

from math import cos, sin
import numpy as np


TICK_NS=5_000_000
G=np.array([0.,0.,-9.80665])


def quat_product(a,b):
    x,y,z,w=a
    X,Y,Z,W=b
    return np.array([w*X+x*W+y*Z-z*Y,w*Y-x*Z+y*W+z*X,
                     w*Z+x*Y-y*X+z*W,w*W-x*X-y*Y-z*Z])


def axis(i,angle):
    q=np.zeros(4)
    q[i]=sin(angle/2.)
    q[3]=cos(angle/2.)
    return q


def ypr(yaw,pitch,roll):
    return quat_product(quat_product(axis(2,yaw),axis(1,pitch)),axis(0,roll))


def rotate(q,val):
    qv=q[:3]
    return val+2.*np.cross(qv,np.cross(qv,val)+q[3]*val)


def inverse(q):
    return q*np.array([-1.,-1.,-1.,1.])


def world(t,kind):
    """Analytic derivatives provide IMU truth independent of the shooting integrator."""
    if kind==0:
        amplitudes=np.array([.41,.23,.21]); freqs=np.array([1.57,2.18,1.24])
        phases=np.array([.30,1.13,-.72]); signs=np.array([1.,1.,1.])
        omega_f=np.array([1.84,1.33,2.61])
    else:
        amplitudes=np.array([.31,.36,.18]); freqs=np.array([2.18,1.53,1.37])
        phases=np.array([-.38,.79,1.2]); signs=np.array([-1.,1.,-1.])
        omega_f=np.array([2.06,1.43,1.96])
    scale=signs*amplitudes
    phase=freqs*t+phases
    pos=scale*np.sin(phase)+np.array([.035,-.012,.021])*t
    vel=scale*freqs*np.cos(phase)+np.array([.035,-.012,.021])
    acc=-scale*freqs**2*np.sin(phase)
    angle_amp=np.array([.49,.36,.31])*signs
    phase=omega_f*t+np.array([-.23,.45,1.16])
    yaw,pitch,roll=angle_amp*np.sin(phase)
    rate_y,rate_p,rate_r=angle_amp*omega_f*np.cos(phase)
    gyro=np.array([rate_r-rate_y*sin(pitch),rate_p*cos(roll)+rate_y*cos(pitch)*sin(roll),
                   -rate_p*sin(roll)+rate_y*cos(pitch)*cos(roll)])
    angle=ypr(yaw,pitch,roll)
    return angle,pos,vel,gyro,rotate(inverse(angle),acc-G)


def write_pose(q,p):
    return {'quaternion_xyzw':q.tolist(),'translation_m':p.tolist()}


def mount_pose(t,kind,mount):
    q,p,_,_,_=world(t,kind)
    return quat_product(q,mount[0]),p+rotate(q,mount[1])


def project(target,pose,calibration):
    q,p=pose
    px=rotate(inverse(q),np.asarray(target)-p)
    if px[2]<=.1:
        return None
    fx,fy,cx,cy=calibration
    return np.array([fx*px[0]/px[2]+cx,fy*px[1]/px[2]+cy])


def build(kind,seed):
    generator=np.random.default_rng(seed)
    epoch0=1_735_029_130_627_430_700+seed*10_000_000_000
    initial_bias=np.array([.026,-.032,.017,.093,-.143,.168])
    warm_bias=np.array([-.032,.040,-.019,-.173,.087,-.143])
    flip=np.array([-1.,1.,-1.,-1.,1.,1.]) if kind else np.ones(6)
    biases={'cold':initial_bias*flip+generator.normal(0.,[.004]*3+[.013]*3),
            'warm':warm_bias*flip+generator.normal(0.,[.004]*3+[.013]*3)}
    mounts={
        'near':(ypr(.091,-.062,.046),np.array([-.10,.041,.068])),
        'far':(ypr(-.10,.071,-.040),np.array([.141,-.033,.088])),
    }
    cameras={}
    hidden={}
    world_points={}
    near_marker={}
    def stamp(value):
        return epoch0+int(round(value*1.e9))
    for index,(name,mount) in enumerate(mounts.items()):
        sign=1. if index==0 else -1.
        intrinsic=[372.,352.,322.,241.] if not index else [430.,414.,401.,306.]
        size=[644,484] if not index else [808,612]
        angles=mount[0]
        initial_mount=quat_product(angles,ypr(.052*sign,-.034,.028*sign)),             mount[1]+np.array([.031*sign,-.027,.02])
        timing=np.r_[sign*generator.uniform(.022,.038),
                     -sign*generator.uniform(.00052,.00108),
                     sign*generator.uniform(.018,.032),
                     -sign*generator.uniform(.021,.039)]
        if kind:
            timing[[0,2,3]] *= -1.
        origins={epoch:{'sensor_reference_ns':value+index*10_000_000,
                        'imu_reference_ns':stamp(base)}
                 for epoch,value,base in [('capture', 1_734_990_000_000_000_000,0.),
                                          ('counter-reset', 23_110_000_000,3.57)]}
        cameras[name]={'height_px':size[1],'width_px':size[0],'intrinsics':intrinsic,
                       'nominal_mount':write_pose(*initial_mount),'clocks':origins}
        hidden[name]={'mount':mount,'timing':timing}
        grid=np.array([[x*.178,y*.187,0.] for x in (-2,-1,0,1,2) for y in (-2,-1,0,1,2)])
        stations=np.arange(.23,9.18,.29)
        names=[]
        for i,center in enumerate(stations):
            q,p=mount_pose(center,kind,mount)
            board=p+rotate(q,grid+np.array([.08*sin(i),.12*cos(i*1.4),1.54+.18*cos(i)]))
            group=[f'{name}-{i}-{j}' for j in range(len(board))]
            world_points.update({key:point.tolist() for key,point in zip(group,board)})
            names.append(group)
        near_marker[name]=(stations,names)

    def clock_tags(center):
        return ('capture',0.,2) if center<3.57 else ('counter-reset',3.57,3)

    def visual(frames):
        records=[]
        for name,camera in cameras.items():
            truth=hidden[name]
            rs,skew,*_=truth['timing']
            intrinsics=camera['intrinsics']
            stations,bank=near_marker[name]
            for center in frames:
                epoch,base,parameter=clock_tags(center)
                offset=truth['timing'][parameter]
                sensor_origin=camera['clocks'][epoch]['sensor_reference_ns']
                delta_ns=int(round((center-base-offset)/(1.+skew)*1.e9))
                site=np.argmin(np.abs(stations-center))
                for target in bank[site]:
                    point=world_points[target]
                    row=int(camera['height_px']/2)
                    for _ in range(12):
                        row_phase=row/(camera['height_px']-1)-.5
                        time=base+delta_ns*1.e-9*(1.+skew)+offset+rs*row_phase
                        px=project(point,mount_pose(time,kind,truth['mount']),intrinsics)
                        if px is None:
                            break
                        located=int(round(px[1]))
                        if located==row:
                            break
                        if not 0<=located<camera['height_px']:
                            px=None
                            break
                        row=located
                    else:
                        px=None
                    if px is None or not 5<px[0]<camera['width_px']-5:
                        continue
                    perturb=generator.normal(0.,.14,2)
                    records.append({'camera':name,'clock_epoch':epoch,'timestamp_ns':sensor_origin+delta_ns,
                                    'row':row,'target':target,'pixel':(px+perturb).tolist()})
        generator.shuffle(records)
        return records

    def anchor(t,noise,velocity):
        q,p,v,*_=world(t,kind)
        attitude,pos,speed=noise
        value={'timestamp_ns':stamp(t),
               'quaternion_xyzw':quat_product(q,ypr(*generator.normal(0.,attitude,3))).tolist(),
               'position_m':(p+generator.normal(0.,pos,3)).tolist(),
               'rotation_sigma_rad':attitude, 'position_sigma_m':pos}
        if velocity:
            value.update(velocity_mps=(v+generator.normal(0.,speed,3)).tolist(),velocity_sigma_mps=speed)
        return value

    def inertial(start,end):
        rows=[]
        for ns in range(round(start*1.e9),round(end*1.e9)+1,TICK_NS):
            time=ns*1.e-9
            label='cold' if time<2.83 else 'warm'
            _,_,_,gyro,acc=world(time,kind)
            disturbance=generator.normal(0.,[.00055,.00055,.00055,.0038,.0038,.0038])
            sample=np.r_[gyro,acc]+biases[label]+disturbance
            rows.append({'timestamp_ns':epoch0+ns,'gyro_rad_s':sample[:3].tolist(),
                         'specific_force_mps2':sample[3:].tolist(),'bias_epoch':label})
        return rows

    frames=np.r_[np.arange(.34,2.80,.159),np.arange(2.94,3.46,.127),np.arange(3.74,6.04,.149)]
    fit={'reference_ns':epoch0,'imu':inertial(0.,6.23),'pixels':visual(frames),
         'anchors':[anchor(0.,(.015,.025,.055),True),anchor(2.59,(.018,.028,.05),False),
                    anchor(6.23,(.015,.025,.055),False)],
         'pose_query_ticks_ns':[stamp(t) for t in np.linspace(.23,6.19,31)]}
    # The first follow-on camera row is deliberately withheld until 1.6 s into continuation.
    test_frames=np.arange(8.10,9.05,.096)
    continuation={'reference_ns':epoch0,'imu':inertial(6.50,9.23),'pixels':visual(test_frames),
                  'anchors':[anchor(6.50,(.00027,.00043,.00054),True)],
                  'pose_query_ticks_ns':[stamp(t) for t in np.linspace(6.50,9.23,25)]}
    return {'bias_epochs':['cold','warm'],'cameras':cameras,'targets':world_points,
            'fit':fit,'continuation':continuation}, {'kind':kind,'epoch0':epoch0,'bias':biases,'cameras':hidden}


def errors(report,truth):
    results={'cameras':{},'biases':{},'poses':{}}
    for name,p in report['cameras'].items():
        actual=truth['cameras'][name]
        values=actual['timing']
        q0,t0=actual['mount']
        dq=abs(np.dot(q0,p['quaternion_xyzw']))
        results['cameras'][name]={
            'mount_error_m':float(np.linalg.norm(t0-p['translation_m'])),
            'mount_rotation_error_rad':float(2*np.arccos(np.clip(dq,0.,1.))),
            'readout_error_ms':abs(p['readout_ns']/1.e6-values[0]*1.e3),
            'skew_error_ppm':abs(p['skew_ppm']-values[1]*1.e6),
            'max_offset_error_ms':max(abs(p['offset_ns'][key]/1.e6-y*1.e3)
                                      for key,y in zip(('capture','counter-reset'),values[2:],strict=True)),
            'validation_rmse_px':p['validation_rmse_px'],
            'validation_matched':p['validation_matched'],
        }
    for name,parameters in report['bias'].items():
        delta=np.asarray(parameters)-truth['bias'][name]
        results['biases'][name]={'gyro_error_rad_s':float(np.linalg.norm(delta[:3])),
                                 'specific_force_error_mps2':float(np.linalg.norm(delta[3:]))}
    for name in ('fit','continuation'):
        positions,angles=[],[]
        for p in report[name]['trajectory']:
            q,point,*_=world((p['timestamp_ns']-truth['epoch0'])*1.e-9,truth['kind'])
            positions.append(float(np.linalg.norm(point-p['position_m'])))
            angles.append(float(2*np.arccos(np.clip(abs(np.dot(q,p['quaternion_xyzw'])),0.,1.))))
        results['poses'][name]={'position_rmse_m':float(np.sqrt(np.mean(np.square(positions)))),
                                'terminal_error_m':positions[-1],
                                'rotation_rmse_rad':float(np.sqrt(np.mean(np.square(angles))))}
    return results


def advance_quaternion(attitude,rotvec):
    angle=float(np.linalg.norm(rotvec))
    if angle<=0.:
        return attitude
    step=np.r_[sin(angle/2.)*rotvec/angle,cos(angle/2.)]
    result=quat_product(attitude,step)
    return result/np.linalg.norm(result)


def sequential_continuation(window,biases):
    """Use ordinary scalar time stepping, independent of the estimator's prefix integration."""
    rows=window['imu']
    origin=window['reference_ns']
    ground=window['anchors'][0]
    q=np.asarray(ground['quaternion_xyzw'])
    p=np.asarray(ground['position_m'])
    v=np.asarray(ground['velocity_mps'])
    def corrected(row):
        bias=biases[row['bias_epoch']]
        return np.asarray(row['gyro_rad_s'])-bias[:3],np.asarray(row['specific_force_mps2'])-bias[3:]
    rate,force=corrected(rows[0])
    a=rotate(q,force)+G
    output=[(q,p,v,a)]
    times=[(rows[0]['timestamp_ns']-origin)*1.e-9]
    for previous,row in zip(rows,rows[1:]):
        step=(row['timestamp_ns']-previous['timestamp_ns'])*1.e-9
        rate_next,force_next=corrected(row)
        following_q=advance_quaternion(q,.5*step*(rate+rate_next))
        following_a=rotate(following_q,force_next)+G
        p=p+step*v+step*step*(2.*a+following_a)/6.
        v=v+step*(a+following_a)/2.
        q,a,rate=following_q,following_a,rate_next
        times.append((row['timestamp_ns']-origin)*1.e-9)
        output.append((q,p,v,a))
    return np.array(times),output


def continuation_at(path,timestamp):
    times,points=path
    if not times[0]-1.e-9<=timestamp<=times[-1]+1.e-9:
        return None
    index=min(len(times)-2,max(0,np.searchsorted(times,timestamp,side='right')-1))
    q,p,v,a=points[index]
    after_q,_,_,after_a=points[index+1]
    step=times[index+1]-times[index]
    tau=min(step,max(0.,timestamp-times[index]))
    frac=tau/step
    d=float(np.dot(q,after_q))
    if d<0:
        after_q,d=-after_q,-d
    angle=np.arccos(np.clip(d,0.,1.))
    if abs(angle)<1e-7:
        orientation=q*(1.-frac)+after_q*frac
    else:
        orientation=(q*sin((1.-frac)*angle)+after_q*sin(frac*angle))/sin(angle)
    orientation/=np.linalg.norm(orientation)
    translation=p+v*tau+.5*a*tau**2+(after_a-a)*tau**3/(6.*step)
    return orientation,translation


def independent_holdout(spec,result,truth):
    """Check the mount separately from drift, then reproject with only frozen inertial inputs."""
    path=sequential_continuation(spec['continuation'],{k:np.asarray(v) for k,v in result['bias'].items()})
    origin=spec['continuation']['reference_ns']
    remainder=[]
    for row in result['continuation']['trajectory']:
        check=continuation_at(path,(row['timestamp_ns']-origin)*1.e-9)
        if check is None:
            raise ValueError('Reported a pose outside the continuation')
        angle,point=check
        remainder.append((float(np.linalg.norm(point-row['position_m'])),
                          float(2*np.arccos(np.clip(abs(np.dot(angle,row['quaternion_xyzw'])),0.,1.)))))
    row_errors={}
    for name,model in spec['cameras'].items():
        reported=result['cameras'][name]
        mounting=np.asarray(reported['quaternion_xyzw']),np.asarray(reported['translation_m'])
        residuals=[]
        survey_residuals=[]
        for feature in spec['continuation']['pixels']:
            if feature['camera']!=name:
                continue
            epoch=model['clocks'][feature['clock_epoch']]
            device=(feature['timestamp_ns']-epoch['sensor_reference_ns'])*1.e-9
            imu=(epoch['imu_reference_ns']-origin)*1.e-9
            phase=feature['row']/(model['height_px']-1.)-.5
            t=imu+reported['offset_ns'][feature['clock_epoch']]*1.e-9+device*(1.+reported['skew_ppm']*1.e-6)
            t+=phase*reported['readout_ns']*1.e-9
            predicted=continuation_at(path,t)
            if predicted is None:
                continue
            full_pose=quat_product(predicted[0],mounting[0]),predicted[1]+rotate(predicted[0],mounting[1])
            uv=project(spec['targets'][feature['target']],full_pose,model['intrinsics'])
            survey_pose=mount_pose(t+(origin-truth['epoch0'])*1.e-9,truth['kind'],mounting)
            direct=project(spec['targets'][feature['target']],survey_pose,model['intrinsics'])
            observed=np.asarray(feature['pixel'])
            if uv is not None and direct is not None:
                residuals.append(float(np.sum((uv-observed)**2)))
                survey_residuals.append(float(np.sum((direct-observed)**2)))
        row_errors[name]={'imu_rmse_px':float(np.sqrt(np.mean(residuals))) if residuals else None,
                          'survey_rmse_px':float(np.sqrt(np.mean(survey_residuals))) if residuals else None,
                          'matched':len(residuals)}
    return {'cameras':row_errors,'max_trajectory_position_agreement_m':max(x[0] for x in remainder),
            'max_trajectory_rotation_agreement_rad':max(x[1] for x in remainder)}


def assess(spec,truth,answer):
    if set(answer.get('cameras',{}))!=set(spec['cameras']) or set(answer.get('bias',{}))!=set(spec['bias_epochs']):
        raise ValueError('No complete inertial calibration report')
    for part in ('fit','continuation'):
        rows=answer[part]['trajectory']
        if [row['timestamp_ns'] for row in rows]!=spec[part]['pose_query_ticks_ns']:
            raise ValueError('Reported the wrong body query stamps')
        for row in rows:
            q,p,v=map(np.asarray,(row['quaternion_xyzw'],row['position_m'],row['velocity_mps']))
            if (q.shape!=(4,) or p.shape!=(3,) or v.shape!=(3,) or abs(np.linalg.norm(q)-1.)>1.e-6
                    or not all(np.all(np.isfinite(item)) for item in (q,p,v))):
                raise ValueError('Invalid reported body pose')
    for name,bias in answer['bias'].items():
        vals=np.asarray(bias)
        if vals.shape!=(6,) or not np.all(np.isfinite(vals)):
            raise ValueError(f'Invalid estimated bias for {name}')
    for name,calibration in answer['cameras'].items():
        q=np.asarray(calibration['quaternion_xyzw'])
        t=np.asarray(calibration['translation_m'])
        offsets=calibration['offset_ns']
        if (q.shape!=(4,) or t.shape!=(3,) or abs(np.linalg.norm(q)-1)>1.e-6 or not np.all(np.isfinite(t)) or
                set(offsets)!=set(spec['cameras'][name]['clocks']) or not all(np.isfinite(x) for x in
                [*offsets.values(),calibration['skew_ppm'],calibration['readout_ns']])):
            raise ValueError(f'Invalid camera calibration for {name}')
    accuracy=errors(answer,truth)
    independent=independent_holdout(spec,answer,truth)
    fit=accuracy['poses']['fit']
    continuation=accuracy['poses']['continuation']
    checks={'recovered_metric_fit_motion': fit['position_rmse_m']<.028 and fit['rotation_rmse_rad']<.018,
            'blind_motion_continuation': (continuation['position_rmse_m']<.045
                and continuation['terminal_error_m']<.08 and continuation['rotation_rmse_rad']<.018
                and independent['max_trajectory_position_agreement_m']<.004
                and independent['max_trajectory_rotation_agreement_rad']<.004)}
    checks['separate_inertial_bias_epochs']=all(
        row['gyro_error_rad_s']<.01 and row['specific_force_error_mps2']<.055
        for row in accuracy['biases'].values())
    for name,expected in accuracy['cameras'].items():
        calculated=independent['cameras'][name]
        observed=answer['cameras'][name]
        checks[f'{name}/timing_and_mount']=(
            expected['max_offset_error_ms']<=1.0 and expected['readout_error_ms']<=1.5
            and expected['mount_error_m']<=.012 and expected['mount_rotation_error_rad']<=.012
            and expected['skew_error_ppm']<=210.
        )
        checks[f'{name}/survey_reprojection']=(calculated['survey_rmse_px'] is not None
                                              and calculated['survey_rmse_px']<=.55)
        checks[f'{name}/inertial_holdout_reprojection']=(calculated['matched']>=150
             and calculated['matched']==observed['validation_matched'] and calculated['imu_rmse_px'] is not None
             and calculated['imu_rmse_px']<=8. and isinstance(observed['validation_rmse_px'],(int,float))
             and abs(calculated['imu_rmse_px']-observed['validation_rmse_px'])<=.035)
    return {key:bool(value) for key,value in checks.items()},{'errors':accuracy,'independent_holdout':independent}


def evaluate_cases(run):
    cases,evidence={},{}
    for kind,seed,name in ((0,213,'warm_imu_and_camera_counter_reset'),(1,916,'independent_motion_and_blind_continuation')):
        try:
            spec,truth=build(kind,seed)
            baseline=run('calibrate-inertial',spec)
            checks,report=assess(spec,truth,baseline)
            if kind==0:
                forged=dict(spec,continuation=dict(spec['continuation']))
                forged['continuation']['pixels']=[
                    dict(point,pixel=[point['pixel'][0]+11.8,point['pixel'][1]])
                    for point in spec['continuation']['pixels']]
                another=run('calibrate-inertial',forged)
                changed=independent_holdout(forged,baseline,truth)
                stable=all(baseline[key]==another.get(key) for key in ('bias','fit','continuation'))
                for cam,model in baseline['cameras'].items():
                    revised=another.get('cameras',{}).get(cam,{})
                    stable &= all(model[key]==revised.get(key) for key in
                                  ('quaternion_xyzw','translation_m','readout_ns','skew_ppm','offset_ns'))
                    check=changed['cameras'][cam]
                    stable &= (check['matched']==revised.get('validation_matched') and
                               abs(check['imu_rmse_px']-revised.get('validation_rmse_px',0.))<=.035 and
                               check['imu_rmse_px']>9.)
                checks['validation_pixels_do_not_change_fit_or_motion']=bool(stable)
                report['altered_holdout']=changed
            else:
                malformed=dict(spec,continuation=dict(spec['continuation']))
                malformed['continuation']['imu']=list(spec['continuation']['imu'])
                sample=malformed['continuation']['imu'][6]
                malformed['continuation']['imu'][6]=dict(sample,bias_epoch='uncommissioned-bias')
                checks['unknown_epoch_keeps_previous_output']=bool(
                    run('calibrate-inertial',malformed,invalid=True).get('atomic'))
            cases[name],evidence[name]=checks,report
        except (ValueError,IndexError,KeyError,TypeError,AttributeError,OverflowError,np.linalg.LinAlgError) as exc:
            cases[name]={'valid_joint_motion_report':False}
            evidence[name]={'error':str(exc)}
    return cases,evidence
