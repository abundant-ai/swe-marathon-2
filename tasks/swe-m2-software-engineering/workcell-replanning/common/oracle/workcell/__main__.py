"""Command-line adapter for the workcell replay package."""

import argparse
import json
from pathlib import Path
import sys
import tempfile

from .model import Object, number, obj, robot_from
from .scene import reconcile


def run(command: str, spec: Object) -> Object:
    """Dispatch a validated JSON object to the installed workcell operation."""
    robot = robot_from(spec["robot"])
    if command == "scene":
        return reconcile(robot, spec["initial_scene"], spec["events"]).encoded()
    if command == "certify":
        from .motion import certify, path_from
        from .scene import scene_from

        scene = scene_from(spec["scene"])
        margin = number(spec["margin_m"])
        if margin < 0:
            raise ValueError("negative clearance margin")
        result = certify(robot, scene, path_from(spec["trajectory"]), margin)
        return {"revision": scene.revision, "status": result.status,
                "segment_index": result.segment, "witness_fraction": result.fraction}
    if command == "plan-window":
        from .timed import plan_window

        return plan_window(robot, spec)
    from .recovery import recover

    return recover(robot, spec)


def publish(output: Path, report: Object) -> None:
    """Publish complete serialized results atomically."""
    text = json.dumps(report, allow_nan=False, indent=2) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".workcell-", dir=output.parent) as temporary:
        staged = Path(temporary) / "report.json"
        staged.write_text(text, encoding="utf-8")
        staged.replace(output)


def main() -> int:
    """Read user arguments and return a process exit status."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    package = Path(__file__).parent
    operations = {
        "scene": "scene.py",
        "certify": "motion.py",
        "recover": "recovery.py",
        "plan-window": "timed.py",
        "dispatch": "dispatch.py",
    }
    for name, module in operations.items():
        if (package / module).is_file():
            subcommand = commands.add_parser(name)
            subcommand.add_argument("--spec", type=Path, required=True)
            subcommand.add_argument("--output", type=Path, required=True)
            if name == "dispatch":
                subcommand.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    try:
        spec = obj(json.loads(args.spec.read_text(encoding="utf-8")))
        if args.command == "dispatch":
            from .dispatch import dispatch

            state = args.state.resolve()
            if args.output.resolve() == state:
                raise ValueError("output and state must be distinct paths")
            result = dispatch(spec, state)
        else:
            result = run(args.command, spec)
        publish(args.output, result)
    except (KeyError, OSError, OverflowError, UnicodeError, ValueError) as exc:
        print(f"workcell: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
