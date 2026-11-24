"""Take a small attributed XY excerpt of the TUM VI room1 mocap CSV."""

import argparse
import csv
from pathlib import Path


def extract(source: Path, destination: Path) -> None:
    """Write every ninth mocap row from a fixed contiguous room1 interval."""
    with source.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        sample = [
            [row["Time"], row["transform.translation.x"], row["transform.translation.y"]]
            for index, row in enumerate(reader) if 2240 <= index < 2960 and (index - 2240) % 9 == 0
        ]
    if len(sample) != 80:
        raise ValueError("room1 source lacks the expected 80 samples")
    with destination.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("time_s", "x_m", "y_m"))
        writer.writerows(sample)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    extract(args.source, args.destination)
