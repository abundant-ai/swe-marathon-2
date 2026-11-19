"""Build a self-contained Harbor bundle from sources, the one build of the original and the cases.

usage: package_step.py [--flat] [--output DIR]

--flat writes the same files without the steps wrapper, under the task name with `-single`
appended, for harnesses that accept only tasks without declared steps.

Needs, all made beforehand and none committed:
- experiment/build/bpl and build.txt: the hardened original (scripts/build_original.py). It goes,
  compressed, into both images' build contexts (with the private build marker, which mark.py
  writes into it there) and into the reference solution (with the all-zero marker), each beside
  mark.py and smoke.sh from common/hardening.
- steps/01-rebuild-interpreter/tests/private/cases.json: the private cases (scripts/make_cases.py).
- experiment/seeds.json: the private seeds (scripts/seeds.py), for the marker.
- an upstream checkout holding the pinned commit (BASEDPL_CHECKOUT, default
  ../../../../.cache-src/basedpl next to this repository), whose documentation goes into the
  agent image (bpl_text.documentation) and whose licence goes with the solution.

Packaging stops if a private case holds a program the shipped documentation holds, or a
near-copy of one (make_cases.leaks), or if the build's sha256 is not the one build.txt records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpl_text  # noqa: E402

TASK_ROOT = Path(__file__).resolve().parent.parent
STEP = "steps/01-rebuild-interpreter"
HIDDEN = TASK_ROOT / STEP / "tests" / "private" / "cases.json"
BUILD = TASK_ROOT / "experiment" / "build"
EXCLUDED = {"__pycache__", ".pytest_cache", ".DS_Store", "experiment"}
HARDENING = TASK_ROOT / "common" / "hardening"
SHIPPED_TOOLS = ("mark.py", "smoke.sh")  # what of common/hardening the images and the solution use


def original() -> tuple[bytes, bytes]:
    """The compressed build of the original and its build.txt, after checking that the build is
    the one build.txt records (its sha256) and holds the zero marker once."""
    binary, build = BUILD / "bpl", BUILD / "build.txt"
    if not binary.is_file() or not build.is_file():
        raise ValueError("Build the original first (scripts/build_original.py); experiment/build/bpl is missing")
    data = binary.read_bytes()
    facts = dict(line.split(" ", 1) for line in build.read_text().splitlines() if " " in line)
    if hashlib.sha256(data).hexdigest() != facts.get("sha256"):
        raise ValueError("experiment/build/bpl is not the build that build.txt records")
    if data.count(b"BPL-BUILD-MARKER-" + b"0" * 32) != 1:
        raise ValueError("experiment/build/bpl does not hold the zero build marker exactly once")
    packed = BUILD / "bpl.xz"
    if not packed.is_file() or lzma.decompress(packed.read_bytes()) != data:
        packed.write_bytes(lzma.compress(data, preset=9 | lzma.PRESET_EXTREME))
    return packed.read_bytes(), build.read_bytes()


def collect() -> dict[str, bytes]:
    """Every file of the bundle, by its path in the bundle."""
    if not HIDDEN.is_file():
        raise ValueError("Generate the cases first (scripts/make_cases.py); the private cases.json is missing")
    content: dict[str, bytes] = {"task.toml": (TASK_ROOT / "task.toml").read_bytes()}
    for directory in ("environment", STEP):
        for path in (TASK_ROOT / directory).rglob("*"):
            relative = path.relative_to(TASK_ROOT)
            if path.is_file() and not EXCLUDED.intersection(relative.parts) and path.suffix != ".pyc":
                content[relative.as_posix()] = path.read_bytes()
    checkout = Path(os.environ.get("BASEDPL_CHECKOUT", TASK_ROOT.parents[3] / ".cache-src" / "basedpl"))
    pages = bpl_text.documentation(checkout)
    import make_cases  # noqa: PLC0415
    import seeds  # noqa: PLC0415

    skeletons, texts = bpl_text.leak_index(pages)
    cases = json.loads(HIDDEN.read_text(encoding="utf-8"))["cases"]
    found = make_cases.leaks(cases, skeletons, texts)
    if found:
        raise ValueError(f"{len(found)} private cases hold a program the documentation shows: "
                         f"{', '.join(cases[int(index)]['id'] for index in found[:20])}")
    for name, text in pages.items():
        content[f"environment/docs/{name}"] = text.encode("utf-8")
    packed, build = original()
    tools = {name: (HARDENING / name).read_bytes() for name in SHIPPED_TOOLS}
    marker = str(seeds.value("marker")).encode() + b"\n"
    for place in ("environment", f"{STEP}/tests"):
        content[f"{place}/original/bpl.xz"] = packed
        content[f"{place}/original/build.txt"] = build
        content[f"{place}/original/marker"] = marker
        for name, data in tools.items():
            content[f"{place}/original/{name}"] = data
    # The reference solution gets the build with its zero marker: no marker file.
    content[f"{STEP}/solution/bpl.xz"] = packed
    content[f"{STEP}/solution/build.txt"] = build
    for name, data in tools.items():
        content[f"{STEP}/solution/{name}"] = data
    content[f"{STEP}/solution/LICENSE"] = bpl_text.git_bytes(checkout, "LICENSE")
    return dict(sorted(content.items()))


def flatten(content: dict[str, bytes]) -> dict[str, bytes]:
    """The bundle without the steps wrapper, under the task name with `-single` appended."""
    prefix = f"{STEP}/"
    flat = {(name[len(prefix):] if name.startswith(prefix) else name): data for name, data in content.items()}
    head, marker, _ = content["task.toml"].decode().partition("\n[[steps]]")
    if not marker:
        raise ValueError("task.toml declares no [[steps]] table")
    head = re.sub(r"^multi_step_reward_strategy\s*=.*\n", "", head, flags=re.M)
    head, count = re.subn(r'^(name = "abundant/[^"]+)"', r'\1-single"', head, count=1, flags=re.M)
    if count != 1:
        raise ValueError("task.toml has no [task].name to rename")
    flat["task.toml"] = (head.rstrip("\n") + "\n").encode()
    return flat


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flat", action="store_true")
    parser.add_argument("--output", type=Path, default=TASK_ROOT / "experiment" / "dist")
    args = parser.parse_args()
    content = collect()
    if args.flat:
        content = flatten(content)
    slug = re.search(r'^name = "abundant/([^"]+)"', content["task.toml"].decode(), flags=re.M).group(1)
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in content.items()}
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    staging = args.output.resolve() / ("flat" if args.flat else "bundles") / digest[:12] / slug
    if staging.exists():
        shutil.rmtree(staging)
    for name, data in content.items():
        target = staging / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if name.endswith(".sh"):
            target.chmod(0o755)
    size = sum(len(data) for data in content.values())
    print(json.dumps({"task_path": str(staging), "content_sha256": digest, "files": len(content), "bytes": size}, indent=2))


if __name__ == "__main__":
    main()
