"""Build a self-contained Harbor bundle from sources and generated cases.

usage: package_step.py [--flat] [--output DIR]

The default bundle uses the task-root instruction, tests and solution.
Use --flat to publish the same files with the existing -single suffix.

The upstream checkout (GOOSE_CHECKOUT, default ../../../../../.cache-src/goose next to this
repository) must be at UPSTREAM_COMMIT. Its build sources, less the standard library's os and
ffi modules, go into both images and into the reference solution, which builds the original
compiler itself, each with the hardening in common/hardening (apply.sh before the build,
smoke.sh after it); its documentation and samples go into the agent image. Its tests never
leave this machine except as generated cases, and packaging stops if a private case has an input
that a shipped file or a visible case already holds.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parent.parent
STEP = "steps/01-rebuild-compiler"
HIDDEN = TASK_ROOT / "tests" / "private" / "cases.json"
VISIBLE = TASK_ROOT / "experiment" / "visible.json"
UPSTREAM_COMMIT = (
    "745901fd48224feb782d707922a20dcd25c669fd"  # aardappel/goose, Apache-2.0
)
EXCLUDED = {"__pycache__", ".pytest_cache", ".DS_Store", "experiment"}
BUILD_SOURCES = (
    "CMakeLists.txt",
    "LICENSE",
    "cmake/",
    "src/",
    "stdlib/",
    "third_party/",
)
# Modules that read raw memory (ffi) or any file (os) from inside the compiler's process,
# where `goose run` runs a program: never built or installed.
DROPPED = ("stdlib/ffi.goose", "stdlib/os.goose")
HARDENING = TASK_ROOT / "common" / "hardening"


def tracked(checkout: Path) -> list[str]:
    return [
        name
        for name in subprocess.run(
            ["git", "-C", str(checkout), "ls-files"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split("\n")
        if name
    ]


def shipped_docs(name: str) -> bool:
    """README, licence, the Markdown documentation and the sample programs; no tests, editors, sites or data."""
    if name in ("README.md", "LICENSE", "samples/README.md"):
        return True
    if re.fullmatch(r"docs/(design/)?[^/]+\.md", name):
        return (
            name != "docs/testing.md"
        )  # how upstream tests itself: not documentation of the compiler
    return bool(re.fullmatch(r"samples/[^/]+\.goose", name))


def agent_visible(name: str) -> bool:
    """A checkout file the agent image holds: documentation and samples in /app/docs, the
    standard library in /usr/local/share/goose/stdlib."""
    return shipped_docs(name) or (name.startswith("stdlib/") and name not in DROPPED)


def collect() -> dict[str, bytes]:
    """Collect the prepared cases, runtime files and upstream inputs by archive path."""
    for required in (HIDDEN, VISIBLE):
        if not required.is_file():
            raise ValueError(
                f"Generate the cases first (scripts/make_cases.py); missing {required.name}"
            )
    content: dict[str, bytes] = {"task.toml": (TASK_ROOT / "task.toml").read_bytes()}
    content["instruction.md"] = (TASK_ROOT / "instruction.md").read_bytes()
    for directory in ("environment", "tests", "solution"):
        for path in (TASK_ROOT / directory).rglob("*"):
            relative = path.relative_to(TASK_ROOT)
            if (
                path.is_file()
                and not EXCLUDED.intersection(relative.parts)
                and path.suffix != ".pyc"
            ):
                content[relative.as_posix()] = path.read_bytes()
    checkout = Path(
        os.environ.get("GOOSE_CHECKOUT", TASK_ROOT.parents[4] / ".cache-src" / "goose")
    )
    head = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if head != UPSTREAM_COMMIT:
        raise ValueError(
            f"The upstream checkout at {checkout} is not at {UPSTREAM_COMMIT}"
        )
    import make_cases
    import seeds

    found = make_cases.leaks(
        json.loads(HIDDEN.read_text(encoding="utf-8"))["cases"],
        json.loads(VISIBLE.read_text(encoding="utf-8"))["cases"],
        make_cases.shipped_texts(checkout),
        make_cases.shared_modules(checkout),
    )
    if found:
        raise ValueError(
            f"{len(found)} private cases have an input the agent can know: {', '.join(found[:20])}"
        )
    for name in tracked(checkout):
        data = None
        if (
            name.startswith(BUILD_SOURCES) or name in BUILD_SOURCES
        ) and name not in DROPPED:
            data = (checkout / name).read_bytes()
            for place in ("environment", "tests", "solution"):
                content[f"{place}/upstream/{name}"] = data
        if shipped_docs(name):
            content[f"environment/docs/{name}"] = (
                data if data is not None else (checkout / name).read_bytes()
            )
    for path in sorted(HARDENING.iterdir()):
        for place in ("environment", "tests", "solution"):
            content[f"{place}/hardening/{path.name}"] = path.read_bytes()
    # The build marker (scripts/seeds.py) goes into both images' builds of the original, never into
    # the solution's: the verifier refuses a submission that holds it.
    marker = str(seeds.value("marker")).encode() + b"\n"
    for place in ("environment", "tests"):
        content[f"{place}/hardening/marker"] = marker
    content["environment/run_examples.py"] = (
        TASK_ROOT / "tests" / "verifier" / "runcases.py"
    ).read_bytes()
    content["environment/recorder.py"] = (
        TASK_ROOT / "tests" / "verifier" / "recorder.py"
    ).read_bytes()
    content["environment/examples.json"] = VISIBLE.read_bytes()
    return dict(sorted(content.items()))


def flatten(content: dict[str, bytes]) -> dict[str, bytes]:
    prefix = f"{STEP}/"
    flat = {(name.removeprefix(prefix)): data for name, data in content.items()}
    head, _, _ = content["task.toml"].decode().partition("\n[[steps]]")
    head = re.sub(r"^multi_step_reward_strategy\s*=.*\n", "", head, flags=re.MULTILINE)
    head, count = re.subn(
        r'^(name = "abundant/[^"]+)"', r'\1-single"', head, count=1, flags=re.MULTILINE
    )
    if count != 1:
        raise ValueError("task.toml has no [task].name to rename")
    flat["task.toml"] = (head.rstrip("\n") + "\n").encode()
    return flat


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flat", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=TASK_ROOT / "experiment" / "dist"
    )
    args = parser.parse_args()
    content = collect()
    if args.flat:
        content = flatten(content)
    slug = re.search(
        r'^name = "abundant/([^"]+)"', content["task.toml"].decode(), flags=re.MULTILINE
    ).group(1)
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in content.items()}
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    staging = (
        args.output.resolve()
        / ("flat" if args.flat else "bundles")
        / digest[:12]
        / slug
    )
    if staging.exists():
        shutil.rmtree(staging)
    for name, data in content.items():
        target = staging / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if name.endswith(".sh"):
            target.chmod(0o755)
    print(
        json.dumps(
            {
                "task_path": str(staging),
                "content_sha256": digest,
                "files": len(content),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
