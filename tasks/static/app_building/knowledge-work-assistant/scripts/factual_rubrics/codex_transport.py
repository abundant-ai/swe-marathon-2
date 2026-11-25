"""Temporary author-only structured judging through the authenticated Codex CLI."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import tempfile
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

OutputT = TypeVar("OutputT", bound=BaseModel)


class CodexTransport:
    """Tool-disabled, read-only, ephemeral calls with schema validation and traces."""

    def __init__(
        self, output: Path, *, model: str, reasoning: str, timeout: int, retries: int
    ) -> None:
        """Configure explicit temporary calibration policy without changing runtime.

        Args:
            output: Private author directory for inputs, schemas, outputs, and events.
            model: Explicit Codex model ID recorded with every call.
            reasoning: Explicit reasoning effort supported by that model.
            timeout: Per-attempt wall-clock deadline in seconds.
            retries: Number of repairs allowed for invalid structured output.
        """
        if timeout <= 0 or retries < 0:
            raise ValueError("Timeout must be positive and retries nonnegative")
        self.output = output.resolve()
        self.output.mkdir(parents=True, exist_ok=True)
        self.model, self.reasoning, self.timeout, self.retries = (
            model,
            reasoning,
            timeout,
            retries,
        )

    async def run(
        self,
        instructions: str,
        payload: str,
        schema: type[OutputT],
        validator: Callable[[OutputT], OutputT],
        label: str,
    ) -> tuple[OutputT, str]:
        """Run a fresh constrained Codex request and validate its final object.

        Args:
            instructions: Reviewed role and judge instructions, supplied separately.
            payload: JSON-escaped question data; never read from the checkout by tools.
            schema: Pydantic output class passed through --output-schema.
            validator: Request-specific identity, grounding, or evidence validator.
            label: Safe diagnostic prefix; a UUID prevents concurrent collisions.

        Returns:
            Validated output and local call ID. Output failures get bounded repairs;
            transport failures stop immediately and preserve private diagnostics.

        Raises:
            RuntimeError: CLI failure, tool use, missing output, or exhausted repairs.
            TimeoutError: An attempt exceeds the explicit wall-clock budget.
        """
        identity = f"{label}-{uuid.uuid4().hex}"
        directory = self.output / identity
        directory.mkdir()
        schema_path = directory / "schema.json"
        schema_path.write_text(json.dumps(schema.model_json_schema()))
        (directory / "input.json").write_text(
            json.dumps(
                {
                    "instructions": instructions,
                    "payload": payload,
                    "model": self.model,
                    "reasoning": self.reasoning,
                },
                indent=2,
            )
        )
        repair = ""
        for attempt in range(self.retries + 1):
            target = directory / f"output-{attempt}.json"
            with tempfile.TemporaryDirectory(prefix="rubric-codex-") as temporary:
                command = [
                    "codex",
                    "exec",
                    "--ignore-user-config",
                    "--ephemeral",
                    "--sandbox",
                    "read-only",
                    "--skip-git-repo-check",
                    "-C",
                    temporary,
                    "-m",
                    self.model,
                    "-c",
                    f"model_reasoning_effort={json.dumps(self.reasoning)}",
                    "-c",
                    "project_doc_max_bytes=0",
                    "-c",
                    'web_search="disabled"',
                    "-c",
                    f"developer_instructions={json.dumps(instructions + ' Use no tools. Return only the structured final object.')}",
                ]
                for feature in (
                    "shell_tool",
                    "unified_exec",
                    "shell_snapshot",
                    "apps",
                    "browser_use",
                    "computer_use",
                    "multi_agent",
                    "multi_agent_v2",
                ):
                    command.extend(["--disable", feature])
                command.extend(
                    [
                        "--output-schema",
                        str(schema_path),
                        "--output-last-message",
                        str(target),
                        "--json",
                        "-",
                    ]
                )
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    start_new_session=True,
                )
                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate((payload + repair).encode()), self.timeout
                    )
                except BaseException:
                    if process.returncode is None:
                        os.killpg(process.pid, signal.SIGTERM)
                        await process.wait()
                    raise
            (directory / f"events-{attempt}.jsonl").write_bytes(stdout)
            (directory / f"stderr-{attempt}.txt").write_bytes(stderr)
            if process.returncode or not target.exists():
                raise RuntimeError(
                    f"Codex transport failed; diagnostic call {identity}, exit {process.returncode}"
                )
            events = [
                json.loads(line)
                for line in stdout.decode().splitlines()
                if line.strip()
            ]
            forbidden = {
                "command_execution",
                "mcp_tool_call",
                "web_search",
                "file_change",
                "collab_tool_call",
            }
            if any(event.get("item", {}).get("type") in forbidden for event in events):
                raise RuntimeError(f"Codex judge used tools; rejecting call {identity}")
            try:
                result = validator(schema.model_validate_json(target.read_text()))
                return result, identity
            except (ValueError, TypeError) as error:
                (directory / f"validation-{attempt}.txt").write_text(str(error))
                repair = (
                    "\n\nYour previous output failed validation. Return a complete corrected object. Error: "
                    + str(error)
                )
        raise RuntimeError(
            f"Codex output repairs exhausted; diagnostic call {identity}"
        )


def identity_output(value: OutputT) -> OutputT:  # noqa: UP047 - Keep the existing generic callable signature.
    """Return a schema-validated object when no extra request checks are needed.

    Args:
        value: Parsed provider output.

    Returns:
        The unchanged object.
    """
    return value
