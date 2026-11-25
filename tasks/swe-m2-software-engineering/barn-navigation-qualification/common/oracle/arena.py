"""Field geometry shared by the lidar navigator's sensing, routing and motion."""

from math import ceil, floor


def segment_gap(c: complex, a: complex, b: complex) -> float:
    """Distance from point c to the closed segment ab."""
    d, e = b - a, c - a
    span = d.real * d.real + d.imag * d.imag
    t = 0.0 if span == 0 else min(1.0, max(0.0, (e.real * d.real + e.imag * d.imag) / span))
    return abs(e - d * t)


class Arena:
    """Walls, the cylinder lattice and the inflated robot body of one mission."""

    def __init__(self, spec: dict) -> None:
        """Read the public geometry of a field mission."""
        self.width, self.height = (float(value) for value in spec["bounds_m"])
        lattice = spec["lattice"]
        self.origin = complex(*(float(value) for value in lattice["origin_m"]))
        self.pitch = float(lattice["pitch_m"])
        self.columns, self.rows = int(lattice["columns"]), int(lattice["rows"])
        self.cylinder = float(spec["obstacle_radius_m"])
        self.body = float(spec["radius_m"]) + float(spec["margin_m"])
        self.start = complex(*(float(value) for value in spec["start_m"]))
        self.goal = complex(*(float(value) for value in spec["goal_m"]))

    def site(self, i: int, j: int) -> complex:
        """Center of lattice site (i, j); j counts rows upward from the origin."""
        return self.origin + self.pitch * complex(i, j)

    def box(self, low: complex, high: complex) -> tuple:
        """Column and row ranges of the sites centered inside an axis-aligned box."""
        o, p = self.origin, self.pitch
        columns = range(max(0, ceil((low.real - o.real) / p)),
                        min(self.columns - 1, floor((high.real - o.real) / p)) + 1)
        rows = range(max(0, ceil((low.imag - o.imag) / p)),
                     min(self.rows - 1, floor((high.imag - o.imag) / p)) + 1)
        return columns, rows

    def around(self, a: complex, b: complex, reach: float) -> tuple:
        """Site ranges that could lie within reach of the segment ab."""
        return self.box(complex(min(a.real, b.real) - reach, min(a.imag, b.imag) - reach),
                        complex(max(a.real, b.real) + reach, max(a.imag, b.imag) + reach))

    def wall_gap(self, p: complex) -> float:
        """Distance from p to the nearest arena wall, negative outside the arena."""
        return min(p.real, self.width - p.real, p.imag, self.height - p.imag)
