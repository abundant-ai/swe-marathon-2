"""Finite input validation and rigid-pose utilities."""

from dataclasses import dataclass
from math import atan2, acos, isfinite, sin
from bisect import bisect_left
import numpy as np


def obj(value):
    """Require a JSON object."""
    if not isinstance(value,dict):
        raise ValueError("expected an object")
    return value


def rows(value,size=None):
    """Require a JSON array with an optional declared size."""
    if not isinstance(value,list) or (size is not None and len(value)!=size):
        raise ValueError("invalid list or size")
    return value


def number(value,minimum=None):
    """Require a finite JSON number, optionally bounded below."""
    if type(value) not in (int,float) or not isfinite(value) or (minimum is not None and value<minimum):
        raise ValueError("invalid finite number")
    return float(value)


def positive(value):
    """Require a positive finite magnitude."""
    result=number(value)
    if result<=0:
        raise ValueError("expected a positive number")
    return result


def integer(value,minimum=0):
    """Require an integral tick distinct from a boolean."""
    if type(value) is not int or (minimum is not None and value<minimum):
        raise ValueError("invalid tick")
    return value


def name(value):
    """Require a nonempty wire identity."""
    if not isinstance(value,str) or not value:
        raise ValueError("invalid ID")
    return value


def vector(value,size):
    """Decode a fixed-length numeric vector."""
    return np.array([number(item) for item in rows(value,size)])


def normalize(q):
    """Normalize a finite quaternion stably for very large or small scalars."""
    scale=np.max(np.abs(q))
    if scale==0:
        raise ValueError("zero quaternion")
    q=q/scale
    return q/np.linalg.norm(q)


def rotation(q):
    """Convert a scalar-last unit quaternion to a proper 3D rotation."""
    x,y,z,w=normalize(q)
    return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                     [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                     [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])


def quaternion(R):
    """Recover a scalar-last quaternion, including rotations near a half turn."""
    trace=R.trace()
    chosen=int(np.argmax([*R.diagonal(),trace]))
    if chosen==3:
        q=[R[2,1]-R[1,2],R[0,2]-R[2,0],R[1,0]-R[0,1],1+trace]
    else:
        i,j,k=chosen,(chosen+1)%3,(chosen+2)%3
        q=[0.]*4
        q[i]=1+R[i,i]-R[j,j]-R[k,k]
        q[j]=R[j,i]+R[i,j]
        q[k]=R[k,i]+R[i,k]
        q[3]=R[k,j]-R[j,k]
    q=normalize(np.array(q))
    return -q if q[3]<0 else q


def rigid(t,R):
    """Assemble a homogeneous transform from Cartesian and rotational components."""
    value=np.eye(4)
    value[:3,:3],value[:3,3]=R,t
    return value


def unpack(raw):
    """Read a pose prescribed by Cartesian translation and quaternion."""
    data=obj(raw)
    return rigid(vector(data["translation_m"],3),rotation(vector(data["quaternion_xyzw"],4)))


def pack(value):
    """Write the public rigid-pose representation."""
    return {"translation_m":value[:3,3].tolist(),"quaternion_xyzw":quaternion(value[:3,:3]).tolist()}


def inverse(T):
    """Invert a rigid transform without a general matrix solve."""
    R=T[:3,:3].T
    return rigid(-R@T[:3,3],R)


def geodesic(R):
    """Compute the shortest relative orientation error in radians."""
    q=quaternion(R)
    return 2*atan2(np.linalg.norm(q[:3]),q[3])


def axis_angle(R):
    """Return the principal rotation vector, with a stable zero-angle branch."""
    q=quaternion(R)
    length=np.linalg.norm(q[:3])
    if length<1e-12:
        return 2*q[:3]
    return q[:3]*(2*atan2(length,q[3])/length)


def slerp(a,b,t):
    """Interpolate unit quaternions along the shortest rotation arc."""
    dot=float(a@b)
    if dot<0:
        b,dot=-b,-dot
    if dot>1-1e-12:
        return normalize((1-t)*a+t*b)
    angle=acos(max(-1.,min(1.,dot)))
    return (sin((1-t)*angle)*a+sin(t*angle)*b)/sin(angle)


@dataclass(frozen=True)
class Track:
    """A pose sequence with exact integer acquisition ticks."""
    ticks: tuple
    values: dict

    @classmethod
    def read(cls,value):
        """Read pose records and reject duplicate acquisitions."""
        poses={}
        for reading in map(obj,rows(value)):
            tick=integer(reading["tick"])
            if tick in poses:
                raise ValueError("duplicate pose tick")
            poses[tick]=unpack(reading)
        return cls(tuple(sorted(poses)),poses)

    def sample(self,tick,gap):
        """Return an exact or bounded-interpolated pose without extrapolation."""
        if tick in self.values:
            return self.values[tick]
        index=bisect_left(self.ticks,tick)
        if index==0 or index==len(self.ticks):
            return None
        lower,upper=self.ticks[index-1:index+1]
        if max(tick-lower,upper-tick)>gap:
            return None
        f=(tick-lower)/(upper-lower)
        a,b=self.values[lower],self.values[upper]
        q=slerp(quaternion(a[:3,:3]),quaternion(b[:3,:3]),f)
        return rigid((1-f)*a[:3,3]+f*b[:3,3],rotation(q))
