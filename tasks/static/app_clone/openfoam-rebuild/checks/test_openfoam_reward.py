"""reward = checks_passed / checks_kept; a failed build passes no check."""

import pytest
from openfoam_verifier import runner
from openfoam_verifier.contracts import CheckResult, VerificationContext
from openfoam_verifier.contracts import Test as Case


def context(tmp_path, n_checks=(2, 2)):
    tests = tuple(
        Case(f"r{i}", "s", "p", tuple(f"c{j}" for j in range(n)), (), {}, 1.0)
        for i, n in enumerate(n_checks)
    )
    app = tmp_path / "app"
    app.mkdir(exist_ok=True)
    return VerificationContext(
        app=app,
        dataset=tmp_path,
        tests=tests,
        output=tmp_path,
        uid=0,
        gid=0,
        workers=1,
        build_timeout=1,
        work=tmp_path,
    )


def with_checks(monkeypatch, build_status, passed):
    def build(ctx):
        return CheckResult("build", build_status, "")

    def recorded(ctx):
        return CheckResult(
            "recorded_runs", "failed", "", {"checks_passed": float(passed)}
        )

    monkeypatch.setattr(
        runner,
        "CHECKS",
        (("build", build, ()), ("recorded_runs", recorded, ("build",))),
    )


def test_missing_compile_script_scores_zero(tmp_path):
    result = runner.verify(context(tmp_path))
    statuses = {c.requirement: c.status for c in result.checks}
    assert statuses == {"build": "failed", "recorded_runs": "skipped"}
    assert result.metrics["reward"] == 0.0 and not result.passed


def test_failed_build_scores_zero_even_if_runs_would_pass(tmp_path, monkeypatch):
    with_checks(monkeypatch, "failed", 4)
    assert runner.verify(context(tmp_path)).metrics["reward"] == 0.0


@pytest.mark.parametrize(
    "passed, reward, resolved, almost",
    [(0, 0.0, 0.0, 0.0), (3, 0.75, 0.0, 0.0), (4, 1.0, 1.0, 1.0)],
)
def test_reward_is_share_of_checks(
    tmp_path, monkeypatch, passed, reward, resolved, almost
):
    with_checks(monkeypatch, "passed", passed)
    m = runner.verify(context(tmp_path)).metrics
    assert (m["reward"], m["resolved"], m["almost"], m["checks"]) == (
        reward,
        resolved,
        almost,
        4.0,
    )


def test_almost_at_95_percent(tmp_path, monkeypatch):
    with_checks(monkeypatch, "passed", 19)
    assert runner.verify(context(tmp_path, (20,))).metrics["almost"] == 1.0
    with_checks(monkeypatch, "passed", 18)
    assert runner.verify(context(tmp_path, (20,))).metrics["almost"] == 0.0
