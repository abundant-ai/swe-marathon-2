"""Build the flat, self-contained Harbor bundle of this task and print its content hash.

usage: package_task.py [--output DIR]

The bundle holds what the platform needs and nothing else: task.toml, instruction.md, environment/ (the agent image
inputs), tests/ (the verifier image inputs, including the staged private cases, fonts and the meson wheel) and
solution/ (the reference patch). The README, notes, development scripts and the private store stay out. Packaging
stops when a staged input is missing, when environment/docs/notes.md no longer matches the instruction, or when an
agent-visible file names a private case.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
SHIPPED = ("task.toml", "instruction.md", "environment", "tests", "solution")
EXCLUDED_NAMES = {".gitignore", ".DS_Store", "__pycache__"}
REQUIRED = (
    "tests/private/cases.jsonl",
    "tests/private/expected.json",
    "tests/driver/hbdrv.c",
    "solution/private/harfbuzz-14.3.0-to-15.2.0.patch",
)


def collect() -> dict[str, bytes]:
    content: dict[str, bytes] = {}
    for top in SHIPPED:
        path = TASK / top
        files = (
            [path]
            if path.is_file()
            else sorted(p for p in path.rglob("*") if p.is_file())
        )
        for f in files:
            rel = f.relative_to(TASK)
            if any(part in EXCLUDED_NAMES for part in rel.parts):
                continue
            content[rel.as_posix()] = f.read_bytes()
    for name in REQUIRED:
        if name not in content:
            raise SystemExit(f"missing {name}: stage the private material first")
    if not any(n.startswith("tests/wheels/meson-") for n in content):
        raise SystemExit("missing the meson wheel in tests/wheels/")
    return content


def check_notes(content: dict[str, bytes]) -> None:
    instruction = content["instruction.md"].decode()
    notes = content["environment/docs/notes.md"].decode()
    start = instruction.index("## The notes, 14.3.1 to 15.2.0")
    section = instruction[start:].split("\n", 1)[1]
    following = section.find("\n## ")
    body = (section if following < 0 else section[:following]).strip("\n")
    if body not in notes:
        raise SystemExit(
            "environment/docs/notes.md does not match the instruction's notes"
        )


def check_leaks(content: dict[str, bytes]) -> None:
    cases = [
        json.loads(line)
        for line in content["tests/private/cases.jsonl"].decode().splitlines()
        if line
    ]
    ids = {c["id"] for c in cases}
    fonts = {Path(c["font"]).name for c in cases if c["font"].startswith("synth/")}
    visible = {
        n: d
        for n, d in content.items()
        if n.startswith("environment/") or n == "instruction.md"
    }
    for name, data in visible.items():
        text = data.decode(errors="replace")
        hits = [i for i in ids if i in text] + [f for f in fonts if f in text]
        if hits:
            raise SystemExit(f"{name} names private material: {hits[:3]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=TASK / "experiment" / "dist")
    args = parser.parse_args()
    content = collect()
    check_notes(content)
    check_leaks(content)
    slug = re.search(
        r'^name = "abundant/([^"]+)"', content["task.toml"].decode(), flags=re.MULTILINE
    ).group(1)
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in content.items()}
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    staging = args.output.resolve() / "flat" / digest[:12] / slug
    if staging.exists():
        shutil.rmtree(staging)
    for name, data in content.items():
        target = staging / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if name.endswith(".sh"):
            target.chmod(0o755)
    (staging.parent / "SHA256SUMS").write_text(
        "".join(f"{h}  {n}\n" for n, h in sorted(hashes.items()))
    )
    print(
        json.dumps(
            {
                "task_path": str(staging),
                "content_sha256": digest,
                "files": len(content),
                "bytes": sum(len(d) for d in content.values()),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
