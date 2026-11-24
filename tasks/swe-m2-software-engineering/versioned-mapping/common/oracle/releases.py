"""Publish immutable map blobs and atomically move an active version pointer."""

from contextlib import contextmanager
import fcntl
import hashlib
import os
from pathlib import Path
import re
import tempfile
from typing import Iterator

from .maps import FREE, OCCUPIED, json_bytes, map_document, parse_cell, read_map, read_object, write_bytes


def fingerprint(content: bytes) -> str:
    """Identify a snapshot by its exact bytes."""
    return hashlib.sha256(content).hexdigest()


def version_id(value: str) -> str:
    """Validate a user-supplied ID before using it as a filename."""
    if re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("Expected a lowercase SHA-256 version ID")
    return value


def blob_path(store: Path, version: str) -> Path:
    """Resolve a validated ID into its immutable object path."""
    return store / "objects" / version_id(version)


def read_blob(store: Path, version: str) -> bytes:
    """Read a snapshot and reject damaged content-addressed storage."""
    payload = blob_path(store, version).read_bytes()
    if fingerprint(payload) != version:
        raise ValueError("Snapshot hash does not match its version")
    return payload


def active(store: Path) -> str:
    """Read one complete active version pointer."""
    return version_id((store / "active").read_text(encoding="ascii").strip())


@contextmanager
def exclusive(store: Path) -> Iterator[None]:
    """Serialize mutations using a lock already created by init."""
    with (store / "lock").open("rb") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def init(store: Path, map_path: Path) -> dict[str, str]:
    """Publish a brand-new store only after its original version is complete."""
    read_map(map_path)
    payload = map_path.read_bytes()
    version = fingerprint(payload)
    if os.path.lexists(store):
        raise ValueError("The store already exists")
    with tempfile.TemporaryDirectory(dir=store.parent, prefix=".map-store-") as temporary:
        staged = Path(temporary) / "store"
        (staged / "objects").mkdir(parents=True)
        blob_path(staged, version).write_bytes(payload)
        (staged / "active").write_text(version + "\n", encoding="ascii")
        (staged / "lock").touch()
        if os.path.lexists(store):
            raise ValueError("The store already exists")
        staged.rename(store)
    return {"version": version, "active_version": version}


def patched_bytes(store: Path, base: str, patch_path: Path) -> bytes:
    """Validate a proposal against a pinned map and materialize its new state."""
    old_payload = read_blob(store, base)
    grid, cells = read_map(blob_path(store, base))
    patch = read_object(patch_path)
    changes = patch.get("changes")
    if type(patch.get("schema_version")) is not int or patch["schema_version"] != 1:
        raise ValueError("Unsupported patch version")
    if patch.get("base_sha256") != base or not isinstance(changes, list):
        raise ValueError("Patch must target the supplied base")
    if not changes:
        return old_payload
    seen = set()
    for update in changes:
        if not isinstance(update, dict):
            raise ValueError("Malformed patch entry")
        cell = parse_cell(update.get("cell"), grid)
        before, after = cells.get(cell, "unknown"), update.get("to")
        if cell in seen or update.get("from") != before or after not in (FREE, OCCUPIED) or after == before:
            raise ValueError("Duplicate, stale or invalid patch entry")
        support = update.get("support")
        if (not isinstance(support, list) or any(not isinstance(name, str) or not name for name in support)
                or len(set(support)) < 2):
            raise ValueError("A change needs evidence from two supporting visits")
        seen.add(cell)
        cells[cell] = after
    return json_bytes(map_document(grid, cells))


def publish(store: Path, base: str, patch: Path) -> dict[str, str]:
    """Publish an immutable candidate without changing active localization."""
    with exclusive(store):
        current = active(store)
        payload = patched_bytes(store, base, patch)
        version = fingerprint(payload)
        destination = blob_path(store, version)
        if not destination.exists():
            write_bytes(destination, payload)
        else:
            read_blob(store, version)
    return {"version": version, "active_version": current}


def activate(store: Path, version: str, expect_active: str) -> dict[str, str]:
    """Move the active pointer only when the caller's prior state matches."""
    with exclusive(store):
        if active(store) != expect_active:
            raise ValueError("Active version changed")
        read_blob(store, version)
        write_bytes(store / "active", (version + "\n").encode("ascii"))
    return {"version": version, "active_version": version}


def snapshot(store: Path, version: str, output: Path) -> None:
    """Export the chosen immutable snapshot or one atomic active resolution."""
    selected = active(store) if version == "active" else version
    write_bytes(output, read_blob(store, selected))
