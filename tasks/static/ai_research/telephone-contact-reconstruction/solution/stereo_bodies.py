"""Recover visible metric surfaces from independent rectified pairs in the public RGB recording."""

import cv2
import numpy as np
from scipy.ndimage import (
    binary_dilation,
    binary_erosion,
    gaussian_filter,
    maximum_filter,
)

from optics import rays, world_to_rgb
from multiview import D, K, combine
from visibility import native_surfaces, mask


def rectified_depth(images, poses, anchor, other, pixels, directions):
    transform = np.linalg.inv(poses[other]) @ poses[anchor]
    size = (640, 480)
    left, right, p1, p2, _, _, _ = cv2.stereoRectify(
        K,
        D,
        K,
        D,
        size,
        transform[:3, :3].copy(),
        transform[:3, 3:4].copy(),
        flags=cv2.CALIB_ZERO_DISPARITY,
        alpha=0.15,
    )
    # Camera motion can be diagonal or largely optical. Auto-cropping such a pair
    # can return a nearly empty or excessively zoomed rectified overlap.
    shift = right @ transform[:3, 3]
    focal = 430.0
    center = np.array([320.0, 240.0]) - focal * left[:2, 2] / left[2, 2]
    p1 = np.array([[focal, 0, center[0], 0], [0, focal, center[1], 0], [0, 0, 1, 0]])
    p2 = p1.copy()
    p2[:2, 3] = focal * shift[:2]
    axis = int(abs(p2[1, 3]) > abs(p2[0, 3]))
    base = -p2[axis, 3]
    if abs(base) < 5 or abs(base) > 180:
        return np.full(pixels.shape[:2], np.nan)
    pairs = []
    for image, rot, proj in zip(
        (images[anchor], images[other]), (left, right), (p1, p2), strict=True
    ):
        maps = cv2.initUndistortRectifyMap(K, D, rot, proj, size, cv2.CV_32FC1)
        view = cv2.remap(image, *maps, cv2.INTER_LINEAR)
        if axis == 1:
            view = view.swapaxes(0, 1)
        if base < 0:
            view = view[:, ::-1]
        pairs.append(np.ascontiguousarray(view))
    minimum = max(0, int(abs(base) / 5) - 4)
    count = min(256, int(np.ceil((abs(base) / 0.43 - minimum) / 16)) * 16)
    matcher = cv2.StereoSGBM_create(
        minDisparity=minimum,
        numDisparities=count,
        blockSize=5,
        P1=8 * 3 * 25,
        P2=32 * 3 * 25,
        disp12MaxDiff=1,
        uniquenessRatio=9,
        speckleWindowSize=80,
        speckleRange=2,
        mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY,
    )
    disparity = matcher.compute(*pairs).astype(np.float32) / 16
    if base < 0:
        disparity = disparity[:, ::-1]
    if axis == 1:
        disparity = disparity.T
    rect_xy = cv2.undistortPoints(pixels.reshape(-1, 1, 2), K, D, R=left, P=p1)
    rect_xy = rect_xy.reshape(pixels.shape).astype(np.float32)
    disp = cv2.remap(disparity, rect_xy, None, cv2.INTER_NEAREST)
    result = np.full(disp.shape, np.nan)
    valid = (disp > max(0, minimum)) & ((rect_xy >= 0) & (rect_xy < [639, 479])).all(
        axis=2
    )
    result[valid] = abs(base) / disp[valid] / (directions[valid] @ left[2])
    return result


def depth_maps(images, poses):
    import warnings

    yy, xx = np.mgrid[0:480:4, 0:640:4]
    pixels = np.stack((xx, yy), axis=-1).astype(float)
    directions = rays(pixels.reshape(-1, 2), np.eye(4)).reshape(120, 160, 3)
    centers = poses[:, :3, 3]
    maps = []
    for anchor in range(len(poses)):
        distances = np.linalg.norm(centers - centers[anchor], axis=1)
        # Different baselines keep periodic texture and false disparity matches from voting twice.
        valid = np.flatnonzero((distances > 0.040) & (distances < 0.27))
        choice = set()
        for distance in (0.065, 0.11, 0.17, 0.22):
            if len(valid):
                choice.add(int(valid[np.argmin(abs(distances[valid] - distance))]))
        samples = [
            rectified_depth(images, poses, anchor, j, pixels, directions)
            for j in sorted(choice)
        ]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            if len(samples) < 2:
                maps.append(np.full(yy.shape, np.nan))
                continue
            stack = np.stack(samples)
            med = np.nanmedian(stack, axis=0)
            close = abs(stack - med) < (0.015 + 0.018 * med)
            consensus = np.nanmedian(np.where(close, stack, np.nan), axis=0)
            consensus[
                (close.sum(axis=0) < 2) | (consensus < 0.4) | (consensus > 4.5)
            ] = np.nan
            maps.append(consensus)
    return np.stack(maps)


def surface_net(field, origin, spacing):
    grid_shape = np.array(field.shape) - 1
    corners = np.array(
        [[x, y, z] for x in range(2) for y in range(2) for z in range(2)]
    )
    samples = np.stack(
        [
            field[x : x + grid_shape[0], y : y + grid_shape[1], z : z + grid_shape[2]]
            for x, y, z in corners
        ],
        axis=-1,
    )
    active = (samples.min(-1) < 0) & (samples.max(-1) >= 0)
    bases = np.argwhere(active)
    if len(bases) == 0:
        return np.empty((0, 3)), np.empty((0, 3), int)
    values = samples[active]
    coords = np.zeros((len(bases), 3))
    num = np.zeros(len(bases))
    for i, a in enumerate(corners):
        for j, b in enumerate(corners[i + 1 :], i + 1):
            if np.abs(a - b).sum() != 1:
                continue
            hit = (values[:, i] < 0) != (values[:, j] < 0)
            t = values[hit, i] / (values[hit, i] - values[hit, j])
            coords[hit] += a + (b - a) * t[:, None]
            num += hit
    vertices = origin + spacing * (bases + coords / num[:, None])
    ids = np.full(grid_shape, -1, int)
    ids[active] = np.arange(len(bases))
    faces = []
    for axis in range(3):
        lo = [slice(1, -1)] * 3
        hi = lo.copy()
        lo[axis] = slice(0, -1)
        hi[axis] = slice(1, None)
        left, right = field[tuple(lo)], field[tuple(hi)]
        crossed = (left < 0) != (right < 0)
        edge = np.argwhere(crossed)
        edge[:, [(axis + 1) % 3, (axis + 2) % 3]] += 1
        q = []
        for first, second in ((0, 0), (1, 0), (1, 1), (0, 1)):
            near = edge.copy()
            near[:, (axis + 1) % 3] -= first
            near[:, (axis + 2) % 3] -= second
            q.append(ids[tuple(near.T)])
        q = np.stack(q, axis=1)
        good = (q >= 0).all(axis=1)
        faces.extend((q[good][:, [0, 1, 2]], q[good][:, [0, 2, 3]]))
    return vertices, np.concatenate(faces)


def object_shells(mesh, images, poses, depths):
    v, f, c, o, p = mesh
    surfaces = list(native_surfaces(mesh, poses))
    fit = {}
    for label in (2, 3):
        bounds = v[np.unique(f[o == label])]
        low, high = bounds.min(0) - 0.024, bounds.max(0) + 0.024
        step = 0.004 if label in (1, 2) else 0.006
        axes = [np.arange(a, b + step, step) for a, b in zip(low, high)]
        xyz = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1)
        points = xyz.reshape(-1, 3)
        all_masks = []
        tight = []
        empty = np.zeros(len(points), int)
        protect = np.zeros(len(points), int)
        for k, (_, z, fid) in enumerate(surfaces):
            prev = np.zeros(fid.shape, np.uint8)
            seen = fid >= 0
            prev[seen] = o[fid[seen]]
            trace = TRACES["input-object-contours"].get(str(k))
            if trace:
                loops = trace[str(label)]
                if isinstance(loops, dict):
                    loops = [loops["outer"], *loops.get("holes", [])]
                else:
                    loops = [loops]
                silhouette = mask(loops)
            else:
                guess = prev == label
                if guess.sum() < 40:
                    continue
                y, x = np.where(guess)
                x0 = max(0, x.min() - 14)
                x1 = min(640, x.max() + 15)
                y0 = max(0, y.min() - 14)
                y1 = min(480, y.max() + 15)
                window = guess[y0:y1, x0:x1]
                seed = np.zeros(window.shape, np.uint8)
                seed[binary_dilation(window, iterations=8)] = cv2.GC_PR_BGD
                seed[window] = cv2.GC_PR_FGD
                seed[binary_erosion(window, iterations=3)] = cv2.GC_FGD
                if not np.any(seed == cv2.GC_FGD) or not np.any(seed == cv2.GC_BGD):
                    continue
                cv2.setRNGSeed(700 * label + k)
                cv2.grabCut(
                    images[k][y0:y1, x0:x1].copy(),
                    seed,
                    None,
                    np.zeros((1, 65)),
                    np.zeros((1, 65)),
                    3,
                    cv2.GC_INIT_WITH_MASK,
                )
                silhouette = np.zeros_like(guess)
                silhouette[y0:y1, x0:x1] = seed % 2 == 1
            signed = cv2.distanceTransform(
                silhouette.astype(np.uint8), cv2.DIST_L2, 3
            ) - cv2.distanceTransform((~silhouette).astype(np.uint8), cv2.DIST_L2, 3)
            uv = world_to_rgb(points, poses[k])
            xy = np.rint(uv).astype(int).clip([0, 0], [639, 479])
            x, y = xy.T
            sample = signed[y, x]
            # The two traced photographs bound the solid to within their one-pixel contour band.
            if trace:
                tight.append(sample + 1)
            else:
                all_masks.append(sample + 2)
            opt = (points - poses[k, :3, 3]) @ poses[k, :3, 2]
            depth = depths[k][
                np.minimum(119, (y + 2) // 4), np.minimum(159, (x + 2) // 4)
            ]
            empty += opt < depth - 0.012
            visible = fid[y, x] >= 0
            contact = visible & (p[np.maximum(fid[y, x], 0)] > 0)
            protect += contact & (opt <= z[y, x] + 0.008)
        field = np.min(tight, axis=0)
        if all_masks:
            field = np.minimum(field, np.quantile(all_masks, 0.65, axis=0))
        field = np.minimum(field, (2.5 - empty) * 2)
        field = gaussian_filter(field.reshape(xyz.shape[:-1]), 0.65)
        vv, ff = surface_net(field, low, step)
        if not len(ff):
            continue
        centers = vv[ff].mean(1)
        nearest = (
            np.rint((centers - low) / step)
            .astype(int)
            .clip(0, np.array(xyz.shape[:-1]) - 1)
        )
        projects = protect.reshape(xyz.shape[:-1])[tuple(nearest.T)]
        ff = ff[projects < 2]
        fit[label] = (
            vv,
            ff,
            np.tile(np.median(c[np.unique(f[o == label])], axis=0), (len(vv), 1)),
        )
    return fit


def compact_piece(v, f, c, spacing):
    ids = np.unique(f)
    reverse = np.full(len(v), -1, int)
    reverse[ids] = np.arange(len(ids))
    points = v[ids]
    rgb = c[ids]
    _, inv = np.unique(
        np.rint(points / spacing).astype(np.int32), axis=0, return_inverse=True
    )
    count = np.bincount(inv)
    vertices = np.stack(
        [np.bincount(inv, weights=points[:, i]) / count for i in range(3)], axis=1
    )
    colors = np.stack(
        [np.bincount(inv, weights=rgb[:, i]) / count for i in range(3)], axis=1
    )
    faces = inv[reverse[f]]
    keep = (
        (faces[:, 0] != faces[:, 1])
        & (faces[:, 1] != faces[:, 2])
        & (faces[:, 2] != faces[:, 0])
    )
    faces = faces[keep]
    _, rows = np.unique(np.sort(faces, axis=1), axis=0, return_index=True)
    return vertices, faces[np.sort(rows)], colors


def replace_bodies(mesh, images, poses):
    """Recover the mug and telephone bodies while keeping their exposed contact patches visible."""
    depths = depth_maps(images, poses)
    shells = object_shells(mesh, images, poses, depths)
    v, f, c, o, p = mesh
    all_views = list(native_surfaces(mesh, poses))
    # Upper contact geometry was reconstructed from manual public-view traces.
    # Retain the older tape model, whose annulus and exposed inner wall are analytic.
    kept = (p != 0) | (o <= 1)
    faces = f[kept]
    vid, ix = np.unique(faces, return_inverse=True)
    pieces = [(v[vid], ix.reshape(-1, 3), c[vid], o[kept], p[kept])]
    for label in (2, 3):
        if label not in shells:
            original = (o == label) & (p == 0)
            pieces.append((v, f[original], c, label, 0))
            continue
        vv, ff, cc = shells[label]
        vv, ff, cc = compact_piece(vv, ff, cc, 0.012 if label == 3 else 0.009)
        pts = np.concatenate((vv, vv[ff].mean(1)))
        can_occlude = np.zeros(len(pts), int)
        for k, (_, z, fid) in enumerate(all_views):
            orig_contact = (
                (fid >= 0)
                & (o[np.maximum(0, fid)] == label)
                & (p[np.maximum(0, fid)] != 0)
            )
            # Beyond the optical contour band preserve protrusions on the observed body.
            front = maximum_filter(np.where(orig_contact, z, 0.0), size=5)
            uv = world_to_rgb(pts, poses[k])
            inside = ((uv >= 0) & (uv < [639, 479])).all(1)
            xy = np.rint(uv).astype(int).clip([0, 0], [639, 479])
            observed = front[xy[:, 1], xy[:, 0]]
            opt = (pts - poses[k, :3, 3]) @ poses[k, :3, 2]
            can_occlude += inside & (observed > 0) & (opt < observed + 0.004)
        reject = (can_occlude[: len(vv)][ff] > 0).any(1) | (can_occlude[len(vv) :] > 0)
        pieces.append((vv, ff[~reject], cc, label, 0))
    return combine(pieces)
