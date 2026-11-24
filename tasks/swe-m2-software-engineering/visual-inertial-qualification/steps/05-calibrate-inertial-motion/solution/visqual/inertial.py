"""Batch fit a rolling-shutter rig by repeatedly integrating debiased inertial data."""

import numpy as np


G_WORLD = np.array([0., 0., -9.80665])
BIAS_SCALE = np.array([.04, .04, .04, .19, .19, .19])
INITIAL_SCALE = np.array([.08, .08, .08, .11, .11, .11, .18, .18, .18])


def qmul(a, b):
    u,v = a[..., :3],b[..., :3]
    s,t = a[..., 3:],b[..., 3:]
    return np.concatenate((s*v+t*u+np.cross(u,v),s*t-np.sum(u*v,axis=-1,keepdims=True)),axis=-1)


def qexp(rotvec):
    theta = np.linalg.norm(rotvec,axis=-1,keepdims=True)
    return np.concatenate((.5*np.sinc(theta/(2*np.pi))*rotvec,np.cos(.5*theta)),axis=-1)


def qconj(q):
    return q*np.array([-1.,-1.,-1.,1.])


def rotate(q, a):
    cross = 2.*np.cross(q[..., :3],a)
    return a+q[..., 3:]*cross+np.cross(q[..., :3],cross)


def qlog(q):
    q = np.where(q[..., 3:]<0.,-q,q)
    n = np.linalg.norm(q[..., :3],axis=-1,keepdims=True)
    factor = np.where(n < 1.e-12,2.,2.*np.arctan2(n,q[..., 3:])/np.maximum(n,1.e-15))
    return factor*q[..., :3]


def chain(deltas, initial):
    """Parallel prefix multiplication, preserving the time order of noncommuting increments."""
    prefix = deltas.copy()
    step=1
    while step<len(prefix):
        prefix[step:] = qmul(prefix[:-step],prefix[step:])
        step*=2
    sequence=np.vstack((initial,qmul(initial,prefix)))
    return sequence/np.linalg.norm(sequence,axis=1,keepdims=True)


class ImuWindow:
    def __init__(self, raw, epoch_index):
        self.origin = raw['reference_ns']
        stamps = [row['timestamp_ns'] for row in raw['imu']]
        if type(self.origin) is not int or len(stamps)<2 or any(type(stamp) is not int for stamp in stamps):
            raise ValueError('At least two native integer IMU stamps are required')
        self.times = np.asarray([stamp-self.origin for stamp in stamps])*1.e-9
        self.omega = np.array([row['gyro_rad_s'] for row in raw['imu']])
        self.force = np.array([row['specific_force_mps2'] for row in raw['imu']])
        self.epochs = np.array([epoch_index[row['bias_epoch']] for row in raw['imu']])
        self.dt = np.diff(self.times)[:,None]
        if np.any(self.dt<=0.) or np.any(self.dt>.04+1e-12):
            raise ValueError('IMU stamps must increase with no interval longer than 40 ms')
        self.initial = raw['anchors'][0]
        self.initial_q=np.asarray(self.initial['quaternion_xyzw'])
        self.initial_p=np.asarray(self.initial['position_m'])
        self.initial_v=np.asarray(self.initial['velocity_mps'])
        self.anchors=raw['anchors']
        if self.initial['timestamp_ns']!=stamps[0] or any(not stamps[0]<=a['timestamp_ns']<=stamps[-1] for a in self.anchors):
            raise ValueError('The initial prior must match the first IMU sample and all anchors need support')
        if (self.omega.shape!=(len(stamps),3) or self.force.shape!=(len(stamps),3) or
                not np.all(np.isfinite(self.omega)) or not np.all(np.isfinite(self.force))):
            raise ValueError('Invalid inertial vector')

    def integrate(self,bias,initial):
        q_initial=qmul(self.initial_q,qexp(initial[:3]))
        p_initial=self.initial_p+initial[3:6]
        v_initial=self.initial_v+initial[6:9]
        corrections = bias[self.epochs]
        corrected_rate=self.omega-corrections[:,:3]
        angles = .5*self.dt*(corrected_rate[:-1]+corrected_rate[1:])
        q=chain(qexp(angles),q_initial)
        a=rotate(q,self.force-corrections[:,3:])+G_WORLD
        dv=.5*self.dt*(a[:-1]+a[1:])
        v=np.vstack((v_initial,v_initial+np.cumsum(dv,axis=0)))
        dp=self.dt*v[:-1]+self.dt**2*(a[:-1]/3.+a[1:]/6.)
        p=np.vstack((p_initial,p_initial+np.cumsum(dp,axis=0)))
        return q,p,v,a

    def query(self,trajectory,t):
        q,p,v,a=trajectory
        index=np.clip(np.searchsorted(self.times,t,'right')-1,0,len(self.dt)-1)
        tau=(t-self.times[index])[:,None]
        step=self.dt[index]
        tau=np.clip(tau,0.,step)
        delta_a=a[index+1]-a[index]
        motion=p[index]+v[index]*tau+.5*a[index]*tau**2+delta_a*tau**3/(6.*step)
        velocity=v[index]+a[index]*tau+delta_a*tau**2/(2.*step)
        relative=qlog(qmul(qconj(q[index]),q[index+1]))
        attitude=qmul(q[index],qexp(relative*tau/step))
        return attitude,motion,velocity

    def anchor_residual(self,trajectory):
        anchor_t=np.array([row['timestamp_ns']-self.origin for row in self.anchors])*1.e-9
        pose,p,v=self.query(trajectory,anchor_t)
        residual=[]
        for row,q,a,b in zip(self.anchors,pose,p,v,strict=True):
            rotation=qlog(qmul(qconj(np.asarray(row['quaternion_xyzw'])),q))
            residual.extend(rotation/row['rotation_sigma_rad'])
            residual.extend((a-row['position_m'])/row['position_sigma_m'])
            if 'velocity_mps' in row:
                residual.extend((b-row['velocity_mps'])/row['velocity_sigma_mps'])
        return np.asarray(residual)


class Camera:
    def __init__(self, raw):
        self.q=np.asarray(raw['nominal_mount']['quaternion_xyzw'])
        self.p=np.asarray(raw['nominal_mount']['translation_m'])
        self.height=raw['height_px']
        self.intrinsics=np.asarray(raw['intrinsics'])
        self.clocks={name:(n,row) for n,(name,row) in enumerate(raw['clocks'].items())}
        self.scale=np.r_[np.repeat(.13,3),np.repeat(.12,3), .02, .001,
                         np.repeat(.02,len(self.clocks))]
        self.limit=np.r_[np.repeat(np.inf,6),.045,.0016,np.repeat(.060,len(self.clocks))]/self.scale

    def observations(self,body,rows,targets):
        clock=[]
        time=[]
        init=[]
        phase=[]
        points=[]
        pixels=[]
        for row in rows:
            if (type(row['row']) is not int or not 0<=row['row']<self.height
                    or type(row['timestamp_ns']) is not int):
                raise ValueError('A corner requires an original sensor row and integer epoch stamp')
            index,base=self.clocks[row['clock_epoch']]
            clock.append(index)
            init.append((base['imu_reference_ns']-body.origin)*1.e-9)
            time.append((row['timestamp_ns']-base['sensor_reference_ns'])*1.e-9)
            phase.append(row['row']/(self.height-1)-.5)
            points.append(targets[row['target']])
            pixels.append(row['pixel'])
        arrays=[np.array(item) for item in (init,time,phase,points,pixels)]
        return np.asarray(clock,dtype=int),*arrays

    def model(self,parameters):
        q=qmul(self.q,qexp(parameters[:3]))
        p=self.p+parameters[3:6]
        return q,p

    def residual(self,body,trajectory,rows,parameters):
        clock,base,time,phase,points,pixels=rows
        timestamp=base+time*(1.+parameters[7])+parameters[6]*phase+parameters[8+clock]
        valid=(timestamp>=body.times[0])&(timestamp<=body.times[-1])
        q_body,p_body,_=body.query(trajectory,timestamp)
        q_mount,p_mount=self.model(parameters)
        body_points=rotate(qconj(q_body),points-p_body)
        xyz=rotate(qconj(q_mount),body_points-p_mount)
        valid &= xyz[:,2]>.1
        ratio=xyz[:,:2]/np.maximum(.045,xyz[:,2:3])
        px=ratio*self.intrinsics[:2]+self.intrinsics[2:]
        return px-pixels,valid


class Fit:
    def __init__(self,spec):
        self.spec=spec
        self.bias_index={name:i for i,name in enumerate(spec['bias_epochs'])}
        if not self.bias_index or len(self.bias_index)!=len(spec['bias_epochs']):
            raise ValueError('Bias epoch names must be distinct')
        self.fit=ImuWindow(spec['fit'],self.bias_index)
        self.holdout=ImuWindow(spec['continuation'],self.bias_index)
        self.cameras={name:Camera(record) for name,record in spec['cameras'].items()}
        self.fit_rows={name:cam.observations(self.fit,[o for o in spec['fit']['pixels'] if o['camera']==name],
                                            spec['targets'])
                       for name,cam in self.cameras.items()}
        self.holdout_rows={name:cam.observations(self.holdout,
                                [o for o in spec['continuation']['pixels'] if o['camera']==name],spec['targets'])
                          for name,cam in self.cameras.items()}
        if set(self.fit.epochs)!=set(range(len(self.bias_index))):
            raise ValueError('All declared bias epochs need observations in the fit')
        if any(row['camera'] not in self.cameras for phase in ('fit','continuation') for row in spec[phase]['pixels']):
            raise ValueError('Unknown optical camera')
        self.bias_count=len(self.bias_index)
        self.scale=np.r_[INITIAL_SCALE,np.tile(BIAS_SCALE,self.bias_count),
                         *(camera.scale for camera in self.cameras.values())]
        self.max=np.r_[np.repeat(np.inf,9+6*self.bias_count),
                       *(camera.limit for camera in self.cameras.values())]

    def split(self,x):
        scaled=x*self.scale
        offset=9+6*self.bias_count
        bias=scaled[9:offset].reshape(self.bias_count,6)
        cameras={}
        for name,camera in self.cameras.items():
            cameras[name]=scaled[offset:offset+len(camera.scale)]
            offset+=len(camera.scale)
        return scaled[:9],bias,cameras

    def outputs(self,x):
        position,bias,parameters=self.split(x)
        fitted=self.fit.integrate(bias,position)
        return fitted,bias,parameters

    def error(self,x):
        trajectory,_,parameters=self.outputs(x)
        errors=[self.fit.anchor_residual(trajectory)]
        for name,camera in self.cameras.items():
            reprojection,valid=camera.residual(self.fit,trajectory,self.fit_rows[name],parameters[name])
            reprojection[~valid] += 1000.
            errors.append(reprojection.ravel()/.22)
        return np.concatenate(errors)

    def minimize(self):
        x=np.zeros(len(self.scale))
        residual=self.error(x)
        loss=residual@residual
        damping=1.e-3
        for iteration in range(35):
            jac=[]
            delta=1.e-4
            for k in range(len(x)):
                perturb=np.zeros_like(x)
                perturb[k]=delta
                jac.append((self.error(x+perturb)-self.error(x-perturb))/(2*delta))
            J=np.column_stack(jac)
            H=J.T@J
            slope=J.T@residual
            accepted=False
            for _ in range(9):
                step=np.linalg.solve(H+damping*np.diag(np.maximum(1.,H.diagonal())),-slope)
                guess=np.clip(x+step,-self.max,self.max)
                trial=self.error(guess)
                cost=trial@trial
                if cost<loss:
                    accepted=True
                    residual,x,loss=trial,guess,cost
                    damping=max(1.e-9,damping*.3)
                    break
                damping*=8.
            if not accepted or np.linalg.norm(step)<1.e-6:
                break
        return x,iteration+1,float(loss)

    def report(self):
        x,iterations,loss=self.minimize()
        fit,bias,parameters=self.outputs(x)
        holdout=self.holdout.integrate(bias,np.zeros(9))
        output={'iterations':iterations,'objective':loss,'bias':dict(zip(self.bias_index,bias.tolist(),strict=True)),
                'cameras':{}}
        for name,cam in self.cameras.items():
            q,p=cam.model(parameters[name])
            errors,support=cam.residual(self.holdout,holdout,self.holdout_rows[name],parameters[name])
            matched=errors[support]
            output['cameras'][name]={'quaternion_xyzw':q.tolist(),'translation_m':p.tolist(),
                'readout_ns':float(parameters[name][6]*1.e9),'skew_ppm':float(parameters[name][7]*1.e6),
                'offset_ns':dict(zip(cam.clocks,(parameters[name][8:]*1.e9).tolist(),strict=True)),
                'validation_rmse_px':float(np.sqrt(np.mean(np.sum(matched**2,axis=1)))) if len(matched) else None,
                'validation_matched':int(np.sum(support))}
        for name,body,trajectory in (('fit',self.fit,fit),('continuation',self.holdout,holdout)):
            stamps=self.spec[name]['pose_query_ticks_ns']
            q,p,v=body.query(trajectory,np.asarray([t-body.origin for t in stamps])*1.e-9)
            output[name]={'trajectory':[
                {'timestamp_ns':timestamp,'position_m':point.tolist(),'quaternion_xyzw':angle.tolist(),
                 'velocity_mps':velocity.tolist()}
                for timestamp,point,angle,velocity in zip(stamps,p,q,v,strict=True)]}
        return output


def solve(spec):
    if len(spec['continuation']['anchors']) != 1:
        raise ValueError('Continuation has only its initial metric prior')
    return Fit(spec).report()
