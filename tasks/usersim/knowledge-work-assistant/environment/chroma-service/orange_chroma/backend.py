"""Adapt Chroma 1.5.9's Rust vectors to its HTTP serializer's ndarray contract."""

from typing import Any

import numpy as np
from chromadb.api.rust import RustBindingsAPI
from chromadb.api.types import GetResult, QueryResult
from overrides import override


class HttpRustAPI(RustBindingsAPI):
    """Keep the pinned Rust store while normalizing requested vector outputs."""

    @override(check_signature=False)
    def _get(self, *args: Any, **kwargs: Any) -> GetResult:
        """Read records using the upstream signature and normalize vector rows.

        Args:
            args: Positional arguments forwarded unchanged to RustBindingsAPI._get.
            kwargs: Collection, filter, pagination and include arguments from Chroma.

        Returns:
            Original result with ndarray vectors expected by Chroma's HTTP serializer.
        """
        result = super()._get(*args, **kwargs)
        if result["embeddings"] is not None:
            result["embeddings"] = np.asarray(result["embeddings"])
        return result

    @override(check_signature=False)
    def _query(self, *args: Any, **kwargs: Any) -> QueryResult:
        """Run upstream vector search and normalize optional returned embeddings.

        Args:
            args: Positional arguments forwarded unchanged to RustBindingsAPI._query.
            kwargs: Query, filter and result options already bounded by HTTP policy.

        Returns:
            Original result with ndarray vectors in each requested result group.
        """
        result = super()._query(*args, **kwargs)
        if result["embeddings"] is not None:
            result["embeddings"] = [np.asarray(group) for group in result["embeddings"]]
        return result
