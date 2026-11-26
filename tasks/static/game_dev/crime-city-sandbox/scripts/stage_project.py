"""Assemble a runnable game project for local runs: the starter, overlays, the vendor art.

Author tool for this Mac (never packaged). The vendor art (the four CC0 packs) never
enters Git: the starter's assets/vendor/ keeps only the .import files, the bone map and
the licences. This copies, in order:
1. environment/game (the starter) to OUT, without any .godot folder;
2. each --overlay folder over it (the reference game's files, for example; a file in an
   overlay replaces the starter's file of the same path);
3. the art binaries of the packs already on this machine (game-spike/vendor, no download)
   into OUT/assets/vendor/<pack>/, next to their .import files.

Usage:
  python scripts/stage_project.py --out DIR [--overlay DIR ...] [--vendor DIR] [--no-art]
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
STARTER = TASK / "environment" / "game"
VENDOR = Path.home() / "Documents/github/Abundant/game-spike/vendor"
UBC = (
    "quaternius-universal-base-characters/extracted/Universal Base Characters[Standard]"
)
UAL = "quaternius-universal-animation-library/extracted/Universal Animation Library[Standard]"
# Starter folder under assets/vendor -> (source folder under VENDOR, licence file there).
PACKS = {
    "kenney_car_kit": (
        "kenney-car-kit/extracted/Models/GLB format",
        "kenney-car-kit/extracted/License.txt",
    ),
    "kenney_city_roads": (
        "kenney-city-kit-roads/extracted/Models/GLB format",
        "kenney-city-kit-roads/extracted/License.txt",
    ),
    "ubc": (f"{UBC}/Base Characters/Godot - UE", f"{UBC}/License_Standard.txt"),
    "ubc_hair": (
        f"{UBC}/Hairstyles/Rigged to Head Bone/glTF (Godot -Unreal)",
        f"{UBC}/License_Standard.txt",
    ),
    "ual": (f"{UAL}/Unreal-Godot", f"{UAL}/License.txt"),
}
ART_SUFFIXES = (".glb", ".gltf", ".bin", ".png")


def art_files(vendor: Path) -> list[tuple[Path, str]]:
    """Every art binary of the packs as (source file, path under assets/vendor).

    Args:
        vendor: The folder holding the extracted packs (game-spike/vendor).

    Returns:
        Sorted pairs; raises FileNotFoundError when a pack folder is missing.
    """
    out = []
    for pack, (src, _licence) in PACKS.items():
        root = vendor / src
        if not root.is_dir():
            raise FileNotFoundError(f"pack folder missing: {root}")
        for f in sorted(root.rglob("*")):
            if f.is_file() and f.suffix.lower() in ART_SUFFIXES:
                out.append((f, f"{pack}/{f.relative_to(root).as_posix()}"))
    return out


def licences(vendor: Path) -> list[tuple[Path, str]]:
    """The packs' licence files as (source file, path under assets/vendor)."""
    return [(vendor / lic, f"{pack}/License.txt") for pack, (_s, lic) in PACKS.items()]


def copy_tree(src: Path, dst: Path) -> None:
    """Copy src's files over dst (merging), skipping .godot, .git and Python caches."""
    skip = {".godot", ".git", "__pycache__"}
    for f in sorted(src.rglob("*")):
        rel = f.relative_to(src)
        if any(part in skip for part in rel.parts) or not f.is_file():
            continue
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, target)


def stage(out: Path, overlays: list[Path], vendor: Path, art: bool = True) -> int:
    """Build OUT from the starter, the overlays and (optionally) the art binaries.

    Args:
        out: Destination; must not exist.
        overlays: Folders copied over the starter, in order.
        vendor: The extracted packs.
        art: Copy the art binaries too.

    Returns:
        The number of art files copied.
    """
    if out.exists():
        raise FileExistsError(out)
    out.mkdir(parents=True)
    copy_tree(STARTER, out)
    for ov in overlays:
        if not ov.is_dir():
            raise FileNotFoundError(ov)
        copy_tree(ov, out)
    n = 0
    if art:
        for src, rel in art_files(vendor):
            target = out / "assets" / "vendor" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            n += 1
    return n


def main() -> int:
    """Parse the command line and stage the project."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--overlay", type=Path, action="append", default=[])
    ap.add_argument("--vendor", type=Path, default=VENDOR)
    ap.add_argument("--no-art", action="store_true")
    a = ap.parse_args()
    n = stage(a.out.resolve(), [o.resolve() for o in a.overlay], a.vendor, not a.no_art)
    print(f"staged {a.out} ({n} art files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
