"""Requirement checks in execution order.

All five read one measurement pass. `candidate_tree` is the prerequisite: with
no artifact or no restored unit the other four are skipped and score zero.
"""

from verifier.checks import test_candidate_tree as tree
from verifier.checks import test_integrity as integrity
from verifier.checks import test_reference_calls as calls
from verifier.checks import test_repository_tests as repository
from verifier.checks import test_units as units
from verifier.contracts import RegisteredCheck

CHECKS = (
    RegisteredCheck("candidate_tree", tree.test_candidate_tree),
    RegisteredCheck("unit_restoration", units.test_unit_restoration, ("candidate_tree",)),
    RegisteredCheck("reference_calls", calls.test_reference_calls, ("candidate_tree",)),
    RegisteredCheck("repository_tests", repository.test_repository_tests, ("candidate_tree",)),
    RegisteredCheck("measurement_integrity", integrity.test_measurement_integrity, ("candidate_tree",)),
)
