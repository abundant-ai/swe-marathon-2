"""Attribute blocks (PART 4) and attribute merging (PART 9 §15 A3,
CARVE-P4-002, PART 10 §1)."""

from .chars import ASCII_PUNCT, is_ascii_digit, is_ascii_letter


def _is_ident_start(c):
    return is_ascii_letter(c) or c == "_"


def _is_ident_char(c):
    return is_ascii_letter(c) or is_ascii_digit(c) or c == "_" or c == "-"


def _is_explicit_start(c):
    return is_ascii_letter(c) or is_ascii_digit(c) or c == "_"


_UNQUOTED_EXCLUDE = set("}|\"'\\ \t\n\r")


class Attrs:
    """Ordered attribute list.  Entries are [lower_name, display_name, value];
    the class entry's value is a list of class tokens."""

    __slots__ = ("entries",)

    def __init__(self):
        self.entries = []

    def copy(self):
        a = Attrs()
        a.entries = [
            [e[0], e[1], list(e[2]) if e[0] == "class" else e[2]] for e in self.entries
        ]
        return a

    def __bool__(self):
        return bool(self.entries)

    def _find(self, lname):
        for e in self.entries:
            if e[0] == lname:
                return e
        return None

    def add(self, name, value):
        lname = name.lower()
        if lname == "class":
            toks = _class_tokens(value)
            e = self._find("class")
            if e is None:
                e = ["class", name, []]
                self.entries.append(e)
            for t in toks:
                if t not in e[2]:
                    e[2].append(t)
            return
        e = self._find(lname)
        if e is None:
            self.entries.append([lname, name, value])
        else:
            e[2] = value

    def merge(self, other):
        """Merge `other` (later in source order) into self."""
        if other is None:
            return self
        for e in other.entries:
            if e[0] == "class":
                ce = self._find("class")
                if ce is None:
                    ce = ["class", e[1], []]
                    self.entries.append(ce)
                for t in e[2]:
                    if t not in ce[2]:
                        ce[2].append(t)
            else:
                se = self._find(e[0])
                if se is None:
                    self.entries.append([e[0], e[1], e[2]])
                else:
                    se[2] = e[2]
        return self

    def get(self, lname, default=None):
        e = self._find(lname)
        if e is None:
            return default
        if e[0] == "class":
            return list(e[2])
        return e[2]

    def has(self, lname):
        return self._find(lname) is not None

    def remove(self, lname):
        self.entries = [e for e in self.entries if e[0] != lname]

    def classes(self):
        e = self._find("class")
        return list(e[2]) if e else []

    def id(self):
        e = self._find("id")
        return e[2] if e else None

    def __repr__(self):
        return f"Attrs({self.entries!r})"


def _class_tokens(value):
    toks = [t for t in _split_ascii_ws(value) if t]
    if not toks:
        return [value]
    return toks


def _split_ascii_ws(value):
    out = []
    cur = []
    for ch in value:
        if ch in " \t\n\x0c\r":
            if cur:
                out.append("".join(cur))
                cur = []
        else:
            cur.append(ch)
    if cur:
        out.append("".join(cur))
    return out


def items_to_attrs(items, attrs=None):
    if attrs is None:
        attrs = Attrs()
    for name, value in items:
        attrs.add(name, value)
    return attrs


def parse_attr_block(s, i, end=None, allow_empty=False, multiline=False):
    """Parse one attribute block at s[i] == '{'.

    Returns (items, j) with j the index after the closing '}', or None.
    items is a list of (name, value) in source order; `.x` gives
    ('class', 'x'), `#x` gives ('id', 'x'), `:tag` gives ('lang', tag),
    a boolean gives (name, '').  An empty block returns ([], j) only when
    allow_empty.
    """
    if end is None:
        end = len(s)
    if i >= end or s[i] != "{":
        return None
    j = i + 1
    items = []

    def skip_pad(j, allow_nl):
        # spaces, then (multiline) at most one newline + whitespace run, then spaces
        while j < end and s[j] == " ":
            j += 1
        if allow_nl and j < end and s[j] == "\n":
            j += 1
            while j < end and (s[j] == " " or s[j] == "\t"):
                j += 1
            # a blank line ends the block: the next char must not be another newline
            if j < end and s[j] == "\n":
                return None
        return j

    j = skip_pad(j, multiline)
    if j is None:
        return None
    if j < end and s[j] == "}":
        if allow_empty and not multiline:
            # empty block: only spaces
            inner = s[i + 1 : j]
            if all(c == " " for c in inner):
                return [], j + 1
        return None
    while True:
        if j >= end:
            return None
        c = s[j]
        if c == "#":
            k = j + 1
            if k < end and _is_explicit_start(s[k]):
                k += 1
                while k < end and _is_ident_char(s[k]):
                    k += 1
                items.append(("id", s[j + 1 : k]))
                j = k
            else:
                return None
        elif c == ".":
            k = j + 1
            if k < end and _is_explicit_start(s[k]):
                k += 1
                while k < end and _is_ident_char(s[k]):
                    k += 1
                items.append(("class", s[j + 1 : k]))
                j = k
            else:
                return None
        elif c == ":":
            k = j + 1
            # optional language tag: subtags of 1-8 ASCII alnum joined by '-'
            if k < end and (is_ascii_letter(s[k]) or is_ascii_digit(s[k])):
                while True:
                    st = k
                    while k < end and (is_ascii_letter(s[k]) or is_ascii_digit(s[k])):
                        k += 1
                    if k - st < 1 or k - st > 8:
                        return None
                    if (
                        k < end
                        and s[k] == "-"
                        and k + 1 < end
                        and (is_ascii_letter(s[k + 1]) or is_ascii_digit(s[k + 1]))
                    ):
                        k += 1
                        continue
                    break
            items.append(("lang", s[j + 1 : k]))
            j = k
        elif _is_ident_start(c):
            k = j + 1
            while k < end and _is_ident_char(s[k]):
                k += 1
            name = s[j:k]
            if k < end and s[k] == "=":
                k += 1
                if k >= end:
                    return None
                q = s[k]
                if q == '"' or q == "'":
                    k += 1
                    buf = []
                    while True:
                        if k >= end:
                            return None
                        ch = s[k]
                        if ch == q:
                            k += 1
                            break
                        if ch == "\n" or ch == "\r":
                            return None
                        if ch == "\\" and k + 1 < end and s[k + 1] in ASCII_PUNCT:
                            buf.append(s[k + 1])
                            k += 2
                            continue
                        buf.append(ch)
                        k += 1
                    items.append((name, "".join(buf)))
                else:
                    st = k
                    while k < end and s[k] not in _UNQUOTED_EXCLUDE:
                        k += 1
                    if k == st:
                        return None
                    items.append((name, s[st:k]))
                j = k
            else:
                if name[0] == "_":
                    return None
                items.append((name, ""))
                j = k
        else:
            return None
        # after an attribute: separator or end
        if j >= end:
            return None
        c = s[j]
        if c == "}":
            return items, j + 1
        if c == " ":
            j2 = skip_pad(j, multiline)
            if j2 is None:
                return None
            if j2 < end and s[j2] == "}":
                return items, j2 + 1
            j = j2
            continue
        if multiline and c == "\n":
            j2 = skip_pad(j, True)
            if j2 is None:
                return None
            if j2 < end and s[j2] == "}":
                return items, j2 + 1
            j = j2
            continue
        return None


def parse_attr_run(s, i, end=None, allow_empty=False):
    """Parse a glued run of inline attribute blocks at s[i].

    Returns (Attrs, j) or None when no valid block starts at i.
    With allow_empty (bracketed spans), `{}` / `{ }` are members that
    contribute nothing."""
    if end is None:
        end = len(s)
    attrs = None
    j = i
    count = 0
    while j < end and s[j] == "{":
        r = parse_attr_block(s, j, end, allow_empty=allow_empty)
        if r is None:
            break
        items, j2 = r
        if attrs is None:
            attrs = Attrs()
        items_to_attrs(items, attrs)
        j = j2
        count += 1
    if count == 0:
        return None
    return attrs, j
