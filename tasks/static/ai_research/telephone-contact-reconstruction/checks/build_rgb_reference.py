"""Rebuild the two-view RGB fit from public contours and a prior public-RGB scene.

The prior mesh supplies the desk/environment hypothesis only. A validated archived
model output avoids executing historical third-party candidate code in this check.
The six public camera views provide the metric landmarks for the two support planes.
"""

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from fit_rgb_control import (
    CHECKS,
    FIELDS,
    D,
    K,
    combine,
    inputs,
    mask,
    native_surfaces,
    planar_patch,
    rays,
    register,
    sample_loop,
    triangulate,
    world_to_rgb,
)
from scipy.ndimage import binary_erosion, distance_transform_edt, map_coordinates
from scipy.optimize import least_squares
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation

KEYS = (1, 4)
PINNED_LAYOUT = "4ab3149c50eb9425ae8dc0ef21d56ad0be473c901c084f212d7d2c7f95d90d7a"


def load_inputs():
    images, poses = inputs(include_dense=False)
    parts = [json.loads((CHECKS / f"i{k}.json").read_text()) for k in KEYS]
    native = json.loads((CHECKS / "input-object-contours.json").read_text())
    bodies = []
    for key in KEYS:
        row = {}
        for label, outline in native[str(key)].items():
            row[label] = (
                [outline["outer"], *outline.get("holes", [])]
                if isinstance(outline, dict)
                else [outline]
            )
        bodies.append(row)
    return poses[list(KEYS)], [images[i] for i in KEYS], parts, bodies


def fit_plane(loops, poses):
    """Choose the 3D plane transferring the two independently traced optical boundaries."""
    contours = [sample_loop(x) for x in loops]
    center = triangulate([p.mean(axis=0) for p in contours], poses)
    trees = [cKDTree(p) for p in contours]

    def transfer(uv, i, coeff):
        ray = rays(uv, poses[i])
        origin = poses[i, :3, 3]
        return origin + ray * ((1 - origin @ coeff) / (ray @ coeff))[:, None]

    def residual(coeff):
        out = []
        for i in (0, 1):
            projected = world_to_rgb(transfer(contours[i], i, coeff), poses[1 - i])
            near = trees[1 - i].query(projected)[1]
            out.extend((projected - contours[1 - i][near]).ravel())
        return out

    guesses = ([0, 0, 1], [0.2, -0.7, 1], [-0.2, 0.7, 1], [0.8, 0.2, 1])
    solutions = [
        least_squares(
            residual,
            np.asarray(g) / np.dot(center, g),
            loss="soft_l1",
            f_scale=1.5,
            max_nfev=200,
        )
        for g in guesses
    ]
    best = min(solutions, key=lambda r: r.cost)
    return lambda uv, i=0: transfer(uv, i, best.x)


def contact_geometry():
    poses, images, parts, bodies = load_inputs()
    pieces = []
    # F1–F2 share one physical top mouth. The visible inner wall descends below the lip.
    metal = fit_plane([d["1"][0] for d in parts], poses)
    annuli = parts[0]["1"]
    v, f, c = planar_patch(annuli, metal, images[0], 3)
    pieces.append((v, f, c, 1, 1))
    outer = metal(sample_loop(annuli[0], 80))
    inner = metal(sample_loop(annuli[1], 80))
    normal = np.linalg.svd(outer - outer.mean(0))[2][-1]
    if normal[1] < 0:
        normal = -normal
    # Front wall height is constrained by the two RGB silhouettes.
    dsts = [mask(d["1"]) for d in bodies]
    signed = [distance_transform_edt(~m) - distance_transform_edt(m) for m in dsts]

    def ring_error(h):
        bottom = outer + normal * h
        errors = []
        for i in range(2):
            uv = world_to_rgb(bottom, poses[i])
            idx = uv[:, 1] >= np.percentile(uv[:, 1], 60)
            errors.extend(map_coordinates(signed[i], uv[idx].T[::-1], order=1))
        return errors

    height = least_squares(ring_error, [0.040], bounds=(0.015, 0.09), loss="soft_l1").x[
        0
    ]

    def tube(ring, h, obj, part):
        n = len(ring)
        a = np.arange(n)
        b = np.roll(a, -1)
        v = np.vstack((ring, ring + normal * h))
        f = np.vstack(
            (np.stack((a, b, a + n), axis=1), np.stack((a + n, b, b + n), axis=1))
        )
        uv = np.rint(world_to_rgb(v, poses[0])).astype(int)
        color = images[0][uv[:, 1], uv[:, 0]]
        return (v, f, color, obj, part)

    pieces.extend([tube(outer, height, 1, 0), tube(inner, height, 1, 2)])
    # Fit the handle and handset surfaces individually. Thin surfaces retain their open contour.
    for part, obj in ((3, 2), (4, 3)):
        plane = fit_plane([d[str(part)][0] for d in parts], poses)
        v, f, c = planar_patch(parts[0][str(part)], plane, images[0], 2)
        pieces.append((v, f, c, obj, part))

    # Mug rim centers and silhouettes were traced on the same two public RGB sheets.
    def oval(x, y, rx, ry, angle):
        theta = np.linspace(0, 2 * np.pi, 68, endpoint=False)
        a = np.deg2rad(angle)
        return np.stack(
            (
                x + rx * np.cos(theta) * np.cos(a) - ry * np.sin(theta) * np.sin(a),
                y + rx * np.cos(theta) * np.sin(a) + ry * np.sin(theta) * np.cos(a),
            ),
            axis=1,
        )

    rims = [oval(304.4, 326.4, 16.6, 8.1, -9), oval(220.6, 163.9, 16.4, 7.4, -9)]
    # Parallel to the desk and tape. Establish a metric center from the public B tracks.
    center = triangulate([r.mean(0) for r in rims], poses)

    def mug_plane(uv):
        rr = rays(uv, poses[0])
        return (
            poses[0, :3, 3]
            + rr * ((center - poses[0, :3, 3]) @ normal / (rr @ normal))[:, None]
        )

    mug_rim = mug_plane(rims[0])
    mug_inner = center + (mug_rim - center) * 0.86
    targets = [mask(d["2"]) for d in bodies]
    sds = [distance_transform_edt(~m) - distance_transform_edt(m) for m in targets]

    def mug_base_error(h):
        errors = []
        for k in range(2):
            uv = world_to_rgb(mug_rim + normal * h, poses[k])
            near = uv[:, 1] >= np.percentile(uv[:, 1], 70)
            errors.extend(map_coordinates(sds[k], uv[near].T[::-1], order=1))
        return errors

    mug_height = least_squares(
        mug_base_error, [0.09], bounds=(0.03, 0.18), loss="soft_l1"
    ).x[0]
    pieces.extend(
        [tube(mug_rim, mug_height, 2, 0), tube(mug_inner, mug_height * 0.87, 2, 0)]
    )
    top = (rims[0].mean(0) + (rims[0] - rims[0].mean(0)) * 0.86).tolist()
    v, f, c = planar_patch([rims[0].tolist(), top], mug_plane, images[0], 2)
    pieces.append((v, f, c, 2, 0))
    # The broad telephone shell lies below the resting raised receiver.
    shell = fit_plane([d["3"][0] for d in bodies], poses)
    v, f, c = planar_patch(bodies[0]["3"], shell, images[0], 4)
    ray0 = world_to_rgb(v[f].mean(axis=1), poses[0])
    r0 = np.rint(ray0).astype(int)
    inside = mask(parts[0]["4"])
    # Exclude the handset in the public silhouette, whose geometry is already modeled.
    keep = ~inside[r0[:, 1], r0[:, 0]]
    pieces.append((v + normal * 0.003, f[keep], c, 3, 0))
    ring = shell(sample_loop(bodies[0]["3"][0], 100))
    pieces.append(tube(ring, 0.018, 3, 0))
    return pieces


ORIGIN = np.array([0.0739, 0.5202, 0.9241])
AXES = np.array(
    [[0.6902, -0.7232, -0.0235], [-0.2853, -0.2421, -0.9274], [0.665, 0.6468, -0.3734]]
)
CORNERS = np.array(
    [
        [0, 0, 0],
        [0.835, 0, 0],
        [0.835, 0.35, 0],
        [1.706, 0.35, 0],
        [1.706, 1.69, 0],
        [0, 1.69, 0],
    ]
)
# Outer table corners are visible in both public images. The corner nearest the
# first camera is visible only in the later public view.
LANDMARKS = [
    {1: [540.7, 327.0], 3: [553.8, 224.1], 5: [38.1, 251.4]},
    {0: [201.2, 305.4], 1: [468.9, 188.2], 3: [537.7, 99.3], 5: [8.2, 85.5]},
]


def fit_support_planes(archive):
    images, poses = inputs(include_dense=False)
    poses = register(images, poses)

    def orient(x):
        return Rotation.from_rotvec(x[3:6]).as_matrix() @ AXES

    def transform(x, xyz):
        return (xyz * np.array([np.exp(x[6]), np.exp(x[7]), 1])) @ orient(x).T + x[:3]

    def loss(x):
        return np.concatenate(
            [
                (
                    world_to_rgb(transform(x, CORNERS[list(m)]), poses[i])
                    - np.array(list(m.values()))
                ).ravel()
                for i, m in zip((1, 4), LANDMARKS)
            ]
        )

    q = least_squares(loss, np.r_[ORIGIN, np.zeros(5)], loss="soft_l1").x
    ar = archive
    v, f, c, obj = (ar[k] for k in ("vertices", "faces", "colors", "face_ids"))
    local = (v - ORIGIN) @ np.linalg.inv(AXES.T)
    moved = transform(q, local)
    floor_tri = np.max(abs(local[f, 2] + 0.716), axis=1) < 0.001
    desk_tri = np.max(abs(local[f, 2]), axis=1) < 0.001
    maps = []
    sift = cv2.SIFT_create(nfeatures=4000, contrastThreshold=0.014)
    features = []
    for i, (camera, d, face) in enumerate(
        native_surfaces((moved, f, c, obj), poses[:6])
    ):
        shade = np.zeros_like(face, np.uint8)
        seen = face >= 0
        shade[seen] = np.where(
            floor_tri[face[seen]], 1, np.where(desk_tri[face[seen]], 2, 0)
        )
        # Remove projected boundaries to suppress mixing of the different planes.
        whole = np.zeros_like(shade)
        for label in (1, 2):
            whole[binary_erosion(shade == label, iterations=6)] = label
        maps.append(whole)
        key, desc = sift.detectAndCompute(
            cv2.cvtColor(images[i], cv2.COLOR_RGB2GRAY), None
        )
        features.append((np.array([k.pt for k in key]), desc))
    matcher = cv2.BFMatcher()
    allpts = {1: [], 2: []}
    for i in range(6):
        for j in range(i + 1, 6):
            if np.linalg.norm(poses[i, :3, 3] - poses[j, :3, 3]) < 0.13:
                continue
            kp, des = features[i]
            kp2, ds2 = features[j]
            matches = [
                a
                for a, b in matcher.knnMatch(des, ds2, k=2)
                if a.distance < 0.78 * b.distance
            ]
            px = kp[[a.queryIdx for a in matches]]
            px2 = kp2[[a.trainIdx for a in matches]]
            uv = [
                cv2.undistortPoints(x.reshape(-1, 1, 2), K, D).reshape(-1, 2)
                for x in (px, px2)
            ]
            X = cv2.triangulatePoints(
                np.linalg.inv(poses[i])[:3],
                np.linalg.inv(poses[j])[:3],
                uv[0].T,
                uv[1].T,
            )
            X = (X[:3] / X[3]).T
            err = np.maximum(
                np.linalg.norm(world_to_rgb(X, poses[i]) - px, axis=1),
                np.linalg.norm(world_to_rgb(X, poses[j]) - px2, axis=1),
            )
            indices = lambda a: (
                np.clip(a[:, 1].round().astype(int), 0, 479),
                np.clip(a[:, 0].round().astype(int), 0, 639),
            )
            ma = maps[i][indices(px)]
            mb = maps[j][indices(px2)]
            for k in (1, 2):
                sel = (
                    (ma == k)
                    & (mb == k)
                    & (X[:, 2] > 0.3)
                    & (X[:, 2] < 5)
                    & (err < 1.8)
                )
                allpts[k].extend(X[sel])
    plane_results = {}

    for k in (1, 2):
        pts = np.asarray(allpts[k])
        normal = orient(q)[:, 2].copy()
        heights = (q[:3] - pts) @ normal
        print(k, len(pts), np.percentile(heights, [10, 25, 50, 75, 90]).round(4))

        def residual(coeff, points=pts):
            return (points @ coeff - 1) / np.linalg.norm(coeff)

        guess = normal / (normal @ q[:3] - (0.7 if k == 1 else 0))
        out = least_squares(residual, guess, loss="cauchy", f_scale=0.012).x
        distance = np.abs(residual(out))
        print(
            np.round(out, 7),
            "median distance",
            np.median(distance),
            "supports",
            sum(distance < 0.035),
        )
        plane_results["floor" if k == 1 else "desk"] = out.tolist()
    return plane_results


def layout(archive):
    ps, photos, _, bodies = load_inputs()

    def orient(x):
        return Rotation.from_rotvec(x[3:6]).as_matrix() @ AXES

    def transform(x, xyz):
        return (xyz * np.array([np.exp(x[6]), np.exp(x[7]), 1])) @ orient(x).T + x[:3]

    def loss(x):
        result = []
        for i, m in enumerate(LANDMARKS):
            loc = world_to_rgb(transform(x, CORNERS[list(m)]), ps[i])
            result.extend((loc - np.array(list(m.values()))).ravel())
        return result

    q = least_squares(loss, np.r_[ORIGIN, np.zeros(5)], loss="soft_l1").x
    # A white tape mark on the concrete floor sets the table-to-floor height.
    floor = triangulate([[53.3, 380.5], [35.4, 220.1]], ps)
    normal = orient(q)[:, 2]
    height = np.dot(q[:3] - floor, normal)
    v, f, c, ids = (archive[k] for k in FIELDS[:4])
    only = ids == 0
    f = f[only]
    local = (v - ORIGIN) @ np.linalg.inv(AXES.T)
    v = transform(q, local)
    # RGB features on the tabletop and concrete floor constrain separate elevations and tilts.
    # Each plane uses public color correspondences from the six supplied images.
    plane = fit_support_planes(archive)

    def project_height(coeff):
        coefficient = np.asarray(coeff)
        return (1 - v @ coefficient) / (normal @ coefficient)

    # Interpolate vertical support geometry between table and floor while preserving
    # the relative elevation of books, monitor and other clutter above the tabletop.
    floor_depth = np.clip(-local[:, 2] / 0.716, 0, 1)
    desk_surface = 1 - floor_depth
    height_change = desk_surface * project_height(plane["desk"]) + floor_depth * (
        project_height(plane["floor"]) + 0.716
    )
    # The distances above are absolute shifts to the two surfaces. For coordinates
    # not exactly on them, retain the template offset from the nearest support.
    height_change += local[:, 2]
    v = v + height_change[:, None] * normal
    base = (v, f, c, np.zeros(len(f), np.int32))
    # Use public RGB samples for vertices that are visible in each calibrated source.
    colors = np.zeros_like(c, float)
    weights = np.zeros(len(v))
    for i, (camera, depth, fid) in enumerate(native_surfaces(base, ps)):
        projected = np.rint(world_to_rgb(v, ps[i]))
        in_img = ((projected >= 0) & (projected < [640, 480])).all(axis=1)
        ind = np.flatnonzero(in_img & (camera[:, 2] > 0.1))
        uv = np.zeros(projected.shape, dtype=int)
        uv[ind] = projected[ind].astype(int)
        u, w = uv.T
        valid = np.abs(depth[w[ind], u[ind]] - camera[ind, 2]) < 0.035
        ind = ind[valid]
        # Avoid projecting one of the three withheld-from-context physical objects onto the desk underneath.
        occluded = np.zeros((480, 640), bool)
        for rings in bodies[i].values():
            occluded |= mask(rings)
        ind = ind[~occluded[w[ind], u[ind]]]
        colors[ind] += photos[i][w[ind], u[ind]]
        weights[ind] += 1
    c = np.where(weights[:, None] > 0, colors / np.maximum(weights[:, None], 1), c)
    pieces = contact_geometry()
    xyz = v[f].mean(1)
    keep = np.ones(len(f), bool)
    for vv, ff, _, oi, part in pieces:
        if part == 0:
            continue
        keep &= cKDTree(vv[ff].mean(1)).query(xyz)[0] > (0.015 if oi == 2 else 0.023)
    total = len(f[keep]) + sum(len(x[1]) for x in pieces)
    if total > 20000:
        idx = np.flatnonzero(keep)
        keep[idx[np.linspace(0, len(idx) - 1, total - 20000).astype(int)]] = False
    print(
        "layout fit RMS",
        np.sqrt(np.mean(np.square(loss(q)))),
        "floor separation",
        height,
        "visible colors",
        sum(weights > 0),
        "/",
        len(c),
    )
    return combine([(v, f[keep], c, 0, 0), *pieces])


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--layout-artifact", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    with args.layout_artifact.open("rb") as f:
        if hashlib.file_digest(f, "sha256").hexdigest() != PINNED_LAYOUT:
            raise ValueError("Expected the pinned prior public-RGB layout")
    with np.load(args.layout_artifact, allow_pickle=False) as archive:
        mesh = layout(archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output, **dict(zip(FIELDS, mesh)))
