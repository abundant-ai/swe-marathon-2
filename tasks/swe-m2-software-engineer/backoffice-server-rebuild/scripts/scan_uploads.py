"""Find hidden scenario inputs or answers that the candidate's image also receives.

usage: scan_uploads.py BUNDLE

BUNDLE is a packaged task (scripts/package_step.py), with or without the steps wrapper; everything
under BUNDLE/environment is what the candidate's image is built from. Each step's private scenarios
are read once, one scenario at a time, and every upload in them is compared with those files: a
base64 string in a JSON request body (decoded as the server decodes it), a long text in one, a raw
`body_file` from the private media, or a media file put into a JSON body (`body_insert`). So is every
recorded file answer. Files are hashed in chunks; none is held whole unless its first bytes match. Prints a JSON report and
exits 1 when the candidate receives an upload, a cut-short upload of at least PREFIX bytes (the start
of a file it has), or a file answer, or when a scenario names a private file that is missing.
"""

from __future__ import annotations

import base64
import binascii
import gzip
import hashlib
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

PREFIX = 64  # an upload this long that is the start of a shipped file is that file cut short
WHITESPACE = json.decoder.WHITESPACE


def scenarios(text: str) -> Iterator[dict[str, Any]]:
    """The scenarios of a corpus document, decoded one at a time; the whole list would need many times the memory."""
    decoder = json.JSONDecoder()

    def skip(index: int) -> int:
        return WHITESPACE.match(text, index).end()

    def expect(index: int, char: str) -> int:
        index = skip(index)
        if text[index:index + 1] != char:
            raise ValueError(f"expected {char!r} at offset {index}")
        return skip(index + 1)

    index = expect(0, "{")
    while text[index:index + 1] != "}":
        key, index = decoder.raw_decode(text, index)
        index = expect(index, ":")
        if key != "scenarios":
            _, index = decoder.raw_decode(text, index)
        else:
            index = expect(index, "[")
            while text[index:index + 1] != "]":
                scenario, index = decoder.raw_decode(text, index)
                yield scenario
                index = skip(index)
                if text[index:index + 1] == ",":
                    index = skip(index + 1)
            index += 1
        index = skip(index)
        if text[index:index + 1] == ",":
            index = skip(index + 1)


def strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)


def payloads(body: Any) -> Iterator[tuple[str, bytes]]:
    """What a JSON request body can carry as a file: base64 strings, decoded strictly as the server does, and long texts."""
    for text in strings(body):
        if len(text) >= 16:
            try:
                yield "base64", base64.b64decode(text, validate=True)
            except (binascii.Error, ValueError):
                pass
        if len(text) >= PREFIX:
            yield "text", text.encode()


def digest(path: Path) -> tuple[str, bytes, int]:
    """A file's SHA-256, first PREFIX bytes and size, read in chunks: the media is a couple of hundred megabytes."""
    hashed, head = hashlib.sha256(), b""
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            if len(head) < PREFIX:
                head += chunk[:PREFIX - len(head)]
            hashed.update(chunk)
    return hashed.hexdigest(), head, path.stat().st_size


class Shipped:
    """Every file under BUNDLE/environment, by SHA-256 and by its first PREFIX bytes (the files are read again only to
    compare a prefix)."""

    def __init__(self, bundle: Path) -> None:
        self.count = 0
        self.by_digest: dict[str, str] = {}
        self.by_head: dict[bytes, list[tuple[str, Path, int]]] = {}
        for path in sorted((bundle / "environment").rglob("*")):
            if path.is_file():
                self.count += 1
                name = path.relative_to(bundle).as_posix()
                sha, head, size = digest(path)
                self.by_digest.setdefault(sha, name)
                if size >= PREFIX:
                    self.by_head.setdefault(head, []).append((name, path, size))

    def find(self, data: bytes) -> tuple[str, str] | None:
        """("equal" or "prefix", the shipped file) when the candidate has these bytes."""
        name = self.by_digest.get(hashlib.sha256(data).hexdigest())
        if name is not None and data:
            return "equal", name
        if len(data) >= PREFIX:
            for name, path, size in self.by_head.get(data[:PREFIX], []):
                if size >= len(data):
                    with open(path, "rb") as file:
                        if file.read(len(data)) == data:
                            return "prefix", name
        return None

    def find_file(self, path: Path, known: tuple[str, bytes, int]) -> tuple[str, str] | None:
        """The same for a file of the private media, read in full only when its first bytes match a shipped file's."""
        sha, head, size = known
        name = self.by_digest.get(sha)
        if name is not None and size:
            return "equal", name
        if size >= PREFIX and any(shipped_size >= size for _, _, shipped_size in self.by_head.get(head, [])):
            return self.find(path.read_bytes())
        return None


def scan(bundle: Path) -> dict[str, Any]:
    shipped = Shipped(bundle)
    report: dict[str, Any] = {"shipped_files": shipped.count, "corpora": 0, "scenarios": 0, "steps": 0,
                              "base64": 0, "text": 0, "body_file": 0, "body_insert": 0, "file_answers": 0, "missing": [], "leaks": []}
    for corpus in sorted(bundle.glob("**/tests/private/scenarios.json.gz")):
        report["corpora"] += 1
        media, read = corpus.parent / "media", {}
        for scenario in scenarios(gzip.decompress(corpus.read_bytes()).decode("utf-8")):
            report["scenarios"] += 1
            for number, step in enumerate(scenario["steps"], start=1):
                report["steps"] += 1
                where = f"{scenario['id']} step {number} ({step['method']} {step['path']})"
                for kind, data in payloads(step.get("body")):
                    report[kind] += 1
                    hit = shipped.find(data)
                    if hit:
                        report["leaks"].append({"what": f"{kind} upload ({hit[0]})", "where": where, "file": hit[1]})
                # a raw upload, or a file put into a JSON body (as base64 or as text): the media file itself is what is sent
                kind, name = ("body_insert", step["body_insert"]["file"]) if "body_insert" in step else ("body_file", step.get("body_file"))
                if name is not None:
                    if name not in read:
                        path = media / name
                        read[name] = digest(path) if path.is_file() else None
                    if read[name] is None:
                        report["missing"].append(f"{where}: {name}")
                    else:
                        report[kind] += 1
                        hit = shipped.find_file(media / name, read[name])
                        if hit:
                            report["leaks"].append({"what": f"{kind} upload ({hit[0]})", "where": where, "file": hit[1]})
                answer = step.get("json")
                if isinstance(answer, dict) and set(answer) == {"binary"}:
                    report["file_answers"] += 1
                    name = shipped.by_digest.get(str(answer["binary"].get("sha256")))
                    if name is not None:
                        report["leaks"].append({"what": "file answer", "where": where, "file": name})
    return report


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    report = scan(Path(sys.argv[1]))
    print(json.dumps(report, indent=1))
    return 1 if report["leaks"] or report["missing"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
