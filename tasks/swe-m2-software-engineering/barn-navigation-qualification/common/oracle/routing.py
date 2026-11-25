"""Shortest routes on a half-pitch node lattice around the blocked cylinders.

Unknown sites are treated as open, so routes are optimistic; the motion layer
refuses to sweep anything that is not known to be free. Nodes sit at half the
cylinder pitch, so every site center and every midpoint between two sites is a
node, and moves reach the 16 nearest directions.
"""

from heapq import heappop, heappush
from math import ceil, floor, gcd, hypot, sqrt

from .arena import segment_gap

MOVES = tuple((a, b) for a in range(-2, 3) for b in range(-2, 3) if gcd(abs(a), abs(b)) == 1)
LINK = 4.0  # start and goal join nodes within this many half pitches
RELIEF = 1e-9


class Router:
    """Plan around every blocked site with a fixed clearance margin."""

    def __init__(self, arena, margin: float) -> None:
        """Index the nodes and their wall clearances."""
        self.arena = arena
        self.step = arena.pitch / 2
        self.need = arena.body + margin
        o, h = arena.origin, self.step
        self.columns = range(ceil(-o.real / h - 1e-9), floor((arena.width - o.real) / h + 1e-9) + 1)
        self.rows = range(ceil(-o.imag / h - 1e-9), floor((arena.height - o.imag) / h + 1e-9) + 1)
        self.cap = self.need + h * sqrt(5) / 2 + 1e-6
        self.gap = {(a, b): min(self.cap, arena.wall_gap(self.point(a, b)))
                    for a in self.columns for b in self.rows}
        self.blocked = set()

    def point(self, a: int, b: int) -> complex:
        """Position of node (a, b)."""
        return self.arena.origin + self.step * complex(a, b)

    def block(self, site: tuple) -> None:
        """Add a blocked site and lower the clearance of the nodes near it."""
        if site in self.blocked:
            return
        self.blocked.add(site)
        center, radius = self.arena.site(*site), self.arena.cylinder
        reach = self.cap + radius
        o, h = self.arena.origin, self.step
        for a in range(ceil((center.real - reach - o.real) / h), floor((center.real + reach - o.real) / h) + 1):
            for b in range(ceil((center.imag - reach - o.imag) / h), floor((center.imag + reach - o.imag) / h) + 1):
                if (a, b) in self.gap:
                    self.gap[a, b] = min(self.gap[a, b], abs(self.point(a, b) - center) - radius)

    def clear(self, p: complex, q: complex, relief: bool = False) -> bool:
        """Whether the inflated body slides straight from p to q.

        With relief, p may already be closer than the margin to something; the
        move then only has to avoid getting any closer to it.
        """
        arena = self.arena
        need = self.need
        wall = min(need, arena.wall_gap(p) - RELIEF) if relief else need
        if arena.wall_gap(p) < wall or arena.wall_gap(q) < wall:
            return False
        reach = need + arena.cylinder
        columns, rows = arena.around(p, q, reach)
        if len(columns) * len(rows) <= len(self.blocked):
            nearby = [(i, j) for i in columns for j in rows if (i, j) in self.blocked]
        else:
            nearby = [(i, j) for i, j in self.blocked if i in columns and j in rows]
        for i, j in nearby:
            center = arena.site(i, j)
            limit = min(reach, abs(p - center) - RELIEF) if relief else reach
            if segment_gap(center, p, q) < limit:
                return False
        return True

    def edge(self, n: tuple, m: tuple, length: float) -> bool:
        """Whether two valid nodes are joined by a clear segment."""
        if min(self.gap[n], self.gap[m]) >= self.need + length / 2:
            return True
        return self.clear(self.point(*n), self.point(*m))

    def nodes_near(self, p: complex):
        """Valid nodes within the link radius of a point, nearest first."""
        o, h = self.arena.origin, self.step
        a0, b0 = (p.real - o.real) / h, (p.imag - o.imag) / h
        found = []
        for a in range(ceil(a0 - LINK), floor(a0 + LINK) + 1):
            for b in range(ceil(b0 - LINK), floor(b0 + LINK) + 1):
                if self.gap.get((a, b), -1.0) >= self.need and hypot(a - a0, b - b0) <= LINK:
                    found.append((abs(self.point(a, b) - p), (a, b)))
        return sorted(found)

    def plan(self, start: complex, goal: complex):
        """Waypoints from start to goal, string-pulled, or None when none exist."""
        if self.clear(start, goal, relief=True):
            return [goal]
        sources = [(cost, n) for cost, n in self.nodes_near(start) if self.clear(start, self.point(*n), relief=True)]
        sinks = {n: cost for cost, n in self.nodes_near(goal) if self.clear(self.point(*n), goal)}
        if not sources or not sinks:
            return None
        best, parent, frontier = {}, {}, []
        for cost, n in sources:
            if cost < best.get(n, float("inf")):
                best[n], parent[n] = cost, None
                heappush(frontier, (cost + abs(goal - self.point(*n)), cost, n))
        finish, finish_cost = None, float("inf")
        closed = set()
        while frontier:
            estimate, cost, n = heappop(frontier)
            if estimate >= finish_cost:
                break
            if n in closed:
                continue
            closed.add(n)
            if n in sinks and cost + sinks[n] < finish_cost:
                finish, finish_cost = n, cost + sinks[n]
            a, b = n
            for da, db in MOVES:
                m = (a + da, b + db)
                if m in closed or self.gap.get(m, -1.0) < self.need:
                    continue
                length = self.step * hypot(da, db)
                total = cost + length
                if total < best.get(m, float("inf")) and self.edge(n, m, length):
                    best[m], parent[m] = total, n
                    heappush(frontier, (total + abs(goal - self.point(*m)), total, m))
        if finish is None:
            return None
        chain = []
        while finish is not None:
            chain.append(self.point(*finish))
            finish = parent[finish]
        return self.pull([start] + chain[::-1] + [goal])

    def pull(self, points: list) -> list:
        """Drop intermediate points whenever a straight segment stays clear."""
        out, i = [], 0
        while i < len(points) - 1:
            j = i + 1
            while j + 1 < len(points) and self.clear(points[i], points[j + 1], relief=i == 0):
                j += 1
            out.append(points[j])
            i = j
        return out

    def keeps(self, z: complex, route: list, sites: list) -> bool:
        """Whether a route stays clear of newly blocked sites."""
        reach = self.need + self.arena.cylinder
        legs = list(zip([z] + route, route))
        return all(segment_gap(self.arena.site(*site), p, q) >= reach for site in sites for p, q in legs)
