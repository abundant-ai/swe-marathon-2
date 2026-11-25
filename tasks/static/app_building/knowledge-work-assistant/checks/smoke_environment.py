"""Probe fresh-container transfer, GPU embeddings, and the evaluation allowlist.

Run with --seed from a controlled Harbor solution, then without it from a verifier
wrapper. This is an author check and is never a scored requirement for candidates.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import sys
import urllib.error
import urllib.request
from importlib.metadata import version
from pathlib import Path


def seed() -> None:
    """Leave declared and undeclared markers in the development container."""
    Path("/app/container-transfer-marker").write_text(os.environ["MODAL_TASK_ID"])
    Path("/tmp/undeclared-development-marker").write_text("must not survive")


def http_status(url: str) -> int | None:
    """Attempt a bounded HTTPS request without credentials or proxy overrides.

    Args:
        url: Public URL used to probe the network boundary.

    Returns:
        The server's HTTP status, or None when the connection is blocked. HTTP
        errors still count as connectivity, so a remote 403 is not a false pass.
    """
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url, timeout=8) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return None


async def check_resources() -> dict[str, object]:
    """Exercise the actual GPU helper and network policy as the candidate UID.

    Returns:
        Observations suitable for the author validation report.

    Raises:
        AssertionError: A resource or isolation observation contradicts the task.
    """
    sys.path.insert(0, "/opt/resources")
    assert os.getuid() == 10001
    assert not any("MODAL_TOKEN" in key or "JUDGE" in key for key in os.environ)
    # An unauthenticated API response proves TLS reached the approved service.
    approved = http_status("https://api.openai.com/v1/models")
    assert approved == 401, approved
    blocked = {}
    for url in (
        "https://example.com",
        "https://github.com",
        "https://raw.githubusercontent.com",
        "https://huggingface.co",
        "https://pypi.org",
        "http://example.com",
        "https://1.1.1.1",
    ):
        status = http_status(url)
        assert status is None, (url, status)
        blocked[url] = True
    report = await check_embeddings()
    report.update({"approved_api_status": approved, "blocked_destinations": blocked})
    return report


async def check_embeddings() -> dict[str, object]:
    """Exercise the bundled SGLang server on this Harbor container's GPU.

    Returns:
        Framework version, GPU name, model revision, vector dimensions, and UID.

    Raises:
        AssertionError: The runtime or embeddings violate the supplied contract.
    """
    sys.path.insert(0, "/opt/resources")
    import torch
    from jina import MODEL_REVISION, embed

    assert os.getuid() == 10001
    assert version("sglang") == "0.5.9"
    query = (await embed(["Who owns the product launch?"], "query"))[0]
    document = (await embed(["Priya owns the product launch."], "document"))[0]
    for vector in (query, document):
        assert len(vector) == 1024
        assert all(math.isfinite(value) for value in vector)
        assert abs(math.sqrt(sum(value * value for value in vector)) - 1) < 0.01
    assert query != document
    return {
        "gpu": torch.cuda.get_device_name(),
        "embedding_dimensions": 1024,
        "model_revision": MODEL_REVISION,
        "framework": "sglang",
        "framework_version": version("sglang"),
        "candidate_uid": os.getuid(),
    }


def become_candidate() -> None:
    """Match the application UID and environment before loading GPU code.

    Restored application files may be root-owned. Clear inherited credentials
    and use the same writable home and Python paths as candidate processes.
    """
    if os.getuid() == 0:
        os.chown("/app", 10001, 10001)
    os.chdir("/app")
    os.environ.clear()
    os.environ.update(
        {
            "HOME": "/app",
            "PATH": "/opt/runtime/bin:/usr/bin:/bin",
            "PYTHONPATH": "/opt/resources",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
        }
    )
    if os.getuid() == 0:
        os.setgroups([])
        os.setgid(10001)
        os.setuid(10001)
    assert os.getuid() == 10001


def main() -> None:
    """Seed development state or validate a fresh verifier, without writing rewards.

    Verification checks transfer before dropping privileges and clearing inherited
    credentials. The production verifier runs separately after this process exits.
    """
    if "--seed" in sys.argv:
        seed()
        become_candidate()
        print(json.dumps(asyncio.run(check_resources())), flush=True)
        return
    development_id = Path("/app/container-transfer-marker").read_text()
    verifier_id = os.environ["MODAL_TASK_ID"]
    assert development_id != verifier_id, "Verifier reused the development container"
    assert not Path("/tmp/undeclared-development-marker").exists()
    become_candidate()
    report = asyncio.run(check_resources())
    report.update(
        {
            "fresh_container": True,
            "declared_artifact_restored": True,
            "undeclared_marker_absent": True,
            "development_id": development_id,
            "verifier_id": verifier_id,
        }
    )
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
