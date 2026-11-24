"""Portable policy observation, execution and audit command line."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Iterator

from .calibration import bind, calibrate
from .model import Record, frame, mapping, number, parse
from .session import decide, first, start, updates


def publish(path: Path, content: Record) -> None:
    """Replace one output atomically, writing durable bytes before rename."""
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(content, stream, allow_nan=False, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def read(path: Path) -> object:
    """Load one JSON document without interpreting arbitrary code."""
    return json.loads(path.read_text(encoding="utf-8"))


def readings(path: Path) -> Iterator[object]:
    """Yield each complete packet in a supplied NDJSON stream."""
    with path.open(encoding="utf-8") as text:
        for line in text:
            yield json.loads(line)


def main() -> int:
    """Dispatch the observation, stream or qualification command."""
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    observe = modes.add_parser("observe")
    stream = modes.add_parser("stream")
    compare = modes.add_parser("compare")
    commission = modes.add_parser("calibrate")
    for command in (observe, stream):
        command.add_argument("--spec", type=Path, required=True)
    observe.add_argument("--input", type=Path, required=True)
    observe.add_argument("--output", type=Path, required=True)
    stream.add_argument("--state", type=Path, required=True)
    stream.add_argument("--calibration", type=Path)
    has_drive = Path(__file__).with_name("drive.py").is_file()
    if has_drive:
        drive = modes.add_parser("calibrate-drive")
        drive.add_argument("--spec", type=Path, required=True)
        drive.add_argument("--output", type=Path, required=True)
        stream.add_argument("--drive", type=Path)
        stream.add_argument("--safety", type=Path)
    commission.add_argument("--spec", type=Path, required=True)
    commission.add_argument("--output", type=Path, required=True)
    for option in ("left-spec", "right-spec", "left", "right", "output"):
        compare.add_argument("--" + option, type=Path, required=True)
    compare.add_argument("--tolerance", type=float, required=True)
    if Path(__file__).with_name("locomotion.py").is_file():
        locomotion = modes.add_parser("locomote")
        locomotion.add_argument("--spec", type=Path, required=True)
        locomotion.add_argument("--state", type=Path, required=True)
    if Path(__file__).with_name("course_nav.py").is_file():
        navigation = modes.add_parser("navigate")
        navigation.add_argument("--spec", type=Path, required=True)
        navigation.add_argument("--state", type=Path, required=True)
    if Path(__file__).with_name("scan_nav.py").is_file():
        navigation = modes.add_parser("navigate-scans")
        navigation.add_argument("--spec", type=Path, required=True)
        navigation.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.mode == "observe":
            contract = parse(read(args.spec), runnable=False)
            sample = mapping(read(args.input))
            publish(args.output, {"observation": frame(contract, sample, sample["last_action"])})
        elif args.mode == "calibrate":
            publish(args.output, calibrate(read(args.spec)))
        elif args.mode == "calibrate-drive":
            from .drive import identify

            publish(args.output, identify(read(args.spec)))
        elif args.mode == "navigate":
            from .course_nav import navigate

            navigate(args.spec, args.state)
        elif args.mode == "navigate-scans":
            from .scan_nav import navigate_scans

            navigate_scans(args.spec, args.state)
        elif args.mode == "locomote":
            from .locomotion import locomote

            locomote(args.spec, args.state)
        elif args.mode == "stream":
            raw = read(args.spec)
            ready = bind(raw, read(args.calibration)) if args.calibration else raw
            contract = parse(ready, runnable=True)
            adapter = None
            if has_drive and (args.drive or args.safety):
                from .drive import Adapter

                if args.drive is None or args.safety is None:
                    raise ValueError("drive and safety reports are required together")
                commissioned, limits = read(args.drive), read(args.safety)
                canonical = json.dumps([ready, commissioned, limits], sort_keys=True, allow_nan=False)
                fingerprint = sha256(canonical.encode()).hexdigest()
                adapter = Adapter.from_reports(contract, ready, commissioned, limits, fingerprint)
            args.state.mkdir(exist_ok=True, parents=True)
            path = args.state / "session.json"
            state = mapping(read(path)) if path.is_file() else start(contract)
            if path.is_file() and (adapter is not None or "drive" in state):
                if adapter is None or state.get("drive", {}).get("fingerprint") != adapter.fingerprint:
                    raise ValueError("session requires its original commissioned configuration")
            for line in sys.stdin:
                packet = json.loads(line)
                if adapter is None:
                    response, state, changed = decide(contract, state, packet)
                else:
                    response, state, changed = adapter.step(contract, state, packet)
                if changed:
                    publish(path, state)
                    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
                    try:
                        os.fsync(directory)
                    finally:
                        os.close(directory)
                print(json.dumps(response, allow_nan=False), flush=True)
        else:
            eps = number(args.tolerance)
            if eps < 0:
                raise ValueError("negative tolerance")
            left = list(updates(parse(read(args.left_spec), runnable=True), readings(args.left)))
            right = list(updates(parse(read(args.right_spec), runnable=True), readings(args.right)))
            publish(args.output, first(left, right, eps))
    except (ValueError, TypeError, KeyError, OverflowError, OSError) as error:
        print(f"policy_bridge: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
