"""An evaluation that cannot finish must not leave a reward."""


def test_evaluation_error_removes_stale_reward_and_reports_the_error(scenario):
    data = scenario("evaluation_error")
    assert data["raised"] is True
    assert data["reward_exists"] is False
    assert data["report"]["status"] == "evaluation_error"
    assert data["report"]["error"] == "sandbox unavailable"
    assert data["report"]["result"] is None
    assert "reward" not in data["metrics_json"]
