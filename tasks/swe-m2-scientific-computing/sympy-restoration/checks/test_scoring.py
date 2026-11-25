"""The reward: min(unit share, call share) over the calls nothing visible repeats, gated by the
delivered tree and the measurement's controls; the three bars of a complete restoration are
reported as `complete`."""

import pytest


def test_registry_lists_every_mandatory_check_once(scenario):
    data = scenario("registry")
    assert data["checks"] == data["mandatory"]
    assert len(set(data["checks"])) == len(data["checks"]) == 5
    assert all(needs == ["candidate_tree"] for name, needs in data["requires"].items() if name != "candidate_tree")


def test_published_thresholds_are_loaded(scenario):
    assert scenario("config")["scoring"] == {"unit_bar": 0.99, "call_bar": 0.9, "test_bar": 0.95}


def test_reward_is_the_smaller_of_the_unit_and_call_shares(scenario):
    data = scenario("partial")
    # 48 of 80 units, 80 of 160 calls: min(0.6, 0.5)
    assert data["metrics"]["unit_share"] == 0.6 and data["metrics"]["call_share"] == 0.5
    assert data["metrics"]["reward"] == 0.5 and data["reward_txt"] == "0.500000"
    assert data["metrics_json"]["reward"] == 0.5 and data["metrics_json"]["complete"] is False
    # the three bars are reported, and the tests share does not enter the reward
    assert data["metrics"]["test_share"] == 0.1 and data["metrics"]["unit_pass_rate"] == 0.5
    assert "partial_score" not in data["metrics_json"]


def test_the_reference_scores_one_and_is_complete(scenario):
    data = scenario("reference")
    assert data["reward_txt"] == "1.000000" and data["metrics"]["complete"] is True
    assert set(data["status"].values()) == {"passed"}


def test_complete_needs_all_three_bars_exactly(scenario):
    data = scenario("pass")
    assert data["metrics"]["complete"] is True and set(data["status"].values()) == {"passed"}
    assert data["metrics"]["reward"] == pytest.approx(min(79 / 80, 150 / 160))


@pytest.mark.parametrize(
    ("case", "failed_check", "reward"),
    [
        ("units_below", "unit_restoration", 78 / 80),
        ("calls_below", "reference_calls", 140 / 160),
        ("tests_below", "repository_tests", 1.0),
    ],
)
def test_one_missed_bar_is_not_complete_and_leaves_the_reward_to_the_shares(scenario, case, failed_check, reward):
    data = scenario(case)
    assert data["metrics"]["complete"] is False and data["metrics"]["reward"] == pytest.approx(reward)
    assert [name for name, status in data["status"].items() if status != "passed"] == [failed_check]


def test_a_tripped_control_gives_zero_whatever_the_shares(scenario):
    data = scenario("tripped")
    assert data["reward_txt"] == "0.000000" and data["metrics"]["complete"] is False
    assert data["metrics"]["unit_share"] == 1.0 and data["status"]["measurement_integrity"] == "failed"


@pytest.mark.parametrize("case", ["nothing_delivered", "nothing_restored"])
def test_missing_work_fails_the_prerequisite_and_skips_the_rest(scenario, case):
    data = scenario(case)
    assert data["reward_txt"] == "0.000000" and data["metrics"]["reward"] == 0.0
    assert data["status"]["candidate_tree"] == "failed"
    assert {status for name, status in data["status"].items() if name != "candidate_tree"} == {"skipped"}
    assert data["report_status"] == "completed"


def test_failure_text_states_the_measured_share(scenario):
    text = scenario("candidate_failure_text")["explanation"]["unit_restoration"]
    assert "98 of 100" in text and "0.99" in text


def test_items_not_reached_that_could_change_the_reward_are_an_evaluation_error(scenario):
    assert "did not reach" in scenario("units_unreached")["error"]
    assert "did not reach" in scenario("calls_unreached")["error"]
    # the smaller share was measured in full, or the change is within the tolerance: a completed result
    data = scenario("unreached_not_the_minimum")
    assert "error" not in data and data["reward"] == 0.5
    data = scenario("unreached_within_tolerance")
    assert "error" not in data and data["reward"] == 0.75
    # a reward a tripped control already sets to 0 is not undetermined
    data = scenario("unreached_tripped")
    assert "error" not in data and data["reward"] == 0.0


def test_tests_not_reached_leave_complete_open_and_the_reward_alone(scenario):
    data = scenario("tests_unreached")
    assert "error" not in data and data["reward"] == 1.0 and data["complete"] is None
    # another bar is missed anyway, or the tests not reached could not close the gap: not complete
    for case in ("tests_unreached_units_below", "tests_unreached_short"):
        data = scenario(case)
        assert "error" not in data and data["complete"] is False, (case, data)


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


def test_reward_type_is_continuous(task_root):
    import tomllib

    config = tomllib.loads((task_root / "task.toml").read_text())
    assert config["metadata"]["reward_type"] == "continuous"
