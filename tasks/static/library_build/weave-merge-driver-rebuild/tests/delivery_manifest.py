"""Check a delivered /app/driver copy against the collect hook's manifest.

The root collect hook (/usr/local/lib/weave-collect/collect) runs in the agent
container after the agent's turn.  It kills the agent user's processes, removes
what Harbor's tar transfer would reject, and writes .delivery/manifest.json.
The verifier calls check() on its copy of the tree.  The manifest tells a lost
or cut delivery apart from honest work; it is never part of the score.

    from delivery_manifest import check
    result = check("/app/driver")

The result is {"present": bool, "missing": [...], "changed": [...], "late": [...],
"notes": [...]}:

* missing: manifest files absent from the copy, or no longer regular files;
* changed: manifest files whose size or sha256 differs;
* late: the manifest's late_files (ctime after end_bound);
* present: False when there is no manifest, or when it does not parse (a note
  says which).

Paths in the lists are the manifest's "path" text.  Python 3.12, standard
library only, iterative.  No link inside the copy is followed.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat

FORMAT = "weave-delivery-manifest/1"
MANIFEST_CAP = 256 << 20
O_DIR = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
O_FILE = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC


def check(delivery_dir) -> dict:
    """Compare the tree at delivery_dir with delivery_dir/.delivery/manifest.json."""
    result: dict = {
        "present": False,
        "missing": [],
        "changed": [],
        "late": [],
        "notes": [],
    }
    notes = result["notes"]
    try:
        root_fd = os.open(
            os.fsencode(delivery_dir), os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
        )
    except OSError as exc:
        notes.append(f"delivery directory unreadable: {exc}")
        return result
    try:
        manifest = _load(root_fd, notes)
        if manifest is not None:
            result["present"] = True
            _compare(root_fd, manifest, result)
            _summarise(manifest, notes)
    except Exception as exc:  # noqa: BLE001 - check() reports, it never raises
        notes.append(f"check stopped early: {type(exc).__name__}: {exc}")
    finally:
        os.close(root_fd)
    return result


def _load(root_fd: int, notes: list) -> dict | None:
    fds: list[int] = []
    try:
        fds.append(os.open(b".delivery", O_DIR, dir_fd=root_fd))
        fds.append(os.open(b"manifest.json", O_FILE, dir_fd=fds[0]))
        st = os.fstat(fds[1])
        if not stat.S_ISREG(st.st_mode):
            notes.append("manifest is not a regular file")
            return None
        if st.st_size > MANIFEST_CAP:
            notes.append(f"manifest is larger than {MANIFEST_CAP} bytes")
            return None
        data = _read_all(fds[1])
    except FileNotFoundError:
        notes.append("no manifest at .delivery/manifest.json")
        return None
    except OSError as exc:
        notes.append(f"manifest unreadable: {exc}")
        return None
    finally:
        for fd in fds:
            os.close(fd)
    try:
        manifest = json.loads(data)
    except (ValueError, RecursionError) as exc:
        notes.append(f"manifest does not parse: {type(exc).__name__}: {exc}")
        return None
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list):
        notes.append("manifest does not parse: no list of files")
        return None
    return manifest


def _read_all(fd: int) -> bytes:
    chunks = []
    while chunk := os.read(fd, 1 << 20):
        chunks.append(chunk)
    return b"".join(chunks)


def _entry_path(entry) -> bytes | None:
    """The exact relative path of a manifest entry, or None if it is invalid."""
    if not isinstance(entry, dict):
        return None
    raw_hex = entry.get("path_hex")
    if raw_hex is not None:
        if not isinstance(raw_hex, str):
            return None
        try:
            raw = bytes.fromhex(raw_hex)
        except ValueError:
            return None
    else:
        text = entry.get("path")
        if not isinstance(text, str):
            return None
        try:
            raw = text.encode("utf-8", "surrogateescape")
        except UnicodeEncodeError:
            return None
    if b"\0" in raw or any(part in (b"", b".", b"..") for part in raw.split(b"/")):
        return None
    return raw


def _open_parent(root_fd: int, parts: tuple[bytes, ...]) -> int | None:
    """Descriptor of the directory parts names, reached without following a
    link; root_fd itself for the top level; None if it cannot be reached."""
    fd = root_fd
    try:
        for part in parts:
            nxt = os.open(part, O_DIR, dir_fd=fd)
            if fd != root_fd:
                os.close(fd)
            fd = nxt
    except OSError:
        if fd != root_fd:
            os.close(fd)
        return None
    return fd


def _sha256(dir_fd: int, name: bytes) -> str | None:
    try:
        fd = os.open(name, O_FILE, dir_fd=dir_fd)
    except OSError:
        return None
    try:
        digest = hashlib.sha256()
        while chunk := os.read(fd, 1 << 20):
            digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None
    finally:
        os.close(fd)


def _compare(root_fd: int, manifest: dict, result: dict) -> None:
    invalid = unhashed = unreadable = 0
    cached: tuple[tuple[bytes, ...] | None, int | None] = (None, None)
    try:
        for entry in manifest["files"]:
            rel = _entry_path(entry)
            size = entry.get("size") if isinstance(entry, dict) else None
            if rel is None or not isinstance(size, int) or isinstance(size, bool):
                invalid += 1
                continue
            label = entry["path"] if isinstance(entry.get("path"), str) else rel.hex()
            *parents, name = rel.split(b"/")
            key = tuple(parents)
            if key != cached[0]:
                if cached[1] is not None and cached[1] != root_fd:
                    os.close(cached[1])
                cached = (key, _open_parent(root_fd, key))
            dir_fd = cached[1]
            try:
                st = None if dir_fd is None else os.lstat(name, dir_fd=dir_fd)
            except OSError:
                st = None
            if st is None or not stat.S_ISREG(st.st_mode):
                result["missing"].append(label)
                continue
            if st.st_size != size:
                result["changed"].append(label)
                continue
            expected = entry.get("sha256")
            if not isinstance(expected, str):
                unhashed += 1
                continue
            actual = _sha256(dir_fd, name)
            if actual is None:
                unreadable += 1
            if actual != expected.lower():
                result["changed"].append(label)
    finally:
        if cached[1] is not None and cached[1] != root_fd:
            os.close(cached[1])
    late = manifest.get("late_files")
    if isinstance(late, list):
        result["late"] = [
            item if isinstance(item, str) else repr(item) for item in late
        ]
    notes = result["notes"]
    if invalid:
        notes.append(f"{invalid} manifest entries could not be read and were skipped")
    if unhashed:
        notes.append(
            f"{unhashed} files have no sha256 in the manifest; compared by size only"
        )
    if unreadable:
        notes.append(f"{unreadable} files could not be read here; counted as changed")


def _summarise(manifest: dict, notes: list) -> None:
    if manifest.get("format") != FORMAT:
        notes.append(f"unexpected manifest format {manifest.get('format')!r}")
    errors = manifest.get("errors")
    if isinstance(errors, list) and errors:
        notes.append(
            f"collect hook recorded {len(errors)} error(s); first: {errors[0]}"
        )
    processes = manifest.get("processes")
    if isinstance(processes, list) and processes:
        alive = sum(1 for p in processes if isinstance(p, dict) and p.get("alive"))
        notes.append(
            f"{len(processes)} non-root process(es) found at collection, {alive} alive "
            "(see kill_rounds)"
        )
    remaining = manifest.get("remaining_processes")
    if isinstance(remaining, list) and remaining:
        notes.append(
            f"{len(remaining)} non-root process(es) were still alive after the kill rounds"
        )
    egress = manifest.get("egress")
    if isinstance(egress, dict) and egress.get("open"):
        hosts = egress.get("hosts") if isinstance(egress.get("hosts"), dict) else {}
        open_hosts = [
            h
            for h, v in hosts.items()
            if isinstance(v, dict) and v.get("state") == "open"
        ]
        notes.append("public egress was open at collection: " + ", ".join(open_hosts))
    counts = manifest.get("removed_counts")
    if isinstance(counts, dict) and counts:
        notes.append(
            "collect hook removed: "
            + ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
        )
