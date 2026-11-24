"""Detect package leaks, stage drift, and changes to the measured source excerpt."""

from hashlib import sha256
from pathlib import Path
import subprocess
import sys
import tomllib

TASK = Path(__file__).resolve().parents[1]


def test_package_has_isolated_checkpoints_and_attributed_excerpt(tmp_path: Path) -> None:
    """Build a temporary bundle and verify the runtime-only stage fingerprints."""
    subprocess.run([sys.executable, "-B", str(TASK / "scripts" / "package_task.py"),
                    "--output", str(tmp_path)], check=True, capture_output=True, timeout=15)
    bundle = tmp_path / "swe-m2_software-engineering_fixed-lag-fusion"
    assert {path.name for path in bundle.iterdir()} == {"task.toml", "environment", "steps"}
    configuration = tomllib.loads((bundle / "task.toml").read_text(encoding="utf-8"))
    assert len(configuration["steps"]) == 8
    source = bundle / "environment" / "resources" / "room1_xy.csv"
    assert sha256(source.read_bytes()).hexdigest() == "7af4a6b86a1a3bc35252693ecf7f1ba2cd5bc77922cfecc57782bb025bed0cad"
    base = bundle / "steps" / "01-smooth-window" / "solution" / "lagfusion"
    final = bundle / "steps" / "04-revise-stream" / "solution" / "lagfusion"
    assert not (base / "session.py").exists()
    assert (final / "session.py").read_bytes() == (TASK / "common/oracle/lagfusion/session.py").read_bytes()
    last = bundle / "steps" / "05-qualify-network"
    assert not (final / "network.py").exists()
    assert (last / "solution" / "lagfusion" / "network.py").read_bytes() == (TASK / "common/oracle/lagfusion/network.py").read_bytes()
    assert (last / "tests" / "network_probes.py").is_file()
    integrity = bundle / "steps" / "06-track-integrity"
    assert not (last / "solution" / "lagfusion" / "integrity.py").exists()
    assert not (last / "tests" / "integrity_probes.py").exists()
    assert (integrity / "solution" / "lagfusion" / "integrity.py").read_bytes() == (TASK / "common/oracle/lagfusion/integrity.py").read_bytes()
    assert (integrity / "tests" / "network_probes.py").is_file()
    assert (integrity / "tests" / "integrity_probes.py").is_file()
    vision = bundle / "steps" / "07-smooth-native-tracks"
    assert not (integrity / "solution" / "lagfusion" / "vision.py").exists()
    assert not (integrity / "tests" / "vision_probes.py").exists()
    assert (vision / "solution" / "lagfusion" / "vision.py").read_bytes() == (TASK / "common/oracle/lagfusion/vision.py").read_bytes()
    assert (vision / "tests" / "vision_probes.py").is_file()
    rewind = bundle / "steps" / "08-reopen-fixed-lag"
    assert not (vision / "solution" / "lagfusion" / "rewind.py").exists()
    assert not (vision / "tests" / "rewind_probes.py").exists()
    assert (rewind / "solution" / "lagfusion" / "rewind.py").is_file()
    assert (rewind / "tests" / "rewind_probes.py").is_file()
    assert "reopen-tracks" not in (vision / "solution" / "lagfusion" / "__main__.py").read_text()
    assert "reopen-tracks" in (rewind / "solution" / "lagfusion" / "__main__.py").read_text()
    assert not list((bundle / "environment").rglob("verify.py"))
