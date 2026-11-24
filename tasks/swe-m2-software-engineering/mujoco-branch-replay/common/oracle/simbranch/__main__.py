"""Command line for recording, restoring, and branching MuJoCo rollouts."""

import argparse
import json
from pathlib import Path
import sys

from .core import Model, object_of, rollout, study, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("trace", "resume", "study", "rebase", "rechart"):
        operation = sub.add_parser(name)
        operation.add_argument("--spec", type=Path, required=True)
        operation.add_argument("--output", type=Path, required=True)
        if name == "study":
            operation.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    try:
        spec = object_of(json.loads(args.spec.read_text(encoding="utf-8")))
        if args.command == "rebase":
            from .rebase import rebase

            write(args.output, rebase(spec))
            return 0
        if args.command == "rechart":
            from .rechart import rechart

            write(args.output, rechart(spec))
            return 0
        model = Model.compile(spec["model"])
        if args.command == "study":
            state = args.state.resolve()
            if state == args.output.resolve():
                raise ValueError("state and output paths must be different")
            report = study(model, spec, state)
        elif args.command == "resume":
            report = rollout(model, spec, checkpoint=spec.get("checkpoint"), checkpoints=True)
        else:
            report = rollout(model, spec)
        write(args.output, report)
    except (KeyError, TypeError, ValueError, OverflowError, OSError) as exc:
        print(f"simbranch: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
