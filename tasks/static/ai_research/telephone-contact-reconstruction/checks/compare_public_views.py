"""Compare completed meshes with unused public exposures and independently triangulated landmarks."""

import argparse
import csv
import importlib.util
import io
import json
from pathlib import Path
from zipfile import ZipFile

import cv2
import numpy as np
from PIL import Image


def compare(public_builder, mesh_paths):
    spec = importlib.util.spec_from_file_location("telephone_builder", public_builder)
    scene = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scene)
    images, poses = scene.inputs()
    rows = list(csv.DictReader((public_builder.parent / "b-poses.csv").open()))
    reserved = (7, 19, 31, 43, 55, 69)
    with ZipFile(public_builder.parent / "frames.zip") as archive:
        photos = [
            np.array(
                Image.open(io.BytesIO(archive.read(rows[k]["frame"]))).convert("RGB")
            )
            for k in reserved
        ]
    fields = ("tx", "ty", "tz", "qx", "qy", "qz", "qw")
    raw = np.array([[float(rows[k][field]) for field in fields] for k in reserved])
    poses = scene.register(
        images + photos, np.concatenate((poses, scene.poses_from_rows(raw)))
    )[-len(reserved) :]
    sift = cv2.SIFT_create(nfeatures=4000)
    features = [
        sift.detectAndCompute(cv2.cvtColor(im, cv2.COLOR_RGB2GRAY), None)
        for im in photos
    ]
    matcher = cv2.BFMatcher()
    landmarks = [[] for _ in photos]
    for i in range(len(photos)):
        for j in range(i + 1, len(photos)):
            if np.linalg.norm(poses[i, :3, 3] - poses[j, :3, 3]) < 0.13:
                continue
            matches = [
                a
                for a, b in matcher.knnMatch(features[i][1], features[j][1], k=2)
                if a.distance < 0.7 * b.distance
            ]
            if not matches:
                continue
            px = [
                np.array([features[k][0][get(m)].pt for m in matches])
                for k, get in ((i, lambda m: m.queryIdx), (j, lambda m: m.trainIdx))
            ]
            uv = [
                cv2.undistortPoints(x[:, None], scene.K, scene.D).reshape(-1, 2).T
                for x in px
            ]
            homogeneous = cv2.triangulatePoints(
                np.linalg.inv(poses[i])[:3], np.linalg.inv(poses[j])[:3], *uv
            )
            world = (homogeneous[:3] / homogeneous[3]).T
            keep = np.ones(len(world), bool)
            for k, points in zip((i, j), px, strict=True):
                keep &= (
                    np.linalg.norm(scene.world_to_rgb(world, poses[k]) - points, axis=1)
                    < 1.0
                )
            for k, points in zip((i, j), px, strict=True):
                z = (world - poses[k, :3, 3]) @ poses[k, :3, 2]
                valid = keep & (z > 0.4) & (z < 4.5)
                landmarks[k].extend(zip(points[valid], z[valid]))
    output = {}
    for path in mesh_paths:
        with np.load(path) as data:
            mesh = tuple(data[n] for n in scene.FIELDS)
        fractions = []
        agreement = []
        for k, (camera, depth, face) in enumerate(scene.native_surfaces(mesh, poses)):
            ids = face[2::4, 2::4]
            yy, xx = np.where(ids >= 0)
            x = 4 * xx + 2
            y = 4 * yy + 2
            tri = mesh[1][ids[yy, xx]]
            a, b, c = np.moveaxis(camera[tri], 1, 0)
            p = scene.rays(np.stack((x, y), axis=-1), np.eye(4)) * depth[y, x, None]
            ab, ac, ap = b - a, c - a, p - a

            def dot(u, v):
                return np.einsum("ij,ij->i", u, v)

            aa, bb, cc, dd, ee = (
                dot(ab, ab),
                dot(ab, ac),
                dot(ac, ac),
                dot(ab, ap),
                dot(ac, ap),
            )
            det = aa * cc - bb * bb
            inv = np.divide(1, det, out=np.zeros_like(det), where=det > 1e-16)
            wb = (cc * dd - bb * ee) * inv
            wc = (aa * ee - bb * dd) * inv
            color = np.einsum(
                "ni,nic->nc", np.stack((1 - wb - wc, wb, wc), axis=1), mesh[2][tri]
            )
            accurate = np.abs(color - photos[k][y, x]).mean(1) <= 25.5
            fractions.append(float(accurate.sum() / ids.size))
            for uv, z in landmarks[k]:
                u, v = np.rint(uv).astype(int)
                if 0 <= u < 640 and 0 <= v < 480:
                    agreement.append(abs(depth[v, u] - z) <= 0.05)
        output[str(path)] = {
            "rgb_10percent_coverage": float(np.mean(fractions)),
            "rgb_per_view": fractions,
            "landmarks_within_5cm": float(np.mean(agreement)),
            "landmark_ray_count": len(agreement),
        }
    return output


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("public_builder", type=Path)
    p.add_argument("meshes", nargs="+", type=Path)
    args = p.parse_args()
    print(json.dumps(compare(args.public_builder, args.meshes), indent=2))
