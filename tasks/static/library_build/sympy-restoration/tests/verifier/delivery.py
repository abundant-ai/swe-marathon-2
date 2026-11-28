"""What arrived of the submitted tree, read before anything of it is measured.

The collect step of the work's environment marks every delivery before it is copied here: a
mark (`.fsmaint`) whose first line is `listed <entries> <bytes>` or `refused`, and a record
(`.fsmaint.json`) of every entry with the times it had when the work ended. The mark's lines are
printable ASCII, one per line; its last line signs the other lines and the record's sha256 with a
key the work's user, `dev`, cannot read.

- No tree, no mark, an unreadable, oversized or unsigned mark, a listed file that did not arrive
  as it was listed, a link or a file that arrived without being listed, or a record that says a
  process of the user `dev` outlived the collect step: the copy failed or cannot be trusted,
  which is an evaluation error, never the submission's score. The collect step always leaves a
  marked tree, whatever the work left under its name, so these come from the infrastructure;
  except when the collect step says (in its progress file, which the setup step made and only root
  can write, copied beside the tree) that it began and did not finish, and there is no mark it
  signed: the work kept it from running (it started no process, as a work that forks without end
  makes it), and what arrived is an empty delivery that scores 0, with a note.
- `refused` (nothing usable under the tree's name: nothing at all, a link, a file, a tree that
  could not be listed, or one over the collect step's limits): a completed evaluation of an empty
  delivery, which scores 0.
- `listed`: measured, except that a file changed at or after the end of the work (its change or
  modification time at or after the recorded end bound, less a small allowance) is not taken. A
  unit file the collect step replaced by the last copy taken of it before the end (`copied`) is
  taken as that copy, which it lists. The end is never later than the start of the first process
  of the work (else the start of the work) plus the time the work is given (`limit`). A
  record without an end of the work is returned with `end_bound` None: the measurement then grades
  a tree with no restored unit as 0, and raises an evaluation error for any other, since none of
  its files could be told from one written after the work.
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
PROGRESS = Path(
    "/var/lib/fsmaint/out/progress"
)  # where the collect step got to, copied beside the tree
PROGRESS_LIMIT = 4096
MARK_LIMIT = 1 << 20  # bytes of the mark read, at most
RECORD_LIMIT = 64 << 20  # bytes of the record read, at most
SKEW_SEC = 0.25  # a change this close before the end bound counts as after it
WORK_LIMIT_SEC = (
    34560  # the time the work is given: no end of it is later than its start plus this
)
PUBLIC_HOSTS = ("pypi.org", "files.pythonhosted.org", "github.com")
END_SOURCES = ("netcheck", "collect", "session", "limit", "unchanged")


@dataclass
class Delivery:
    """The collect step's account of the tree, checked against what arrived."""

    state: str
    entries: dict[str, dict[str, Any]] = field(default_factory=dict)
    end_bound: float | None = None
    end_from: str | None = None
    end_note: str | None = None
    late: set[str] = field(default_factory=set)
    copied: dict[str, dict[str, Any]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


def _read_bounded(path: Path, limit: int) -> tuple[bytes | None, str]:
    """(the file's bytes, or None and why not: "missing", "not a regular file" or "too large")."""
    try:
        info = os.lstat(path)
    except OSError:
        return None, "missing"
    if not stat.S_ISREG(info.st_mode):
        return None, "not a regular file"
    if info.st_size > limit:
        return None, f"larger than {limit:,} bytes"
    try:
        with open(path, "rb") as handle:
            return handle.read(limit + 1), ""
    except OSError:
        return None, "unreadable"


def _sha256(path: Path) -> str | None:
    try:
        whole = hashlib.sha256()
        with open(path, "rb") as handle:
            while chunk := handle.read(1 << 20):
                whole.update(chunk)
        return whole.hexdigest()
    except OSError:
        return None


def progress_stage(path: Path) -> str | None:
    """The stage the collect step last wrote into its progress file, or None without a readable one."""
    raw, _why = _read_bounded(path, PROGRESS_LIMIT)
    if raw is None:
        return None
    try:
        stage = json.loads(raw.decode("utf-8", "replace").strip() or "null").get(
            "stage"
        )
    except (ValueError, AttributeError):
        return None
    return stage if isinstance(stage, str) and len(stage) <= 40 else None


def read_delivery(top: Path, key_path: Path, progress: Path = PROGRESS) -> Delivery:
    """Check the mark and the record against the tree that arrived.

    Args:
        top: The arrived tree (`/app/sympy`).
        key_path: The signing key, readable by the verifier only.
        progress: The collect step's progress file, copied beside the tree.

    Returns:
        The delivery's state, its listed entries, the end bound (None when the record holds no end
        of the work) and the files changed after it.

    Raises:
        EvaluationError: Nothing arrived, the mark or the record is missing, unreadable or not
            signed with the key, a listed file is absent or differs from its listing, a link or
            an unlisted file arrived, a process of the user `dev` outlived the collect step, or
            the record's end of the work is malformed or contradicts its entries.
    """
    if top.is_symlink() or not top.is_dir():
        raise EvaluationError(
            "Nothing arrived: the tree is missing, though the collect step marks every delivery"
        )
    try:
        key = key_path.read_bytes().strip()
    except OSError as exc:
        raise EvaluationError("The delivery key is unreadable") from exc

    def unmarked(why: str) -> Delivery:
        """No mark the collect step signed: an empty delivery when the collect step says it began and did
        not finish (the work kept it from running), else the copy failed (an evaluation error)."""
        stage = progress_stage(progress)
        if stage is not None and stage not in ("done", "not begun"):
            note = (
                f"collect step: it began and did not finish (it got to `{stage}`), and the tree arrived without a "
                f"mark it signed ({why}): what arrived was not measured"
            )
            return Delivery(
                state="refused",
                notes=[note],
                summary={"listed": "refused", "refused": note, "progress": stage},
            )
        raise EvaluationError(
            f"The tree arrived without a mark the collect step signed: {why}"
        )

    raw, why = _read_bounded(top / MARK, MARK_LIMIT)
    if raw is None:
        return unmarked(
            "no mark" if why == "missing" else f"the mark cannot be read: {why}"
        )
    lines = raw.decode("utf-8", "backslashreplace").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    signed = lines[-1].split(" ") if lines else []
    if len(lines) < 2 or len(signed) != 3 or signed[0] != "sig":
        return unmarked("the mark cannot be read")
    body, record_sha, signature = lines[:-1], signed[1], signed[2]
    expected = hmac.new(
        key,
        ("\n".join(body) + "\n" + record_sha).encode(errors="backslashreplace"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return unmarked("the mark is not signed with the delivery key")
    head = body[0].split(" ")
    delivery = Delivery(
        state=head[0] if head else "",
        notes=[f"collect step: {line}" for line in body[1:]][:50],
    )
    payload, why = _read_bounded(top / RECORD, RECORD_LIMIT)
    if delivery.state == "refused" and len(head) == 1:
        # nothing usable stood under the tree's name, the tree was over the limits, or the collect step did
        # not finish: an empty delivery. Nothing of it is measured, so a record newer than the mark (a collect
        # step stopped between writing the two) changes nothing.
        record = None
        if payload is not None and hashlib.sha256(payload).hexdigest() == record_sha:
            try:
                record = json.loads(payload)
            except ValueError:
                record = None
        delivery.summary = (
            summarise(record)
            if isinstance(record, dict)
            else {
                "listed": "refused",
                "refused": body[1] if len(body) > 1 else None,
                "record": "not the one the mark signs",
            }
        )
        return delivery
    if payload is None:
        raise EvaluationError(f"The collect step's record cannot be read: {why}")
    if hashlib.sha256(payload).hexdigest() != record_sha:
        raise EvaluationError(
            "The collect step's record differs from the one its mark signs"
        )
    try:
        record = json.loads(payload)
    except ValueError as exc:
        raise EvaluationError("The collect step's record cannot be read") from exc
    if not isinstance(record, dict):
        raise EvaluationError("The collect step's record cannot be read")
    delivery.summary = summarise(record)
    if not (
        len(head) == 3
        and head[0] == "listed"
        and all(v.isascii() and v.isdigit() for v in head[1:])
    ):
        raise EvaluationError("The collect step's mark cannot be read")
    left = record.get("processes_left")
    if isinstance(left, int) and not isinstance(left, bool) and left > 0:
        raise EvaluationError(
            f"{left} processes of the user dev outlived the collect step, so the copy may differ from its listing"
        )
    listed = {
        item["path"]: item
        for item in record.get("entries", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    if len(listed) != int(head[1]):
        raise EvaluationError(
            "The collect step's record does not list what its mark counts"
        )
    if any(item.get("type") not in ("file", "directory") for item in listed.values()):
        raise EvaluationError(
            "The collect step's record lists an entry that is neither a file nor a directory"
        )
    # nothing may be reached through a link, and nothing may arrive that the collect step did not list
    for folder, dirs, names in os.walk(top, followlinks=False):
        for name in dirs + names:
            path = os.path.join(folder, name)
            rel = os.path.relpath(path, top).replace(os.sep, "/")
            if os.path.islink(path):
                raise EvaluationError(
                    f"A link arrived, though the collect step removes every link: {rel!r}"
                )
            if name in names and rel not in listed and rel not in (MARK, RECORD):
                raise EvaluationError(
                    f"A file arrived that the collect step did not list: {rel!r}"
                )
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
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_size != item.get("size")
            or _sha256(arrived) != item.get("sha256")
        ):
            short.append(path)
    if short:
        raise EvaluationError(
            f"The copy arrived incomplete or changed: {len(short)} listed files differ, first {short[0]!r}"
        )
    delivery.entries = listed
    bound, origin = record.get("end_bound"), record.get("end_from")
    if bound is None and origin is None:
        # no end of the work: measure() grades a tree with no restored unit and refuses any other
        delivery.end_note = str(
            record.get("end_note") or "no end of the work on record"
        )
        return delivery
    try:
        delivery.end_bound, delivery.end_from = float(bound), str(origin)
    except (TypeError, ValueError) as exc:
        raise EvaluationError(
            "The collect step's record holds a malformed end of the work"
        ) from exc
    if delivery.end_from not in END_SOURCES:
        raise EvaluationError(
            f"The collect step's record names an unknown end of the work: {delivery.end_from!r}"
        )
    if (
        delivery.end_from == "collect"
        and (record.get("net_probe") or {}).get("any_open") is not False
    ):
        raise EvaluationError(
            "The collect step took its own start as the end of the work although public hosts were not seen closed"
        )
    limit = work_limit(record)
    if limit is not None and delivery.end_bound > limit:
        delivery.end_bound, delivery.end_from = limit, "limit"
    cutoff = delivery.end_bound - SKEW_SEC
    for path, item in listed.items():
        times = [
            t
            for t in (item.get("ctime"), item.get("mtime"))
            if isinstance(t, (int, float))
        ]
        if item.get("type") == "file" and (not times or max(times) >= cutoff):
            delivery.late.add(path)
        copied = item.get("copied")
        if isinstance(copied, dict) and path not in delivery.late:
            captured = copied.get("captured")
            if (
                isinstance(captured, (int, float))
                and not isinstance(captured, bool)
                and captured <= delivery.end_bound
            ):
                delivery.copied[path] = copied
            else:
                delivery.late.add(
                    path
                )  # a copy that did not hold its content by the end is not taken either
    if delivery.copied:
        changed = sorted(
            {
                str(uid)
                for c in delivery.copied.values()
                for uid in (c.get("units_changed_after") or [])
            }
        )
        delivery.notes.append(
            f"{len(delivery.copied)} unit files changed after the end of the work were taken as the last copy the collect step "
            f"held of them before it ({', '.join(sorted(delivery.copied)[:5])}); units whose bodies changed after it: "
            f"{len(changed)}{' (' + ', '.join(changed[:10]) + ')' if changed else ''}"
        )
    if delivery.end_from == "unchanged" and delivery.late:
        raise EvaluationError(
            "The collect step's record says nothing changed during the work, yet lists files changed since it began"
        )
    return delivery


def work_limit(record: dict) -> float | None:
    """The time the work is given ran out: the start of the work, which the setup step took before the
    agent's own clock began, plus WORK_LIMIT_SEC; None without a start of the work. (The first process
    of the work, which began after that clock, only decides when the net check may end it.)"""
    started = record.get("work_started")
    if not isinstance(started, (int, float)) or isinstance(started, bool):
        return None
    return started + WORK_LIMIT_SEC


def summarise(record: dict) -> dict:
    """What metrics.json keeps of the record: never raising, never part of the score."""
    try:
        probe = record.get("net_probe") or {}
        opened = record.get("netcheck_open") or {}
        netcheck = record.get("netcheck") or {}
        sessions = record.get("sessions") or {}
        return {
            "listed": record.get("listed"),
            "refused": record.get("refused"),
            "end_bound": record.get("end_bound"),
            "end_from": record.get("end_from"),
            "end_note": record.get("end_note"),
            "end_bounds": record.get("end_bounds"),
            "egress_open": probe.get("any_open"),
            "egress_hosts": probe.get("hosts"),
            "netcheck_openings": len(netcheck.get("openings") or []),
            "netcheck_last_poll": netcheck.get("last_poll"),
            "netcheck_local_polls": netcheck.get("local_polls"),
            "netcheck_settle": record.get("netcheck_settle"),
            "netcheck_open": opened or None,
            "sessions_available": sessions.get("available"),
            "sessions_seen": sessions.get("seen"),
            "sessions": (sessions.get("sessions") or [])[-5:],
            "sessions_alive_at_start": record.get("sessions_alive_at_start"),
            "process_count": record.get("process_count"),
            "processes": (record.get("processes") or [])[:50],
            "kill_passes": record.get("kill_passes"),
            "processes_left": record.get("processes_left"),
            "listing_complete": record.get("listing_complete"),
            "work_started": record.get("work_started"),
            "limit_bound": record.get("limit_bound"),
            "limit_from": record.get("limit_from"),
            "copies": record.get("copies"),
            "first_process": sessions.get("first_process"),
            "user_processes_max": sessions.get("user_processes_max"),
            "sweep_started_at": record.get("sweep_started_at"),
            "notes": [str(n) for n in record.get("notes", [])][:50],
        }
    except Exception as exc:  # noqa: BLE001 - a record, never a reason to lose the evaluation
        return {"error": type(exc).__name__}


def network_open(hosts=PUBLIC_HOSTS, seconds: float = 3.0) -> str | None:
    """The first public host with which a TLS handshake completes from here, or None."""
    answered: list[str] = []

    def reach(host: str) -> None:
        try:
            with socket.create_connection((host, 443), timeout=seconds) as raw:
                raw.settimeout(seconds)
                with ssl.create_default_context().wrap_socket(
                    raw, server_hostname=host
                ):
                    answered.append(host)
        except (OSError, ssl.SSLError, ValueError):
            pass

    workers = [
        threading.Thread(target=reach, args=(host,), daemon=True) for host in hosts
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(2 * seconds + 0.5)
    return answered[0] if answered else None
