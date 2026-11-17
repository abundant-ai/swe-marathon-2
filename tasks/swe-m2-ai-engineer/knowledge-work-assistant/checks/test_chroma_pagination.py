"""Exercise the storage probe above SQLite's usual parameter ceiling."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from task_paths import TASK_ROOT


def test_probe_reads_large_document_and_chunk_collections(tmp_path: Path) -> None:
    """Verify complete body hashes and chunk owners across bounded read pages.

    Args:
        tmp_path: Isolated Chroma store containing more than 32,766 records per
            collection, reproducing the full-corpus verifier's previous failure.
    """
    build = """
import sys
import chromadb
client = chromadb.PersistentClient(path=sys.argv[1])
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
    assert snapshot["hashes"] == expected
    assert set(snapshot["chunk_owners"]) == set(expected)
    assert len(snapshot["chunk_owners"]) == len(expected)
