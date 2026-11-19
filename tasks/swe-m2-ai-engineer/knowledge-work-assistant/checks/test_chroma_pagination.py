"""Exercise the storage probe above SQLite's usual parameter ceiling."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import os
from pathlib import Path

from task_paths import TASK_ROOT


def test_probe_reads_large_document_and_chunk_collections(tmp_path: Path, chroma_endpoint: dict[str, str]) -> None:
    """Verify complete body hashes and chunk owners across bounded read pages.

    Args:
        tmp_path: Isolated Chroma store containing more than 32,766 records per
            collection, reproducing the full-corpus verifier's previous failure.
        chroma_endpoint: Production HTTP service enforcing 100-record read pages.
    """
    build = """
import sys
import os
import chromadb
client = chromadb.HttpClient(host=os.environ['ORANGE_CHROMA_HOST'], port=int(os.environ['ORANGE_CHROMA_PORT']))
docs = client.create_collection('documents', embedding_function=None)
chunks = client.create_collection('chunks', embedding_function=None)
for offset in range(0, 33000, 1000):
    ids = [str(i) for i in range(offset, offset + 1000)]
    docs.add(ids=ids, documents=ids, embeddings=[[1.0, 0.0]] * len(ids))
    chunks.add(ids=ids, metadatas=[{'doc_id': i} for i in ids], embeddings=[[1.0, 0.0]] * len(ids))
"""
    subprocess.run([sys.executable, "-I", "-c", build, str(tmp_path)], check=True,
                   capture_output=True, text=True, timeout=180)
    probe = TASK_ROOT / "steps/01-build-rag/tests/verifier/probes/test_chroma.py"
    result = subprocess.run([sys.executable, "-I", str(probe), str(tmp_path)],
                            check=True, capture_output=True, text=True, timeout=180)
    snapshot = json.loads(result.stdout)
    expected = {str(i): hashlib.sha256(str(i).encode()).hexdigest() for i in range(33000)}
    assert snapshot["body_digest"] == hashlib.sha256(json.dumps(expected, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert snapshot["document_count"] == len(expected)
    assert snapshot["invalid_chunk_owners"] == 0
    assert snapshot["chunk_count"] == len(expected)
