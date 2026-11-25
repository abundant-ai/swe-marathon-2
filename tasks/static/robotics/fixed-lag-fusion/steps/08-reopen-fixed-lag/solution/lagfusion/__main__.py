"""Run the planar fixed-lag fusion workbench."""

import argparse
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from .contract import Json, obj, read_config, read_events
from .gaussian import Smoother


def invalid_constant(value: str) -> None:
    """Reject non-JSON numeric literals before processing a request."""
    raise ValueError(f"invalid JSON constant {value}")


def smooth(spec: Json) -> Json:
    """Run the offline estimator with the commands installed at this milestone."""
    adapter = None
    if Path(__file__).with_name("sensors.py").is_file():
        from .sensors import adapter_from

        adapter = adapter_from(spec)
    return Smoother(read_config(spec["config"])).execute(
        read_events(spec["events"], adapter)
    )


def publish(destination: Path, data: Json) -> None:
    """Write a complete report atomically and preserve previous output on failure."""
    text = json.dumps(data, indent=2, allow_nan=False) + "\n"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(
        prefix=".lagfusion-output-", dir=destination.parent
    ) as scratch:
        report = Path(scratch) / "report.json"
        report.write_text(text, encoding="utf-8")
        report.replace(destination)


def main() -> int:
    """Parse CLI arguments and run the selected estimator operation."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    package = Path(__file__).parent
    for command, filename in (
        ("smooth", "gaussian.py"),
        ("calibrate", "calibration.py"),
        ("ingest", "session.py"),
        ("qualify-network", "network.py"),
        ("track-integrity", "integrity.py"),
        ("smooth-tracks", "vision.py"),
        ("reopen-tracks", "rewind.py"),
        ("recalibrate-tracks", "mount.py"),
    ):
        if (package / filename).is_file():
            subcommand = commands.add_parser(command)
            if command in ("smooth-tracks", "reopen-tracks", "recalibrate-tracks"):
                subcommand.add_argument("--manifest", type=Path, required=True)
            else:
                subcommand.add_argument("--spec", type=Path, required=True)
                subcommand.add_argument("--output", type=Path, required=True)
            if command in (
                "ingest",
                "track-integrity",
                "reopen-tracks",
                "recalibrate-tracks",
            ):
                subcommand.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()

    try:
        if args.command == "smooth-tracks":
            from .vision import stream

            config = obj(
                json.loads(
                    args.manifest.read_text(encoding="utf-8"),
                    parse_constant=invalid_constant,
                )
            )
            stream(config, sys.stdin, sys.stdout)
            return 0
        if args.command in ("reopen-tracks", "recalibrate-tracks"):
            if args.command == "recalibrate-tracks":
                from .mount import stream
            else:
                from .rewind import stream
            config = obj(
                json.loads(
                    args.manifest.read_text(encoding="utf-8"),
                    parse_constant=invalid_constant,
                )
            )
            stream(config, args.state, sys.stdin, sys.stdout)
            return 0
        spec = obj(
            json.loads(
                args.spec.read_text(encoding="utf-8"), parse_constant=invalid_constant
            )
        )
        if args.command == "smooth":
            report = smooth(spec)
        elif args.command == "calibrate":
            from .calibration import calibrate

            report = calibrate(spec)
        elif args.command == "qualify-network":
            from .network import qualify_network

            report = qualify_network(spec)
        else:
            state = args.state.resolve()
            if args.output.resolve() in (
                state,
                state.with_name(state.name + ".lock").resolve(),
            ):
                raise ValueError("output aliases the state or lock")
            if args.command == "track-integrity":
                from .integrity import track

                report = track(spec, state)
            else:
                from .session import ingest

                report = ingest(spec, state)
        publish(args.output, report)
    except (
        KeyError,
        OSError,
        OverflowError,
        TypeError,
        ValueError,
        RuntimeError,
        np.linalg.LinAlgError,
    ) as error:
        print(f"lagfusion: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
