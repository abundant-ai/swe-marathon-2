"""Independent pixel projections, known clock perturbations and real mocap playback."""

import csv
from math import acos,cos,sin,sqrt
import numpy as np


def rotation(axis,angle):
    """Generate an independent Rodrigues rotation around a unit axis."""
    u=np.asarray(axis,dtype=float)
    u/=np.linalg.norm(u)
    x,y,z=u
    skew=np.array([[0,-z,y],[z,0,-x],[-y,x,0]])
    return np.eye(3)*cos(angle)+(1-cos(angle))*np.outer(u,u)+sin(angle)*skew


def pose(angle,translation,axis=(0,0,1)):
    """Build a planted proper rigid transform."""
    T=np.eye(4)
    T[:3,:3]=rotation(axis,angle)
    T[:3,3]=translation
    return T


def encode(T):
    """Create a quaternion via a symmetric eigenproblem independent of candidate helpers."""
    R=T[:3,:3]
    xx,xy,xz=R[0]
    yx,yy,yz=R[1]
    zx,zy,zz=R[2]
    K=np.array([[xx-yy-zz,yx+xy,zx+xz,yz-zy],
                [yx+xy,yy-xx-zz,zy+yz,zx-xz],
                [zx+xz,zy+yz,zz-xx-yy,xy-yx],
                [yz-zy,zx-xz,xy-yx,xx+yy+zz]])
    _,vectors=np.linalg.eigh(K)
    q=vectors[:,-1].copy()
    q[:3]*=-1
    return {"translation_m":T[:3,3].tolist(),"quaternion_xyzw":q.tolist()}


def decode(p):
    """Decode a report pose for comparison with planted world transforms."""
    xyz=np.asarray(p["quaternion_xyzw"],dtype=float)
    q=xyz/np.linalg.norm(xyz)
    x,y,z,w=q
    T=np.eye(4)
    T[:3,:3]=np.array([[1-2*y*y-2*z*z,2*(x*y-w*z),2*(x*z+w*y)],
                       [2*(x*y+w*z),1-2*x*x-2*z*z,2*(y*z-w*x)],
                       [2*(x*z-w*y),2*(y*z+w*x),1-2*x*x-2*y*y]])
    T[:3,3]=p["translation_m"]
    return T


def same(value,wanted,tol=3e-7):
    """Compare finite numeric structures at laboratory precision."""
    try:
        a,b=np.asarray(value),np.asarray(wanted)
        return a.dtype.kind in "fiu" and a.shape==b.shape and bool(np.allclose(a,b,atol=tol,rtol=tol))
    except (TypeError,ValueError,OverflowError):
        return False


def same_pose(actual,expected):
    """Compare the physical transform, allowing either equivalent quaternion sign."""
    if not isinstance(actual,dict):
        return False
    try:
        return same(decode(actual),expected,2e-6)
    except (ValueError,TypeError,KeyError,IndexError,OverflowError):
        return False


def rig_model():
    """Define a toed-in, asymmetric stereo rig with independently known camera extrinsics."""
    transform=pose(-0.11,[0.19,0.017,-0.005],[0.13,1,0.22])
    rig={"left":{"fx":523.4,"fy":517.5,"cx":302.1,"cy":213.45},
         "right":{"fx":611.3,"fy":591.2,"cx":318.1,"cy":246.7},
         "left_from_right":encode(transform),"min_parallax_rad":0.005,"max_reprojection_px":1.2}
    return rig,transform


def match(rig,T_left_right,identity,known):
    """Project a supplied left-frame physical point into camera pixel observations."""
    right=T_left_right[:3,:3].T@(known-T_left_right[:3,3])
    def pixels(camera,point):
        x,y,z=point
        return [camera["cx"]+camera["fx"]*x/z,camera["cy"]+camera["fy"]*y/z]
    return {"id":identity,"left_uv":pixels(rig["left"],known),"right_uv":pixels(rig["right"],right)}


def stereo_check(run):
    """Check independent projections, weak rays, points behind the camera and bad pairing."""
    rig,T=rig_model()
    rng=np.random.default_rng(61)
    good=[np.array([*rng.uniform(-0.85,.9,2),depth]) for depth in (0.65,0.82,1.4,2.0,2.6,3.8)]
    samples=[match(rig,T,f"good-{i}",point) for i,point in enumerate(good)]
    distant=match(rig,T,"distant",np.array([.3,-.1,1224.0]))
    behind=match(rig,T,"behind",np.array([.22,-.02,-1.8]))
    mismatch=match(rig,T,"mismatched",np.array([.33,-.18,1.4]))
    mismatch["right_uv"][1]+=41.2
    result=run("triangulate",{"rig":rig,"matches":samples+[distant,behind,mismatch]})
    output=result.get("matches")
    correctly_shaped=(isinstance(output,list) and len(output)==9 and all(isinstance(item,dict) for item in output))
    keep=correctly_shaped and all(row.get("id")==f"good-{i}" and row.get("status")=="ok"
                and same(row.get("position_m"),point) and same(row.get("reprojection_px"),0.0)
                for i,(row,point) in enumerate(zip(output[:6],good,strict=True)))
    rejection=correctly_shaped and [row.get("status") for row in output[6:]]==[
        "low_parallax","behind_camera","reprojection_error"] and all(
            "position_m" in item and item["position_m"] is None for item in output[6:])
    return {"native_camera_coordinates_from_independent_projection":keep,
            "physical_stereo_rejections":keep and rejection}


def path_at(index,mode="spatial"):
    """Create noncommuting, time-varying rotations and independent translations."""
    i=float(index)
    if mode=="axial":
        return pose(.09*i,[.23*sin(.36*i),.24*cos(.18*i),.03*i])
    X=pose(.36*sin(.49*i)+.07*i,[.31*sin(i*.45),.55*cos(i*.38),0.025*i],[.3,.5,1])
    return X@pose(.43*cos(i*.38)-.04*i,[0.03*i,.12*sin(i*.71),.19*cos(i*.56)],[-.8,0.3,.1])


def session(origin,mount,offset,mode="spatial"):
    """Encode camera and body tracks with separate sign, clock and world conventions."""
    body_origin=pose(.67,[.3,1.2,-.7],[1,1,-1])
    camera_world=pose(-1.52,[-5,3,1.8],[.5,-.4,.2])
    body=[]; camera=[]
    for i in range(19):
        tick=origin+i*3
        movement=path_at(i if mode!="periodic" else i%4,"axial" if mode=="axial" else "spatial")
        T=body_origin@movement
        raw=encode(T)
        if i%2:
            raw["quaternion_xyzw"]=[-q for q in raw["quaternion_xyzw"]]
        body.append({"tick":tick,**raw})
        camera.append({"tick":tick+offset,**encode(camera_world@T@mount)})
    return {"body":body[::2]+body[1::2],"left":camera[::-1]}


def planted(offset,mount):
    """Form a two-session clock-grid problem using exact support."""
    return {"sessions":[session(10**16+31,mount,offset),session(900,mount,offset)],
            "offset_candidates":[offset+6,offset-3,offset,offset+3],"lag_ticks":6,
            "min_pairs":15,"ambiguity_cost":1e-8}


def matching_calibration(actual,offset,mount):
    """Verify real mount direction and both absolute residuals."""
    return (actual.get("status")=="ok" and type(actual.get("offset_ticks")) is int and actual["offset_ticks"]==offset
            and type(actual.get("pair_count")) is int and actual["pair_count"]>=25
            and same_pose(actual.get("body_from_left"),mount)
            and same(actual.get("translation_rmse_m"),0.0,2e-6) and same(actual.get("rotation_rmse_rad"),0.0,2e-6))


def calibration_check(run):
    """Check signed clock and near-half-turn mount recovery plus deterministic abstention."""
    first=pose(0.87,[.31,-.24,.18],[.48,-1,.35])
    other=pose(2.87,[-.17,.39,.23],[-.32,.14,.7])
    primary=run("calibrate",planted(-10,first))
    second=run("calibrate",planted(7,other))
    passed=matching_calibration(primary,-10,first)
    alternate=matching_calibration(second,7,other)
    no_exc=run("calibrate",{"sessions":[session(120,first,-10,"axial")],"offset_candidates":[-10],
                           "lag_ticks":6,"min_pairs":12,"ambiguity_cost":1e-8})
    repeat=run("calibrate",{"sessions":[session(120,first,-10,"periodic")],"offset_candidates":[-10,2],
                           "lag_ticks":6,"min_pairs":12,"ambiguity_cost":1e-8})
    no_overlap=run("calibrate",planted(-10,first)|{"lag_ticks":139})
    result={"signed_clock_and_noncommuting_mount":passed,"near_half_turn_and_opposite_offset":alternate,
            "exact_tick_overlap_and_axis_observability":(passed or alternate)
                and no_exc.get("status")=="insufficient_motion" and no_overlap.get("status")=="insufficient_overlap",
            "periodic_motion_clock_ambiguity":(passed or alternate) and repeat.get("status")=="ambiguous"}
    return result,primary,first


def read_mocap(path):
    """Read the attributed TUM VI pose excerpts using the source's scalar-last quaternions."""
    with (path/"tumvi-room1-poses.csv").open(newline="",encoding="utf-8") as stream:
        raw=list(csv.DictReader(stream))
    if len(raw)!=80:
        raise RuntimeError("incomplete TUM VI pose fixture")
    return [decode({"translation_m":[float(row[key]) for key in ("tx","ty","tz")],
                    "quaternion_xyzw":[float(row[key]) for key in ("qx","qy","qz","qw")]}) for row in raw]


def midpoint(a,b):
    """Produce the expected midpoint by normalizing the sum of consistently signed quaternions."""
    qa=np.array(encode(a)["quaternion_xyzw"])
    qb=np.array(encode(b)["quaternion_xyzw"])
    q=qa+qb if qa@qb>=0 else qa-qb
    return decode({"translation_m":(a[:3,3]+b[:3,3])/2,"quaternion_xyzw":q})


def pose_distance(a,b):
    """Measure the geodesic angle on the planted physical orientation."""
    return acos(max(-1.,min(1.,(np.trace(a[:3,:3].T@b[:3,:3])-1)/2)))


def heldout_case(data,calibration,mount,begin):
    """Project tracks over a measured trajectory and plant independent review faults."""
    mocap=read_mocap(data)[begin:begin+12]
    rig,T=rig_model()
    epoch=10**16+177
    offset=-10
    supported=(0,1,3,4,7,8)
    records=[{"tick":epoch+4*i,**encode(mocap[i])} for i in supported]
    expected={}
    def frame(identity,index,status):
        corrected=epoch+4*index
        outside=index>=len(mocap)
        ground=midpoint(mocap[1],mocap[3]) if index==2 else mocap[0 if outside else index]
        estimate=ground@mount
        surveyed=estimate@pose(0.062+0.004*index,[.021,-.03,.011])
        matches=[]
        points=[]
        for i,p in enumerate(([.22,.14,1.9],[-.58,.33,3.1],[.75,-.62,4.0])):
            point=np.asarray(p) if status!="poor_stereo" else np.array([*p[:2],355.])
            image=match(rig,T,f"landmark-{i}",point)
            world=(estimate@np.array([*point,1.0]))[:3]
            delta=np.array([-.021,.027+.01*i,.013])
            image["reference_world_point_m"]=(world+delta).tolist()
            matches.append(image)
            points.append({"id":image["id"],"truth":world,"error_sq":float(delta@delta)})
        expected[identity]={"status":status,"T":estimate,"survey":surveyed,"points":points}
        return {"id":identity,"left_tick":corrected+offset,"right_tick":corrected+offset+(4 if status=="stereo_skew" else 1),
                "reference_world_from_left":encode(surveyed),"matches":matches}
    segments=[
        {"id":"qualified","frames":[frame("exact-a",0,"usable"),frame("interpolated",2,"usable"),
                                    frame("skew",3,"stereo_skew"),frame("exact-b",4,"usable"),
                                    frame("missing",16,"missing_body"),frame("exact-c",8,"usable")]},
        {"id":"insufficient","frames":[frame("partial",7,"usable"),frame("weak",4,"poor_stereo"),
                                       frame("late",23,"missing_body")]},
    ]
    return {"rig":rig,"calibration":calibration,"body":records[::-1],"max_body_gap_ticks":4,
            "max_stereo_skew_ticks":1,"min_matches":2,"min_coverage":0.60,"segments":segments},expected


def agrees(report,spec,expected):
    """Evaluate the output independently against surveyed poses, landmarks and support."""
    segments=report.get("segments")
    if not isinstance(segments,list) or len(segments)!=2:
        return False
    for out,query in zip(segments,spec["segments"],strict=True):
        if not isinstance(out,dict) or out.get("id")!=query["id"]:
            return False
        shown=out.get("frames")
        if not isinstance(shown,list) or len(shown)!=len(query["frames"]):
            return False
        t,r,p=[],[],[]
        for row,frame in zip(shown,query["frames"],strict=True):
            truth=expected[frame["id"]]
            if not isinstance(row,dict) or row.get("id")!=frame["id"] or row.get("status")!=truth["status"]:
                return False
            if truth["status"]!="usable":
                if "world_from_left" not in row or row["world_from_left"] is not None or row.get("points")!=[]:
                    return False
                continue
            points=row.get("points")
            if not same_pose(row.get("world_from_left"),truth["T"]) or not isinstance(points,list) or len(points)!=3:
                return False
            for actual,known in zip(points,truth["points"],strict=True):
                if not isinstance(actual,dict) or actual.get("id")!=known["id"] or not same(actual.get("position_m"),known["truth"]):
                    return False
                p.append(known["error_sq"])
            diff=truth["T"][:3,3]-truth["survey"][:3,3]
            t.append(float(diff@diff))
            r.append(pose_distance(truth["T"],truth["survey"])**2)
        covered=len(t)/len(shown)
        status="ok" if covered>=spec["min_coverage"] else "insufficient_coverage"
        if (out.get("status")!=status or type(out.get("requested_frames")) is not int
                or out["requested_frames"]!=len(shown) or type(out.get("usable_frames")) is not int
                or out["usable_frames"]!=len(t) or not same(out.get("coverage"),covered)):
            return False
        for metric,values in zip(("translation_rmse_m","rotation_rmse_rad","landmark_rmse_m"),(t,r,p),strict=True):
            if status=="ok":
                if not same(out.get(metric),sqrt(sum(values)/len(values)),2e-6):
                    return False
            elif metric not in out or out[metric] is not None:
                return False
    return True


def checks(run,level,data):
    """Grade geometry, calibration, and recording qualification cumulatively."""
    result=stereo_check(run)
    if level>=2:
        tests,fit,mount=calibration_check(run)
        result.update(tests)
    if level>=3:
        known={"status":"ok","offset_ticks":-10,"pair_count":34,"body_from_left":encode(mount),
               "translation_rmse_m":0.,"rotation_rmse_rad":0.}
        spec,expected=heldout_case(data,known,mount,9)
        changed,other=heldout_case(data,known,mount,40)
        fit_replay=run("qualify",spec|{"calibration":fit}) if fit.get("status")=="ok" else {}
        outcome=run("qualify",spec)
        result["survey_error_and_support_on_real_mocap"]=agrees(outcome,spec,expected)
        result["independent_heldout_recording"]=agrees(run("qualify",changed),changed,other)
        result["actual_fit_used_for_validation"]=agrees(fit_replay,spec,expected)
        bad=spec|{"body":spec["body"]+[spec["body"][0]]}
        result["malformed_input_keeps_existing_output"]=result["survey_error_and_support_on_real_mocap"] and run(
            "qualify",bad,invalid=True).get("atomic",False)
    return result
