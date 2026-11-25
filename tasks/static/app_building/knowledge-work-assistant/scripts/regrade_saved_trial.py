"""Run Harbor verification on saved outputs and retain service diagnostics."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from harbor.models.trial.config import EnvironmentConfig, SourceTrialConfig, TrialConfig
from harbor.models.trial.result import TrialResult
from harbor.trial.trial import Trial


async def regrade(source: Path, task: Path, output: Path, name: str) -> None:
    """Replay saved artifacts without starting an agent or changing its code.

    Args:
        source: Complete recorded trial, including artifact metadata.
        task: Packaged task with the corrected verifier configuration.
        output: Parent directory for the new Harbor trial record.
        name: Unique replay name, also used to identify its Modal sandbox.

    Raises:
        RuntimeError: Harbor cannot finish verification or collect diagnostics.
    """
    import modal

    recorded = TrialResult.model_validate_json((source / "result.json").read_text())
    config = TrialConfig(
        task={"path": task},
        trial_name=name,
        trials_dir=output,
        agent=recorded.config.agent,
        artifacts=recorded.config.artifacts,
        environment=EnvironmentConfig(type="modal", delete=False),
        source_trial=SourceTrialConfig(
            action="regrade", type="local", trial_id=recorded.id, path=source
        ),
    )
    trial = await Trial.create(config)
    try:
        result = await trial.run()
        print("Verification reward:", result.verifier_result, flush=True)
        if result.exception_info is not None:
            raise RuntimeError(result.exception_info.exception_message)
    finally:
        app = await modal.App.lookup.aio("__harbor__")
        async for sandbox in modal.Sandbox.list.aio(app_id=app.app_id):
            tags = await sandbox.get_tags.aio()
            if tags.get("harbor.session_id") not in {
                f"{name}__verifier__trial",
                f"{name}__verifier__01-build-rag",
            }:
                continue
            try:
                # This is the supplied embedding service's log, not process env.
                process = await sandbox.exec.aio(
                    "cat",
                    "/tmp/orange-jina-10001/server.log",
                    timeout=30,
                )
                log = await process.stdout.read.aio()
                (output / name / "jina-server.log").write_text(log)
                process = await sandbox.exec.aio(
                    "cat",
                    "/logs/verifier/generation.json",
                    timeout=30,
                )
                answers = await process.stdout.read.aio()
                if await process.wait.aio() == 0:
                    (output / name / "candidate-evaluation-answers.json").write_text(
                        json.dumps(json.loads(answers)["answers"], indent=2)
                    )
            finally:
                await sandbox.terminate.aio()


def main() -> None:
    """Parse explicit replay locations; credentials come only from process env."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    os.environ.setdefault("MODAL_ENVIRONMENT", "testing")
    asyncio.run(
        regrade(
            args.source.resolve(), args.task.resolve(), args.output.resolve(), args.name
        )
    )


if __name__ == "__main__":
    main()
