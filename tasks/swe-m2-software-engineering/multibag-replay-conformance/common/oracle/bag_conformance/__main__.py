"""CLI for native ROS 2 replay conformance."""

from argparse import ArgumentParser
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
import sqlite3
import sys

from rosbags.rosbag2 import ReaderError

from .native import index


def main() -> int:
    """Run an installed milestone and report invalid input cleanly."""
    functions = {"index": index}
    for command, module in (("replay", "playback"), ("qualify", "transforms"), ("incident", "incident"), ("serve", "service"), ("live", "live"), ("receipt", "live")):
        if find_spec("." + module, __package__):
            functions[command] = getattr(import_module("." + module, __package__), command)
    parser = ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="action", required=True)
    for name in functions:
        subcommand = subcommands.add_parser(name)
        if name in ("live", "receipt"):
            subcommand.add_argument("--state", required=True, type=Path)
            if name == "receipt":
                subcommand.add_argument("--request-id", required=True)
            continue
        if name == "serve":
            subcommand.add_argument("--request", required=True, type=Path)
            subcommand.add_argument("--state", required=True, type=Path)
        else:
            subcommand.add_argument("--spec", required=True, type=Path)
        subcommand.add_argument("--output", required=True, type=Path)
        if name in ("replay", "qualify"):
            subcommand.add_argument("--script", required=True, type=Path)
    arguments = vars(parser.parse_args())
    action = functions[arguments.pop("action")]
    try:
        action(**arguments)
    except (OSError, AttributeError, IndexError, KeyError, TypeError, ValueError, ReaderError, sqlite3.Error, RuntimeError, ImportError) as error:
        print(f"bag_conformance: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
