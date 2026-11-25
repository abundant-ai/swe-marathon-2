"""Check interpolation extrema and receipt dose accounting for later stages."""

from pathlib import Path

import pytest

VERIFIER = Path(__file__).resolve().parents[1] / "common/verifier"


def _row(tick: int, position: float, velocity: float, flow: float) -> dict:
    """Create one seven-axis sample with only the first joint moving."""
    return {"t_ns": tick, "q_rad": [position] + [0.0] * 6, "qd_rad_s": [velocity] + [0.0] * 6, "flow_ml_s": flow}


def test_hermite_checks_extrema_between_controller_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Detect endpoint-only validation on an overshooting move and a fast midpoint."""
    monkeypatch.syspath_prepend(str(VERIFIER))
    from trajectory import parse_knots, segments

    reversed_velocity = [_row(0, 0, 4, 1), _row(1_000_000_000, 0, -4, 0)]
    crossing = [_row(0, 0, 0, 1), _row(1_000_000_000, 1, 0, 0)]

    first = next(segments(parse_knots(reversed_velocity, 10_000_000, 2))).bounds()[0]
    second = next(segments(parse_knots(crossing, 10_000_000, 2))).bounds()[0]
    assert first.lower_rad == 0
    assert first.upper_rad == pytest.approx(1.0)
    assert second.max_speed_rad_s == pytest.approx(1.5)
    assert second.max_acceleration_rad_s2 == pytest.approx(6.0)


def test_process_flow_matches_split_receipts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Preserve held flow across half-open trace fragments and a spray shutoff."""
    monkeypatch.syspath_prepend(str(VERIFIER))
    from trajectory import parse_knots, sample_process

    rows = [_row(13, 0, 0, 4), _row(400_000_013, 0, 0, 1), _row(1_000_000_013, 0, 0, 0)]
    whole = parse_knots(rows, 10_000_000, 4)
    first = parse_knots(rows[:2], 10_000_000, 4, finish_disabled=False)
    last = parse_knots(rows[1:], 10_000_000, 4, finish_disabled=False)
    assert list(sample_process(whole, 10_000_000)) == [
        *sample_process(first, 10_000_000), *sample_process(last, 10_000_000),
    ]
    assert sum(sample.flow_ml_s * sample.duration_s for sample in sample_process(whole, 10_000_000)) == (
        pytest.approx(2.2)
    )
    with pytest.raises(ValueError, match="disabled"):
        parse_knots(rows[:2], 10_000_000, 4)


def test_swept_clearance_detects_mid_interval_and_retains_uncertainty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Check a collision away from endpoints and a bound with insufficient margin."""
    monkeypatch.syspath_prepend(str(VERIFIER))
    from swept_clearance import certify_clearance
    from trajectory import parse_knots, segments

    crossing = [_row(0, 0, 1, 0), _row(1_000_000_000, 1, 1, 0)]
    segment = next(segments(parse_knots(crossing, 10_000_000, 2)))
    radii = (1.0,) * 6
    collision = certify_clearance(segment, lambda q: abs(q[0] - 0.23) - 0.04, 0.02, radii, 0)
    assert collision.status == "violation"
    assert collision.fraction not in (None, 0.0, 0.5, 1.0)
    clear = certify_clearance(segment, lambda q: 0.5 - q[0] * 0.1, 0.02, radii, 0)
    assert clear.status == "clear"
    assert clear.samples > 1
    unknown = certify_clearance(segment, lambda _: 0.02, 0.02, radii, 0, max_depth=1)
    assert unknown.status == "unresolved"
