"""Grade one checkpoint of the BARN navigation qualification.

Every case runs the submitted package as the unprivileged candidate account on
inputs that only the verifier holds. A case fails only on a contract
violation. Any other exception is a verifier fault: it propagates, the step
exits nonzero and no reward file is left behind.

Stage k earns passed/COUNTS[k] once at least one of its positive cases passes,
and nothing otherwise, so a package that only ever answers "blocked" or
"waiting" earns nothing. The checkpoint reward nests the stages:
r1 = credit1 and r_k = 0.2 * r_(k-1) + 0.8 * credit_k.
"""

import argparse
import json
from pathlib import Path
import shutil
import tempfile
from time import monotonic

from probes import CASES
from transport import PACKAGE, Violation

COUNTS = {1: 3, 2: 3, 3: 5, 4: 18, 5: 12}
POSITIVE = {
    1: {"shortest_authored_clutter_plan", "recorded_world_zero_crop_plan"},
    2: {"closed_loop_staggered_aisles", "closed_loop_real_obstacle_crop"},
    3: {"temporary_gate_opens_with_old_revision_noise", "midrun_cell_closure_and_lost_pose",
        "independent_completion_metric"},
}  # in stages 4 and 5 every field mission is positive
CARRY = 0.2
MAX_ENTRIES = 1024
MAX_BYTES = 12_000_000


def registry(level: int) -> list:
    """Every case of stages 1..level, checked against the fixed stage sizes."""
    cases = [case for case in CASES if case[0] <= level]
    if level >= 4:
        from courses import MISSIONS
        from field import field_mission
        cases += [(mission["stage"], name, field_mission, {"mission": name})
                  for name, mission in MISSIONS.items() if mission["stage"] <= level]
    for k in range(1, level + 1):
        names = [name for first, name, _, _ in cases if first == k]
        if len(names) != COUNTS[k] or len(set(names)) != len(names):
            raise AssertionError(f"stage {k} registers {len(names)} cases instead of {COUNTS[k]}")
        if not POSITIVE.get(k, set()) <= set(names):
            raise AssertionError(f"stage {k} names a positive case it does not register")
    return cases


def stage(source: Path, target: Path) -> bool:
    """Copy a bounded tree of regular files for the candidate account to run."""
    if not source.is_dir() or source.is_symlink():
        return False
    size = 0
    for count, path in enumerate(source.rglob("*"), 1):
        if count > MAX_ENTRIES or path.is_symlink() or not (path.is_file() or path.is_dir()):
            return False
        if path.is_file():
            size += path.stat().st_size
            if size > MAX_BYTES:
                return False
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))
    for child in [target, *target.rglob("*")]:
        child.chmod(0o755 if child.is_dir() else 0o644)
    return True


def credit(k: int, names: list, checks: dict) -> float:
    """Fraction of stage k that passed, or zero when no positive case passed."""
    positive = POSITIVE.get(k)
    if not any(checks[name] for name in names if positive is None or name in positive):
        return 0.0
    return sum(checks[name] for name in names) / COUNTS[k]


def nested(credits: dict) -> float:
    """Checkpoint reward: each stage keeps a 0.2 share of everything before it."""
    reward = 0.0
    for k in sorted(credits):
        reward = credits[k] if k == 1 else round(CARRY * reward + (1 - CARRY) * credits[k], 12)
    return reward


def grade(artifact: Path, level: int, only: set | None = None) -> dict:
    """Run the cases of stages 1..level in one scratch tree; ``only`` selects a diagnostic subset."""
    cases = [case for case in registry(level) if only is None or case[1] in only]
    checks, observations, seconds = {}, {}, {}
    began = monotonic()
    with tempfile.TemporaryDirectory(prefix="barn-grade-", ignore_cleanup_errors=True) as scratch:
        root = Path(scratch)
        root.chmod(0o755)
        app = root / "app"
        app.mkdir()
        usable = stage(artifact, app / PACKAGE)
        for index, (_, name, probe, config) in enumerate(cases):
            checks[name] = False
            if not usable:
                observations[name] = "no usable candidate artifact"
                continue
            case = root / f"case-{index:02d}"
            case.mkdir()
            start = monotonic()
            try:
                observations[name] = probe(app, case, config)
                checks[name] = True
            except Violation as error:
                observations[name] = str(error)
            seconds[name] = round(monotonic() - start, 3)
    stages = {}
    for k in sorted({first for first, _, _, _ in cases}):
        names = [name for first, name, _, _ in cases if first == k]
        stages[k] = {"passed": sum(checks[name] for name in names), "cases": len(names),
                     "runtime_s": round(sum(seconds.get(name, 0.0) for name in names), 3)}
    report = {"stage": level, "checks": checks, "observations": observations,
              "runtime_s": {"cases": seconds, "stages": {str(k): row["runtime_s"] for k, row in stages.items()},
                            "total": round(monotonic() - began, 3)}}
    if only is not None:
        report["diagnostic"] = sorted(only)
        return report
    credits = {k: credit(k, [name for first, name, _, _ in cases if first == k], checks) for k in stages}
    report["component_scores"] = {str(k): round(value, 12) for k, value in credits.items()}
    report["passed"] = {str(k): f"{row['passed']}/{row['cases']}" for k, row in stages.items()}
    report["reward"] = nested(credits)
    return report


def main(level: int | None = None) -> None:
    """Grade a checkpoint and publish the evidence, writing the reward last."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stage", type=int, required=True,
                        choices=range(1, len(COUNTS) + 1) if level is None else (level,))
    parser.add_argument("--artifact", type=Path, default=Path("/app") / PACKAGE)
    parser.add_argument("--logs", type=Path, default=Path("/logs/verifier"))
    parser.add_argument("--case", action="append", metavar="NAME",
                        help="diagnostic run of the named case only (repeatable); never writes a reward")
    args = parser.parse_args()
    only = None if args.case is None else set(args.case)
    if only is not None:
        unknown = only - {name for _, name, _, _ in registry(args.stage)}
        if unknown:
            parser.error(f"stage {args.stage} has no case named {', '.join(sorted(unknown))}")
    args.logs.mkdir(parents=True, exist_ok=True)
    args.logs.chmod(0o700)
    reward = args.logs / "reward.txt"
    reward.unlink(missing_ok=True)
    report = grade(args.artifact, args.stage, only)
    (args.logs / "checkpoint.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n",
                                               encoding="utf-8")
    if only is None:
        reward.write_text(f"{report['reward']:.12g}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
