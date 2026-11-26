"""Framing and signing of the telemetry link.

Every message, in both directions, is a 4-byte big-endian length L, a 32-byte
HMAC-SHA256 tag of the payload under the per-run key, and L - 32 bytes of UTF-8 JSON.
Each payload carries a sequence number `n` that starts at 0 on each side and grows by
one per message, so a message can be neither forged nor replayed.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import socket
import struct
from dataclasses import dataclass

TAG_BYTES = 32
INBOUND_LIMIT = 64 << 20  # largest message the kit accepts from the game
OUTBOUND_LIMIT = 16 << 20  # largest message the telemetry node accepts


class LinkError(Exception):
    """The link failed. `kind` says how, in a few words a report can group by.

    Kinds: "closed" (the game side closed the link or the process ended), "unsigned"
    (a message with a bad tag), "bad_message" (malformed JSON, wrong sequence number,
    oversized), "timeout" (no message within the allowed time).
    """

    def __init__(self, kind: str, message: str) -> None:
        """Create the error.

        Args:
            kind: One of the kinds listed on the class.
            message: Human-readable detail for logs and reports.
        """
        super().__init__(message)
        self.kind = kind


def encode(key: bytes, obj: dict) -> bytes:
    """Serialise and sign one message.

    Used by Link.send; pure (no I/O).

    Args:
        key: The per-run key (32 bytes).
        obj: The JSON object to send; it must already carry its sequence number.

    Returns:
        The framed bytes: length, tag, payload.

    Raises:
        LinkError: The payload is larger than the telemetry node accepts.
    """
    payload = json.dumps(obj, separators=(",", ":"), allow_nan=False).encode()
    if len(payload) + TAG_BYTES > OUTBOUND_LIMIT:
        raise LinkError("bad_message", f"message of {len(payload)} bytes is too large")
    tag = hmac.new(key, payload, hashlib.sha256).digest()
    return struct.pack(">I", len(payload) + TAG_BYTES) + tag + payload


def decode_body(key: bytes, body: bytes) -> dict:
    """Check the tag of one received message body and parse its JSON.

    Args:
        key: The per-run key.
        body: The L bytes that followed the length prefix (tag, then payload).

    Returns:
        The parsed JSON object.

    Raises:
        LinkError: "unsigned" when the tag does not match, "bad_message" when the
            payload is not a JSON object.
    """
    if len(body) < TAG_BYTES:
        raise LinkError("bad_message", "message shorter than its tag")
    tag, payload = body[:TAG_BYTES], body[TAG_BYTES:]
    want = hmac.new(key, payload, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, want):
        raise LinkError("unsigned", "message with a bad signature")
    try:
        obj = json.loads(payload.decode("utf-8", errors="replace"))
    except ValueError as exc:
        raise LinkError("bad_message", f"message is not JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise LinkError("bad_message", "message is not a JSON object")
    return obj


@dataclass
class Link:
    """One accepted telemetry connection with its key and sequence counters.

    Created by session.Session after the game connects; used only from one thread at a
    time per direction (the realtime reader thread receives, the caller sends).

    Attributes:
        sock: The connected TCP socket (TCP_NODELAY set by the creator).
        key: The per-run key.
        seq_in: Sequence number expected on the next received message.
        seq_out: Sequence number of the next sent message.
    """

    sock: socket.socket
    key: bytes
    seq_in: int = 0
    seq_out: int = 0

    def send(self, obj: dict) -> None:
        """Send one command, adding the next sequence number.

        Args:
            obj: Command fields; a copy with "n" added is sent.

        Raises:
            LinkError: "closed" when the socket is gone; "bad_message" when too large.
        """
        msg = dict(obj)
        msg["n"] = self.seq_out
        data = encode(self.key, msg)
        try:
            self.sock.sendall(data)
        except OSError as exc:
            raise LinkError("closed", f"link closed while sending: {exc}") from exc
        self.seq_out += 1

    def recv(self, timeout_s: float | None) -> dict:
        """Receive one message, checking its tag and sequence number.

        Args:
            timeout_s: Seconds to wait for the whole message; None waits forever.

        Returns:
            The message's JSON object (with its "n").

        Raises:
            LinkError: "timeout", "closed", "unsigned" or "bad_message".
        """
        self.sock.settimeout(timeout_s)
        header = self._read(4)
        (length,) = struct.unpack(">I", header)
        if length < TAG_BYTES or length > INBOUND_LIMIT:
            raise LinkError("bad_message", f"message length {length} out of range")
        obj = decode_body(self.key, self._read(length))
        if obj.get("n") != self.seq_in:
            raise LinkError(
                "bad_message",
                f"message number {obj.get('n')!r}, expected {self.seq_in}",
            )
        self.seq_in += 1
        return obj

    def _read(self, n: int) -> bytes:
        """Read exactly n bytes from the socket (its timeout already set by recv)."""
        chunks = []
        left = n
        while left > 0:
            try:
                chunk = self.sock.recv(min(left, 1 << 20))
            except TimeoutError as exc:
                raise LinkError("timeout", "no message in time") from exc
            except OSError as exc:
                raise LinkError("closed", f"link closed: {exc}") from exc
            if not chunk:
                raise LinkError("closed", "link closed by the game")
            chunks.append(chunk)
            left -= len(chunk)
        return b"".join(chunks)

    def close(self) -> None:
        """Close the socket; safe to call more than once."""
        try:
            self.sock.close()
        except OSError:
            pass
