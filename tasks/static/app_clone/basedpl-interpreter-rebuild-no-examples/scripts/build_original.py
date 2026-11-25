"""Build the hardened original `bpl` once, here, for both images and the reference solution.

usage: build_original.py [--checkout DIR] [--jobs N]

The pinned commit of AnswerDotAI/basedpl (UPSTREAM_COMMIT, tag v0.1.95) is exported from the
checkout (BASEDPL_CHECKOUT, default ../../../../../.cache-src/basedpl next to this repository) into
experiment/build/src, hardened by common/hardening/apply.sh (the patch, the all-zero build marker,
the pinned Cargo.lock) and built with Rust 1.100.0 for x86_64-unknown-linux-musl through
`cargo zigbuild` (Homebrew zig and cargo-zigbuild): a static PIE with no dynamic loader, the same
CPU level as upstream's x86-64 releases (`-C target-cpu=x86-64-v3`, from upstream's
.cargo/config.toml) and every local path remapped out of the binary.

It writes experiment/build/bpl and experiment/build/build.txt (commit, toolchain, target, link
mode, size, sha256). packaging compresses that binary into both images' build contexts, where
common/hardening/mark.py writes the private build marker over the zeros and checks the result
against build.txt, and into the reference solution as it is, with the zero marker. One binary,
then, everywhere: the images record and serve the build the solution delivers.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import struct
import subprocess
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_COMMIT = "af3609a9348471494d2bed952cbbf2a5ecdbd53e"  # AnswerDotAI/basedpl v0.1.95, Apache-2.0
TOOLCHAIN = "1.100.0"
TARGET = "x86_64-unknown-linux-musl"
ZERO_MARKER = b"BPL-BUILD-MARKER-" + b"0" * 32
BUILD = TASK_ROOT / "experiment" / "build"


def describe(binary: Path) -> dict[str, str]:
    """What build.txt records about a built binary: its link mode, size and sha256."""
    data = binary.read_bytes()
    if not data.startswith(b"\x7fELF"):
        raise ValueError(f"{binary} is not an ELF executable")
    if data.count(ZERO_MARKER) != 1:
        raise ValueError(
            f"{binary} holds the zero build marker {data.count(ZERO_MARKER)} times, not once"
        )
    for local in (str(Path.home()), "/private/tmp", "/Users/"):
        if local.encode() in data:
            raise ValueError(f"{binary} embeds a local path ({local})")
    return {
        "link": link_mode(data),
        "size": str(len(data)),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def link_mode(data: bytes) -> str:
    """How an x86-64 ELF executable is linked, from its header and program headers: "static-pie"
    (position independent, no loader), "static" (fixed addresses, no loader) or "dynamic" (it
    names a loader, PT_INTERP)."""
    (kind,) = struct.unpack_from("<H", data, 16)
    (phoff,) = struct.unpack_from("<Q", data, 32)
    size, count = struct.unpack_from("<HH", data, 54)
    types = {
        struct.unpack_from("<I", data, phoff + index * size)[0]
        for index in range(count)
    }
    if 3 in types:  # PT_INTERP
        return "dynamic"
    return "static-pie" if kind == 3 else "static" if kind == 2 else "unknown"


def main() -> None:
    """Build the reference interpreter from the checkout selected by the CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--checkout",
        type=Path,
        default=Path(
            os.environ.get(
                "BASEDPL_CHECKOUT", TASK_ROOT.parents[4] / ".cache-src" / "basedpl"
            )
        ),
    )
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    source, target_dir = BUILD / "src", BUILD / "target"
    shutil.rmtree(source, ignore_errors=True)
    source.mkdir(parents=True)
    archive = subprocess.run(
        ["git", "-C", str(args.checkout), "archive", UPSTREAM_COMMIT],
        capture_output=True,
        check=True,
    ).stdout
    subprocess.run(["tar", "-x", "-C", str(source)], input=archive, check=True)
    subprocess.run(
        ["sh", str(TASK_ROOT / "common" / "hardening" / "apply.sh"), str(source)],
        check=True,
    )
    home = Path.home()
    flags = [
        "-Zshare-generics=yes",
        "-C",
        "target-cpu=x86-64-v3",
        f"--remap-path-prefix={source}=/src",
        f"--remap-path-prefix={home / '.cargo'}=/cargo",
        f"--remap-path-prefix={home / '.rustup'}=/rustup",
        f"--remap-path-prefix={target_dir}=/target",
    ]
    env = dict(
        os.environ,
        RUSTFLAGS=" ".join(flags),
        RUSTC_BOOTSTRAP="1",
        CARGO_INCREMENTAL="0",
        CARGO_TARGET_DIR=str(target_dir),
    )
    subprocess.run(
        [
            "cargo",
            f"+{TOOLCHAIN}",
            "zigbuild",
            "--release",
            "--locked",
            "--target",
            TARGET,
            "-j",
            str(args.jobs),
            "-p",
            "basedpl-cli",
            "--bin",
            "bpl",
            "--no-default-features",
            "--config",
            "profile.release.strip=true",
        ],
        cwd=source,
        env=env,
        check=True,
    )
    binary = BUILD / "bpl"
    shutil.copyfile(target_dir / TARGET / "release" / "bpl", binary)
    binary.chmod(0o755)
    facts = {
        "commit": UPSTREAM_COMMIT,
        "toolchain": TOOLCHAIN,
        "target": TARGET,
        **describe(binary),
    }
    (BUILD / "build.txt").write_text(
        "".join(f"{key} {value}\n" for key, value in facts.items())
    )
    print((BUILD / "build.txt").read_text(), end="")


if __name__ == "__main__":
    main()
