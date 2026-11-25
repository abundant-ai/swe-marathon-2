"""Separate trusted judge criteria from parameterized evidence messages."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from string import Formatter


def split_prompt(template: str) -> tuple[str, str]:
    """Separate Markdown instructions from the input template.

    Args:
        template: Judge Markdown with one Inputs or Questions section boundary.

    Returns:
        Static instructions and the unrendered evidence section. A Questions
        heading is retained so the author's input layout stays intact.

    Raises:
        ValueError: The boundary is missing, repeated, or leaves an empty section.
    """
    boundaries = list(re.finditer(r"(?m)^## (Inputs|Questions)[ \t]*\n", template))
    if len(boundaries) != 1:
        raise ValueError("Judge template requires one Inputs or Questions boundary")
    boundary = boundaries[0]
    instructions = template[: boundary.start()].strip()
    if not instructions or not template[boundary.end() :].strip():
        raise ValueError("Judge template requires nonempty instructions and inputs")
    start = boundary.end() if boundary[1] == "Inputs" else boundary.start()
    return instructions, template[start:].strip()


def render_inputs(template: str, values: Mapping[str, object]) -> str:
    """Insert JSON-encoded evidence into named placeholders exactly once.

    Args:
        template: Evidence section using plain named fields without format options.
        values: Exact field mapping; nested records and lists retain their JSON shape.

    Returns:
        User-message content with literal braces and newlines safely JSON-encoded.

    Raises:
        ValueError: Fields are missing, unused, or use unsupported formatting.
        TypeError: An evidence value cannot be serialized as JSON.
    """
    fields: set[str] = set()
    for _, name, spec, conversion in Formatter().parse(template):
        if name is not None:
            if not name.isidentifier() or spec or conversion:
                raise ValueError("Judge input placeholders must be plain names")
            fields.add(name)
    if fields != values.keys():
        raise ValueError("Judge input values must match template fields exactly")
    encoded = {
        key: json.dumps(value, ensure_ascii=False, allow_nan=False)
        for key, value in values.items()
    }
    return template.format_map(encoded)
