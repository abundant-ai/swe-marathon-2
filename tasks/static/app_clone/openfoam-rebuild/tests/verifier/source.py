"""Prepare a fresh build and identify entire upstream implementation files."""

from __future__ import annotations

import hashlib
import re
import stat
from pathlib import Path

_FINGERPRINTS = Path(__file__).with_name("upstream.sha256")
_CPP = {
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".h",
    ".hh",
    ".hpp",
    ".hxx",
    ".ipp",
    ".inl",
    ".l",
    ".y",
}
# The reference solution is OpenFOAM's own source. It carries a key made for each bundle by
# scripts/package.sh; only the key's digest is here, so a submission cannot claim it.
_REFERENCE = Path(__file__).with_name("reference.sha256")
_TOKENS = re.compile(
    rb'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[\w]+|[^\s]', re.DOTALL
)


def fingerprint(source: bytes) -> str | None:
    """Fingerprint a substantive C++ implementation independently of its comments and spacing.

    Args:
        source: Complete file contents from the upstream indexer or a submission.

    Returns:
        A SHA-256 digest of the token stream, or None for short or non-text files.
    """
    if b"\0" in source:
        return None
    tokens = [t for t in _TOKENS.findall(source) if not t.startswith((b"//", b"/*"))]
    if len(tokens) < 256:
        return None
    return hashlib.sha256(b"\0".join(tokens)).hexdigest()


def prepare_source(root: Path) -> str | None:
    """Remove native build products and screen the unpacked source before compile.sh.

    Args:
        root: Delivered source tree, before the build user can run any command.

    Returns:
        A build rejection for copied upstream code or unsupported special files.
        Otherwise returns None. Regular scripts and in-tree source links are retained.
    """
    upstream = _upstream(root)
    for path in root.rglob("*"):
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            try:
                target = path.resolve()
            except (OSError, RuntimeError):
                return f"invalid source link: {path.relative_to(root)}"
            if not target.is_relative_to(root):
                return f"source link leaves submission: {path.relative_to(root)}"
            continue
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            return f"expected a regular source file: {path.relative_to(root)}"
        with path.open("rb") as stream:
            magic = stream.read(8)
            if magic.startswith(
                (b"\x7fELF", b"!<arch>\n", b"!<thin>\n", b"BC\xc0\xde", b"\0asm")
            ):
                path.unlink()
            elif _copied(path, magic + stream.read(), upstream):
                return f"source matches an upstream OpenFOAM implementation: {path.relative_to(root)}"
    return None


def copied_source(root: Path) -> str | None:
    """Screen the tree again after compile.sh, which may have unpacked or written source.

    Returns:
        A build rejection for copied upstream code, otherwise None.
    """
    upstream = _upstream(root)
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink() and _copied(path, None, upstream):
            return f"source matches an upstream OpenFOAM implementation: {path.relative_to(root)}"
    return None


def _upstream(root: Path) -> set[str]:
    if _is_reference(root):
        return set()
    return set(_FINGERPRINTS.read_text().splitlines())


def _copied(path: Path, content: bytes | None, upstream: set[str]) -> bool:
    if not upstream or path.suffix.lower() not in _CPP:
        return False
    return fingerprint(path.read_bytes() if content is None else content) in upstream


def _is_reference(root: Path) -> bool:
    """The submission is the reference solution of this bundle."""
    key = root / ".reference-key"
    if not _REFERENCE.is_file() or key.is_symlink() or not key.is_file():
        return False
    digest = hashlib.sha256(key.read_bytes()).hexdigest()
    return digest == _REFERENCE.read_text().strip()
