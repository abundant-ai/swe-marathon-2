"""Inline parser (PART 3, PART 9 §9 inline pairing).

The P1 atom scan and the P2 pairing reading are performed in one
left-to-right pass per region: at each position the atom table is tried
first, then the pairing steps R1-R5; atoms are opaque to pairing.
"""

import re
import unicodedata
from bisect import bisect_left

from .attrs import parse_attr_run
from .chars import (
    ASCII_PUNCT,
    is_alnum,
    is_cc,
    is_cf,
    is_grapheme_extender,
    is_unicode_ws,
)
from .nodes import (
    NBSP,
    Autolink,
    Bracket,
    Code,
    Comment,
    CriticComment,
    Crossref,
    Elem,
    Esc,
    Ext,
    HardBreak,
    Image,
    InlineNote,
    Link,
    Literal,
    Math,
    NoteRef,
    RawInline,
    RefLink,
    Smart,
    SoftBreak,
    Span,
    Subst,
    Text,
    Verbatim,
)

BARE = "/*_~="
BRACE_MARKS = "/*_~=^,+-"
KIND_ELEM = {
    "/": "em",
    "*": "strong",
    "_": "u",
    "~": "s",
    "=": "mark",
    "^": "sup",
    ",": "sub",
    "+": "ins",
    "-": "del",
}
MAX_DEPTH = 199

_EMAIL_RE = re.compile(r"[A-Za-z0-9.\-_+]+@[A-Za-z0-9.\-_+]+\.[A-Za-z]+>")
_SCHEME_RE = re.compile(r"[A-Za-z][A-Za-z0-9+\-.]*:")
_URL_ASCII = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    "-._~:/?#[]@!$&'()*+,;=%"
)
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_\-]*")
_FORMAT_RE = re.compile(r"\{=([A-Za-z_][A-Za-z0-9_\-]*)\}")
_EXPLICIT_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_\-]*")
_LANG_INFO_RE = re.compile(r"[A-Za-z0-9\-_+#./]+")
_LINES_RE = re.compile(r"([1-9][0-9]*)-([1-9][0-9]*)")


def _url_char(c):
    if c in _URL_ASCII:
        return True
    if ord(c) < 128:
        return False
    return not (is_unicode_ws(c) or is_cf(c) or is_cc(c))


_SPECIAL_CHARS = "\\`$!<{^[:%/*_~=\n"
_SPECIAL = set(_SPECIAL_CHARS)
_PLAIN_RE = re.compile("[^" + re.escape(_SPECIAL_CHARS) + "]+")
_PLAIN_BY_KIND = {}


def _plain_re_for(kind):
    r = _PLAIN_BY_KIND.get(kind)
    if r is None:
        r = re.compile("[^" + re.escape(_SPECIAL_CHARS + kind) + "]+")
        _PLAIN_BY_KIND[kind] = r
    return r


class Delim:
    __slots__ = ("ch", "combined", "idx", "pos")

    def __init__(self, ch, pos, idx, combined=False):
        self.ch = ch
        self.pos = pos
        self.idx = idx
        self.combined = combined


class _Restart(Exception):
    pass


class InlineParser:
    def __init__(
        self, src, in_note=False, in_cell=False, line_block=False, literal=None
    ):
        self.s = src
        self.literal = literal or ()
        self.n = len(src)
        self.in_note = in_note
        self.in_cell = in_cell
        self.line_block = line_block
        self.removed_end = {}  # end -> start of removed (comment) ranges
        self.removed_start = {}  # start -> end
        self.nested_cache = {}
        self.bracket_cache = {}
        self.depth = 0
        self.used_delims = set()
        self.tail_cache = {}
        self.tok_pos = {}

    def find_tok(self, tok, i, end):
        """self.s.find(tok, i, end) through a per-token position index, so
        repeated searches for a missing closer stay linear overall."""
        lst = self.tok_pos.get(tok)
        if lst is None:
            lst = []
            s = self.s
            k = s.find(tok)
            while k >= 0:
                lst.append(k)
                k = s.find(tok, k + 1)
            self.tok_pos[tok] = lst
        idx = bisect_left(lst, i)
        if idx < len(lst):
            k = lst[idx]
            if k + len(tok) <= end:
                return k
        return -1

    # ------------------------------------------------------------ helpers

    def prev_char(self, i):
        """Source character before position i, skipping removed comment
        ranges.  None at the start of the block."""
        j = i
        while True:
            st = self.removed_end.get(j)
            if st is None:
                break
            j = st
        if j <= 0:
            return None
        return self.s[j - 1]

    def next_char(self, i, end=None):
        """Source character at position i (the char after a delimiter),
        skipping braced comments and removed ranges."""
        s = self.s
        if end is None:
            end = self.n
        j = i
        while j < end:
            e = self.removed_start.get(j)
            if e is not None:
                j = e
                continue
            if (
                s[j] == "{"
                and j + 1 < end
                and s[j + 1] == "%"
                and j not in self.literal
                and not (j + 2 < end and is_grapheme_extender(s[j + 2]))
            ):
                k = self.find_tok("%}", j + 2, end)
                if k >= 0:
                    j = k + 2
                    continue
            return s[j]
        return None

    def backtick_run(self, i):
        s = self.s
        j = i
        n = self.n
        while j < n and s[j] == "`":
            j += 1
        return j - i

    def find_code_close(self, i, ln, limit):
        """Find a backtick run of exactly ln starting at or after i (< limit)."""
        s = self.s
        j = i
        while True:
            k = s.find("`", j, limit)
            if k < 0:
                return -1
            m = k
            while m < limit and s[m] == "`":
                m += 1
            if m - k == ln:
                return k
            j = m

    def parse_title(self, i, end):
        s = self.s
        q = s[i]
        j = i + 1
        buf = []
        while j < end:
            c = s[j]
            if c == q:
                return "".join(buf), j + 1
            if c == "\\" and j + 1 < end and s[j + 1] in ASCII_PUNCT:
                buf.append(s[j + 1])
                j += 2
                continue
            buf.append(c)
            j += 1
        return None

    def parse_link_tail(self, i, end):
        """s[i] == '(' : returns (dest, title, end_index) or None."""
        key = (i, end)
        c = self.tail_cache.get(key, 0)
        if c != 0:
            return c
        r = self._parse_link_tail(i, end)
        self.tail_cache[key] = r
        return r

    def _parse_link_tail(self, i, end):
        s = self.s
        j = i + 1
        if j >= end:
            return None
        c = s[j]
        if c == " " or c == ")":
            if c == " " and j + 1 < end and (s[j + 1] == '"' or s[j + 1] == "'"):
                t = self.parse_title(j + 1, end)
                if t is not None:
                    title, k = t
                    while k < end and s[k] == " ":
                        k += 1
                    if k < end and s[k] == ")":
                        return "", title, k + 1
            k = j
            while k < end and s[k] == " ":
                k += 1
            if k < end and s[k] == ")":
                return "", None, k + 1
            return None
        depth = 0
        buf = []
        opens = []
        while j < end:
            c = s[j]
            if c == "\\" and j + 1 < end and s[j + 1] in "()\\":
                buf.append(s[j + 1])
                j += 2
                continue
            if c == "(":
                depth += 1
                opens.append(j)
            elif c == ")":
                if depth == 0:
                    break
                depth -= 1
                opens.pop()
            elif is_unicode_ws(c):
                break
            buf.append(c)
            j += 1
        if opens:
            # a nested `(` that never closed fails as a tail opener too
            tc = self.tail_cache
            if j >= end:
                for o in opens:
                    tc[(o, end)] = None
            else:
                for o in opens[:-1]:
                    tc[(o, end)] = None
        if j >= end or not buf:
            return None
        dest = "".join(buf)
        if s[j] == ")":
            return dest, None, j + 1
        if s[j] == " " and j + 1 < end and (s[j + 1] == '"' or s[j + 1] == "'"):
            t = self.parse_title(j + 1, end)
            if t is not None:
                title, k = t
                while k < end and s[k] == " ":
                    k += 1
                if k < end and s[k] == ")":
                    return dest, title, k + 1
        return None

    def quoted_end(self, j, end):
        """A quoted run opening at s[j] (`"` or `'`): the index after its
        closing quote, or -1.  A backslash takes the next character with it;
        the run stops at a newline (CARVE-P4-006)."""
        s = self.s
        q = s[j]
        k = j + 1
        while k < end and s[k] != "\n":
            c = s[k]
            if c == "\\":
                k += 2
                continue
            if c == q:
                return k + 1
            k += 1
        return -1

    def include_literal(self, i, end):
        """A directive-shaped `{{ ... }}` at s[i] (PART 6 include_directive)
        whose literal fallback reads none of its tokens (CARVE-P6-001): a
        bare path with a bare `@code`, an `@lines` value that is no valid
        range, or a `@code:` value that is no language_info token.  Returns
        the index after its `}}`, or -1 when the span is read as ordinary
        inline content."""
        s = self.s
        if not s.startswith("{{", i):
            return -1

        def spaces(k):
            while k < end and s[k] == " ":
                k += 1
            return k

        j = spaces(i + 2)
        if j == i + 2 or j >= end:
            return -1
        if s[j] == '"':
            # an unterminated quote falls back to the bare reading, which
            # cannot begin with a quote
            j = self.quoted_end(j, end)
            if j < 0:
                return -1
            bare = False
        else:
            k = j
            while k < end and s[k] not in "#@} \n":
                k += 1
            if k == j:
                return -1
            j = k
            bare = True
        k = spaces(j)
        if k < end and s[k] == "#":
            m = _EXPLICIT_RE.match(s, k + 1, end)
            if not m:
                return -1
            j = m.end()
        options = []
        while True:
            k = spaces(j)
            if k >= end or s[k] != "@":
                break
            m = _IDENT_RE.match(s, k + 1, end)
            if not m:
                return -1
            name, j, value = m.group(0), m.end(), None
            if j < end and s[j] == ":":
                if j + 1 < end and s[j + 1] in "\"'":
                    q = self.quoted_end(j + 1, end)
                    if q < 0:
                        return -1
                    value = s[j + 2 : q - 1]
                    j = q
                else:
                    k = j + 1
                    while k < end and s[k] not in "}|\"'\\@ \t\n":
                        k += 1
                    if k == j + 1:
                        return -1
                    value = s[j + 1 : k]
                    j = k
            options.append((name, value))
        k = spaces(j)
        if k == j or not s.startswith("}}", k):
            return -1
        for name, value in options:
            if name == "code":
                if value is None:
                    if bare:
                        return k + 2
                elif not _LANG_INFO_RE.fullmatch(value):
                    return k + 2
            elif name == "lines":
                r = _LINES_RE.fullmatch(value or "")
                if r is None or int(r.group(1)) > int(r.group(2)):
                    return k + 2
        return -1

    def parse_autolink(self, i, end):
        """s[i] == '<'.  Returns ('xref', id, j) / ('url', body, j) /
        ('email', body, j) or None."""
        s = self.s
        if s.startswith("</#", i):
            j = i + 3
            while j < end and s[j] not in "> \n":
                j += 1
            if j > i + 3 and j < end and s[j] == ">":
                return "xref", s[i + 3 : j], j + 1
            return None
        m = _SCHEME_RE.match(s, i + 1, end)
        if m:
            j = m.end()
            st = j
            while j < end and _url_char(s[j]):
                j += 1
            if j > st and j < end and s[j] == ">":
                return "url", s[i + 1 : j], j + 1
        m = _EMAIL_RE.match(s, i + 1, end)
        if m:
            return "email", s[i + 1 : m.end() - 1], m.end()
        return None

    def find_bracket_close(self, i, end, code_limit, alt=False):
        """s[i] == '['.  Index of the balanced ']' or -1.  One stack-based
        scan records the outcome of every bracket it passes."""
        # A result found with a scan bounded by E holds for any bound e <= E
        # that still contains it: every lookahead the scan made before the
        # match ended before it, and a failed one fails with less room too.
        cache = self.bracket_cache
        key = (i, alt)
        r = cache.get(key)
        if r is not None:
            bound, j = r
            if end <= bound and (j < 0 or j < end):
                return j
        s = self.s
        stack = []
        j = i
        res = -1
        while j < end:
            c = s[j]
            if c == "\\":
                if j + 1 < end and s[j + 1] in ASCII_PUNCT:
                    j += 2
                else:
                    j += 1
                continue
            if c == "`":
                ln = self.backtick_run(j)
                cl = self.find_code_close(j + ln, ln, code_limit)
                if cl < 0:
                    break
                j = cl + ln
                continue
            if c == "{" and j + 1 < end:
                c2 = s[j + 1]
                if (
                    c2 == "#" or (c2 == "%" and not alt and j not in self.literal)
                ) and not (j + 2 < end and is_grapheme_extender(s[j + 2])):
                    k = self.find_tok(c2 + "}", j + 2, end)
                    if k >= 0 and (c2 == "%" or k > j + 2):
                        j = k + 2
                        continue
            elif c == "<":
                a = self.parse_autolink(j, end)
                if a is not None:
                    j = a[2]
                    continue
            elif c == "[":
                stack.append(j)
            elif c == "]" and stack:
                o = stack.pop()
                cache[(o, alt)] = (end, j)
                if not stack:
                    res = j
                    break
                if j + 1 < end and s[j + 1] == "(":
                    t = self.parse_link_tail(j + 1, end)
                    if t is not None:
                        j = t[2]
                        continue
            j += 1
        for o in stack:
            cache[(o, alt)] = (end, -1)
        if res < 0:
            cache[key] = (end, -1)
        return res

    def find_ext_close(self, i, end):
        """i is just after ':name['.  Returns index of closing ']' or -1."""
        s = self.s
        depth = 0
        j = i
        first = -1
        while j < end:
            c = s[j]
            if c == "\\":
                if j + 1 < end and s[j + 1] in ASCII_PUNCT:
                    j += 2
                else:
                    j += 1
                continue
            if c == "[":
                depth += 1
            elif c == "]":
                if first < 0:
                    first = j
                if depth == 0:
                    return j
                depth -= 1
            j += 1
        return first

    # ------------------------------------------------------------ code spans

    def code_value(self, content, closed):
        if closed:
            if (
                len(content) >= 2
                and content[0] == " "
                and content[-1] == " "
                and content.strip(" ") != ""
            ):
                content = content[1:-1]
            return content
        # unclosed: the block's trailing whitespace is stripped
        if self.line_block:
            return content.rstrip(" \t")
        return content.rstrip(" \t\n")

    # ------------------------------------------------------------ entry

    def parse(self):
        nodes, _ = self.read(0, self.n, None, self.n, True, False)
        return nodes

    def read(self, start, end, kind, code_limit, run_start, mark_before):
        """Read the region [start, end).  For a nested braced reading, kind
        is its mark and the reading ends at the closer token `kind}`.

        Returns (nodes, (close_index, opaque_ranges)); close_index is -1 when
        the closer was not reached (nodes is then None for nested readings)."""
        bare_at = set()
        while True:
            rd = _Reader(
                self, start, end, kind, code_limit, run_start, mark_before, bare_at
            )
            try:
                return rd.run()
            except _Restart as r:
                if r.args[0] in bare_at:
                    raise
                bare_at.add(r.args[0])

    def read_nested(self, i, kind, end, code_limit):
        """Nested reading of a braced span whose content starts at i.
        Returns (close_index or -1 / -2, nodes, opaque_ranges)."""
        key = (i, kind, end)
        r = self.nested_cache.get(key)
        if r is not None:
            return r
        if self.find_tok(kind + "}", i, end) < 0:
            # no closer token of this kind anywhere ahead: the opener fails
            r = (-1, None, [])
            self.nested_cache[key] = r
            return r
        self.depth += 1
        try:
            if self.depth > MAX_DEPTH:
                # over the cap the whole spelling stays literal (PART 9 §22)
                r = (self.overcap_close(i, kind, end, code_limit), None, None)
            else:
                nodes, info = self.read(i, end, kind, code_limit, False, True)
                r = (info[0], nodes, info[1])
        finally:
            self.depth -= 1
        self.nested_cache[key] = r
        return r

    def nest_ok(self):
        """Whether a construct's content may open one more nesting level:
        the top inline run is level 1, so 199 spans nest in it (PART 9 §22,
        MAX_NESTING_DEPTH).  Past the cap a construct stays literal."""
        return self.depth < MAX_DEPTH

    def sub_region(
        self, st, en, code_limit, in_note=None, run_start=True, mark_before=False
    ):
        saved = self.in_note
        if in_note:
            self.in_note = True
        self.depth += 1
        try:
            nodes, _ = self.read(st, en, None, code_limit, run_start, mark_before)
        finally:
            self.in_note = saved
            self.depth -= 1
        return nodes

    def overcap_close(self, i, kind, end, code_limit):
        """Closer token of a braced span over the nesting cap, found by one
        iterative scan rather than by nested readings: a braced opener with
        a closer token ahead nests, atoms and comments are skipped.  Returns
        the index of its `kind}` or -1."""
        s = self.s
        stack = [kind]
        j = i
        while j < end:
            c = s[j]
            if c == "\\":
                j += 2 if j + 1 < end and s[j + 1] in ASCII_PUNCT else 1
                continue
            if c == "`":
                ln = self.backtick_run(j)
                cl = self.find_code_close(j + ln, ln, code_limit)
                if cl < 0:
                    return -1
                j = cl + ln
                continue
            if c == "{" and j + 1 < end:
                c2 = s[j + 1]
                if c2 in "%#":
                    k = self.find_tok(c2 + "}", j + 2, end)
                    if k >= 0:
                        j = k + 2
                        continue
                elif c2 in BRACE_MARKS and self.find_tok(c2 + "}", j + 2, end) >= 0:
                    stack.append(c2)
                    j += 2
                    continue
            if c == stack[-1] and j + 1 < end and s[j + 1] == "}":
                stack.pop()
                if not stack:
                    return j
                j += 2
                continue
            j += 1
        return -1

    # ------------------------------------------------------------ atoms

    def code_atom(self, rd, i, prefix):
        """Code span (or math / literal when prefix is given) whose backtick
        run starts at i.  Returns the index after it."""
        s = self.s
        end = rd.end
        code_limit = rd.code_limit
        ln = self.backtick_run(i)
        close = self.find_code_close(i + ln, ln, code_limit)
        st = prefix[2] if prefix is not None else i
        if close < 0:
            content = s[i + ln : code_limit]
            val = self.code_value(content, False)
            node = self.make_code(prefix, val)
            rd.emit(node, st, code_limit)
            rd.opaque.append((st, code_limit))
            return code_limit
        content = s[i + ln : close]
        val = self.code_value(content, True)
        j = close + ln
        if prefix is None:
            m = _FORMAT_RE.match(s, j, end)
            if m:
                node = RawInline(m.group(1), val)
                rd.emit(node, st, m.end())
                rd.opaque.append((st, m.end()))
                return m.end()
        node = self.make_code(prefix, val)
        j2 = self.attach(node, j, end)
        rd.emit(node, st, j2)
        rd.opaque.append((st, j2))
        return j2

    def attach(self, node, j, end):
        """R3: a glued attribute run at j attaches to node."""
        s = self.s
        if j < end and s[j] == "{":
            r = parse_attr_run(s, j, end)
            if r is not None:
                attrs, j2 = r
                if node.attrs is None:
                    node.attrs = attrs
                else:
                    node.attrs.merge(attrs)
                return j2
        return j

    def make_code(self, prefix, val):
        if prefix is None:
            return Code(val)
        if prefix[0] == "math":
            return Math(val, prefix[1])
        return Literal(val)

    def bracket(self, i, end, code_limit, image):
        """Bracket run at s[i] == '['.  Returns (node, end_index) or None
        (the `[` / `![` is text)."""
        s = self.s
        st = i - 1 if image else i
        # note reference
        if not image and not self.in_note and i + 1 < end and s[i + 1] == "^":
            k = i + 2
            while k < end and s[k] != "]" and s[k] != "\n":
                k += 1
            if k < end and s[k] == "]" and k > i + 2:
                label = s[i + 2 : k]
                node = NoteRef(label, None, None)
                j = self.attach(node, k + 1, end)
                node.src = s[i:j]
                return node, j
        q = self.find_bracket_close(i, end, code_limit, alt=image)
        if q < 0:
            return None
        t = q + 1
        nx = s[t] if t < end else None
        if nx == "(":
            tail = self.parse_link_tail(t, end)
            if tail is not None:
                dest, title, j = tail
                if not image and not self.nest_ok():
                    j = self.attach(Link([], dest, title), j, end)
                    return Verbatim(s[st:j]), j
                if image:
                    node = Image(self.alt_text(i + 1, q), dest, title)
                else:
                    node = Link(self.sub_region(i + 1, q, code_limit), dest, title)
                j = self.attach(node, j, end)
                return node, j
        elif nx == "[":
            k = t + 1
            label = None
            collapsed = False
            lend = k
            if k < end and s[k] == "]":
                collapsed = True
                text = s[i + 1 : q]
                if "\n" not in text and (not image or text != ""):
                    label = text
                    lend = k + 1
            else:
                m = k
                while m < end and s[m] != "]" and s[m] != "\n":
                    m += 1
                if m < end and s[m] == "]" and m > k and s[k] != "@":
                    label = s[k:m]
                    lend = m + 1
            if label is None:
                # a declining `[t][...]` is the verbatim source run
                m2 = k
                while m2 < end and s[m2] != "]":
                    m2 += 1
                if m2 < end and (
                    collapsed or (m2 > k and (s[k] == "@" or "\n" in s[k:m2]))
                ):
                    return Verbatim(s[st : m2 + 1]), m2 + 1
                if collapsed:
                    return Verbatim(s[st : k + 1]), k + 1
            if label is not None:
                if not image and not self.nest_ok():
                    j = self.attach(Span([], None), lend, end)
                    return Verbatim(s[st:j]), j
                if image:
                    node = RefLink(
                        None,
                        label,
                        collapsed,
                        None,
                        None,
                        image=True,
                        alt=self.alt_text(i + 1, q),
                    )
                else:
                    node = RefLink(
                        self.sub_region(i + 1, q, code_limit),
                        label,
                        collapsed,
                        None,
                        None,
                    )
                node.text_label = s[i + 1 : q]
                j = self.attach(node, lend, end)
                node.src = s[st:j]
                return node, j
        elif nx == "{" and not image:
            r = parse_attr_run(s, t, end, allow_empty=True)
            if r is not None:
                attrs, j = r
                if not self.nest_ok():
                    return Verbatim(s[st:j]), j
                node = Span(
                    self.sub_region(i + 1, q, code_limit), attrs if attrs else None
                )
                return node, j
        if image:
            return None
        if not self.nest_ok():
            return Verbatim(s[st : q + 1]), q + 1
        node = Bracket(self.sub_region(i + 1, q, code_limit))
        return node, q + 1

    def alt_text(self, st, en):
        """Scalar alt text: source with escaped_char decoded."""
        s = self.s
        out = []
        j = st
        while j < en:
            c = s[j]
            if c == "\\" and j + 1 < en and s[j + 1] in ASCII_PUNCT:
                out.append(s[j + 1])
                j += 2
                continue
            out.append(c)
            j += 1
        return "".join(out)

    def find_combined_closer(self, j, end, kind):
        """Look ahead (outside atoms and formed nested spans) for the closer
        token `*/` of a combined opener whose `*` is at j-1."""
        s = self.s
        opener_end = j
        while j < end:
            c = s[j]
            if kind is not None and c == kind and j + 1 < end and s[j + 1] == "}":
                return False
            if c == "\\":
                j += 2
                continue
            if c == "`":
                ln = self.backtick_run(j)
                cl = self.find_code_close(j + ln, ln, end)
                if cl < 0:
                    return False
                j = cl + ln
                continue
            if c == "[":
                q = self.find_bracket_close(j, end, end)
                if q >= 0:
                    j = q + 1
                    continue
            if c == "<":
                a = self.parse_autolink(j, end)
                if a is not None:
                    j = a[2]
                    continue
            if c == "{" and j + 1 < end and s[j + 1] in "%#":
                k = self.find_tok(s[j + 1] + "}", j + 2, end)
                if k >= 0:
                    j = k + 2
                    continue
            if c == "{" and j + 1 < end and s[j + 1] in BRACE_MARKS:
                r = self.read_nested(j + 2, s[j + 1], end, end)
                if r[0] >= 0:
                    j = r[0] + 2
                    continue
            if (
                c == "*"
                and j + 1 < end
                and s[j + 1] == "/"
                and j != opener_end
                and self.is_combined_closer(j, end)
            ):
                return True
            j += 1
        return False

    def is_combined_closer(self, i, end):
        s = self.s
        b = self.prev_char(i)
        if b is None or b in " \t\n\r":
            return False
        a = s[i + 2] if i + 2 < end else None
        return not (a is not None and is_alnum(a))

    def comment_end(self, i, end, kind, slash_star, tilde=False, arrow_before=False):
        """End of a `%%` comment at i (CARVE-P9-041, CARVE-P9-042).  Inside a
        `{~` frame the comment runs to the frame's first raw `~}`, which
        still closes the frame unless the comment swallowed the frame's only
        arrow; after a `{~` that formed no frame the comment takes that
        `~}` with it."""
        nl = self.find_tok("\n", i, end)
        ce = end if nl < 0 else nl
        if kind == "~":
            k = self.find_tok("~}", i + 2, ce)
            if k >= 0:
                if not arrow_before and self.find_tok("~>", i + 2, k) >= 0:
                    return k + 2
                return k
        elif tilde:
            k = self.find_tok("~}", i + 2, ce)
            if k >= 0:
                return k + 2
        if kind is not None:
            k = self.find_tok(kind + "}", i + 2, ce)
            if k >= 0:
                ce = k
        if slash_star:
            k = self.find_tok("*/", i + 2, ce)
            if k >= 0:
                ce = k
        return ce

    def find_arrow(self, st, en, ranges):
        s = self.s
        j = st
        rs = sorted(ranges)
        ri = 0
        while j < en - 1:
            while ri < len(rs) and rs[ri][1] <= j:
                ri += 1
            if ri < len(rs) and rs[ri][0] <= j < rs[ri][1]:
                j = rs[ri][1]
                continue
            if s[j] == "\\":
                j += 2
                continue
            if s[j] == "~" and s[j + 1] == ">":
                return j
            j += 1
        return -1

    def braced(self, rd, i, mark):
        """R1 nested opener at s[i] == '{'.  Returns the index after the span
        (and its attribute run) or None if the opener fails."""
        end = rd.end
        code_limit = rd.code_limit
        close, nodes, inner_opaque = self.read_nested(i + 2, mark, end, code_limit)
        if close < 0 or close == i + 2:
            return None
        if nodes is None:
            # over the nesting cap: its closer closes no parent
            rd.emit(Verbatim(self.s[i : close + 2]), i, close + 2)
            rd.opaque.append((i, close + 2))
            return close + 2
        if mark == "~":
            arrow = self.find_arrow(i + 2, close, inner_opaque)
            if arrow >= 0:
                old = self.sub_region(
                    i + 2, arrow, code_limit, run_start=False, mark_before=True
                )
                new = self.sub_region(arrow + 2, close, code_limit, run_start=False)
                node = Subst(old, new)
                rd.emit(node, i, close + 2)
                rd.opaque.append((i, close + 2))
                return close + 2
        node = Elem(KIND_ELEM[mark], nodes)
        j = self.attach(node, close + 2, end)
        rd.emit(node, i, j)
        rd.opaque.append((i, j))
        return j


def finish(items):
    """Merge adjacent source-contiguous text nodes."""
    res = []
    for it in items:
        if isinstance(it, Text):
            if not it.s:
                continue
            if res and isinstance(res[-1], Text):
                prev = res[-1]
                if (
                    prev.start >= 0
                    and it.start == prev.start + len(prev.s)
                    and not it.at_start
                ):
                    res[-1] = Text(prev.s + it.s, prev.start, prev.at_start)
                    continue
        res.append(it)
    return res


class _Reader:
    """One left-to-right reading of a region (PART 9 §9 P1 + P2)."""

    def __init__(
        self, p, start, end, kind, code_limit, run_start, mark_before, bare_at
    ):
        self.p = p
        self.s = p.s
        self.start = start
        self.end = end
        self.kind = kind
        self.code_limit = code_limit
        self.run_start = run_start
        self.mark_before = mark_before
        self.bare_at = bare_at
        self.out = []
        self.stack = []
        self.lit = {}
        self.opaque = []
        self.ts = start
        self.at_start = True
        self.slash_star = False
        self.tilde_open = False

    # -- output helpers
    def flush(self, upto):
        if upto > self.ts:
            self.out.append(Text(self.s[self.ts : upto], self.ts, self.at_start))
            self.at_start = False
        self.ts = upto

    def emit(self, node, at, nxt):
        """Emit node whose source starts at `at`; text resumes at nxt."""
        self.flush(at)
        self.out.append(node)
        self.at_start = False
        self.ts = nxt

    # -- guards
    def can_open(self, d, pos):
        p = self.p
        a = p.next_char(pos + 1, self.end)
        if a is None or a in " \t\n\r" or a == d:
            return False
        if d == "=" and a == ">":
            return False
        if d == "=" and self.in_comparison(pos):
            return False
        b = p.prev_char(pos)
        if b is not None:
            exempt = False
            if pos == self.start and self.mark_before:
                exempt = True
            else:
                for e in self.stack:
                    if e.pos == pos - 1 or (e.combined and e.pos + 1 == pos - 1):
                        exempt = True
                        break
            if not exempt:
                if is_alnum(b) or b == d or b == "_":
                    return False
                if b == "/" and (d == "/" or d == "_"):
                    return False
        return True

    def can_close(self, d, pos):
        p = self.p
        b = p.prev_char(pos)
        if b is None or b in " \t\n\r":
            return False
        if pos == self.start:
            # nothing of this region precedes it
            return False
        if d == "=" and self.in_comparison(pos):
            return False
        a = p.next_char(pos + 1, self.end)
        return not (a is not None and is_alnum(a))

    def in_comparison(self, pos):
        """The `=` of `!=`, `<=`, `>=` is part of that symbol."""
        s = self.s
        if pos == 0:
            return False
        b = s[pos - 1]
        if b not in "!<>":
            return False
        if pos - 1 < self.ts:
            # the character was consumed by an escape or another construct
            return False
        if b == "<":
            a = s[pos + 1] if pos + 1 < len(s) else ""
            if a == "=" or a == ">":
                return False  # `<==` / `<=>` are arrows
        if b == ">":
            # `==>=`: the `>` belongs to an intact arrow
            used = self.p.used_delims
            if (
                pos >= 3
                and s[pos - 3 : pos] == "==>"
                and (pos - 2) not in used
                and (pos - 3) not in used
            ):
                return False
            if (
                pos >= 3
                and s[pos - 3 : pos] == "-->"
                and not (pos >= 4 and s[pos - 4] == "-")
            ):
                return False
            if pos >= 3 and s[pos - 3 : pos] == "<=>" and (pos - 2) not in used:
                return False
        return True

    def word_flanked(self, pos):
        s = self.s
        b = pos - 1
        while b >= 0 and is_grapheme_extender(s[b]):
            b -= 1
        if b < 0 or not is_alnum(s[b]):
            return False
        return not (pos + 1 >= len(s) or not is_alnum(s[pos + 1]))

    def note_literal(self, c, i):
        if self.word_flanked(i) and not self.in_social_name(i):
            self.lit.setdefault(c, []).append(i)

    def in_social_name(self, i):
        """Whether position i lies inside a mention or tag name."""
        s = self.s
        j = i - 1
        while j >= self.start and (s[j].isalnum() and s[j].isascii() or s[j] in "_-."):
            j -= 1
        if j < self.start or s[j] not in "@#":
            return False
        b = s[j - 1] if j > self.start else None
        glued = b is not None and b.isascii() and (b.isalnum() or b == "_")
        return not glued or any(e.pos == j - 1 for e in self.stack)

    # -- the reading
    def run(self):
        p = self.p
        s = self.s
        end = self.end
        kind = self.kind
        i = self.start
        plain = _PLAIN_RE if kind is None else _plain_re_for(kind)
        while i < end:
            c = s[i]
            if c not in _SPECIAL and c != kind:
                m = plain.match(s, i, end)
                i = m.end()
                continue
            if kind is not None and c == kind and i + 1 < end and s[i + 1] == "}":
                self.flush(i)
                for e in self.stack:
                    if e.combined:
                        raise _Restart(e.pos)
                return finish(self.out), (i, self.opaque)
            if c == "\\":
                nx = s[i + 1] if i + 1 < end else None
                if nx is not None and nx in ASCII_PUNCT:
                    self.emit(Esc(nx, i), i, i + 2)
                    i += 2
                    continue
                if nx == " ":
                    self.emit(NBSP(i), i, i + 2)
                    i += 2
                    continue
                if nx == "\n" or i + 1 >= p.n:
                    self.emit(HardBreak(i), i, i + 2)
                    i += 2
                    continue
                i += 1
                continue
            if c == "`":
                i = p.code_atom(self, i, None)
                continue
            if c == "$":
                if i + 1 < end and s[i + 1] == "`":
                    i = p.code_atom(self, i + 1, ("math", False, i))
                    continue
                if i + 2 < end and s[i + 1] == "$" and s[i + 2] == "`":
                    i = p.code_atom(self, i + 2, ("math", True, i))
                    continue
                i += 1
                continue
            if c == "!":
                if i + 1 < end and s[i + 1] == "`":
                    i = p.code_atom(self, i + 1, ("lit", None, i))
                    continue
                if i + 1 < end and s[i + 1] == "[":
                    r = p.bracket(i + 1, end, self.code_limit, True)
                    if r is not None:
                        node, j = r
                        self.emit(node, i, j)
                        self.opaque.append((i, j))
                        i = j
                        continue
                i += 1
                continue
            if c == "<":
                a = p.parse_autolink(i, end)
                if a is not None:
                    typ, body, j = a
                    if typ == "xref":
                        # ids are NFC (CARVE-P2-004), so the id is looked up in
                        # NFC, as R1 looks heading text up (PART 9R R1, R4)
                        node = Crossref(unicodedata.normalize("NFC", body), s[i:j])
                        self.emit(node, i, j)
                        self.opaque.append((i, j))
                        i = j
                        continue
                    if typ == "url":
                        node = Autolink(body, body)
                    else:
                        node = Autolink(body, "mailto:" + body)
                    j2 = p.attach(node, j, end)
                    self.emit(node, i, j2)
                    self.opaque.append((i, j2))
                    i = j2
                    continue
                i += 1
                continue
            if c == "{" and i + 1 < end:
                c2 = s[i + 1]
                if c2 == "{":
                    j = p.include_literal(i, end)
                    if j > 0:
                        self.emit(Verbatim(s[i:j]), i, j)
                        self.opaque.append((i, j))
                        i = j
                        continue
                ext = i + 2 < end and is_grapheme_extender(s[i + 2])
                if c2 == "%" and not ext and i not in p.literal:
                    k = p.find_tok("%}", i + 2, end)
                    if k >= 0:
                        p.removed_start[i] = k + 2
                        p.removed_end[k + 2] = i
                        self.emit(Comment(), i, k + 2)
                        self.opaque.append((i, k + 2))
                        i = k + 2
                        continue
                    i += 1
                    continue
                if c2 == "#" and not ext:
                    k = p.find_tok("#}", i + 2, end)
                    if k > i + 2:
                        self.emit(CriticComment(s[i + 2 : k]), i, k + 2)
                        self.opaque.append((i, k + 2))
                        i = k + 2
                        continue
                    i += 1
                    continue
                if c2 == "-" and s.startswith("--}", i + 1):
                    self.emit(Smart("\u2013", "{--}"), i, i + 4)
                    i += 4
                    continue
                if c2 in BRACE_MARKS and not ext:
                    if c2 == "~":
                        self.tilde_open = True
                    if (c2 == "+" or c2 == "-") and kind == c2:
                        i += 1
                        continue
                    r = p.braced(self, i, c2)
                    if r is not None:
                        i = r
                        continue
                    i += 1
                    continue
                i += 1
                continue
            if c == "^" and not p.in_note and i + 1 < end and s[i + 1] == "[":
                q = p.find_bracket_close(i + 1, end, self.code_limit)
                if q >= 0 and s[i + 2 : q].strip(" \t\n") != "":
                    if not p.nest_ok():
                        j = p.attach(Span([], None), q + 1, end)
                        self.emit(Verbatim(s[i:j]), i, j)
                        self.opaque.append((i, j))
                        i = j
                        continue
                    children = p.sub_region(i + 2, q, self.code_limit, in_note=True)
                    node = InlineNote(children)
                    j = p.attach(node, q + 1, end)
                    self.emit(node, i, j)
                    self.opaque.append((i, j))
                    i = j
                    continue
                i += 1
                continue
            if c == "[":
                r = p.bracket(i, end, self.code_limit, False)
                if r is not None:
                    node, j = r
                    self.emit(node, i, j)
                    self.opaque.append((i, j))
                    i = j
                    continue
                i += 1
                continue
            if c == ":":
                m = _IDENT_RE.match(s, i + 1, end)
                if m and m.end() < end and s[m.end()] == "[":
                    cst = m.end() + 1
                    q = p.find_ext_close(cst, end)
                    if q >= 0:
                        if not p.nest_ok():
                            j = p.attach(Span([], None), q + 1, end)
                            self.emit(Verbatim(s[i:j]), i, j)
                            self.opaque.append((i, j))
                            i = j
                            continue
                        children = p.sub_region(cst, q, q)
                        node = Ext(m.group(0), children)
                        j = p.attach(node, q + 1, end)
                        self.emit(node, i, j)
                        self.opaque.append((i, j))
                        i = j
                        continue
                i += 1
                continue
            if c == "%" and i + 1 < end and s[i + 1] == "%":
                if (i > self.start and s[i - 1] == " ") or (
                    i == self.start and self.run_start
                ):
                    arrow = (
                        kind == "~" and p.find_arrow(self.start, i, self.opaque) >= 0
                    )
                    ce = p.comment_end(
                        i, end, kind, self.slash_star, self.tilde_open, arrow
                    )
                    self.flush(i)
                    rs = i
                    out = self.out
                    if (
                        out
                        and isinstance(out[-1], Text)
                        and out[-1].start + len(out[-1].s) == i
                    ):
                        t = out[-1]
                        st = t.s.rstrip(" ")
                        rs = i - (len(t.s) - len(st))
                        if st:
                            t.s = st
                        else:
                            out.pop()
                    p.removed_start[rs] = ce
                    p.removed_end[ce] = rs
                    self.ts = ce
                    i = ce
                    continue
                i += 2
                continue
            if c in BARE:
                if i + 1 < end and is_grapheme_extender(s[i + 1]):
                    i += 1
                    continue
                if c == "/" and i + 1 < end and s[i + 1] == "*":
                    self.slash_star = True
                r = self.delim(i, c)
                if r is not None:
                    i = r
                    continue
                i += 1
                continue
            if c == "\n":
                self.emit(SoftBreak(i), i, i + 1)
                i += 1
                continue
            i += 1
        self.flush(end)
        if kind is not None:
            return None, (-1, self.opaque)
        for e in self.stack:
            if e.combined:
                raise _Restart(e.pos)
        return finish(self.out), (-1, self.opaque)

    def delim(self, i, c):
        """Bare delimiter steps R2-R5 (and the combined token).  Returns the
        index to continue at, or None when c is text."""
        p = self.p
        s = self.s
        end = self.end
        stack = self.stack
        combined = None
        for e in stack:
            if e.combined:
                combined = e
        if (
            c == "/"
            and combined is None
            and i + 1 < end
            and s[i + 1] == "*"
            and i not in self.bare_at
        ):
            a2 = s[i + 2] if i + 2 < end else None
            if (
                a2 is not None
                and a2 not in " \t\n\r"
                and not is_grapheme_extender(a2)
                and self.can_open("/", i)
                and not any(e.ch == "/" or e.ch == "*" for e in stack)
            ) and p.find_combined_closer(i + 2, end, self.kind):
                self.flush(i)
                self.out.append(Text("/*", i))
                stack.append(Delim("/", i, len(self.out) - 1, combined=True))
                self.ts = i + 2
                return i + 2
        if combined is not None and (c == "/" or c == "*"):
            if (
                c == "*"
                and i + 1 < end
                and s[i + 1] == "/"
                and i != combined.pos + 2
                and p.is_combined_closer(i, end)
            ):
                return self.close(combined, i, 2, None)
            return None
        if self.kind is not None and c == self.kind:
            self.note_literal(c, i)
            return None
        if self.can_close(c, i):
            for k in range(len(stack) - 1, -1, -1):
                e = stack[k]
                if e.ch == c and not e.combined:
                    lst = self.lit.get(c)
                    if lst:
                        for q in lst:
                            if e.pos < q < i:
                                del stack[k]
                                self.note_literal(c, i)
                                return None
                    for e2 in stack[k + 1 :]:
                        if e2.combined:
                            raise _Restart(e2.pos)
                    return self.close(e, i, 1, KIND_ELEM[c])
        if self.can_open(c, i) and not any(e.ch == c or e.combined for e in stack):
            self.flush(i)
            self.out.append(Text(c, i))
            stack.append(Delim(c, i, len(self.out) - 1))
            self.ts = i + 1
            return i + 1
        self.note_literal(c, i)
        return None

    def close(self, e, i, width, kindname):
        self.p.used_delims.add(i)
        self.p.used_delims.add(e.pos)
        self.flush(i)
        stack = self.stack
        k = stack.index(e)
        del stack[k:]
        out = self.out
        children = finish(out[e.idx + 1 :])
        if kindname is None:
            node = Elem("strong", [Elem("em", children)])
        else:
            node = Elem(kindname, children)
        del out[e.idx :]
        out.append(node)
        j = self.p.attach(node, i + width, self.end)
        self.ts = j
        self.at_start = False
        return j


def parse_inline(src, in_note=False, in_cell=False, line_block=False, literal=None):
    p = InlineParser(
        src, in_note=in_note, in_cell=in_cell, line_block=line_block, literal=literal
    )
    return p.parse(), p
