"""Check that the packaged workcell oracle makes a safe loaded detour."""

from pathlib import Path
import subprocess
import sys


TASK_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_NAME = "swe-m2_software-engineering_workcell-replanning"
FINAL_SCENARIO = """
import json
from pathlib import Path
import subprocess
import sys

checkpoint, work = map(Path, sys.argv[1:])
sys.path.insert(0, str(checkpoint / "tests"))
from geometry import legal_trajectory
from probes import obstructed_workcell

spec, scene = obstructed_workcell()
request = work / "request.json"
output = work / "report.json"
request.write_text(json.dumps(spec), encoding="utf-8")
subprocess.run(
    [sys.executable, "-B", "-m", "workcell", "recover", "--spec", str(request), "--output", str(output)],
    cwd=checkpoint / "solution",
    check=True,
    timeout=20,
)
report = json.loads(output.read_text(encoding="utf-8"))
assert report["status"] == "replanned"
assert report["revision"] == scene["revision"]
assert legal_trajectory(
    spec["robot"], scene, report["trajectory"], spec["measured_q"], spec["goal_q"], spec["margin_m"],
)
"""


MOVING_SCENARIOS = """
from pathlib import Path
import sys

bundle, scratch = map(Path, sys.argv[1:])
checkpoint = bundle / "steps" / "05-dispatch-motion"
sys.path.insert(0, str(checkpoint / "tests"))

from checkpoint import CLI, stage
from dispatch_probes import complete_mission
from missions import missions
from timed_checks import valid_plan

app = scratch / "app"
assert stage(checkpoint / "solution" / "workcell", app)
run = CLI(app, scratch)
cases = {case["id"]: case for case in missions()}
for name in ("early-berth-entry-strands-arm", "braking-misses-last-safe-window"):
    case = cases[name]
    reply = run("plan-window", case["spec"])
    assert valid_plan(case["spec"], reply, expect_ready=case["expect_ready"]), name
for name in ("early-close-wait-for-reopen", "two-carriages-clear-after-reconnect"):
    case = cases[name]
    state = scratch / f"{name}.json"

    def exchange(packet, *, lose_output=False):
        return run("dispatch", packet, state=state, lose_output=lose_output)

    assert complete_mission(exchange, case), name
"""


def test_workcell_package_recovers_after_fixture_updates(tmp_path: Path) -> None:
    """Verify runtime isolation and execute the loaded detour from a fresh bundle."""
    subprocess.run(
        [sys.executable, "-B", str(TASK_ROOT / "scripts" / "package_task.py"), "--output", str(tmp_path)],
        check=True,
        capture_output=True,
        timeout=10,
    )
    bundle = tmp_path / BUNDLE_NAME
    assert {path.name for path in bundle.iterdir()} == {"task.toml", "environment", "steps"}
    assert not any(path.name == "probes.py" for path in (bundle / "environment").rglob("*"))

    first = bundle / "steps" / "01-reconcile-scene" / "solution" / "workcell"
    assert {path.name for path in first.glob("*.py")} == {"__init__.py", "__main__.py", "model.py", "scene.py"}
    final = bundle / "steps" / "03-recover-motion"
    for name in ("motion.py", "recovery.py"):
        authored = TASK_ROOT / "common" / "oracle" / "workcell" / name
        assert (final / "solution" / "workcell" / name).read_bytes() == authored.read_bytes()

    subprocess.run(
        [sys.executable, "-BI", "-c", FINAL_SCENARIO, str(final), str(tmp_path)],
        check=True,
        timeout=30,
    )


    last = bundle / "steps" / "05-dispatch-motion"
    assert (last / "tests" / "missions.py").is_file()
    assert not any(p.name == "missions.py" for p in last.joinpath("solution").rglob("*"))
    assert not any(p.name == "dispatch.py" for p in final.joinpath("solution").rglob("*"))
    subprocess.run(
        [sys.executable, "-BI", "-c", MOVING_SCENARIOS, str(bundle), str(tmp_path)],
        check=True,
        timeout=30,
    )
