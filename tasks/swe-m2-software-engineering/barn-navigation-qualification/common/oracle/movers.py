"""Moving obstacles for the stage 5 field navigator.

Each observation lists every mover's position, velocity and radius. The
navigator reads its scans with those discs in mind, so a passing mover never
becomes a phantom cylinder, and it accepts a forward speed only if braking at
the limit from it stays clear of everywhere a mover could reach meanwhile.
"""

from .arena import segment_gap
from .motion import braking
from .pilot import MOTION_MARGIN, Pilot


def mover_clear(z: complex, u: complex, speeds: list, dt: float, movers: list,
                body: float, track_speed: float, margin: float) -> bool:
    """Whether a straight braking profile stays out of every mover's reach.

    During the first tick each mover follows its reported velocity exactly;
    afterwards it may be anywhere within track_speed of where that tick ends.
    """
    position = z
    for k, speed in enumerate(speeds):
        following = position + u * (speed * dt)
        for center, velocity, radius in movers:
            need = body + radius + margin
            if k == 0:
                if segment_gap(0j, position - center, following - center - velocity * dt) < need:
                    return False
            elif segment_gap(center + velocity * dt, position, following) < need + track_speed * k * dt:
                return False
        position = following
    return True


class Tracker(Pilot):
    """The field navigator that also avoids tracked movers."""

    def __init__(self, spec: dict) -> None:
        """Read the mission limits, including how fast an unseen turn could move a mover."""
        super().__init__(spec)
        self.track_speed = float(spec.get("max_track_speed_mps", 0.0))

    def perceive(self, observation: dict) -> list:
        """Center, velocity and radius of every tracked mover."""
        return [(complex(*(float(value) for value in track["position"])),
                 complex(*(float(value) for value in track["velocity"])),
                 float(track["radius_m"])) for track in observation.get("tracks") or ()]

    def clear(self, z: complex, heading: complex, v: float, movers: list) -> bool:
        """Whether holding v and then braking keeps out of every mover's reach."""
        return not movers or mover_clear(z, heading, [v] + braking(v, self.dv), self.dt, movers,
                                         self.arena.body, self.track_speed, MOTION_MARGIN)
