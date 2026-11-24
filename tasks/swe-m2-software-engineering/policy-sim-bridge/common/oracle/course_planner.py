"""Find paths through observed obstacle rectangles in the survey frame."""

from heapq import heappop, heappush
from itertools import count
from math import ceil, cos, hypot, pi, sin


def cap(vector, maximum):
    length = hypot(*vector)
    scale = min(1.0, maximum / max(length, 1e-8))
    return [component * scale for component in vector]


def heading(angle):
    return (angle + pi) % (2 * pi) - pi


class Site:
    """Treat the robot's planar exclusion radius as a path clearance margin."""

    def __init__(self, extent, obstacles, radius, cell):
        self.xmin, self.xmax, self.ymin, self.ymax = extent
        self.boxes = obstacles
        self.radius = radius
        self.cell = cell

    def clear(self, point):
        x, y = point
        margin = self.radius
        return (
            self.xmin + margin <= x <= self.xmax - margin
            and self.ymin + margin <= y <= self.ymax - margin
            and all(hypot(max(lo - x, x - hi, 0), max(bottom - y, y - top, 0)) >= margin
                    for lo, hi, bottom, top in self.boxes)
        )

    def visible(self, start, end):
        x, y = start
        dx, dy = end[0] - x, end[1] - y
        steps = max(1, ceil(hypot(dx, dy) / (.42 * self.cell)))
        return all(self.clear((x + dx * i / steps, y + dy * i / steps)) for i in range(steps + 1))

    def key(self, point):
        return round(point[0] / self.cell), round(point[1] / self.cell)

    def at(self, key):
        return self.cell * key[0], self.cell * key[1]

    def closest(self, point):
        x, y = self.key(point)
        locations = [(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
        cells = [cell for cell in locations if self.visible(point, self.at(cell))]
        return min(cells, key=lambda cell: hypot(self.at(cell)[0]-point[0], self.at(cell)[1]-point[1]),
                   default=None)

    def route(self, start, goal):
        if self.visible(start, goal):
            return [goal]
        first, target = self.closest(start), self.closest(goal)
        if first is None or target is None:
            return []
        parents = {first: None}
        costs = {first: 0.0}
        frontier = []
        order = count()

        def push(cell, cost):
            estimate = hypot(cell[0] - target[0], cell[1] - target[1])
            heappush(frontier, (cost + estimate, next(order), cost, cell))

        push(first, 0.0)
        while frontier:
            _, _, cost, cell = heappop(frontier)
            if cost != costs[cell]:
                continue
            if cell == target:
                ends = [goal]
                while cell is not None:
                    ends.append(self.at(cell))
                    cell = parents[cell]
                return ends[::-1]
            for dx, dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
                other = cell[0] + dx, cell[1] + dy
                length = cost + hypot(dx, dy)
                if length < costs.get(other, float('inf')) and self.visible(self.at(cell), self.at(other)):
                    costs[other] = length
                    parents[other] = cell
                    push(other, length)
        return []

    def pursuit(self, position, route):
        nearest = min(range(len(route)), key=lambda i:hypot(route[i][0]-position[0],route[i][1]-position[1]))
        region = [waypoint for waypoint in route[max(nearest-1,0):] if self.visible(position,waypoint)]
        return region[-1] if region else None


def pursuit_twist(position, velocity, yaw, target, target_yaw, limit=.56):
    """Track a target in world coordinates and transform the twist to the body frame."""
    velocity = cap([1.65*(target[i] - position[i])-.2*velocity[i] for i in range(2)],limit)
    v_x = cos(yaw)*velocity[0]+sin(yaw)*velocity[1]
    v_y = -sin(yaw)*velocity[0]+cos(yaw)*velocity[1]
    return [float(max(-.55,min(.55,v_x))),float(max(-.38,min(.38,v_y))),
            float(max(-.55,min(.55,1.55*heading(target_yaw-yaw))))]
