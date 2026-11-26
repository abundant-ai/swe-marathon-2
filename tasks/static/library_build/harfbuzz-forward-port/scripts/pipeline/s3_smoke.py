"""S3: the driver against upstream's own expectations for the Khmer coeng fix (#6735).

`prepare`: take the lines 15.2.0 added to `khmer-misc.tests` (new against 15.1.0) and their font out of the release
tarballs, and write driver input. `compare`: read the driver's outputs for two builds, count the lines whose output
differs, and check the 15.2.0 build against upstream's expectations. Host side, Python 3.11+ with -I; it only parses
tar members as data. Spike only: upstream's in-house font is never part of the task.
"""

from __future__ import annotations

import json
import re
import sys
import tarfile
from pathlib import Path

CACHE = Path.home() / "Documents/github/Abundant/lib-tasks-cache/harfbuzz-forward-port"
MEMBER = "test/shape/data/in-house/tests/khmer-misc.tests"


def lines_of(version: str) -> list[str]:
    with tarfile.open(CACHE / f"dl/harfbuzz/harfbuzz-{version}.tar.xz") as tar:
        data = tar.extractfile(f"harfbuzz-{version}/{MEMBER}").read().decode()
    return [line for line in data.splitlines() if line and not line.startswith("#")]


def prepare(out: Path) -> None:
    new = [line for line in lines_of("15.2.0") if line not in set(lines_of("15.1.0"))]
    out.mkdir(parents=True, exist_ok=True)
    rows, expected = [], {}
    with tarfile.open(CACHE / "dl/harfbuzz/harfbuzz-15.2.0.tar.xz") as tar:
        for n, line in enumerate(new):
            font, opts, text, want = line.split(";")
            name = Path(font).name
            member = f"harfbuzz-15.2.0/test/shape/data/in-house/fonts/{name}"
            target = out / name
            if not target.exists():
                target.write_bytes(tar.extractfile(member).read())
            level = re.search(r"--cluster-level=(\d)", opts)
            cps = ",".join(tok[2:] for tok in text.split(","))
            cid = f"s3-{n:02d}"
            rows.append(
                f"{cid}\t/work/s3/{name}\t0\tnames=1;cl={level.group(1) if level else 0}\t{cps}"
            )
            expected[cid] = want
    (out / "cases.tsv").write_text("\n".join(rows) + "\n")
    (out / "expected.json").write_text(json.dumps(expected, indent=1))
    print(
        json.dumps(
            {
                "new_lines": len(new),
                "fonts": sorted({Path(r.split("\t")[1]).name for r in rows}),
            }
        )
    )


def upstream_format(result: str) -> str:
    """Our driver's line in hb-shape's default text form (offsets and y advance only when non-zero)."""
    glyphs = []
    for item in result.split("|"):
        m = re.fullmatch(r"(.+)=(\d+)@(-?\d+),(-?\d+)\+(-?\d+),(-?\d+)", item)
        name, cluster, xo, yo, xa, ya = m.groups()
        text = (
            f"{name}={cluster}"
            + (f"@{xo},{yo}" if xo != "0" or yo != "0" else "")
            + f"+{xa}"
        )
        glyphs.append(text + (f",{ya}" if ya != "0" else ""))
    return "[" + "|".join(glyphs) + "]"


def compare(out: Path) -> None:
    expected = json.loads((out / "expected.json").read_text())

    def read(name: str) -> dict[str, str]:
        return dict(
            line.split("\t", 1) for line in (out / name).read_text().splitlines()
        )

    base, target = read("base.out"), read("target.out")
    differ = sorted(c for c in expected if base[c] != target[c])
    match = sorted(c for c in expected if upstream_format(target[c]) == expected[c])
    report = {
        "lines": len(expected),
        "base_differs_from_15.2.0": len(differ),
        "15.2.0_matches_upstream_expectation": len(match),
        "mismatches": {
            c: [upstream_format(target[c]), expected[c]]
            for c in expected
            if c not in match
        },
    }
    (out / "report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    {"prepare": prepare, "compare": compare}[sys.argv[1]](Path(sys.argv[2]))
