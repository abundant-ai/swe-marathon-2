"""Construct the scene from the calibrated public desk edges, measured feature picks and RGB patches.

Adapted from the source of Oddish trial swe-m2_ai-research_clutter-object-metrology-correct-ab991e51-2.
Its public-view feature picks and procedural object topology are preserved. The desk frame and
texture swatches are recovered from the supplied photographs when this function executes.
"""

from itertools import pairwise

import numpy as np
from photo_fit import desk_basis, sample_textures  # bundled module


def _rotation(quaternion):
    vector = np.asarray(quaternion[:3])
    scalar = quaternion[3]
    skew = np.cross(vector, np.eye(3)).T
    return np.eye(3) + 2 * (scalar * skew + skew @ skew) / np.dot(
        quaternion, quaternion
    )


def _on_plane(pixels, height, frame=4):
    pixels = np.asarray(pixels, dtype=float)
    origin, quaternion = np.split(np.asarray(_REFERENCE_POSES[frame]), [3])
    image_rays = np.concatenate(
        ((pixels - [319.5, 239.5]) / 525.0, np.ones(pixels.shape[:-1] + (1,))), axis=-1
    )
    directions = image_rays @ _rotation(quaternion).T @ _DESK_AXES.T
    center = (origin - _CORNER) @ _DESK_AXES.T
    lengths = (height - center[2]) / directions[..., 2]
    return center + lengths[..., None] * directions


def _cross2(first, second):
    return first[..., 0] * second[..., 1] - first[..., 1] * second[..., 0]


def _area(loop):
    return _cross2(loop, np.roll(loop, -1, axis=0)).sum() * 0.5


def _ears(loop):
    """Triangulate a simple planar outline, including the gamepad's cutout."""
    order = list(range(len(loop)))
    if _area(loop) < 0:
        order.reverse()
    faces = []
    while len(order) > 3:
        for index, middle in enumerate(order):
            first, last = order[index - 1], order[(index + 1) % len(order)]
            left, tip, right = loop[[first, middle, last]]
            if _cross2(tip - left, right - tip) <= 1e-12:
                continue
            other = loop[[idx for idx in order if idx not in (first, middle, last)]]
            interior = (
                (_cross2(tip - left, other - left) >= 0)
                & (_cross2(right - tip, other - tip) >= 0)
                & (_cross2(left - right, other - right) >= 0)
            )
            if not interior.any():
                faces.append((first, middle, last))
                order.pop(index)
                break
        else:
            raise ValueError("Outline is not a simple polygon")
    faces.append(tuple(order))
    return np.asarray(faces, dtype=np.int32)


def _round_loop(outline, rounds=1):
    outline = np.asarray(outline, dtype=float)
    for _ in range(rounds):
        following = np.roll(outline, -1, axis=0)
        outline = np.stack(
            (0.76 * outline + 0.24 * following, 0.24 * outline + 0.76 * following),
            axis=1,
        ).reshape(-1, outline.shape[1])
    return outline


def _inset(outline, delta):
    edges = np.roll(outline, -1, axis=0) - outline
    inward = edges[:, ::-1] * [-1, 1] / np.linalg.norm(edges, axis=1)[:, None]
    summed = inward + np.roll(inward, 1, axis=0)
    return outline + (
        np.asarray(delta)[..., None]
        * summed
        / np.maximum(0.9, np.sum(inward * summed, axis=1))[:, None]
    )


def _rows(lower, upper):
    secondary = np.roll(lower, -1)
    upper_secondary = np.roll(upper, -1)
    return np.concatenate(
        (
            np.column_stack((lower, secondary, upper_secondary)),
            np.column_stack((lower, upper_secondary, upper)),
        )
    )


class _Mesh:
    def __init__(self):
        self.vertices = []
        self.triangles = []
        self.colors = []
        self.identities = []
        self.count = 0
        self.swatch_jobs = {}

    def put(self, vertices, faces, rgb, label=0, swatch=None):
        vertices = np.asarray(vertices, dtype=float).reshape(-1, 3)
        faces = np.asarray(faces, dtype=np.int32).reshape(-1, 3)
        if swatch is not None:
            self.swatch_jobs[swatch] = (self.count, vertices)
            if swatch in _SWATCHES:
                rgb = _SWATCHES[swatch]
        rgb = np.asarray(rgb).reshape(-1, 3)
        self.vertices.append(vertices)
        self.colors.append(np.broadcast_to(rgb, vertices.shape))
        self.triangles.append(faces + self.count)
        self.identities.append(np.full(len(faces), label, dtype=np.int32))
        self.count += len(vertices)

    def sheet(
        self,
        corners,
        columns,
        rows,
        rgb,
        label=0,
        swatch=None,
        bend=None,
        reverse=False,
    ):
        """A bilinear patch; consecutive corners follow its perimeter."""
        corners = np.asarray(corners, dtype=float)
        horizontal, vertical = np.meshgrid(
            np.linspace(0, 1, columns + 1), np.linspace(0, 1, rows + 1)
        )
        horiz = horizontal[..., None]
        vert = vertical[..., None]
        nodes = (1 - vert) * ((1 - horiz) * corners[0] + horiz * corners[1]) + vert * (
            (1 - horiz) * corners[3] + horiz * corners[2]
        )
        if bend is not None:
            nodes += bend(horizontal, vertical)
        grid = np.arange(nodes.shape[0] * nodes.shape[1]).reshape(nodes.shape[:2])
        base, right = grid[:-1, :-1].ravel(), grid[:-1, 1:].ravel()
        across, diag = grid[1:, :-1].ravel(), grid[1:, 1:].ravel()
        faces = np.concatenate(
            (
                np.column_stack((base, right, diag)),
                np.column_stack((base, diag, across)),
            )
        )
        if reverse or (np.ptp(corners[:, 2]) < 0.025 and _area(corners[:, :2]) < 0):
            faces = faces[:, ::-1]
        rgb = rgb(nodes) if callable(rgb) else rgb
        self.put(nodes, faces, rgb, label, swatch)

    def shell(self, rings, rgb, label=0, cap=True, bottom=True):
        rings = np.asarray(rings, dtype=float)
        if _area(rings[-1, :, :2]) < 0:
            rings = rings[:, ::-1]
            if np.ndim(rgb) == 3:
                rgb = np.asarray(rgb)[:, ::-1]
        count = rings.shape[1]
        indices = np.arange(len(rings) * count).reshape(len(rings), count)
        if np.ndim(rgb) == 2:
            rgb = np.broadcast_to(np.asarray(rgb)[:, None, :], rings.shape)
        faces = [_rows(low, high) for low, high in pairwise(indices)]
        if bottom:
            faces.append(_ears(rings[0, :, :2])[:, ::-1])
        if cap:
            faces.append(indices[-1][_ears(rings[-1, :, :2])])
        self.put(rings, np.concatenate(faces), rgb, label)

    def cylinder(
        self,
        center,
        profile,
        label=0,
        segments=24,
        flatten=1.0,
        direction=(1.0, 0.0),
        cap=True,
    ):
        theta = np.arange(segments) * (2 * np.pi / segments)
        axis = np.asarray(direction, dtype=float)
        axis /= np.linalg.norm(axis)
        circle = np.cos(theta)[:, None] * axis + flatten * np.sin(theta)[
            :, None
        ] * axis[::-1] * [-1, 1]
        rings = [
            np.column_stack((center + radius * circle, np.full(segments, height)))
            for radius, height, _ in profile
        ]
        rgb = []
        for _, _, color in profile:
            modulation = (1.0 + 0.09 * np.sin(theta + 0.4))[:, None]
            rgb.append(np.asarray(color) * modulation)
        self.shell(rings, rgb, label, cap=cap, bottom=cap)

    def slab(self, outline, lower, upper, rgb, side, label=0, top=True):
        outline = np.asarray(outline, dtype=float)
        footprint = outline[:, :2]
        low = np.column_stack((footprint, np.broadcast_to(lower, (len(footprint),))))
        high = np.column_stack((footprint, np.broadcast_to(upper, (len(footprint),))))
        self.shell([low, high], [side, rgb], label, cap=top)

    def finish(self):
        positions = np.concatenate(self.vertices)
        faces = np.concatenate(self.triangles)
        along = positions[faces[:, 1]] - positions[faces[:, 0]]
        across = positions[faces[:, 2]] - positions[faces[:, 0]]
        valid = np.linalg.norm(np.cross(along, across), axis=1) > 1.0e-11
        used, indices = np.unique(faces[valid].ravel(), return_inverse=True)
        colors = np.clip(np.rint(np.concatenate(self.colors)[used]), 0, 255).astype(
            np.uint8
        )
        return (
            positions[used] @ _DESK_AXES + _CORNER,
            indices.reshape(-1, 3).astype(np.int32),
            colors,
            np.concatenate(self.identities)[valid],
        )


def _rectangle(xmin, xmax, ymin, ymax):
    return np.array([[xmin, ymin], [xmax, ymin], [xmax, ymax], [xmin, ymax]])


def _xyz(outline, height):
    return np.column_stack((outline, np.broadcast_to(height, (len(outline),))))


def _quad_from_three(first, second, fourth):
    first, second, fourth = np.asarray([first, second, fourth])
    return np.array([first, second, second + fourth - first, fourth])


def _tube(mesh, path, radius, rgb, label=0, sides=6):
    path = np.asarray(path, dtype=float)
    tangents = np.gradient(path, axis=0)
    tangents /= np.linalg.norm(tangents, axis=1, keepdims=True)
    auxiliary = np.array([0.0, 0.0, 1.0])
    first = np.cross(tangents, auxiliary)
    vertical = np.linalg.norm(first, axis=1) < 0.15
    first[vertical] = np.cross(tangents[vertical], [0.0, 1.0, 0.0])
    first /= np.linalg.norm(first, axis=1, keepdims=True)
    second = np.cross(tangents, first)
    angles = np.arange(sides) * 2 * np.pi / sides
    vertices = path[:, None] + radius * (
        np.cos(angles)[None, :, None] * first[:, None]
        + np.sin(angles)[None, :, None] * second[:, None]
    )
    face_rows = np.arange(len(path) * sides).reshape(len(path), sides)
    mesh.put(
        vertices,
        np.concatenate([_rows(low, high) for low, high in pairwise(face_rows)]),
        rgb,
        label,
    )


def _wood(nodes):
    east, north = nodes[..., 0], nodes[..., 1]
    grain = (
        1.5 * np.sin(east * 33 + north * 227 + 0.85 * np.sin(east * 39))
        + 1.6 * np.sin(east * 20 + north * 112)
        + 1.25 * np.cos(east * 10 - north * 42)
    )
    light = grain + 7.0 * np.exp(-((east - 0.26) ** 2 + (north - 0.23) ** 2) / 0.11)
    for xx, yy, strength, span in [
        (0.17, 0.16, 18, 0.075),
        (0.24, 0.31, 23, 0.05),
        (0.45, 0.35, 17, 0.075),
        (0.37, 0.51, 18, 0.1),
        (0.10, 0.58, 14, 0.1),
    ]:
        light -= strength * np.exp(-((east - xx) ** 2 + (north - yy) ** 2) / span**2)
    return np.array([209, 198, 197]) + light[..., None] * np.array([1.0, 1.0, 1.06])


def _environment_structure(mesh):
    desk = _rectangle(0, 1.15, 0, 1.02)
    mesh.slab(desk, -0.024, 0.0, (189, 166, 144), (136, 111, 89), top=False)
    mesh.sheet(_xyz(desk, 0.0), 29, 22, _wood)
    for xmin, xmax, ymin, ymax in [
        (0.026, 0.073, 0.055, 0.108),
        (0.889, 0.935, 0.035, 0.080),
        (0.025, 0.071, 0.83, 0.88),
    ]:
        mesh.slab(
            _rectangle(xmin, xmax, ymin, ymax),
            -0.734,
            -0.024,
            (46, 39, 39),
            (38, 32, 32),
        )
    mesh.slab(
        _rectangle(0.225, 0.392, 0.066, 0.362),
        -0.72,
        -0.085,
        (45, 33, 29),
        (41, 29, 24),
    )
    for strip in range(39):
        north = -2.1 + strip * 0.114
        deck = _rectangle(-2.1, 2.3, north, north + 0.114)

        def floor_colors(nodes, index=strip):
            along, transverse = nodes[..., 0], nodes[..., 1]
            shift = 5.0 * np.sin(index * 12.23) + 3.0 * np.sin(index * 4.83)
            grain = (
                5.0 * np.sin(along * 17.5 + transverse * 90 + index * 16.0)
                + 3.0 * np.sin(along * 72 + transverse * 300.0)
                + 4.0 * np.cos(along * 33.8 + transverse * 211)
            )
            shadow = 25 * np.exp(
                -((along - 0.10) ** 2 + (transverse - 0.46) ** 2) / 0.65
            )
            seams = 14 * (np.mod(along + index * 0.41, 1.25) < 0.09)
            fade = grain + shift - shadow - seams
            return [112, 82, 53] + fade[..., None] * [1.0, 0.86, 0.69]

        mesh.sheet(_xyz(deck, -0.735), 23, 1, floor_colors)


def _paperwork(mesh):
    envelope = _on_plane(
        [(158, 325), (174, 354), (470, 492), (549, 229), (267, 213)], 0.003
    )
    mesh.slab(envelope, 0.0007, 0.003, (195, 156, 107), (144, 114, 84), top=False)
    crest = _on_plane((226, 307), 0.003)[:2]
    under_pad = _on_plane((315, 384), 0.003)[:2]

    def kraft(nodes):
        delta = nodes[..., :2] - crest
        along = delta @ [0.70, 0.714]
        across = delta @ [-0.714, 0.70]
        stamp = np.exp(-((along / 0.024) ** 6 + (across / 0.0048) ** 2))
        mark = stamp * (15 + 6 * np.sin(along * 350) + 8 * np.sin(across * 1150))
        falloff = 48 * np.exp(
            -np.sum((nodes[..., :2] - under_pad) ** 2, axis=-1) / 0.005
        )
        return np.array([204, 166, 117]) - (mark + falloff)[..., None] * [
            0.85,
            0.93,
            0.81,
        ]

    for idx in range(1, len(envelope) - 1):
        first, second, third = envelope[[0, idx, idx + 1]]
        if _area(np.array([first[:2], second[:2], third[:2]])) < 0:
            second, third = third, second
        mesh.sheet([first, second, third, third], 10, 7, kraft)

    flyer_tl, flyer_fr, long_edge = _on_plane(
        [(321, 199), (435, 369), (306, 307)], 0.005
    )
    along = flyer_fr - long_edge
    along /= np.linalg.norm(along)
    width = np.dot(flyer_fr - flyer_tl, along)
    flyer = np.array(
        [flyer_fr - width * along, flyer_fr, flyer_tl + width * along, flyer_tl]
    )
    mesh.sheet(flyer, 21, 25, (112, 102, 128), swatch="brochure")

    loose_nw = _on_plane((348, 184), 0.0055)
    loose_sw = _on_plane((473, 331), 0.007)
    loose_se = _on_plane((605, 258), 0.011)
    loose = _quad_from_three(loose_sw, loose_se, loose_nw)
    mesh.slab(
        loose,
        [pt[2] - 0.0015 for pt in loose],
        loose[:, 2],
        (197, 193, 205),
        (184, 178, 183),
        top=False,
    )
    mesh.sheet(loose, 21, 19, (228, 222, 232), swatch="loose")

    near_left, far_left, near_right = _on_plane(
        [(395, 133), (433, 59), (615, 198)], np.array([0.016, 0.018, 0.021]), frame=4
    )
    stack = _quad_from_three(near_left, near_right, far_left)
    mesh.slab(stack, 0.003, 0.006, (158, 140, 160), (145, 126, 147), top=False)
    mesh.slab(stack, 0.006, 0.011, (184, 181, 191), (174, 167, 184), top=False)
    mesh.slab(stack, 0.011, 0.014, (179, 178, 216), (127, 126, 168), top=False)
    mesh.slab(stack, 0.014, stack[:, 2], (216, 214, 223), (199, 190, 207), top=False)
    mesh.sheet(stack, 19, 22, (225, 222, 233), swatch="stack")

    near_left, near_right, back_right = _on_plane(
        [(43, 201), (183, 144), (108, 59)], 0.035, frame=2
    )
    book = _quad_from_three(near_right, near_left, back_right)[[1, 0, 3, 2]]
    mesh.slab(book, 0.001, 0.003, (69, 81, 119), (57, 67, 99), top=False)
    mesh.slab(book, 0.003, 0.032, (206, 198, 196), (177, 163, 163), top=False)
    mesh.slab(book, 0.032, 0.035, (100, 123, 174), (49, 68, 122), top=False)
    mesh.sheet(book, 19, 23, (95, 123, 178), swatch="book")


def _gamepad(mesh):
    image_rim = np.array(
        [
            [241, 416, 0.019],
            [242, 385, 0.036],
            [248, 354, 0.044],
            [260, 334, 0.048],
            [274, 328, 0.052],
            [285, 328, 0.050],
            [299, 336, 0.051],
            [322, 339, 0.051],
            [340, 337, 0.051],
            [349, 328, 0.053],
            [364, 325, 0.051],
            [376, 328, 0.050],
            [385, 338, 0.047],
            [394, 359, 0.041],
            [399, 386, 0.030],
            [400, 414, 0.016],
            [394, 427, 0.012],
            [383, 433, 0.012],
            [373, 430, 0.015],
            [363, 420, 0.022],
            [351, 408, 0.025],
            [336, 401, 0.031],
            [320, 399, 0.032],
            [305, 403, 0.033],
            [291, 406, 0.032],
            [281, 411, 0.024],
            [273, 426, 0.020],
            [262, 437, 0.015],
            [251, 438, 0.014],
            [244, 431, 0.017],
        ]
    )
    outline = _on_plane(image_rim[:, :2], image_rim[:, 2])
    outline = _round_loop(outline)
    if _area(outline[:, :2]) < 0:
        outline = outline[::-1]

    planar, shoulder = outline[:, :2], outline[:, 2]
    bevel = np.minimum(0.007, shoulder * 0.23)
    underside = 0.005 + 0.49 * np.maximum(0, shoulder - 0.021)
    upper = _inset(planar, bevel)
    upper_height = shoulder + 0.005
    rings = [
        _xyz(_inset(planar, bevel * 1.16), underside),
        _xyz(_inset(planar, bevel * 0.30), underside + 0.004),
        _xyz(planar, shoulder - 0.003),
        _xyz(_inset(planar, bevel * 0.22), shoulder + 0.001),
        _xyz(upper, upper_height),
    ]
    mesh.shell(
        rings,
        [(11, 10, 13), (17, 15, 19), (22, 20, 26), (28, 26, 33), (34, 31, 38)],
        label=1,
        cap=False,
    )
    faces = _ears(upper)
    refined = np.asarray(rings[-1]).tolist()
    cache = {}
    boundary = {
        tuple(sorted((index, (index + 1) % len(upper)))) for index in range(len(upper))
    }

    def between(first, second):
        key = tuple(sorted((first, second)))
        if key not in cache:
            vertex = (np.array(refined[first]) + refined[second]) / 2
            if key not in boundary:
                distance = np.min(np.linalg.norm(planar - vertex[:2], axis=1))
                vertex[2] += min(0.0055, distance * 0.18)
            cache[key] = len(refined)
            refined.append(vertex)
            if key in boundary:
                boundary.update(
                    (
                        tuple(sorted((first, cache[key]))),
                        tuple(sorted((second, cache[key]))),
                    )
                )
        return cache[key]

    for _ in range(2):
        split = []
        for start, middle, end in faces:
            left, right, across = (
                between(start, middle),
                between(middle, end),
                between(end, start),
            )
            split.extend(
                (
                    (start, left, across),
                    (left, middle, right),
                    (across, right, end),
                    (left, right, across),
                )
            )
        faces = split
    nodes = np.array(refined)
    body_color = (
        np.array([32, 29, 36]) + np.minimum(7, (nodes[:, 2] - 0.025) * 185)[:, None]
    )
    mesh.put(nodes, faces, body_color, 1)

    port_axis = _on_plane([(273, 350), (369, 346)], 0.051)
    port_axis = np.diff(port_axis[:, :2], axis=0)[0]
    port_axis /= np.linalg.norm(port_axis)
    pad = _on_plane((273, 361), 0.064)[:2]
    mesh.cylinder(
        pad,
        [
            (0.0161, 0.046, (17, 15, 20)),
            (0.0163, 0.056, (23, 20, 26)),
            (0.0152, 0.061, (40, 36, 43)),
            (0.0128, 0.063, (51, 46, 53)),
        ],
        1,
    )
    cross_outline = np.array(
        [
            [-1, -0.33],
            [-0.33, -0.33],
            [-0.33, -1],
            [0.33, -1],
            [0.33, -0.33],
            [1, -0.33],
            [1, 0.33],
            [0.33, 0.33],
            [0.33, 1],
            [-0.33, 1],
            [-0.33, 0.33],
            [-1, 0.33],
        ]
    )
    cross_outline = (
        0.0115 * (cross_outline @ np.array([port_axis, port_axis[::-1] * [-1, 1]]))
        + pad
    )
    mesh.slab(_round_loop(cross_outline), 0.0628, 0.0646, (54, 49, 56), (42, 38, 46), 1)

    for index, pixel in enumerate([(296, 384), (345, 373)]):
        height = [0.070, 0.069][index]
        thumb = _on_plane(pixel, height)[:2]
        mesh.cylinder(
            thumb,
            [
                (0.0134, 0.035, (17, 16, 22)),
                (0.0142, 0.049, (21, 18, 24)),
                (0.0119, 0.055, (27, 24, 31)),
                (0.006, height - 0.012, (31, 27, 34)),
                (0.0092, height - 0.009, (23, 21, 27)),
                (0.0115, height - 0.0045, (38, 35, 42)),
                (0.0108, height - 0.0007, (52, 48, 54)),
                (0.0089, height, (44, 41, 48)),
            ],
            1,
            segments=20,
        )

    orange = _on_plane((319, 344), 0.057)[:2]
    mesh.cylinder(
        orange,
        [
            (0.0108, 0.049, (55, 43, 36)),
            (0.0102, 0.054, (119, 60, 31)),
            (0.0087, 0.056, (245, 119, 31)),
            (0.0078, 0.057, (253, 155, 56)),
        ],
        1,
        flatten=0.68,
        direction=port_axis,
    )
    mesh.cylinder(
        orange + port_axis * 0.0008,
        [(0.0034, 0.0567, (192, 76, 25)), (0.0026, 0.0574, (210, 105, 34))],
        1,
        segments=12,
        flatten=0.77,
        direction=port_axis,
    )
    for pixel, ink in zip(
        [(364, 337), (376, 347), (367, 359), (353, 351)],
        [(156, 154, 140), (145, 146, 151), (151, 154, 164), (109, 117, 120)],
    ):
        switch = _on_plane(pixel, 0.059)[:2]
        mesh.cylinder(
            switch,
            [
                (0.006, 0.043, (31, 28, 32)),
                (0.0058, 0.054, (32, 29, 35)),
                (0.0048, 0.058, (53, 51, 55)),
                (0.0041, 0.059, (71, 69, 70)),
            ],
            1,
            segments=16,
        )
        mesh.cylinder(
            switch, [(0.0015, 0.0588, ink), (0.0012, 0.0595, ink)], 1, segments=9
        )


def _red_housing(mesh):
    rim = _on_plane(
        [
            (219, 235),
            (223, 224),
            (240, 216),
            (257, 209),
            (271, 209),
            (280, 216),
            (288, 231),
            (295, 251),
            (293, 260),
            (285, 269),
            (269, 275),
            (246, 279),
            (232, 276),
            (225, 267),
        ],
        0.023,
    )
    outline = _round_loop(rim[:, :2], 1)
    if _area(outline) < 0:
        outline = outline[::-1]
    rings = [
        _xyz(_inset(outline, inset), height)
        for inset, height in [
            (0.0045, 0.0048),
            (0.001, 0.008),
            (0, 0.013),
            (0.0007, 0.0155),
            (-0.00035, 0.018),
            (0, 0.023),
            (0.0016, 0.027),
            (0.005, 0.031),
            (0.011, 0.0315),
        ]
    ]
    mesh.shell(
        rings,
        [
            (106, 20, 23),
            (139, 27, 32),
            (147, 26, 32),
            (60, 30, 35),
            (137, 29, 36),
            (161, 32, 42),
            (183, 43, 54),
            (190, 49, 61),
            (182, 44, 53),
        ],
        2,
    )
    center = _on_plane((254, 249), 0.033)[:2]
    mesh.cylinder(
        center,
        [
            (0.0254, 0.0306, (66, 63, 121)),
            (0.0255, 0.0325, (72, 124, 199)),
            (0.0249, 0.0343, (75, 136, 210)),
            (0.018, 0.0349, (76, 133, 204)),
            (0.0073, 0.0347, (61, 112, 184)),
            (0.00685, 0.0336, (57, 54, 114)),
            (0.00645, 0.0306, (79, 15, 35)),
        ],
        2,
        segments=40,
        cap=False,
    )
    mesh.cylinder(
        center,
        [(0.00665, 0.0297, (101, 14, 31)), (0.0066, 0.0318, (103, 18, 31))],
        2,
        segments=24,
    )
    tab = _on_plane([(219, 217), (247, 207), (252, 219), (224, 229)], 0.033)
    tab = _round_loop(tab[:, :2])
    mesh.slab(tab, 0.015, 0.033, (41, 97, 166), (32, 62, 115), 2)


def _carton(mesh):
    sections = [
        ((323, 167), (386, 150), 0.0025, 0.0025, 0.039, 0.000),
        ((323, 164), (388, 147), 0.008, 0.008, 0.040, 0.003),
        ((322, 147), (390, 133), 0.027, 0.027, 0.041, 0.003),
        ((321, 120), (394, 107), 0.058, 0.057, 0.045, 0.005),
        ((322, 98), (398, 86), 0.084, 0.085, 0.050, 0.005),
        ((319, 77), (400, 73), 0.111, 0.112, 0.045, 0.006),
        ((315, 54), (406, 58), 0.134, 0.133, 0.036, 0.002),
        ((313, 28), (403, 29), 0.157, 0.156, 0.019, 0.001),
        ((312, 18), (401, 10), 0.166, 0.173, 0.012, 0.000),
        ((309, 11), (398, 2), 0.171, 0.179, 0.006, 0.000),
    ]
    grid = []
    for low, high, height_left, height_right, depth, bulge in sections:
        left, right = _on_plane([low, high], np.array([height_left, height_right]))
        edge = right[:2] - left[:2]
        normal = edge[::-1] * [-1, 1] / np.linalg.norm(edge)
        delta = np.r_[normal * depth, 0.0]
        bow = np.r_[-normal * bulge, 0.0]
        front_center = (left + right) / 2.0 + bow
        back_center = front_center + 1.13 * delta - 0.9 * bow
        grid.append(
            [left, front_center, right, right + delta, back_center, left + delta]
        )
    grid = np.array(grid)

    for panel_index in range(6):
        right_edge = (panel_index + 1) % 6
        columns = [19, 19, 8, 12, 12, 8][panel_index]
        base_color = [
            (217, 208, 215),
            (220, 212, 218),
            (219, 214, 216),
            (215, 207, 211),
            (213, 206, 210),
            (202, 191, 196),
        ][panel_index]
        for section in range(len(sections) - 1):
            bounds = grid[
                [section, section, section + 1, section + 1],
                [panel_index, right_edge, right_edge, panel_index],
            ]
            rows = [1, 6, 8, 8, 7, 6, 5, 3, 3][section]
            if panel_index >= 2:
                rows = max(1, rows // 2)
            name = (
                f"carton{panel_index}_{section}" if panel_index in (0, 1, 5) else None
            )
            if panel_index in (2, 3, 4):
                columns = min(columns, 4)
            tint = (
                np.array(base_color)
                if section >= 4
                else np.array(base_color) * (0.68 + section * 0.070)
            )
            mesh.sheet(bounds, columns, rows, tint, 3, swatch=name)
    mesh.put(grid[0], [[1, 5, 0], [1, 4, 5], [1, 3, 4], [1, 2, 3]], (169, 142, 118), 3)
    mesh.put(grid[-1], [[0, 5, 1], [1, 5, 4], [1, 4, 3], [1, 3, 2]], (242, 238, 237), 3)


def _desk_accessories(mesh):
    connector = _on_plane([(201, 174), (235, 167), (249, 200), (210, 207)], 0.023)
    connector_outline = _round_loop(connector[:, :2])
    mesh.slab(connector_outline, 0.002, 0.023, (33, 30, 38), (22, 20, 22))

    cord_pixels = [
        (248, 190),
        (277, 201),
        (286, 218),
        (289, 240),
        (298, 263),
        (317, 270),
        (347, 270),
        (376, 265),
        (402, 255),
        (419, 238),
        (428, 215),
        (432, 187),
        (433, 168),
    ]
    cord = _on_plane(
        cord_pixels,
        np.array(
            [
                0.015,
                0.011,
                0.009,
                0.008,
                0.007,
                0.006,
                0.006,
                0.007,
                0.009,
                0.011,
                0.012,
                0.012,
                0.012,
            ]
        ),
    )
    _tube(
        mesh,
        _round_loop(np.concatenate([cord, cord[-2:0:-1]]))[: 2 * len(cord) - 2],
        0.0022,
        (34, 28, 40),
    )
    cable_tip = _on_plane(
        [(427, 171), (431, 158), (436, 158), (437, 168), (434, 179)], 0.018
    )
    mesh.slab(_round_loop(cable_tip[:, :2]), 0.009, 0.018, (29, 26, 34), (41, 36, 45))

    front_bottom = _on_plane([(222, 131), (292, 135)], 0.0025)
    front_top = _on_plane([(216, 42), (296, 45)], np.array([0.110, 0.114]))
    holder_front = np.array(
        [front_bottom[0], front_bottom[1], front_top[1], front_top[0]]
    )
    holder_axis = np.diff(front_bottom[:, :2], axis=0)[0]
    holder_depth = np.r_[holder_axis[::-1] * [-1, 1] * 0.75, 0.0]
    holder_back = holder_front + holder_depth
    mesh.sheet(holder_front, 15, 17, (53, 43, 46), swatch="holder")
    mesh.put(
        np.concatenate([holder_front, holder_back]),
        [
            (0, 3, 7),
            (0, 7, 4),
            (1, 5, 6),
            (1, 6, 2),
            (4, 7, 6),
            (4, 6, 5),
            (0, 4, 5),
            (0, 5, 1),
        ],
        (42, 39, 56),
    )
    for offset, height, radius, tint in [
        (0.00, 0.153, 0.0031, (46, 76, 112)),
        (0.010, 0.131, 0.004, (192, 196, 62)),
        (0.018, 0.167, 0.0033, (45, 107, 85)),
        (0.027, 0.145, 0.0039, (62, 82, 145)),
        (0.034, 0.151, 0.0039, (177, 143, 68)),
    ]:
        base = (
            0.60 * front_bottom[1, :2]
            + 0.40 * front_bottom[0, :2]
            + 0.57 * holder_depth[:2]
        )
        center = base + [offset, 0.17 * offset]
        mesh.cylinder(
            center,
            [
                (radius, 0.052, tint),
                (radius, height - 0.001, tint),
                (0.75 * radius, height, tint),
            ],
            segments=8,
        )

    back_edge, short_edge, bottom_edge = _on_plane(
        [(115, 24), (21, 69), (208, 112)], np.array([0.053, 0.058, 0.029]), frame=5
    )
    phone = _quad_from_three(back_edge, short_edge, bottom_edge)
    mesh.slab(phone, 0.002, phone[:, 2], (184, 174, 158), (127, 118, 108), top=False)
    mesh.sheet(phone, 16, 19, (186, 176, 161), swatch="phone")
    handset = _on_plane(
        [
            (29, 79),
            (47, 71),
            (80, 83),
            (114, 107),
            (159, 138),
            (163, 153),
            (151, 163),
            (131, 159),
            (117, 149),
            (74, 120),
            (40, 103),
            (29, 98),
        ],
        0.071,
        frame=5,
    )
    handset_outline = _round_loop(handset[:, :2])
    if _area(handset_outline) < 0:
        handset_outline = handset_outline[::-1]
    mesh.shell(
        [
            _xyz(_inset(handset_outline, 0.0065), 0.024),
            _xyz(handset_outline, 0.046),
            _xyz(_inset(handset_outline, 0.0025), 0.066),
            _xyz(_inset(handset_outline, 0.0075), 0.072),
        ],
        [(111, 103, 94), (150, 142, 133), (185, 177, 169), (189, 181, 169)],
    )

    coiled = _on_plane(
        [
            (153, 107),
            (169, 114),
            (167, 133),
            (178, 145),
            (192, 157),
            (204, 175),
            (207, 185),
            (217, 192),
        ],
        np.array([0.046, 0.020, 0.010, 0.009, 0.008, 0.007, 0.008, 0.009]),
    )
    anchors = np.linspace(0, 1, len(coiled))
    phases = np.linspace(0.0, 1.0, 109)
    centers = np.column_stack([np.interp(phases, anchors, coord) for coord in coiled.T])
    across = np.gradient(centers[:, :2], axis=0)[:, ::-1] * [-1, 1]
    across /= np.linalg.norm(across, axis=1, keepdims=True)
    angle = phases * 2 * np.pi * 19
    centers[:, :2] += across * (0.0045 * np.cos(angle))[:, None]
    centers[:, 2] += 0.0045 * np.sin(angle)
    _tube(mesh, centers, 0.0015, (166, 155, 145), sides=4)

    keyboard_near_left, keyboard_near_right, keyboard_far_left = _on_plane(
        [(428, 81), (538, 118), (522, -117)], 0.026, frame=5
    )
    keyboard = _quad_from_three(
        keyboard_near_left, keyboard_near_right, keyboard_far_left
    )
    mesh.slab(keyboard, 0.002, 0.026, (182, 174, 169), (141, 132, 128), top=False)
    mesh.sheet(keyboard, 14, 28, (176, 166, 165), swatch="keyboard")

    mug = _on_plane((376, 22), 0.085, frame=5)[:2]
    mesh.cylinder(
        mug,
        [
            (0.027, 0.002, (191, 182, 173)),
            (0.028, 0.015, (198, 190, 185)),
            (0.034, 0.080, (223, 214, 209)),
            (0.034, 0.086, (228, 219, 213)),
            (0.0315, 0.086, (214, 205, 194)),
            (0.030, 0.075, (170, 157, 144)),
            (0.025, 0.010, (151, 135, 123)),
        ],
        segments=22,
        cap=False,
    )
    theta = np.linspace(-1.18, 1.18, 13)
    handle = np.column_stack(
        (
            mug[0] - 0.022 - 0.022 * np.cos(theta),
            np.full(len(theta), mug[1]),
            0.049 + 0.023 * np.sin(theta),
        )
    )
    _tube(mesh, handle, 0.004, (213, 204, 199), sides=7)


def _construct():
    mesh = _Mesh()
    _environment_structure(mesh)
    _paperwork(mesh)
    _desk_accessories(mesh)
    _gamepad(mesh)
    _red_housing(mesh)
    _carton(mesh)
    return mesh


def build_context(frames, rows):
    """Recover the desk frame from two physical edges and bake image colors onto its mesh."""
    global _CORNER, _DESK_AXES, _REFERENCE_POSES, _SWATCHES
    _CORNER, _DESK_AXES = desk_basis(frames, rows)
    _REFERENCE_POSES = dict(enumerate(rows))
    _SWATCHES = {}
    mesh = _construct()
    _SWATCHES = sample_textures(mesh, frames, rows, _DESK_AXES, _CORNER)
    return _construct().finish()
