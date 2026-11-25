"""Self-check for the grader: the test runner must still tell right from wrong."""


def test_must_pass():
    assert 1 + 1 == 2


def test_must_fail():
    assert 1 + 1 == 3
