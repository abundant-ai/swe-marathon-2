"""Qualify a stereo recording using independent pose and point evidence."""

from math import sqrt
import numpy as np
from .pose import Track,geodesic,integer,name,number,obj,pack,rows,unpack,vector
from .stereo import Rig,decode_matches


def qualify(spec):
    """Check the calibrated time and stereo support before computing survey metrics."""
    rig=Rig.read(spec["rig"])
    calibration=obj(spec["calibration"])
    if calibration["status"]!="ok":
        raise ValueError("successful calibration is required")
    offset=integer(calibration["offset_ticks"],None)
    mount=unpack(calibration["body_from_left"])
    track=Track.read(spec["body"])
    max_gap=integer(spec["max_body_gap_ticks"])
    max_skew=integer(spec["max_stereo_skew_ticks"])
    minimum=integer(spec["min_matches"],1)
    coverage_needed=number(spec["min_coverage"],0)
    if coverage_needed>1:
        raise ValueError("coverage must not exceed one")
    segments=[]
    identities=set()
    for segment in map(obj,rows(spec["segments"])):
        label=name(segment["id"])
        if label in identities:
            raise ValueError("duplicate segment")
        identities.add(label)
        frames=[]
        frame_ids=set()
        t_errors,r_errors,p_errors=[],[],[]
        for raw in map(obj,rows(segment["frames"])):
            identity=name(raw["id"])
            if identity in frame_ids:
                raise ValueError("duplicate frame")
            frame_ids.add(identity)
            left,right=integer(raw["left_tick"]),integer(raw["right_tick"])
            survey=unpack(raw["reference_world_from_left"])
            matches=decode_matches(raw["matches"])
            survey_points={row["id"]:vector(row["reference_world_point_m"],3) for row in raw["matches"]}
            record={"id":identity,"status":"stereo_skew","world_from_left":None,"points":[]}
            frames.append(record)
            if abs(right-left)>max_skew:
                continue
            record["status"]="missing_body"
            at=track.sample(left-offset,max_gap)
            if at is None:
                continue
            record["status"]="poor_stereo"
            reconstructed=[result for m in matches if (result:=rig.match(*m))["status"]=="ok"]
            if len(reconstructed)<minimum:
                continue
            estimate=at@mount
            record["status"]="usable"
            record["world_from_left"]=pack(estimate)
            t_errors.append(float(np.sum((survey[:3,3]-estimate[:3,3])**2)))
            r_errors.append(geodesic(survey[:3,:3].T@estimate[:3,:3])**2)
            for found in reconstructed:
                key=found["id"]
                position=estimate[:3,:3]@np.asarray(found["position_m"])+estimate[:3,3]
                p_errors.append(float(np.sum((position-survey_points[key])**2)))
                record["points"].append({"id":key,"position_m":position.tolist()})
        usable=len(t_errors)
        fraction=usable/len(frames) if frames else 0.0
        valid=usable>0 and fraction>=coverage_needed
        segments.append({
            "id":label,"status":"ok" if valid else "insufficient_coverage","requested_frames":len(frames),
            "usable_frames":usable,"coverage":fraction,"frames":frames,
            "translation_rmse_m":sqrt(sum(t_errors)/usable) if valid else None,
            "rotation_rmse_rad":sqrt(sum(r_errors)/usable) if valid else None,
            "landmark_rmse_m":sqrt(sum(p_errors)/len(p_errors)) if valid else None,
        })
    return {"segments":segments}
