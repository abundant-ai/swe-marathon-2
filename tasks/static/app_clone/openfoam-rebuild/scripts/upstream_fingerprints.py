"""Writes tests/verifier/upstream.sha256: the fingerprint (verifier/source.py) of every C/C++
file of OpenFOAM at the pinned commit, read with git archive so that no file is lost to a
case-insensitive file system. etc/ is left out: its files are readable in the agent's image.

usage: upstream_fingerprints.py <bare clone of openfoam.git>
"""

import io
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath

COMMIT = "481094fdf34f11ed6d0d603ee59a858a0124236d"
TESTS = Path(__file__).resolve().parents[1] / "tests"


def main():
    sys.path.insert(0, str(TESTS))
    from verifier.source import _CPP, fingerprint

    tar = subprocess.run(
        [
            "git",
            "-C",
            sys.argv[1],
            "archive",
            "--format=tar",
            COMMIT,
            "--",
            ".",
            ":!etc",
        ],
        capture_output=True,
        check=True,
    ).stdout
    found = set()
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        for m in t:
            if m.isfile() and PurePosixPath(m.name).suffix.lower() in _CPP:
                f = fingerprint(t.extractfile(m).read())
                if f:
                    found.add(f)
    (TESTS / "verifier/upstream.sha256").write_text(
        "".join(f + "\n" for f in sorted(found))
    )
    print(f"{len(found)} fingerprints")


if __name__ == "__main__":
    main()
