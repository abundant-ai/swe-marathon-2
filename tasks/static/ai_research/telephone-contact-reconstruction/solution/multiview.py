"""Fit the receiver, handle and vertex appearance from multiple public RGB views."""

import csv
import io
import json
import sys
from pathlib import Path
from zipfile import ZipFile

import cv2
import numpy as np
from PIL import Image
from scipy.interpolate import CubicSpline
from scipy.ndimage import map_coordinates
from scipy.optimize import least_squares
from scipy.sparse import coo_matrix, eye
from scipy.sparse.linalg import spsolve
from scipy.spatial import Delaunay, cKDTree
from scipy.spatial.transform import Rotation

from optics import (
    K1,
    K2,
    K3,
    P1,
    P2,
    C,
    F,
    poses_from_rows,
    rays,
    triangulate,
    world_to_rgb,
)
from visibility import mask, native_surfaces

PUBLIC = Path(__file__).resolve().parent
FIELDS = ("vertices", "faces", "colors", "face_ids", "part_ids")
K = np.array([[F[0], 0, C[0]], [0, F[1], C[1]], [0, 0, 1.0]])
D = np.array([K1, K2, P1, P2, K3])
cv2.setNumThreads(2)


def inputs(include_dense=True):
    with Image.open(PUBLIC / "observation.png") as f:
        images = [
            np.array(
                f.crop(
                    (
                        640 * (k % 2),
                        502 * (k // 2),
                        640 * (k % 2) + 640,
                        502 * (k // 2) + 480,
                    )
                )
            )
            for k in range(6)
        ]
    poses = poses_from_rows(np.loadtxt(PUBLIC / "b-keyframes.txt"))
    if not include_dense:
        return images, poses
    dense = PUBLIC
    with (dense / "b-poses.csv").open() as f:
        rows = list(csv.DictReader(f))
    indices = [0, 12, 24, 36, 48, 60, 66]
    with ZipFile(dense / "frames.zip") as ar:
        for k in indices:
            images.append(
                np.array(
                    Image.open(io.BytesIO(ar.read(rows[k]["frame"]))).convert("RGB")
                )
            )
    dense_poses = poses_from_rows(
        np.array(
            [
                [
                    float(rows[k][key])
                    for key in ("tx", "ty", "tz", "qx", "qy", "qz", "qw")
                ]
                for k in indices
            ]
        )
    )
    return images, np.concatenate([poses, dense_poses])


def register(images, poses):
    """Triangulate broad-baseline texture tracks and refine other public RGB poses by PnP."""
    cv2.setRNGSeed(204)
    sift = cv2.SIFT_create(nfeatures=4200)
    matcher = cv2.BFMatcher()
    feats = [
        sift.detectAndCompute(cv2.cvtColor(im, cv2.COLOR_RGB2GRAY), None)
        for im in images
    ]
    kp = [np.array([p.pt for p in k]) for k, _ in feats]

    def links(i, j):
        return {
            a.queryIdx: a.trainIdx
            for a, b in matcher.knnMatch(feats[i][1], feats[j][1], k=2)
            if a.distance < 0.79 * b.distance
        }

    matches = links(1, 4)
    ind = np.array(list(matches))
    px0 = kp[1][ind]
    px1 = kp[4][list(matches.values())]
    uv0 = cv2.undistortPoints(px0.reshape(-1, 1, 2), K, D).reshape(-1, 2)
    uv1 = cv2.undistortPoints(px1.reshape(-1, 1, 2), K, D).reshape(-1, 2)
    X = cv2.triangulatePoints(
        np.linalg.inv(poses[1])[:3], np.linalg.inv(poses[4])[:3], uv0.T, uv1.T
    )
    X = (X[:3] / X[3]).T
    keep = (
        (np.linalg.norm(world_to_rgb(X, poses[1]) - px0, axis=1) < 2.5)
        & (np.linalg.norm(world_to_rgb(X, poses[4]) - px1, axis=1) < 2.5)
        & (X[:, 2] > 0.25)
    )
    info = dict(zip(ind[keep], X[keep]))
    out = poses.copy()
    for i in [k for k in range(len(images)) if k not in (1, 4)]:
        link = links(1, i)
        a = list(set(link) & info.keys())
        if len(a) < 10:
            continue
        cam = np.array([info[x] for x in a])
        uv = kp[i][[link[x] for x in a]]
        ok, r, t, ins = cv2.solvePnPRansac(
            cam, uv, K, D, iterationsCount=1000, reprojectionError=3.5, confidence=0.999
        )
        if not ok or len(ins) < 14:
            continue
        r, t = cv2.solvePnPRefineLM(cam[ins[:, 0]], uv[ins[:, 0]], K, D, r, t)
        inv = np.eye(4)
        inv[:3, :3] = Rotation.from_rotvec(r.ravel()).as_matrix()
        inv[:3, 3] = t.ravel()
        out[i] = np.linalg.inv(inv)
    return out


def sample_loop(contour, n=100):
    p = np.array(contour, float)
    p = np.vstack((p, p[0]))
    lens = np.r_[0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
    s = np.linspace(0, lens[-1], n, endpoint=False)
    return np.stack([np.interp(s, lens, p[:, i]) for i in range(2)], axis=1)


def planar_patch(rings, plane, image, spacing):
    """Triangulate a traced, potentially concave surface and preserve its holes."""
    region = mask(rings)
    yy, xx = np.where(region)
    points = [
        np.stack(
            (
                xx[(xx % spacing == 0) & (yy % spacing == 0)],
                yy[(xx % spacing == 0) & (yy % spacing == 0)],
            ),
            axis=1,
        )
    ]
    for ring in rings:
        points.append(
            sample_loop(
                ring,
                max(
                    19,
                    int(
                        np.linalg.norm(
                            np.diff(np.vstack((ring, ring[0])), axis=0), axis=1
                        ).sum()
                        / 1.5
                    ),
                ),
            )
        )
    pts = np.unique(np.round(np.vstack(points), 4), axis=0)
    face = Delaunay(pts).simplices
    test = pts[face].mean(1)
    inside = map_coordinates(region.astype(float), test.T[::-1], order=1) > 0.25
    face = face[inside]
    xy = np.rint(pts).astype(int)
    return plane(pts), face, image[xy[:, 1], xy[:, 0]]


def combine(pieces):
    groups = [[] for _ in FIELDS]
    off = 0
    for v, f, c, obj, part in pieces:
        a = np.broadcast_to(obj, len(f))
        b = np.broadcast_to(part, len(f))
        for center, value in zip(groups, (v, f + off, c, a, b)):
            center.append(value)
        off += len(v)
    return tuple(np.concatenate(g) for g in groups)


def footprints(mesh, poses, images):
    v, f, _, _, p = mesh
    top = v[np.unique(f[p == 4])]
    rings = []
    for i in range(6):
        uv = world_to_rgb(top, poses[i])
        lo = np.maximum(uv.min(0).astype(int) - 5, 0)
        hi = np.minimum(uv.max(0).astype(int) + 6, [639, 479])
        pix = np.min(images[i], axis=2)
        # The mobile camera auto-exposes as it moves from the darker end of the room.
        threshold = [192, 194, 195, 210, 233, 239][i]
        binary = np.zeros_like(pix)
        binary[lo[1] : hi[1] + 1, lo[0] : hi[0] + 1] = (
            pix[lo[1] : hi[1] + 1, lo[0] : hi[0] + 1] >= threshold
        )
        outside = np.rint(uv).astype(np.int32)
        hull = np.zeros_like(pix)
        cv2.fillConvexPoly(hull, cv2.convexHull(outside), 1)
        hull = cv2.dilate(hull, np.ones((9, 9), np.uint8))
        contours, _ = cv2.findContours(
            (binary * hull).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        contour = max(contours, key=cv2.contourArea)
        ring = cv2.approxPolyDP(contour, 0.7, True)[:, 0].astype(float)
        rings.append(ring)
    return rings


def fit_receiver(mesh, poses, images):
    rings = footprints(mesh, poses, images)
    contours = [sample_loop(r, 140) for r in rings]
    trees = [cKDTree(r) for r in contours]
    ref = 1
    center = triangulate([r.mean(0) for r in contours], poses[:6])

    def lift(src, uv, coeff):
        ray = rays(uv, poses[src])
        origin = poses[src, :3, 3]
        return origin + ray * ((1 - origin @ coeff) / (ray @ coeff))[:, None]

    def error(x):
        res = []
        for i in range(6):
            if i == ref:
                continue
            for a, b in ((ref, i), (i, ref)):
                uv = world_to_rgb(lift(a, contours[a], x), poses[b])
                m = trees[b].query(uv)[1]
                res.extend((uv - contours[b][m]).ravel())
        return res

    opts = [np.array(x) for x in ([0, 0, 1], [0, -0.7, 1], [0.4, 0.3, 1])]
    models = [least_squares(error, v / (v @ center), loss="soft_l1") for v in opts]
    sol = min(models, key=lambda v: v.cost)
    verts, faces, colors = planar_patch(
        [rings[ref]], lambda uv: lift(ref, uv, sol.x), images[ref], 2
    )
    return (verts, faces, colors, 3, 4), rings


def resample(p, n):
    u = np.r_[0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
    u /= u[-1]
    return CubicSpline(u, p, axis=0, bc_type="natural")(np.linspace(0, 1, n))


def mug_tube(trace, poses, imgs):
    origins = np.asarray(trace["mug_crop_origins_xy"])
    pts = [
        resample((np.asarray(v) - [33, 23]) / 6 + origins[i], 18)
        for i, v in enumerate(trace["mug_centerline_enlarged"])
    ]
    xyz = np.array([triangulate([p[j] for p in pts], poses[:6]) for j in range(18)])
    xyz = resample(xyz, 30)
    # Input-frame handle areas constrain a circular ceramic tube radius. The
    # ratio of area to projected centerline arclength estimates its optical width.
    parts = [TRACES[f"i{i}"] for i in (1, 4)]
    rad = []
    for i, k in enumerate((1, 4)):
        area = mask(parts[i]["3"]).sum()
        length = np.linalg.norm(np.diff(pts[k], axis=0), axis=1).sum()
        distance = np.median(((xyz - poses[k, :3, 3]) @ poses[k, :3, :3])[:, 2])
        rad.append(area * distance / (2 * length * 521.0))
    radius = float(np.mean(rad))
    tang = np.gradient(xyz, axis=0)
    tang /= np.linalg.norm(tang, axis=1)[:, None]
    base = np.linalg.svd(xyz - xyz.mean(0))[2][-1]
    across = np.cross(tang, base)
    across /= np.linalg.norm(across, axis=1)[:, None]
    up = np.cross(across, tang)
    angle = np.linspace(0, 2 * np.pi, 12, endpoint=False)
    verts = (
        xyz[:, None, :]
        + radius
        * (
            across[:, None, :] * np.cos(angle)[None, :, None]
            + up[:, None, :] * np.sin(angle)[None, :, None]
        )
    ).reshape(-1, 3)
    a = np.arange(len(verts) - 12).reshape(-1, 12)
    b = np.roll(a, -1, axis=1)
    f = np.vstack(
        (
            np.stack((a, b, a + 12), axis=-1).reshape(-1, 3),
            np.stack((b, b + 12, a + 12), axis=-1).reshape(-1, 3),
        )
    )
    return verts, f, np.tile([235, 231, 224], (len(verts), 1)), 2, 3


def exposure_curves(images):
    """Put public photographs on a common exposure using matched unsaturated RGB patches."""
    sift = cv2.SIFT_create(nfeatures=3500)
    features = [
        sift.detectAndCompute(cv2.cvtColor(im, cv2.COLOR_RGB2GRAY), None)
        for im in images
    ]
    smooth = [cv2.GaussianBlur(im, (9, 9), 2).astype(float) for im in images]
    samples = []
    for i in range(len(images)):
        for j in range(i + 1, len(images)):
            matches = [
                a
                for a, b in cv2.BFMatcher().knnMatch(
                    features[i][1], features[j][1], k=2
                )
                if a.distance < 0.70 * b.distance
            ]
            if len(matches) < 12:
                continue
            coords = [
                np.rint([features[k][0][get(ma)].pt for ma in matches]).astype(int)
                for k, get in ((i, lambda ma: ma.queryIdx), (j, lambda ma: ma.trainIdx))
            ]
            colors = [smooth[k][xy[:, 1], xy[:, 0]] for k, xy in zip((i, j), coords)]
            good = (
                (colors[0] > 15)
                & (colors[0] < 236)
                & (colors[1] > 15)
                & (colors[1] < 236)
            ).all(1)
            if good.any():
                samples.append((i, j, colors[0][good], colors[1][good]))
    if not samples:
        return images

    def error(params):
        logs = params.reshape(len(images), 3)
        residual = [
            ((np.log(a) - logs[i]) - (np.log(b) - logs[j])).ravel()
            for i, j, a, b in samples
        ]
        residual.append(10 * logs.mean(0))
        return np.concatenate(residual)

    log = least_squares(
        error, np.zeros(3 * len(images)), loss="soft_l1", f_scale=0.04
    ).x.reshape(-1, 3)
    return np.stack(
        [
            np.rint(np.clip(im / np.exp(v), 0, 255)).astype(np.uint8)
            for im, v in zip(images, log)
        ]
    )


def fit_colors(mesh, poses, images):
    """Solve the sRGB barycentric rendering equations against public views, with robust residual weights."""
    v, f, prior, _, _ = mesh
    parts = []
    targets = []
    for k, (camera, z, face) in enumerate(native_surfaces(mesh, poses)):
        y, x = np.where(face[2::4, 2::4] >= 0)
        y = 4 * y + 2
        x = 4 * x + 2
        tri = f[face[y, x]]
        a, b, c = np.moveaxis(camera[tri], 1, 0)
        pts = rays(np.column_stack((x, y)), np.eye(4)) * z[y, x, None]
        ab = b - a
        ac = c - a
        ap = pts - a
        d = lambda x, y: np.einsum("ij,ij->i", x, y)
        aa, bb, cc, dd, ee = d(ab, ab), d(ab, ac), d(ac, ac), d(ab, ap), d(ac, ap)
        det = aa * cc - bb * bb
        inv = np.divide(1, det, out=np.zeros_like(det), where=det > 1e-20)
        beta = (cc * dd - bb * ee) * inv
        gamma = (aa * ee - bb * dd) * inv
        bary = np.clip(np.stack((1 - beta - gamma, beta, gamma), axis=1), 0, 1)
        bary /= bary.sum(1, keepdims=True)
        parts.append((tri, bary))
        targets.append(images[k][y, x])
    tri = np.concatenate([t for t, b in parts])
    vals = np.concatenate([b for t, b in parts])
    y = np.concatenate(targets).astype(float)
    A = coo_matrix(
        (vals.ravel(), (np.repeat(np.arange(len(y)), 3), tri.ravel())),
        shape=(len(y), len(v)),
    ).tocsr()
    colors = prior.astype(float)
    weights = np.ones(len(y))
    reg = 0.8
    for step in range(4):
        weighted = A.multiply(weights[:, None]).tocsr()
        colors = spsolve(
            (A.T @ weighted + reg * eye(len(v))).tocsc(),
            A.T @ (weights[:, None] * y) + reg * prior,
        )
        residual = np.abs(A @ colors - y).mean(1)
        weights = np.minimum(1, 15 / (residual + 0.01))
    return np.clip(colors, 0, 255)


def refine_texture(mesh, poses, images):
    """Subdivide large visible faces where a single interpolant misses observed RGB detail."""
    vertices, faces, colors, objects, parts = mesh
    area_error = np.zeros(len(faces))
    for k, (_, _, visible) in enumerate(native_surfaces(mesh, poses)):
        y, x = np.where(visible[2::4, 2::4] >= 0)
        y, x = 4 * y + 2, 4 * x + 2
        ids = visible[y, x]
        target = images[k][y, x].astype(float)
        mean = colors[faces].mean(axis=1)
        residual = np.mean(np.abs(target - mean[ids]), axis=1)
        area_error += np.bincount(
            ids, weights=np.minimum(residual, 60), minlength=len(faces)
        )
    limit = min((20000 - len(faces)) // 2, np.count_nonzero(area_error > 0))
    if limit <= 0:
        return mesh
    split = np.argsort(-area_error, kind="stable")[:limit]
    retained = np.ones(len(faces), bool)
    retained[split] = False
    triangles = faces[split]
    mid = np.arange(len(split)) + len(vertices)
    children = [
        np.column_stack((triangles[:, i], triangles[:, (i + 1) % 3], mid))
        for i in range(3)
    ]
    return (
        np.vstack((vertices, vertices[triangles].mean(1))),
        np.vstack([faces[retained], *children]),
        np.vstack((colors, colors[triangles].mean(1))),
        np.r_[objects[retained], np.tile(objects[split], 3)],
        np.r_[parts[retained], np.tile(parts[split], 3)],
    )


def build(
    include_receiver=True,
    include_dense=True,
    base_reference=None,
):
    trace = TRACES["public-traces"]
    images, old = inputs(include_dense=include_dense)
    poses = register(images, old)
    v, f, c, o, p = base_reference
    new = mug_tube(trace, poses, images)
    keep = p != 3
    # Avoid overlap of the old vessel side with the reconstructed physical ceramic.
    nearest = cKDTree(new[0]).query(v[f].mean(1))[0]
    keep &= ~((o == 2) & (nearest < 0.004))
    additions = [new]
    if include_receiver:
        new_receiver, rings = fit_receiver((v, f, c, o, p), poses, images)
        keep &= p != 4
        # The receiver rests above its supporting base. Remove the former shell only
        # where it overlaps the independently segmented contact face in several public views.
        cent = v[f].mean(1)
        votes = np.zeros(len(f), int)
        from scipy.ndimage import binary_dilation

        for k, ring in enumerate(rings):
            uv = world_to_rgb(cent, poses[k])
            inside = (
                np.isfinite(uv).all(1)
                & (uv[:, 0] >= 0)
                & (uv[:, 1] >= 0)
                & (uv[:, 0] < 639)
                & (uv[:, 1] < 479)
            )
            ids = np.flatnonzero(inside)
            xy = np.rint(uv[ids]).astype(int)
            m = binary_dilation(mask([ring]), iterations=2)
            votes[ids] += m[xy[:, 1], xy[:, 0]]
        keep &= ~((o == 3) & (p == 0) & (votes >= 2))
        additions.append(new_receiver)
    m = combine([(v, f[keep], c, o[keep], p[keep]), *additions])
    if include_dense:
        from stereo_bodies import replace_bodies

        m = replace_bodies(m, images, poses)
    m = refine_texture(m, poses, images)
    c = fit_colors(m, poses, images)
    # The dense recording ends at the first mapping pose. Use its texture as a prior,
    # then fit the surveyed traverse to avoid overrepresenting the earlier exposures.
    if include_dense:
        mapping_prior = (m[0], m[1], c, m[3], m[4])
        c = fit_colors(mapping_prior, poses[:6], exposure_curves(images[:6]))
    return (m[0], m[1], c, m[3], m[4])
