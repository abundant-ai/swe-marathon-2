"""Local regression for the packaged PX4 replay and redundant supervisor."""

import json
from pathlib import Path
import subprocess
import sys
import tomllib

TASK = Path(__file__).resolve().parents[1]


def test_px4_replay_and_supervisor_offline_packaging(tmp_path: Path) -> None:
    """Run the packaged final verifier against the reference and an empty artifact."""
    bundle=tmp_path/"bundle"
    subprocess.run([sys.executable,"-B",str(TASK/"scripts"/"package_task.py"),"--output",str(bundle)],check=True)
    assert not (bundle/"environment"/"flight.py").exists()
    assert not (bundle/"environment"/"authority.py").exists()
    manifest=tomllib.loads((bundle/"task.toml").read_text())
    assert manifest["multi_step_reward_strategy"]=="final"
    commissioning, flight, landing, moving, relative = manifest["steps"][-5:]
    assert commissioning["name"]=="05-commission-inertial-timing"
    assert flight["name"]=="06-fly-with-delayed-aiding"
    assert landing["name"]=="07-land-with-degraded-aiding"
    assert moving["name"]=="08-land-on-moving-cart"
    assert relative["name"]=="09-land-from-onboard-aiding"
    assert (bundle/"environment"/"example"/"moving-cart-spec.json").is_file()
    assert (bundle/"environment"/"example"/"moving-cart-observations.jsonl").is_file()
    assert not (bundle/"environment"/"moving_native.py").exists()
    for entry, expected in ((commissioning,"numpy==2.2.6"),(flight,"mujoco==3.3.7"),
                            (landing,"mujoco==3.3.7"),(moving,"mujoco==3.3.7"),(relative,"mujoco==3.3.7")):
        verifier=bundle/"steps"/entry["name"]/"tests"
        assert expected in (verifier/"requirements.txt").read_text().splitlines()
    assert not (bundle/"environment"/"flight_native.py").exists()
    assert (bundle/"steps"/landing["name"]/"tests"/"landing_native.py").is_file()
    assert (bundle/"steps"/landing["name"]/"solution"/"px4_recovery"/"landing.py").is_file()
    assert (bundle/"steps"/moving["name"]/"tests"/"moving_native.py").is_file()
    assert (bundle/"steps"/moving["name"]/"solution"/"px4_recovery"/"moving_landing.py").is_file()
    assert not (bundle/"steps"/landing["name"]/"tests"/"moving_native.py").exists()
    assert (bundle/"steps"/relative["name"]/"tests"/"relative_native.py").is_file()
    assert (bundle/"steps"/relative["name"]/"solution"/"px4_recovery"/"relative_landing.py").is_file()
    assert not (bundle/"steps"/moving["name"]/"tests"/"relative_native.py").exists()
    step=bundle/"steps"/"04-supervise-redundant-estimators"
    cases = (("reference",step/"solution"/"px4_recovery",1.0),("nop",tmp_path/"missing",0.0))
    for name, artifact, expected in cases:
        result=tmp_path/name
        subprocess.run([sys.executable,"-IB",str(step/"tests"/"verify.py"),"--stage","4",
                        "--artifact",str(artifact),"--output",str(result)],check=True)
        actual=json.loads((result/"checkpoint.json").read_text())
        assert actual["reward"]==actual["legacy"]==actual["redundancy"]==expected
        assert len(actual["checks"])==16
        assert len(actual["observations"])==len(actual["checks"])
