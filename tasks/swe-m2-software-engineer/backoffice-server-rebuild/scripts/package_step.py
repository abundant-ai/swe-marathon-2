"""Build a self-contained Harbor bundle from sources, the pinned reference application and recorded scenarios.

usage: package_step.py [--flat] [--output DIR]

--flat writes the same files without the steps wrapper, under the task name with
`-single` appended, for harnesses that accept only tasks without declared steps.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from reference import checkout  # noqa: E402

TASK_ROOT = Path(__file__).resolve().parent.parent
STEP = "steps/01-rebuild-server"
SCENARIOS = TASK_ROOT / STEP / "tests" / "private" / "scenarios.json"
MEDIA = TASK_ROOT / "experiment" / "media"  # scripts/make_media.py: `visible` ships as samples, `private` only to the verifier
EXCLUDED = {"__pycache__", ".pytest_cache", ".DS_Store", "experiment"}
CLIENT_FILES = ("index.html", "package.json", "package-lock.json", "tsconfig.json", "tsconfig.app.json", "tsconfig.node.json", "vite.config.ts",
                "eslint.config.js", ".prettierrc.json", "openapi.json", "README.md")


def collect() -> dict[str, bytes]:
    """Map bundle paths to file contents.

    Raises:
        ValueError: The private scenarios have not been recorded.
    """
    if not SCENARIOS.is_file():
        raise ValueError("Record the scenarios first: scripts/record_scenarios.py")
    for kind in ("visible", "private"):
        if not (MEDIA / kind / "manifest.json").is_file():
            raise ValueError(f"Make the media first: scripts/make_media.py --out experiment/media/{kind}")
    content: dict[str, bytes] = {"task.toml": (TASK_ROOT / "task.toml").read_bytes()}
    for directory in ("environment", STEP):
        for path in (TASK_ROOT / directory).rglob("*"):
            relative = path.relative_to(TASK_ROOT)
            if path.is_file() and not EXCLUDED.intersection(relative.parts) and path.suffix != ".pyc" and path != SCENARIOS:
                content[relative.as_posix()] = path.read_bytes()
    # the scenarios travel compressed (a tenth of the size); mtime 0 keeps the bundle hash stable
    content[f"{STEP}/tests/private/scenarios.json.gz"] = gzip.compress(SCENARIOS.read_bytes(), compresslevel=9, mtime=0)
    source = checkout()
    package = source / "backend" / "src" / "stockwell"
    for path in sorted(package.rglob("*.py")):
        relative = path.relative_to(package).as_posix()
        content[f"environment/sealed/stockwell/{relative}"] = path.read_bytes()
        content[f"{STEP}/solution/data/stockwell/{relative}"] = path.read_bytes()
    requirements = (source / "requirements.txt").read_bytes()
    content["environment/requirements.txt"] = requirements
    content[f"{STEP}/tests/requirements.txt"] = requirements
    client = source / "frontend"
    for name in CLIENT_FILES:
        if (client / name).is_file():
            content[f"environment/client/{name}"] = (client / name).read_bytes()
    for folder in ("src", "public", "dist"):
        for path in sorted((client / folder).rglob("*")):
            relative = path.relative_to(client)
            if path.is_file() and not path.name.endswith(".map") and "test" not in relative.parts and "test" not in path.name.split("."):
                content[f"environment/client/{path.relative_to(client).as_posix()}"] = path.read_bytes()
    for path in sorted((source / "backend" / "tests" / "fixtures").iterdir()):
        if path.is_file():
            content[f"environment/samples/{path.name}"] = path.read_bytes()
    for kind, place in (("visible", "environment/samples"), ("private", f"{STEP}/tests/private/media")):
        for path in sorted((MEDIA / kind).rglob("*")):
            if path.is_file() and path.name != "manifest.json" and not path.name.startswith("."):
                content[f"{place}/{path.relative_to(MEDIA / kind).as_posix()}"] = path.read_bytes()
    return dict(sorted(content.items()))


def flatten(content: dict[str, bytes]) -> dict[str, bytes]:
    prefix = f"{STEP}/"
    flat = {(name[len(prefix):] if name.startswith(prefix) else name): data for name, data in content.items()}
    config = content["task.toml"].decode()
    head, marker, _ = config.partition("\n[[steps]]")
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
        if name.endswith((".sh", "start-sealed-server")):
            target.chmod(0o755)
    print(json.dumps({"task_path": str(staging), "content_sha256": digest, "files": len(content)}, indent=2))


if __name__ == "__main__":
    main()
