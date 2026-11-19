"""Local-only Responses service and installer for oracle contract testing."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock, Thread
from typing import Iterator
from contextlib import contextmanager

from pydantic import JsonValue

from task_paths import TASK_ROOT
from verifier.application.client import ApplicationClient

SOLUTION = TASK_ROOT / "steps/01-build-rag/solution"


class ModelServer(ThreadingHTTPServer):
    """A stateless two-search assistant; records requests for call-chain assertions."""

    requests: list[dict[str, JsonValue]]
    request_lock: Lock
    answer_mode: str
    search_rounds: int


class ModelHandler(BaseHTTPRequestHandler):
    """Serve deterministic tool calls and answers over the actual HTTP boundary."""

    server: ModelServer

    def do_POST(self) -> None:
        """Run two retrieval rounds, then cite exact excerpts returned by the app.

        This checks transport and orchestration without claiming model quality.
        Each decision depends only on this request's history, allowing concurrency.
        """
        if self.headers.get("Authorization") != "Bearer controlled-no-secret":
            self.send_error(401, "Application credential alias was not used")
            return
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        with self.server.request_lock:
            self.server.requests.append(payload)
        outputs = [row for row in payload["input"] if row.get("type") == "function_call_output"]
        if len(outputs) < self.server.search_rounds and payload.get("tools") and payload.get("tool_choice") != "none":
            query = next(row["content"] for row in payload["input"] if row.get("role") == "user") if not outputs else "Cedar followup"
            if isinstance(query, list):
                query = " ".join(block.get("text", "") for block in query)
            item = {"type": "function_call", "id": f"fc-{len(outputs)}", "status": "completed",
                    "name": "retrieve", "call_id": f"call-{len(outputs)}",
                    "arguments": json.dumps({"query": query, "retrieval_method": "hybrid" if not outputs else "bm25"})}
        else:
            evidence = json.loads(outputs[0]["output"])
            draft = {"answer": " ".join(row["quote"] for row in evidence) or "No evidence found.",
                     "evidence_ids": [row["evidence_id"] for row in evidence]}
            if self.server.answer_mode == "fabricated_citation":
                draft["evidence_ids"] = ["invented-evidence"]
            item = {"type": "message", "id": "message-test", "status": "completed", "role": "assistant",
                    "content": [{"type": "output_text", "text": json.dumps(draft), "annotations": []}]}
        status = "incomplete" if self.server.answer_mode == "incomplete" else "completed"
        response = json.dumps({
            "id": "response-test", "object": "response", "created_at": 1,
            "model": payload["model"], "status": status, "output": [item], "error": None,
            "incomplete_details": {"reason": "max_output_tokens"} if status == "incomplete" else None,
            "usage": {"input_tokens": 10, "output_tokens": 10, "total_tokens": 20},
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, format: str, *args: object) -> None:
        """Suppress fixture HTTP logs so pytest output contains only test evidence.

        Args:
            format: Base server's diagnostic template, intentionally unused.
            args: Diagnostic values, intentionally unused.
        """


@contextmanager
def model_service() -> Iterator[ModelServer]:
    """Start and clean up a loopback-only controlled Responses endpoint.

    Yields:
        Server with an ephemeral port and thread-safe request history.
    """
    server = ModelServer(("127.0.0.1", 0), ModelHandler)
    server.requests = []
    server.request_lock = Lock()
    server.answer_mode = "normal"
    server.search_rounds = 2
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@dataclass(frozen=True)
class InstalledOracle:
    """Independent installed application and controlled endpoint."""

    app: ApplicationClient
    server: ModelServer


def install_oracle(root: Path, server: ModelServer) -> InstalledOracle:
    """Exercise the real installer, then point public settings at local test models.

    Args:
        root: Empty temporary workspace; no developer application files are used.
        server: Controlled Responses endpoint with no production credential.

    Returns:
        Subprocess adapter using real SQLite/Chroma and deterministic model doubles.
    """
    subprocess.run([sys.executable, str(SOLUTION / "oracle.py"), "--app-root", str(root), "--install-only"], check=True)
    resources = root / "test-resources.json"
    resources.write_text(json.dumps({"generation": {
        "model": "controlled-model", "base_url": f"http://127.0.0.1:{server.server_port}/v1",
        "credential_env": "ORANGE_OPENAI_API_KEY",
    }}))
    config_path = root / "oracle-config.json"
    config = json.loads(config_path.read_text())
    config["resources_path"] = str(resources)
    config_path.write_text(json.dumps(config))
    app = ApplicationClient(root, environment={
        "PYTHONPATH": str(TASK_ROOT / "checks/fixtures/oracle_models"),
        "ORANGE_OPENAI_API_KEY": "controlled-no-secret",
        "OPENAI_API_KEY": "wrong-harness-key", "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1", "TOKENIZERS_PARALLELISM": "false",
    })
    return InstalledOracle(app, server)
