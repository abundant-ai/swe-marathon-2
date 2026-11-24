"""Runs the registered checks in order and aggregates the reward."""
from __future__ import annotations

from .checks.test_build import test_build
from .checks.test_recorded_runs import test_recorded_runs
from .contracts import CheckResult, VerificationContext, VerificationResult

# (requirement, check, prerequisites)
CHECKS = (
    ("build", test_build, ()),
    ("recorded_runs", test_recorded_runs, ("build",)),
)
ALMOST = 0.95


def verify(context: VerificationContext) -> VerificationResult:
    """Reward: the share of all checks that pass. A failed build passes none. Also reported:
    resolved (every check passes) and almost (at least 95% pass), as in ProgramBench."""
    results: dict[str, CheckResult] = {}
    for name, function, requires in CHECKS:
        unmet = [r for r in requires if results[r].status != "passed"]
        results[name] = (CheckResult(name, "skipped", f"needs {', '.join(unmet)}") if unmet
                         else function(context))
    total = sum(len(t.checks) for t in context.tests)
    passed = results["recorded_runs"].metrics.get("checks_passed", 0.0)
    share = passed / total if total else 0.0
    metrics = {"reward": share, "checks": float(total), "checks_passed": float(passed),
               "resolved": float(share == 1.0), "almost": float(share >= ALMOST)}
    return VerificationResult(share == 1.0, tuple(results.values()), metrics)
