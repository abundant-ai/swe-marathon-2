"""Record the sha256 of every build of BasedPL 0.1.95 that upstream publishes, for the verifier's refusal.

usage: upstream_builds.py [--download-dir DIR]

Downloads the v0.1.95 GitHub release's `bpl` binaries and every 0.1.95 wheel on PyPI (into
experiment/upstream-builds, Git-ignored; nothing downloaded is committed or run) and writes
steps/01-rebuild-interpreter/tests/verifier/upstream_builds.json: the sha256 of each release binary
and of each executable inside each wheel (the standalone `bpl` and the Python extension), with where
it came from. The verifier refuses a submission holding any file with one of these hashes: a
published build of the original, fetched rather than written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parent.parent
OUT = TASK_ROOT / "steps" / "01-rebuild-interpreter" / "tests" / "verifier" / "upstream_builds.json"
RELEASE = "https://github.com/AnswerDotAI/basedpl/releases/download/v0.1.95/"
RELEASE_BINARIES = ("bpl-linux-x86_64", "bpl-linux-arm64", "bpl-macos-arm64")
PYPI = "https://pypi.org/pypi/basedpl/0.1.95/json"
MAGICS = (b"\x7fELF", b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe")  # ELF, Mach-O 64-bit, universal Mach-O


def fetch(url: str, target: Path) -> Path:
    """`url` saved at `target` (kept from an earlier run when present), streamed in 1 MB pieces."""
    if not target.is_file():
        request = urllib.request.Request(url, headers={"User-Agent": "task-build-hashes"})
        with urllib.request.urlopen(request, timeout=120) as response, open(target.with_suffix(".part"), "wb") as handle:
            while chunk := response.read(1 << 20):
                handle.write(chunk)
        target.with_suffix(".part").rename(target)
    return target


def sha256_of(stream) -> str:
    """The sha256 of everything `stream` yields, read in 1 MB pieces."""
    digest = hashlib.sha256()
    while chunk := stream.read(1 << 20):
        digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-dir", type=Path, default=TASK_ROOT / "experiment" / "upstream-builds")
    args = parser.parse_args()
    args.download_dir.mkdir(parents=True, exist_ok=True)
    builds = []
    for name in RELEASE_BINARIES:
        path = fetch(RELEASE + name, args.download_dir / name)
        with open(path, "rb") as handle:
            builds.append({"sha256": sha256_of(handle), "source": f"GitHub release v0.1.95: {name}", "size": path.stat().st_size})
    with urllib.request.urlopen(urllib.request.Request(PYPI, headers={"User-Agent": "task-build-hashes"}), timeout=60) as response:
        files = json.load(response)["urls"]
    for entry in files:
        if not entry["filename"].endswith(".whl"):
            continue
        path = fetch(entry["url"], args.download_dir / entry["filename"])
        with open(path, "rb") as handle:
            if sha256_of(handle) != entry["digests"]["sha256"]:
                raise SystemExit(f"{entry['filename']} does not match PyPI's sha256")
        with zipfile.ZipFile(path) as wheel:
            for member in wheel.infolist():
                with wheel.open(member) as stream:
                    head = stream.read(4)
                if head not in MAGICS:
                    continue
                with wheel.open(member) as stream:
                    builds.append({"sha256": sha256_of(stream), "source": f"PyPI {entry['filename']}: {member.filename}",
                                   "size": member.file_size})
    OUT.write_text(json.dumps({"builds": builds}, indent=1, sort_keys=True) + "\n")
    print(f"{len(builds)} published builds recorded in {OUT.relative_to(TASK_ROOT)}")


if __name__ == "__main__":
    main()
