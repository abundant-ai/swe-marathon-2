"""Check runtime packaging without importing native dependencies."""
from pathlib import Path
import subprocess
import sys

TASK = Path(__file__).resolve().parents[1]


def test_portable_package(tmp_path: Path) -> None:
    """Build a temporary runtime bundle and check protected test placement."""
    subprocess.run([sys.executable, "-B", str(TASK/"scripts/package_task.py"),
                    "--output",str(tmp_path)],check=True,capture_output=True,timeout=15)
    bundle=tmp_path/"swe-m2_software-engineering_contact-wrench-calibration"
    assert {item.name for item in bundle.iterdir()} == {"steps","task.toml","environment"}
    assert not list((bundle/"environment").rglob("probes.py"))
    steps=sorted((bundle/"steps").iterdir())
    assert len(steps)==3
    assert (steps[-1]/"solution/wrenchlab/__main__.py").is_file()
    assert (steps[-1]/"tests/probes.py").is_file()
