"""Output normalisation: rule lists compare as sets, JSON compares parsed with keys sorted.

These are the only two liberties the brief grants: the order of keys inside a JSON object, and
the order of the rules listed for a decision. Everything else is compared as printed.
"""

from __future__ import annotations

import json
import re

RULES = re.compile(rb"\[rules: ([0-9, ]+)\]")


def _sorted_rules(match: re.Match[bytes]) -> bytes:
    numbers = sorted(int(n) for n in match.group(1).split(b","))
    return b"[rules: " + b", ".join(str(n).encode() for n in numbers) + b"]"


def _walk(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: (
                sorted(item)
                if key == "determining_rules" and isinstance(item, list)
                else _walk(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_walk(item) for item in value]
    return value


def normalise(stdout: bytes, fmt: str) -> str:
    """Return the comparable form of one run's standard output.

    JSON output that does not parse is compared as text, so a malformed report fails
    against a well-formed expected one instead of raising.
    """
    if fmt == "json":
        try:
            parsed = json.loads(stdout.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return stdout.decode("utf-8", "replace")
        return json.dumps(_walk(parsed), sort_keys=True)
    return RULES.sub(_sorted_rules, stdout).decode("utf-8", "replace")
