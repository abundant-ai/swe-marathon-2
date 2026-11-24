"""Command line for the contact wrench qualification laboratory."""

import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from .core import calibrate, object_of, qualify, transform


def main():
    """Validate and atomically publish the selected contact report."""
    commands = {"transform":transform, "calibrate":calibrate, "qualify":qualify}
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in commands:
        cli = sub.add_parser(name)
        cli.add_argument("--spec",type=Path,required=True)
        cli.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    try:
        spec = object_of(json.loads(args.spec.read_text(encoding="utf-8")))
        report = json.dumps(commands[args.command](spec),indent=2,allow_nan=False)+"\n"
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with TemporaryDirectory(dir=args.output.parent) as work:
            temporary = Path(work)/"report"
            temporary.write_text(report,encoding="utf-8")
            temporary.replace(args.output)
    except (KeyError, TypeError, ValueError, OSError, OverflowError) as error:
        print(f"wrenchlab: {error}",file=sys.stderr)
        return 1
    return 0


if __name__=="__main__":
    sys.exit(main())
