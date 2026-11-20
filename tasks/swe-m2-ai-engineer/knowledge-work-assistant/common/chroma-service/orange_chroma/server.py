"""Launch the pinned Chroma API behind a mandatory request-policy boundary."""

from __future__ import annotations

import json
import os
from urllib.parse import parse_qs, urlencode

from chromadb.config import Settings
from chromadb.server.fastapi import FastAPI as ChromaServer
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from orange_chroma.policy import ReadPolicy, RejectedRequest, bounded_payload, operation, positive_integer


class LimitedChroma:
    """Expose only capped data operations; no uncapped backend listener exists."""

    def __init__(self, app: ASGIApp, policy: ReadPolicy) -> None:
        """Wrap the upstream ASGI application with trusted, immutable policy.

        Args:
            app: Chroma's in-process HTTP application.
            policy: Limits loaded from the protected service environment.
        """
        self.app = app
        self.policy = policy

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Validate and bound each HTTP request before invoking Chroma.

        Args:
            scope: ASGI connection metadata.
            receive: Incoming body stream, including chunked HTTP requests.
            send: Response channel owned by the ASGI server.

        Returns:
            None. Emits an upstream response, or a 422/413 policy rejection.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        try:
            kind = operation(scope["method"], scope["path"])
            body = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                body.extend(message.get("body", b""))
                if len(body) > self.policy.max_body_bytes:
                    await JSONResponse({"error": "Request body exceeds service limit"}, status_code=413)(scope, receive, send)
                    return
                if not message.get("more_body", False):
                    break
            if kind in {"get", "query"}:
                payload = json.loads(body)
                if not isinstance(payload, dict):
                    raise RejectedRequest("Expected a JSON object")
                body = bytearray(json.dumps(bounded_payload(kind, payload, self.policy)).encode())
            if kind == "list":
                query = parse_qs(scope["query_string"].decode(), keep_blank_values=True)
                values = query.get("limit", [str(self.policy.max_records)])
                if len(values) != 1:
                    raise RejectedRequest("Specify limit once")
                limit = positive_integer(int(values[0]), "limit", self.policy.max_records)
                query["limit"] = [str(limit)]
                scope = {**scope, "query_string": urlencode(query, doseq=True).encode()}
        except (RejectedRequest, ValueError, UnicodeError) as exc:
            await JSONResponse({"error": str(exc)}, status_code=422)(scope, receive, send)
            return

        sent = False

        async def bounded_receive() -> Message:
            """Deliver the validated body once, then preserve disconnect events."""
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        headers = [(key, value) for key, value in scope["headers"] if key.lower() != b"content-length"]
        scope = {**scope, "headers": headers + [(b"content-length", str(len(body)).encode())]}
        await self.app(scope, bounded_receive, send)


def create_app() -> LimitedChroma:
    """Build one service process from required infrastructure-owned settings.

    Returns:
        The capped API, with an exclusive persistent store and telemetry disabled.

    Raises:
        KeyError: Required trusted configuration is absent.
        ValueError: A configured limit is not positive.
    """
    maximum = int(os.environ["CHROMA_MAX_READ_RECORDS"])
    body_bytes = int(os.environ["CHROMA_MAX_BODY_BYTES"])
    if maximum <= 0 or body_bytes <= 0:
        raise ValueError("Chroma service limits must be positive")
    server = ChromaServer(Settings(
        chroma_api_impl="orange_chroma.backend.HttpRustAPI",
        is_persistent=True, persist_directory=os.environ["CHROMA_PERSIST_DIRECTORY"],
        anonymized_telemetry=False, allow_reset=False,
    ))
    return LimitedChroma(server.app(), ReadPolicy(maximum, body_bytes))
