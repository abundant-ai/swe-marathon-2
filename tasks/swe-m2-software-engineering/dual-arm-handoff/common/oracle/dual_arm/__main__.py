"""Run the spatial checker, paired-pose planner, or dispatcher."""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

from .core import certify


def publish(path, value):
    """Atomically replace one JSON response or journal."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".dual-arm-", dir=path.parent) as holding:
        item = Path(holding) / "response"
        with item.open("w", encoding="utf-8") as log:
            log.write(json.dumps(value, allow_nan=False) + "\n")
            log.flush()
            os.fsync(log.fileno())
        item.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    verbs = parser.add_subparsers(dest="command", required=True)
    names = ["certify", "plan", "dispatch", "contingency"]
    for name, module in (("commission-native", "commission_native.py"), ("plan-native", "plan_native.py"),
                         ("dispatch-native", "dispatch_native.py")):
        if Path(__file__).with_name(module).is_file():
            names.append(name)
    for name in names:
        run = verbs.add_parser(name)
        run.add_argument("--spec", type=Path, required=True)
        run.add_argument("--output", type=Path, required=True)
        if name in ("dispatch", "dispatch-native"):
            run.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    try:
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
        if args.command == "certify":
            report = certify(spec)
        elif args.command == "plan":
            from .planning import Window, plan

            report = plan(Window.parse(spec))
        elif args.command == "contingency":
            from .contingency import synthesize

            report = synthesize(spec)
        elif args.command == "commission-native":
            from .commission_native import commission_native

            report = commission_native(spec)
        elif args.command == "plan-native":
            from .plan_native import plan_native

            report = plan_native(spec)
        else:
            from .dispatch import dispatch

            state = args.state.resolve()
            if state == args.output.resolve():
                raise ValueError("State and output paths must differ")
            if args.command == "dispatch-native":
                from .dispatch_native import dispatch_native

                report = dispatch_native(spec, state, publish)
            else:
                report = dispatch(spec, state, publish)
        publish(args.output, report)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError, RuntimeError) as error:
        print(f"dual_arm: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
