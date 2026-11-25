"""Closed-loop navigator for lidar field missions.

Each tick folds the scan into the site map, keeps an optimistic route to the
goal and then either rotates in place or drives straight along the heading.
A forward speed is used only if braking at the limit from it keeps the body
clear of every site not yet seen to be free, so the hardest braking the limits
allow is always a safe command. Braking ends on exactly zero because the field
certifies every tick with a positive forward speed, however small.

This navigator assumes nothing in the field moves. The stage 5 navigator in
movers.py extends it with the mover tracks.
"""

from cmath import exp, phase
from math import pi, tau

from .arena import Arena, segment_gap
from .motion import fastest, free_run, reach, slowed, turn_rate
from .routing import Router
from .sensing import FREE, OCCUPIED, UNKNOWN, SiteMap

ROUTE_MARGIN = 2e-3   # clearance beyond the inflated body that routes keep
MOTION_MARGIN = 1e-3  # clearance beyond the inflated body that braking sweeps keep
ARRIVED = 1e-6        # distance from a waypoint that counts as reaching it
ALIGNED = 1e-7        # heading error that counts as facing the waypoint
STALL_RUN = 0.01      # a free run this short in front of the robot counts as blocked
PATIENCE = 6          # blocked ticks before unseen sites ahead are routed around
RETRY = 20            # ticks to wait before planning again after a failed plan


def wrap(angle: float) -> float:
    """Equivalent angle in [-pi, pi)."""
    return (angle + pi) % tau - pi


def reply(status: str, v: float = 0.0, w: float = 0.0) -> dict:
    """One protocol response."""
    return {"status": status, "v_mps": v, "w_radps": w}


class Pilot:
    """Stream controller for missions that report range scans."""

    def __init__(self, spec: dict) -> None:
        """Read the mission limits and start with an unexplored field."""
        self.arena = Arena(spec)
        self.map = SiteMap(self.arena, spec["scan"])
        self.dt = float(spec["dt"])
        self.max_v, self.max_w = float(spec["max_v"]), float(spec["max_w"])
        self.dv = float(spec["max_accel"]) * self.dt
        self.dw = float(spec["max_alpha"]) * self.dt
        self.tolerance = float(spec["goal_tolerance_m"])
        self.assumed = set()
        self.router = Router(self.arena, ROUTE_MARGIN)
        self.route = None
        self.wait = 0
        self.stalled = 0

    def tick(self, observation: dict) -> dict:
        """Choose the command for one control period."""
        x, y, yaw = (float(value) for value in observation["pose"])
        v0, w0 = (float(value) for value in observation["velocity"])
        z = complex(x, y)
        movers = self.perceive(observation)
        fresh = self.map.update(z, yaw, observation["scan"], [(c, r) for c, _, r in movers])
        self.learn(z, fresh)
        if abs(z - self.arena.goal) <= self.tolerance and v0 <= self.dv and abs(w0) <= self.dw:
            return reply("succeeded")
        if self.route is None and not self.replan(z):
            return reply("running", *self.brake(v0, w0))
        while len(self.route) > 1 and abs(self.route[0] - z) <= ARRIVED:
            self.route.pop(0)
        offset = self.route[0] - z
        turn = wrap(phase(offset) - yaw) if abs(offset) > ARRIVED else 0.0
        if abs(turn) <= ALIGNED and abs(w0) <= self.dw:
            heading = exp(1j * yaw)
            along = max(0.0, offset.real * heading.real + offset.imag * heading.imag)
            return reply("running", self.drive(z, heading, along, v0, movers), 0.0)
        if v0 <= self.dv:
            return reply("running", 0.0, turn_rate(w0, turn, self.dw, self.max_w, self.dt))
        return reply("running", *self.brake(v0, w0))

    def perceive(self, observation: dict) -> list:
        """Movers to account for this tick as (center, velocity, radius): none here."""
        return []

    def clear(self, z: complex, heading: complex, v: float, movers: list) -> bool:
        """Whether holding v and then braking avoids every mover: none are assumed."""
        return True

    def learn(self, z: complex, fresh: list) -> None:
        """Block newly seen cylinders and drop routes they cut."""
        for site in fresh:
            self.router.block(site)
        settled = [site for site in self.assumed if self.map.state[site[0]][site[1]] != UNKNOWN]
        if settled:
            self.assumed.difference_update(settled)
            if any(self.map.state[i][j] == FREE for i, j in settled):
                self.rebuild()
                self.route = None
                return
        if fresh and self.route is not None and not self.router.keeps(z, self.route, fresh):
            self.route = None

    def rebuild(self) -> None:
        """Recreate the router from the occupied and the assumed sites."""
        self.router = Router(self.arena, ROUTE_MARGIN)
        for i, column in enumerate(self.map.state):
            for j, state in enumerate(column):
                if state == OCCUPIED:
                    self.router.block((i, j))
        for site in self.assumed:
            self.router.block(site)

    def replan(self, z: complex) -> bool:
        """Plan a fresh route, forgetting assumed blockages if nothing else works."""
        if self.wait:
            self.wait -= 1
            return False
        self.route = self.router.plan(z, self.arena.goal)
        if self.route is None and self.assumed:
            self.assumed.clear()
            self.rebuild()
            self.route = self.router.plan(z, self.arena.goal)
        if self.route is None:
            self.wait = RETRY
            return False
        return True

    def brake(self, v0: float, w0: float) -> tuple:
        """Slow both speeds toward zero as hard as allowed."""
        v = slowed(v0, self.dv)
        w = 0.0 if abs(w0) <= self.dw else w0 - (self.dw if w0 > 0 else -self.dw)
        return v, w

    def drive(self, z: complex, heading: complex, along: float, v0: float, movers: list) -> float:
        """Fastest straight speed that can still stop in time for every hazard."""
        dt, dv = self.dt, self.dv
        low, high = slowed(v0, dv), min(self.max_v, v0 + dv)
        run = free_run(self.arena, self.map.state, z, heading, reach(high, dv, dt), MOTION_MARGIN)
        limit = min(along, run)

        def admissible(v: float) -> bool:
            """Whether holding v and then braking stays clear of everything."""
            return reach(v, dv, dt) <= limit + 1e-12 and self.clear(z, heading, v, movers)

        v = fastest(low, high, admissible)
        if low == 0.0 and v < 1e-9:
            v = 0.0
        self.notice(z, heading, run, along)
        return v

    def notice(self, z: complex, heading: complex, run: float, along: float) -> None:
        """Route around unseen sites that have blocked the way for too long."""
        if run >= min(along, STALL_RUN):
            self.stalled = 0
            return
        self.stalled += 1
        if self.stalled < PATIENCE:
            return
        self.stalled = 0
        arena = self.arena
        ahead = z + heading * (run + STALL_RUN)
        reach_site = arena.body + MOTION_MARGIN + arena.cylinder
        columns, rows = arena.around(z, ahead, reach_site)
        unseen = [(i, j) for i in columns for j in rows if self.map.state[i][j] == UNKNOWN
                  and segment_gap(arena.site(i, j), z, ahead) < reach_site]
        for site in unseen:
            self.assumed.add(site)
            self.router.block(site)
        self.route = None
