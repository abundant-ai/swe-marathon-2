"""Check public and private file scopes for the cumulative rollout qualification bundle."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_paired_rollout_bundle(tmp_path):
    """Ship selected runtime dependencies and only the current reference capabilities."""
    spec = spec_from_file_location("rollout_replay_packager", ROOT / "scripts/package_task.py")
    packager = module_from_spec(spec)
    spec.loader.exec_module(packager)
    bundle = packager.package(tmp_path)
    config = tomllib.loads((bundle / "task.toml").read_text())
    assert config["artifacts"] == ["/app/rollout_qualification"]
    assert config["verifier"]["environment_mode"] == "separate"
    assert not {"scripts", "checks", "common", "experiment", "README.md"} & {item.name for item in bundle.iterdir()}
    modules = set()
    for step, component in zip(config["steps"], packager.MODULES, strict=True):
        modules.update(component)
        folder = bundle / "steps" / step["name"]
        assert {file.name for file in (folder / "solution/rollout_qualification").iterdir()} == modules
        assert (folder / "tests/probes.py").is_file()
