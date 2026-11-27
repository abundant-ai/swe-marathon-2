"""Project the four labeled contact surfaces on withheld native Freiburg 2 RGB photographs."""
from __future__ import annotations

import ctypes
import subprocess
import tempfile
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT.parent / 'functional-parts'),str(ROOT.parent / 'dense-functional-parts')]
from score import Reference, aggregate, checked_labeled, iou, mask, metrics, native_labels, project, Rasterizer, reliable_iou
from whole_scene import color_at_samples

def native_surfaces(mesh, poses):
    """Find depth and nearest face at every native integer pixel center under the B lens."""
    with tempfile.TemporaryDirectory() as tmp:
        dll=Path(tmp)/'raster.so'
        subprocess.run(['cc','-O2','-std=c99','-shared','-fPIC',str(ROOT/'raster.c'),'-lm','-o',str(dll)],check=True)
        render=ctypes.CDLL(str(dll)).raster
        double=np.ctypeslib.ndpointer(np.float64,flags='C_CONTIGUOUS')
        render.argtypes=[double,ctypes.c_size_t,double,np.ctypeslib.ndpointer(np.int32,flags='C_CONTIGUOUS')]
        render.restype=None
        for pose in poses:
            camera=(mesh[0]-pose[:3,3]) @ pose[:3,:3]
            tri=np.ascontiguousarray(camera[mesh[1]],np.float64)
            depth=np.full((480,640),np.inf)
            face=np.full((480,640),-1,np.int32)
            render(tri,len(tri),depth,face)
            yield camera,depth,face


def appearance(mesh,camera,depth,face,rgb,sensor):
    """Use the same native optical rays for geometry and for triangle color interpolation."""
    from telephone_optics import rays
    y,x=np.where(face>=0)
    tri=mesh[1][face[y,x]]
    a,b,c=np.moveaxis(camera[tri],1,0)
    p=rays(np.column_stack((4*x+2,4*y+2)),np.eye(4))*depth[y,x,None]
    first=b-a;second=c-a;offset=p-a
    def dot(u,v):return np.einsum('ij,ij->i',u,v)
    aa,ab,bb,ap,bp=dot(first,first),dot(first,second),dot(second,second),dot(first,offset),dot(second,offset)
    det=aa*bb-ab*ab
    inv=np.divide(1,det,out=np.zeros_like(det),where=det>1e-20)
    wb=(bb*ap-ab*bp)*inv;wc=(aa*bp-ab*ap)*inv
    weights=np.clip(np.stack((1-wb-wc,wb,wc),axis=1),0,1)
    weights/=np.maximum(weights.sum(1,keepdims=True),1e-15)
    predicted=np.zeros(rgb.shape,float)
    predicted[y,x]=np.einsum('ni,nic->nc',weights,mesh[2][tri])
    known=sensor>0
    near=np.abs(sensor-depth)<=.05
    accurate=np.abs(predicted-rgb.astype(float)).mean(axis=2)<=25.5
    return {'depth_5cm_coverage':float(near[known].mean()),'rgbd_5cm_10percent_coverage':float((near&accurate)[known].mean())}


def score(mesh):
    """Score functional surfaces, registered object geometry and whole-room color and depth."""
    scene = checked_labeled(mesh[:4])
    groups = np.asarray(mesh[4])
    parent = np.array([0,1,1,2,3])
    if groups.shape != scene[3].shape or not np.issubdtype(groups.dtype,np.integer) or not np.isin(groups,range(5)).all():
        raise ValueError('Expected one integer functional part ID 0..4 per triangle')
    assigned = groups != 0
    if np.any(parent[groups[assigned]] != scene[3][assigned]):
        raise ValueError('Functional face is assigned to a different object')
    ref = Reference.load(ROOT.parent / 'precision-pilot/data/clutter/data', 'b')
    with np.load(ROOT/'optical-poses.npz') as ar: poses=ar['poses']
    with np.load(ROOT/'scoring-rgb.npz') as ar: rgb=ar['rgb']
    scene_views=[];z_views=[];obj_views=[]
    raw = {i:[] for i in range(1,5)}
    optical = {i:[] for i in range(1,5)}
    contact_views = []
    picking = (ROOT / "contact-picking.enabled").exists()
    if picking:
        from contact_queries import count_queries, summarize_counts
    details = []
    for view,(camera,zbuffer,face) in enumerate(native_surfaces(scene,poses)):
        valid=face>=0
        predicted=np.zeros(face.shape,np.uint8)
        predicted[valid]=groups[face[valid]]
        z=zbuffer[2::4,2::4];f=face[2::4,2::4];obj=np.zeros(f.shape,np.uint8)
        obj[f>=0]=scene[3][f[f>=0]]
        z_views.append(z);obj_views.append(obj)
        scene_views.append(appearance(scene,camera,z,f,rgb[view],ref.depth[view]))
        outlines = json.loads((ROOT / f'h{view}.json').read_text())
        record = {}
        contact_counts = {}
        for name, rings in outlines.items():
            idx = int(name)
            truth = mask(rings)
            if picking:
                contact_counts[idx] = count_queries(idx, truth, predicted[2::4,2::4], z, ref.depth[view], ref.labels[view])
            selected = predicted == idx
            a, b = iou(selected,truth), reliable_iou(selected,truth)
            raw[idx].append(a)
            optical[idx].append(b)
            record[name] = {'raw_iou':a, 'reliable_iou':b, 'reference_pixels':int(truth.sum()),
                            'predicted_pixels':int(selected.sum())}
        details.append(record)
        if picking:
            contact_views.append(contact_counts)
    optical_score, parts = aggregate(optical)
    surfaces=metrics(ref,np.stack(obj_views),np.stack(z_views))
    whole={**{k:float(np.mean([row[k] for row in scene_views])) for k in scene_views[0]},'views':scene_views}
    coarse = surfaces['macro']['depth_f1_3cm']
    color = whole['rgbd_5cm_10percent_coverage']
    report = {'reward':min(coarse,optical_score,color), 'part_success':optical_score,
            'part_success_by_id':parts,'raw_part_success':aggregate(raw)[0],
            'object_depth_f1':coarse,'objects':surfaces['objects'],'whole_scene':whole,'views':details}

    if picking:
        report["contact_picking"] = summarize_counts(contact_views)
        report["reward"] = min(report["reward"], report["contact_picking"]["macro_f1"])
    return report
