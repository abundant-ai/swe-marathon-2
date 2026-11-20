"""The reward formula: thresholds, fixed denominators and mandatory conditions."""

import pytest


def test_registry_lists_every_mandatory_check_once(scenario):
    data = scenario("registry")
    assert data["checks"] == data["mandatory"]
    assert len(set(data["checks"])) == len(data["checks"]) == 5
    assert all(needs == ["candidate_tree"] for name, needs in data["requires"].items() if name != "candidate_tree")


def test_published_thresholds_are_loaded(scenario):
    assert scenario("config")["scoring"] == {"unit_bar": 0.99, "call_bar": 0.9, "test_bar": 0.95}


def test_reward_is_one_exactly_at_the_thresholds(scenario):
    data = scenario("pass")
    assert data["passed"] is True and data["reward_txt"] == "1"
    assert data["metrics"]["unit_pass_rate"] == 0.99
    assert data["metrics"]["call_match_rate"] == 0.9
    assert data["metrics"]["test_pass_rate"] == 0.95
    assert set(data["status"].values()) == {"passed"}


@pytest.mark.parametrize(
    ("case", "failed_check"),
    [
        ("units_below", "unit_restoration"),
        ("calls_below", "reference_calls"),
        ("tests_below", "repository_tests"),
        ("tripped", "measurement_integrity"),
    ],
)
def test_one_missed_condition_gives_reward_zero(scenario, case, failed_check):
    data = scenario(case)
    assert data["passed"] is False and data["reward_txt"] == "0"
    assert data["status"][failed_check] == "failed"
    assert [name for name, status in data["status"].items() if status != "passed"] == [failed_check]


def test_partial_score_pools_fixed_denominators(scenario):
    data = scenario("units_below")
    assert data["metrics"]["partial_score"] == pytest.approx((98 + 400 + 200) / 700, abs=1e-6)
    assert data["metrics_json"]["partial_score"] == data["metrics"]["partial_score"]
    assert data["metrics_json"]["reward"] == 0


@pytest.mark.parametrize("case", ["nothing_delivered", "nothing_restored"])
def test_missing_work_fails_the_prerequisite_and_skips_the_rest(scenario, case):
    data = scenario(case)
    assert data["reward_txt"] == "0" and data["metrics"]["partial_score"] == 0.0
    assert data["status"]["candidate_tree"] == "failed"
    assert {status for name, status in data["status"].items() if name != "candidate_tree"} == {"skipped"}
    assert data["report_status"] == "completed"


def test_failure_text_states_the_measured_share(scenario):
    text = scenario("candidate_failure_text")["explanation"]["unit_restoration"]
    assert "98 of 100" in text and "0.99" in text


def test_a_verdict_that_items_not_reached_would_decide_is_an_evaluation_error(scenario):
    # every other condition met: the tests not reached would decide, so no reward is published
    assert "repository_tests" in scenario("tests_unreached")["error"]
    assert "reference_calls" in scenario("calls_unreached")["error"]
    # another bar is missed anyway, or the items not reached could not close the gap: a completed 0
    for case in ("tests_unreached_units_below", "tests_unreached_short"):
        data = scenario(case)
        assert data["reward"] == 0.0 and "error" not in data, (case, data)


def test_one_deadline_covers_the_measurement_inside_the_verifier_limit(task_root):
    import json
    import re

    config = json.loads((task_root / "steps/01-restore-bodies/tests/verifier/grade_config.json").read_text())
    toml = (task_root / "task.toml").read_text()
    limit = int(re.search(r"^\[verifier\]\n(?:.*\n)*?timeout_sec = (\d+)$", toml, re.M).group(1))
    assert "pytest_budget_sec" not in config, "the test phase has the time the earlier phases leave"
    assert config["doctest_budget_sec"] + config["vector_budget_sec"] < config["measure_budget_sec"] <= limit - 600
    engine = (task_root / "steps/01-restore-bodies/tests/verifier/engine.py").read_text()
    assert "time.time()" not in engine and "time.time()" not in (task_root / "steps/01-restore-bodies/tests/verifier/lib/gradelib.py").read_text()
    body = engine[engine.index("def measure("):]
    assert "deadline=deadline)" in body and 'deadline = t_start + float(cfg.get("measure_budget_sec", 6000))' in body
