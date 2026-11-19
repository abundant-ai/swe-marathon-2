"""Start a credential-free Modal GPU worker for a locally persisted oracle index."""

from __future__ import annotations

import time
from pathlib import Path

import httpx
import modal


def start_gpu(environment: Path, token: str, modal_environment: str) -> tuple[modal.Sandbox, str]:
    """Launch the pinned task image with authenticated SGLang ingress.

    Args:
        environment: Task Docker build context, excluding author scripts and tests.
        token: Random embedding-only bearer token, unrelated to provider credentials.
        modal_environment: Existing Modal environment selected by the run config.

    Returns:
        Live sandbox and HTTPS endpoint. The caller must terminate the sandbox.

    Raises:
        RuntimeError: SGLang does not become ready within five minutes.
    """
    app = modal.App.lookup("enterprise-rag-testing", environment_name=modal_environment, create_if_missing=True)
    image = modal.Image.from_dockerfile(environment / "Dockerfile", context_dir=environment)
    command = (
        "import os; from jina import server_command; command=server_command(); "
        "command[command.index('--host')+1]='0.0.0.0'; "
        "command.extend(['--api-key',os.environ['EMBEDDING_TOKEN']]); "
        "os.execv(command[0],command)"
    )
    with modal.enable_output():
        sandbox = modal.Sandbox.create(
            "/opt/runtime/bin/python", "-c", command, app=app, image=image,
            environment_name=modal_environment, gpu="L4", cpu=4, memory=16384,
            timeout=86400, encrypted_ports=[30000], block_network=True,
            env={"EMBEDDING_TOKEN": token, "OMP_NUM_THREADS": "4"},
        )
    try:
        endpoint = sandbox.tunnels()[30000].url
        deadline = time.monotonic() + 300
        with httpx.Client(headers={"Authorization": "Bearer " + token}, timeout=5) as connection:
            while time.monotonic() < deadline:
                try:
                    if connection.get(endpoint + "/health").is_success:
                        return sandbox, endpoint
                except httpx.HTTPError:
                    pass
                time.sleep(1)
        raise RuntimeError(f"SGLang failed to start in sandbox {sandbox.object_id}")
    except BaseException:
        sandbox.terminate()
        raise
