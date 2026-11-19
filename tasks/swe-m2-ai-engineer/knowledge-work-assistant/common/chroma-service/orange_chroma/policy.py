"""Pure request validation for the public subset of Chroma's v2 API."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReadPolicy:
    """Trusted service limits, parsed once at startup."""

    max_records: int
    max_body_bytes: int


class RejectedRequest(ValueError):
    """The request is outside the service's permitted API or read budget."""


COLLECTIONS = "/api/v2/tenants/default_tenant/databases/default_database/collections"
IDENTITY = "/api/v2/auth/identity"


def operation(method: str, path: str) -> str:
    """Resolve an allowlisted operation before Chroma sees the request.

    Args:
        method: HTTP method normalized by the ASGI server.
        path: Decoded request path; alternate tenants and admin routes are denied.

    Returns:
        Read operation name, or ``other`` for permitted non-record operations.

    Raises:
        RejectedRequest: The route or method is not explicitly exposed.
    """
    path = path.rstrip("/")
    if method == "GET" and path in {
        "/api/v2", "/api/v2/heartbeat", "/api/v2/version",
        "/api/v2/pre-flight-checks", IDENTITY,
        "/api/v2/tenants/default_tenant",
        "/api/v2/tenants/default_tenant/databases/default_database",
        COLLECTIONS + "_count",
    }:
        return "other"
    if path == COLLECTIONS and method in {"GET", "POST"}:
        return "list" if method == "GET" else "other"
    if re.fullmatch(re.escape(COLLECTIONS) + r"/[^/]+", path) and method in {"GET", "PUT", "DELETE"}:
        return "other"
    match = re.fullmatch(re.escape(COLLECTIONS) + r"/[^/]+/(get|query|add|update|upsert|delete|count)", path)
    if match and method == ("GET" if match[1] == "count" else "POST"):
        return match[1]
    raise RejectedRequest("This Chroma endpoint is not available")


def positive_integer(value: Any, name: str, maximum: int) -> int:
    """Validate a strict positive integer against a trusted maximum.

    Args:
        value: Decoded JSON value; booleans and floats are not accepted.
        name: Field name included in the public error.
        maximum: Inclusive upper bound.

    Returns:
        Validated integer, unchanged.

    Raises:
        RejectedRequest: The type or range is invalid.
    """
    if type(value) is not int or not 1 <= value <= maximum:
        raise RejectedRequest(f"{name} must be an integer between 1 and {maximum}")
    return value


def bounded_payload(kind: str, payload: dict[str, Any], policy: ReadPolicy) -> dict[str, Any]:
    """Apply record limits before database work, preserving caller-owned input.

    Args:
        kind: Allowlisted endpoint operation.
        payload: Parsed JSON request object.
        policy: Immutable limits supplied by the service container.

    Returns:
        A new payload with bounded get/query limits. Query batches share one budget.

    Raises:
        RejectedRequest: A limit, batch, or ID list exceeds the request budget.
    """
    result = dict(payload)
    if kind == "get":
        limit = result.get("limit")
        result["limit"] = positive_integer(policy.max_records if limit is None else limit, "limit", policy.max_records)
        ids = result.get("ids")
        if ids is not None and (not isinstance(ids, list) or len(ids) > policy.max_records):
            raise RejectedRequest(f"ids may contain at most {policy.max_records} entries; paginate reads")
    elif kind == "query":
        vectors = result.get("query_embeddings")
        if not isinstance(vectors, list) or not 1 <= len(vectors) <= policy.max_records:
            raise RejectedRequest("query_embeddings must be a nonempty bounded batch")
        result["n_results"] = positive_integer(result.get("n_results", 10), "n_results", policy.max_records // len(vectors))
    return result
