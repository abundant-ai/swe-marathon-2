"""Check a staged Kev checkpoint and score it with kev.benchmark. Exit 0 scored, 2 unusable checkpoint, 3 broken suites."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import torch

BASE = "Qwen/Qwen3.5-0.8B-Base"
BASE_REVISION = "dc7cdfe2ee4154fa7e30f5b51ca41bfa40174e68"
SUITES = {
    "transfer_test": ("/opt/kev/evals/v4/transfer-v4", "test"),
    "transfer_dev": ("/opt/kev/evals/v4/transfer-v4", "development"),
    "decision_test": ("/opt/kev/evals/v7/decision-v7", "test"),
}


def suites_intact() -> bool:
    from kev.suite import load_split

    try:
        for path, split in SUITES.values():
            load_split(path, split, allow_test=True)
    except (OSError, ValueError) as exc:
        print(f"suite check failed: {exc}", file=sys.stderr)
        return False
    return True


def checkpoint_facts(model: Path) -> dict | None:
    meta = torch.load(model / "head.pt", map_location="cpu", weights_only=True)
    adapter = json.loads((model / "adapter_config.json").read_text(encoding="utf-8"))
    if not isinstance(meta, dict) or not isinstance(adapter, dict):
        print("head.pt or adapter_config.json is not a mapping", file=sys.stderr)
        return None
    facts = {
        "base": meta.get("base"),
        "base_revision": meta.get("base_revision"),
        "weights": meta.get("weights", "lora"),
        "lora": meta.get("lora"),
        "head_dim": meta.get("head_dim"),
        "temperature": meta.get("temperature"),
        "adapter_r": adapter.get("r"),
        "adapter_bytes": (model / "adapter_model.safetensors").stat().st_size,
    }
    if (
        facts["base"] != BASE
        or facts["base_revision"] != BASE_REVISION
        or facts["weights"] != "lora"
    ):
        print(
            f"checkpoint is not a LoRA checkpoint on {BASE}@{BASE_REVISION}: {facts}",
            file=sys.stderr,
        )
        return None
    return facts


def main(model: Path, out: Path) -> int:
    if not suites_intact():
        return 3
    try:
        facts = checkpoint_facts(model)
    except Exception as exc:  # noqa: BLE001  (any failure to read the candidate's files is the candidate's)
        print(
            f"cannot read the checkpoint: {type(exc).__name__}: {exc}", file=sys.stderr
        )
        return 2
    if facts is None:
        return 2
    (out / "checkpoint.json").write_text(json.dumps(facts, indent=1))
    for name, (suite, split) in SUITES.items():
        command = [
            sys.executable,
            "-I",
            "-m",
            "kev.benchmark",
            "--run",
            str(model),
            "--suite",
            suite,
            "--out",
            str(out / name),
            "--device",
            "cuda",
        ]
        command += ["--allow-test"] if split == "test" else ["--split", split]
        print("running", " ".join(command), flush=True)
        if subprocess.run(command, check=False).returncode != 0:
            print(f"kev.benchmark failed on {name}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]), Path(sys.argv[2])))
