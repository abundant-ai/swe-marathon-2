"""Build a self-contained Harbor bundle from sources, the one build of the original and the cases.

usage: package_step.py [--flat [--keep-name]] [--output DIR]

--flat writes the same files without the steps wrapper, under the task name with `-single`
appended, for harnesses that accept only tasks without declared steps; with --keep-name, under
the task's own name, so that the upload is the next version of the same task. The one step's
files move to the top and task.toml loses its [[steps]] tables (whose limits equal the top-level
ones) and its multi-step reward strategy (one step: its reward is the trial's).

Needs, all made beforehand and none committed:
- experiment/build/bpl and build.txt: the hardened original (scripts/build_original.py). It goes,
  compressed, into both images' build contexts (with the private build marker, which mark.py
  writes into it there), beside mark.py and smoke.sh from common/hardening, and into the reference
  solution (with the all-zero marker), beside mark.py alone: the solution only installs it.
- steps/01-rebuild-interpreter/tests/private/cases.json: the private cases (scripts/make_cases.py).
- experiment/seeds.json: the private seeds (scripts/seeds.py), for the marker.
- an upstream checkout holding the pinned commit (BASEDPL_CHECKOUT, default
  ../../../../.cache-src/basedpl next to this repository), whose documentation goes into the
  agent image (bpl_text.documentation) and whose licence goes with the solution, with the source
  the build was compiled from (`hardened_source`, in the solution's source/).

Packaging stops if a private case holds a program the shipped documentation holds, or a
near-copy of one (make_cases.leaks), if a documented item in scope, or a read path of the
file-read rule, has no case (scope_cases.missing), or if the build's sha256 is not the one build.txt
records.

Of the private cases and of build.txt, the bundle holds only what is read there (CASE_KEYS and
PLAN_KEYS, by the verifier image; BUILD_KEYS, by mark.py). The generator's notes on each case
(where it came from: `source`, `suite`, `family`; how it was put together: `want`,
`scaffold_lines`) and the build's provenance (upstream's commit, the toolchain, the target, the
size) stay in the files above, which are never shipped as they are.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpl_text  # noqa: E402

TASK_ROOT = Path(__file__).resolve().parent.parent
STEP = "steps/01-rebuild-interpreter"
HIDDEN = TASK_ROOT / STEP / "tests" / "private" / "cases.json"
BUILD = TASK_ROOT / "experiment" / "build"
EXCLUDED = {"__pycache__", ".pytest_cache", ".DS_Store", "experiment"}
HARDENING = TASK_ROOT / "common" / "hardening"
SHIPPED_TOOLS = ("mark.py", "smoke.sh")  # what of common/hardening both images use; the solution takes mark.py
CASE_KEYS = ("argv", "files", "form", "id", "kind", "links", "outside", "stdin")  # what the verifier image reads of a private case
PLAN_KEYS = ("unset", "variants")  # and of its "record" entry: the recorder's settling plan
BUILD_KEYS = ("link", "sha256")  # what mark.py reads of build.txt: the link mode it reports and the sha256 it checks
# Of upstream's files at the pinned commit, the ones the build of `bpl` reads, for the solution's source/: the
# workspace's manifests, every crate's build script and sources, and what the build embeds (the documentation pages
# build.rs reads, llms.txt, the key layout); not upstream's tests, notes, Python package or web files.
SOURCE_FILES = re.compile(r"Cargo\.toml|build\.rs|LICENSE|\.cargo/config\.toml|src/.+|"
                          r"(cli|jit|image|py|testkit|wasm|xtask)/(Cargo\.toml|build\.rs|src/.+)|"
                          r"nbs/llms\.txt|nbs/((glyphs|system)/)?[^/]+\.(qmd|ipynb)|python/basedpl/browser/layout\.json")


def shipped_cases(cases: list[dict]) -> bytes:
    """The private cases as the bundle holds them: each case's CASE_KEYS and, of its "record" entry,
    PLAN_KEYS, written as make_cases.py writes the private file."""
    shipped = []
    for case in cases:
        kept = {key: case[key] for key in CASE_KEYS if key in case}
        if "record" in case:
            kept["record"] = {key: case["record"][key] for key in PLAN_KEYS if key in case["record"]}
        shipped.append(kept)
    return json.dumps({"cases": shipped}, ensure_ascii=False, sort_keys=True).encode("utf-8")


def shipped_build(build: bytes) -> bytes:
    """build.txt as the bundle holds it: its BUILD_KEYS lines, in their order."""
    lines = [line for line in build.decode("utf-8").splitlines() if line.split(" ", 1)[0] in BUILD_KEYS]
    if sorted(line.split(" ", 1)[0] for line in lines) != sorted(BUILD_KEYS):
        raise ValueError(f"experiment/build/build.txt does not hold each of {', '.join(BUILD_KEYS)} once")
    return ("\n".join(lines) + "\n").encode("utf-8")


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


def hardened_source(checkout: Path) -> dict[str, bytes]:
    """The source the original was compiled from, as readable files: upstream's files at the pinned
    commit that the build reads (SOURCE_FILES), hardened by common/hardening/apply.sh as
    scripts/build_original.py hardens them before it builds (the patch, the all-zero build marker,
    the pinned Cargo.lock).

    Args:
        checkout: An upstream checkout that holds the pinned commit (see bpl_text.git_files).

    Returns:
        The files' bytes by their path in the source tree, sorted.
    """
    with tempfile.TemporaryDirectory() as folder:
        tree = Path(folder) / "basedpl"
        for path in bpl_text.git_files(checkout):
            if SOURCE_FILES.fullmatch(path):
                (tree / path).parent.mkdir(parents=True, exist_ok=True)
                (tree / path).write_bytes(bpl_text.git_bytes(checkout, path))
        subprocess.run(["sh", str(HARDENING / "apply.sh"), str(tree)], capture_output=True, check=True)
        return {path.relative_to(tree).as_posix(): path.read_bytes() for path in sorted(tree.rglob("*")) if path.is_file()}


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
    table = json.loads(content[f"{STEP}/tests/verifier/functions.json"].decode("utf-8"))["functions"]
    if table != bpl_text.function_table(pages):
        raise ValueError("tests/verifier/functions.json is not the shipped documentation's table of functions: "
                         "run scripts/function_table.py")
    import make_cases  # noqa: PLC0415
    import seeds  # noqa: PLC0415

    skeletons, texts = bpl_text.leak_index(pages)
    cases = json.loads(HIDDEN.read_text(encoding="utf-8"))["cases"]
    found = make_cases.leaks(cases, skeletons, texts)
    if found:
        raise ValueError(f"{len(found)} private cases hold a program the documentation shows: "
                         f"{', '.join(cases[int(index)]['id'] for index in found[:20])}")
    import scope_cases  # noqa: PLC0415
    absent = scope_cases.missing(cases, pages)
    if absent:
        raise ValueError(f"no private case uses {len(absent)} documented items in scope: {', '.join(absent[:20])}")
    content[f"{STEP}/tests/private/cases.json"] = shipped_cases(cases)
    for name, text in pages.items():
        content[f"environment/docs/{name}"] = text.encode("utf-8")
    packed, build = original()
    build = shipped_build(build)
    tools = {name: (HARDENING / name).read_bytes() for name in SHIPPED_TOOLS}
    marker = str(seeds.value("marker")).encode() + b"\n"
    for place in ("environment", f"{STEP}/tests"):
        content[f"{place}/original/bpl.xz"] = packed
        content[f"{place}/original/build.txt"] = build
        content[f"{place}/original/marker"] = marker
        for name, data in tools.items():
            content[f"{place}/original/{name}"] = data
    # The reference solution gets the build with its zero marker (no marker file), its installer and the licence.
    content[f"{STEP}/solution/bpl.xz"] = packed
    content[f"{STEP}/solution/build.txt"] = build
    content[f"{STEP}/solution/mark.py"] = tools["mark.py"]
    content[f"{STEP}/solution/LICENSE"] = bpl_text.git_bytes(checkout, "LICENSE")
    for name, data in hardened_source(checkout).items():  # the source of that build, to read: never installed
        content[f"{STEP}/solution/source/{name}"] = data
    return dict(sorted(content.items()))


def flatten(content: dict[str, bytes], keep_name: bool = False) -> dict[str, bytes]:
    """The bundle without the steps wrapper, under the task name with `-single` appended, or under
    the task's own name with `keep_name`."""
    prefix = f"{STEP}/"
    flat = {(name[len(prefix):] if name.startswith(prefix) else name): data for name, data in content.items()}
    head, marker, _ = content["task.toml"].decode().partition("\n[[steps]]")
    if not marker:
        raise ValueError("task.toml declares no [[steps]] table")
    import tomllib  # noqa: PLC0415
    config = tomllib.loads(content["task.toml"].decode())
    for step in config["steps"]:
        for part in ("agent", "verifier"):
            if step.get(part, {}).get("timeout_sec", config[part]["timeout_sec"]) != config[part]["timeout_sec"]:
                raise ValueError(f"step {step['name']}'s {part} limit differs from the top-level one: a flat bundle would change it")
    head = re.sub(r"^multi_step_reward_strategy\s*=.*\n", "", head, flags=re.M)
    if not keep_name:
        head, count = re.subn(r'^(name = "abundant/[^"]+)"', r'\1-single"', head, count=1, flags=re.M)
        if count != 1:
            raise ValueError("task.toml has no [task].name to rename")
    flat["task.toml"] = (head.rstrip("\n") + "\n").encode()
    return flat


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flat", action="store_true")
    parser.add_argument("--keep-name", action="store_true", help="with --flat: keep the task's own name")
    parser.add_argument("--output", type=Path, default=TASK_ROOT / "experiment" / "dist")
    args = parser.parse_args()
    if args.keep_name and not args.flat:
        parser.error("--keep-name goes with --flat")
    content = collect()
    if args.flat:
        content = flatten(content, keep_name=args.keep_name)
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
