"""Broken and hostile game projects for the grader's acceptance checks (author-side).

Each case is the self-test project (tests/selftest/project) with an overlay from
checks/fixtures/hostile/<case>/: files copied over the project (a hostile.gd is picked up
by the project's main script and given its hooks), "project.append" appended to
project.godot. "foreign" is the spike's unrelated project, and "big_cache" gets a
generated noise texture. EXPECTED says what grading each case must produce.
"""

from __future__ import annotations

import os
import shutil
import struct
import zlib
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
BASE = TASK / "tests" / "selftest" / "project"
FOREIGN = TASK / "spike" / "measure" / "foreign_project"
FIXTURES = TASK / "checks" / "fixtures" / "hostile"

# case -> (what must happen, grader options for the case)
EXPECTED: dict[str, tuple[str, dict]] = {
    "control": ("reward 1.0 (positive control: our own project, no defect)", {}),
    "foreign": ("G_static fails (no Jolt, no actions): reward 0", {}),
    "import_crash": (
        "G_import fails (the editor crashes while importing): reward 0",
        {},
    ),
    "import_hang": (
        "G_import fails (import stopped at its time cap): reward 0",
        {"import_cap_s": 25},
    ),
    "big_cache": (
        "G_import fails (import cache over its cap): reward 0",
        {"cache_cap_mb": 4},
    ),
    "hang_boot": (
        "G_boot fails (never reaches a playable world): reward 0",
        {"boot_s": 15},
    ),
    "no_contract": ("G_boot fails (no state report): reward 0", {"boot_s": 15}),
    "stall": ("every instance stalls (blocked telemetry): reward 0", {"step_s": 8}),
    "crash": ("every instance's process crashes: reward 0", {}),
    "remove_telemetry": ("every instance loses its telemetry node: reward 0", {}),
    "pause_telemetry": (
        "every instance stalls or loses its heartbeat: reward 0",
        {"step_s": 8},
    ),
    "memory_hog": (
        "every instance passes its memory limit: reward 0",
        {"memory_mb": 400},
    ),
    "corrupt_save": (
        "the damaged-save instance crashes and scores 0; the rest pass",
        {},
    ),
    "wallclock": ("the replay instance scores 0 (traces differ by pace)", {}),
    "giant_logs": ("a reward is written; the output kept is capped", {}),
    "spawner": ("a reward is written; no spawned process outlives its game", {}),
}


def png_bytes(width: int, height: int, pixels: bytes) -> bytes:
    """Encode RGB pixels (width * height * 3 bytes) as a PNG file."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    rows = b"".join(
        b"\x00" + pixels[y * width * 3 : (y + 1) * width * 3] for y in range(height)
    )
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows, 1))
        + chunk(b"IEND", b"")
    )


def build(case: str, dst: Path) -> Path:
    """Write the project for one case into dst (which must not exist).

    Args:
        case: A key of EXPECTED.
        dst: Destination folder.

    Returns:
        dst.

    Raises:
        KeyError: Unknown case.
        FileExistsError: dst exists.
    """
    if case not in EXPECTED:
        raise KeyError(case)
    if dst.exists():
        raise FileExistsError(dst)
    if case == "foreign":
        shutil.copytree(FOREIGN, dst, ignore=shutil.ignore_patterns(".godot"))
        return dst
    shutil.copytree(BASE, dst, ignore=shutil.ignore_patterns(".godot"))
    overlay = FIXTURES / case
    if overlay.is_dir():
        for src in sorted(overlay.rglob("*")):
            rel = src.relative_to(overlay)
            if src.is_dir():
                continue
            if src.name == "project.append":
                with open(dst / "project.godot", "a") as f:
                    f.write(src.read_text())
            elif src.name != "README.txt":
                (dst / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst / rel)
    if case == "big_cache":
        (dst / "noise.png").write_bytes(
            png_bytes(2048, 2048, os.urandom(2048 * 2048 * 3))
        )
    return dst
