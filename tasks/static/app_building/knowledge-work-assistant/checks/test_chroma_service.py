"""Exercise the protected service using real clients and adversarial HTTP calls."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import chromadb
import httpx
import pytest
from chroma_support import chroma_service
from orange_chroma.policy import COLLECTIONS


def test_read_limits_and_pagination(chroma_endpoint: dict[str, str]) -> None:
    """Enforce limits on all read forms while retaining complete paginated access.

    Args:
        chroma_endpoint: Fresh process running the exact production service.
    """
    host, port = (
        chroma_endpoint["ORANGE_CHROMA_HOST"],
        int(chroma_endpoint["ORANGE_CHROMA_PORT"]),
    )
    client = chromadb.HttpClient(host=host, port=port)
    collection = client.create_collection("documents", embedding_function=None)
    ids = [str(i) for i in range(250)]
    collection.add(ids=ids, documents=ids, embeddings=[[1.0, 0.0]] * len(ids))
    assert len(collection.get()["ids"]) == 100
    pages = [
        collection.get(limit=100, offset=offset)["ids"] for offset in (0, 100, 200)
    ]
    assert {identity for page in pages for identity in page} == set(ids)
    assert len(collection.peek(limit=100)["ids"]) == 100
    assert (
        sum(
            map(
                len,
                collection.query(query_embeddings=[[1.0, 0.0]] * 2, n_results=50)[
                    "ids"
                ],
            )
        )
        == 100
    )
    base = f"http://{host}:{port}"
    route = f"{COLLECTIONS}/{collection.id}"
    with httpx.Client(base_url=base, trust_env=False) as http:
        for endpoint, payload in [
            ("get", {"limit": 101}),
            ("get", {"limit": -1}),
            ("get", {"limit": True}),
            ("get", {"limit": 100.5}),
            ("get", {"ids": ids[:101]}),
            ("query", {"query_embeddings": [[1.0, 0.0]] * 2, "n_results": 51}),
            ("query", {"query_embeddings": [[1.0, 0.0]] * 101, "n_results": 1}),
        ]:
            assert http.post(f"{route}/{endpoint}", json=payload).status_code == 422
        assert len(http.post(f"{route}/get", json={"limit": None}).json()["ids"]) == 100
        assert http.get(COLLECTIONS + "?limit=101").status_code == 422
        # Client-side settings and arbitrary headers do not change service policy.
        assert (
            http.post(
                f"{route}/get",
                headers={"CHROMA_MAX_READ_RECORDS": "9999"},
                json={"limit": 9999},
            ).status_code
            == 422
        )
        assert collection.count() == 250
        assert (
            sum(
                map(
                    len,
                    collection.query(
                        query_embeddings=[[1.0, 0.0]],
                        n_results=100,
                        include=["embeddings"],
                    )["embeddings"],
                )
            )
            == 100
        )


@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", "/api/v2/reset"),
        ("POST", "/api/v1/reset"),
        ("GET", "/api/v1/collections"),
        ("GET", "/openapi.json"),
        ("POST", "/api/v2/tenants"),
        ("POST", COLLECTIONS + "/example/search"),
        ("GET", COLLECTIONS.replace("default_database", "another_database")),
    ],
)
def test_no_alternative_admin_or_read_route(
    chroma_endpoint: dict[str, str], method: str, path: str
) -> None:
    """Deny uncapped APIs, alternate namespaces, and administration before routing.

    Args:
        chroma_endpoint: Isolated service endpoint.
        method: Attempted HTTP method.
        path: Bypass route absent from the supported API.
    """
    base = f"http://{chroma_endpoint['ORANGE_CHROMA_HOST']}:{chroma_endpoint['ORANGE_CHROMA_PORT']}"
    response = httpx.request(method, base + path, json={}, trust_env=False)
    assert response.status_code == 422


def test_ten_concurrent_readers(chroma_endpoint: dict[str, str]) -> None:
    """Keep each concurrent request bounded without cross-request result mixing.

    Args:
        chroma_endpoint: Fresh shared service with a single small collection.
    """
    client = chromadb.HttpClient(
        host=chroma_endpoint["ORANGE_CHROMA_HOST"],
        port=int(chroma_endpoint["ORANGE_CHROMA_PORT"]),
    )
    collection = client.create_collection("documents", embedding_function=None)
    collection.add(ids=[str(i) for i in range(200)], embeddings=[[1.0, 0.0]] * 200)
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(collection.get, limit=100) for _ in range(10)]
        assert all(len(future.result()["ids"]) == 100 for future in futures)


def test_service_restart_and_fresh_instance(tmp_path: Path) -> None:
    """Persist data across service restarts without leaking it into a fresh trial.

    Args:
        tmp_path: Parent of independent development and evaluation stores.
    """
    for iteration in range(2):
        with chroma_service(tmp_path / "development") as endpoint:
            client = chromadb.HttpClient(
                host=endpoint["ORANGE_CHROMA_HOST"],
                port=int(endpoint["ORANGE_CHROMA_PORT"]),
            )
            if iteration == 0:
                collection = client.create_collection(
                    "documents", embedding_function=None
                )
                collection.add(ids=["dev-only"], embeddings=[[1.0, 0.0]])
            assert client.get_collection("documents").count() == 1
    with chroma_service(tmp_path / "evaluation") as endpoint:
        client = chromadb.HttpClient(
            host=endpoint["ORANGE_CHROMA_HOST"],
            port=int(endpoint["ORANGE_CHROMA_PORT"]),
        )
        assert client.count_collections() == 0


def test_oversized_body_rejected(chroma_endpoint: dict[str, str]) -> None:
    """Reject oversized bodies before writes or expensive database parsing.

    Args:
        chroma_endpoint: Fresh production service with its 16 MiB body limit.
    """
    base = f"http://{chroma_endpoint['ORANGE_CHROMA_HOST']}:{chroma_endpoint['ORANGE_CHROMA_PORT']}"
    response = httpx.post(
        base + COLLECTIONS, content=b" " * (16777216 + 1), trust_env=False
    )
    assert response.status_code == 413
