"""Build a self-contained Harbor bundle from sources, the pinned reference application and recorded scenarios.

usage: package_step.py [--flat] [--output DIR]

--flat writes the same files without the steps wrapper, under the task name with
`-single` appended, for harnesses that accept only tasks without declared steps.

The reference server ships as bytecode only (compiled here with Python 3.12, the
images' version), both as the sealed server and as the solution's data, so no
source of it is in the bundle or in any layer of either image. Files are hashed
and copied in chunks: the media alone is a couple of hundred megabytes.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from reference import checkout  # noqa: E402

TASK_ROOT = Path(__file__).resolve().parent.parent
STEP = "steps/01-rebuild-server"
SCENARIOS = TASK_ROOT / STEP / "tests" / "private" / "scenarios.json"
MEDIA = TASK_ROOT / "experiment" / "media"  # scripts/make_media.py: `visible` ships as samples, `private` only to the verifier
CACHE = TASK_ROOT / "experiment" / "dist" / ".cache"
EXCLUDED = {"__pycache__", ".pytest_cache", ".DS_Store", "experiment"}
CLIENT_FILES = ("index.html", "package.json", "package-lock.json", "tsconfig.json", "tsconfig.app.json", "tsconfig.node.json", "vite.config.ts",
                "eslint.config.js", ".prettierrc.json", "openapi.json", "README.md")
EXECUTABLE = (".sh", "start-sealed-server", "prepare-delivery")
# py_compile with hash-based, unchecked headers: no source mtime in the file, so the bytes depend on the source alone.
# optimize=0 keeps docstrings and asserts, which the server's behaviour depends on (its OpenAPI text, for one).
COMPILE = """
import json, py_compile, sys
for source, target, shown in json.load(sys.stdin):
    py_compile.compile(source, cfile=target, dfile=shown, doraise=True, optimize=0,
                       invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)
"""

Source = bytes | Path


def python312(reference: Path) -> list[str]:
    """A Python 3.12 to compile with: STOCKWELL_PYTHON, the checkout's environment, or one uv provides."""
    for candidate in (os.environ.get("STOCKWELL_PYTHON"), str(reference / "backend" / ".venv" / "bin" / "python")):
        if candidate and Path(candidate).exists():
            return [candidate]
    return ["uv", "run", "--no-project", "--python", "3.12", "python"]


def compiled(reference: Path) -> dict[str, Path]:
    """Bytecode of the reference package for the sealed server and for the solution, cached by source content."""
    package = reference / "backend" / "src" / "stockwell"
    sources = sorted(package.rglob("*.py"))
    command = python312(reference)
    version = subprocess.run([*command, "-c", "import sys; print(sys.version_info[:2] == (3, 12), sys.version.split()[0])"],
                             capture_output=True, text=True, check=True).stdout.split()
    if version[0] != "True":
        raise ValueError(f"the reference must be compiled with Python 3.12, not {version[1]}")
    digest = hashlib.sha256(version[1].encode())
    for path in sources:
        digest.update(path.relative_to(package).as_posix().encode() + b"\0" + path.read_bytes())
    folder = CACHE / f"bytecode-{digest.hexdigest()[:16]}"
    places = {"environment/sealed/stockwell": "/opt/stockwell/app/stockwell", f"{STEP}/solution/data/stockwell": "/app/server/stockwell"}
    jobs, out = [], {}
    for prefix, shown in places.items():
        for path in sources:
            relative = path.relative_to(package).with_suffix(".pyc").as_posix()
            target = folder / prefix / relative
            out[f"{prefix}/{relative}"] = target
            jobs.append([str(path), str(target), f"{shown}/{path.relative_to(package).as_posix()}"])
    if not (folder / ".done").is_file():
        shutil.rmtree(folder, ignore_errors=True)
        subprocess.run([*command, "-I", "-c", COMPILE], input=json.dumps(jobs), text=True, check=True)
        (folder / ".done").write_text("ok\n")
    return out


def compressed_scenarios() -> Path:
    """The scenarios gzipped (a tenth of the size) in chunks, mtime 0 for a stable hash, cached by source content."""
    digest = hashlib.sha256()
    with open(SCENARIOS, "rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    target = CACHE / f"scenarios-{digest.hexdigest()[:16]}.json.gz"
    if not target.is_file():
        CACHE.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix(".part")
        with open(SCENARIOS, "rb") as source, open(partial, "wb") as raw, \
                gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as packed:
            for chunk in iter(lambda: source.read(1 << 20), b""):
                packed.write(chunk)
        partial.replace(target)
    return target


def collect() -> dict[str, Source]:
    """Map bundle paths to their contents, as bytes or as the file that holds them.

    Raises:
        ValueError: The private scenarios have not been recorded, or the media not made.
    """
    if not SCENARIOS.is_file():
        raise ValueError("Record the scenarios first: scripts/record_scenarios.py")
    for kind in ("visible", "private"):
        if not (MEDIA / kind / "manifest.json").is_file():
            raise ValueError(f"Make the media first: scripts/make_media.py --out experiment/media/{kind}")
    content: dict[str, Source] = {"task.toml": TASK_ROOT / "task.toml"}
    for directory in ("environment", STEP):
        for path in (TASK_ROOT / directory).rglob("*"):
            relative = path.relative_to(TASK_ROOT)
            if path.is_file() and not EXCLUDED.intersection(relative.parts) and path.suffix != ".pyc" and path != SCENARIOS:
                content[relative.as_posix()] = path
    content[f"{STEP}/tests/private/scenarios.json.gz"] = compressed_scenarios()
    source = checkout()
    content.update(compiled(source))
    content["environment/requirements.txt"] = source / "requirements.txt"
    content[f"{STEP}/tests/requirements.txt"] = source / "requirements.txt"
    client = source / "frontend"
    for name in CLIENT_FILES:
        if (client / name).is_file():
            content[f"environment/client/{name}"] = client / name
    for folder in ("src", "public", "dist"):
        for path in sorted((client / folder).rglob("*")):
            relative = path.relative_to(client)
            if path.is_file() and not path.name.endswith(".map") and "test" not in relative.parts and "test" not in path.name.split("."):
                content[f"environment/client/{relative.as_posix()}"] = path
    # Stockwell's own test fixtures never ship: the hidden `files` scenarios upload them (scripts/scan_uploads.py)
    for kind, place in (("visible", "environment/samples"), ("private", f"{STEP}/tests/private/media")):
        for path in sorted((MEDIA / kind).rglob("*")):
            if path.is_file() and path.name != "manifest.json" and not path.name.startswith("."):
                content[f"{place}/{path.relative_to(MEDIA / kind).as_posix()}"] = path
    return dict(sorted(content.items()))


def flatten(content: dict[str, Source]) -> dict[str, Source]:
    prefix = f"{STEP}/"
    flat = {(name[len(prefix):] if name.startswith(prefix) else name): data for name, data in content.items()}
    config = read(content["task.toml"]).decode()
    head, marker, _ = config.partition("\n[[steps]]")
    if not marker:
        raise ValueError("task.toml declares no [[steps]] table")
    head = re.sub(r"^multi_step_reward_strategy\s*=.*\n", "", head, flags=re.M)
    head, count = re.subn(r'^(name = "abundant/[^"]+)"', r'\1-single"', head, count=1, flags=re.M)
    if count != 1:
        raise ValueError("task.toml has no [task].name to rename")
    flat["task.toml"] = (head.rstrip("\n") + "\n").encode()
    return flat


def read(data: Source) -> bytes:
    return data if isinstance(data, bytes) else data.read_bytes()


def sha256(data: Source) -> str:
    if isinstance(data, bytes):
        return hashlib.sha256(data).hexdigest()
    with open(data, "rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flat", action="store_true")
    parser.add_argument("--output", type=Path, default=TASK_ROOT / "experiment" / "dist")
    args = parser.parse_args()
    content = collect()
    if args.flat:
        content = flatten(content)
    slug = re.search(r'^name = "abundant/([^"]+)"', read(content["task.toml"]).decode(), flags=re.M).group(1)
    hashes = {name: sha256(data) for name, data in content.items()}
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    staging = args.output.resolve() / ("flat" if args.flat else "bundles") / digest[:12] / slug
    if staging.exists():
        shutil.rmtree(staging)
    size = 0
    for name, data in content.items():
        target = staging / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            target.write_bytes(data)
        else:
            shutil.copyfile(data, target)
        size += target.stat().st_size
        if name.endswith(EXECUTABLE):
            target.chmod(0o755)
    print(json.dumps({"task_path": str(staging), "content_sha256": digest, "files": len(content), "bytes": size}, indent=2))


if __name__ == "__main__":
    main()
