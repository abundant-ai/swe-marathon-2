"""Offline LeRobot dataset audit and repair."""

from argparse import ArgumentParser
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
import sys

import pyarrow as pa

from .dataset import audit


def main() -> int:
    """Run the requested installed operation and report invalid inputs."""
    parser = ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="operation", required=True)
    functions = {"audit": audit}
    for command, module in (("plan", "planning"), ("apply", "publication"),
                            ("time-plan", "clocked"), ("time-apply", "clocked"),
                            ("action-qualify", "actions"), ("reconstruct-actions", "journals")):
        if find_spec("." + module, __package__):
            functions[command] = getattr(import_module("." + module, __package__), command.replace("-", "_"))
    for command in functions:
        action = subcommands.add_parser(command)
        action.add_argument("--dataset", type=Path, required=True)
        action.add_argument("--output", type=Path, required=True)
        if command in ("plan", "apply", "time-plan", "time-apply", "action-qualify"):
            action.add_argument("--ledger", type=Path, required=True)
        if command == "reconstruct-actions":
            action.add_argument("--journal", type=Path, required=True)
        if command in ("apply", "time-apply"):
            action.add_argument("--plan", dest="proposal", type=Path, required=True)
    values = vars(parser.parse_args())
    function = functions[values.pop("operation")]
    try:
        function(**values)
    except (OSError, KeyError, OverflowError, TypeError, ValueError, pa.ArrowException) as error:
        print(f"lerobot_repair: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
