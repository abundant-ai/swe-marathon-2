"""Applies a patch to the files it changes or adds inside a source tar, in place, without
unpacking the whole tree (a case-insensitive file system would lose some of OpenFOAM's files).

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
        names = {m.name for m in members}
        for p in paths:
            (Path(tmp) / p).parent.mkdir(parents=True, exist_ok=True)
            if f"openfoam/{p}" in names:
                (Path(tmp) / p).write_bytes(src.extractfile(f"openfoam/{p}").read())
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
            like = next(m for m in members if m.isfile())
            for p in paths:
                if f"openfoam/{p}" not in names:  # a file the patch adds
                    data = (Path(tmp) / p).read_bytes()
                    m = tarfile.TarInfo(f"openfoam/{p}")
                    m.size, m.mode, m.mtime = len(data), 0o644, like.mtime
                    m.uname, m.gname = like.uname, like.gname
                    dst.addfile(m, io.BytesIO(data))
    archive.write_bytes(out.getvalue())
    print(f"patched {len(paths)} files in {archive.name}")


if __name__ == "__main__":
    main()
