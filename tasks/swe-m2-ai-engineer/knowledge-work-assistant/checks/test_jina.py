"""Check the embedding client's batching, prefixes, and response validation."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

from task_paths import TASK_ROOT
from types import ModuleType
from typing import Any

import httpx
import pytest


@pytest.fixture
def jina() -> ModuleType:
    """Load the resource helper without importing any GPU libraries.

    Returns:
        A fresh client module for each test, independent of the author runtime.
    """
    path = TASK_ROOT / "environment/resources/jina.py"
    spec = importlib.util.spec_from_file_location("jina_client", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_embedding_batches_preserve_order_and_role(jina: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise real HTTP serialization with deliberately reordered responses.

    Args:
        jina: Isolated resource client.
        monkeypatch: Restore HTTP and startup replacements after the check.
    """
    requests: list[dict[str, Any]] = []
    starts: list[bool] = []

    def ready() -> None:
        """Record the single service-readiness check for this batch."""
        starts.append(True)

    def respond(request: httpx.Request) -> httpx.Response:
        """Return indexed unit vectors in reverse order.

        Args:
            request: Actual serialized embedding request.

        Returns:
            A response whose ordering differs from the input ordering.
        """
        import json
        body = json.loads(request.content)
        requests.append(body)
        rows = []
        for index, text in enumerate(body["input"]):
            vector = [0.0] * 1024
            vector[int(text.split(": ")[1])] = 1.0
            rows.append({"index": index, "embedding": vector})
        return httpx.Response(200, json={"data": list(reversed(rows))})

    original = httpx.Client

    def client(**kwargs: Any) -> httpx.Client:
        """Use an in-memory transport while preserving the real pooled client.

        Args:
            **kwargs: The helper's timeout, base URL, and proxy options.

        Returns:
            Client connected to the controlled embedding response handler.
        """
        return original(transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setattr(jina, "ensure_server", ready)
    monkeypatch.setattr(jina.httpx, "Client", client)
    for side, prefix in (("query", "Query: "), ("document", "Document: ")):
        requests.clear()
        result = asyncio.run(jina.embed([str(i) for i in range(130)], side))
        assert [len(row["input"]) for row in requests] == [64, 64, 2]
        assert all(text.startswith(prefix) for row in requests for text in row["input"])
        assert all(vector[i] == 1 for i, vector in enumerate(result))
    assert len(starts) == 2


def test_invalid_and_empty_inputs_do_not_start_server(jina: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject invalid inputs and handle empty batches before touching the GPU.

    Args:
        jina: Isolated client module.
        monkeypatch: Prevent any service startup.
    """
    def forbidden() -> None:
        """Fail if input validation attempts to start the service."""
        pytest.fail("Unexpected service startup")

    monkeypatch.setattr(jina, "ensure_server", forbidden)
    assert asyncio.run(jina.embed([], "query")) == []
    with pytest.raises(ValueError):
        asyncio.run(jina.embed(["text"], "invalid"))
    with pytest.raises(ValueError):
        asyncio.run(jina.embed([None], "query"))


def test_invalid_embedding_responses_are_rejected(jina: ModuleType) -> None:
    """Reject missing results, duplicate indices, NaNs, and non-unit vectors.

    Args:
        jina: Isolated response validator.
    """
    for payload in (
        {"data": []},
        {"data": [{"index": 1, "embedding": [1.0] + [0.0] * 1023}]},
        {"data": [{"index": 0, "embedding": [float("nan")] * 1024}]},
        {"data": [{"index": 0, "embedding": [0.0] * 1024}]},
    ):
        with pytest.raises(ValueError):
            jina.validate_vectors(payload, 1)


def test_server_finds_build_tools_when_harness_replaces_path(
    jina: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Inspect the actual spawn environment under a stripped harness PATH.

    Args:
        jina: Isolated embedding client with no running service.
        monkeypatch: Restore environment and process replacements after the test.
        tmp_path: Writable startup-lock directory.
    """
    captured: dict[str, str] = {}

    def directory(path: str) -> Path:
        """Redirect server scratch storage into the isolated test directory.

        Args:
            path: Production scratch path.

        Returns:
            Test-owned service directory.
        """
        return tmp_path / "service"

    def unavailable(request: httpx.Request) -> httpx.Response:
        """Request startup by reporting no healthy server.

        Args:
            request: Loopback health request.

        Returns:
            Service-unavailable response.
        """
        return httpx.Response(503)

    def intercept(command: list[str], **kwargs: Any) -> None:
        """Capture startup settings without launching GPU code on the host.

        Args:
            command: Server executable and arguments.
            **kwargs: Actual process options, including its isolated environment.

        Raises:
            RuntimeError: Deliberately stops after capturing the spawn request.
        """
        captured.update(kwargs["env"])
        raise RuntimeError("captured server startup")

    monkeypatch.setenv("PATH", "/harness/bin:/usr/bin:/bin")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-harness-secret")
    monkeypatch.setenv("ORANGE_OPENAI_API_KEY", "synthetic-application-secret")
    monkeypatch.setattr(jina, "Path", directory)
    monkeypatch.setattr(jina.subprocess, "Popen", intercept)
    with httpx.Client(base_url=jina.BASE_URL, transport=httpx.MockTransport(unavailable)) as client:
        def pooled() -> httpx.Client:
            """Return the controlled health client.

            Returns:
                Pool reporting that a new server must be started.
            """
            return client

        monkeypatch.setattr(jina, "_client", pooled)
        with pytest.raises(RuntimeError, match="captured server startup"):
            jina.ensure_server()
    assert captured["PATH"].split(":")[:2] == ["/opt/runtime/bin", "/usr/local/cuda/bin"]
    assert "/usr/bin" in captured["PATH"].split(":")
    assert "/harness/bin" not in captured["PATH"].split(":")
    assert "OPENAI_API_KEY" not in captured and "ORANGE_OPENAI_API_KEY" not in captured


def test_warm_calls_skip_health_and_recover_after_disconnect(
    jina: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Avoid the slow readiness probe until a connection failure invalidates it.

    Args:
        jina: Fresh client with no known service readiness.
        monkeypatch: Redirect the lock directory and HTTP transport.
        tmp_path: Isolated directory for the startup lock.
    """
    health_calls: list[str] = []
    fail_next: list[bool] = []

    def directory(path: str) -> Path:
        """Redirect the service's scratch path into this test's directory.

        Args:
            path: Production path, intentionally unused by the controlled test.

        Returns:
            A directory that cannot collide with a real running service.
        """
        return tmp_path / "service"

    def respond(request: httpx.Request) -> httpx.Response:
        """Simulate a healthy service with one optional dropped connection.

        Args:
            request: Readiness or embedding request from the real client.

        Returns:
            Healthy status or a valid normalized vector.

        Raises:
            httpx.ConnectError: The test requested a simulated service failure.
        """
        if request.url.path == "/health":
            health_calls.append(request.url.path)
            return httpx.Response(200)
        if fail_next:
            fail_next.pop()
            raise httpx.ConnectError("Service stopped", request=request)
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0] + [0.0] * 1023}]})

    with httpx.Client(base_url=jina.BASE_URL, transport=httpx.MockTransport(respond)) as client:
        def pooled() -> httpx.Client:
            """Return the shared connection pool used across test event loops.

            Returns:
                The controlled synchronous HTTP client.
            """
            return client

        monkeypatch.setattr(jina, "Path", directory)
        monkeypatch.setattr(jina, "_client", pooled)
        for _ in range(2):
            asyncio.run(jina.embed(["text"], "query"))
        assert len(health_calls) == 1
        fail_next.append(True)
        with pytest.raises(httpx.ConnectError):
            asyncio.run(jina.embed(["text"], "query"))
        asyncio.run(jina.embed(["text"], "query"))
        assert len(health_calls) == 2
