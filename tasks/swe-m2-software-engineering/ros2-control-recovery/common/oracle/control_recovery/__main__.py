"""Command line for controller inspection, planning, and durable recovery."""

import argparse
from contextlib import contextmanager
import fcntl
from importlib.util import find_spec
import json
import os
from pathlib import Path
import sys
import tempfile
from uuid import uuid4

from .core import Installation, counter, inspect, name_of, object_of, plan


def canonical(value):
    """Serialize wire records in key order for stable retry identity."""
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":"))


def publish(output: Path, report):
    """Replace the output atomically after writing complete JSON."""
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".controller-") as temp:
        staged = Path(temp) / "document"
        with staged.open("w", encoding="utf-8") as stream:
            stream.write(canonical(report) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        staged.replace(output)


@contextmanager
def lock_store(state: Path):
    """Lock a stable parent inode so atomic state replacement cannot split waiters."""
    state.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(state.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield descriptor
    finally:
        os.close(descriptor)


def acknowledgement(packet, entry, installation):
    """Validate the issued primitive against authoritative readback."""
    previous = packet["previous"]
    command = entry["report"]["command"]
    if command is None:
        return previous is None, None
    if previous is None or previous["id"] != entry["report"]["command_id"]:
        return False, None
    outcome, kind = previous["outcome"], command["kind"]
    if kind != "mode":
        active = command["controller"] in installation.active
        return outcome == "applied" and active == (kind == "start"), None
    device = installation.devices[command["device"]]
    if outcome == "obsolete":
        return device.generation > command["generation"], None
    if device.generation != command["generation"]:
        return False, None
    if outcome == "applied":
        return device.ready and device.mode == command["mode"], None
    return device.mode != command["mode"], (command["device"], command["generation"], command["mode"])


def next_record(packet, entry, installation):
    """Fence old sequence numbers and forbid switches that failed at a live generation."""
    if entry is None:
        return (frozenset() if packet["sequence"] == 1 and packet["previous"] is None else None)
    last = entry["packet"]
    if packet["sequence"] != last["sequence"] + 1:
        return None
    if any(canonical(packet[field]) != canonical(last[field]) for field in ("hardware", "controllers")):
        return None
    for name, reading in installation.devices.items():
        if reading.generation < last["snapshot"]["devices"][name]["generation"]:
            return None
    accepted, failure = acknowledgement(packet, entry, installation)
    if not accepted:
        return None
    previous = {tuple(item) for item in entry["forbidden"]
                if installation.devices[item[0]].generation == item[1]}
    if failure is not None:
        previous.add(failure)
    return previous


def recover(packet, installation, state):
    """Persist one authoritative decision and replay its stable command ID on retry."""
    run_id, sequence = name_of(packet["run_id"]), counter(packet["sequence"], 1)
    previous = packet["previous"]
    if previous is not None:
        previous = object_of(previous)
        name_of(previous["id"])
        if previous["outcome"] not in ("applied", "failed", "obsolete"):
            raise ValueError("invalid acknowledgement type")
    with lock_store(state) as directory:
        try:
            journal = object_of(json.loads(state.read_text(encoding="utf-8")))
        except FileNotFoundError:
            journal = {}
        entry = journal.get(run_id)
        if entry is not None and canonical(entry["packet"]) == canonical(packet):
            return entry["report"]
        identity = {"run_id": run_id, "sequence": sequence}
        forbidden = next_record(packet, entry, installation)
        if forbidden is None:
            return dict(identity, status="rejected", selected={}, command=None, command_id=None)
        proposed = plan(installation, forbidden)
        command = proposed["command"]
        response = dict(identity, **proposed, status="issued" if command else "settled",
                        command_id=uuid4().hex if command else None)
        journal[run_id] = {"packet": packet, "report": response, "forbidden": sorted(forbidden)}
        publish(state, journal)
        os.fsync(directory)
        return response


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    operations = parser.add_subparsers(dest="command", required=True)
    names = ("inspect", "plan", "recover", "schedule")
    if find_spec(".servo", __package__) is not None:
        names += ("servo",)
    for name in names:
        command = operations.add_parser(name)
        command.add_argument("--spec", type=Path, required=True)
        if name != "servo":
            command.add_argument("--output", type=Path, required=True)
        if name == "recover":
            command.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    try:
        packet = object_of(json.loads(args.spec.read_text(encoding="utf-8")))
        if args.command == "servo":
            from .servo import servo

            servo(packet, sys.stdin, sys.stdout)
            return 0
        installation = Installation.parse(packet)
        if args.command == "inspect":
            report = inspect(installation)
        elif args.command == "plan":
            report = plan(installation)
        elif args.command == "schedule":
            from .handover import schedule

            report = schedule(packet, installation)
        else:
            state = args.state.resolve()
            if state == args.output.resolve():
                raise ValueError("state and output paths must be distinct")
            report = recover(packet, installation, state)
        publish(args.output, report)
    except (KeyError, TypeError, ValueError, OverflowError, OSError) as exc:
        print(f"control_recovery: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
