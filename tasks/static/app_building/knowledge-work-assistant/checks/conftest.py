"""Make author-side verifier modules importable without packaging candidate code."""

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

TASK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK_ROOT / "scripts"))

sys.path.insert(0, str(TASK_ROOT / "tests"))
sys.path.insert(0, str(TASK_ROOT / "common/chroma-service"))


@pytest.fixture
def chroma_endpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[dict[str, str]]:
    """Provide a fresh protected HTTP database to tests that exercise storage.

    Args:
        tmp_path: Test-specific data directory, removed by pytest.
        monkeypatch: Restores endpoint environment variables after the test.

    Yields:
        Connection settings for the service, never production credentials.
    """
    from chroma_support import chroma_service

    with chroma_service(tmp_path / "chroma-service") as endpoint:
        for key, value in endpoint.items():
            monkeypatch.setenv(key, value)
        yield endpoint
