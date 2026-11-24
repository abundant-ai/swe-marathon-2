"""Run recorded and closed-loop private cases in a separate environment."""

import argparse
import json
from pathlib import Path
import shutil
from subprocess import TimeoutExpired
import tempfile

from probes import CASES
from transport import Violation

PACKAGE = "sim_regression"


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
    with tempfile.TemporaryDirectory(prefix="simulator-regression-") as tmp:
        root = Path(tmp)
        root.chmod(0o755)
        app = root / "app"
        app.mkdir()
        has_code=stage(artifact,app/PACKAGE)
        for index,(first,name,probe,config) in enumerate(CASES):
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
    return {"stage":level,"reward":sum(checks.values())/len(checks),"checks":checks,"observations":observations}


def main() -> None:
    """Protect verifier output and publish checkpoint evidence."""
    p=argparse.ArgumentParser()
    p.add_argument("--stage",type=int,choices=(1,2,3),required=True)
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
