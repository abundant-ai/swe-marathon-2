"""A policy with its history taken away: the temporal conditions rewritten to constants.

Selection asks what a program that never looks at the history would print for a replay case:
one that drops every temporal condition (`when temporal { … }` and `unless temporal { … }`
removed, an inline `temporal { … }` read as `true`), and one that reads every temporal condition
as false (`when temporal { … }` becomes `when { false }`, `unless temporal { … }` is removed, an
inline `temporal { … }` is `false`). The release build replays the rewritten policies over the
same trace; a case whose recorded answer one of them reproduces is one such a program passes.

The rewrite works on the policy text: string literals and comments are skipped, and a block is
the text between its `{` and the `}` that closes it.
"""

from __future__ import annotations

VARIANTS = ("drop", "false")


def _skip(text: str, i: int) -> int:
    """The index after whitespace and comments starting at `i`."""
    n = len(text)
    while i < n:
        if text[i].isspace():
            i += 1
        elif text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j + 1
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
        else:
            break
    return i


def _string_end(text: str, i: int) -> int:
    """The index after the string literal that opens at `i`."""
    n = len(text)
    i += 1
    while i < n:
        if text[i] == "\\":
            i += 2
        elif text[i] == '"':
            return i + 1
        else:
            i += 1
    return n


def _close(text: str, i: int) -> int | None:
    """The index after the `}` that closes the `{` at `i`; None when none does."""
    depth = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == '"':
            i = _string_end(text, i)
            continue
        if text.startswith("//", i) or text.startswith("/*", i):
            i = _skip(text, i)
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return None


def _word(text: str, i: int) -> tuple[str, int]:
    j = i
    while j < len(text) and (text[j].isalnum() or text[j] == "_"):
        j += 1
    return text[i:j], j


def rewrite(text: str, variant: str) -> str | None:
    """The policy with its temporal conditions replaced as `variant` says; None when it has none
    (it then already ignores the history) or when a block does not close."""
    out: list[str] = []
    i = 0
    n = len(text)
    found = False
    prev_word = ""
    while i < n:
        c = text[i]
        if c == '"':
            j = _string_end(text, i)
            out.append(text[i:j])
            i, prev_word = j, ""
            continue
        if text.startswith("//", i) or text.startswith("/*", i):
            j = _skip(text, i)
            out.append(text[i:j])
            i = j
            continue
        if c.isalpha() or c == "_":
            word, j = _word(text, i)
            if word in ("when", "unless"):
                k = _skip(text, j)
                nxt, k2 = _word(text, k)
                if nxt == "temporal":
                    k3 = _skip(text, k2)
                    if k3 < n and text[k3] == "{":
                        end = _close(text, k3)
                        if end is None:
                            return None
                        found = True
                        if word == "when" and variant == "false":
                            out.append("when { false }")
                        i, prev_word = end, ""
                        continue
            if word == "temporal" and prev_word not in ("def", "when", "unless"):
                k = _skip(text, j)
                if k < n and text[k] == "{":
                    end = _close(text, k)
                    if end is None:
                        return None
                    found = True
                    out.append("true" if variant == "drop" else "false")
                    i, prev_word = end, ""
                    continue
            out.append(word)
            i, prev_word = j, word
            continue
        out.append(c)
        if not c.isspace():
            prev_word = ""
        i += 1
    return "".join(out) if found else None
