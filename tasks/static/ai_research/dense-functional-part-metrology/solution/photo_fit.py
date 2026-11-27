"""Re-fit the physical desk from RGB gradients and sample textures inside public image masks."""

import numpy as np
from camera import poses_from_rows  # bundled module
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt, gaussian_filter, map_coordinates
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation


def sample(source, pixels):
    return np.stack(
        [
            map_coordinates(source[:, :, i], pixels.T[::-1], mode="nearest", order=1)
            for i in range(3)
        ],
        axis=-1,
    )


FRONT = {
    0: [((10, 458), (62, 435)), ((460, 276), (625, 210))],
    1: [((320, 441), (440, 363)), ((607, 259), (633, 241))],
    2: [((510, 465), (594, 389))],
    3: [((508, 459), (586, 337))],
    4: [((510, 435), (567, 301))],
    5: [((526, 444), (596, 312))],
}
LEFT = {
    1: [((3, 292), (52, 463))],
    2: [((10, 286), (104, 470))],
    3: [((10, 317), (155, 471))],
    4: [((10, 365), (139, 470))],
    5: [((9, 430), (65, 471))],
}


def find_edge(view, segments, front, blurred):
    direction = np.diff(segments[0], axis=0)[0]
    direction = direction / np.linalg.norm(direction)
    down = direction[::-1] * [-1, 1]
    samples = np.concatenate(
        [
            np.linspace(a, b, max(10, int(np.linalg.norm(np.array(a) - b)) // 2))
            for a, b in segments
        ]
    )
    steps = np.arange(-24, 24, 0.5)
    queries = samples[:, None, :] + steps[None, :, None] * down
    gray = (
        sample(blurred[view], queries.reshape(-1, 2))
        .reshape(len(samples), len(steps), 3)
        .mean(axis=-1)
    )
    grad = -np.gradient(gray, axis=1)
    coords = samples @ direction
    best_score = -1
    for slope in np.arange(-0.13, 0.13, 0.003):
        for shift in np.arange(-15, 15, 0.5):
            delta = (coords - coords.mean()) * slope + shift
            idx = np.rint((delta - steps[0]) / 0.5).astype(int).clip(1, len(steps) - 2)
            values = np.maximum(
                grad[np.arange(len(idx))[:, None], idx[:, None] + np.arange(-1, 2)], 0
            ).max(axis=-1)
            score = np.minimum(values, 19).mean() - 0.017 * abs(shift)
            if score > best_score:
                best_score = score
                best = delta
    pix = samples + best[:, None] * down
    fit = np.linalg.svd(np.column_stack((pix, np.ones(len(pix)))))[2][-1]
    return fit, pix


def desk_basis(frames, rows):
    """Intersect the measured multiview desk-edge planes and jointly fit orthogonal axes."""
    pose = poses_from_rows(rows)
    blurred = [
        gaussian_filter(frame.astype(float), sigma=(1.25, 1.25, 0)) for frame in frames
    ]
    groups = []
    for picks, front in ((FRONT, True), (LEFT, False)):
        normals = []
        offsets = []
        for view, segments in picks.items():
            coeff, _ = find_edge(view, segments, front, blurred)
            normal = pose[view, :3, :3] @ (
                coeff * [525, 525, 1] + [0, 0, np.array([319.5, 239.5]) @ coeff[:2]]
            )
            normal /= np.linalg.norm(normal)
            normals.append(normal)
            offsets.append(normal @ pose[view, :3, 3])
        groups.append((np.asarray(normals), np.asarray(offsets)))
    (fn, fd), (ln, ld) = groups
    origin = np.linalg.lstsq(np.vstack((fn, ln)), np.r_[fd, ld], rcond=None)[0]
    right = np.linalg.svd(fn)[2][-1]
    back = np.linalg.svd(ln)[2][-1]
    if right[0] < 0:
        right = -right
    if back[2] < 0:
        back = -back
    back -= right * (back @ right)
    back /= np.linalg.norm(back)
    initial = Rotation.from_matrix(
        np.stack((right, back, np.cross(right, back)))
    ).as_rotvec()

    def residual(param):
        a, b, _ = Rotation.from_rotvec(param[3:]).as_matrix()
        return np.r_[
            fn @ param[:3] - fd, ln @ param[:3] - ld, 0.4 * (fn @ a), 0.35 * (ln @ b)
        ]

    out = least_squares(
        residual, np.r_[origin, initial], loss="soft_l1", f_scale=0.0025
    )
    basis = Rotation.from_rotvec(out.x[3:]).as_matrix()
    if basis[2, 1] > 0:
        basis[2] *= -1
    # Heights are input-only stereo paper/desk measurements in the preliminary desk
    # frame. Recover the final physical plane and intersection of the two visible edges.
    references = [
        ((427, 365), -0.018),
        ((332, 293), -0.028),
        ((337, 223), -0.034),
        ((361, 213), -0.036),
        ((457, 320), -0.014),
        ((167, 339), -0.028),
        ((419, 370), -0.018),
        ((435, 368), -0.016),
        ((344, 229), -0.032),
        ((456, 304), -0.010),
        ((211, 299), -0.035),
    ]
    up = basis[2]
    center = pose[4, :3, 3]
    old_dist = out.x[:3] @ up
    points = []
    for pixel, height in references:
        ray = np.r_[(np.asarray(pixel) - [319.5, 239.5]) / 525, 1.0] @ pose[4, :3, :3].T
        points.append(
            center + (old_dist + height - 0.002 - center @ up) / (ray @ up) * ray
        )
    direction = np.linalg.svd(fn)[2][-1]
    if direction[0] < 0:
        direction = -direction
    edge = np.linalg.lstsq(np.vstack((fn, direction)), np.r_[fd, 0], rcond=None)[0]
    offsets = np.vstack((np.asarray(points) - edge, np.sqrt(12) * direction))
    normal = np.linalg.svd(offsets)[2][-1]
    if normal[1] > 0:
        normal = -normal
    direction -= normal * (normal @ direction)
    direction /= np.linalg.norm(direction)
    depth_axis = np.cross(direction, normal)
    if depth_axis[2] < 0:
        depth_axis = -depth_axis
    corner = edge + np.median((ld - ln @ edge) / (ln @ direction)) * direction
    return corner, np.stack((direction, depth_axis, normal))


SOURCES = {
    "brochure": {
        4: [
            (302, 237),
            (322, 200),
            (360, 214),
            (372, 231),
            (403, 266),
            (454, 308),
            (434, 367),
            (290, 299),
            (265, 286),
            (292, 271),
        ],
        2: [
            (311, 255),
            (358, 226),
            (390, 249),
            (429, 302),
            (465, 379),
            (417, 431),
            (302, 315),
        ],
    },
    "loose": {
        4: [(349, 185), (414, 162), (484, 159), (570, 211), (602, 257), (473, 330)],
        0: [(215, 129), (320, 131), (386, 197), (408, 310), (206, 297)],
    },
    "stack": {
        0: [(308, 88), (428, 44), (456, 67), (583, 188), (452, 271)],
        4: [(396, 130), (432, 58), (614, 111), (612, 195)],
        5: [(394, 178), (442, 96), (637, 146), (619, 242)],
    },
    "book": {
        2: [(0, 136), (108, 60), (180, 145), (44, 201), (3, 146)],
        3: [(0, 122), (68, 87), (157, 165), (37, 243), (0, 198)],
        5: [(0, 140), (20, 139), (124, 222), (25, 317), (0, 282)],
    },
    "phone": {
        5: [
            (30, 54),
            (113, 25),
            (212, 103),
            (211, 131),
            (167, 162),
            (49, 136),
            (24, 100),
        ],
        4: [(0, 0), (135, 0), (207, 61), (192, 94), (153, 123), (0, 76)],
    },
    "keyboard": {
        5: [(429, 82), (471, 0), (566, 0), (537, 119)],
        4: [(433, 39), (455, 0), (557, 0), (541, 73)],
        0: [(422, 28), (450, 0), (640, 0), (640, 44), (514, 110)],
    },
    "holder": {
        4: [(215, 39), (293, 42), (292, 132), (218, 128)],
        5: [(214, 55), (302, 66), (293, 187), (223, 174)],
    },
    "carton": {
        4: [
            (307, 12),
            (396, 0),
            (402, 8),
            (411, 68),
            (404, 81),
            (397, 102),
            (393, 123),
            (386, 150),
            (322, 168),
            (309, 159),
            (303, 150),
            (303, 99),
            (307, 47),
            (309, 40),
        ],
        2: [
            (387, 31),
            (481, 28),
            (491, 39),
            (485, 86),
            (480, 120),
            (468, 144),
            (450, 192),
            (378, 193),
            (369, 186),
            (374, 112),
            (378, 68),
            (385, 51),
        ],
        5: [
            (305, 68),
            (390, 50),
            (401, 58),
            (405, 125),
            (398, 138),
            (388, 192),
            (325, 215),
            (305, 208),
            (302, 194),
            (302, 131),
            (303, 109),
        ],
    },
}


def get_source(group, view, polygon, rgb_frames):
    mask_image = Image.new("L", (640, 480))
    ImageDraw.Draw(mask_image).polygon(polygon, fill=255)
    region = np.asarray(mask_image) > 0
    rgb = rgb_frames[view]
    mean = rgb.mean(axis=2)
    if group == "loose":
        region &= mean > 146
        if view == 4:
            mask_image = Image.new("L", (640, 480))
            ImageDraw.Draw(mask_image).line(
                [
                    (432, 163),
                    (434, 181),
                    (428, 220),
                    (419, 238),
                    (404, 250),
                    (391, 256),
                ],
                fill=255,
                width=9,
            )
            region &= np.asarray(mask_image) == 0
    if group == "brochure":
        region &= mean > 47
        mask_image = Image.new("L", (640, 480))
        pts = (
            [(300, 264), (317, 271), (347, 270), (376, 263), (397, 256)]
            if view == 4
            else [
                (306, 272),
                (322, 293),
                (357, 308),
                (386, 307),
                (411, 302),
                (432, 294),
            ]
        )
        ImageDraw.Draw(mask_image).line(pts, fill=255, width=7)
        region &= np.asarray(mask_image) == 0
    if group == "stack":
        region &= mean > 135
    if group == "phone":
        region &= mean > 80
    distance, indices = distance_transform_edt(~region, return_indices=True)
    filled = gaussian_filter(rgb[indices[0], indices[1]], sigma=(1.0, 1.0, 0))
    return filled, distance


def sample_textures(mesh, frames, rows, axes, corner):
    rgb_frames = np.asarray(frames, dtype=float)
    pose = poses_from_rows(rows)
    sources = {
        group: {
            view: get_source(group, view, poly, rgb_frames)
            for view, poly in entries.items()
        }
        for group, entries in SOURCES.items()
    }
    results = {}
    default_colors = np.vstack(mesh.colors)
    for name, (start, local_points) in mesh.swatch_jobs.items():
        group = "carton" if name.startswith("carton") else name
        view_sources = sources[group]
        default = default_colors[start : start + len(local_points)]
        points = local_points @ axes + corner
        color = default.copy()
        quality = np.full(len(points), np.inf)
        for weight, (view, (source, distance)) in enumerate(view_sources.items()):
            cam = (points - pose[view, :3, 3]) @ pose[view, :3, :3]
            depth = cam[:, 2]
            pix = cam[:, :2] / depth[:, None] * 525 + np.array([319.5, 239.5])
            visible = (
                (depth > 0.05)
                & (pix[:, 0] >= 0)
                & (pix[:, 0] < 640)
                & (pix[:, 1] >= 0)
                & (pix[:, 1] < 480)
            )
            error = map_coordinates(distance, pix.T[::-1], mode="nearest", order=1)
            cost = error + weight * (32 if group in ("carton", "brochure") else 9)
            if group == "carton":
                reach = 24
            elif group == "brochure":
                reach = 5
            elif group == "loose":
                reach = 19
            else:
                reach = 12
            b = (cost < quality) & (error < reach) & visible
            if b.any():
                estimated = sample(source, pix[b])
                blend = np.clip((error[b] - max(3, reach - 8)) / 8, 0, 0.85)[:, None]
                color[b] = estimated * (1 - blend) + default[b] * blend
                quality[b] = cost[b]
        results[name] = np.uint8(np.rint(np.clip(color, 0, 255)))
    return results
