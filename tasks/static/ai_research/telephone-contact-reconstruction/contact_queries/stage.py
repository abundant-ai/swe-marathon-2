"""Add metric contact picking to a fully hydrated telephone reconstruction package."""

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASK = HERE.parent
NAME = "swe-m2_ai-research_telephone-contact-picking"


def stage(base, out):
    if out.exists():
        raise FileExistsError(out)
    inventory = json.loads((TASK / "scripts/qualified-inventory.json").read_text())
    actual = {path.relative_to(base).as_posix() for path in base.rglob("*") if path.is_file()}
    if actual != inventory.keys():
        raise ValueError("Expected the complete qualified telephone runtime")
    for name in inventory:
        if hashlib.sha256((base/name).read_bytes()).hexdigest() != inventory[name]:
            raise ValueError(f"Expected a qualified matched telephone package at {name}")
    shutil.copytree(base, out)
    for file in (TASK / "solution").iterdir():
        if file.is_file() and file.suffix in {".py", ".json", ".c", ".sh"}:
            shutil.copy2(file, out / "solution" / file.name)
    score = out / "tests/private/dense-telephone-parts"
    shutil.copy2(HERE / "contact_queries.py", score)
    shutil.copy2(HERE / "telephone_score.py", score)
    shutil.copy2(HERE / "test_reconstruction.py", out / "tests")
    (score / "contact-picking.enabled").touch()
    digests_path = out / "tests/fixture-digests.json"
    private = out / "tests/private"
    digests = {}
    for path in sorted(private.rglob("*")):
        if path.is_file():
            with path.open("rb") as source:
                digests[path.relative_to(private).as_posix()] = hashlib.file_digest(source, "sha256").hexdigest()
    shutil.copy2(TASK / "tests/verify.py", out / "tests/verify.py")
    digests_path.write_text(json.dumps(digests, indent=2, sort_keys=True) + "\n")
    config = out / "task.toml"
    config.write_text(
        re.sub(r'name = "abundant/[^"]+"', f'name = "abundant/{NAME}"', config.read_text(), count=1)
        .replace("four named contact surfaces", "depth-accurate contact picks")
    )
    brief = out / "instruction.md"
    brief.write_text(
        brief.read_text().rstrip() + "\n\n" + (HERE / "brief.md").read_text()
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path)
    parser.add_argument("output_root", type=Path)
    args = parser.parse_args()
    stage(args.base, args.output_root / NAME)
