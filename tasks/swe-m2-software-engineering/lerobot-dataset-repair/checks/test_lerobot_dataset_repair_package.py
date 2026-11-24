"""Check the LeRobot task packaging and source asset provenance."""

from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import tomllib

import pytest


ROOT = Path(__file__).resolve().parents[1]


def get_packager():
    """Load the task's standalone packager without cross-task imports."""
    spec = spec_from_file_location("lerobot_repair_packager", ROOT / "scripts/package_task.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_lerobot_repair_bundle_stage_scopes(tmp_path):
    """Keep authoring files private and introduce only the current oracle modules."""
    packager = get_packager()
    bundle = packager.package(tmp_path)
    config = tomllib.loads((bundle / "task.toml").read_text())
    assert config["artifacts"] == ["/app/lerobot_repair"]
    assert config["verifier"]["environment_mode"] == "separate"
    assert not {"README.md", "common", "scripts", "checks", "experiment"} & {item.name for item in bundle.iterdir()}

    modules = set()
    for step, introduced in zip(config["steps"], packager.MODULES, strict=True):
        modules.update(introduced)
        location = bundle / "steps" / step["name"]
        assert {item.name for item in (location / "solution/lerobot_repair").iterdir()} == modules
        assert (location / "instruction.md").is_file()
        assert (location / "tests/time_probes.py").is_file() == ("clocked.py" in modules)
        assert (location / "tests/action_probes.py").is_file() == ("actions.py" in modules)
        assert (location / "tests/requirements.txt").read_bytes() == (
            bundle / "environment/requirements.txt").read_bytes()
        assert (location / "tests/so101-rows.parquet").read_bytes() == (
            bundle / "environment/resources/so101-rows.parquet").read_bytes()
    assert (bundle / "environment/resources/action_example.py").is_file()
    global_stage=bundle/"steps/06-reconstruct-global-actions"
    assert (global_stage/"tests/journal_probes.py").is_file()
    assert (global_stage/"solution/lerobot_repair/queue_recovery.py").is_file()
    assert not (bundle/"steps/05-qualify-actuation/tests/journal_probes.py").exists()
    assert not (bundle / "environment/resources/action_probes.py").exists()
    final = bundle / "steps/05-qualify-actuation/tests"
    assert (final / "so101-headless.xml").read_bytes() == (
        bundle / "environment/resources/so101-headless.xml").read_bytes()
    with pytest.raises(ValueError):
        packager.package(tmp_path)


def test_lerobot_repair_fixture_attribution():
    """Keep the redistributed sample tied to its recorded derivation."""
    resources = ROOT / "environment/resources"
    expected = "e58a74e93ebb7ec34fb490c2e08815bb5ce30333af094cd550c2a8010f3bbe50"
    assert sha256((resources / "so101-rows.parquet").read_bytes()).hexdigest() == expected
    assert expected in (resources / "SO101-ATTRIBUTION.md").read_text()
    assert "https://creativecommons.org/licenses/by/4.0/" in (resources / "SO101-ATTRIBUTION.md").read_text()


def test_lerobot_repair_native_episode_scaffolding(tmp_path):
    """Keep orphan evidence structurally native so strict independent readers can audit it."""
    import os
    import subprocess
    import sys

    pytest.importorskip("pyarrow")
    pytest.importorskip("av")
    script = """
from pathlib import Path
import sys
import pyarrow.parquet as pq
from fixtures import fixture
root, asset = map(Path, sys.argv[1:])
data = fixture(root, asset)
files = sorted((data.root / 'meta/episodes').glob('chunk-*/file-*.parquet'))
columns = [set(pq.ParquetFile(file).schema_arrow.names) for file in files]
assert len(columns) > 1 and all(current == columns[0] for current in columns[1:])
assert {'episode_index', 'length', 'dataset_from_index', 'dataset_to_index'} <= columns[0]
assert any(row['issues'] == ['NO_FRAME_ROWS'] for row in data.audit['episodes'])
"""
    environment = dict(os.environ, PYTHONPATH=str(ROOT / "common/verifier"))
    subprocess.run([sys.executable, "-B", "-c", script, tmp_path,
                    ROOT / "environment/resources/so101-rows.parquet"], env=environment, check=True)
