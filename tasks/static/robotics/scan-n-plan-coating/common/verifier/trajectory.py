"""Parse controller records, bound Hermite motion and sample actual process flow."""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
import math

AXES = 7
Vector = tuple[float, ...]


@dataclass(frozen=True)
class Knot:
    """One controller sample at an absolute or job-relative integer time."""

    t_ns: int
    q_rad: Vector
    qd_rad_s: Vector
    flow_ml_s: float


@dataclass(frozen=True)
class AxisBounds:
    """Position and derivative extrema over an entire interpolated segment."""

    lower_rad: float
    upper_rad: float
    max_speed_rad_s: float
    max_acceleration_rad_s2: float


@dataclass(frozen=True)
class ProcessSample:
    """A time-weighted motion observation carrying the held material flow."""

    t_ns: float
    duration_s: float
    q_rad: Vector
    qd_rad_s: Vector
    flow_ml_s: float


def number(value: object, field: str) -> float:
    """Read one finite JSON numeric field without accepting boolean values."""
    if type(value) not in (int, float):
        raise ValueError(f"{field} must be finite")
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError(f"{field} must be finite") from error
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def vector(value: object, field: str) -> Vector:
    """Read the six arm axes followed by the positioner in wire order."""
    if not isinstance(value, list) or len(value) != AXES:
        raise ValueError(f"{field} must contain {AXES} axes")
    return tuple(number(element, field) for element in value)


def parse_knots(
    records: object, control_period_ns: int, max_flow_ml_s: float, *, finish_disabled: bool = True,
) -> tuple[Knot, ...]:
    """Parse Hermite knots and the held flow values in a controller trace.

    Args:
        records: Submitted plan rows or independently measured receipt rows.
        control_period_ns: Cadence from the public job, in nanoseconds.
        max_flow_ml_s: Inclusive upper flow bound.
        finish_disabled: Require zero flow at the final row for completed plans.
            Receipt fragments can end inside an enabled interval.

    Returns:
        Validated immutable samples, ordered by time, in public wire order.

    Raises:
        ValueError: Invalid row type, numeric value, cadence or flow.
    """
    if type(control_period_ns) is not int or control_period_ns <= 0:
        raise ValueError("Control period must be a positive integer")
    if not isinstance(records, list) or len(records) < 2:
        raise ValueError("A nonempty interpolation needs at least two samples")
    result = []
    for row in records:
        if not isinstance(row, Mapping):
            raise ValueError("Each trajectory row must be an object")
        tick = row.get("t_ns")
        if type(tick) is not int or tick < 0:
            raise ValueError("t_ns must be a nonnegative integer")
        if result:
            delta = tick - result[-1].t_ns
            if delta <= 0 or delta % control_period_ns:
                raise ValueError("Timestamps must increase by whole control periods")
        flow = number(row.get("flow_ml_s"), "flow_ml_s")
        if not 0 <= flow <= max_flow_ml_s:
            raise ValueError("Flow exceeds its limits")
        result.append(Knot(tick, vector(row.get("q_rad"), "q_rad"), vector(row.get("qd_rad_s"), "qd_rad_s"), flow))
    if finish_disabled and result[-1].flow_ml_s != 0:
        raise ValueError("Flow must be disabled at the final plan knot")
    return tuple(result)


def interior_roots(a: float, b: float, c: float) -> tuple[float, ...]:
    """Solve a quadratic and keep only real roots strictly inside (0, 1)."""
    if a == 0:
        roots = () if b == 0 else (-c / b,)
    else:
        discriminant = b * b - 4.0 * a * c
        if discriminant < 0:
            return ()
        stable = -0.5 * (b + math.copysign(math.sqrt(discriminant), b))
        roots = (0.0,) if stable == 0 else (stable / a, c / stable)
    return tuple(root for root in roots if 0 < root < 1)


@dataclass(frozen=True)
class Segment:
    """Cubic joint coefficients expressed over a normalized controller interval."""

    left: Knot
    right: Knot
    coefficients: tuple[tuple[float, float, float, float], ...]

    @property
    def seconds(self) -> float:
        """Return the segment duration in seconds."""
        return (self.right.t_ns - self.left.t_ns) * 1e-9

    def at(self, fraction: float) -> tuple[Vector, Vector]:
        """Evaluate joint positions and velocities at an interval fraction.

        Args:
            fraction: Normalized time in the closed range [0, 1].

        Returns:
            Joint positions and velocities in radians and radians per second.
        """
        if not 0 <= fraction <= 1:
            raise ValueError("Hermite time fraction outside segment")
        positions = []
        velocities = []
        for a, b, c, d in self.coefficients:
            positions.append(((a * fraction + b) * fraction + c) * fraction + d)
            velocities.append(((3.0 * a * fraction + 2.0 * b) * fraction + c) / self.seconds)
        return tuple(positions), tuple(velocities)

    def bounds(self) -> tuple[AxisBounds, ...]:
        """Bound all seven joints continuously using the stationary points."""
        interval = self.seconds
        out = []
        for a, b, c, d in self.coefficients:
            roots = interior_roots(3 * a, 2 * b, c)
            positions = [((a * u + b) * u + c) * u + d for u in (0, 1, *roots)]
            roots = interior_roots(0, 6 * a, 2 * b)
            speeds = [abs((3 * a * u + 2 * b) * u + c) / interval for u in (0, 1, *roots)]
            accel = max(abs(2 * b), abs(6 * a + 2 * b)) / interval**2
            out.append(AxisBounds(min(positions), max(positions), max(speeds), accel))
        return tuple(out)


def segments(knots: tuple[Knot, ...]) -> Iterator[Segment]:
    """Construct Hermite polynomials from already validated heading and velocity rows."""
    for left, right in zip(knots, knots[1:]):
        dt = (right.t_ns - left.t_ns) * 1e-9
        coefficients = []
        for q0, q1, v0, v1 in zip(left.q_rad, right.q_rad, left.qd_rad_s, right.qd_rad_s, strict=True):
            c, end = v0 * dt, v1 * dt
            difference = q1 - q0
            coefficients.append((-2 * difference + c + end, 3 * difference - 2 * c - end, c, q0))
        yield Segment(left, right, tuple(coefficients))


def sample_process(knots: tuple[Knot, ...], max_step_ns: int) -> Iterator[ProcessSample]:
    """Subdivide each interval, retaining the correct left-held material flow.

    Args:
        knots: Controller observations or commands accepted by parse_knots().
        max_step_ns: Maximum duration of each midpoint quadrature cell.

    Yields:
        Weighted samples that integrate over disjoint half-open intervals.
    """
    if max_step_ns <= 0:
        raise ValueError("Process sampling requires a positive interval")
    for segment in segments(knots):
        ticks = segment.right.t_ns - segment.left.t_ns
        cells = (ticks + max_step_ns - 1) // max_step_ns
        for index in range(cells):
            fraction = (index + 0.5) / cells
            q, qd = segment.at(fraction)
            yield ProcessSample(
                segment.left.t_ns + fraction * ticks, segment.seconds / cells,
                q, qd, segment.left.flow_ml_s,
            )
