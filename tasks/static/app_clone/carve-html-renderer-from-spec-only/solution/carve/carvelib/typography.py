"""Passes over parsed inline content that read the remaining text:
mentions, tags and symbols (PART 9 §7, PART 8 order), then smart
typography (PART 9 §8, CARVE-P3-021, CARVE-P3-023)."""

import re

from .attrs import parse_attr_run
from .chars import is_ascii_digit, is_flank, is_letter, is_number
from .nodes import (
    NBSP,
    Bracket,
    Comment,
    Elem,
    Esc,
    Ext,
    HardBreak,
    InlineNote,
    Link,
    Mention,
    RefLink,
    Smart,
    SoftBreak,
    Span,
    Subst,
    Symbol,
    Text,
    Verbatim,
)

_NAME_RE = re.compile(r"[A-Za-z0-9_\-]+(?:\.[A-Za-z0-9_\-]+)*")
_SYMBOL_RE = re.compile(r":([A-Za-z0-9+\-][A-Za-z0-9_+\-]*):")
_HAS_LETTER = re.compile(r"[A-Za-z]")


def _boundary_ok(ch):
    return ch is None or not (
        ("a" <= ch <= "z") or ("A" <= ch <= "Z") or ("0" <= ch <= "9") or ch == "_"
    )


def social_pass(nodes, parser, no_tags=False):
    """Split text nodes for mentions, tags and symbols (in place)."""
    out = []
    for nd in nodes:
        if isinstance(nd, Text):
            out.extend(_split_social(nd, parser, no_tags))
            continue
        _recurse_social(nd, parser, no_tags)
        out.append(nd)
    return out


def _recurse_social(nd, parser, no_tags):
    for attr in ("children",):
        ch = getattr(nd, attr, None)
        if ch:
            setattr(nd, attr, social_pass(ch, parser, no_tags))
    if isinstance(nd, Subst):
        nd.old = social_pass(nd.old, parser, no_tags)
        nd.new = social_pass(nd.new, parser, no_tags)


def _split_social(t, parser, no_tags):
    s = t.s
    if "@" not in s and "#" not in s and ":" not in s:
        return [t]
    res = []
    i = 0
    seg = 0
    n = len(s)
    src = parser.s if parser is not None else None
    while i < n:
        c = s[i]
        if c == "@" or (c == "#" and not no_tags) or c == ":":
            if i == 0 and t.at_start:
                prev = None
            elif src is not None and t.start >= 0:
                prev = parser.prev_char(t.start + i)
            else:
                prev = s[i - 1] if i > 0 else None
            if _boundary_ok(prev):
                if c == "@" or c == "#":
                    m = _NAME_RE.match(s, i + 1)
                    if m and _HAS_LETTER.search(m.group(0)):
                        if i > seg:
                            res.append(
                                Text(
                                    s[seg:i],
                                    t.start + seg if t.start >= 0 else -1,
                                    t.at_start and seg == 0,
                                )
                            )
                        res.append(Mention(c, m.group(0)))
                        i = m.end()
                        seg = i
                        continue
                else:
                    m = _SYMBOL_RE.match(s, i)
                    if m:
                        if i > seg:
                            res.append(
                                Text(
                                    s[seg:i],
                                    t.start + seg if t.start >= 0 else -1,
                                    t.at_start and seg == 0,
                                )
                            )
                        sym = Symbol(m.group(1))
                        j = m.end()
                        if j < n and s[j] == "{":
                            r = parse_attr_run(s, j, n)
                            if r is not None:
                                sym.attrs = r[0]
                                j = r[1]
                        res.append(sym)
                        i = j
                        seg = i
                        continue
        i += 1
    if seg == 0:
        return [t]
    if seg < n:
        res.append(Text(s[seg:], t.start + seg if t.start >= 0 else -1, False))
    return res


# ---------------------------------------------------------------- smart typography

LDQ, RDQ, LSQ, RSQ = "“", "”", "‘", "’"
EM, EN = "—", "–"
START_BLOCK = "START_BLOCK"
START = "START"
WORD = "WORD"

_OPEN_AFTER = set("([{=:-–—/") | {LDQ, LSQ}
_R1_CLOSE_NEXT = set("\"'.,;:!?)]")
_ELISIONS = {
    "tis",
    "tisn",
    "twas",
    "twasn",
    "twere",
    "twill",
    "twould",
    "em",
    "cause",
    "til",
    "n",
    "bout",
}


def dash_run(L):
    out = []
    while L > 0:
        if L % 3 == 0:
            out.append(EM * (L // 3))
            break
        if L % 2 == 0:
            out.append(EN * (L // 2))
            break
        out.append(EM)
        L -= 3
    return "".join(out)


class _QuoteRec:
    __slots__ = ("buf", "demotable", "idx", "retain")

    def __init__(self, buf, idx, demotable, retain):
        self.buf = buf
        self.idx = idx
        self.demotable = demotable
        self.retain = retain


class Typo:
    def __init__(self):
        self.prev = START_BLOCK
        self.prev_ws_like = True  # for the dash flag rule
        self.single = None  # open single-quote span record

    def finalize(self):
        r = self.single
        if r is not None and r.demotable and not r.retain:
            r.buf[r.idx] = RSQ
        self.single = None


def smart_pass(nodes):
    st = Typo()
    _walk(nodes, st, START_BLOCK)
    st.finalize()


def _next_of(siblings, k):
    """The character following sibling k: None (end of content), a char, or
    ' ' for a rendered break / space."""
    j = k + 1
    while j < len(siblings):
        nd = siblings[j]
        if isinstance(nd, Comment):
            j += 1
            continue
        if isinstance(nd, Text):
            if nd.s:
                return nd.s[0]
            j += 1
            continue
        if isinstance(nd, (SoftBreak, HardBreak)):
            return "\n"
        if isinstance(nd, NBSP):
            return " "
        if isinstance(nd, Esc):
            return "\\"
        return "x"  # any other construct starts with a non-space source char
    return None


def _walk(nodes, st, start_kind):
    st.prev = start_kind
    st.prev_ws_like = True
    for k, nd in enumerate(nodes):
        if isinstance(nd, Text):
            nd.s = _text(nd.s, st, nodes, k)
        elif isinstance(nd, Esc):
            st.prev = nd.ch
            st.prev_ws_like = False
        elif isinstance(nd, NBSP):
            st.prev = " "
            st.prev_ws_like = True
        elif isinstance(nd, (SoftBreak, HardBreak)):
            st.prev = "\n"
            st.prev_ws_like = True
        elif isinstance(nd, Comment):
            pass
        elif isinstance(nd, Smart):
            st.prev = nd.glyph[-1]
            st.prev_ws_like = False
        elif isinstance(nd, Verbatim):
            st.prev = nd.s[-1] if nd.s else st.prev
            st.prev_ws_like = False
        elif isinstance(nd, (Elem, Span, Link, Ext)):
            _walk(nd.children, st, START)
            st.prev = WORD
            st.prev_ws_like = False
        elif isinstance(nd, Bracket):
            _walk(nd.children, st, START)
            st.prev = "]"
            st.prev_ws_like = False
        elif isinstance(nd, RefLink):
            if nd.children is not None:
                _walk(nd.children, st, START)
            st.prev = WORD
            st.prev_ws_like = False
        elif isinstance(nd, Subst):
            _walk(nd.old, st, START)
            _walk(nd.new, st, START)
            st.prev = WORD
            st.prev_ws_like = False
        elif isinstance(nd, InlineNote):
            sub = Typo()
            _walk(nd.children, sub, START_BLOCK)
            sub.finalize()
            st.prev = WORD
            st.prev_ws_like = False
        elif isinstance(nd, Symbol):
            if nd.attrs:
                st.prev = WORD
            else:
                st.prev = ":"
            st.prev_ws_like = False
        elif isinstance(nd, Mention):
            st.prev = nd.name[-1]
            st.prev_ws_like = False
        else:
            # code, math, literal, raw, autolink, crossref, image, note refs...
            st.prev = WORD
            st.prev_ws_like = False


def _is_ln(c):
    return c is not None and len(c) == 1 and (is_letter(c) or is_number(c))


_TRIGGER_RE = re.compile("[\"'\\-<=>!.(+]")


def _text(s, st, siblings, k):
    n = len(s)
    if n == 0:
        return s
    if _TRIGGER_RE.search(s) is None:
        # nothing to substitute: only the running context changes
        last = s[-1]
        st.prev = last
        st.prev_ws_like = is_flank(last)
        return s
    buf = []
    i = 0
    nxt_after = None
    computed_after = False
    while i < n:
        c = s[i]
        if c == '"' or c == "'":
            nx = s[i + 1] if i + 1 < n else None
            if nx is None:
                if not computed_after:
                    nxt_after = _next_of(siblings, k)
                    computed_after = True
                nx = nxt_after
            prev = st.prev
            g = _quote(c, prev, nx, st, s, i, n, siblings, k, buf)
            buf.append(g)
            if g == LDQ or g == LSQ:
                st.prev_ws_like = (prev in (START, START_BLOCK)) or (
                    isinstance(prev, str) and len(prev) == 1 and is_flank(prev)
                )
            else:
                st.prev_ws_like = False
            st.prev = g
            i += 1
            continue
        if c == "-":
            j = i
            while j < n and s[j] == "-":
                j += 1
            L = j - i
            if L == 1:
                buf.append("-")
                st.prev = "-"
                st.prev_ws_like = False
                i = j
                continue
            if L == 2 and j < n and s[j] == ">":
                buf.append("→")
                st.prev = "→"
                st.prev_ws_like = False
                i = j + 1
                continue
            # dash run: flag rule
            if j < n:
                after = s[j]
            else:
                if not computed_after:
                    nxt_after = _next_of(siblings, k)
                    computed_after = True
                after = nxt_after
            before_ws = (
                st.prev_ws_like
                or st.prev in (START, START_BLOCK)
                or (
                    isinstance(st.prev, str) and len(st.prev) == 1 and is_flank(st.prev)
                )
            )
            if before_ws and after is not None and not is_flank(after):
                buf.append("-" * L)
                st.prev = "-"
                st.prev_ws_like = False
                i = j
                continue
            g = dash_run(L)
            buf.append(g)
            st.prev = g[-1]
            st.prev_ws_like = False
            i = j
            continue
        if c == "<":
            if s.startswith("<-->", i):
                g, w = "↔", 4
            elif s.startswith("<--", i) and not s.startswith("<---", i):
                g, w = "←", 3
            elif s.startswith("<==", i):
                g, w = "⇐", 3
            elif s.startswith("<=>", i):
                g, w = "⇔", 3
            elif s.startswith("<=", i):
                g, w = "≤", 2
            else:
                g, w = "<", 1
            buf.append(g)
            st.prev = g
            st.prev_ws_like = False
            i += w
            continue
        if c == "=" and s.startswith("==>", i):
            buf.append("⇒")
            st.prev = "⇒"
            st.prev_ws_like = False
            i += 3
            continue
        if c == ">" and s.startswith(">=", i):
            buf.append("≥")
            st.prev = "≥"
            st.prev_ws_like = False
            i += 2
            continue
        if c == "!" and s.startswith("!=", i):
            buf.append("≠")
            st.prev = "≠"
            st.prev_ws_like = False
            i += 2
            continue
        if c == "." and s.startswith("...", i):
            buf.append("…")
            st.prev = "…"
            st.prev_ws_like = False
            i += 3
            continue
        if c == "(" and s.startswith("(tm)", i):
            buf.append("™")
            st.prev = "™"
            st.prev_ws_like = False
            i += 4
            continue
        if c == "+" and s.startswith("+-", i):
            buf.append("±")
            st.prev = "±"
            st.prev_ws_like = False
            i += 2
            continue
        buf.append(c)
        if c == "(":
            st.prev_ws_like = st.prev in (START, START_BLOCK) or (
                isinstance(st.prev, str) and len(st.prev) == 1 and is_flank(st.prev)
            )
        elif is_flank(c):
            st.prev_ws_like = True
        else:
            st.prev_ws_like = False
        st.prev = c
        i += 1
    res = "".join(buf)
    if st.single is not None and st.single.buf is buf:
        # an open single quote in this text may be demoted at the end of
        # content: route that write back into the text node
        st.single.buf = _Deferred(siblings, k, buf)
    return res


class _Deferred:
    """List-like proxy: demotion writes into the text node after the fact."""

    __slots__ = ("buf", "k", "siblings")

    def __init__(self, siblings, k, buf):
        self.siblings = siblings
        self.k = k
        self.buf = buf

    def __setitem__(self, idx, val):
        self.buf[idx] = val
        nd = self.siblings[self.k]
        nd.s = "".join(self.buf)


def _quote(c, prev, nx, st, s, i, n, siblings, k, buf):
    # base direction
    if prev in (START, START_BLOCK):
        opens = True
    elif prev == WORD:
        opens = False
    elif prev in ("-", EN, EM, "/"):
        # R1
        opens = not (nx is None or is_flank(nx) or nx in _R1_CLOSE_NEXT)
    elif is_flank(prev) or prev in _OPEN_AFTER:
        opens = True
    else:
        opens = False
    if c == '"':
        return LDQ if opens else RDQ
    # single quote
    if is_ascii_digit(nx):
        return RSQ
    if opens:
        # R2 listed elisions
        j = i + 1
        while j < n and is_letter(s[j]):
            j += 1
        word = s[i + 1 : j]
        if word and word.lower() in _ELISIONS:
            after = s[j] if j < n else None
            quoted = False
            if after == "'":
                follow = s[j + 1] if j + 1 < n else None
                if follow is None and j + 1 >= n:
                    follow = _next_of(siblings, k)
                if not _is_ln(follow):
                    quoted = True
            if not quoted:
                return RSQ
        if _is_ln(nx):
            if st.single is not None:
                return RSQ
            retain = (prev == START_BLOCK) or (prev == LDQ)
            st.single = _QuoteRec(buf, len(buf), True, retain)
            return LSQ
        if st.single is None:
            st.single = _QuoteRec(buf, len(buf), False, True)
        return LSQ
    # closing
    if _is_ln(prev) and _is_ln(nx):
        return RSQ
    if not (isinstance(prev, str) and len(prev) == 1 and is_flank(prev)):
        st.single = None
    return RSQ
