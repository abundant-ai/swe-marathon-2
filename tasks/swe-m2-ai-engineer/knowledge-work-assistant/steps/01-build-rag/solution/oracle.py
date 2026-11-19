"""Install and exercise the step-1 baseline using only public inputs."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OracleContext:
    """Public workspace, sample corpus, and application interpreter."""

    app_root: Path
    corpus_path: Path
    python: Path


def install_application(context: OracleContext) -> None:
    """Copy the baseline application into its declared submission directory.

    Args:
        context: Destination workspace and interpreter; existing application
            files with the same names are replaced, unrelated files remain.
    """
    source = Path(__file__).resolve().parent / "app"
    context.app_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, context.app_root, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    launcher = context.app_root / "orange"
    launcher.write_text(f"#!{context.python}\nfrom cli import main\n\nif __name__ == '__main__':\n    main()\n")
    launcher.chmod(0o755)
    development = context.app_root / "dev"
    development.mkdir(exist_ok=True)
    (development / "PROGRESS.MD").write_text(
        "# Baseline progress\n\nInstalled BM25, Jina embedding retrieval, and RRF "
        "with top-20 results and RRF k=20. Generation uses iterative retrieve tool calls.\n"
        "Development smoke evaluation has not run yet.\n"
    )


def oracle(context: OracleContext) -> None:
    """Produce a working submission and run a small public development exercise.

    Uses an authored two-document corpus with known facts to test the real CLI,
    saves questions/references/answers/report in a version folder, then replaces
    the development index with the provided public sample. It never reads private
    evaluation inputs or writes a reward.

    Args:
        context: Only the application workspace, public corpus, and interpreter.

    Raises:
        subprocess.CalledProcessError: Ingestion or generation fails.
        ValueError: The development answers violate the CLI result contract.
    """
    install_application(context)
    version = context.app_root / "dev/v1"
    version.mkdir(parents=True, exist_ok=True)
    documents = [
        {"doc_id": "dev-release", "source_type": "document", "title": "Cedar release owner",
         "content": "The Cedar release owner is Ada Chen. The planned release date is November 30."},
        {"doc_id": "dev-followup", "source_type": "slack", "title": "Cedar rollout update",
         "content": "Ada Chen confirmed the Cedar release date changed to December 2 after testing."},
    ]
    questions = [
        {"question_id": 0, "question": "Who owns the Cedar release?", "reference_answer": "Ada Chen"},
        {"question_id": 1, "question": "What is the updated Cedar release date?", "reference_answer": "December 2"},
    ]
    (version / "corpus.json").write_text(json.dumps(documents, indent=2) + "\n")
    (version / "questions.json").write_text(json.dumps(questions, indent=2) + "\n")
    run_cli(context, ["ingest", "--path", str(version / "corpus.json"), "--refresh"])
    run_cli(context, ["answer", "--questions", str(version / "questions.json"),
                      "--output", str(version / "answers.json")])
    answers = json.loads((version / "answers.json").read_text())
    if not isinstance(answers, list) or len(answers) != len(questions):
        raise ValueError("Development CLI must return one answer per question")
    results = []
    for expected, actual in zip(questions, answers):
        correct = expected["reference_answer"].casefold() in actual["answer"].casefold()
        results.append({"question_id": expected["question_id"], "reference_present": correct})
    (version / "report.json").write_text(json.dumps({
        "method": "Case-insensitive reference substring; a smoke check, not a semantic accuracy estimate.",
        "results": results,
    }, indent=2) + "\n")
    run_cli(context, ["ingest", "--path", str(context.corpus_path), "--refresh"])
    with (context.app_root / "dev/PROGRESS.MD").open("a") as stream:
        stream.write("\nCompleted the development CLI exercise; see v1/report.json. "
                     "Replaced its index with the public company sample.\n")


def run_cli(context: OracleContext, arguments: list[str]) -> None:
    """Execute the installed public launcher and fail on command errors.

    Args:
        context: Installed application location.
        arguments: Public CLI arguments, without the executable name.
    """
    subprocess.run([str(context.app_root / "orange"), *arguments], cwd=context.app_root, check=True)


def main() -> None:
    """Adapt Harbor's solve.sh invocation to the typed oracle context.

    --install-only supports offline author checks; the default also runs the
    development exercise and ingests the public sample using the supplied models.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-root", type=Path, default=Path("/app"))
    parser.add_argument("--corpus", type=Path, default=Path("/data/corpus.json"))
    parser.add_argument("--install-only", action="store_true")
    arguments = parser.parse_args()
    context = OracleContext(arguments.app_root.resolve(), arguments.corpus.resolve(), Path(sys.executable))
    if arguments.install_only:
        install_application(context)
    else:
        oracle(context)


if __name__ == "__main__":
    main()
