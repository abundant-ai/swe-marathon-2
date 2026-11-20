"""Only unit bodies travel from the submitted tree into the graded tree."""


def test_only_accepted_unit_bodies_reach_the_graded_tree(scenario):
    data = scenario("transplant")
    assert data["states"]["U0001"] == "restored"
    assert data["states"]["U0002"] == "todo"
    assert data["states"]["U0003"].startswith("rejected")
    candidate = data["candidate"]
    assert "return x * 2" in candidate
    # edits outside unit bodies and rejected bodies never arrive
    assert "return x + 1\n" in candidate and "x + 100" not in candidate
    assert "HELPER" not in candidate and "os.getcwd" not in candidate
    assert 'raise NotImplementedError("RESTORE U0003")' in candidate


def test_missing_file_keeps_the_skeleton(scenario):
    data = scenario("transplant")
    assert data["missing_states"] == {"U0001": "missing"}
    assert data["missing_is_skeleton"] is True
