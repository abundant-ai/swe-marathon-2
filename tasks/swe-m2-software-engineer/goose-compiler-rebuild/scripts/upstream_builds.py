"""Record the sha256 of every build of Goose that upstream publishes, for the verifier's refusal.

usage: upstream_builds.py [--download-dir DIR] [--offline]

Downloads every asset of every GitHub release of aardappel/goose (the pinned commit, 745901f, is
tagged by none of them; every published compiler is an earlier version, and would still answer
most cases) and every bottle of Homebrew's goose-lang formula (Linux ones among them), into
experiment/upstream-builds (Git-ignored; nothing downloaded is committed or run), and writes
steps/01-rebuild-compiler/tests/verifier/upstream_builds.json: the sha256 of each archive as
published and of the compiler executable inside it (`goose` or `goose.exe`; never TinyCC's
objects, which the task's own build of the compiler also produces), with where each came from.
The verifier refuses a submission holding any file with one of these hashes: a published build of
the original, fetched rather than written. The file also records whether each published compiler
holds the lines of upstream's help text the verifier refuses in any delivered executable
(`verify.UNHARDENED_USAGE`), which the hardened build lacks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
import urllib.request
import zipfile
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parent.parent
OUT = TASK_ROOT / "steps" / "01-rebuild-compiler" / "tests" / "verifier" / "upstream_builds.json"
RELEASES = "https://api.github.com/repos/aardappel/goose/releases?per_page=100"
BREW = "https://formulae.brew.sh/api/formula/goose-lang.json"
BREW_TOKEN = "QQ=="  # Homebrew's anonymous bearer token for its bottles on ghcr.io
COMPILERS = ("goose", "goose.exe")
MAGICS = (b"\x7fELF", b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"MZ\x90\x00", b"MZ")  # ELF, Mach-O 64-bit, universal, PE
USAGE = (b"goose help c covers writing the C yourself (goose -o out.c)",
         b"Writes the program's C, for a build of your own or a C host")
HEADERS = {"User-Agent": "task-build-hashes", "Accept": "application/vnd.github+json"}


def fetch(url: str, target: Path, headers: dict | None = None) -> Path:
    """`url` saved at `target` (kept from an earlier run when present), streamed in 1 MB pieces."""
    if not target.is_file():
        request = urllib.request.Request(url, headers={"User-Agent": "task-build-hashes", **(headers or {})})
        with urllib.request.urlopen(request, timeout=300) as response, open(target.with_suffix(target.suffix + ".part"), "wb") as handle:
            while chunk := response.read(1 << 20):
                handle.write(chunk)
        target.with_suffix(target.suffix + ".part").rename(target)
    return target


def api(url: str) -> object:
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as response:
        return json.load(response)


def sha256_of(stream) -> tuple[str, int, dict[str, int]]:
    """The sha256 of everything `stream` yields, read in 1 MB pieces, its length, and how often each
    line of USAGE occurs in it (counted across piece boundaries)."""
    digest, size, tail, counts = hashlib.sha256(), 0, b"", {text.decode(): 0 for text in USAGE}
    overlap = max(len(text) for text in USAGE)
    while chunk := stream.read(1 << 20):
        digest.update(chunk)
        size += len(chunk)
        joined = tail + chunk
        for text in USAGE:
            counts[text.decode()] += joined.count(text) - tail.count(text)
        tail = joined[-overlap:]
    return digest.hexdigest(), size, counts


def compilers_in(path: Path):
    """(member name, open stream) for each compiler executable inside the archive at `path`."""
    if path.name.endswith(".zip"):
        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                if member.filename.rsplit("/", 1)[-1] in COMPILERS and not member.is_dir():
                    with archive.open(member) as stream:
                        if stream.read(4).startswith(MAGICS):
                            with archive.open(member) as again:
                                yield member.filename, again
        return
    with tarfile.open(path, "r:*") as archive:
        for member in archive:
            if member.isfile() and member.name.rsplit("/", 1)[-1] in COMPILERS:
                stream = archive.extractfile(member)
                head = stream.read(4)
                if head.startswith(MAGICS):
                    yield member.name, archive.extractfile(member)


def record(path: Path, source: str, expected: str | None, builds: list, notes: list) -> None:
    """The archive's own hash (checked against `expected` where upstream states one) and its compilers'."""
    with open(path, "rb") as handle:
        digest, size, _ = sha256_of(handle)
    if expected and digest != expected:
        raise SystemExit(f"{path.name}: sha256 {digest} is not the published {expected}")
    builds.append({"sha256": digest, "size": size, "source": source})
    found = 0
    for name, stream in compilers_in(path):
        digest, size, counts = sha256_of(stream)
        builds.append({"sha256": digest, "size": size, "source": f"{source}: {name}", "usage_text": counts})
        found += 1
        missing = [text for text, count in counts.items() if not count]
        if missing:
            notes.append(f"{source}: {name} lacks the usage text {missing}")
    if not found:
        notes.append(f"{source}: no compiler executable found inside")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-dir", type=Path, default=TASK_ROOT / "experiment" / "upstream-builds")
    parser.add_argument("--offline", action="store_true", help="hash what an earlier run downloaded; fetch nothing")
    args = parser.parse_args()
    args.download_dir.mkdir(parents=True, exist_ok=True)
    builds, notes, sources = [], [], []
    index = args.download_dir / "index.json"
    if args.offline:
        listed = json.loads(index.read_text())
    else:
        listed = {"releases": [], "bottles": []}
        for release in api(RELEASES):
            for asset in release["assets"]:
                digest = (asset.get("digest") or "").removeprefix("sha256:") or None
                listed["releases"].append({"tag": release["tag_name"], "name": asset["name"], "url": asset["browser_download_url"],
                                           "sha256": digest, "published_at": release["published_at"]})
        formula = api(BREW)
        for tag, bottle in formula["bottle"]["stable"]["files"].items():
            listed["bottles"].append({"version": formula["versions"]["stable"], "tag": tag, "url": bottle["url"],
                                      "sha256": bottle["sha256"]})
        index.write_text(json.dumps(listed, indent=1) + "\n")
    for asset in listed["releases"]:
        source = f"GitHub release {asset['tag']}: {asset['name']}"
        path = fetch(asset["url"], args.download_dir / asset["name"]) if not args.offline else args.download_dir / asset["name"]
        record(path, source, asset.get("sha256"), builds, notes)
        sources.append(source)
    for bottle in listed["bottles"]:
        name = f"goose-lang-{bottle['version']}.{bottle['tag']}.bottle.tar.gz"
        source = f"Homebrew bottle goose-lang {bottle['version']} {bottle['tag']}: {name}"
        path = (fetch(bottle["url"], args.download_dir / name, {"Authorization": f"Bearer {BREW_TOKEN}"}) if not args.offline
                else args.download_dir / name)
        record(path, source, bottle["sha256"], builds, notes)
        sources.append(source)
    distinct = {build["sha256"] for build in builds}
    OUT.write_text(json.dumps({"builds": builds, "usage_text": [text.decode() for text in USAGE], "notes": notes},
                              indent=1, sort_keys=True) + "\n")
    print(f"{len(sources)} published archives, {len(builds)} files, {len(distinct)} distinct hashes recorded in "
          f"{OUT.relative_to(TASK_ROOT)}; {len(notes)} note(s)")
    for note in notes:
        print(f"  {note}")


if __name__ == "__main__":
    main()
