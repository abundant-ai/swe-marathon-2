"""Set up the local tools the case generator and packaging need, all under experiment/.

usage: setup_tools.py [--archives DIR]

- experiment/original/: the original's release builds from carve-rs 0.1.14's GitHub release,
  each archive and binary checked against the sha256 in carve_text.py: `carve-linux` (the static
  x86-64 musl build that the verifier records with and the reference solution delivers, kept as
  `carve-linux.tar.gz`, the archive as released) and, on a Mac, `carve-macos` (the arm64 build,
  for choosing and checking cases here). Archives are read from --archives when given (files
  named as released), else downloaded.
- experiment/specmodel/: Carve's executable spec model at the pinned spec commit (its
  scripts/spec, scripts/lib and the resources they read, from the checkout in
  ../.cache-src/carve), with ohm-js 17.5.0 (the version the spec repository locks) and djot.js
  0.3.2 (@djot/djot, likewise) installed beside it for spec_model.mjs.

Nothing here is shipped: packaging reads experiment/original/carve-linux.tar.gz only.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import platform
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path

import carve_text as ct

TASK_ROOT = Path(__file__).resolve().parent.parent
ORIGINAL = TASK_ROOT / "experiment" / "original"
MODEL = TASK_ROOT / "experiment" / "specmodel"
RELEASE_URL = (
    f"https://github.com/markup-carve/carve-rs/releases/download/{ct.CARVE_RS_TAG}/"
)
NODE_PACKAGES = ("ohm-js@17.5.0", "@djot/djot@0.3.2")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def archive_bytes(name: str, wanted: str, local: Path | None) -> bytes:
    """A release archive's bytes, from `local` or downloaded, checked against `wanted`."""
    data = (
        (local / name).read_bytes()
        if local
        else urllib.request.urlopen(RELEASE_URL + name, timeout=120).read()
    )
    if sha256(data) != wanted:
        raise SystemExit(f"{name}: sha256 {sha256(data)} is not the pinned {wanted}")
    return data


def binary_from(data: bytes, wanted: str) -> tuple[bytes, bytes]:
    """The `carve` binary and LICENSE in a release archive, the binary checked against `wanted`.
    Read in memory: nothing of the archive is written but these two files."""
    found = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for member in archive.getmembers():
            name = member.name.rsplit("/", 1)[-1]
            if member.isfile() and name in ("carve", "LICENSE"):
                found[name] = archive.extractfile(member).read()
    if "carve" not in found or sha256(found["carve"]) != wanted:
        raise SystemExit("the archive's carve binary is not the pinned build")
    return found["carve"], found.get("LICENSE", b"")


def originals(local: Path | None) -> None:
    ORIGINAL.mkdir(parents=True, exist_ok=True)
    data = archive_bytes(ct.LINUX_ARCHIVE, ct.LINUX_ARCHIVE_SHA256, local)
    binary, licence = binary_from(data, ct.LINUX_BINARY_SHA256)
    (ORIGINAL / "carve-linux.tar.gz").write_bytes(data)
    (ORIGINAL / "carve-linux").write_bytes(binary)
    (ORIGINAL / "carve-linux").chmod(0o755)
    (ORIGINAL / "LICENSE").write_bytes(licence)
    if platform.system() == "Darwin":
        binary, _ = binary_from(
            archive_bytes(ct.MAC_ARCHIVE, ct.MAC_ARCHIVE_SHA256, local),
            ct.MAC_BINARY_SHA256,
        )
        (ORIGINAL / "carve-macos").write_bytes(binary)
        (ORIGINAL / "carve-macos").chmod(0o755)
    print(
        json.dumps(
            {
                "linux_binary_sha256": ct.LINUX_BINARY_SHA256,
                "archive_sha256": ct.LINUX_ARCHIVE_SHA256,
            }
        )
    )


def spec_model() -> None:
    staging = Path(tempfile.mkdtemp(prefix="carve-specmodel-"))
    try:
        archive = ct.git(
            ct.SPEC_CHECKOUT,
            "archive",
            ct.SPEC_COMMIT,
            "scripts/spec",
            "scripts/lib",
            "resources/carve-core.ohm",
            "resources/spec",
        )
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(staging, filter="data")
        MODEL.mkdir(parents=True, exist_ok=True)
        for part in ("scripts", "resources"):
            shutil.rmtree(MODEL / part, ignore_errors=True)
            shutil.copytree(staging / part, MODEL / part)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    (MODEL / "package.json").write_text(
        json.dumps(
            {"name": "carve-specmodel-local", "private": True, "type": "module"},
            indent=2,
        )
        + "\n"
    )
    subprocess.run(
        [
            "npm",
            "install",
            "--no-audit",
            "--no-fund",
            "--ignore-scripts",
            "--save-exact",
            *NODE_PACKAGES,
        ],
        cwd=MODEL,
        check=True,
        timeout=600,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archives", type=Path)
    parser.add_argument("--skip-model", action="store_true")
    args = parser.parse_args()
    originals(args.archives)
    if not args.skip_model:
        spec_model()


if __name__ == "__main__":
    main()
