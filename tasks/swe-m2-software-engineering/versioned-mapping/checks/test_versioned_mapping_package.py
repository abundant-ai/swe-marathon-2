"""Validate the staged bundle and calibrate its packaged verifier."""

import importlib.util
from pathlib import Path
import tomllib


TASK_ROOT = Path(__file__).resolve().parents[1]


def task_module(name: str, relative_path: str):
    """Load this task's development module without sharing other tasks' imports."""
    spec = importlib.util.spec_from_file_location(name, TASK_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mapping_bundle_keeps_author_files_out_and_solutions_incremental(tmp_path):
    package_task = task_module("mapping_packager", "scripts/package_task.py")
    bundle = package_task.package(tmp_path)
    config = tomllib.loads((bundle / "task.toml").read_text())
    assert config["artifacts"] == ["/app/versioned_mapping"]
    assert config["verifier"]["environment_mode"] == "separate"
    assert not {"checks", "scripts", "common", "README.md"} & {path.name for path in bundle.iterdir()}
    assert list((bundle / "environment").glob("*.py")) == []

    oracle_files = set()
    for step, introduced_modules in zip(config["steps"], package_task.SOLUTION_STAGES, strict=True):
        oracle_files.update(introduced_modules)
        stage = bundle / "steps" / step["name"]
        assert (stage / "instruction.md").is_file()
        assert {file.name for file in (stage / "solution/versioned_mapping").iterdir()} == oracle_files
        assert {"checkpoint.py", "probes.py", "verify.py", "test.sh"} <= {
            file.name for file in (stage / "tests").iterdir()
        }


def test_mapping_bundle_accepts_reference_and_rejects_noop(tmp_path):
    package_task = task_module("mapping_packager", "scripts/package_task.py")
    calibration = task_module("mapping_calibration", "checks/calibrate.py")
    calibration.calibrate(package_task.package(tmp_path), tmp_path / "calibration")
