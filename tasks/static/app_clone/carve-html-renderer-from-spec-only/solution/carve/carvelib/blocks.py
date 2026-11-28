"""Block layout parser (PART 0 line automaton, PART 2 blocks, PART 9 block
clauses).

Each physical line runs the ordered procedure of CARVE-P0-024:
  S1  payload of an open fence, then erasure of `%%` lines and one-line
      link / abbreviation definitions;
  S2  owner: walk the open frames outside-in, each consuming its prefix;
  S3  form: classify the rest of the line in the owner's coordinates;
  S4  lazy: fold into the deepest open paragraph when permitted;
  S5  apply: close missed frames and apply the form in the owner.
"""

import re

from .attrs import items_to_attrs, parse_attr_block
from .chars import (
    ASCII_PUNCT,
    indent_cols,
    is_blank,
    is_unicode_ws,
    label_key,
    strip_cols,
)
from .nodes import (
    BlockQuote,
    Caption,
    CodeBlock,
    DefDesc,
    DefList,
    DefTerm,
    Div,
    Document,
    FootnoteDef,
    Heading,
    ListBlock,
    ListItem,
    Paragraph,
    RawBlock,
    Table,
    ThematicBreak,
)

MAX_NESTING = 200

_THEMATIC_RE = re.compile(r"(?:-{3,}|\*{3,}|_{3,}|- - -(?: -)*|\* \* \*(?: \*)*)$")
_HEADING_RE = re.compile(r"(#{1,6}) +(.*)$")
_FENCE_RE = re.compile(r"(`{3,}|~{3,})(.*)$")
_COLON_RE = re.compile(r"(:{3,})(.*)$")
_FOOTNOTE_RE = re.compile(r"\[\^([^\]\n]+)\]:( +)(.*)$")
_ABBR_RE = re.compile(r"\*\[([A-Za-z0-9]+)\]: +(.+)$")
_LANG_RE = re.compile(r"[A-Za-z0-9\-_+#./]+")
_RAW_RE = re.compile(r" ?=([A-Za-z_][A-Za-z0-9_\-]*)$")
_TYPE_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_\-]*")
_ROMAN_LO = set("ivxlcdm")
_ROMAN_UP = set("IVXLCDM")
_TASK_STATES = set(" xX_-/!>?")
_REGION_RE = re.compile(r"%%[ \t]*#(?:region|endregion)(?![A-Za-z0-9_])")

# ------------------------------------------------------------------ helpers


def roman_value(s):
    vals = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}
    s = s.lower()
    total = 0
    for k, ch in enumerate(s):
        v = vals[ch]
        if k + 1 < len(s) and vals[s[k + 1]] > v:
            total -= v
        else:
            total += v
    return total


class Marker:
    __slots__ = (
        "ambiguous",
        "attrs",
        "bare",
        "bullet",
        "content",
        "delim",
        "dialect",
        "kind",
        "lead",
        "spaces",
        "task",
        "text",
        "value",
        "width",
    )

    def __init__(self):
        self.kind = None  # 'bullet' | 'ordered' | 'term' | 'desc'
        self.bullet = None
        self.dialect = None  # 'decimal' | 'alpha' | 'ALPHA' | 'roman' | 'ROMAN'
        self.delim = None
        self.value = None
        self.text = None
        self.attrs = None
        self.width = 0
        self.spaces = 0
        self.content = ""
        self.task = None
        self.ambiguous = False
        self.bare = False
        self.lead = 0  # columns between the content column and the content


def parse_marker(t):
    """Recognize a list / definition marker at the start of t (no leading
    whitespace).  Returns a Marker or None."""
    n = len(t)
    if n < 2:
        return None
    c = t[0]
    m = Marker()
    if c == "-" or c == "*":
        j = 1
        if t[j] == "{":
            r = parse_attr_block(t, j, allow_empty=True)
            if r is None:
                return None
            m.attrs = r[0]
            j = r[1]
        k = j
        while k < n and t[k] == " ":
            k += 1
        if k == j or k >= n:
            return None
        m.lead = j - 1
        m.kind = "bullet"
        m.bullet = c
        m.width = 1
        m.spaces = k - j
        content = t[k:]
        if (
            len(content) >= 4
            and content[0] == "["
            and content[2] == "]"
            and content[1] in _TASK_STATES
            and content[3] == " "
            and content[4:].strip(" \t") != ""
        ):
            m.task = content[1]
            m.lead += 4
            content = content[4:]
        m.content = content
        return m
    if c == ":":
        if t.startswith("::") and n > 2 and t[2] == " ":
            k = 2
            while k < n and t[k] == " ":
                k += 1
            if k >= n:
                return None
            m.kind = "term"
            m.width = 2
            m.spaces = k - 2
            m.content = t[k:]
            return m
        if n > 1 and t[1] == " ":
            k = 1
            while k < n and t[k] == " ":
                k += 1
            if k >= n or t[k:].strip(" \t") == "":
                return None
            m.kind = "desc"
            m.width = 1
            m.spaces = k - 1
            m.content = t[k:]
            return m
        return None
    # ordered
    j = 0
    if c == ".":
        m.dialect = "decimal"
        m.delim = "."
        m.bare = True
        m.value = None
        j = 1
        if n > 1 and t[1] == ".":
            return None
    elif "0" <= c <= "9":
        while j < n and "0" <= t[j] <= "9":
            j += 1
        if j >= n or t[j] not in ".)":
            return None
        m.dialect = "decimal"
        m.delim = t[j]
        m.value = int(t[:j])
        m.text = t[:j]
        j += 1
    elif ("a" <= c <= "z") or ("A" <= c <= "Z"):
        while j < n and (("a" <= t[j] <= "z") or ("A" <= t[j] <= "Z")):
            j += 1
        if j >= n or t[j] not in ".)":
            return None
        word = t[:j]
        m.delim = t[j]
        m.text = word
        if len(word) == 1:
            if c in _ROMAN_LO or c in _ROMAN_UP:
                m.ambiguous = True
            m.dialect = "alpha" if c.islower() else "ALPHA"
            m.value = ord(c.lower()) - 96
        else:
            if all(ch in _ROMAN_LO for ch in word):
                m.dialect = "roman"
            elif all(ch in _ROMAN_UP for ch in word):
                m.dialect = "ROMAN"
            else:
                return None
            m.value = roman_value(word)
        j += 1
    else:
        return None
    m.kind = "ordered"
    m.width = j
    if j < n and t[j] == "{":
        r = parse_attr_block(t, j, allow_empty=True)
        if r is None:
            return None
        m.attrs = r[0]
        m.lead = r[1] - j
        j = r[1]
    k = j
    while k < n and t[k] == " ":
        k += 1
    sp = k - j
    if sp == 0 or k >= n:
        return None
    if m.delim == "." and m.dialect != "decimal" and sp < 2:
        return None
    m.spaces = sp
    m.content = t[k:]
    return m


def parse_fence_info(rest, fch, flen):
    """Code-fence opener metadata.  Returns (lang, title, label, ok) where ok
    is False when the line is not a code fence."""
    if rest == "":
        return None, None, None, True
    info = rest
    if info[0] == " ":
        info = info[1:]
        if info == "" or info[0] == " " or info[0] == "\t":
            return None, None, None, False
    elif info[0] == "\t":
        return None, None, None, False
    lang = None
    title = None
    label = None
    pos = 0
    n = len(info)
    m = _LANG_RE.match(info)
    if m and info[0] != "=":
        lang = m.group(0)
        pos = m.end()
    r = _parse_meta(info, pos, lang is not None)
    if r is not None:
        title, label = r
        if lang is None and title is None and label is None:
            return None, None, None, False
        return lang, title, label, True
    # recovery
    if lang is not None:
        nc = info[pos] if pos < n else ""
        if nc and (
            is_unicode_ws(nc) or nc == "\ufeff" or nc in '"{[' or nc in "\u201c\u201d"
        ):
            if fch * flen in info[pos:]:
                return None, None, None, False
            return lang, None, None, True
    return None, None, None, False


def _parse_meta(s, pos, need_space):
    """Parse [space+ "title"] [space+ [label]] from pos to the end.  Returns
    (title, label) or None."""
    n = len(s)
    title = None
    label = None
    j = pos
    first = True

    def spaces(j):
        k = j
        while k < n and s[k] == " ":
            k += 1
        return k

    if j >= n:
        return None, None
    k = spaces(j)
    if (need_space or not first) and k == j:
        return None
    if k >= n:
        return None
    j = k
    if s[j] == '"':
        e = s.find('"', j + 1)
        if e < 0:
            return None
        title = s[j + 1 : e]
        j = e + 1
        if j >= n:
            return title, None
        k = spaces(j)
        if k == j or k >= n:
            return None
        j = k
    if s[j] == "[":
        e = _label_close(s, j)
        if e < 0:
            return None
        label = s[j + 1 : e]
        j = e + 1
        if j != n:
            return None
        return title, label
    return None


def _label_close(s, i):
    """Balanced, escape- and literal-span-aware close of a [label] slot."""
    from .inline import InlineParser

    p = InlineParser(s)
    return p.find_bracket_close(i, len(s), len(s))


def parse_colon_opener(t):
    """Classify a colon-fence line.  Returns (fence_len, kind, title, label,
    ok, bare) or None when the line is not a colon fence opener.
    kind: None (generic div), a type word, '|', '\\\\', '>', 'figure'."""
    m = _COLON_RE.match(t)
    if not m:
        return None
    flen = len(m.group(1))
    rest = m.group(2)
    if rest == "":
        return flen, None, None, None, True
    if rest[0] == "[":
        e = _label_close(rest, 0)
        if e >= 0 and e == len(rest) - 1:
            return flen, None, None, rest[1:e], True
        return None
    if rest[0] != " ":
        return None
    k = 0
    while k < len(rest) and rest[k] == " ":
        k += 1
    body = rest[k:]
    if body == "":
        return flen, None, None, None, True
    if body == "|" or body == "\\" or body == ">":
        return flen, body, None, None, True
    if body[0] == "[":
        e = _label_close(body, 0)
        if e >= 0 and e == len(body) - 1:
            return flen, None, None, body[1:e], True
        return None
    tm = _TYPE_RE.match(body)
    if not tm:
        return None
    word = tm.group(0)
    after = body[tm.end() :]
    if after == "":
        return flen, word, None, None, True
    r = _parse_meta(body, tm.end(), True)
    if r is not None:
        return flen, word, r[0], r[1], True
    # recovery: the type word must end at whitespace / BOM / quote / { / [
    nc = after[0]
    if is_unicode_ws(nc) or nc == "\ufeff" or nc in '"{[' or nc in "\u201c\u201d":
        return flen, word, None, None, False
    return None


def is_colon_closer(t, flen):
    t = t.strip(" \t")
    return len(t) == flen and t == ":" * flen


def split_row_attrs(t):
    """For a line ending in `}`, find a row attribute block glued to the last
    `|`.  Returns (row_text, attrs_items) or (t, None)."""
    if not t.endswith("}"):
        return t, None
    k = 0
    while True:
        k = t.find("|{", k)
        if k < 0:
            return t, None
        r = parse_attr_block(t, k + 1)
        if r is not None and r[1] == len(t) and r[0]:
            return t[: k + 1], r[0]
        k += 1


def valid_row(t):
    if not t or t[0] != "|":
        return False
    body, _ = split_row_attrs(t)
    return len(body) >= 2 and body[-1] == "|"


def valid_cont_row(t):
    if not t or t[0] != "+":
        return False
    return len(t) >= 2 and t[-1] == "|"


def match_link_def(t):
    """One-line link reference definition (CARVE-P3-005).  Returns
    (label, dest, title, attrs_items) or None."""
    if not t.startswith("[") or t.startswith(("[^", "[@")):
        return None
    n = len(t)
    k = 1
    while k < n and t[k] != "]" and t[k] != "\n":
        k += 1
    if k >= n or t[k] != "]" or k == 1:
        return None
    label = t[1:k]
    if label[0] == "@" or label[0] == "^":
        return None
    if k + 1 >= n or t[k + 1] != ":":
        return None
    j = k + 2
    if j == n:
        return label, "", None, None
    if t[j] != " ":
        return None
    while j < n and t[j] == " ":
        j += 1
    if j >= n:
        return label, "", None, None
    # destination
    depth = 0
    buf = []
    st = j
    while j < n:
        c = t[j]
        if c == "\\" and j + 1 < n and t[j + 1] in "()\\":
            buf.append(t[j + 1])
            j += 2
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            if depth == 0:
                break
            depth -= 1
        elif is_unicode_ws(c):
            break
        buf.append(c)
        j += 1
    if j == st or depth != 0:
        return None
    if j < n and t[j] == ")":
        return None
    dest = "".join(buf)
    title = None
    if j == n:
        return label, dest, None, None
    if t[j] != " ":
        return None
    if j + 1 < n and t[j + 1] in "\"'":
        q = t[j + 1]
        m = j + 2
        tb = []
        while m < n and t[m] != q:
            if t[m] == "\\" and m + 1 < n and t[m + 1] in ASCII_PUNCT:
                tb.append(t[m + 1])
                m += 2
                continue
            tb.append(t[m])
            m += 1
        if m >= n:
            return None
        title = "".join(tb)
        j = m + 1
        if j == n:
            return label, dest, title, None
        if t[j] != " ":
            return None
    # attributes
    if j + 1 < n and t[j + 1] == "{":
        r = parse_attr_block(t, j + 1)
        if r is not None and r[1] == n and r[0]:
            return label, dest, title, r[0]
    return None


def match_abbr_def(t):
    m = _ABBR_RE.match(t)
    if not m:
        return None
    return m.group(1), m.group(2)


def is_region_marker(t):
    return _REGION_RE.match(t) is not None


def open_backtick(text):
    """Whether text ends inside an unclosed backtick run."""
    if "`" not in text:
        return False
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\" and i + 1 < n and text[i + 1] in ASCII_PUNCT:
            i += 2
            continue
        if c == "`":
            j = i
            while j < n and text[j] == "`":
                j += 1
            ln = j - i
            # find closing run of exactly ln
            k = j
            found = -1
            while True:
                k = text.find("`", k)
                if k < 0:
                    break
                m = k
                while m < n and text[m] == "`":
                    m += 1
                if m - k == ln:
                    found = m
                    break
                k = m
            if found < 0:
                return True
            i = found
            continue
        i += 1
    return False


# ------------------------------------------------------------------ frames

_BRACED_ONLY_RE = re.compile(r"(?:\{%.*?%\}[ \t]*)+$")


def _comment_only(content):
    """Caption content made only of braced comments, whitespace and a
    trailing `%%` comment (CARVE-P2-020)."""
    s = content
    i = 0
    n = len(s)
    while i < n:
        if s[i] in " \t":
            i += 1
            continue
        if s.startswith("{%", i):
            k = s.find("%}", i + 2)
            if k < 0:
                return False
            i = k + 2
            continue
        return bool(s.startswith("%%", i) and (i == 0 or s[i - 1] == " "))
    return True


def braced_only(t):
    return _BRACED_ONLY_RE.match(t) is not None


class Frame:
    __slots__ = (
        "attach",
        "blank_before_line",
        "blank_count",
        "blank_seen",
        "cap_blanks",
        "cap_host",
        "children",
        "content_col",
        "count_before_line",
        "dl",
        "fence_len",
        "had_visible",
        "indent",
        "kind",
        "leaf",
        "list",
        "marker_col",
        "node",
        "outer_blanks",
        "pending",
        "stanza",
    )

    def __init__(self, kind, node, content_col=0, indent=0):
        self.kind = kind
        self.node = node
        self.children = getattr(node, "children", None)
        self.content_col = content_col
        self.indent = indent
        self.leaf = None
        self.pending = None
        self.blank_seen = False
        self.blank_count = 0
        self.blank_before_line = False
        self.count_before_line = 0
        self.cap_host = None
        self.cap_blanks = 0
        self.fence_len = 0
        self.marker_col = 0
        self.list = None
        self.dl = None
        self.attach = None
        self.had_visible = False
        self.stanza = None
        self.outer_blanks = None


class Leaf:
    __slots__ = (
        "attached",
        "fch",
        "flen",
        "host",
        "indent",
        "kind",
        "lines",
        "no_marked_cont",
        "node",
        "pulled",
        "src_lines",
    )

    def __init__(self, kind, node, indent=0):
        self.kind = kind  # 'para' | 'code' | 'raw' | 'table' | 'caption'
        self.node = node
        self.indent = indent
        self.fch = None
        self.flen = 0
        self.lines = None
        self.host = None
        self.attached = None
        self.src_lines = None
        self.no_marked_cont = False
        self.pulled = False  # a paragraph that has taken a lazy line


class Attach:
    __slots__ = ("block", "closer_line", "col", "form", "m", "seen_blank", "state")

    def __init__(self, m, form, col=None):
        self.m = m
        self.form = form  # 'own' | 'marker'
        self.col = col  # an own-line `+`'s written column
        self.state = "offer"
        self.block = None
        self.seen_blank = False
        self.closer_line = -1  # index of a closer the host reads, once found


class CommentSpan:
    __slots__ = ("flen", "lineblock", "owner")

    def __init__(self, owner, flen, lineblock=False):
        self.owner = owner
        self.flen = flen
        self.lineblock = lineblock


INVISIBLE_FORMS = ("attrs", "footnote", "commentfence", "region")


class BlockParser:
    def __init__(self, text):
        if text == "":
            lines = []
            last_nl = False
        else:
            lines = text.split("\n")
            if text.endswith("\n"):
                lines.pop()
                last_nl = True
            else:
                last_nl = False
        self.lines = lines
        self.last_nl = last_nl
        self.doc = Document()
        self.stack = [Frame("doc", self.doc)]
        self.linkdefs = []
        self.abbrdefs = []
        self.footnotes = []
        self.note_keys = set()
        self.comment = None
        self.li = 0
        self.unrouted = None

    # -------------------------------------------------------------- driver

    def parse(self):
        lines = self.lines
        self.li = self.frontmatter()
        while self.li < len(lines):
            self.process(self.li)
        self.close_frames(0)
        self.close_leaf(self.stack[0])
        return self.doc

    def frontmatter(self):
        lines = self.lines
        if not lines:
            return 0
        first = lines[0].rstrip(" \t")
        if not re.match(r"---(?: ?[A-Za-z0-9]+)?$", first):
            return 0
        for k in range(1, len(lines)):
            if lines[k].rstrip(" \t") == "---":
                return k + 1
        return len(lines)

    # -------------------------------------------------------------- walking

    def walk(self, line, limit=None):
        """Consume frame prefixes outside-in.  Returns (reached, residuals).

        A block a `+` attached sits at its host's marker column, so its frames
        are measured from that column, and a nonblank line the attachment does
        not route is never measured against them from the host's content
        column.  Under an own-line `+` an item, description or note body is
        held at its marker column, so such a line misses the host (PART 0 P1,
        L8); otherwise it reaches the host by the host's own prefix and stops
        there, and the main walk records that host in `self.unrouted`.  The
        main walk also records in `self.cols` the written column at which each
        residual begins."""
        res = [line]
        cols = [0]
        cur = line
        stack = self.stack
        n = len(stack) if limit is None else limit
        if limit is None:
            self.unrouted = None
            self.cols = cols
        for k in range(1, n):
            f = stack[k]
            a = f.attach
            attached = False
            if (
                a is not None
                and a.state == "active"
                and a.block is not None
                and not isinstance(a.block, Leaf)
            ):
                nxt = self.attach_route(f, a, cur)
                if nxt is not None:
                    res.append(nxt)
                    cols.append(cols[-1] + a.m)
                    cur = nxt
                    continue
                attached = (
                    f.attach is a and not is_blank(cur) and self.attached_above(k)
                )
                if attached and a.form == "own" and f.kind in ("item", "dd", "fn"):
                    # an own-line grant holds its host at the marker column:
                    # a line the attached block does not take misses the host
                    # and ends the attachment (PART 0 P1, L8)
                    break
            kind = f.kind
            if kind == "quote":
                t = cur.lstrip(" \t")
                if t.startswith(">") and (len(t) == 1 or t[1] == " "):
                    width = indent_cols(cur) + min(len(t), 2)
                    cur = t[2:]
                else:
                    break
            elif kind in ("item", "dd", "fn"):
                width = f.content_col
                if is_blank(cur):
                    cur = ""
                elif indent_cols(cur) >= f.content_col:
                    cur = strip_cols(cur, f.content_col)[0]
                else:
                    break
            else:
                width = f.indent
                cur = strip_cols(cur, f.indent)[0]
            res.append(cur)
            cols.append(cols[-1] + width)
            if attached:
                if limit is None:
                    self.unrouted = k
                break
        return len(res) - 1, res

    def attached_above(self, k):
        """Whether the frame above stack[k] belongs to the block stack[k]'s
        `+` attached."""
        stack = self.stack
        if k + 1 >= len(stack):
            return False
        b = stack[k].attach.block
        g = stack[k + 1]
        return g is b or (g.kind == "item" and g.list is b)

    def attach_route(self, f, a, p):
        """Route a line to a block a `+` attached at f's marker column."""
        b = a.block
        if is_blank(p):
            return None
        if indent_cols(p) < a.m:
            return None
        body = strip_cols(p, a.m)[0]
        bt = body.lstrip(" \t")
        if isinstance(b, Frame):
            if b not in self.stack:
                f.attach = None
                return None
            if b.kind == "quote":
                if bt.startswith(">") and (len(bt) == 1 or bt[1] == " "):
                    return body
                if bt.startswith("^ ") and indent_cols(body) == 0:
                    # the attached quote's caption slot
                    return body
                return None
            if b.kind in ("div", "lineblock"):
                if f.kind == "item" and indent_cols(body) == 0:
                    m = parse_marker(bt)
                    if m is not None and m.kind in ("bullet", "ordered"):
                        return None
                if f.kind == "dd" and indent_cols(body) == 0:
                    m = parse_marker(bt)
                    if m is not None and m.kind in ("term", "desc"):
                        return None
                return body
            return None
        if isinstance(b, ListBlock):
            ch = f.children
            if not ch or ch[-1] is not b:
                f.attach = None
                return None
            if indent_cols(body) == 0:
                m = parse_marker(bt)
                if m is not None and m.kind in ("bullet", "ordered"):
                    return body
            # a line reaching the open item's content column
            for k in range(len(self.stack) - 1, 0, -1):
                g = self.stack[k]
                if g is f:
                    break
                if g.kind == "item" and g.list is b:
                    if indent_cols(body) >= g.content_col:
                        return body
                    break
            return None
        return None

    # -------------------------------------------------------------- per line

    def process(self, li):
        raw = self.lines[li]
        self.li = li + 1
        stack = self.stack
        r, res = self.walk(raw)
        deepest = len(stack) - 1

        # an open %%% comment span hides its body
        if self.comment is not None:
            cs = self.comment
            if r >= cs.owner:
                t = res[cs.owner].strip(" \t")
                m = re.match(r"%{3,}", t)
                if m and len(m.group(0)) == cs.flen:
                    self.comment = None
                return
            if self.erase_line(res[r].strip(" \t")):
                # S1 erases the line before S2 measures reach, so it misses no
                # frame and leaves the span open (PART 0 FAMILY GUARDS)
                return
            self.comment = None
            # a closer below the host's content column still ends the span
            t = res[r].strip(" \t")
            m = re.match(r"%{3,}", t)
            if m and len(m.group(0)) == cs.flen and not is_blank(res[r]):
                return

        top = stack[-1]
        leaf = top.leaf

        # S1 payload of an open code / raw fence
        if leaf is not None and leaf.kind in ("code", "raw"):
            if leaf.attached is not None:
                done = self.attached_fence_line(top, leaf, r, res)
                if done:
                    return
            elif r == deepest:
                body = strip_cols(res[r], leaf.indent)[0]
                if self.fence_closer(leaf, body):
                    leaf.node.closed = True
                    self.close_leaf(top)
                    if leaf.kind == "code":
                        top.cap_host = leaf.node
                        top.cap_blanks = 0
                    self.bookkeep(r, res, False)
                    return
                leaf.node.lines.append(body)
                self.bookkeep(r, res, False)
                return
            else:
                self.close_leaf(top)

        # a table a `+` attached at the host's marker column reads its rows
        # there until its first line that is not a row (PART 9 §5, B-table-end)
        if leaf is not None and leaf.kind == "table" and leaf.attached is not None:
            if self.attached_row(top, leaf, r, res):
                return
            self.close_leaf(top)
            top.attach = None

        # a line block body reads verse
        if top.kind == "lineblock" and r == deepest:
            self.bookkeep(r, res, False)
            self.verse_line(top, res[r], r)
            return

        # a colon closer of the innermost reached colon frame
        for k in range(r, 0, -1):
            f = stack[k]
            if f.kind in ("div", "lineblock"):
                if is_colon_closer(res[k], f.fence_len):
                    self.bookkeep(r, res, False)
                    self.close_frames(k - 1, closer=True)
                    return
                break

        cur = res[r]
        t = cur.strip(" \t")

        # S1 erasure of comments and one-line definitions
        if t.startswith("%%") and not t.startswith("%%%") and is_region_marker(t):
            self.invisible_line(r)
            return
        if self.erase_line(t):
            return

        # S2: a lone `+` at the marker column of an eligible container
        if t == "+" and r < deepest:
            host = self.plus_host(r, res)
            if host is not None:
                self.close_frames(host)
                h = stack[host]
                self.close_leaf(h)
                if h.kind == "quote":
                    # a structural line inside its quote is that quote's blank
                    # line (CARVE-P9-080), so it separates the quote's blocks
                    # for §17 L1
                    h.blank_seen = True
                    h.blank_count += 1
                else:
                    # the `+` reaches its host at the marker column, short of
                    # the content column, so a blank run before it is not the
                    # host's (PART 0 L6) and cannot loosen it
                    h.blank_seen = False
                    h.blank_count = 0
                a = Attach(h.marker_col, "own", self.cols[r] + indent_cols(res[r]))
                h.attach = a
                return

        # an outstanding `+` offer
        for k in range(1, len(stack)):
            a = stack[k].attach
            if a is not None and a.state == "offer":
                done = self.offer_line(k, a, r, res, li)
                if done is True:
                    return
                if done == "host closed":
                    r, res = self.walk(raw)
                    deepest = len(stack) - 1
                break

        if t == "":
            self.bookkeep(r, res, True)
            self.blank_line(r)
            return

        self.classify_and_apply(r, res, li)

    def erase_line(self, t):
        """S1 erasure (CARVE-P0-005): a `%%` line comment other than a region
        marker, or a one-line link or abbreviation definition, which still
        registers.  Returns True when the line is erased."""
        if t.startswith("%%") and not t.startswith("%%%"):
            return not is_region_marker(t)
        if t.startswith("[") and not t.startswith("[^"):
            d = match_link_def(t)
            if d is not None:
                self.linkdefs.append(d)
                return True
        if t.startswith("*["):
            d = match_abbr_def(t)
            if d is not None:
                self.abbrdefs.append(d)
                return True
        return False

    # -------------------------------------------------------------- `+`

    def plus_host(self, r, res):
        """The frame a lone `+` reaches at its marker column."""
        stack = self.stack
        cur = res[r]
        ind = indent_cols(cur)
        if self.unrouted == r:
            # the line reached the host by its own prefix; the attached
            # frames above it are measured from the host's marker column
            h = stack[r]
            if h.kind == "quote":
                return None
            ind += h.content_col - h.attach.m
        k = r + 1
        if k < len(stack):
            f = stack[k]
            if f.kind in ("item", "dd", "fn", "quote") and f.marker_col == ind:
                return k
        return None

    def offer_line(self, k, a, r, res, li):
        """Apply the CARVE-P9-067 gates to the first line after a `+`.
        Returns True when the line has been consumed."""
        stack = self.stack
        h = stack[k]
        if r < k - 1:
            h.attach = None
            return False
        p = res[k - 1]
        if is_blank(p) or (p.strip(" \t").strip("> ") == "" and ">" in p):
            h.attach = None
            return False
        ind = indent_cols(p)
        body = strip_cols(p, a.m)[0] if ind >= a.m else p
        t = body.strip(" \t")
        # invisible lines the host keeps
        if (
            (ind == a.m or ind >= h.content_col)
            and self.is_invisible_text(t)
            and not self.offer_lookahead(k, a)
        ):
            h.attach = None
            return False
        if (
            (ind == a.m or ind >= h.content_col)
            and t.startswith("{")
            and self.attr_prefix_open(t)
        ):
            lv = k - 1 if ind == a.m else k
            col0 = ind if lv == k - 1 else ind - h.content_col
            ext = self.attr_run_extent(self.li, lv, col0)
            if ext is not None:
                if not self.offer_lookahead(k, a, start=ext[0]):
                    h.attach = None
                    return False
                self.li = ext[0]
                self.close_frames(k)
                at = items_to_attrs(ext[1])
                if h.pending is None:
                    h.pending = at
                else:
                    h.pending.merge(at)
                return True
        if ind == a.m or ind >= h.content_col:
            if t.startswith("{"):
                items = self.attr_line(t)
                if items is not None:
                    self.close_frames(k)
                    at = items_to_attrs(items)
                    if h.pending is None:
                        h.pending = at
                    else:
                        h.pending.merge(at)
                    return True
                if braced_only(t):
                    return True
            if t.startswith("%%%"):
                m = re.match(r"%{3,}", t)
                self.close_frames(k)
                self.comment = CommentSpan(k, len(m.group(0)))
                return True
        # column gate: an own-line `+` takes a block at its own written column,
        # a marker-line one a block at its host's marker column (CARVE-P9-067)
        if (self.cols[k - 1] + ind != a.col) if a.form == "own" else ind != a.m:
            return self.refuse(k)
        # sibling gate
        mk = parse_marker(t)
        if mk is not None:
            if h.kind == "item" and mk.kind in ("bullet", "ordered"):
                h.attach = None
                return False
            if h.kind == "dd" and mk.kind in ("term", "desc"):
                h.attach = None
                return False
        # closer gate
        for j in range(k, 0, -1):
            g = stack[j]
            if g.kind in ("div", "lineblock"):
                if is_colon_closer(t, g.fence_len):
                    h.attach = None
                    return False
                break
        # accepted: the block starts in the host at its marker column
        self.close_frames(k)
        self.close_leaf(h)
        depth_before = len(stack)
        self.bookkeep(k, res[:k] + [body], False)
        form = self.classify(t, body, h, k, None)
        if form[0] == "plus":
            h.attach = None
            return True
        self.apply(form, h, k, body, t, indent_cols(body), li)
        a.state = "active"
        if len(stack) > depth_before:
            nf = stack[depth_before]
            if nf.kind == "item":
                a.block = nf.list
            elif nf.kind in ("quote", "div", "lineblock"):
                a.block = nf
            else:
                a.block = None
        elif h.leaf is not None and h.leaf.kind in ("code", "raw", "table"):
            a.block = h.leaf
            h.leaf.attached = a
        else:
            a.block = None
            if h.kind == "quote" and h.leaf is not None and h.leaf.kind == "para":
                h.leaf.no_marked_cont = True
        if a.block is None:
            h.attach = None
        return True

    def refuse(self, k):
        """The next visible line refuses the `+` stack[k] offered.  A quote
        that refuses an own-line `+` does not stay open: the `+` carried none
        of its prefix, and only a description or note body that refuses one
        stays open for the next line (CARVE-P9-067).  Returns False, or
        'host closed' when the line must be walked again."""
        h = self.stack[k]
        a = h.attach
        h.attach = None
        if h.kind == "quote" and a.form == "own":
            self.close_frames(k - 1)
            return "host closed"
        return False

    def is_invisible_text(self, t):
        if t.startswith("{") and (self.attr_line(t) is not None or braced_only(t)):
            return True
        return t.startswith("%%%")

    def attr_run_extent(self, j0, lv, col0):
        """A block attribute run whose open first line is lines[j0 - 1],
        read at frame level lv with its `{` at column col0: continuation
        lines must reach level lv and stand past col0 (PART 9 §15 A5).
        Returns (index after its last line, items) or None."""
        lines = self.lines
        _, rs = self.walk(lines[j0 - 1], limit=lv + 1)
        parts = [rs[lv].strip(" \t")]
        j = j0
        while j < len(lines):
            rr, rs = self.walk(lines[j], limit=lv + 1)
            if rr < lv:
                return None
            c2 = rs[lv]
            if is_blank(c2) or indent_cols(c2) <= col0:
                return None
            parts.append(c2.strip(" \t"))
            if "}" in c2:
                items = self.multi_attr("\n".join(parts))
                if items is None:
                    return None
                return j + 1, items
            j += 1
        return None

    def offer_lookahead(self, k, a, start=None):
        """Whether the first visible line after the invisible lines at the
        current position passes the `+` gates."""
        lines = self.lines
        j = self.li if start is None else start
        h = self.stack[k]
        fence = None
        cur = lines[j - 1] if j > 0 else ""
        rr0, rs0 = self.walk(cur, limit=k)
        if rr0 >= k - 1:
            t0 = rs0[k - 1].strip(" \t")
            if t0.startswith("%%%"):
                fence = len(re.match(r"%{3,}", t0).group(0))
        while j < len(lines):
            rr, rs = self.walk(lines[j], limit=k)
            j += 1
            if rr < k - 1:
                return False
            p = rs[k - 1]
            t = p.strip(" \t")
            if fence is not None:
                m = re.match(r"%{3,}", t)
                if m and len(m.group(0)) == fence:
                    fence = None
                continue
            if t == "":
                return False
            if t.startswith("%%%"):
                fence = len(re.match(r"%{3,}", t).group(0))
                continue
            if t.startswith("%%"):
                continue
            if t.startswith("[") and match_link_def(t) is not None:
                continue
            if t.startswith("*[") and match_abbr_def(t) is not None:
                continue
            if self.is_invisible_text(t):
                continue
            if t.startswith("{") and self.attr_prefix_open(t):
                # a wrapped attribute run is invisible too
                ip = indent_cols(p)
                if ip == a.m or ip >= h.content_col:
                    lv = k - 1 if ip == a.m else k
                    col0 = ip if lv == k - 1 else ip - h.content_col
                    ext = self.attr_run_extent(j, lv, col0)
                    if ext is not None:
                        j = ext[0]
                        continue
            if indent_cols(p) != a.m:
                return False
            body = strip_cols(p, a.m)[0].strip(" \t")
            mk = parse_marker(body)
            if mk is not None:
                if h.kind == "item" and mk.kind in ("bullet", "ordered"):
                    return False
                if h.kind == "dd" and mk.kind in ("term", "desc"):
                    return False
            return True
        return False

    def attached_fence_line(self, h, leaf, r, res):
        """S1 for a fence a `+` attached at h's marker column.  Returns True
        when the line was consumed as payload / closer."""
        a = leaf.attached
        k = len(self.stack) - 1
        if r < k - 1:
            self.close_leaf(h)
            h.attach = None
            return False
        p = res[k - 1]
        if is_blank(p):
            if a.form == "marker" and not self.attached_closer_ahead(h, leaf, k):
                self.close_leaf(h)
                h.attach = None
                return False
            leaf.node.lines.append(strip_cols(p, a.m)[0])
            a.seen_blank = True
            return True
        ind = indent_cols(p)
        if ind < a.m:
            self.close_leaf(h)
            h.attach = None
            return False
        body = strip_cols(p, a.m)[0]
        body2 = strip_cols(body, leaf.indent)[0]
        if self.attached_closer(h, leaf, p, a.seen_blank and a.form == "marker"):
            leaf.node.closed = True
            self.close_leaf(h)
            h.attach = None
            if leaf.kind == "code":
                h.cap_host = leaf.node
                h.cap_blanks = 0
            return True
        if a.seen_blank and a.form == "own" and ind < h.content_col:
            # an own-line fence ends at a line that misses its host (S1
            # step 2); a marker-line fence past a blank has a closer ahead
            # and keeps whatever stands before it (carve#5587)
            self.close_leaf(h)
            h.attach = None
            return False
        leaf.node.lines.append(body2)
        return True

    def attached_closer(self, h, leaf, p, host_reads):
        """Whether line p closes a fence a `+` attached at h's marker column.
        A closer stands at the opener's column; a closing run indented past
        it is payload (CARVE-P2-006, plus-ownership F01).  Past the first
        blank of a marker-line fence the host reads the closer, from its
        marker column up to one column left of its content column, whatever
        stands between (carve#5579, carve#5587, plus-ownership F05)."""
        a = leaf.attached
        ind = indent_cols(p)
        hi = a.m + leaf.indent
        if host_reads:
            hi = max(hi, h.content_col - 1)
        if ind < a.m or ind > hi:
            return False
        return self.fence_closer(leaf, p.lstrip(" \t"))

    def attached_closer_ahead(self, h, leaf, k):
        """Whether a closer the host reads follows before the host ends."""
        a = leaf.attached
        if self.li <= a.closer_line:
            # payload lines change no frame, so an earlier scan still holds
            return True
        lines = self.lines
        j = self.li
        while j < len(lines):
            rr, rs = self.walk(lines[j], limit=k)
            j += 1
            if rr < k - 1:
                return False
            p = rs[k - 1]
            if is_blank(p):
                continue
            if indent_cols(p) < a.m:
                return False
            if self.attached_closer(h, leaf, p, True):
                a.closer_line = j - 1
                return True
        return False

    def attached_row(self, h, leaf, r, res):
        """Take a row of a table a `+` attached at h's marker column.
        Returns True when the line was such a row."""
        a = leaf.attached
        k = len(self.stack) - 1
        if r < k - 1:
            return False
        p = res[k - 1]
        if is_blank(p) or indent_cols(p) != a.m:
            return False
        body = strip_cols(p, a.m)[0]
        t = body.strip(" \t")
        if not (valid_row(t) or (valid_cont_row(t) and self.cont_row_ok(leaf))):
            return False
        self.bookkeep(k, res[:k] + [body], False)
        leaf.node.raw_lines.append(t)
        return True

    def cont_row_ok(self, leaf):
        """A `+` continuation row needs a row above it other than a lone
        delimiter row under the header (PART 9 §5 T6)."""
        from .tables import is_delim_row

        rl = leaf.node.raw_lines
        return not (len(rl) == 2 and is_delim_row(rl[1]))

    def fence_closer(self, leaf, body):
        tb = body.rstrip(" \t")
        if not tb or tb[0] != leaf.fch:
            return False
        k = 0
        while k < len(tb) and tb[k] == leaf.fch:
            k += 1
        return k == len(tb) and k >= leaf.flen

    # -------------------------------------------------------------- bookkeeping

    def bookkeep(self, r, res, blank, invisible=False):
        """Blank-line state for frames 0..r (L1, N1a).

        A footnote definition is invisible for its full extent (CARVE-P9-013,
        PART 0 T), so no line inside it ends a blank run of the frames around
        it.  A blank inside the note is the note's when the next visible line
        is the note's own (PART 0 L6): that line gives those frames back the
        blank state they had when the note opened.  To a frame outside two
        notes, every line of the inner one is invisible."""
        stack = self.stack
        notes = [j for j in range(1, len(stack)) if stack[j].kind == "fn"]
        for k in range(r + 1):
            f = stack[k]
            if blank or is_blank(res[k]):
                f.blank_seen = True
                f.blank_count += 1
            elif notes and k < notes[-1]:
                if not invisible and sum(1 for j in notes if j > k) == 1:
                    f.blank_seen, f.blank_count = stack[notes[-1]].outer_blanks[k]
            elif not invisible:
                f.blank_before_line = f.blank_seen
                f.count_before_line = f.blank_count
                f.blank_seen = False
                f.blank_count = 0

    # -------------------------------------------------------------- S3 / S4 / S5

    def classify_and_apply(self, r, res, li):
        stack = self.stack
        deepest = len(stack) - 1
        cur = res[r]
        owner = stack[r]
        t = cur.strip(" \t")
        ind = indent_cols(cur)

        para = None
        dleaf = stack[-1].leaf
        if dleaf is not None and dleaf.kind == "para":
            para = dleaf

        form = self.classify(t, cur, owner, r, para)
        kind = form[0]
        if (
            kind in ("quote", "footnote", "colon")
            or (kind == "marker" and form[1].kind != "term")
        ) and len(stack) - 1 >= MAX_NESTING:
            form = ("text",)
            kind = "text"

        # multi-line block-position brace runs
        literal_brace = False
        if kind == "bracerun":
            # no line of a run is lazy: an opener that misses the frame of an
            # open paragraph is that paragraph's literal text (CARVE-P2-035)
            consumed = (
                None
                if r < deepest and para is not None
                else self.brace_run(r, res, li, form)
            )
            if consumed is not None:
                return
            literal_brace = form[1] == "comment"
            form = ("text",)
            kind = "text"

        # a line that reaches a quote host by its `>` prefix starts a block
        # there rather than continuing the block a `+` attached (plus-ownership
        # Q040, X07)
        fold = not (self.unrouted == r and stack[r].kind == "quote")
        if r < deepest:
            if fold and para is not None and self.lazy_ok(form, r, para):
                self.bookkeep(r, res, False)
                if literal_brace:
                    self.mark_literal_brace(para.node, len(para.node.lines))
                para.node.lines.append(t)
                para.pulled = True
                return
            top = stack[-1]
            if (
                fold
                and top.kind == "lineblock"
                and top.stanza
                and self.lazy_ok(form, r)
            ):
                # a lazy line folds into a stanza that already holds a verse
                # line; it stands left of the fence, so it keeps no leading
                # run (CARVE-P9-044, carve#4956)
                self.bookkeep(r, res, False)
                top.stanza.append(cur.lstrip(" \t"))
                return
            cleaf = top.leaf
            if (
                fold
                and cleaf is not None
                and cleaf.kind == "caption"
                and self.lazy_ok(form, r)
                and kind != "caption"
            ):
                self.bookkeep(r, res, False)
                cleaf.lines.append(cur.rstrip(" \t"))
                cleaf.src_lines.append(t)
                return
            if fold and kind == "commentfence":
                # a %%% span closes missed quotes only
                cut = None
                for k in range(r + 1, len(stack)):
                    if stack[k].kind == "quote":
                        cut = k
                        break
                if cut is not None:
                    self.close_frames(cut - 1)
                top = stack[-1]
                self.close_leaf(top)
                self.comment = CommentSpan(r, form[1])
                return
            self.close_frames(r)
            owner = stack[r]
        self.bookkeep(r, res, False, invisible=kind in INVISIBLE_FORMS)
        self.apply(form, owner, r, cur, t, ind, li)
        if literal_brace:
            lf = stack[-1].leaf
            if (
                lf is not None
                and lf.kind == "para"
                and lf.node.lines
                and lf.node.lines[-1] == t
            ):
                self.mark_literal_brace(lf.node, len(lf.node.lines) - 1)

    def mark_literal_brace(self, para, line_index):
        if para.literal_braces is None:
            para.literal_braces = set()
        para.literal_braces.add(line_index)

    def lazy_ok(self, form, r, para=None):
        """S4: may this line fold into the deepest open paragraph?"""
        kind = form[0]
        if kind in ("text", "plus"):
            # a `+` that reached no marker column is a letter (PART 0 S2)
            return True
        if kind == "caption":
            # a caret line interrupts nothing; it ends only a paragraph that is
            # a captionable host (PART 9 §10 I7).  As the first unmarked line
            # after a quote's marked lines it attaches to that quote instead
            # (CARVE-P2-008); a paragraph a lazy line has already pulled ends
            # only at a blank or an interrupting block (PART 0 lifetimes)
            if para is None:
                return False
            if not para.pulled and any(
                self.stack[k].kind == "quote" for k in range(r + 1, len(self.stack))
            ):
                return False
            return not self.image_paragraph(para.node)
        if kind == "marker":
            m = form[1]
            stack = self.stack
            only_quotes = all(
                stack[k].kind == "quote" for k in range(r + 1, len(stack))
            )
            if m.kind in ("bullet", "ordered"):
                # folds only into a document, quote or colon paragraph; read in
                # a marker body it opens a list there
                return only_quotes and stack[r].kind not in ("item", "dd", "fn")
            if m.kind == "desc":
                return only_quotes
            return False
        return False

    def classify(self, t, cur, owner, r, para):
        """Return a form tuple for the line content t in frame owner."""
        c = t[0]
        if c == "%" and t.startswith("%%%"):
            m = re.match(r"%{3,}", t)
            return ("commentfence", len(m.group(0)))
        if c == "`" or c == "~":
            m = _FENCE_RE.match(t)
            if m:
                fence = m.group(1)
                rest = m.group(2)
                rm = _RAW_RE.match(rest)
                if rm:
                    return ("raw", fence, rm.group(1))
                lang, title, label, ok = parse_fence_info(rest, c, len(fence))
                if ok:
                    return ("code", fence, lang, title, label)
        if c == "#":
            m = _HEADING_RE.match(t)
            if m and m.group(2) != "":
                return ("heading", len(m.group(1)), m.group(2))
        if c in "-*_" and _THEMATIC_RE.match(t):
            return ("hr",)
        if c == ">" and (len(t) == 1 or t[1] == " "):
            return ("quote", t[2:] if len(t) > 1 else "")
        if c == "[" and t.startswith("[^"):
            m = _FOOTNOTE_RE.match(t)
            if m and m.group(3).strip(" \t") != "":
                return (
                    "footnote",
                    m.group(1),
                    m.group(3),
                    len(m.group(1)) + len(m.group(2)) + 2,
                )
        if c == "{":
            in_span = para is not None and open_backtick("\n".join(para.node.lines))
            if not in_span:
                a = self.attr_line(t)
                if a is not None:
                    return ("attrs", a)
                if t.startswith("{%"):
                    if t.find("%}") < 0:
                        return ("bracerun", "comment")
                elif self.attr_prefix_open(t):
                    return ("bracerun", "attrs")
        if c in "-*.:" or ("0" <= c <= "9") or ("a" <= c <= "z") or ("A" <= c <= "Z"):
            m = parse_marker(t)
            if m is not None and (
                m.kind != "desc" or (self.dl_open(owner) and owner.blank_count < 3)
            ):
                return ("marker", m)
        if c == "|" and valid_row(t):
            return ("row",)
        if c == "+":
            if t == "+":
                return ("plus",)
            if (
                valid_cont_row(t)
                and owner.leaf is not None
                and owner.leaf.kind == "table"
                and self.cont_row_ok(owner.leaf)
            ):
                return ("controw",)
        if c == ":":
            o = parse_colon_opener(t)
            if o is not None:
                return ("colon", o)
        if c == "^" and len(t) > 1 and t[1] == " ":
            content = t[1:].lstrip(" ")
            if content and not _comment_only(content):
                return ("caption", content)
        return ("text",)

    def dl_open(self, owner):
        ch = owner.children
        if not ch:
            return False
        last = ch[-1]
        return isinstance(last, DefList) and not last.sealed

    def attr_line(self, t):
        """A single-line block attribute line: one or more glued blocks."""
        j = 0
        items = []
        n = len(t)
        while j < n:
            if t[j] != "{":
                return None
            r = parse_attr_block(t, j)
            if r is None:
                return None
            items.extend(r[0])
            j = r[1]
        return items

    def attr_prefix_open(self, t):
        """Whether t could start a multi-line attribute block (no closing
        brace on this line for the last block)."""
        j = 0
        n = len(t)
        while j < n and t[j] == "{":
            r = parse_attr_block(t, j)
            if r is None:
                return "}" not in t[j:]
            j = r[1]
        return False

    def brace_run(self, r, res, li, form):
        """A block-position brace run continuing past its opener
        (CARVE-P2-035).  Returns True when consumed."""
        stack = self.stack
        cur = res[r]
        col = indent_cols(cur)
        t = cur.strip(" \t")
        parts = [t]
        j = self.li
        lines = self.lines
        while j < len(lines):
            rr, rs = self.walk(lines[j], limit=r + 1)
            if rr < r:
                return None
            c2 = rs[r]
            if is_blank(c2):
                return None
            if indent_cols(c2) <= col:
                return None
            parts.append(c2.strip(" \t"))
            text = "\n".join(parts)
            if form[1] == "comment":
                if "%}" in c2:
                    k = text.find("%}")
                    rest = text[k + 2 :].strip(" \t")
                    if rest == "" or braced_only(rest):
                        self.li = j + 1
                        if r < len(stack) - 1:
                            self.close_frames(r)
                        o = stack[r]
                        self.close_leaf(o)
                        return True
                    return None
            else:
                if "}" in c2:
                    items = self.multi_attr(text)
                    if items is None:
                        return None
                    self.li = j + 1
                    if r < len(stack) - 1:
                        self.close_frames(r)
                    o = stack[r]
                    self.close_leaf(o)
                    at = items_to_attrs(items)
                    if o.pending is None:
                        o.pending = at
                    else:
                        o.pending.merge(at)
                    o.cap_host = None
                    return True
            j += 1
        return None

    def multi_attr(self, text):
        j = 0
        items = []
        n = len(text)
        while j < n:
            if text[j] != "{":
                return None
            r = parse_attr_block(text, j, multiline=True)
            if r is None:
                return None
            items.extend(r[0])
            j = r[1]
            while j < n and text[j] == "\n":
                return None
        return items

    # -------------------------------------------------------------- apply

    def apply(self, form, owner, r, cur, t, ind, li):
        kind = form[0]
        stack = self.stack
        leaf = owner.leaf
        if leaf is not None and stack[-1] is owner:
            lk = leaf.kind
            if lk == "para" and not leaf.no_marked_cont:
                if kind == "text":
                    leaf.node.lines.append(t)
                    return
                if kind == "marker":
                    mk = form[1].kind
                    if mk in ("bullet", "ordered") and owner.kind in (
                        "doc",
                        "quote",
                        "div",
                    ):
                        leaf.node.lines.append(t)
                        return
                    if (
                        mk == "desc"
                        and owner.kind in ("quote", "doc", "div")
                        and not self.dl_open(owner)
                    ):
                        leaf.node.lines.append(t)
                        return
                if kind == "caption":
                    if self.image_paragraph(leaf.node):
                        self.close_leaf(owner)
                        self.start_caption(owner, leaf.node, form[1], t)
                        return
                    leaf.node.lines.append(t)
                    return
                if kind in ("controw",):
                    leaf.node.lines.append(t)
                    return
                if kind == "plus":
                    leaf.node.lines.append(t)
                    return
            elif lk == "caption":
                if kind in ("text", "plus") or (
                    kind == "marker" and form[1].kind in ("bullet", "ordered")
                ):
                    # a continuation line keeps its leading run (CARVE-P2-020)
                    leaf.lines.append(cur.rstrip(" \t"))
                    leaf.src_lines.append(t)
                    return
            elif lk == "table" and (kind == "row" or kind == "controw"):
                leaf.node.raw_lines.append(t)
                return
        self.close_leaf(owner)

        if kind == "text":
            self.start_para(owner, t)
        elif kind == "heading":
            h = Heading(form[1], form[2], self.take_pending(owner))
            self.add_block(owner, h)
        elif kind == "hr":
            self.add_block(owner, ThematicBreak(self.take_pending(owner)))
        elif kind == "code":
            fence, lang, title, label = form[1], form[2], form[3], form[4]
            node = CodeBlock(lang, title, label, self.take_pending(owner))
            self.add_block(owner, node)
            lf = Leaf("code", node, ind)
            lf.fch = fence[0]
            lf.flen = len(fence)
            owner.leaf = lf
        elif kind == "raw":
            fence, fmt = form[1], form[2]
            node = RawBlock(fmt, self.take_pending(owner))
            self.add_block(owner, node)
            lf = Leaf("raw", node, ind)
            lf.fch = fence[0]
            lf.flen = len(fence)
            owner.leaf = lf
        elif kind == "commentfence":
            self.comment = CommentSpan(r, form[1])
            owner.cap_host = None
        elif kind == "quote":
            q = BlockQuote(self.take_pending(owner))
            self.add_block(owner, q)
            f = Frame("quote", q)
            f.marker_col = ind
            stack.append(f)
            self.apply_rest(f, form[1], li, cur)
        elif kind == "footnote":
            label, content = form[1], form[2]
            key = label_key(label)
            if content.strip(" \t") == "+" and key in self.note_keys:
                # a losing duplicate whose body is a lone `+`: the `+` takes
                # nothing, and the lines below belong to the container the
                # definition stands in (PART 9R R2)
                return
            self.note_keys.add(key)
            ch = owner.children
            if ch and isinstance(ch[-1], (ListBlock, DefList)):
                # the definition is a block between that list and any later
                # item, which is then no adjacent sibling (PART 9 §11 N1)
                ch[-1].sealed = True
            fn = FootnoteDef(label)
            self.footnotes.append(fn)
            f = Frame("fn", fn, content_col=ind + 2)
            f.marker_col = ind
            f.outer_blanks = [(g.blank_seen, g.blank_count) for g in stack]
            stack.append(f)
            self.apply_rest(f, content, li, cur, lead=form[3])
        elif kind == "attrs":
            a = items_to_attrs(form[1])
            if owner.pending is None:
                owner.pending = a
            else:
                owner.pending.merge(a)
            owner.cap_host = None
        elif kind == "marker":
            self.open_marker(owner, form[1], ind, li, cur)
        elif kind == "row":
            node = Table(self.take_pending(owner))
            node.raw_lines.append(t)
            self.add_block(owner, node)
            owner.leaf = Leaf("table", node)
        elif kind == "colon":
            self.open_colon(owner, form[1], ind, t, li)
        elif kind == "caption":
            host = owner.cap_host
            if host is not None and owner.cap_blanks <= 1:
                self.start_caption(owner, host, form[1], t)
            else:
                self.start_para(owner, t)
        elif kind == "plus":
            # a `+` reaching no marker column is a letter
            self.start_para(owner, t)
        else:
            self.start_para(owner, t)

    def apply_rest(self, f, rest, li, cur=None, marker_body=False, lead=0):
        """Classify the rest of a container's marker line in the new frame.
        A block opened there stands at its written column (PART 0 S3,
        CARVE-P9-083): `lead` counts the columns between the frame's content
        column and the rest, which a task box, marker-glued attributes or a
        note's label occupy without moving the content column."""
        t = rest.strip(" \t")
        if t == "":
            return
        if marker_body and rest[0] == "\t":
            # a tab past the separator is the first content character, and
            # what follows is paragraph text whatever it spells (CARVE-P2-010)
            self.start_para(f, rest.rstrip(" \t"))
            return
        if t.startswith("%%") and not t.startswith("%%%") and is_region_marker(t):
            return
        if self.erase_line(t):
            return
        if t == "+":
            a = Attach(f.marker_col, "marker")
            f.attach = a
            return
        form = self.classify(t, rest, f, len(self.stack) - 1, None)
        if form[0] == "bracerun":
            form = ("text",)
        if (
            form[0] in ("quote", "footnote", "colon")
            or (form[0] == "marker" and form[1].kind != "term")
        ) and len(self.stack) - 1 >= MAX_NESTING:
            form = ("text",)
        if form[0] in ("code", "raw", "colon"):
            # a fence's lines move left only by the space before its opener
            lead = 0
        self.apply(form, f, len(self.stack) - 1, rest, t, indent_cols(rest) + lead, li)

    # -------------------------------------------------------------- blocks

    def take_pending(self, owner):
        p = owner.pending
        owner.pending = None
        return p

    def add_block(self, owner, node):
        owner.children.append(node)
        owner.cap_host = None
        if owner.kind == "item" and owner.had_visible and owner.blank_before_line:
            owner.list.loose = True
        owner.had_visible = True
        owner.blank_before_line = False
        if owner.kind == "quote":
            owner.node.has_content = True

    def start_para(self, owner, t):
        p = Paragraph([t], self.take_pending(owner))
        self.add_block(owner, p)
        owner.leaf = Leaf("para", p)

    def start_caption(self, owner, host, content, src=None):
        lf = Leaf("caption", None)
        lf.host = host
        lf.lines = [content]
        lf.src_lines = [src if src is not None else "^ " + content]
        owner.leaf = lf
        owner.cap_host = None

    def image_paragraph(self, para):
        from .inline import parse_inline
        from .nodes import Comment, Image, Math, RefLink

        nodes, _ = parse_inline("\n".join(para.lines))
        vis = [n for n in nodes if not isinstance(n, Comment)]
        if len(vis) != 1:
            return False
        n = vis[0]
        if isinstance(n, Image) or (isinstance(n, RefLink) and n.image):
            return True
        if isinstance(n, Math) and n.display:
            para.math_host = True
            return True
        return False

    def close_leaf(self, frame):
        lf = frame.leaf
        if lf is None:
            return
        frame.leaf = None
        k = lf.kind
        if k == "para":
            frame.cap_host = None
        elif k == "caption":
            lf.host.caption = Caption(lf.lines, lf.src_lines)
            frame.cap_host = None
        elif k == "table":
            frame.cap_host = lf.node
            frame.cap_blanks = 0
        elif k in ("code", "raw"):
            node = lf.node
            if not node.closed:
                if self.li >= len(self.lines) and not self.last_nl:
                    node.final_nl = False
                frame.cap_host = None
            if lf.attached is not None and frame.attach is lf.attached:
                frame.attach = None

    def blank_line(self, r):
        stack = self.stack
        if r < len(stack) - 1:
            # an unmarked blank ends the quotes it misses
            self.close_frames(r)
        owner = stack[r]
        lf = owner.leaf
        if lf is not None:
            if lf.kind == "para":
                host = lf.node if self.image_paragraph_cheap(lf.node) else None
                self.close_leaf(owner)
                if host is not None:
                    owner.cap_host = host
                    owner.cap_blanks = 1
                return
            if lf.kind in ("caption", "table"):
                self.close_leaf(owner)
                if owner.cap_host is not None:
                    owner.cap_blanks = 1
                return
        if owner.cap_host is not None:
            owner.cap_blanks += 1

    def image_paragraph_cheap(self, para):
        t = "\n".join(para.lines)
        if not (t.startswith(("![", "$$`", "{%"))):
            return False
        return self.image_paragraph(para)

    def invisible_line(self, r):
        stack = self.stack
        if r < len(stack) - 1:
            self.close_frames(r)
        owner = stack[r]
        self.close_leaf(owner)
        owner.cap_host = None
        ch = owner.children
        if ch and isinstance(ch[-1], (ListBlock, DefList)):
            ch[-1].sealed = True

    # -------------------------------------------------------------- lists

    def open_marker(self, owner, m, ind, li, cur):
        stack = self.stack
        if m.kind in ("bullet", "ordered"):
            lst = None
            ch = owner.children
            if (
                ch
                and isinstance(ch[-1], ListBlock)
                and not ch[-1].sealed
                and owner.pending is None
            ):
                last = ch[-1]
                if self.same_list(last, m) and owner.count_before_line < 3:
                    lst = last
            if lst is None:
                lst = ListBlock(
                    m.kind == "ordered",
                    m.bullet,
                    m.dialect,
                    m.delim,
                    task=m.task is not None,
                    attrs=self.take_pending(owner),
                )
                lst.first_marker = m
                if m.kind == "ordered":
                    lst.first_value = m.value
                    lst.bare = m.bare
                self.add_block(owner, lst)
            else:
                if owner.blank_before_line:
                    lst.loose = True
                owner.cap_host = None
            item = ListItem(items_to_attrs(m.attrs) if m.attrs else None, m.task)
            item.marker = m
            lst.items.append(item)
            f = Frame("item", item, content_col=ind + m.width + m.spaces)
            f.marker_col = ind
            f.list = lst
            stack.append(f)
            self.apply_rest(f, m.content, li, cur, marker_body=True, lead=m.lead)
            return
        if m.kind == "term":
            dl = None
            ch = owner.children
            if (
                ch
                and isinstance(ch[-1], DefList)
                and not ch[-1].sealed
                and owner.count_before_line < 3
                and owner.pending is None
            ):
                dl = ch[-1]
            if dl is None:
                dl = DefList(self.take_pending(owner))
                self.add_block(owner, dl)
            else:
                owner.cap_host = None
            dl.items.append(DefTerm(m.content.rstrip(" \t"), None))
            return
        if m.kind == "desc":
            dl = owner.children[-1]
            dd = DefDesc()
            dl.items.append(dd)
            owner.cap_host = None
            f = Frame("dd", dd, content_col=ind + m.width + m.spaces)
            f.marker_col = ind
            f.dl = dl
            stack.append(f)
            self.apply_rest(f, m.content, li, cur, marker_body=True, lead=m.lead)
            return

    def same_list(self, lst, m):
        if m.kind == "bullet":
            if lst.ordered or lst.bullet != m.bullet:
                return False
            return lst.task == (m.task is not None)
        if not lst.ordered or lst.delim != m.delim:
            return False
        d = lst.dialect
        md = m.dialect
        if len(lst.items) == 1 and lst.first_marker.ambiguous:
            # N3: the second marker decides an ambiguous first letter
            fm = lst.first_marker
            fv_alpha = ord(fm.text.lower()) - 96
            fv_roman = roman_value(fm.text)
            upper = fm.text.isupper()
            if md in ("roman", "ROMAN") or m.ambiguous:
                if (md in ("ROMAN", "ALPHA")) != upper:
                    return False
                if m.ambiguous:
                    # consecutive roman or consecutive letter
                    if roman_value(m.text) == fv_roman + 1:
                        lst.dialect = "ROMAN" if upper else "roman"
                        lst.decided = True
                        return True
                    if m.value == fv_alpha + 1:
                        lst.dialect = "ALPHA" if upper else "alpha"
                        lst.decided = True
                        return True
                    return False
                if m.value == fv_roman + 1:
                    lst.dialect = md
                    lst.decided = True
                    return True
                return False
            if md in ("alpha", "ALPHA"):
                if (md == "ALPHA") != upper:
                    return False
                if m.value == fv_alpha + 1:
                    lst.dialect = md
                    lst.decided = True
                    return True
                return False
            return False
        if d == md:
            return True
        if m.ambiguous:
            if d in ("roman", "ROMAN") and ((d == "ROMAN") == m.text.isupper()):
                return True
            if d in ("alpha", "ALPHA") and ((d == "ALPHA") == m.text.isupper()):
                return True
        return False

    # -------------------------------------------------------------- colon fences

    def open_colon(self, owner, o, ind, t, li):
        flen, kind, title, label, ok = o
        stack = self.stack
        attrs = self.take_pending(owner)
        if kind == ">":
            q = BlockQuote(attrs, fenced=True)
            self.add_block(owner, q)
            f = Frame("div", q, indent=ind)
            f.fence_len = flen
            stack.append(f)
            return
        in_group = any(isinstance(g.node, Div) and g.node.is_figure for g in stack)
        d = Div(kind, title, label, attrs, flen)
        if kind == "figure" and title is None and label is None and ok and not in_group:
            d.is_figure = True
        self.add_block(owner, d)
        fk = "lineblock" if kind == "|" else "div"
        f = Frame(fk, d, indent=ind)
        f.fence_len = flen
        if fk == "lineblock":
            d.stanzas = []
        stack.append(f)

    def verse_line(self, f, cur, r):
        d = f.node
        if is_colon_closer(cur, f.fence_len):
            self.close_frames(r - 1, closer=True)
            return
        t = cur.rstrip(" \t")
        if t == "" or is_blank(t):
            f.stanza = None
            return
        if t.startswith("%%") and not t.startswith("%%%"):
            if f.stanza is None:
                f.stanza = []
                d.stanzas.append(f.stanza)
            f.stanza.append(None)
            return
        lt = t.lstrip(" ")
        if lt.startswith("%%%") and (len(t) - len(lt)) <= 3:
            m = re.match(r"%{3,}", lt)
            self.comment = CommentSpan(r, len(m.group(0)), lineblock=True)
            return
        if f.stanza is None:
            f.stanza = []
            d.stanzas.append(f.stanza)
        f.stanza.append(cur)

    # -------------------------------------------------------------- closing

    def close_frames(self, keep, closer=False):
        """Close frames above index keep."""
        stack = self.stack
        while len(stack) - 1 > keep:
            f = stack.pop()
            self.close_leaf(f)
            is_closed_here = closer and len(stack) - 1 == keep
            node = f.node
            if isinstance(node, Div):
                node.closed = is_closed_here
            parent = stack[-1]
            if f.kind == "quote":
                parent.cap_host = node if node.has_content else None
                parent.cap_blanks = 0
            elif (
                f.kind == "div"
                and is_closed_here
                and (
                    isinstance(node, BlockQuote)
                    or (isinstance(node, Div) and node.is_figure)
                )
            ):
                parent.cap_host = node
                parent.cap_blanks = 0
            else:
                parent.cap_host = None
            if f.kind == "item":
                f.list.sealed = False
            parent.leaf = None
            if parent.attach is not None and parent.attach.block is f:
                parent.attach = None
