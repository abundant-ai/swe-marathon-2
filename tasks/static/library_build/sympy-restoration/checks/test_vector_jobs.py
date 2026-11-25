"""A call that ends, blocks or runs past its time costs that call and the rest of its unit, never the
calls of other units; what the runner writes out of order or out of form is never taken."""


def ok(vid):
    return ["ok", vid]


def test_replay_jobs_resume_after_a_call_that_crashes_or_hangs(scenario):
    data = scenario("vector_jobs")
    results, starts = data["results"], data["starts"]
    # a job that runs through is started once
    assert (
        results["ok1"] == ok("ok1")
        and results["ok2"] == ok("ok2")
        and starts["mod_ok"] == 1
    )
    # the call that ended the process does not match; the other unit's calls are replayed in a new
    # process, and the half-written line it left does not spoil them
    assert results["c1"] == ok("c1") and results["c2_crash"] is None
    assert (
        results["c3"] == ok("c3")
        and results["c4"] == ok("c4")
        and starts["mod_crash"] == 2
    )
    # a call that blocks past its time is a Timeout; the rest of its unit is not run; another unit's call runs
    assert (
        results["h1"] == ok("h1")
        and results["h2_hang"] == ["EXC", "Timeout", []]
        and results["h3"] is None
    )
    assert results["h4"] == ok("h4") and starts["mod_hang"] == 2


def test_a_start_that_returns_nothing_costs_only_its_unit(scenario):
    data = scenario("vector_jobs")
    results, starts = data["results"], data["starts"]
    # the first call of a unit ends the process: the rest of that unit does not match and the job
    # resumes at the next unit, which is replayed in full
    assert results["b1_die"] is None and results["b2_die"] is None
    assert (
        results["b3"] == ok("b3")
        and results["b4"] == ok("b4")
        and starts["mod_barren"] == 2
    )
    # a module whose runner ends before its import is done loses its calls at once
    assert [results[v] for v in ("d1", "d2", "d3")] == [None, None, None] and starts[
        "mod_dead"
    ] == 1
    # an import that never finishes ends the job in one start
    assert (
        results["i1"] is None
        and results["i2"] is None
        and starts["mod_import_hang"] == 1
    )
    # calls of units that were not restored are not replayed
    assert "s1" not in results and "mod_not_restored" not in starts


def test_a_call_that_runs_out_of_time_skips_the_rest_of_its_unit(scenario):
    data = scenario("vector_jobs")
    results, starts = data["results"], data["starts"]
    assert results["w1_slow"] == ["EXC", "Timeout", []] and results["w2"] is None
    assert (
        results["w3"] == ok("w3")
        and results["w4"] == ok("w4")
        and starts["mod_slow"] == 2
    )
    assert data["stats"]["timeouts"] == 2 and data["stats"]["units_cut"] == 4, data[
        "stats"
    ]


def test_what_the_runner_writes_out_of_order_or_out_of_form_is_never_taken(scenario):
    """A body that reached the process wrote a result for the call behind it (the call's own result
    then is out of order), one wrote a line past the limit, one sent a list as the call's id: each costs
    its own call and the rest of its unit; the forged result is never taken, and nothing raises."""
    data = scenario("vector_jobs")
    results = data["results"]
    assert (
        results["f1_forged"] is None
        and results["f2_victim"] == ok("f2_victim")
        and results["f3"] == ok("f3")
    ), results
    assert (
        results["x1_flood"] is None
        and results["x2"] is None
        and results["x3"] == ok("x3")
    )
    assert results["l1_listid"] is None and results["l2"] == ok("l2")
    assert data["stats"]["malformed"] >= 2 and data["stats"]["ended_or_stopped"] >= 1, (
        data["stats"]
    )
