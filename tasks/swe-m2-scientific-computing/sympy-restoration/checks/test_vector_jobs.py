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
    # a job that reports nothing twice in a row is given up; its later calls are not reached
    assert results["d1"] is None and "d2" not in results and "d3" not in results and starts["mod_dead"] == 2
    # calls of units that were not restored are not replayed
    assert "s1" not in results and "mod_not_restored" not in starts
