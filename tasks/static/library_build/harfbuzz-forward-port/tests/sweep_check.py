"""What the agent side's sweep says about the tree that arrived, read in the verifier image.

The sweep (environment/fsmaint-sweep, the agent image's collect hook) ends the session's processes,
puts back what changed after the end of the work, makes the tree copyable, and leaves in
/var/lib/fsmaint/out, which is copied out beside the tree: `progress` (where it got to), `mark`
(its first line `listed <entries> <bytes> <sha256 of the sorted listing>` or `refused`, its notes,
and a last line with the record's sha256 and an HMAC-SHA256 over the other lines and that digest)
and `record.json` (everything it found and did).

check(tree, out, key) reads them and the tree that arrived, and returns
{"fault": str or None, "refused": bool, "notes": [str], "record": {...}}:
- `fault`: the check itself cannot score: the sweep's folder or its progress did not arrive, the
  sweep began and did not finish, its mark is missing, unreadable or not signed with the key, its
  record did not arrive whole, or the tree that arrived is not the one the mark lists (cut short in
  the copy, or changed). The trial then ends without a reward instead of with a 0.
- `refused`: the sweep refused the tree (over the limits, no room to pack it, the end of the work
  kept from the net check, or nothing usable under the tree's name); it scores 0.
- `notes`: the mark's notes and what the record shows, for metrics.json.
- `record`: a bounded summary of the record: the end of the work, the late entries and what became
  of them, egress after the session, the processes found, and the changes that made it copyable.

Pure functions over the standard library; nothing here follows a link or reads more than a bound.
Run by root before any process of the tree's own code exists:
    python3 -I -B /tests/sweep_check.py /app/harfbuzz /var/lib/fsmaint/out /tests/private/fsmaint.key
prints the same dict as JSON.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import stat
import sys
from pathlib import Path

TREE = Path("/app/harfbuzz")
OUT = Path("/var/lib/fsmaint/out")
KEY = Path("/tests/private/fsmaint.key")
MARK, RECORD, PROGRESS = "mark", "record.json", "progress"
MARK_LIMIT = 1 << 16
RECORD_LIMIT = 64 << 20
PROGRESS_LIMIT = 8192
KEY_LIMIT = 4096
# The sweep's own limits (environment/fsmaint-sweep): a mark that lists more is not read.
LIMIT_ENTRIES = 200_000
LIMIT_BYTES = 1 << 30
MARK_NOTES_KEPT = 20
LATE_SHOWN = 20
PROCESSES_SHOWN = 10
TEXT = 200  # characters of one shown string, at most


class Unreadable(Exception):
    """A file of the sweep's is missing, not a regular file, or larger than its bound."""


def read_bounded(path: Path, limit: int) -> bytes:
    """A regular file's bytes, opened without following a link, at most `limit` of them."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except OSError as exc:
        raise Unreadable(f"{path.name} did not arrive ({exc.strerror})") from exc
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise Unreadable(f"{path.name} is not a regular file")
        chunks, total = [], 0
        while total <= limit:
            chunk = os.read(fd, min(1 << 20, limit + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
    finally:
        os.close(fd)
    if total > limit:
        raise Unreadable(f"{path.name} is larger than {limit} bytes")
    return b"".join(chunks)


def progress_stage(out: Path) -> str | None:
    """Where the sweep got to, from its progress file; None when it cannot be read."""
    try:
        text = read_bounded(out / PROGRESS, PROGRESS_LIMIT).decode("utf-8").strip()
        state = json.loads(text)
    except (Unreadable, UnicodeDecodeError, ValueError):
        return None
    stage = state.get("stage") if isinstance(state, dict) else None
    return stage if isinstance(stage, str) else None


def parse_mark(data: bytes) -> tuple[list[str], str, str]:
    """(the lines above the signature, the record's sha256, the signature); ValueError when the
    mark does not have that shape."""
    text = data.decode("ascii")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if len(lines) < 2:
        raise ValueError("too few lines")
    sig = lines[-1].split(" ")
    if len(sig) != 3 or sig[0] != "sig" or len(sig[1]) != 64 or len(sig[2]) != 64:
        raise ValueError("no signature line")
    return lines[:-1], sig[1], sig[2]


def signature_of(key: bytes, lines: list[str], digest: str) -> str:
    body = "\n".join(lines) + "\n" + digest
    return hmac.new(key, body.encode("ascii"), hashlib.sha256).hexdigest()


def listing_of(
    tree: Path, most_entries: int, most_bytes: int
) -> tuple[int, int, str | None]:
    """(entries, bytes of files, sha256 of the sorted listing) of a tree, the way the sweep lists
    it: every entry below the top, by folder descriptor, never through a link (a folder as
    `d <path>`, a link as `l <path> <target>`, a file as `f <path> <size> <sha256>`, anything else
    as `o <path>`, tab-separated, sorted by the path's bytes, joined by newlines). It stops once
    past `most_entries` or `most_bytes` (the sha256 is then None)."""
    lines: list[bytes] = []
    total = 0

    def visit(fd: int, rel: bytes) -> bool:
        nonlocal total
        with os.scandir(fd) as listing:
            names = sorted(os.fsencode(item.name) for item in listing)
        for name in names:
            path = rel + b"/" + name if rel else name
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if len(lines) >= most_entries:
                lines.append(b"")
                return False
            if stat.S_ISDIR(info.st_mode):
                lines.append(b"d\t" + path)
                child = os.open(
                    name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
                )
                try:
                    if not visit(child, path):
                        return False
                finally:
                    os.close(child)
            elif stat.S_ISLNK(info.st_mode):
                lines.append(b"l\t" + path + b"\t" + os.readlink(name, dir_fd=fd))
            elif stat.S_ISREG(info.st_mode):
                total += info.st_size
                if total > most_bytes:
                    return False
                whole = hashlib.sha256()
                handle = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    while chunk := os.read(handle, 1 << 20):
                        whole.update(chunk)
                finally:
                    os.close(handle)
                lines.append(
                    b"f\t%s\t%d\t%s" % (path, info.st_size, whole.hexdigest().encode())
                )
            else:
                lines.append(b"o\t" + path)
        return True

    top = os.open(tree, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        whole = visit(top, b"")
    finally:
        os.close(top)
    if not whole:
        return len(lines), total, None
    lines.sort(key=lambda line: line.split(b"\t", 2)[1])
    return len(lines), total, hashlib.sha256(b"\n".join(lines)).hexdigest()


def short(value: object) -> object:
    if isinstance(value, str) and len(value) > TEXT:
        return value[: TEXT - 4] + " ..."
    return value


def summary(record: dict) -> dict:
    """The record, bounded: what metrics.json keeps of it."""
    late = [item for item in record.get("late") or [] if isinstance(item, dict)]
    actions: dict[str, int] = {}
    for item in late:
        action = str(item.get("action") or "")
        kind = (
            "removed"
            if action.startswith("removed")
            else f"put back ({item.get('from')})"
            if action.startswith("put back")
            else "other"
        )
        actions[kind] = actions.get(kind, 0) + 1
    opened = (
        record.get("netcheck_open")
        if isinstance(record.get("netcheck_open"), dict)
        else {}
    )
    probe = record.get("net_probe") if isinstance(record.get("net_probe"), dict) else {}
    watch = (
        record.get("tree_watch") if isinstance(record.get("tree_watch"), dict) else {}
    )
    links = record.get("links") if isinstance(record.get("links"), dict) else {}
    processes = [p for p in record.get("processes") or [] if isinstance(p, dict)]
    return {
        "listed": short(record.get("listed")),
        "refused": short(record.get("refused")),
        "end_bound": record.get("end_bound"),
        "end_from": record.get("end_from"),
        "end_note": short(record.get("end_note")),
        "work_started": record.get("work_started"),
        "sweep_started_at": record.get("sweep_started_at"),
        "late": {
            "count": len(late),
            "by_action": actions,
            "first": [
                {key: short(item.get(key)) for key in ("path", "type", "action")}
                for item in late[:LATE_SHOWN]
            ],
        },
        "egress": {
            "first_open_at": opened.get("first_open_at"),
            "end_bound": opened.get("end_bound"),
            "host": short(opened.get("host")),
            "session_alive": opened.get("session_alive"),
            "after_limit": opened.get("after_limit"),
            "ended_at": opened.get("ended_at"),
            "processes_left_then": opened.get("processes_left"),
            "open_at_sweep": probe.get("any_open"),
        },
        "processes": {
            "count": record.get("process_count"),
            "left": record.get("processes_left"),
            "stop_passes": record.get("stop_passes"),
            "kill_passes": record.get("kill_passes"),
            "sessions_alive_at_start": record.get("sessions_alive_at_start"),
            "first": [
                {
                    "pid": p.get("pid"),
                    "state": p.get("state"),
                    "threads": (p.get("threads") or [])[:4],
                    "command": short(p.get("command")),
                }
                for p in processes[:PROCESSES_SHOWN]
            ],
        },
        "changes": record.get("changes")
        if isinstance(record.get("changes"), dict)
        else {},
        "links": {
            key: len(value) for key, value in links.items() if isinstance(value, list)
        },
        "build_folders": len(record.get("build_folders") or []),
        "tree_watch": {
            key: watch.get(key)
            for key in (
                "looks",
                "last_look",
                "tracked",
                "untracked",
                "store_bytes",
                "copying",
            )
        },
        "limits": record.get("limits"),
    }


def flags(record: dict) -> list[str]:
    """What the audit of a trial should look at, from the record."""
    found = []
    late = record.get("late") or []
    if late:
        found.append(
            f"sweep: {len(late)} entries changed after the end of the work were put back as they "
            "were at the end, or removed"
        )
    if record.get("processes_left"):
        found.append(
            f"sweep: {record['processes_left']} processes of the session survived its end"
        )
    if record.get("end_from") is None and not record.get("refused"):
        found.append(
            "sweep: no end of the work could be told, so nothing was taken out as late"
        )
    if record.get("end_from") == "limit":
        found.append("sweep: the work ran to its time limit")
    copied = (record.get("links") or {}).get("copied") or []
    if copied:
        found.append(f"sweep: {len(copied)} links out of the tree became copies")
    return found


def check(tree: Path = TREE, out: Path = OUT, key_path: Path = KEY) -> dict:
    """What the sweep's mark, its record and the tree that arrived say (the module's docstring)."""
    result: dict = {"fault": None, "refused": False, "notes": [], "record": {}}
    try:
        top = os.lstat(out)
    except OSError:
        top = None
    if top is None or not stat.S_ISDIR(top.st_mode):
        result["fault"] = "the sweep's folder did not arrive"
        return result
    stage = progress_stage(out)
    if stage is None:
        result["fault"] = (
            "no word from the sweep: its progress file did not arrive or cannot be read"
        )
        return result
    if stage != "done":
        result["fault"] = (
            "the sweep never began"
            if stage == "not begun"
            else f"the sweep began and did not finish (it got to: {short(stage)})"
        )
        return result
    try:
        mark = read_bounded(out / MARK, MARK_LIMIT)
        lines, digest, signature = parse_mark(mark)
    except Unreadable as exc:
        result["fault"] = f"the sweep finished, but its mark {exc}"
        return result
    except (UnicodeDecodeError, ValueError):
        result["fault"] = "the sweep's mark cannot be read"
        return result
    try:
        key = read_bounded(key_path, KEY_LIMIT).strip()
    except Unreadable:
        key = b""
    if not key:
        result["fault"] = "the check has no key to read the sweep's mark"
        return result
    if not hmac.compare_digest(signature_of(key, lines, digest), signature):
        result["fault"] = "the sweep's mark is not signed with the check's key"
        return result
    try:
        payload = read_bounded(out / RECORD, RECORD_LIMIT)
    except Unreadable as exc:
        result["fault"] = f"the sweep's record {exc}"
        return result
    if hashlib.sha256(payload).hexdigest() != digest:
        result["fault"] = (
            "the sweep's record did not arrive whole: it differs from its mark"
        )
        return result
    try:
        record = json.loads(payload)
    except ValueError:
        record = None
    if not isinstance(record, dict):
        result["fault"] = "the sweep's record cannot be read"
        return result
    result["record"] = summary(record)
    result["notes"] = [f"sweep: {line}" for line in lines[1 : 1 + MARK_NOTES_KEPT]]
    result["notes"] += flags(record)
    head = lines[0].split(" ")
    if head == ["refused"]:
        result["refused"] = True
        return result
    if (
        len(head) != 4
        or head[0] != "listed"
        or not all(value.isascii() and value.isdigit() for value in head[1:3])
        or len(head[3]) != 64
    ):
        result["fault"] = (
            "the sweep's mark lists the tree in a form the check cannot read"
        )
        return result
    entries, size, listed = int(head[1]), int(head[2]), head[3]
    if entries > LIMIT_ENTRIES or size > LIMIT_BYTES:
        result["fault"] = "the sweep's mark lists more than its own limits allow"
        return result
    try:
        found = os.lstat(tree)
    except OSError:
        found = None
    if found is None or not stat.S_ISDIR(found.st_mode):
        if entries == 0:
            return result
        result["fault"] = (
            f"the tree did not arrive, though the sweep listed {entries} entries"
        )
        return result
    try:
        arrived = listing_of(tree, entries, size)
    except OSError as exc:
        result["fault"] = f"the tree that arrived cannot be read ({exc.strerror})"
        return result
    if arrived != (entries, size, listed):
        result["fault"] = (
            "the tree that arrived is not the one the sweep listed: "
            f"{arrived[0]} entries and {arrived[1]} bytes arrived where it listed {entries} and "
            f"{size}" + ("" if arrived[2] is None else ", and their listing differs")
        )
        return result
    return result


def main(argv: list[str]) -> int:
    tree = Path(argv[1]) if len(argv) > 1 else TREE
    out = Path(argv[2]) if len(argv) > 2 else OUT
    key = Path(argv[3]) if len(argv) > 3 else KEY
    print(json.dumps(check(tree, out, key), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
