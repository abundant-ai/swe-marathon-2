"""Command-line entry point for the mapping workflow."""

from argparse import ArgumentParser
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
import sys

from .maps import build, json_bytes


def add_command(commands, name: str, operation, *, paths: tuple[str, ...], strings: tuple[str, ...] = ()) -> None:
    """Bind CLI options to the operation's named arguments."""
    parser = commands.add_parser(name)
    parser.set_defaults(operation=operation)
    for path in paths:
        parser.add_argument(f"--{path}", required=True, type=Path)
    for value in strings:
        parser.add_argument(f"--{value}", required=True)


def parser_for_workspace() -> ArgumentParser:
    """Register the commands installed by the current milestone."""
    parser = ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(required=True)
    add_command(commands, "build", build, paths=("grid", "visit", "output"))
    if find_spec(".registration", __package__):
        registration = import_module(".registration", __package__)
        add_command(commands, "register", registration.register, paths=("map", "visit", "prior", "output"))
    if find_spec(".evidence", __package__):
        evidence = import_module(".evidence", __package__)
        add_command(commands, "propose", evidence.propose, paths=("base", "evidence", "output"))
    if find_spec(".releases", __package__):
        releases = import_module(".releases", __package__)
        add_command(commands, "init", releases.init, paths=("store", "map"))
        add_command(commands, "publish", releases.publish, paths=("store", "patch"), strings=("base",))
        add_command(commands, "activate", releases.activate, paths=("store",), strings=("version", "expect-active"))
        add_command(commands, "snapshot", releases.snapshot, paths=("store", "output"), strings=("version",))
    if find_spec(".canary", __package__):
        canary = import_module(".canary", __package__)
        add_command(commands, "route", canary.route, paths=("store", "request", "output"), strings=("version",))
        add_command(commands, "review", canary.review, paths=("store", "request", "output"))
    return parser


def main() -> int:
    """Run one requested command and print a receipt when it returns one."""
    arguments = vars(parser_for_workspace().parse_args())
    operation = arguments.pop("operation")
    for key in ("grid", "map", "visit", "prior"):
        if key in arguments:
            arguments[key + "_path"] = arguments.pop(key)
    try:
        receipt = operation(**arguments)
    except (OSError, ValueError, OverflowError) as error:
        print(f"versioned_mapping: {error}", file=sys.stderr)
        return 1
    if receipt is not None:
        sys.stdout.buffer.write(json_bytes(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
