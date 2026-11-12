"""Install the pinned Jina snapshot while building the trusted task image."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from huggingface_hub import snapshot_download

from jina import MODEL_ID, MODEL_PATH, MODEL_REVISION


def main() -> None:
    """Download weights, adapters, tokenizer, and custom code before evaluation.

    All adapters are included because the pinned loader opens each of them, even
    for text retrieval. Runtime inference reads the resulting local directory.
    Download errors fail the image build instead of deferring work until grading.
    """
    snapshot_download(
        repo_id=MODEL_ID, revision=MODEL_REVISION, local_dir=MODEL_PATH,
        ignore_patterns=["*.png", ".gitattributes"],
    )
    model = Path(MODEL_PATH)
    shutil.rmtree(model / ".cache", ignore_errors=True)
    (model / "PROVENANCE.json").write_text(json.dumps({
        "model": MODEL_ID, "revision": MODEL_REVISION,
        "modality": "text", "task": "retrieval", "dimensions": 1024,
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
