"""Check treatment component extraction and dry transfers between wet paths."""

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

COMMON = Path(__file__).resolve().parents[1] / "common"


def test_coating_patch_partition_ignores_duplicate_mesh_vertices(monkeypatch: pytest.MonkeyPatch) -> None:
    """Preserve both connected bands of the stacked carrier after vertex duplication."""
    monkeypatch.syspath_prepend(str(COMMON / "oracle"))
    monkeypatch.syspath_prepend(str(COMMON / "verifier"))
    from coating_planner import Workpiece, _target_components
    from offline_cases import offline_cases

    original = next(case.job for case in offline_cases(3) if case.name == "coat-two-flanges-on-stacked-carrier")
    mesh = original["part_mesh"]
    vertices = [mesh["vertices_m"][vertex] for face in mesh["triangles"] for vertex in face]
    triangles = [[start, start + 1, start + 2] for start in range(0, len(vertices), 3)]
    duplicated = {**original, "part_mesh": {"vertices_m": vertices, "triangles": triangles}}

    expected = _target_components(Workpiece(original))
    assert len(expected) == 2
    assert _target_components(Workpiece(duplicated)) == expected


def test_coating_dry_bypass_preserves_wet_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reroute a blocked transfer while keeping adjacent wet motion and flow intact."""
    import numpy as np

    monkeypatch.syspath_prepend(str(COMMON / "oracle"))
    from coating_planner import CollisionGuard, Motion, _TrajectoryRow, bypass_dry_intervals

    rest = np.zeros(7)
    motion = Motion(rest, rest, 0., 20_000_000, 250, .01,
                    np.full(7, -2.), np.full(7, 2.), np.full(7, 3.), np.full(7, 8.))

    def knot(time_ns: int, position_rad: float, flow_ml_s: float) -> _TrajectoryRow:
        """Make a stopped knot with a displacement of the first arm joint."""
        return {"t_ns": time_ns, "q_rad": [position_rad] + [0.] * 6,
                "qd_rad_s": rest.tolist(), "flow_ml_s": flow_ml_s}

    def accepts(knots: list[_TrajectoryRow]) -> bool:
        """Reject the direct 0-to-1 radian transfer while admitting detour legs."""
        return all((left["q_rad"][0], right["q_rad"][0]) != (0., 1.)
                   for left, right in zip(knots[:-1], knots[1:], strict=True))

    def clear_at(_point: np.ndarray, _margin_m: float) -> bool:
        """Accept all vertices so the synthetic obstruction only affects the sweep."""
        return True

    guard = cast(CollisionGuard, SimpleNamespace(
        workpiece=SimpleNamespace(world=[object()]), accepts=accepts, clear_at=clear_at,
    ))
    rows = [knot(0, 0., 0.), knot(1_000_000_000, 1., .4), knot(2_000_000_000, 1.2, 0.)]
    result = bypass_dry_intervals(rows, motion, guard)

    assert result is not None
    assert len(result) == 4 and result[1]["flow_ml_s"] == 0.
    assert accepts(result)
    assert result[-1]["t_ns"] - result[-2]["t_ns"] == rows[-1]["t_ns"] - rows[-2]["t_ns"]
    assert dict(result[-2], t_ns=rows[-2]["t_ns"]) == rows[-2]
    assert dict(result[-1], t_ns=rows[-1]["t_ns"]) == rows[-1]

    rows[0]["flow_ml_s"] = .4
    assert bypass_dry_intervals(rows, motion, guard) is None
