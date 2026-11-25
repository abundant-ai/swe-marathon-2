"""Evaluate camera-mount recovery and retain the preceding eight checkpoints."""

import argparse
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent))
from checkpoint import stage
from reference import Json
from rewind_checkpoint import evaluate as evaluate_rewind

POSITIVE_MISSIONS = ("mount-retired-survey", "mount-epoch-handover")
MISSION_IDS = (*POSITIVE_MISSIONS, "mount-bounded-retirement")


def mount_score(checks: dict[str, dict[str, bool]]) -> float:
    """Score completed missions after an optical recovery passes all its checks.

    An absent or empty mission contributes zero to the fixed denominator.
    """
    completed = {
        name: bool(checks.get(name)) and all(checks[name].values())
        for name in MISSION_IDS
    }
    if not any(completed[name] for name in POSITIVE_MISSIONS):
        return 0.0
    return sum(completed.values()) / len(MISSION_IDS)


def evaluate(artifact: Path, dataset: Path, *, retain: bool = True) -> Json:
    """Run retained replay and new mount missions with separate candidate copies.

    Args:
        artifact: Submitted application package directory.
        dataset: Packaged trajectory excerpt needed by the retained checks.
        retain: Whether to execute the earlier checkpoints for the total reward.

    Returns:
        Check groups, observations, and the final weighted reward.
    """
    retained = (
        evaluate_rewind(artifact, dataset)
        if retain
        else {"reward": 0.0, "groups": {}, "component_scores": {}}
    )
    with TemporaryDirectory(prefix="lagfusion-mount-") as directory:
        root = Path(directory)
        root.chmod(0o711)
        app = root / "app"
        if stage(artifact, app):
            from mount_probes import mount_cases

            checks, evidence = mount_cases(app, root)
        else:
            checks, evidence = (
                {},
                {"artifact_error": "Missing or invalid lagfusion application artifact"},
            )
    score = mount_score(checks)
    return {
        **retained,
        "stage": 9,
        "groups": dict(retained["groups"], mount=checks),
        "component_scores": dict(
            retained["component_scores"],
            retained_stage8=retained["reward"],
            mount=score,
        ),
        "mount_observations": evidence,
        "reward": round(0.20 * retained["reward"] + 0.80 * score, 12),
    }


def main() -> None:
    """Run the selected checks and publish fresh evidence and Harbor reward files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=int, default=9, choices=[9])
    parser.add_argument("--artifact", type=Path, default=Path("/app/lagfusion"))
    parser.add_argument("--logs", type=Path, default=Path("/logs/verifier"))
    parser.add_argument(
        "--dataset", type=Path, default=Path(__file__).with_name("room1_xy.csv")
    )
    parser.add_argument(
        "--mount-only",
        action="store_true",
        help="run the new missions for local diagnosis",
    )
    args = parser.parse_args()
    args.logs.mkdir(parents=True, exist_ok=True)
    args.logs.chmod(0o700)
    reward_path = args.logs / "reward.json"
    reward_path.unlink(missing_ok=True)
    result = evaluate(args.artifact, args.dataset, retain=not args.mount_only)
    (args.logs / "checkpoint.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    reward_path.write_text(
        json.dumps({"reward": result["reward"]}) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
