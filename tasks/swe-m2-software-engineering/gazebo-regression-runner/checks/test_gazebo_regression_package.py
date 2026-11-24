"""Exercise SDF wiring in a correctly isolated runtime package."""

import json
from pathlib import Path
import subprocess
import sys

TASK=Path(__file__).resolve().parents[1]


def test_sdf_regression_packaged_scope_and_frame_report(tmp_path: Path) -> None:
    """Validate a real composed frame via the bundled executable verifier."""
    bundle=tmp_path/"bundle"
    subprocess.run([sys.executable,"-B",str(TASK/"scripts"/"package_task.py"),"--output",str(bundle)],check=True)
    assert (bundle/"environment"/"example"/"rover.sdf").exists()
    assert not (bundle/"environment"/"shadow.py").exists()
    step=bundle/"steps"/"01-inspect-sdf-wiring"
    report=tmp_path/"report"
    subprocess.run([sys.executable,"-IB",str(step/"tests"/"verify.py"),"--stage","1","--artifact",
                    str(step/"solution"/"sim_regression"),"--output",str(report)],check=True)
    assert json.loads((report/"checkpoint.json").read_text())["reward"]==1
