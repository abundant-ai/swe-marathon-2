"""The delivered tree as the brief's copy rules see it, walked without recursion or links.

The same file is the hand-off hook's on the working machine, which applies these rules to
/app/dogwood-rebuild before it is copied, and the grader's, which walks what arrived. Kept:
regular files, directories, and links (listed as links; the copy follows only a link to a file
inside the tree). Left out:
- pipes, sockets and devices;
- cargo's build output: `target/` at the root, and any directory holding cargo's CACHEDIR.TAG;
- a name that is not UTF-8, anything nested more than MAX_DEPTH directories deep, and any path
  longer than MAX_PATH bytes (relative to the root).

The listing of a tree is sorted by path; its digest is the SHA-256 of that listing as JSON, one
entry per line: [path, "d"], [path, "f", size, sha256] or [path, "l", target].
"""

from __future__ import annotations

import hashlib
import json
import os
import pwd
import stat
from collections.abc import Iterator
from dataclasses import dataclass

MAX_DEPTH = 32
MAX_PATH = 1000
CACHEDIR_SIGNATURE = b"Signature: 8a477f597d28d172789f06886806bc55"
HASH_CHUNK = 1 << 20


@dataclass(frozen=True)
class Entry:
    rel: str  # path below the root, `/`-separated
    kind: str  # "d", "f" or "l"
    path: bytes  # absolute path
    st: os.stat_result


@dataclass(frozen=True)
class LeftOut:
    rel: str  # path below the root, with undecodable bytes escaped
    path: bytes
    reason: str
    st: os.stat_result


def _is_build_output(path: bytes, rel: bytes) -> bool:
    if rel == b"target":
        return True
    try:
        fd = os.open(
            path + b"/CACHEDIR.TAG", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        )
    except OSError:
        return False
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return False
        return os.read(fd, len(CACHEDIR_SIGNATURE)) == CACHEDIR_SIGNATURE
    finally:
        os.close(fd)


def walk(
    root: bytes, max_depth: int = MAX_DEPTH, max_path: int = MAX_PATH
) -> Iterator[Entry | LeftOut]:
    """Every entry below `root`, kept (Entry) or left out (LeftOut); a directory that is left out
    is not entered. A directory that cannot be read is listed and not entered."""
    stack: list[tuple[bytes, bytes, int]] = [(root, b"", 0)]
    while stack:
        here, rel_here, depth = stack.pop()
        try:
            names = sorted(os.listdir(here))
        except OSError:
            continue
        below: list[tuple[bytes, bytes, int]] = []
        for name in names:
            path = here + b"/" + name
            rel = rel_here + b"/" + name if rel_here else name
            shown = rel.decode("utf-8", "backslashreplace")
            try:
                st = os.lstat(path)
            except OSError:
                continue
            is_dir = stat.S_ISDIR(st.st_mode)
            reason = None
            try:
                text = rel.decode("utf-8")
            except UnicodeDecodeError:
                text, reason = shown, "a name that is not UTF-8"
            if reason is None and depth > max_depth:
                reason = f"more than {max_depth} directories deep"
            elif reason is None and len(rel) > max_path:
                reason = f"a path longer than {max_path} bytes"
            elif reason is None and not (
                is_dir or stat.S_ISREG(st.st_mode) or stat.S_ISLNK(st.st_mode)
            ):
                reason = "a pipe, socket or device"
            elif reason is None and is_dir and _is_build_output(path, rel):
                reason = "cargo's build output"
            if reason is not None:
                yield LeftOut(text, path, reason, st)
                continue
            kind = "d" if is_dir else "l" if stat.S_ISLNK(st.st_mode) else "f"
            yield Entry(text, kind, path, st)
            if is_dir:
                below.append((path, rel, depth + 1))
        stack.extend(reversed(below))


def sha256_of(path: bytes) -> str | None:
    """The SHA-256 of a regular file, read without following a link; None if it cannot be read."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    digest = hashlib.sha256()
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        while True:
            chunk = os.read(fd, HASH_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    except OSError:
        return None
    finally:
        os.close(fd)
    return digest.hexdigest()


def listing(root: bytes) -> list[list]:
    """The kept entries of the tree at `root`, sorted by path."""
    out: list[list] = []
    for item in walk(root):
        if isinstance(item, LeftOut):
            continue
        if item.kind == "d":
            out.append([item.rel, "d"])
        elif item.kind == "f":
            out.append([item.rel, "f", item.st.st_size, sha256_of(item.path)])
        else:
            try:
                target = os.readlink(item.path).decode("utf-8", "backslashreplace")
            except OSError:
                target = None
            out.append([item.rel, "l", target])
    out.sort(key=lambda e: e[0].encode("utf-8", "surrogateescape"))
    return out


def digest(entries: list[list]) -> str:
    h = hashlib.sha256()
    for e in entries:
        h.update(
            json.dumps(e, ensure_ascii=True, separators=(",", ":")).encode() + b"\n"
        )
    return h.hexdigest()


def totals(entries: list[list]) -> tuple[int, int]:
    """(files, bytes of files) of a listing."""
    files = [e for e in entries if e[1] == "f"]
    return len(files), sum(e[2] for e in files)


def chown_tree(root: bytes, user: str) -> None:
    """Give a tree of the grader's own making, at any depth, to `user`, never following a link."""
    entry = pwd.getpwnam(user)
    ids = (entry.pw_uid, entry.pw_gid)
    os.lchown(root, *ids)
    for item in walk(root, max_depth=1 << 30, max_path=1 << 30):
        os.lchown(item.path, *ids)
