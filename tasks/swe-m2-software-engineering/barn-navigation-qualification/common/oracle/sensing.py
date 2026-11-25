"""Classify lattice sites from range scans taken at exactly known poses.

A site only ever moves from UNKNOWN to FREE or OCCUPIED. FREE needs a ray that
crossed the site's disc well before that ray's return, so an occupied site
would have produced an earlier reading. OCCUPIED needs a return lying on that
site's circle and on no other surface: wall, mover or neighbouring cylinder.
"""

from cmath import exp, phase
from math import asin, ceil, floor, inf, sqrt, tau

UNKNOWN, FREE, OCCUPIED = 0, 1, 2
ROUNDING = 1e-4  # readings are rounded to 0.1 mm; stay twice that short of a return
SURFACE = 2e-4   # a return this close to a circle may have come from it
CORE = 1e-5      # a ray must pass this far inside a disc to prove the disc empty
BLINDED = 1e-3   # a mover this close to the minimum range explains a missing reading


def entry(z: complex, u: complex, center: complex, radius: float) -> float:
    """Distance along the unit ray z + t*u to a disc; 0 inside it and inf on a miss."""
    d = center - z
    along = d.real * u.real + d.imag * u.imag
    across = d.real * d.real + d.imag * d.imag - along * along
    if abs(d) <= radius:
        return 0.0
    if along <= 0 or across > radius * radius:
        return inf
    return along - sqrt(radius * radius - across)


class SiteMap:
    """Occupancy belief over the cylinder lattice that only ever gains certainty."""

    def __init__(self, arena, scan: dict) -> None:
        """Start with every site unknown."""
        self.arena = arena
        self.state = [[UNKNOWN] * arena.rows for _ in range(arena.columns)]
        self.unknown = {(i, j) for i in range(arena.columns) for j in range(arena.rows)}
        self.angle_min = float(scan["angle_min_rad"])
        self.increment = float(scan["angle_increment_rad"])
        self.count = int(scan["count"])
        self.low, self.high = float(scan["range_min_m"]), float(scan["range_max_m"])

    def update(self, z: complex, yaw: float, scan: list, discs: list) -> list:
        """Fold one scan into the site states and return the newly occupied sites."""
        if type(scan) is not list or len(scan) != self.count:
            raise ValueError("scan length differs from the mission")
        if any(abs(z - center) <= radius for center, radius in discs):
            return []  # the sensor sits inside a mover and reports nothing
        first = yaw + self.angle_min
        units = [exp(1j * (first + k * self.increment)) for k in range(self.count)]
        extent = []
        for u, reading in zip(units, scan):
            if reading is None:
                near = min((entry(z, u, c, r) for c, r in discs), default=inf)
                extent.append(None if near < self.low + BLINDED else self.high - ROUNDING)
            else:
                extent.append(float(reading) - ROUNDING)
        self.carve(z, first, units, extent)
        return self.mark(z, units, scan, extent, discs)

    def carve(self, z: complex, first: float, units: list, extent: list) -> None:
        """Mark unknown sites FREE when a ray crossed their core before its return."""
        arena, count, increment = self.arena, self.count, self.increment
        radius = arena.cylinder
        core = radius - CORE
        reach = self.high + radius
        cleared = []
        for i, j in self.unknown:
            d = arena.site(i, j) - z
            distance = abs(d)
            if distance > reach or distance <= radius:
                continue
            half = asin(core / distance)
            middle = (phase(d) - first) % tau
            if self.crossed(d, distance, middle, half, units, extent, count, increment, radius, core):
                cleared.append((i, j))
        for i, j in cleared:
            self.state[i][j] = FREE
            self.unknown.discard((i, j))

    @staticmethod
    def crossed(d, distance, middle, half, units, extent, count, increment, radius, core) -> bool:
        """Whether some ray passes through the disc core short of its own return."""
        for shift in (0.0, -tau, tau):
            low = max(0, ceil((middle - half + shift) / increment))
            high = min(count - 1, floor((middle + half + shift) / increment))
            for k in range(low, high + 1):
                limit = extent[k]
                if limit is None:
                    continue
                u = units[k]
                along = d.real * u.real + d.imag * u.imag
                across = distance * distance - along * along
                if along > 0 and across < core * core and along - sqrt(radius * radius - across) < limit:
                    return True
        return False

    def mark(self, z: complex, units: list, scan: list, extent: list, discs: list) -> list:
        """Attribute each return to the single cylinder whose surface it lies on."""
        arena = self.arena
        radius = arena.cylinder
        fresh = []
        for u, reading, limit in zip(units, scan, extent):
            if reading is None or limit is None:
                continue
            p = z + float(reading) * u
            if arena.wall_gap(p) <= SURFACE:
                continue
            if any(abs(p - c) <= r + SURFACE for c, r in discs):
                continue
            i0 = round((p.real - arena.origin.real) / arena.pitch)
            j0 = round((p.imag - arena.origin.imag) / arena.pitch)
            hits = [(i, j) for i in range(i0 - 1, i0 + 2) for j in range(j0 - 1, j0 + 2)
                    if 0 <= i < arena.columns and 0 <= j < arena.rows
                    and abs(abs(p - arena.site(i, j)) - radius) <= SURFACE]
            if len(hits) == 1:
                i, j = hits[0]
                if self.state[i][j] != OCCUPIED:
                    self.state[i][j] = OCCUPIED
                    self.unknown.discard((i, j))
                    fresh.append((i, j))
        return fresh
