"""The sealed test phase must not lose tests when pytest hangs or a session ends early."""

FILE_A, FILE_B = "pkg/tests/test_a.py", "pkg/tests/test_b.py"
A = [f"{FILE_A}::test_{i}" for i in range(1, 7)]
B = [f"{FILE_B}::test_1", f"{FILE_B}::test_2"]
BUDGET_NOTE = "sealed test run hit its time budget; unfinished tests count as failed"


def ids_by_tag(data):
    return {run["tag"]: run["ids"] for run in data["asked"]}


def test_complete_session_is_the_only_run(scenario):
    data = scenario("sealed_clean")
    assert (data["runs"], data["passes"]) == (1, 1)
    assert data["asked"] == [{"tag": "s1", "workers": 2, "ids": sorted(A + B)}]
    assert [data["outcome"][t] for t in A + B] == ["passed", "failed", "passed", "passed", "passed", "passed", "passed", "failed"]
    assert data["runner_passed"] == 7  # six sealed passes and the self-check
    assert (data["timed_out"], data["selfcheck_ok"], data["tally_exceeded"], data["notes"]) == (False, True, False, [])


def test_file_reported_as_uncollectable_is_not_run_again(scenario):
    data = scenario("sealed_uncollectable")
    assert (data["runs"], data["passes"]) == (1, 1)
    assert data["outcome"][B[0]] is None and data["outcome"][B[1]] is None
    assert data["timed_out"] is False and data["notes"] == []


def test_tests_a_dead_session_never_started_are_run_per_file(scenario):
    data = scenario("sealed_abort")
    asked = ids_by_tag(data)
    assert (data["runs"], data["passes"]) == (3, 2)
    # the test the session named as its crash is failed and not started again
    assert data["outcome"][A[2]] == "failed"
    assert asked["p2f0"] == A[3:] and asked["p2f1"] == B
    assert [run["workers"] for run in data["asked"]] == [0, 0, 2]
    assert [data["outcome"][t] for t in A] == ["passed", "failed", "failed", "passed", "passed", "failed"]
    # file b turned out to be uncollectable in its own run: no outcome and no third pass
    assert data["outcome"][B[0]] is None and data["outcome"][B[1]] is None
    # tallies of the three runs: (1 + 1) + (2 + 1) + (0 + 1)
    assert data["runner_passed"] == 6
    assert (data["timed_out"], data["selfcheck_ok"], data["tally_exceeded"]) == (False, True, False)
    assert data["notes"] == ["3 tests the session did not finish were settled with one process per test file"]
    assert "==== session over 8 tests: done ====" in data["log"]
    assert f"==== pass 2, {FILE_A}, 3 tests: done ====" in data["log"]


def test_session_that_never_reports_falls_back_to_one_process_per_file(scenario):
    data = scenario("sealed_stall")
    asked = ids_by_tag(data)
    assert (data["runs"], data["passes"]) == (3, 2)
    assert asked["p2f0"] == A and asked["p2f1"] == B
    assert [data["outcome"][t] for t in A] == ["passed", "failed", "passed", "passed", "passed", "passed"]
    # the file that hangs on its own settles nothing and is not tried a second time
    assert data["outcome"][B[0]] is None and data["outcome"][B[1]] is None
    assert data["timed_out"] is False and data["selfcheck_ok"] is True and data["first_test_sec"] is None
    assert data["notes"] == ["the test session stopped reporting and was ended",
                             "6 tests the session did not finish were settled with one process per test file"]


def test_test_left_running_twice_is_failed_and_not_started_again(scenario):
    data = scenario("sealed_unnamed")
    asked = ids_by_tag(data)
    assert (data["runs"], data["passes"]) == (4, 3)
    # both tests that were running when the session ended get a second run
    assert asked["p2f0"] == A[2:]
    # A4 finished there; A3 was left running again, so it is failed and the third pass does not get it
    assert data["outcome"][A[3]] == "passed" and data["outcome"][A[2]] == "failed"
    assert asked["p3f0"] == A[4:]
    assert [data["outcome"][t] for t in A + B] == ["passed", "failed", "failed", "passed", "passed", "passed", "passed", "passed"]


def test_time_budget_ends_the_phase_without_another_pass(scenario):
    data = scenario("sealed_budget")
    assert (data["runs"], data["passes"]) == (1, 1)
    assert data["timed_out"] is True and data["runner_passed"] is None
    assert data["outcome"][A[0]] == "passed" and data["outcome"][A[1]] is None
    assert data["notes"] == [BUDGET_NOTE]


def test_wrong_self_check_in_any_run_is_caught(scenario):
    data = scenario("sealed_selfcheck")
    assert data["runs"] == 3 and data["selfcheck_ok"] is False


def test_run_with_more_passes_on_record_than_pytest_counted_is_caught(scenario):
    data = scenario("sealed_tally")
    assert data["runs"] == 3 and data["tally_exceeded"] is True and data["selfcheck_ok"] is True


def test_pass_limit_bounds_a_file_that_never_finishes(scenario):
    data = scenario("sealed_limit")
    asked = ids_by_tag(data)
    assert data["passes"] == 4
    assert [len(asked[f"p{n}f0"]) for n in (2, 3, 4)] == [5, 4, 3]
    # file b settled nothing in its first own run and is dropped after it
    assert [tag for tag in asked if tag.endswith("f1")] == ["p2f1"]
    assert [data["outcome"][t] for t in A] == ["failed", "passed", "passed", "passed", None, None]
    assert data["timed_out"] is False


def test_records_of_a_run_are_read_strictly(scenario):
    data = scenario("sealed_records")
    # a failure in any phase sticks; unknown ids and malformed lines are ignored
    assert data["outcome"] == {A[0]: "passed", A[1]: "failed"}
    assert data["started"] == A[:3]
    assert data["uncollectable"] == [FILE_B]


def test_watcher_tells_an_ended_run_from_a_stalled_one_and_from_the_budget(scenario):
    data = scenario("sealed_watch")
    assert data["ends"]["state"] == "done" and data["ends"]["test_started"] is True
    assert data["never_reports"]["state"] == "stalled" and data["never_reports"]["test_started"] is False
    # a collection error is a record, but collection is still running: the collection allowance applies
    hang = data["collection_error_then_hang"]
    assert hang["state"] == "stalled" and hang["test_started"] is False and hang["seconds"] >= 3.5
    # once a test has started, silence is measured against the shorter allowance
    stop = data["starts_then_stops"]
    assert stop["state"] == "stalled" and stop["test_started"] is True and stop["seconds"] < 10
    assert data["budget"]["state"] == "budget"
    assert all(run["seconds"] < 20 for run in data.values())


def test_runner_tally_reads_the_final_summary_line(scenario):
    data = scenario("runner_tally")
    assert data == {"finished": 7454, "none_passed": 0, "cut_off": None}
