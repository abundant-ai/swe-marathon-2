"""Score complete time-window plans against independently classified outcomes."""

from geometry import Json
from missions import missions
from timed_checks import valid_plan


def window_checks(run) -> Json:
    """Exercise all forecast families with the standalone planner."""
    return {
        case["id"]: valid_plan(
            case["spec"], run("plan-window", case["spec"]), expect_ready=case["expect_ready"],
        )
        for case in missions()
    }
