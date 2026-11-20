"""A call that ends or blocks its replay job must not cost the calls queued behind it."""


def ok(vid):
    return ["ok", vid]


def test_replay_jobs_resume_after_a_call_that_crashes_or_hangs(scenario):
    data = scenario("vector_jobs")
    results, starts = data["results"], data["starts"]
    # a job that runs through is started once
    assert results["ok1"] == ok("ok1") and results["ok2"] == ok("ok2") and starts["mod_ok"] == 1
    # the call that ended the process does not match; the calls behind it are replayed in a new
    # process, and the half-written line it left does not spoil the next result
    assert results["c1"] == ok("c1") and results["c2_crash"] is None
    assert results["c3"] == ok("c3") and results["c4"] == ok("c4") and starts["mod_crash"] == 2
    # the same for a call that blocks past its own time limit
    assert results["h1"] == ok("h1") and results["h2_hang"] is None and results["h3"] == ok("h3")
    assert starts["mod_hang"] == 2


def test_a_start_that_returns_nothing_costs_only_its_unit(scenario):
    data = scenario("vector_jobs")
    results, starts = data["results"], data["starts"]
    # the first call of a unit ends the process before any result: the rest of that unit does not
    # match and the job resumes at the next unit, which is replayed in full
    assert results["b1_die"] is None and results["b2_die"] is None
    assert results["b3"] == ok("b3") and results["b4"] == ok("b4") and starts["mod_barren"] == 2
    # a module whose every start returns nothing loses its own unit's calls, and nothing more
    assert [results[v] for v in ("d1", "d2", "d3")] == [None, None, None] and starts["mod_dead"] == 1
    # an import that never finishes ends the job in one start: every unit of it is lost at once,
    # instead of one unit per restart
    assert results["i1"] is None and results["i2"] is None and starts["mod_import_hang"] == 1
    # calls of units that were not restored are not replayed
    assert "s1" not in results and "mod_not_restored" not in starts


def test_a_call_that_runs_out_of_time_is_followed_by_a_fresh_process(scenario):
    data = scenario("vector_jobs")
    results, starts = data["results"], data["starts"]
    # the runner reports the timeout and exits; the calls behind it run in a new process and the
    # slow call itself keeps its (non-matching) result
    assert results["w1_slow"] == ["EXC", "Timeout", []] and results["w3_slow"] == ["EXC", "Timeout", []]
    assert results["w2"] == ok("w2") and starts["mod_slow"] == 2
    # after its second call past the time, the unit's calls left do not match and are not run
    assert results["w4"] is None


def test_a_line_the_runner_did_not_sign_is_not_read(scenario):
    """A body that reached the process wrote a result for the call behind it (unsigned, or with a tag
    made without the key) and that call then ended the runner: the forged line is not read, so the
    call does not match, and the rest of the job runs as usual."""
    data = scenario("vector_jobs")
    results = data["results"]
    assert results["f1_forged"] == ok("f1_forged") and results["f2_victim"] is None and results["f3"] == ok("f3"), results
