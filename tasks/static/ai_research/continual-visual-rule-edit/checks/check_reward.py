"""Exercise retention boundaries and the frozen-encoder cap using real calibration records."""

import json
import sys
from copy import deepcopy
from math import isclose, nextafter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "tests/private/precision-pilot"
sys.path.insert(0, str(MODULES))
from inspection_eval import reward
from source_registration import score_edits


def check_controls(controls):
    """The matched reference retains its measured score on both target deployments."""
    assert reward(controls["informed_0"], 0, controls)["reward"] == 1.0
    assert reward(controls["informed_1"], 0, controls)["reward"] == 0.0
    assert isclose(reward(controls["informed_1"], 1, controls)["reward"], 2 / 3)
    assert reward(controls["untreated"], 0, controls)["reward"] == 0.0


def check_archive_boundary(controls, field, threshold):
    """Verify both the site exclusion and the fixed-denominator plasticity cap."""
    actual = deepcopy(controls["informed_0"])
    record = actual["installation"][0][0]
    record[field] = threshold
    at = reward(actual, 0, controls)
    assert at["reward"] == 1.0 and at["pairs"][0]["reward"] == 1.0
    record[field] = nextafter(threshold, float("inf"))
    over = reward(actual, 0, controls)
    assert [p["reward"] for p in over["pairs"]] == [0, 1, 1, 1, 1, 1]
    gain = over["acquisition_vs_own_frozen"]
    expected = (min(0, gain["per_site"][0]) + sum(gain["per_site"][1:])) / (
        6 * gain["anchor"]
    )
    assert isclose(gain["normalized"], min(1, max(0, expected)))
    assert isclose(over["reward"], min(5 / 6, gain["normalized"]))


def check_plasticity(controls):
    """Holding the installed encoders fixed throughout must remove the paired plasticity gain."""
    actual = deepcopy(controls["informed_0"])
    actual["runs"][0] = actual["frozen_runs"][0]
    result = reward(actual, 0, controls)
    assert result["acquisition_vs_own_frozen"]["mean"] == 0
    assert result["reward"] == 0


def check_negative_gain(controls):
    """A site that loses plasticity cannot increase the score by also forgetting an old task."""
    candidate = deepcopy(controls["informed_0"])
    for train, frozen in zip(
        candidate["runs"][0][:3], candidate["frozen_runs"][0][:3], strict=True
    ):
        train["initial"][0] = frozen["initial"][0] - 0.025
    retained = reward(candidate, 0, controls)
    candidate["installation"][0][0]["loss"] = 0.021
    failed = reward(candidate, 0, controls)
    assert (
        failed["acquisition_vs_own_frozen"]["normalized"]
        == retained["acquisition_vs_own_frozen"]["normalized"]
    )
    assert failed["reward"] <= retained["reward"]


def check_small_forgetting_contrast(controls):
    """Exercise the two-point tolerance at a site with no contrast on peak forgetting."""
    changed = deepcopy(controls)
    for group in ("informed_0", "untreated"):
        for run in changed[group]["runs"][0][:3]:
            run["peak_forgetting"] = 0.0
    actual = deepcopy(changed["informed_0"])
    for value, expected in ((0.02, 1.0), (nextafter(0.02, float("inf")), 0.0)):
        for run in actual["runs"][0][:3]:
            run["peak_forgetting"] = value
        first = reward(actual, 0, changed)["pairs"][0]
        assert first["gains"][4] == first["reward"] == expected


def check_calibration_floor(controls):
    """A reference whose encoders add too little future learning cannot calibrate the score."""
    calibrated = deepcopy(controls)
    reference = calibrated["informed_0"]
    for run in reference["frozen_runs"][0]:
        run["initial"][0] = 0.0
    for run in reference["runs"][0]:
        run["initial"][0] = 0.01
    measured = reward(controls["informed_0"], 0, calibrated)
    assert measured["acquisition_vs_own_frozen"]["anchor"] == 0.01
    for run in reference["runs"][0]:
        run["initial"][0] = nextafter(0.01, 0.0)
    try:
        reward(controls["informed_0"], 0, calibrated)
    except ValueError as error:
        assert "pooled adaptation contrast" in str(error)
    else:
        raise AssertionError("Accepted a calibration below the one-point gain floor")


def check_diagnostic_isolation(controls):
    """Loss of an optional diagnostic keeps all production denominators and the selected reward."""

    def continuation(site, target, seed, old, new, rates):
        if target == 1:
            raise FloatingPointError("unavailable diagnostic")
        index = 3 * site + (411, 939, 1411).index(seed)
        return controls["untreated"]["runs"][target][index]

    measured = score_edits(None, continuation, diagnostic_target=1)
    assert measured["unavailable_handovers"] == [1]
    assert [len(arm) for arm in measured["runs"]] == [18, 0]
    assert [len(arm) for arm in measured["frozen_runs"]] == [18, 0]
    assert reward(measured, 0, controls)["reward"] == 0
    try:
        score_edits(None, continuation, diagnostic_target=0)
    except FloatingPointError:
        pass
    else:
        raise AssertionError("Official handover instability must propagate")


if __name__ == "__main__":
    controls = json.loads((MODULES / "data/inspection-controls.json").read_text())
    check_controls(controls)
    check_diagnostic_isolation(controls)
    check_negative_gain(controls)
    check_archive_boundary(controls, "loss", 0.02)
    check_archive_boundary(controls, "drift", 0.08)
    check_plasticity(controls)
    check_calibration_floor(controls)
    check_small_forgetting_contrast(controls)
    print(
        "Verified control scores, both archive boundaries, paired plasticity and forgetting tolerance."
    )
