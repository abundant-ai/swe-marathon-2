"""Calibrated two-camera ray geometry in an explicit left-camera frame."""

from dataclasses import dataclass
from math import atan2
import numpy as np

from .pose import inverse,name,number,obj,positive,rows,unpack,vector


@dataclass(frozen=True)
class Camera:
    """Undistorted perspective intrinsics for one stereo image."""
    focal: np.ndarray
    centre: np.ndarray

    @classmethod
    def read(cls,value):
        """Read horizontal and vertical pinhole calibration."""
        data=obj(value)
        return cls(np.array([positive(data["fx"]),positive(data["fy"])]),
                   np.array([number(data["cx"]),number(data["cy"])]))

    def ray(self,pixel):
        """Backproject a pixel to a forward, unit camera ray."""
        point=np.array([*((pixel-self.centre)/self.focal),1.])
        return point/np.linalg.norm(point)

    def pixel(self,point):
        """Project a positive-depth camera point back to image coordinates."""
        return point[:2]/point[2]*self.focal+self.centre


@dataclass(frozen=True)
class Rig:
    """Stereo calibration and the acceptance tolerances for tracking."""
    left: Camera
    right: Camera
    left_from_right: np.ndarray
    min_parallax: float
    max_error: float

    @classmethod
    def read(cls,value):
        """Read the calibrated rig and its geometric quality thresholds."""
        data=obj(value)
        return cls(Camera.read(data["left"]),Camera.read(data["right"]),unpack(data["left_from_right"]),
                   positive(data["min_parallax_rad"]),number(data["max_reprojection_px"],0))

    def match(self,identity,left_pixel,right_pixel):
        """Reconstruct one track and report its first failing physical test."""
        transform=self.left_from_right
        left=self.left.ray(left_pixel)
        right=transform[:3,:3]@self.right.ray(right_pixel)
        origin=transform[:3,3]
        result={"id":identity,"status":"low_parallax","position_m":None,"reprojection_px":None}
        separation=np.linalg.norm(np.cross(left,right))
        parallax=atan2(separation,float(left@right))
        if separation<1e-14 or parallax < self.min_parallax:
            return result
        s,t=np.linalg.lstsq(np.column_stack((left,-right)),origin,rcond=None)[0]
        point=(s*left+origin+t*right)*0.5
        in_right=(inverse(transform)@np.array([*point,1]))[:3]
        if point[2]<=0 or in_right[2]<=0:
            return result|{"status":"behind_camera"}
        error=max(np.linalg.norm(self.left.pixel(point)-left_pixel),np.linalg.norm(self.right.pixel(in_right)-right_pixel))
        if error>self.max_error:
            return result|{"status":"reprojection_error","reprojection_px":float(error)}
        return result|{"status":"ok","position_m":point.tolist(),"reprojection_px":float(error)}


def decode_matches(value):
    """Read unique feature identities and their calibrated pixel coordinates."""
    seen=set()
    result=[]
    for match in map(obj,rows(value)):
        identity=name(match["id"])
        if identity in seen:
            raise ValueError("duplicate match ID")
        seen.add(identity)
        result.append((identity,vector(match["left_uv"],2),vector(match["right_uv"],2)))
    return result


def triangulate(spec):
    """Report each accepted or rejected pair in the acquisition's given order."""
    rig=Rig.read(spec["rig"])
    return {"matches":[rig.match(*match) for match in decode_matches(spec["matches"])]}
