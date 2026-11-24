"""Run recorded and closed-loop private cases in a separate environment."""

import argparse
import json
from pathlib import Path
import shutil
from subprocess import TimeoutExpired
import tempfile

from authority import CASES_V2, experiment
from probes import CASES
from transport import Violation

PACKAGE = "px4_recovery"


def stage(source: Path, target: Path) -> bool:
    """Pass only a bounded regular application tree to the candidate process."""
    if not source.is_dir() or source.is_symlink():
        return False
    size = 0
    for i, path in enumerate(source.rglob("*")):
        if i > 600 or path.is_symlink() or not (path.is_file() or path.is_dir()):
            return False
        if path.is_file():
            size += path.stat().st_size
            if size > 12_000_000:
                return False
    shutil.copytree(source,target,ignore=shutil.ignore_patterns("__pycache__"))
    for child in target.rglob("*"):
        child.chmod(0o755 if child.is_dir() else 0o644)
    return True


def grade(artifact: Path, level: int) -> dict:
    """Score independent experiments with separate scratch and no reference imports."""
    checks, observations = {}, {}
    cases = CASES + [(4, case['name'], experiment, case) for case in CASES_V2]
    commissioning_cases = []
    flight_cases = []
    landing_cases = []
    moving_cases = []
    relative_cases = []
    if level >= 5:
        from commission_checks import COMMISSION_CASES, check_commission
        commissioning_cases = [(5,case["name"],check_commission,case) for case in COMMISSION_CASES]
    if level >= 6:
        from flight_native import FLIGHT_CASES, check_flight
        flight_cases = [(6,case["name"],check_flight,case) for case in FLIGHT_CASES]
    if level >= 7:
        from landing_native import LANDING_CASES, check_landing
        landing_cases = [(7,case["name"],check_landing,case) for case in LANDING_CASES]
    if level >= 8:
        from moving_native import MOVING_CASES, check_moving
        moving_cases = [(8,case["name"],check_moving,case) for case in MOVING_CASES]
    if level >= 9:
        from relative_native import RELATIVE_CASES, check_relative
        relative_cases = [(9,case["name"],check_relative,case) for case in RELATIVE_CASES]
    with tempfile.TemporaryDirectory(prefix="px4-bench-") as tmp:
        root = Path(tmp)
        root.chmod(0o755)
        app = root / "app"
        app.mkdir()
        has_code=stage(artifact,app/PACKAGE)
        for index,(first,name,probe,config) in enumerate(cases + commissioning_cases + flight_cases + landing_cases + moving_cases + relative_cases):
            if first > level:
                continue
            checks[name]=False
            if not has_code:
                observations[name]="no usable candidate artifact"
                continue
            case=root/f"case-{index}"
            case.mkdir()
            try:
                observations[name]=probe(app,case,config) if config else probe(app,case)
                checks[name]=True
            except (Violation,ValueError,KeyError,TypeError,TimeoutExpired) as error:
                observations[name]=str(error)
    report = {"stage":level,"checks":checks,"observations":observations}
    if level >= 4:
        legacy = sum(checks[name] for _, name, _, _ in CASES) / len(CASES)
        redundancy = sum(checks[case["name"]] for case in CASES_V2) / len(CASES_V2)
        retained = (legacy + 4 * redundancy) / 5
        report.update(reward=retained, legacy=legacy, redundancy=redundancy)
        if level >= 5:
            commissioning = sum(checks[name] for _,name,_,_ in commissioning_cases) / len(commissioning_cases)
            report.update(reward=commissioning, commissioning=commissioning)
        if level >= 6:
            flight = sum(checks[name] for _,name,_,_ in flight_cases) / len(flight_cases)
            flight_reward = 0.20*retained + 0.15*commissioning + 0.65*flight
            report.update(reward=flight_reward, flight=flight, retained=retained)
        if level >= 7:
            landing = sum(checks[name] for _,name,_,_ in landing_cases) / len(landing_cases)
            report.update(reward=0.20*flight_reward + 0.80*landing, prior_flight_reward=flight_reward, landing=landing)
        if level >= 8:
            moving = sum(checks[name] for _,name,_,_ in moving_cases) / len(moving_cases)
            any_touchdown = any(checks[name] for _,name,_,case in moving_cases
                               if case["case"]!="persistent-loss")
            previous = report["reward"]
            report.update(reward=.20*previous+(.80*moving if any_touchdown else 0.),
                          prior_landing_reward=previous, moving_landing=moving)
        if level >= 9:
            relative = sum(checks[name] for _,name,_,_ in relative_cases) / len(relative_cases)
            any_touchdown = any(checks[name] for _,name,_,case in relative_cases
                               if case["case"]!="bearing-loss-abort")
            previous = report["reward"]
            report.update(reward=.20*previous+(.80*relative if any_touchdown else 0.),
                          prior_moving_reward=previous, relative_landing=relative)
    else:
        report["reward"] = sum(checks.values()) / len(checks)
    return report


def main() -> None:
    """Protect verifier output and publish checkpoint evidence."""
    p=argparse.ArgumentParser()
    p.add_argument("--stage",type=int,choices=(1,2,3,4,5,6,7,8,9),required=True)
    p.add_argument("--artifact",type=Path,default=Path("/app")/PACKAGE)
    p.add_argument("--output",type=Path,default=Path("/logs/verifier"))
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    args.output.chmod(0o700)
    report=grade(args.artifact,args.stage)
    (args.output/"checkpoint.json").write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    (args.output/"reward.txt").write_text(f"{report['reward']:.12g}\n")


if __name__=="__main__":
    main()
