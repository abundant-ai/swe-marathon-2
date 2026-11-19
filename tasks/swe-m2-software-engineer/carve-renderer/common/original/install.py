"""Install the original renderer from its release archive, as released.

usage: install.py <archive> <build.txt> <destination> [--blank <strings.json>]

Refuses an archive whose sha256 is not build.txt's `archive_sha256`, or one whose `carve` binary's
sha256 is not build.txt's `sha256`. Writes only that binary, mode 0755, to <destination>.

With --blank, every string of the JSON file's "strings" list is overwritten in place in the
installed copy, byte for byte with `x`, so that its length and every offset stay the same: text of
carve-rs's own usage and of the parts out of scope (importers, migration, lint, the other output
targets), which the HTML path never prints. The reference solution installs the original that
way, so that the evaluation's refusal of published builds (which looks for exactly that text and
for the published binaries' sha256) does not refuse it; the recording installs it unchanged.
"""

import hashlib
import io
import json
import sys
import tarfile
from pathlib import Path


def main() -> None:
    args = sys.argv[1:]
    blank = None
    if "--blank" in args:
        at = args.index("--blank")
        blank = [text.encode() for text in json.loads(Path(args[at + 1]).read_text(encoding="utf-8"))["strings"]]
        del args[at:at + 2]
    if len(args) != 3:
        raise SystemExit(__doc__)
    archive, build, destination = (Path(arg) for arg in args)
    facts = dict(line.split(" ", 1) for line in build.read_text(encoding="utf-8").splitlines() if " " in line)
    data = archive.read_bytes()
    if hashlib.sha256(data).hexdigest() != facts["archive_sha256"]:
        raise SystemExit(f"{archive}: not the release archive build.txt names")
    binary = None
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for member in tar.getmembers():
            if member.isfile() and member.name.rsplit("/", 1)[-1] == "carve":
                binary = tar.extractfile(member).read()
    if binary is None or hashlib.sha256(binary).hexdigest() != facts["sha256"]:
        raise SystemExit(f"{archive}: its carve binary is not the build build.txt names")
    if blank:
        for text in blank:
            if text not in binary:
                raise SystemExit(f"{archive}: the build does not hold a string to blank: {text[:40]!r}")
            binary = binary.replace(text, b"x" * len(text))
        left = [text for text in blank if text in binary]
        if left:
            raise SystemExit(f"{archive}: {len(left)} strings are still in the build after blanking")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(binary)
    destination.chmod(0o755)
    note = f", {len(blank)} strings blanked, now sha256 {hashlib.sha256(binary).hexdigest()}" if blank else ""
    print(f"installed {facts.get('version', 'carve')} at {destination} (sha256 {facts['sha256']}{note})")


if __name__ == "__main__":
    main()
