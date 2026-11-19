"""Download pinned sources and prepare the fixed pretokenized training/eval mix."""

import argparse
import json
import sys
import time
from pathlib import Path

from transformers import AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from preparation.build import build  # noqa: E402
from preparation.sources import tokenizer_directory  # noqa: E402
from titans_task import data  # noqa: E402


def validate(root: Path) -> dict[str, int]:
    """Read every artifact through the runtime loader and count real scored inputs.

    Args:
        root: Prepared artifact root containing the saved tokenizer.

    Returns:
        Verified input-token totals for each split.
    """
    tokenizer = AutoTokenizer.from_pretrained(root / "tokenizer", local_files_only=True, use_fast=True)
    result = {"train": data.input_count(data.training_tokens(root, tokenizer))}
    for split in ("public", "private"):
        total = 0
        for _, record in data.evaluation_files(root, split, tokenizer):
            ids = data.evaluation_tokens(root, split, record, tokenizer)
            total += sum(labels.numel() for _, labels in data.packed_batches(ids))
        result[split] = total
    return result


def main() -> None:
    """Build into a fresh staging directory and publish only fully validated data."""
    task = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=task / "experiment/data")
    parser.add_argument("--cache-dir", type=Path, default=task / "experiment/source-cache")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        print(json.dumps(validate(args.output_dir), indent=2))
        return
    if args.output_dir.exists():
        raise FileExistsError(args.output_dir)
    staging = args.output_dir.with_name(args.output_dir.name + ".preparing")
    staging.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_directory(args.cache_dir),
                                              local_files_only=True, use_fast=True)
    if len(tokenizer) != 32000:
        raise ValueError("The fixed scratch task requires the 32K Llama-2 tokenizer")
    tokenizer.model_max_length = 10 ** 12
    report = build(staging, args.cache_dir, tokenizer)
    report["verified_input_tokens"] = validate(staging)
    report["elapsed_seconds"] = time.perf_counter() - started
    staging.rename(args.output_dir)
    report_path = args.output_dir.with_name(args.output_dir.name + ".report.json")
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
