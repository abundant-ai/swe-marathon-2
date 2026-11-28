"""Install the original renderer from its release archive, as released.

usage: install.py <archive> <build.txt> <destination>

Refuses an archive whose sha256 is not build.txt's `archive_sha256`, or one whose `carve` binary's
sha256 is not build.txt's `sha256`. Writes only that binary, mode 0755, to <destination>.
"""

import hashlib
import io
import sys
import tarfile
from pathlib import Path


def main() -> None:
    args = sys.argv[1:]
    if len(args) != 3:
        raise SystemExit(__doc__)
    archive, build, destination = (Path(arg) for arg in args)
    facts = dict(
        line.split(" ", 1)
        for line in build.read_text(encoding="utf-8").splitlines()
        if " " in line
    )
    data = archive.read_bytes()
    if hashlib.sha256(data).hexdigest() != facts["archive_sha256"]:
        raise SystemExit(f"{archive}: not the release archive build.txt names")
    binary = None
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for member in tar.getmembers():
            if member.isfile() and member.name.rsplit("/", 1)[-1] == "carve":
                binary = tar.extractfile(member).read()
    if binary is None or hashlib.sha256(binary).hexdigest() != facts["sha256"]:
        raise SystemExit(
            f"{archive}: its carve binary is not the build build.txt names"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(binary)
    destination.chmod(0o755)
    print(
        f"installed {facts.get('version', 'carve')} at {destination} (sha256 {facts['sha256']})"
    )


if __name__ == "__main__":
    main()
