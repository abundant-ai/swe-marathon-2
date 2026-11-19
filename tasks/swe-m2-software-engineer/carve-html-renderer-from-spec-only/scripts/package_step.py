"""Build a self-contained Harbor bundle from sources, the pinned upstream files and the private cases.

usage: package_step.py [--flat] [--output DIR]

--flat writes the same files without the steps wrapper, under the task name with `-single`
appended, for harnesses that accept only tasks without declared steps.

Needs, all made beforehand and none committed:
- experiment/original/carve-linux.tar.gz and LICENSE: carve-rs 0.1.14's static Linux release
  archive and its licence (scripts/setup_tools.py). The archive goes, as released, into the
  verifier's build context (its builder stage records the answers with it, and the final image
  keeps nothing of it) and into the reference solution, each beside common/original/install.py
  and a build.txt naming the pinned sha256s.
- steps/01-implement-renderer/tests/private/cases.json: the private cases (scripts/make_cases.py).
- the spec checkout at the pinned commit (../.cache-src/carve next to this repository), whose
  specification and documentation pages go into the agent's image (carve_text.specification
  and carve_text.documentation).

Packaging stops if a private case is a source the shipped specification or documentation shows,
or a near-copy of one (make_cases.leaks), or if the archive or its binary is not the pinned build.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import carve_text as ct  # noqa: E402

TASK_ROOT = Path(__file__).resolve().parent.parent
STEP = "steps/01-implement-renderer"
HIDDEN = TASK_ROOT / STEP / "tests" / "private" / "cases.json"
PROBES = TASK_ROOT / STEP / "tests" / "private" / "probes.json"
KEPT_IDS = TASK_ROOT / "experiment" / "kept_ids.txt"
ORIGINAL = TASK_ROOT / "experiment" / "original"
INSTALLER = TASK_ROOT / "common" / "original" / "install.py"
UPSTREAM_BUILDS = TASK_ROOT / STEP / "tests" / "verifier" / "upstream_builds.json"
EXCLUDED = {"__pycache__", ".pytest_cache", ".DS_Store", "experiment"}


def build_facts() -> bytes:
    """build.txt: what the original is, read by install.py and recording.py."""
    lines = [
        f"version carve-rs {ct.CARVE_RS_TAG}",
        f"commit {ct.CARVE_RS_COMMIT}",
        f"spec {ct.SPEC_TAG} {ct.SPEC_COMMIT}",
        f"archive {ct.LINUX_ARCHIVE}",
        f"archive_sha256 {ct.LINUX_ARCHIVE_SHA256}",
        f"sha256 {ct.LINUX_BINARY_SHA256}",
        "link static-pie, x86_64-unknown-linux-musl",
    ]
    return ("\n".join(lines) + "\n").encode()


def original() -> tuple[bytes, bytes]:
    """The release archive and the licence, after checking the archive and its binary against the
    pins."""
    archive, licence = ORIGINAL / "carve-linux.tar.gz", ORIGINAL / "LICENSE"
    if not archive.is_file() or not licence.is_file():
        raise ValueError("Fetch the original first (scripts/setup_tools.py); experiment/original is incomplete")
    data = archive.read_bytes()
    if hashlib.sha256(data).hexdigest() != ct.LINUX_ARCHIVE_SHA256:
        raise ValueError("experiment/original/carve-linux.tar.gz is not the pinned release archive")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        binaries = [tar.extractfile(m).read() for m in tar.getmembers() if m.isfile() and m.name.rsplit("/", 1)[-1] == "carve"]
    if len(binaries) != 1 or hashlib.sha256(binaries[0]).hexdigest() != ct.LINUX_BINARY_SHA256:
        raise ValueError("the archive's carve binary is not the pinned build")
    return data, licence.read_bytes()


def collect() -> dict[str, bytes]:
    """Every file of the bundle, by its path in the bundle."""
    if not HIDDEN.is_file() or not PROBES.is_file():
        raise ValueError("Generate the cases first (scripts/make_cases.py); the private cases.json or probes.json is missing")
    content: dict[str, bytes] = {"task.toml": (TASK_ROOT / "task.toml").read_bytes()}
    for directory in ("environment", STEP):
        for path in (TASK_ROOT / directory).rglob("*"):
            relative = path.relative_to(TASK_ROOT)
            if path.is_file() and not EXCLUDED.intersection(relative.parts) and path.suffix != ".pyc":
                content[relative.as_posix()] = path.read_bytes()
    spec, docs = ct.specification(), ct.documentation()
    import make_cases  # noqa: PLC0415

    skeletons, blob = ct.leak_index({**{f"spec/{k}": v for k, v in spec.items()}, **{f"docs/{k}": v for k, v in docs.items()}})
    cases = json.loads(HIDDEN.read_text(encoding="utf-8"))["cases"]
    found = [case["id"] for case in cases if case["kind"] != "cli"
             and make_cases.leaks((list(case["files"].values()) or [case["stdin"]])[0], skeletons, blob)]
    if found:
        raise ValueError(f"{len(found)} private cases are sources the shipped files show: {', '.join(found[:20])}")
    for name, text in spec.items():
        content[f"environment/spec/{name}"] = text.encode("utf-8")
    for name, text in docs.items():
        content[f"environment/docs/{name}"] = text.encode("utf-8")
    archive, licence = original()
    facts, installer = build_facts(), INSTALLER.read_bytes()
    for place in (f"{STEP}/tests/original", f"{STEP}/solution"):
        content[f"{place}/carve.tar.gz"] = archive
        content[f"{place}/build.txt"] = facts
        content[f"{place}/install.py"] = installer
    # The accepted kept-ids sha256 (the first Linux oracle build's value), which the verifier image
    # build asserts so the denominator cannot drift; empty until that build sets it.
    kept_ids = KEPT_IDS.read_text(encoding="utf-8").strip() if KEPT_IDS.is_file() else ""
    content[f"{STEP}/tests/original/kept_ids.txt"] = (kept_ids + "\n").encode()
    content[f"{STEP}/solution/LICENSE"] = licence
    # What install.py --blank overwrites in the reference solution's copy: the text the verifier's
    # refusal of published builds looks for (tests/verifier/upstream_builds.json), and nothing else.
    strings = json.loads(UPSTREAM_BUILDS.read_text(encoding="utf-8"))["strings"]
    content[f"{STEP}/solution/blank.json"] = (json.dumps({"strings": strings}, indent=1) + "\n").encode()
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
        if name.endswith((".sh", "prepare-delivery", "reserve-delivery-room")):
            target.chmod(0o755)
    size = sum(len(data) for data in content.values())
    print(json.dumps({"task_path": str(staging), "content_sha256": digest, "files": len(content), "bytes": size}, indent=2))


if __name__ == "__main__":
    main()
