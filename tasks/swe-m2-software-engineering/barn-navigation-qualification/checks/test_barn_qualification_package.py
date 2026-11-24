"""Private map qualification regression for the staged runtime."""

import json
from pathlib import Path
import subprocess
import sys

TASK=Path(__file__).resolve().parents[1]


def test_barn_packaged_footprint_and_shortest_route(tmp_path: Path) -> None:
    """Exercise the bundled shortest grid route and footprint-blocked cases."""
    bundle=tmp_path/"bundle"
    subprocess.run([sys.executable,"-B",str(TASK/"scripts"/"package_task.py"),"--output",str(bundle)],check=True)
    stage=bundle/"steps"/"01-plan-clear-routes"
    assert (bundle/"environment"/"example"/"NOTICE.txt").exists()
    assert not (bundle/"environment"/"probes.py").exists()
    out=tmp_path/"out"
    subprocess.run([sys.executable,"-IB",str(stage/"tests"/"verify.py"),"--stage","1","--artifact",
                    str(stage/"solution"/"barn_qualification"),"--output",str(out)],check=True)
    assert json.loads((out/"checkpoint.json").read_text())["reward"]==1
