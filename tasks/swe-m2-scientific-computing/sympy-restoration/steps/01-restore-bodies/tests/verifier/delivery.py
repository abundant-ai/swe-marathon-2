"""What arrived of the submitted tree, read before anything of it is graded.

The collect step of the agent's environment marks every delivery before it is copied here: a
mark (`.fsmaint`) whose first line is `listed <entries> <bytes>`, `refused` or `absent`, and a
record (`.fsmaint.json`) of every entry with the times it had when the work ended. The mark's
last line signs the other lines and the record's sha256 with a key the agent's user cannot read.

- No tree, no mark, an unreadable or unsigned mark, a listed file that did not arrive as it was
  listed, or a link or a file that arrived without being listed: the copy failed, which is an
  evaluation error, never the submission's score.
- `refused` or `absent`: a completed evaluation of an empty delivery.
- `listed` without an end of the work (the collect step could not tell when the work ended, or
  took its own start while public hosts answered): an evaluation error, since no file could be
  told apart from one written after the work.
- `listed`: graded, except that a file changed at or after the end of the work (its change or
  modification time at or after the recorded end bound, less a small allowance) is not taken.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import socket
import ssl
import stat
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from verifier.contracts import EvaluationError

MARK = ".fsmaint"
RECORD = ".fsmaint.json"
MARK_LIMIT = 1 << 20      # bytes of the mark read, at most
RECORD_LIMIT = 64 << 20   # bytes of the record read, at most
SKEW_SEC = 0.25           # a change this close before the end bound counts as after it
PUBLIC_HOSTS = ("pypi.org", "files.pythonhosted.org", "github.com")


@dataclass
class Delivery:
    """The collect step's account of the tree, checked against what arrived."""

    state: str
    entries: dict[str, dict[str, Any]] = field(default_factory=dict)
    end_bound: float | None = None
    end_from: str | None = None
    late: set[str] = field(default_factory=set)
    notes: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


def _read_bounded(path: Path, limit: int) -> bytes | None:
    try:
        info = os.lstat(path)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            return None
        with open(path, "rb") as handle:
            return handle.read(limit + 1)
    except OSError:
        return None


def _sha256(path: Path) -> str | None:
    try:
        whole = hashlib.sha256()
        with open(path, "rb") as handle:
            while chunk := handle.read(1 << 20):
                whole.update(chunk)
        return whole.hexdigest()
    except OSError:
        return None


def read_delivery(top: Path, key_path: Path) -> Delivery:
    """Check the mark and the record against the tree that arrived.

    Args:
        top: The arrived tree (`/app/sympy`).
        key_path: The signing key, readable by the verifier only.

    Returns:
        The delivery's state, its listed entries, the end bound and the files changed after it.

    Raises:
        EvaluationError: Nothing arrived, the mark or the record is missing, unreadable or not
            signed with the key, a listed file is absent or differs from its listing, a link or
            an unlisted file arrived, or the record holds no end of the work.
    """
    if top.is_symlink() or not top.is_dir():
        raise EvaluationError("Nothing arrived: the tree is missing, though the collect step marks every delivery")
    try:
        key = key_path.read_bytes().strip()
    except OSError as exc:
        raise EvaluationError("The delivery key is unreadable in the verifier image") from exc
    raw = _read_bounded(top / MARK, MARK_LIMIT)
    if raw is None:
        raise EvaluationError("The tree arrived without the collect step's mark")
    lines = raw.decode("utf-8", "backslashreplace").splitlines()
    signed = lines[-1].split() if lines else []
    if len(lines) < 2 or len(signed) != 3 or signed[0] != "sig":
        raise EvaluationError("The collect step's mark cannot be read")
    body, record_sha, signature = lines[:-1], signed[1], signed[2]
    expected = hmac.new(key, ("\n".join(body) + "\n" + record_sha).encode(errors="backslashreplace"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise EvaluationError("The collect step's mark is not signed with the delivery key")
    payload = _read_bounded(top / RECORD, RECORD_LIMIT)
    if payload is None or hashlib.sha256(payload).hexdigest() != record_sha:
        raise EvaluationError("The collect step's record is missing or differs from the one its mark signs")
    try:
        record = json.loads(payload)
    except ValueError as exc:
        raise EvaluationError("The collect step's record cannot be read") from exc
    head = body[0].split()
    delivery = Delivery(state=head[0] if head else "", notes=[f"collect step: {line}" for line in body[1:]][:50])
    delivery.summary = summarise(record)
    if delivery.state in ("refused", "absent"):
        return delivery
    if not (len(head) == 3 and head[0] == "listed" and all(v.isascii() and v.isdigit() for v in head[1:])):
        raise EvaluationError("The collect step's mark cannot be read")
    listed = {item["path"]: item for item in record.get("entries", []) if isinstance(item, dict) and isinstance(item.get("path"), str)}
    if len(listed) != int(head[1]):
        raise EvaluationError("The collect step's record does not list what its mark counts")
    if any(item.get("type") not in ("file", "directory") for item in listed.values()):
        raise EvaluationError("The collect step's record lists an entry that is neither a file nor a directory")
    # nothing may be reached through a link, and nothing may arrive that the collect step did not list
    for folder, dirs, names in os.walk(top, followlinks=False):
        for name in dirs + names:
            path = os.path.join(folder, name)
            rel = os.path.relpath(path, top).replace(os.sep, "/")
            if os.path.islink(path):
                raise EvaluationError(f"A link arrived, though the collect step removes every link: {rel!r}")
            if name in names and rel not in listed and rel not in (MARK, RECORD):
                raise EvaluationError(f"A file arrived that the collect step did not list: {rel!r}")
    short = []
    for path, item in listed.items():
        if item.get("type") != "file":
            continue
        arrived = top / path
        try:
            info = os.lstat(arrived)
        except OSError:
            short.append(path)
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_size != item.get("size") or _sha256(arrived) != item.get("sha256"):
            short.append(path)
    if short:
        raise EvaluationError(f"The copy arrived incomplete or changed: {len(short)} listed files differ, first {short[0]!r}")
    delivery.entries = listed
    note = record.get("end_note") or "no end bound on record"
    try:
        delivery.end_bound, delivery.end_from = float(record["end_bound"]), str(record.get("end_from"))
    except (KeyError, TypeError, ValueError) as exc:
        raise EvaluationError(f"The collect step could not tell when the work ended: {note}") from exc
    if delivery.end_from not in ("netcheck", "collect"):
        raise EvaluationError(f"The collect step could not tell when the work ended: {note}")
    if delivery.end_from == "collect" and (record.get("egress") or {}).get("any_open") is not False:
        raise EvaluationError("The collect step took its own start as the end of the work although public hosts answered")
    cutoff = delivery.end_bound - SKEW_SEC
    for path, item in listed.items():
        times = [t for t in (item.get("ctime"), item.get("mtime")) if isinstance(t, (int, float))]
        if item.get("type") == "file" and (not times or max(times) >= cutoff):
            delivery.late.add(path)
    return delivery


def summarise(record: dict) -> dict:
    """What metrics.json keeps of the record: never raising, never part of the score."""
    try:
        egress = record.get("egress") or {}
        opened = record.get("netcheck_open") or {}
        netcheck = record.get("netcheck") or {}
        return {"listed": record.get("listed"), "end_bound": record.get("end_bound"), "end_from": record.get("end_from"),
                "end_note": record.get("end_note"), "egress_open": egress.get("any_open"), "egress_hosts": egress.get("hosts"),
                "netcheck_openings": len(netcheck.get("openings") or []), "netcheck_last_poll": netcheck.get("last_poll"),
                "netcheck_settle": record.get("netcheck_settle"), "netcheck_open": opened or None,
                "process_count": record.get("process_count"), "processes": (record.get("processes") or [])[:50],
                "kill_passes": record.get("kill_passes"), "processes_left": record.get("processes_left"),
                "listing_complete": record.get("listing_complete"), "work_started": record.get("work_started"),
                "sweep_started_at": record.get("sweep_started_at"), "notes": [str(n) for n in record.get("notes", [])][:50]}
    except Exception as exc:  # noqa: BLE001 - a record, never a reason to lose the evaluation
        return {"error": type(exc).__name__}


def network_open(hosts=PUBLIC_HOSTS, seconds: float = 3.0) -> str | None:
    """The first public host with which a TLS handshake completes from here, or None."""
    answered: list[str] = []

    def reach(host: str) -> None:
        try:
            with socket.create_connection((host, 443), timeout=seconds) as raw:
                raw.settimeout(seconds)
                with ssl.create_default_context().wrap_socket(raw, server_hostname=host):
                    answered.append(host)
        except (OSError, ssl.SSLError, ValueError):
            pass

    workers = [threading.Thread(target=reach, args=(host,), daemon=True) for host in hosts]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(2 * seconds + 0.5)
    return answered[0] if answered else None
