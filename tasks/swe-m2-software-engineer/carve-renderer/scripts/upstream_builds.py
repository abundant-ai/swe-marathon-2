"""Record what of the original upstream publishes ready to run, for the verifier's refusal of fetched builds.

usage: upstream_builds.py [--out PATH]

A process the agent leaves behind gets public internet for a while after its session ends, before
its delivery is collected (harbor-lh ops/swe-marathon-v2/PLATFORM_EGRESS_WINDOW.md); it could drop
a published build of the original into /app/rebuild. This lists, for the verifier
(steps/01-implement-renderer/tests/verifier/upstream_builds.json):

- `sha256`: every asset of every carve-rs GitHub release (the digests GitHub reports), the `carve`
  binary inside each x86-64 Linux archive (downloaded), every x86-64 Linux wheel of `carve-lang` on
  PyPI (carve-py, a PyO3 binding over carve-rs) and each file inside it, and every version of the
  carve-go module (a Go wrapper over carve-rs compiled to WebAssembly) with each `.wasm` inside it.
- `strings`: text that carve-rs's command line or its library holds in every one of those builds
  (the native binary, the Python extension and the WebAssembly module) and that an HTML renderer
  written from the specification has no reason to hold: carve-rs's own usage text and messages of
  the parts out of scope (importers, migration, lint, the other output targets), none of them in
  the shipped specification or documentation, nor in a plain Rust build (the Rust tools here).
  The verifier refuses a delivered file that holds two of them.

Downloads go to experiment/upstream/ (one directory per source), are checked against the digests
their registries publish where there is one, and are never run.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
import tarfile
import urllib.request
import zipfile
from pathlib import Path

import carve_text as ct

TASK_ROOT = Path(__file__).resolve().parent.parent
OUT = TASK_ROOT / "steps" / "01-implement-renderer" / "tests" / "verifier" / "upstream_builds.json"
CACHE = TASK_ROOT / "experiment" / "upstream"
PYPI = "https://pypi.org/pypi/carve-lang/json"
GOPROXY = "https://proxy.golang.org/github.com/markup-carve/carve-go/@v/"
LINUX = ("x86_64-unknown-linux-gnu", "x86_64-unknown-linux-musl")
# Source files of carve-rs's parts out of scope: their message text appears in no HTML renderer.
OUT_OF_SCOPE_SOURCES = ("src/main.rs", "src/lint", "src/lint.rs", "src/html_import", "src/html_import.rs", "src/markdown_import",
                        "src/markdown_import.rs", "src/djot_migrate", "src/djot_migrate.rs", "src/bbcode_migrate.rs",
                        "src/migrate_directory.rs", "src/migration.rs", "src/render_ansi.rs", "src/render_plain.rs",
                        "src/render_markdown.rs", "src/render_carve", "src/render_carve.rs", "src/ast_merge.rs", "src/stamp.rs")
MIN_STRING = 24
# Phrases a renderer's own warnings, or its patterns, could share: never used.
GENERIC = re.compile(r"\\|\(\?|has no matching definition|has an empty destination|matches no link definition|opens at line|"
                     r"adds no block")


def fetch(url: str, place: Path) -> bytes:
    """`url`'s bytes, cached at `place`."""
    if place.is_file():
        return place.read_bytes()
    data = urllib.request.urlopen(url, timeout=300).read()
    place.parent.mkdir(parents=True, exist_ok=True)
    place.write_bytes(data)
    return data


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def strings_of(data: bytes, least: int = MIN_STRING) -> set[str]:
    """The printable ASCII runs of `data` at least `least` long."""
    return {match.decode() for match in re.findall(rb"[\x20-\x7e]{%d,}" % least, data)}


def carve_rs(found: dict[str, str]) -> bytes:
    """Record every release asset's digest and the binary of each x86-64 Linux archive; the
    pinned 0.1.14 musl binary's bytes."""
    releases = json.loads(subprocess.run(["gh", "api", "--paginate", "repos/markup-carve/carve-rs/releases?per_page=100"],
                                         check=True, capture_output=True, timeout=300).stdout)
    pinned = b""
    for release in releases:
        for asset in release["assets"]:
            digest = (asset.get("digest") or "").removeprefix("sha256:")
            if digest:
                found[digest] = f"carve-rs {release['tag_name']} release asset {asset['name']}"
            if not asset["name"].endswith(".tar.gz") or not any(target in asset["name"] for target in LINUX):
                continue
            data = fetch(asset["browser_download_url"], CACHE / "carve-rs" / release["tag_name"] / asset["name"])
            if digest and sha256(data) != digest:
                raise SystemExit(f"{asset['name']}: not the digest GitHub reports")
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
                for member in archive.getmembers():
                    if member.isfile() and member.name.rsplit("/", 1)[-1] == "carve":
                        binary = archive.extractfile(member).read()
                        found[sha256(binary)] = f"carve-rs {release['tag_name']} binary from {asset['name']}"
                        if asset["name"] == ct.LINUX_ARCHIVE:
                            pinned = binary
    if sha256(pinned) != ct.LINUX_BINARY_SHA256:
        raise SystemExit("the pinned release binary was not among the assets")
    return pinned


def carve_py(found: dict[str, str]) -> bytes:
    """Record every x86-64 Linux wheel of carve-lang and each file in it; the newest wheel's
    extension module."""
    index = json.loads(fetch(PYPI, CACHE / "carve-py" / "index.json"))
    newest = b""
    for version, files in sorted(index["releases"].items()):
        for item in files:
            name = item["filename"]
            if not (name.endswith(".whl") and "x86_64" in name and ("manylinux" in name or "musllinux" in name)):
                continue
            data = fetch(item["url"], CACHE / "carve-py" / version / name)
            if sha256(data) != item["digests"]["sha256"]:
                raise SystemExit(f"{name}: not the digest PyPI reports")
            found[sha256(data)] = f"carve-lang {version} wheel {name}"
            with zipfile.ZipFile(io.BytesIO(data)) as wheel:
                for member in wheel.infolist():
                    if member.file_size >= 4096:
                        body = wheel.read(member)
                        found[sha256(body)] = f"carve-lang {version} {member.filename} from {name}"
                        if member.filename.endswith(".so") and version == index["info"]["version"]:
                            newest = body
    return newest


def carve_go(found: dict[str, str]) -> bytes:
    """Record every version of the carve-go module and each .wasm inside it; the newest .wasm."""
    versions = sorted(fetch(GOPROXY + "list", CACHE / "carve-go" / "list.txt").decode().split(),
                      key=lambda v: [int(part) for part in re.findall(r"\d+", v)])
    newest = b""
    for version in versions:
        data = fetch(GOPROXY + f"{version}.zip", CACHE / "carve-go" / f"{version}.zip")
        found[sha256(data)] = f"carve-go {version} module zip"
        with zipfile.ZipFile(io.BytesIO(data)) as module:
            for member in module.infolist():
                if member.filename.endswith(".wasm"):
                    body = module.read(member)
                    found[sha256(body)] = f"carve-go {version} {member.filename.rsplit('/', 1)[-1]}"
                    newest = body
    return newest


def sources(prefixes: tuple[str, ...]) -> str:
    """carve-rs's Rust sources under `prefixes` at the pinned commit, joined."""
    return "\n".join(ct.git_text(ct.RS_CHECKOUT, path, ct.CARVE_RS_COMMIT)
                     for prefix in prefixes for path in ct.git_files(ct.RS_CHECKOUT, prefix, ct.CARVE_RS_COMMIT)
                     if path.endswith(".rs"))


def distinctive(builds: list[bytes], only_first: bool = False, prefixes: tuple[str, ...] = OUT_OF_SCOPE_SOURCES,
                most: int = 40) -> list[str]:
    """Strings every build holds (with `only_first`, the first build), that come from carve-rs's
    sources under `prefixes` at the pinned commit, and that neither the shipped text nor a plain
    Rust build holds, nor GENERIC phrases."""
    common = strings_of(builds[0]) if only_first else set.intersection(*(strings_of(build) for build in builds))
    source = sources(prefixes)
    shipped = "\n".join(list(ct.specification().values()) + list(ct.documentation().values()))
    plain = set()
    for tool in (shutil.which("cargo"), shutil.which("rustc"), shutil.which("rustup")):
        if tool:
            plain |= strings_of(Path(tool).resolve().read_bytes())
    picked = [text for text in common if text in source and text not in shipped and text not in plain
              and not re.search(r"[<>]|class=|\{\}", text) and not GENERIC.search(text)]
    return sorted(picked, key=lambda text: (-len(text), text))[:most]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    found: dict[str, str] = {}
    native = carve_rs(found)
    extension = carve_py(found)
    wasm = carve_go(found)
    strings = distinctive([native, extension, wasm])
    usage = distinctive([native], only_first=True, prefixes=("src/main.rs",), most=8)   # the command line's own text
    record = {
        "comment": "Builds of the original that upstream publishes, and text they all hold that an HTML renderer written from "
                   "the specification does not; written by scripts/upstream_builds.py.",
        "sha256": dict(sorted(found.items())),
        "strings": sorted(set(strings) | set(usage)),
        "strings_needed": 2,
    }
    args.out.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"hashes": len(found), "strings": len(record["strings"]), "sample": record["strings"][:8]}, indent=1))


if __name__ == "__main__":
    main()
