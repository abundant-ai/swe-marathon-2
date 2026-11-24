"""Run paired rollout qualification commands."""

from argparse import ArgumentParser
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
import sys

from .dataset import inspect


def main() -> int:
    """Expose the available incremental milestone entry points."""
    actions = {"inspect": inspect}
    for command, module in (("replay", "simulation"), ("qualify", "policy")):
        if find_spec("." + module, __package__):
            actions[command] = getattr(import_module("." + module, __package__), command)
    parser = ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="operation", required=True)
    for command in actions:
        subparser = modes.add_parser(command)
        subparser.add_argument("--output", type=Path, required=True)
        if command == "qualify":
            subparser.add_argument("--spec", type=Path, required=True)
        else:
            subparser.add_argument("--dataset", type=Path, required=True)
        if command == "replay":
            subparser.add_argument("--demo", required=True)
    params = vars(parser.parse_args())
    function = actions[params.pop("operation")]
    try:
        function(**params)
    except (OSError, TypeError, AttributeError, KeyError, IndexError, OverflowError, ValueError) as error:
        print(f"rollout_qualification: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
