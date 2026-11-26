"""Applies a patch to the files it changes inside a source tar, in place, without unpacking
the whole tree (a case-insensitive file system would lose some of OpenFOAM's files).

usage: harden_archive.py <source.tar> <patch>   (paths in the patch: a/<path>, b/<path>;
                                                in the tar: openfoam/<path>)
"""

import io
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


def main():
    archive, patch = Path(sys.argv[1]), Path(sys.argv[2])
    paths = re.findall(r"^\+\+\+ b/(\S+)", patch.read_text(), flags=re.MULTILINE)
    with tempfile.TemporaryDirectory() as tmp, tarfile.open(archive) as src:
        members = src.getmembers()
        for p in paths:
            data = src.extractfile(f"openfoam/{p}").read()
            (Path(tmp) / p).parent.mkdir(parents=True, exist_ok=True)
            (Path(tmp) / p).write_bytes(data)
        subprocess.run(
            ["patch", "-p1", "-s", "-d", tmp, "-i", str(patch.resolve())], check=True
        )
        out = io.BytesIO()
        with tarfile.open(fileobj=out, mode="w", format=src.format) as dst:
            for m in members:
                rel = m.name.removeprefix("openfoam/")
                if m.isfile() and rel in paths:
                    data = (Path(tmp) / rel).read_bytes()
                    m.size = len(data)
                    dst.addfile(m, io.BytesIO(data))
                else:
                    dst.addfile(m, src.extractfile(m) if m.isfile() else None)
    archive.write_bytes(out.getvalue())
    print(f"patched {len(paths)} files in {archive.name}")


if __name__ == "__main__":
    main()
