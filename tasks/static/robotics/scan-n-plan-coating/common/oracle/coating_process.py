"""Expose the cumulative candidate reference CLI for motion checkpoints."""

import argparse
from pathlib import Path
import sys

from coating_io import publish, read_json
from coating_planner import plan
from coating_registration import register


def main(level: int) -> int:
    """Parse only the subcommands available at the installed checkpoint."""
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    names = {"register": "--scans", "plan-pass": "--registration"}
    if level >= 3:
        names["plan-coordinated"] = "--registration"
    if level >= 4:
        names["supervise"] = "--registration"
    for name, input_flag in names.items():
        command = commands.add_parser(name)
        command.add_argument("--job", type=Path, required=True)
        command.add_argument(input_flag, type=Path, required=True)
        command.add_argument("--state" if name == "supervise" else "--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        job = read_json(args.job)
        if args.command == "register":
            publish(args.output, register(job, read_json(args.scans)))
        else:
            registration = read_json(args.registration)
            if args.command == "supervise":
                from coating_supervisor import run
                run(job, registration, args.state)
            else:
                coordinated = args.command == "plan-coordinated"
                publish(args.output, plan(job, registration, coordinated=coordinated))
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2
    return 0
