"""Relative-motion hand-eye and integer camera-clock calibration."""
from math import hypot, sqrt
import numpy as np
from .pose import Track,axis_angle,geodesic,integer,inverse,number,pack,rigid,obj,rows


def relative_pair(tracks,offset,lag):
    """Build body and camera relative motions using exact stamp support."""
    body,left=tracks
    for t in body.ticks:
        if t+lag in body.values and t+offset in left.values and t+offset+lag in left.values:
            yield (inverse(body.values[t])@body.values[t+lag],
                   inverse(left.values[t+offset])@left.values[t+offset+lag])


def fit(motions):
    """Solve AX=XB and return the fit residuals, or report missing excitation."""
    A,B=(np.stack(track) for track in zip(*motions))
    a=np.stack([axis_angle(R) for R in A[:,:3,:3]])
    b=np.stack([axis_angle(R) for R in B[:,:3,:3]])
    if np.linalg.svd(a,compute_uv=False)[1]<0.001:
        return None
    U,_,V=np.linalg.svd(a.T@b)
    U[:,-1]*=np.linalg.det(U@V)
    R=U@V
    left=(A[:,:3,:3]-np.eye(3)).reshape(-1,3)
    right=(B[:,:3,3]@R.T-A[:,:3,3]).reshape(-1)
    translation=np.linalg.lstsq(left,right,rcond=None)[0]
    X=rigid(translation,R)
    xa,xb=A@X,X@B
    t_rmse=sqrt(float(np.mean(np.sum((xa[:,:3,3]-xb[:,:3,3])**2,axis=1))))
    r_rmse=sqrt(float(np.mean([geodesic(a.T@b)**2 for a,b in zip(xa[:,:3,:3],xb[:,:3,:3],strict=True)])))
    return X,t_rmse,r_rmse


def calibrate(spec):
    """Search the declared clock grid, comparing only sufficiently excited pairs."""
    sessions=[(Track.read(row["body"]),Track.read(row["left"])) for row in map(obj,rows(spec["sessions"]))]
    offsets=[integer(item,None) for item in rows(spec["offset_candidates"])]
    if not sessions or not offsets or len(set(offsets))!=len(offsets):
        raise ValueError("missing captures or invalid offset candidates")
    lag=integer(spec["lag_ticks"],1)
    minimum=integer(spec["min_pairs"],3)
    ambiguity=number(spec["ambiguity_cost"],0)
    report={"status":"insufficient_overlap","pair_count":0,"offset_ticks":None,"body_from_left":None,
            "translation_rmse_m":None,"rotation_rmse_rad":None}
    valid=[]
    for offset in offsets:
        motions=[motion for capture in sessions for motion in relative_pair(capture,offset,lag)]
        report["pair_count"]=max(report["pair_count"],len(motions))
        if len(motions)<minimum:
            continue
        report["status"]="insufficient_motion"
        found=fit(motions)
        if found is not None:
            X,t,r=found
            valid.append((hypot(t,r),offset,len(motions),X,t,r))
    if not valid:
        return report
    valid.sort(key=lambda item:item[:2])
    if len(valid)>1 and valid[1][0]-valid[0][0]<=ambiguity:
        return report|{"status":"ambiguous"}
    _,offset,count,X,t,r=valid[0]
    return {"status":"ok","pair_count":count,"offset_ticks":offset,"body_from_left":pack(X),
            "translation_rmse_m":t,"rotation_rmse_rad":r}
