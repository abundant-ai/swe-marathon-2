"""Speed profiles that stop exactly where intended, and swept-path checks.

The navigator only ever rotates in place or drives straight, so every moving
tick sweeps a straight capsule. A speed is accepted only if holding it for one
tick and then braking as hard as allowed keeps the body clear of every static
hazard.
"""

from math import sqrt

from .sensing import FREE

RELIEF = 1e-9
STOPPED = 1e-10  # a braking remainder this small is commanded as exactly zero


def braking(speed: float, step: float) -> list:
    """Speeds commanded on the ticks after this one while braking at the limit."""
    out = []
    speed = slowed(speed, step)
    while speed > 0.0:
        out.append(speed)
        speed = slowed(speed, step)
    return out


def slowed(speed: float, step: float) -> float:
    """Speed after one tick of the hardest braking.

    The verifier certifies every tick with a positive forward speed, however
    small, so a remainder that would only creep forward is rounded to a stop.
    """
    rest = speed - step
    return rest if rest > STOPPED else 0.0


def reach(speed: float, step: float, dt: float) -> float:
    """Distance covered by holding speed for one tick and then braking."""
    return dt * (speed + sum(braking(speed, step)))


def fastest(low: float, high: float, admissible) -> float:
    """Largest value in [low, high] accepted by a predicate that holds for small values.

    When even the low end is rejected the low end is returned anyway: it is the
    hardest braking the limits allow.
    """
    if high <= low or not admissible(low):
        return low
    if admissible(high):
        return high
    for _ in range(48):
        middle = 0.5 * (low + high)
        if admissible(middle):
            low = middle
        else:
            high = middle
    return low


def turn_rate(w0: float, remaining: float, step: float, limit: float, dt: float) -> float:
    """Yaw rate for this tick that can still stop exactly on the remaining turn."""
    sign = 1.0 if remaining >= 0 else -1.0
    angle, current = abs(remaining), w0 * sign
    if current < 0:
        return sign * min(0.0, current + step)
    low, high = max(0.0, current - step), min(limit, current + step)
    return sign * fastest(low, high, lambda w: reach(w, step, dt) <= angle + 1e-12)


def free_run(arena, state: list, z: complex, u: complex, horizon: float, margin: float) -> float:
    """Longest straight advance along u before the body nears a wall or a non-free site.

    A hazard that is already inside the margin may not be approached further,
    but it does not stop motion that keeps or increases the distance to it.
    """
    need = arena.body + margin
    run = horizon
    for gap, slope in ((z.real, u.real), (arena.width - z.real, -u.real),
                       (z.imag, u.imag), (arena.height - z.imag, -u.imag)):
        if slope < 0:
            run = min(run, (gap - min(need, gap - RELIEF)) / -slope)
    reach_site = need + arena.cylinder
    columns, rows = arena.around(z, z + u * horizon, reach_site)
    for i in columns:
        column = state[i]
        for j in rows:
            if column[j] == FREE:
                continue
            d = arena.site(i, j) - z
            along = d.real * u.real + d.imag * u.imag
            if along <= 0:
                continue
            distance = abs(d)
            floor = min(reach_site, distance - RELIEF)
            across = max(0.0, distance * distance - along * along)
            if across < floor * floor:
                run = min(run, along - sqrt(floor * floor - across))
    return max(0.0, run)

