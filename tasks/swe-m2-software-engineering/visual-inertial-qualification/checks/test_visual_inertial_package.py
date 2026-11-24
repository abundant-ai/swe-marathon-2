"""Check runtime packaging without importing native dependencies."""
from pathlib import Path
import subprocess
import sys

TASK = Path(__file__).resolve().parents[1]


def test_portable_package(tmp_path: Path) -> None:
    """Build a temporary runtime bundle and check protected test placement."""
    subprocess.run([sys.executable, "-B", str(TASK/"scripts/package_task.py"),
                    "--output",str(tmp_path)],check=True,capture_output=True,timeout=15)
    bundle=tmp_path/"swe-m2_software-engineering_visual-inertial-qualification"
    assert {item.name for item in bundle.iterdir()} == {"steps","task.toml","environment"}
    assert not list((bundle/"environment").rglob("probes.py"))
    steps=sorted((bundle/"steps").iterdir())
    assert len(steps)==5
    rolling,inertial=steps[-2:]
    assert (rolling/"solution/visqual/__main__.py").is_file()
    assert (rolling/"tests/probes.py").is_file()
    assert (rolling/"solution/visqual/rolling.py").is_file()
    assert (rolling/"tests/rolling_probes.py").is_file()
    assert not (steps[-3]/"tests/rolling_probes.py").exists()
    assert not (steps[-3]/"solution/visqual/rolling.py").exists()
    assert (inertial/"solution/visqual/inertial.py").is_file()
    assert (inertial/"tests/inertial_probes.py").is_file()
    assert (inertial/"tests/verify_rolling.py").read_bytes()==(rolling/"tests/verify.py").read_bytes()
    assert not (rolling/"tests/inertial_probes.py").exists()
    assert not (rolling/"solution/visqual/inertial.py").exists()
    assert not list((bundle/"environment").rglob("rolling_probes.py"))
    assert not list((bundle/"environment").rglob("inertial_probes.py"))
