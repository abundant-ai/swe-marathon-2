"""Exercise the delivered employee software through its public loopback interface."""

from __future__ import annotations

import http.client
import json
import os
import plistlib
import signal
import socket
import subprocess
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from verifier.checks.support import passed, require
from verifier.contracts import CandidateFailure, CheckResult, VerificationContext

__test__ = False


class Employee:
    """A trusted client that supplies the same identity header as the workplace gateway."""

    def __init__(self, port: int, work_timeout: int) -> None:
        """Bind employee requests to this trial's local product."""
        self.port = port
        self.work_timeout = work_timeout

    def request(
        self,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        employee: str = "employee-one",
        method: str | None = None,
        expected: tuple[int, ...] = (200, 201, 202, 204),
    ) -> Any:
        """Read a bounded product response and check its HTTP status and response format."""
        timeout = self.work_timeout if path == "/api/work" else 10
        client = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            client.request(
                method or ("GET" if body is None else "POST"),
                path,
                json.dumps(body) if body is not None else None,
                {"X-Orange-Employee": employee, "Content-Type": "application/json"},
            )
            result = client.getresponse()
            data = result.read(2_000_001)
            require(
                len(data) <= 2_000_000 and result.status in expected,
                f"{path} returned HTTP {result.status}",
            )
            if result.status >= 400:
                return None
            if path == "/":
                require(
                    "text/html" in (result.getheader("Content-Type") or ""),
                    "Desktop must serve HTML",
                )
                return data.decode()
            return json.loads(data) if data else None
        except (OSError, http.client.HTTPException, ValueError) as exc:
            raise CandidateFailure(
                f"Employee could not use {path}: {type(exc).__name__}"
            ) from exc
        finally:
            client.close()

    def work(self, intent: str, text: str, **choices: str) -> dict[str, Any]:
        """Perform employee work and check the common response shape."""
        result = self.request("/api/work", {"intent": intent, "text": text, **choices})
        require(
            isinstance(result, dict)
            and isinstance(result.get("text"), str)
            and isinstance(result.get("citations"), list),
            "Employee work requires a text result and a citation list",
        )
        return result

    def event(
        self, ident: str, version: int, content: str | None, source: str = "slack"
    ) -> None:
        """Send a synthetic source revision or a tombstone to the submitted service."""
        record = {
            "doc_id": ident,
            "version": version,
            "op": "delete" if content is None else "upsert",
        }
        if content is not None:
            record.update(source_type=source, title=ident, content=content)
        self.request("/api/events", record)


@contextmanager
def session(
    context: VerificationContext, state: Path | None = None
) -> Generator[Employee]:
    """Start the candidate-owned service with the candidate identity and clean up its process group."""
    state = state or context.app.inputs / ("desktop-" + uuid4().hex)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    uid = context.app.uid
    identity: dict[str, Any] = (
        {} if uid is None else {"user": uid, "group": uid, "extra_groups": []}
    )
    try:
        proc = subprocess.Popen(
            [
                str(context.app.root / "orange-desktop"),
                "--port",
                str(port),
                "--state",
                str(state),
            ],
            cwd=context.app.root,
            env=context.app.environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            **identity,
        )
    except OSError as exc:
        raise CandidateFailure(
            f"Cannot start employee desktop: {exc.strerror}"
        ) from exc
    client = Employee(port, context.generation.timeout_sec)
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            require(proc.poll() is None, "Employee desktop exited before it was ready")
            try:
                client.request("/")
            except CandidateFailure:
                time.sleep(0.1)
            else:
                break
        else:
            raise CandidateFailure("Employee desktop did not become ready")
        yield client
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=5)


def test_mac_desktop(context: VerificationContext) -> CheckResult:
    """Check the actual app bundle, executable and rendered-service entry point."""
    bundle = context.app.root / "Orange.app/Contents"
    try:
        manifest = (bundle / "Info.plist").resolve(strict=True)
        require(
            manifest.is_relative_to(context.app.root)
            and manifest.is_file()
            and manifest.stat().st_size < 1_000_000,
            "Invalid Mac bundle manifest",
        )
        info = plistlib.loads(manifest.read_bytes())
        require(
            isinstance(info, dict) and info.get("CFBundlePackageType") == "APPL",
            "Expected a macOS app",
        )
        name = info.get("CFBundleExecutable")
        require(
            isinstance(name, str) and Path(name).name == name,
            "Invalid Mac executable name",
        )
        executable = (bundle / "MacOS" / name).resolve(strict=True)
        require(
            executable.is_relative_to(context.app.root)
            and executable.is_file()
            and os.access(executable, os.X_OK),
            "Missing Mac executable",
        )
    except (OSError, ValueError, plistlib.InvalidFileException) as exc:
        raise CandidateFailure("Mac application bundle is unreadable") from exc
    with session(context) as user:
        require(bool(user.request("/").strip()), "Empty employee desktop page")
    return passed("mac_desktop", "Mac bundle and employee web entry point opened")


def test_live_index(context: VerificationContext) -> CheckResult:
    """Observe updates, redelivery and retraction across all seven workplace source types."""
    with session(context) as user:
        for source in (
            "slack",
            "prs",
            "documents",
            "urls",
            "meeting_transcripts",
            "meeting_chats",
            "directory",
        ):
            key = "project-" + uuid4().hex[:12]
            old = "prior-" + uuid4().hex[:8]
            new = "current-" + uuid4().hex[:8]
            content = f"{key} was assigned to {new}."
            user.event(key, 1, f"{key} was assigned to {old}.", source)
            user.event(key, 2, content, source)
            user.event(key, 1, f"{key} was assigned to {old}.", source)
            result = user.work("ask", f"Who owns {key}?")
            require(
                new in result["text"] and old not in result["text"],
                "Answer must reflect the current revision",
            )
            require(
                any(
                    isinstance(c, dict)
                    and c.get("doc_id") == key
                    and isinstance(c.get("quote"), str)
                    and c["quote"]
                    and c["quote"] in content
                    for c in result["citations"]
                ),
                "Missing current source evidence",
            )
            user.event(key, 3, None, source)
            user.event(key, 2, content, source)
            result = user.work("ask", f"Who owns {key}?")
            require(
                new not in json.dumps(result)
                and not any(
                    isinstance(c, dict) and c.get("doc_id") == key
                    for c in result["citations"]
                ),
                "Retracted evidence reappeared",
            )
    return passed(
        "live_index",
        "Seven source types handled revisions, stale deliveries and retractions",
    )


def work_item(user: Employee, kind: str, **choices: str) -> dict[str, Any]:
    """Create work from a fresh company record and verify the actual item's evidence."""
    topic = "rollout-" + uuid4().hex[:10]
    decision = "date-" + uuid4().hex[:8]
    user.event(topic, 1, f"{topic} is confirmed for {decision}.")
    result = user.work(kind, f"Prepare the update about {topic}.", **choices)
    item = result.get("item")
    if not isinstance(item, dict):
        raise CandidateFailure("Expected a grounded, addressable work item")
    require(
        isinstance(item.get("id"), str)
        and bool(item["id"])
        and isinstance(item.get("text"), str)
        and decision in item["text"],
        "Expected a grounded, addressable work item",
    )
    return item


def test_handoff_routing(context: VerificationContext) -> CheckResult:
    """Check company defaults separately from the employee's explicit choices."""
    with session(context) as user:
        item = work_item(user, "handoff")
        require(
            item.get("destination") == "#shift-handoff"
            and item.get("owner") == "Release Coordination",
            "Incorrect default routing or ownership",
        )
        chosen = work_item(user, "handoff", destination="#design", owner="Avery")
        require(
            chosen.get("destination") == "#design" and chosen.get("owner") == "Avery",
            "Employee choices were overwritten",
        )
    return passed(
        "handoff_routing", "Internal handoffs honor defaults and explicit overrides"
    )


def test_external_drafts(context: VerificationContext) -> CheckResult:
    """Use a customer reply, edit the actual saved draft, then inspect the outbox."""
    with session(context) as user:
        before = user.request("/api/outbox")
        item = work_item(user, "customer_reply", destination="Northstar")
        require(
            item.get("status") == "draft" and item.get("destination") == "Northstar",
            "Customer communication must remain a draft",
        )
        edited = "Employee edit " + uuid4().hex
        user.request("/api/drafts/" + item["id"], {"text": edited}, method="PATCH")
        saved = user.request("/api/drafts")
        require(
            isinstance(saved, list)
            and any(
                isinstance(i, dict)
                and i.get("id") == item["id"]
                and i.get("text") == edited
                for i in saved
            ),
            "Edited customer draft was not available",
        )
        require(
            isinstance(before, list) and user.request("/api/outbox") == before,
            "Preparing a draft sent an outbound message",
        )
    return passed("external_drafts", "Customer reply remained editable and unsent")


def test_employee_drafts(context: VerificationContext) -> CheckResult:
    """Reopen a saved draft after restarting and check cross-employee isolation."""
    state = context.app.inputs / ("restart-" + uuid4().hex)
    with session(context, state) as user:
        item = work_item(user, "handoff")
    with session(context, state) as user:
        mine = user.request("/api/drafts")
        others = user.request("/api/drafts", employee="employee-two")
        require(
            isinstance(mine, list)
            and any(isinstance(i, dict) and i.get("id") == item["id"] for i in mine),
            "Draft lost at restart",
        )
        require(
            isinstance(others, list) and item["id"] not in json.dumps(others),
            "Draft leaked to another employee",
        )
        user.request(
            "/api/drafts/" + item["id"],
            {"text": "changed"},
            employee="employee-two",
            method="PATCH",
            expected=(403, 404),
        )
    return passed(
        "employee_drafts", "Draft survived restart and remained private to its author"
    )
