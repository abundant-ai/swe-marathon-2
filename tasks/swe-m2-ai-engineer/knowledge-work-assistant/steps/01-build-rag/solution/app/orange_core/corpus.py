"""Stream a public JSON array without holding every document body in memory."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from orange_core.retrieval import Document


def read_documents(path: Path) -> Iterator[Document]:
    """Validate and yield JSON-array records with memory bounded by one record.

    Args:
        path: UTF-8 JSON array of public corpus objects.

    Yields:
        Validated document objects in file order.

    Raises:
        ValueError: JSON syntax, record structure, or trailing input is invalid.
    """
    decoder = json.JSONDecoder()
    buffer = ""
    eof = False
    with path.open(encoding="utf-8") as stream:
        def refill() -> None:
            """Append a bounded input block and remember end of file."""
            nonlocal buffer, eof
            chunk = stream.read(65536)
            buffer += chunk
            eof = not chunk

        def skip_space() -> None:
            """Consume whitespace, reading further blocks when necessary."""
            nonlocal buffer
            buffer = buffer.lstrip()
            while not buffer and not eof:
                refill()
                buffer = buffer.lstrip()

        skip_space()
        if not buffer.startswith("["):
            raise ValueError("Corpus must be a JSON array")
        buffer = buffer[1:]
        skip_space()
        if not buffer.startswith("]"):
            while True:
                while True:
                    try:
                        value, consumed = decoder.raw_decode(buffer)
                        break
                    except json.JSONDecodeError:
                        if eof:
                            raise
                        refill()
                yield Document.model_validate(value)
                buffer = buffer[consumed:]
                skip_space()
                if buffer.startswith("]"):
                    break
                if not buffer.startswith(","):
                    raise ValueError("Expected comma between corpus records")
                buffer = buffer[1:]
                skip_space()
        buffer = buffer[1:]
        skip_space()
        if buffer:
            raise ValueError("Unexpected data after corpus array")
