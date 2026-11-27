"""Parametric room surfaces in the coordinate frame of the photographed desk."""

import numpy as np

ORIGIN = np.array([0.0739, 0.5202, 0.9241])

DESK_AXES = np.array(
    [[0.6902, -0.7232, -0.0235], [-0.2853, -0.2421, -0.9274], [0.6650, 0.6468, -0.3734]]
)

FLOOR = -0.716


def unit(vector):
    return np.asarray(vector) / np.linalg.norm(vector)


def angles(count):
    return np.linspace(0, 2 * np.pi, count, endpoint=False)


class Mesh:
    def __init__(self):
        self.vertices = []
        self.triangles = []
        self.colors = []
        self.labels = []
        self.count = 0

    def add(self, points, faces, color, label=0):
        points = np.asarray(points, dtype=float).reshape(-1, 3)
        faces = np.asarray(faces, dtype=int).reshape(-1, 3)
        self.vertices.append(points)
        self.colors.append(np.broadcast_to(color, points.shape))
        self.triangles.append(faces + self.count)
        self.labels.append(np.full(len(faces), label, dtype=np.int32))
        self.count += len(points)

    def grid(self, points, color, label=0, wrap=False, reverse=False):
        rows, cols = points.shape[:2]
        ii, jj = np.indices((rows if wrap else rows - 1, cols - 1))
        start = ii * cols + jj
        after = ((ii + 1) % rows) * cols + jj
        faces = np.stack(
            [start, after, after + 1, start, after + 1, start + 1], axis=-1
        ).reshape(-1, 3)
        if reverse:
            faces = faces[:, ::-1]
        rgb = np.asarray(color)
        self.add(points, faces, rgb.reshape(-1, 3), label)

    def panel(
        self, corner, across, along, color, label=0, segments=(1, 1), reverse=False
    ):
        aa, bb = np.meshgrid(
            np.linspace(0, 1, segments[0] + 1),
            np.linspace(0, 1, segments[1] + 1),
            indexing="ij",
        )
        points = (
            np.asarray(corner)
            + aa[..., None] * np.asarray(across)
            + bb[..., None] * np.asarray(along)
        )
        rgb = color(points, aa, bb) if callable(color) else color
        self.grid(points, rgb, label, reverse=reverse)

    def disk(self, boundary, center, color, label=0, reverse=False):
        count = len(boundary)
        idx = np.arange(count)
        faces = np.array([np.full(count, count), idx, (idx + 1) % count]).T
        if reverse:
            faces = faces[:, ::-1]
        rgb = np.asarray(color)
        if rgb.shape == np.shape(boundary):
            rgb = np.vstack([rgb, rgb.mean(axis=0)])
        self.add(np.vstack([boundary, center]), faces, rgb, label)

    def solid(
        self, lower, upper, color, label=0, factors=(0.82, 1.0, 0.84, 0.67), cap=True
    ):
        lower, upper = np.asarray(lower), np.asarray(upper)
        size = len(lower)
        if cap:
            self.add(
                lower,
                [[0, k + 1, k] for k in range(1, size - 1)],
                np.asarray(color) * 0.70,
                label,
            )
            self.add(upper, [[0, k, k + 1] for k in range(1, size - 1)], color, label)
        for idx in range(size):
            nxt = (idx + 1) % size
            rgb = np.asarray(color) * factors[idx % len(factors)]
            self.add(
                [lower[idx], lower[nxt], upper[nxt], upper[idx]],
                [[0, 1, 2], [0, 2, 3]],
                rgb,
                label,
            )

    def box(self, low, high, color, label=0, yaw=0):
        xmin, ymin, zmin = low
        xmax, ymax, zmax = high
        xy = np.array([[xmin, ymin], [xmax, ymin], [xmax, ymax], [xmin, ymax]])
        if yaw:
            center = (xy[0] + xy[2]) / 2
            cosine, sine = np.cos(yaw), np.sin(yaw)
            xy = center + (xy - center) @ np.array([[cosine, sine], [-sine, cosine]])
        self.solid(
            np.c_[xy, np.full(4, zmin)], np.c_[xy, np.full(4, zmax)], color, label
        )

    def revolution(
        self, xy, profile, palette, label=0, count=48, shader=None, caps=(False, False)
    ):
        """Profile travels up the outside, then down the inside if hollow."""
        profile = np.asarray(profile)
        theta = angles(count)
        radial = np.stack([np.cos(theta), np.sin(theta)], axis=-1)
        points = np.empty((count, len(profile), 3))
        points[..., :2] = np.asarray(xy) + radial[:, None] * profile[None, :, :1]
        points[..., 2] = profile[None, :, 1]
        color = np.broadcast_to(np.asarray(palette, dtype=float), points.shape)
        if shader is not None:
            color = shader(color, theta[:, None], points)
        self.grid(points, color, label, wrap=True)
        for index, close in zip((0, -1), caps):
            if close:
                self.disk(
                    points[:, index],
                    (*xy, profile[index, 1]),
                    color[:, index],
                    label,
                    reverse=index == 0,
                )

    def tube(
        self, centers, widths, color, label=0, sides=10, reference=(0, 0, 1), shape=1.0
    ):
        centers = np.asarray(centers, dtype=float)
        tangent = np.gradient(centers, axis=0)
        tangent /= np.linalg.norm(tangent, axis=1, keepdims=True)
        normal = np.cross(tangent, reference)
        normal /= np.linalg.norm(normal, axis=1, keepdims=True)
        binormal = np.cross(tangent, normal)
        dims = np.broadcast_to(np.asarray(widths).reshape(-1, 2), (len(centers), 2))
        theta = angles(sides)
        cosine, sine = np.cos(theta), np.sin(theta)
        cosine = np.copysign(np.abs(cosine) ** shape, cosine)
        sine = np.copysign(np.abs(sine) ** shape, sine)
        points = (
            centers[None]
            + cosine[:, None, None] * normal[None] * dims[None, :, :1]
            + sine[:, None, None] * binormal[None] * dims[None, :, 1:]
        )
        base = np.broadcast_to(color, (len(centers), 3))
        rgb = base[None] * (0.88 + 0.12 * np.cos(theta[:, None, None] - 0.9))
        self.grid(points, rgb, label, wrap=True)
        self.disk(points[:, 0], centers[0], rgb[:, 0], label, reverse=True)
        self.disk(points[:, -1], centers[-1], rgb[:, -1], label)

    def ellipsoid(
        self,
        center,
        radii,
        color,
        count=20,
        levels=10,
        transform=None,
        shade=None,
        label=0,
    ):
        theta = angles(count)
        lat = np.linspace(-np.pi / 2, np.pi / 2, levels + 1)[1:-1]
        normal = np.empty((count, len(lat), 3))
        normal[..., 0] = np.cos(theta[:, None]) * np.cos(lat)
        normal[..., 1] = np.sin(theta[:, None]) * np.cos(lat)
        normal[..., 2] = np.sin(lat)
        span = normal * np.asarray(radii)
        tip = np.array([0, 0, radii[2]], dtype=float)
        if transform is not None:
            span, tip = span @ transform.T, tip @ transform.T
        points = np.asarray(center) + span
        rgb = np.broadcast_to(color, points.shape)
        if shade is not None:
            rgb = shade(normal)
        else:
            rgb = (
                rgb
                * (
                    0.76 + 0.24 * (0.5 + 0.5 * (normal @ np.array([-0.46, 0.27, 0.84])))
                )[..., None]
            )
        self.grid(points, rgb, label, wrap=True)
        self.disk(points[:, 0], center - tip, rgb[:, 0], label, True)
        self.disk(points[:, -1], center + tip, rgb[:, -1], label)

    def finish(self):
        return (
            np.concatenate(self.vertices) @ DESK_AXES.T + ORIGIN,
            np.concatenate(self.triangles).astype(np.int32),
            np.clip(np.concatenate(self.colors), 0, 255),
            np.concatenate(self.labels),
        )


def interpolate_path(points, steps=3):
    points = np.asarray(points)
    padded = np.vstack([points[0], points, points[-1]])
    value = np.arange(steps, dtype=float)[:, None] / steps
    parts = []
    for idx in range(len(points) - 1):
        prev, start, end, following = padded[idx : idx + 4]
        parts.append(
            0.5
            * (
                2 * start
                + (-prev + end) * value
                + (2 * prev - 5 * start + 4 * end - following) * value**2
                + (-prev + 3 * start - 3 * end + following) * value**3
            )
        )
    return np.vstack([*parts, points[-1]])


def rounded_rectangle(length, width, radius, count=5):
    halfsize = np.array([length, width]) / 2
    quadrants = np.array([[1, 1], [-1, 1], [-1, -1], [1, -1]])
    theta = np.arange(4)[:, None] * (np.pi / 2) + np.linspace(0, np.pi / 2, count)[None]
    center = quadrants * (halfsize - radius)
    return (
        center[:, None] + radius * np.stack([np.cos(theta), np.sin(theta)], axis=-1)
    ).reshape(-1, 2)


def desktop(mesh):
    steps = [
        (0, 0),
        (0.835, 0),
        (0.835, 0.350),
        (1.706, 0.350),
        (1.706, 1.690),
        (0, 1.690),
    ]

    def veneer(points, across, along):
        depth, length, _ = np.moveaxis(points, -1, 0)
        grain = (
            2.5 * np.sin(255 * length + 2.4 * np.sin(5 * depth))
            + 1.9 * np.sin(133 * length + 6 * depth)
            + 2.8 * np.sin(63 * length + 8 * depth)
            + 2.1 * np.sin(17 * length + 24 * depth)
            + 1.5 * np.cos(29 * length - 5 * depth)
        )
        lighting = (
            10 * (1 - depth / 1.7) + 3 * np.cos(3 * length) - 3 * np.sin(5 * depth)
        )
        return np.array([203, 193, 184]) + (grain + lighting)[..., None]

    mesh.panel((0, 0, 0), (0.835, 0, 0), (0, 1.690, 0), veneer, segments=(14, 26))
    mesh.panel(
        (0.835, 0.350, 0), (0.871, 0, 0), (0, 1.340, 0), veneer, segments=(11, 21)
    )
    mesh.panel(
        (0, 0, -0.0285), (0.835, 0, 0), (0, 1.690, 0), (98, 87, 80), reverse=True
    )
    mesh.panel(
        (0.835, 0.350, -0.0285),
        (0.871, 0, 0),
        (0, 1.340, 0),
        (98, 87, 80),
        reverse=True,
    )
    for index, (start, end) in enumerate(zip(steps, steps[1:] + steps[:1])):
        rgb = [
            (239, 234, 230),
            (211, 205, 195),
            (228, 224, 215),
            (188, 181, 173),
            (166, 157, 148),
            (191, 184, 175),
        ][index]
        mesh.panel(
            (*start, -0.0285), (*np.subtract(end, start), 0), (0, 0, 0.0285), rgb
        )
    for zpos, rgb in [
        (0.095, (21, 32, 55)),
        (1.55, (59, 63, 73)),
        (0.50, (29, 29, 33)),
        (1.57, (39, 37, 37)),
    ]:
        center = 0.631 if zpos in (0.095, 1.55) else 1.37
        extent = 0.13 if zpos in (0.095, 1.55) else 0.062
        mesh.box(
            (center - extent, zpos - 0.031, FLOOR + 0.041),
            (center + extent, zpos + 0.031, -0.025),
            rgb,
        )
        footprint = rounded_rectangle(0.79 if center < 0.8 else 0.56, 0.078, 0.033, 4)
        footprint = footprint + [center - 0.155, zpos]
        mesh.solid(
            np.c_[footprint, np.full(len(footprint), FLOOR + 0.004)],
            np.c_[
                footprint * 0.98 + [0.02 * (center - 0.155), 0.02 * zpos],
                np.full(len(footprint), FLOOR + 0.041),
            ],
            np.array(rgb) + [6, 5, 5],
            factors=(0.54,),
        )


def ground_and_wall(mesh):
    def concrete(points, _across, _along):
        xx, zz = points[..., 0], points[..., 1]
        ripples = (
            5 * np.sin(xx * 7.66 + zz * 7.5)
            + 5 * np.cos(xx * 10.29 - zz * 5.4)
            + 4 * np.cos(xx * 3.1 + zz * 2.6)
            + 3 * np.sin(xx * 39 - zz * 31.7)
        )
        front = 5 * np.clip((2 - zz) / 2, 0, 1) + 6 * np.clip(xx - 1.1, 0, 1)
        bloom = 6 * np.exp(-((xx - 1.8) ** 2 + (zz + 0.6) ** 2) * 1.4)
        side = 7 * np.exp(-((0.13 * xx - 0.1 * zz + 1) ** 2))
        near = np.clip((zz + 1) * 0.15, 0, 1)
        return (
            np.array([66, 56, 50])
            + (ripples + front + bloom + side)[..., None]
            + near[..., None] * [-2, 4, 9]
        )

    mesh.panel(
        (-3.1, -3.8, FLOOR), (9.1, 0, 0), (0, 9.8, 0), concrete, segments=(31, 33)
    )
    mesh.panel(
        (6.0, -3.8, FLOOR), (20.0, 0, 0), (0, 9.8, 0), concrete, segments=(8, 19)
    )
    mesh.panel((-3.1, 6, FLOOR), (29.1, 0, 0), (0, 3.8, 0), concrete, segments=(10, 4))
    mesh.panel(
        (-3.1, 9.8, FLOOR), (29.1, 0, 0), (0, 0, 4.4), (139, 142, 169), segments=(12, 5)
    )
    for index, xval in enumerate([3.0, 5.2, 7.5, 9.1, 12.0, 12.7, 16.2, 21.0]):
        mesh.panel(
            (xval, 9.785, FLOOR),
            (0.026 + (index % 3) * 0.036, 0, 0),
            (0, 0, 4.1),
            (106, 103, 128),
        )
    mesh.box((8.10, 9.51, FLOOR), (8.73, 9.77, 1.13), (51, 58, 87))
    mesh.panel((8.15, 9.50, FLOOR + 0.10), (0.54, 0, 0), (0, 0, 1.00), (227, 228, 230))
    mesh.box((8.87, 9.61, FLOOR), (10.26, 9.79, 1.62), (176, 139, 101))
    mesh.box((10.30, 9.60, FLOOR), (10.72, 9.80, 1.80), (171, 169, 178))
    mesh.box((-0.97, 3.95, FLOOR), (0.69, 4.02, 0.46), (145, 110, 80), yaw=-0.04)
    mesh.panel(
        (-0.91, 3.904, FLOOR + 0.052), (1.54, -0.061, 0), (0, 0, 1.088), (172, 145, 132)
    )
    for start, direction in [
        ((-0.21, 1.92), (0.154, -0.051)),
        ((-0.032, 1.868), (0.075, -0.045)),
        ((0.993, -0.488), (0.161, 0.007)),
        ((1.031, -0.576), (0.021, 0.211)),
        ((1.071, -0.461), (0.130, 0.009)),
    ]:
        side = 0.013 * unit([-direction[1], direction[0]])
        mesh.panel(
            (*start, FLOOR + 0.001), (*direction, 0), (*side, 0), (151, 140, 111)
        )
    for xval in [1.97, 3.95, 6.05, 10.8]:
        mesh.panel(
            (xval, -4.0, FLOOR + 0.001), (0.009, 0, 0), (1.08, 13.77, 0), (63, 55, 51)
        )
    for start, end in [
        ((4.04, 5.14, FLOOR), (4.71, 4.96, 2.1)),
        ((6.20, 4.90, FLOOR), (5.18, 4.83, 2.21)),
        ((6.37, 1.72, FLOOR), (5.89, 3.29, 2.36)),
        ((2.96, 2.51, FLOOR), (5.89, 3.29, 2.36)),
        ((5.6, 4.57, FLOOR), (5.89, 3.29, 2.36)),
    ]:
        mesh.tube([start, end], (0.012, 0.012), (43, 42, 49), sides=6)


def computer(mesh):
    mesh.revolution(
        (0.724, 0.855),
        [
            (0.136, 0.002),
            (0.143, 0.004),
            (0.144, 0.011),
            (0.138, 0.020),
            (0.112, 0.026),
        ],
        [(71, 65, 66), (133, 127, 123), (184, 180, 174), (97, 94, 90), (44, 43, 46)],
        count=34,
        caps=(True, True),
    )
    mesh.box((0.734, 0.815, 0.012), (0.803, 0.898, 0.160), (41, 40, 44))
    pivot = np.array([0.691, 0.853, 0.069])
    horizontal = np.array([-0.020, -0.9998, 0.0])
    vertical = np.array([0.271, -0.0054, 0.9626])
    backing = np.cross(vertical, horizontal)

    def screen_point(uu, vv, height):
        return pivot + uu * horizontal + vv * vertical + height * backing

    horiz, vert = 0.466, 0.365
    main_outline = np.array(
        [[-horiz / 2, 0], [horiz / 2, 0], [horiz / 2, vert], [-horiz / 2, vert]]
    )
    front = [screen_point(uu, vv, 0.0) for uu, vv in main_outline]
    back = [
        screen_point(uu * 0.97, 0.018 + 0.90 * vv, 0.031) for uu, vv in main_outline
    ]
    mesh.solid(back, front, (168, 169, 169), factors=(0.51, 0.86, 0.76, 0.59))
    mesh.panel(
        screen_point(-horiz / 2, 0, -0.001),
        horiz * horizontal,
        vert * vertical,
        (172, 173, 170),
    )

    def glass(points, aa, bb):
        light = 4 * np.sin(2.7 * aa) + 6 * bb + 3 * np.sin(5.5 * bb + aa)
        return np.array([23, 25, 26]) + light[..., None]

    mesh.panel(
        screen_point(-horiz / 2 + 0.012, 0.020, -0.0016),
        (horiz - 0.025) * horizontal,
        (vert - 0.033) * vertical,
        glass,
        segments=(6, 5),
    )
    mesh.panel(
        screen_point(horiz / 2 - 0.0045, 0.000, -0.002),
        -0.006 * horizontal,
        vert * vertical,
        (215, 216, 213),
        reverse=True,
    )

    pos = np.array([0.437, 0.825])
    yaw = -0.055
    flat = rounded_rectangle(0.196, 0.483, 0.013, 4)
    mat = np.array([[np.cos(yaw), np.sin(yaw)], [-np.sin(yaw), np.cos(yaw)]])
    corners = flat @ mat + pos
    mesh.solid(
        np.c_[corners, np.full(len(corners), 0.001)],
        np.c_[corners, 0.012 + flat[:, 0] * 0.069],
        (90, 89, 84),
        factors=(0.52,),
    )
    for row in range(6):
        for col in range(19):
            if (row == 1 and col in [14]) or (
                row == 0 and (col in range(3, 8) or col in [13, 14, 16])
            ):
                continue
            spot = np.array([-0.063 + row * 0.028, -0.218 + col * 0.024])
            center = pos + spot @ mat
            spread = np.array([0.011, 0.0094])
            rgb = np.array([44, 45, 43]) + 4 * ((row + 2 * col) % 4)
            base = 0.012 + spot[0] * 0.069
            mesh.box(
                (*tuple(center - spread), base),
                (*tuple(center + spread), base + 0.0055),
                rgb,
                yaw=yaw,
            )
            if (col + row) % 3:
                mesh.panel(
                    (*tuple(center - [0.0013, 0.0021]), base + 0.0057),
                    (0.0028, 0, 0),
                    (0, 0.0042, 0),
                    (106, 106, 102),
                )
    mesh.box((0.366, 0.818, 0.006), (0.386, 0.940, 0.0165), (38, 39, 40), yaw=yaw)
    spin = -0.30
    mat_mouse = np.array(
        [[np.cos(spin), -np.sin(spin), 0], [np.sin(spin), np.cos(spin), 0], [0, 0, 1]]
    )
    mesh.ellipsoid(
        (0.240, 0.527, 0.013),
        (0.053, 0.032, 0.017),
        (39, 39, 43),
        count=20,
        levels=7,
        transform=mat_mouse,
    )
    mesh.ellipsoid(
        (0.269, 0.517, 0.026), (0.009, 0.004, 0.005), (65, 62, 62), count=10, levels=5
    )


def book_and_globe(mesh):
    corner = np.array([0.565, 0.253, 0])
    spine = np.array([0.280, -0.009, 0])
    page = np.array([-0.009, -0.200, 0])
    thick = np.array([0, 0, 0.047])
    paper_bottom = np.array(
        [corner, corner + page, corner + spine + page, corner + spine]
    )
    mesh.solid(
        paper_bottom + [0, 0, 0.002],
        paper_bottom + thick,
        (230, 225, 219),
        factors=(0.88, 0.98, 0.82, 0.72),
    )
    mesh.solid(paper_bottom + [0, 0, 0.001], paper_bottom + [0, 0, 0.003], (29, 32, 53))
    cover = (paper_bottom - paper_bottom.mean(0)) * 1.014 + paper_bottom.mean(0)
    mesh.solid(cover + thick, cover + thick + [0, 0, 0.002], (36, 45, 58))
    for row in range(1, 7):
        mesh.panel(
            corner + page + [-0.00002, -0.00045, 0.005 + 0.0058 * row],
            spine,
            (0, 0, 0.0005),
            (185, 181, 176),
        )

    def paper_art(points, uu, vv):
        rect = (0.155 < uu) & (uu < 0.864) & (0.144 < vv) & (vv < 0.827)
        border = (uu > 0.083) & (uu < 0.916) & (vv > 0.091) & (vv < 0.898) & ~rect
        grain = (0.5 + 0.5 * np.sin(87 * uu + 40 * vv + 4 * np.cos(57 * vv))) * (
            0.5 + 0.5 * np.sin(95 * vv - 17 * uu)
        )
        image = np.array([87, 89, 68]) + np.array([80, 69, 51]) * grain[..., None]
        gray_house = (uu > 0.293) & (uu < 0.646) & (vv > 0.232) & (vv < 0.526)
        image[gray_house] = (
            np.array([170, 164, 145]) + (grain[gray_house] * 47)[:, None]
        )
        notch = (uu > 0.335) & (uu < 0.504) & (vv > 0.339) & (vv < 0.441)
        image[notch] *= 0.36
        return np.where(
            rect[..., None],
            image,
            np.where(border[..., None], [59, 69, 45], [31, 37, 59]),
        )

    mesh.panel(
        corner + thick + [0, 0, 0.0022],
        spine,
        page,
        paper_art,
        segments=(21, 15),
        reverse=True,
    )
    globe_pos = (1.273, 0.079, -0.323)
    near_left = np.array([1.039, 0.029, FLOOR + 0.003])
    across = np.array([0.292, -0.102, 0])
    sideways = np.array([0.069, 0.238, 0])
    foot = np.array(
        [
            near_left,
            near_left + across,
            near_left + across + sideways,
            near_left + sideways,
        ]
    )
    mesh.solid(
        foot, foot + [0, 0, 0.211], (193, 112, 39), factors=(0.94, 0.69, 0.75, 0.71)
    )
    mesh.panel(near_left + [0, -0.001, 0.008], across, (0, 0, 0.032), (221, 202, 184))

    def continents(normal):
        xx, yy, hh = np.moveaxis(normal, -1, 0)
        ocean = np.array([53, 147, 191])
        light = np.clip(
            0.80 + 0.21 * (normal @ np.array([-0.55, 0.12, 0.83])), 0.60, 1.08
        )
        bend = np.sin(7 * xx + 4 * hh) * np.cos(8 * yy - 5 * hh) + 0.35 * np.sin(
            19 * xx - 11 * hh + 12 * yy
        )
        lon = (np.arctan2(yy, xx) + np.pi) % (2 * np.pi)
        eastern = (lon + 0.85) % (2 * np.pi) - 0.85
        field = (
            np.exp(-(((lon - 4.0 + 0.55 * hh) / 1.05) ** 2) - ((hh - 0.34) / 0.50) ** 2)
            * 1.24
            + np.exp(
                -(((lon - 3.04 - 0.35 * hh) / 0.39) ** 2) - ((hh + 0.27) / 0.59) ** 2
            )
            * 0.91
            + np.exp(-(((lon - 1.34) / 0.68) ** 2) - ((hh - 0.32) / 0.56) ** 2) * 1.10
            + np.exp(
                -(((lon - 1.28 + 0.71 * hh) / 0.42) ** 2) - ((hh + 0.37) / 0.52) ** 2
            )
            * 1.19
            + np.exp(
                -(((eastern - 0.73 - 0.312 * hh) / 0.42) ** 2)
                - ((hh - 0.35) / 0.58) ** 2
            )
            * 0.91
            + np.exp(
                -(((eastern - 0.11 + 0.17 * hh) / 0.37) ** 2)
                - ((hh + 0.18) / 0.34) ** 2
            )
            * 0.84
            + np.exp(-(((lon - 4.90) / 0.31) ** 2) - ((hh + 0.54) / 0.28) ** 2) * 1.05
            + 0.28 * bend
        )
        land = np.clip((field - 0.62) * 4, 0, 1)
        ground = np.array([144, 163, 101]) + bend[..., None] * np.array([44, 17, 13])
        ground[(hh > 0.22) & (bend > 0.30)] += [25, -32, 1]
        return (ocean + (ground - ocean) * land[..., None]) * light[..., None]

    mesh.ellipsoid(
        globe_pos,
        (0.205, 0.205, 0.205),
        (47, 138, 184),
        count=36,
        levels=18,
        shade=continents,
    )


def drinks_and_decoration(mesh):
    def soda_print(rgb, theta, points):
        result = rgb.copy()
        yy = points[..., 2]
        white = np.abs(np.sin(2 * theta + 45 * yy + 0.6 * np.sin(98 * yy))) < 0.27
        red_body = (yy > 0.005) & (yy < 0.129)
        result[red_body & white] = [212, 194, 180]
        return result * (0.88 + 0.13 * np.cos(theta + 2.2))[..., None]

    for pos in [(0.244, 1.369), (1.476, 0.480)]:
        rows = [
            (0.033, 0),
            (0.034, 0.006),
            (0.033, 0.012),
            (0.033, 0.028),
            (0.033, 0.047),
            (0.033, 0.067),
            (0.033, 0.086),
            (0.033, 0.105),
            (0.033, 0.126),
            (0.028, 0.136),
            (0.029, 0.141),
            (0.025, 0.142),
            (0.019, 0.139),
        ]
        colors = (
            [(162, 155, 151)] * 2
            + [(171, 27, 40)] * 7
            + [(161, 33, 41)]
            + [(223, 222, 220)] * 2
            + [(165, 163, 157)]
        )
        mesh.revolution(
            pos, rows, colors, count=18, shader=soda_print, caps=(True, True)
        )

    mesh.revolution(
        (1.342, 0.838),
        [
            (0.038, 0),
            (0.051, 0.012),
            (0.071, 0.050),
            (0.077, 0.061),
            (0.075, 0.066),
            (0.070, 0.063),
            (0.062, 0.043),
            (0.035, 0.024),
        ],
        [
            (37, 33, 29),
            (32, 33, 31),
            (36, 42, 39),
            (39, 47, 47),
            (170, 169, 153),
            (38, 42, 44),
            (44, 47, 48),
            (30, 32, 34),
        ],
        count=21,
        caps=(True, True),
    )
    mesh.revolution(
        (1.438, 0.961),
        [
            (0.078, 0.005),
            (0.088, 0.015),
            (0.090, 0.021),
            (0.087, 0.024),
            (0.042, 0.016),
        ],
        [
            (64, 73, 94),
            (62, 84, 123),
            (112, 122, 140),
            (198, 192, 180),
            (216, 211, 201),
        ],
        count=18,
        caps=(True, True),
    )

    die = np.array([1.550, 0.708, 0.072])
    yaw = 0.42
    ux = np.array([np.cos(yaw), np.sin(yaw), 0])
    vz = np.array([-ux[1], ux[0], 0])
    up = np.array([0, 0, 1])
    border = rounded_rectangle(0.146, 0.146, 0.023, 4)
    piles = []
    for height, shrink in [
        (-0.071, 0.77),
        (-0.064, 0.94),
        (-0.048, 1.0),
        (0.050, 1.0),
        (0.065, 0.94),
        (0.071, 0.76),
    ]:
        piles.append(
            die + height * up + shrink * (border[:, :1] * ux + border[:, 1:] * vz)
        )
    mesh.grid(
        np.stack(piles, axis=1),
        np.array(
            [
                [212, 155, 15],
                [229, 172, 20],
                [240, 187, 23],
                [253, 217, 38],
                [252, 219, 48],
                [244, 222, 63],
            ]
        )[None]
        + np.zeros((len(border), 1, 3)),
        wrap=True,
    )
    mesh.disk(piles[0], die - 0.071 * up, (156, 119, 24), reverse=True)
    mesh.disk(piles[-1], die + 0.071 * up, (247, 219, 61))
    discs = [(die - 0.0733 * ux - t * vz + t * up, -vz, up) for t in [-0.040, 0, 0.040]]
    discs += [(die - 0.0733 * vz + t * ux + t * up, ux, up) for t in [-0.038, 0.038]]
    arc = angles(12)
    for center, right, upright in discs:
        circle = center + 0.0113 * (
            np.cos(arc)[:, None] * right + np.sin(arc)[:, None] * upright
        )
        mesh.disk(circle, center, (24, 22, 18))

    bear = np.array([1.554, 0.730, 0])

    def fur(at, radii, color, steps=11):
        mesh.ellipsoid(bear + at, radii, color, count=steps, levels=7)

    fur((0.084, 0.026, 0.148), (0.114, 0.124, 0.140), (108, 66, 47))
    fur((0.049, 0.004, 0.296), (0.116, 0.121, 0.106), (117, 74, 48), 20)
    fur((0.060, 0.111, 0.363), (0.044, 0.041, 0.046), (117, 72, 44))
    fur((0.061, -0.099, 0.365), (0.045, 0.039, 0.041), (110, 67, 46))
    fur((-0.047, 0.008, 0.283), (0.044, 0.054, 0.054), (222, 196, 160))
    fur((-0.081, 0.008, 0.302), (0.018, 0.027, 0.017), (54, 37, 30))
    for sign in [-1, 1]:
        fur((-0.027, sign * 0.046, 0.331), (0.010, 0.011, 0.012), (33, 25, 22), 10)
        fur((0.052, sign * 0.130, 0.123), (0.074, 0.056, 0.089), (113, 68, 46))
        fur((-0.008, sign * 0.086, 0.037), (0.091, 0.058, 0.057), (106, 64, 44))


def plants_and_print(mesh):
    rng = np.random.default_rng(121)
    pot = np.array([0.971, 1.612])
    mesh.revolution(
        pot,
        [
            (0.049, 0.003),
            (0.065, 0.093),
            (0.070, 0.096),
            (0.069, 0.107),
            (0.063, 0.107),
            (0.060, 0.095),
        ],
        [
            (81, 82, 70),
            (103, 105, 101),
            (117, 113, 110),
            (139, 135, 130),
            (94, 89, 80),
            (58, 48, 37),
        ],
        count=22,
        caps=(True, True),
    )
    for index in range(22):
        theta = index * 2.39996
        direction = np.array([np.cos(theta), np.sin(theta), 0])
        side = np.array([-np.sin(theta), np.cos(theta), 0])
        start = np.r_[pot, 0.094] + (index % 6) * 0.005 * direction
        height = rng.uniform(0.11, 0.39)
        length = rng.uniform(0.14, 0.41)
        width = rng.uniform(0.013, 0.024)
        curve = np.array(
            [[0.0, 0.0], [0.10, 0.23], [0.32, 0.55], [0.59, 0.80], [1.0, 1.0]]
        )
        pts = start + curve[:, :1] * length * direction + curve[:, 1:] * [0, 0, height]
        offsets = width * np.array([0.05, 0.81, 1.0, 0.62, 0.014])[:, None] * side
        mesh.grid(
            np.stack([pts - offsets, pts + [0, 0, 0.0035], pts + offsets], axis=1),
            np.broadcast_to(
                np.array([[65, 93, 38], [103, 128, 65], [62, 87, 43]])
                * (0.85 + 0.30 * rng.random()),
                (5, 3, 3),
            ),
        )
    pos = (1.386, 1.158)
    mesh.revolution(
        pos,
        [
            (0.030, 0.002),
            (0.039, 0.022),
            (0.037, 0.086),
            (0.039, 0.090),
            (0.034, 0.091),
        ],
        [
            (105, 110, 116),
            (157, 166, 173),
            (144, 169, 188),
            (198, 203, 202),
            (121, 125, 111),
        ],
        count=20,
        caps=(True, True),
    )
    for index in range(9):
        flower = np.array([*pos, 0.282]) + [
            rng.uniform(-0.10, 0.10),
            rng.uniform(-0.080, 0.080),
            rng.uniform(-0.028, 0.071),
        ]
        mesh.tube([[*pos, 0.040], flower], (0.0025, 0.0025), (80, 114, 39), sides=5)
        rgb = [(222, 148, 29), (214, 59, 26), (229, 188, 41)][index % 3]
        mesh.ellipsoid(flower, (0.022, 0.017, 0.012), rgb, count=9, levels=5)

    corner = np.array([0.542, 1.198, 0.003])
    across = np.array([0.030, 0.198, 0])
    along = np.array([0.034, 0.021, 0.251])
    mesh.panel(corner, across, along, (223, 222, 217), reverse=True)
    mesh.panel(corner + [0.006, 0, 0], across, along, (159, 160, 163))
    mesh.panel(
        corner + across * 0.12 + along * 0.40 + [-0.002, 0, 0],
        across * 0.64,
        along * 0.24,
        (82, 117, 171),
        reverse=True,
    )
    for idx in range(10):
        height = 0.085 + 0.083 * idx
        mesh.panel(
            corner + across * 0.20 + height * along + [-0.003, 0, 0],
            across * (0.26 + 0.17 * (idx % 4)),
            along * 0.015,
            (182, 182, 180) if idx not in (4, 5) else (221, 225, 232),
            reverse=True,
        )
    for idx in range(5):
        mesh.panel(
            corner + across * 0.018 + (0.14 + 0.137 * idx) * along + [-0.002, 0, 0],
            across * 0.08,
            along * 0.052,
            (35 + idx * 12, 48 + idx * 12, 65 + idx * 10),
            reverse=True,
        )
    clock_center = np.array([0.674, 1.569, 0.154])
    normal = unit([-0.94, 0.34, 0])
    axis = np.cross([0, 0, 1], normal)
    theta = angles(30)
    ring = np.cos(theta)[:, None] * axis + np.sin(theta)[:, None] * [0, 0, 1]
    mesh.grid(
        np.stack(
            [
                clock_center + 0.054 * ring,
                clock_center + normal * 0.014 + 0.054 * ring,
                clock_center + normal * 0.016 + 0.039 * ring,
            ],
            axis=1,
        ),
        (38, 41, 44),
        wrap=True,
    )
    mesh.disk(
        clock_center + normal * 0.0155 + 0.0392 * ring,
        clock_center + normal * 0.0155,
        (211, 208, 195),
    )


def tape_roll(mesh):
    profile = [
        (0.059, 0.0002),
        (0.0658, 0.0006),
        (0.0686, 0.004),
        (0.0694, 0.014),
        (0.0694, 0.0458),
        (0.0688, 0.0504),
        (0.067, 0.0521),
        (0.061, 0.0523),
        (0.048, 0.0523),
        (0.0434, 0.0521),
        (0.0412, 0.0506),
        (0.0408, 0.0477),
        (0.0408, 0.038),
        (0.0409, 0.0255),
        (0.0410, 0.012),
        (0.0412, 0.002),
        (0.0433, 0.0003),
        (0.059, 0.0002),
    ]
    palette = [
        (108, 109, 115),
        (115, 115, 124),
        (122, 123, 133),
        (130, 130, 140),
        (130, 130, 142),
        (117, 118, 130),
        (113, 114, 125),
        (116, 116, 125),
        (114, 113, 122),
        (119, 116, 120),
        (140, 120, 113),
        (127, 87, 79),
        (129, 79, 68),
        (110, 58, 51),
        (81, 48, 41),
        (62, 43, 36),
        (105, 85, 80),
        (108, 109, 115),
    ]

    def winding(rgb, theta, points):
        result = rgb.copy()
        result *= (
            1
            + 0.115 * np.cos(theta[..., None] + 1.0)
            + 0.017 * np.sin(theta[..., None] * 11)
        )
        wrap = (theta - 1.06) % (2 * np.pi)
        blue = (wrap < 0.48) | ((wrap > 3.05) & (wrap < 3.72))
        trim = (wrap < 0.07) | ((wrap >= 0.48) & (wrap < 0.55))
        for idx in range(11, 16):
            fade = [1.04, 0.96, 0.74, 0.58, 0.43][idx - 11]
            core = np.where(blue, [49, 99, 150], [165, 79, 71])
            core = np.where(trim, [169, 161, 153], core)
            light_marks = (
                1 + 0.14 * np.sin(theta * 35 + idx * 1.6) + 0.13 * np.cos(theta + 2.4)
            )
            result[:, idx] = core * fade * light_marks
        return result

    mesh.revolution((0.327, 0.139), profile, palette, label=1, count=56, shader=winding)


def mug(mesh):
    xy = np.array([0.257, 0.371])
    profile = [
        (0.031, 0.0015),
        (0.0344, 0.0015),
        (0.0377, 0.0045),
        (0.0386, 0.010),
        (0.0396, 0.031),
        (0.0400, 0.059),
        (0.0412, 0.085),
        (0.0418, 0.1005),
        (0.0415, 0.1034),
        (0.0404, 0.1044),
        (0.0390, 0.1041),
        (0.0372, 0.102),
        (0.0368, 0.0975),
        (0.0361, 0.0805),
        (0.0345, 0.054),
        (0.0328, 0.0295),
        (0.030, 0.015),
        (0.025, 0.012),
    ]
    palette = [
        (178, 175, 177),
        (190, 186, 188),
        (207, 203, 204),
        (221, 218, 218),
        (230, 228, 226),
        (234, 231, 229),
        (237, 234, 233),
        (241, 239, 235),
        (248, 246, 240),
        (249, 247, 242),
        (242, 239, 236),
        (222, 218, 222),
        (198, 193, 198),
        (164, 160, 165),
        (126, 120, 124),
        (86, 79, 84),
        (76, 70, 74),
        (80, 75, 78),
    ]

    def glaze(rgb, theta, points):
        result = rgb.copy()
        factor = 0.92 + 0.075 * np.cos(theta + 1.8) + 0.035 * np.cos(2 * theta + 1.45)
        result[:, :8] *= factor[..., None]
        result[:, 11:] *= (0.88 - 0.29 * np.cos(theta + 2.6))[..., None]
        stamp = np.exp(-(((theta[:, 0] - 5.81) / 0.080) ** 4))
        result[:, 4:7] *= (
            1 - stamp[:, None, None] * np.array([0.57, 0.70, 0.25])[None, :, None]
        )
        return result

    mesh.revolution(
        xy, profile, palette, label=2, count=48, shader=glaze, caps=(True, True)
    )
    handle_direction = unit([-0.925, -0.38])
    path = interpolate_path(
        [
            (0.034, 0.076),
            (0.049, 0.080),
            (0.065, 0.076),
            (0.078, 0.069),
            (0.087, 0.056),
            (0.090, 0.041),
            (0.086, 0.026),
            (0.080, 0.016),
            (0.070, 0.013),
            (0.057, 0.0155),
            (0.047, 0.019),
            (0.035, 0.018),
        ],
        steps=2,
    )
    centers = np.column_stack([xy + path[:, :1] * handle_direction, path[:, 1]])
    mesh.tube(
        centers,
        (0.0067, 0.0056),
        (249, 245, 240),
        label=2,
        sides=10,
        reference=(*(-handle_direction[::-1] * [1, -1]), 0),
    )


def telephone(mesh):
    anchor = np.array([0.443, 0.416])
    forward = unit([0.989, 0.146])
    right = np.array([forward[1], -forward[0]])
    length, width = 0.283, 0.170

    def on_phone(uu, vv, hh):
        uu, vv, hh = np.broadcast_arrays(uu, vv, hh)
        xy = anchor + uu[..., None] * forward + vv[..., None] * right
        return np.concatenate([xy, hh[..., None]], axis=-1)

    def deck(uu):
        return 0.028 + 0.146 * np.asarray(uu)

    shell = []
    shell_color = []
    outline = [
        (0.006, 0.010, 0.009, 0.006, 0.006, (149, 142, 132)),
        (0.001, 0.005, 0.002, 0.008, 0.014, (192, 186, 177)),
        (0.000, 0.002, 0.000, 0.013, 0.020, (218, 214, 205)),
        (0.003, 0.001, 0.001, 0.015, 0.026, (223, 219, 210)),
        (0.005, 0.001, 0.006, 0.016, 0.030, (211, 206, 196)),
        (0.008, 0.007, 0.011, 0.013, 0.031, (188, 182, 174)),
    ]
    for front, back, side, radius, height, rgb in outline:
        coords = rounded_rectangle(length - front - back, width - 2 * side, radius)
        uu, vv = (coords + [(length + front - back) / 2, width / 2]).T
        hh = height + (0.145 if height > 0.025 else 0.031) * uu
        shell.append(on_phone(uu, vv, hh))
        light = (0.94 + 0.15 * np.sin(np.arange(len(uu)) * 2 * np.pi / len(uu) - 0.9))[
            :, None
        ]
        shell_color.append(light * np.asarray(rgb))
    perimeter = np.stack(shell, axis=1)
    mesh.grid(
        perimeter, np.stack(shell_color, axis=1), label=3, wrap=True, reverse=True
    )
    mesh.disk(shell[0], shell[0].mean(0), (133, 127, 118), label=3)
    mesh.disk(shell[-1], shell[-1].mean(0), (185, 179, 170), label=3, reverse=True)

    def panel(umin, umax, vmin, vmax, offset, color, divisions=(1, 1)):
        aa, bb = np.meshgrid(
            np.linspace(umin, umax, divisions[0] + 1),
            np.linspace(vmin, vmax, divisions[1] + 1),
            indexing="ij",
        )
        points = on_phone(aa, bb, deck(aa) + offset)
        mesh.grid(
            points,
            color(points, aa, bb) if callable(color) else color,
            label=3,
            reverse=True,
        )

    def trim_color(points, uu, vv):
        grain = (
            1.5 * np.sin(83 * uu + 27 * vv)
            + 2 * np.cos(57 * vv)
            - 5 * np.exp(-(((vv - 0.049) / 0.036) ** 2))
        )
        return np.array([194, 186, 178]) + grain[..., None]

    panel(0.016, 0.266, 0.015, 0.151, 0.004, trim_color, (16, 10))
    panel(0.031, 0.113, 0.066, 0.126, 0.0057, (135, 132, 125))
    panel(0.140, 0.227, 0.071, 0.125, 0.0054, (199, 190, 181))
    panel(0.149, 0.221, 0.078, 0.120, 0.0058, (184, 180, 176))
    for row in range(5):
        start = 0.153 + 0.0125 * row
        panel(
            start,
            start + 0.0014,
            0.081,
            0.114 - 0.003 * (row % 2),
            0.0061,
            (151, 148, 146),
        )

    def key(uu, vv, depth, breadth, height, rgb):
        bounds = rounded_rectangle(
            depth, breadth, min(depth, breadth) * 0.16, count=2
        ) + [uu, vv]
        u0, v0 = bounds.T
        u1, v1 = (bounds * 0.85 + [0.15 * uu, 0.15 * vv]).T
        mesh.solid(
            on_phone(u0[::-1], v0[::-1], deck(u0[::-1]) + 0.0058),
            on_phone(u1[::-1], v1[::-1], deck(u1[::-1]) + 0.0058 + height),
            rgb,
            label=3,
        )

    for row in range(4):
        for col in range(3):
            uu, vv = 0.043 + 0.019 * row, 0.078 + 0.018 * col
            key(
                uu,
                vv,
                0.016,
                0.014,
                0.0029,
                (128 + 3 * row, 126 + 3 * row, 120 + 2 * row),
            )
            panel(
                uu - 0.0025,
                uu + 0.0024,
                vv - 0.0010,
                vv + 0.001,
                0.0088,
                (173, 167, 152),
            )
    for idx in range(7):
        key(0.111 + 0.019 * idx, 0.143, 0.012, 0.0115, 0.0022, (169, 157, 145))
    for idx in range(3):
        key(0.041 + 0.021 * idx, 0.051, 0.012, 0.012, 0.0022, (188, 175, 160))

    for uu in [0.032, 0.238]:
        key(uu, 0.026, 0.045, 0.035, 0.0045, (154, 147, 137))
    sections = np.array(
        [
            [0.002, 0.025, 0.054, 0.0038, 0.004],
            [0.008, 0.026, 0.058, 0.017, 0.011],
            [0.021, 0.027, 0.061, 0.024, 0.0145],
            [0.044, 0.028, 0.064, 0.024, 0.015],
            [0.065, 0.028, 0.066, 0.020, 0.013],
            [0.090, 0.029, 0.072, 0.014, 0.0105],
            [0.128, 0.029, 0.079, 0.0128, 0.0097],
            [0.162, 0.029, 0.086, 0.0135, 0.0107],
            [0.189, 0.028, 0.091, 0.017, 0.0124],
            [0.214, 0.028, 0.095, 0.023, 0.0165],
            [0.238, 0.027, 0.099, 0.0255, 0.015],
            [0.256, 0.026, 0.101, 0.021, 0.012],
            [0.266, 0.026, 0.101, 0.012, 0.008],
            [0.271, 0.026, 0.101, 0.0036, 0.0035],
        ]
    )
    samples = interpolate_path(sections, steps=2)
    centers = on_phone(samples[:, 0], samples[:, 1], samples[:, 2])
    mesh.tube(centers, samples[:, 3:5], (250, 247, 237), label=3, sides=14, shape=0.67)


def layout_prior():
    """Construct the desk, floor, furniture and surrounding room in desk coordinates."""
    mesh = Mesh()
    desktop(mesh)
    ground_and_wall(mesh)
    computer(mesh)
    book_and_globe(mesh)
    drinks_and_decoration(mesh)
    plants_and_print(mesh)
    tape_roll(mesh)
    mug(mesh)
    telephone(mesh)
    return mesh.finish()
