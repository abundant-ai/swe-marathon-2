"""Document-wide resolution (PART 9R): reference links, footnotes, heading
ids, caption numbering, cross-references, abbreviations and block-image
promotion."""

import re
import unicodedata

from .attrs import Attrs, items_to_attrs
from .chars import is_alnum, label_key
from .inline import parse_inline
from .nodes import (
    NBSP,
    Abbr,
    Autolink,
    BlockQuote,
    Bracket,
    CaptionNumber,
    Code,
    CodeBlock,
    Comment,
    DefDesc,
    DefList,
    DefTerm,
    Div,
    Elem,
    Esc,
    Ext,
    FootnoteDef,
    HardBreak,
    Heading,
    Image,
    InlineNote,
    Link,
    ListBlock,
    ListItem,
    Literal,
    Math,
    Mention,
    NoteRef,
    Paragraph,
    RefLink,
    Smart,
    SoftBreak,
    Span,
    Subst,
    Table,
    Text,
    Verbatim,
)
from .typography import smart_pass, social_pass

CANON = ("note", "tip", "warning", "danger", "info", "success", "example", "quote")

REVERSE = {
    "‘": "'",
    "’": "'",
    "‚": "'",
    "‛": "'",
    "“": '"',
    "”": '"',
    "„": '"',
    "‟": '"',
    "«": '"',
    "»": '"',
    "—": "---",
    "–": "--",
    "…": "...",
    "→": "-->",
    "←": "<--",
    "↔": "<-->",
    "⇒": "==>",
    "⇐": "<==",
    "⇔": "<=>",
    "≤": "<=",
    "≥": ">=",
    "≠": "!=",
    "±": "+-",
    "™": "(tm)",
    "©": "(c)",
    "®": "(r)",
}
_ID_STRIP = set(
    "\u200b\u200c\u200d\u2060\ufeff\u00ad\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
)
_NONALNUM_RUN = re.compile(r"[\x00-\x2f\x3a-\x40\x5b-\x60\x7b-\x7f]+")


_BODY_KEYS = ("body-rows", "body-header-rows", "body-header-cols")
_MAX_COUNT = 9007199254740991


def _row_count(v, absent):
    """A row-group count (PART 12 §15): `absent` when the key is missing,
    one for the empty boolean, otherwise a non-negative decimal integer, or
    None when the value is none of these."""
    if v is None:
        return absent
    if v == "":
        return 1
    if v.isascii() and v.isdigit() and int(v) <= _MAX_COUNT:
        return int(v)
    return None


def _count_list(v, empty_entry):
    """A positional count list; `empty_entry` is what an empty entry means,
    or False when an empty entry is invalid.  Returns a list or None."""
    out = []
    for e in v.split(","):
        if e == "":
            if empty_entry is False:
                return None
            out.append(empty_entry)
        elif e.isascii() and e.isdigit() and int(e) <= _MAX_COUNT:
            out.append(int(e))
        else:
            return None
    return out


def _body_partition(a, nrows):
    """The explicit partition `body-rows`, `body-header-rows` and
    `body-header-cols` state with `header-rows` / `footer-rows` (PART 12
    §15): (head, foot, [(header_rows, data_rows, header_cols), ...]), or
    None when the metadata is invalid."""
    br = a.get("body-rows")
    if br is None:
        return None
    data = [] if br == "" else _count_list(br, False)
    if data is None:
        return None
    bhr = a.get("body-header-rows")
    bhc = a.get("body-header-cols")
    if not data and (bhr is not None or bhc is not None):
        return None
    hrows = [0] * len(data) if bhr is None else _count_list(bhr, False)
    hcols = [None] * len(data) if bhc is None else _count_list(bhc, None)
    if (
        hrows is None
        or hcols is None
        or len(hrows) != len(data)
        or len(hcols) != len(data)
    ):
        return None
    head = _row_count(a.get("header-rows"), 0)
    foot = _row_count(a.get("footer-rows"), 0)
    if head is None or foot is None:
        return None
    if head + foot + sum(data) + sum(hrows) != nrows:
        return None
    return head, foot, list(zip(hrows, data, hcols))


def slugify(text):
    t = unicodedata.normalize("NFC", text)
    t = "".join(ch for ch in t if ch not in _ID_STRIP)
    t = "".join(REVERSE.get(ch, ch) for ch in t)
    t = _NONALNUM_RUN.sub("-", t)
    t = t.strip("-")
    if not t:
        return "s"
    if unicodedata.category(t[0])[0] == "N":
        t = "s-" + t
    return t


def plain_text(nodes, for_id=False):
    """Text an inline run carries (CARVE-P2-004 / R4 derivation)."""
    out = []
    _plain(nodes, out, for_id)
    return "".join(out)


def _plain(nodes, out, for_id):
    for nd in nodes:
        t = type(nd)
        if t is Text:
            out.append(nd.s)
        elif t is Esc:
            out.append(nd.ch)
        elif t is NBSP:
            out.append(" ")
        elif t is SoftBreak or t is HardBreak:
            out.append("\n")
        elif t is Smart:
            out.append(nd.glyph)
        elif t is Verbatim:
            out.append(nd.s)
        elif t in (Code, Math, Literal):
            out.append(nd.value)
        elif t is Autolink:
            out.append(nd.text)
        elif t is Image:
            out.append(nd.alt)
        elif t is RefLink:
            if nd.image:
                out.append(nd.alt)
            elif nd.children is not None:
                _plain(nd.children, out, for_id)
        elif t in (Elem, Span, Link, Ext):
            _plain(nd.children, out, for_id)
        elif t is Bracket:
            out.append("![" if nd.bang else "[")
            _plain(nd.children, out, for_id)
            out.append("]")
        elif t is Subst:
            _plain(nd.old, out, for_id)
            _plain(nd.new, out, for_id)
        elif t is Mention:
            out.append(nd.sigil + nd.name)
        elif t is Abbr:
            out.append(nd.term)
        elif t is CaptionNumber:
            out.append(nd.value)
        # comments, critic comments, raw, notes, crossrefs, symbols: nothing


_CONTAINERS = (BlockQuote, Div, ListItem, DefDesc, FootnoteDef)


def walk_blocks(blocks):
    """Every block node in document order (pre-order), as a list."""
    out = []
    stack = [iter(blocks)]
    while stack:
        for b in stack[-1]:
            out.append(b)
            if isinstance(b, _CONTAINERS):
                stack.append(iter(b.children))
                break
            if isinstance(b, (ListBlock, DefList)):
                stack.append(iter(b.items))
                break
        else:
            stack.pop()
    return out


class Resolver:
    def __init__(self, bp, safe=False):
        self.bp = bp
        self.doc = bp.doc
        self.safe = safe
        self.linkdefs = {}
        for label, dest, title, items in bp.linkdefs:
            self.linkdefs[label_key(label)] = (
                dest,
                title,
                items_to_attrs(items) if items else None,
            )
        self.abbrs = {}
        for term, exp in bp.abbrdefs:
            self.abbrs[term] = exp
        self.fndefs = {}
        for fn in bp.footnotes:
            k = label_key(fn.label)
            if k not in self.fndefs:
                self.fndefs[k] = fn
        self.heading_ids = {}
        self.caption_ids = {}
        self.used_ids = set()
        self.notes = []  # ordered endnotes: (number, kind, obj)
        self.note_by_key = {}
        self.note_refs = {}  # number -> list of ref ids
        self.adm_counter = 0

    # ---------------------------------------------------------------- inline parsing

    def parse_inlines(
        self,
        src,
        in_cell=False,
        line_block=False,
        hardbreaks=False,
        no_tags=False,
        literal=None,
    ):
        nodes, p = parse_inline(
            src, in_cell=in_cell, line_block=line_block, literal=literal
        )
        nodes = social_pass(nodes, p, no_tags=no_tags)
        if line_block or hardbreaks:
            nodes = _soft_to_hard(nodes, deep=line_block)
        smart_pass(nodes)
        return nodes, p

    def parse_all(self, blocks, ctx=None):
        for b in walk_blocks(blocks):
            t = type(b)
            if t is Paragraph:
                if b.inlines is None:
                    b.inlines, b.parser = self.parse_inlines(
                        "\n".join(b.lines),
                        hardbreaks=b.hardbreaks,
                        literal=_literal_offsets(b),
                    )
            elif t is Heading or t is DefTerm:
                b.inlines, b.parser = self.parse_inlines(b.text)
            elif t is Div:
                if b.title is not None:
                    b.title_inlines, _ = self.parse_inlines(b.title)
                if b.label is not None:
                    b.label_inlines, _ = self.parse_inlines(b.label)
                if b.kind == "|" and b.stanzas is not None:
                    b.children = [self.verse_para(st) for st in b.stanzas]
                if b.kind == "\\":
                    for c in b.children:
                        if isinstance(c, Paragraph):
                            c.hardbreaks = True
                            c.inlines, c.parser = self.parse_inlines(
                                "\n".join(c.lines), hardbreaks=True
                            )
            elif t is Table and not b.csv:
                self.parse_table(b)
            cap = (
                getattr(b, "caption", None)
                if t in (Paragraph, CodeBlock, BlockQuote, Table, Div)
                else None
            )
            if cap is not None and cap.inlines is None:
                cap.inlines, cap.parser = self.parse_inlines(
                    "\n".join(cap.lines), no_tags=False
                )

    def verse_para(self, stanza):
        """A line-block stanza: leading whitespace and 2+ column gaps kept."""
        lines = []
        for ln in stanza:
            if ln is None:
                lines.append("")
                continue
            ln = ln.rstrip(" \t") if not _ends_gap(ln) else ln
            lines.append(ln)
        p = Paragraph(lines)
        p.line_block = True
        p.inlines, p.parser = self.verse_inlines(lines)
        return p

    def verse_inlines(self, lines):
        # Convert leading whitespace and medial/trailing gaps of 2+ columns
        # to NBSP content; tabs count by columns.
        out_lines = []
        for ln in lines:
            out_lines.append(_verse_line(ln))
        src = "\n".join(out_lines)
        nodes, p = parse_inline(src, line_block=True)
        nodes = social_pass(nodes, p)
        nodes = _soft_to_hard(nodes, deep=True)
        smart_pass(nodes)
        return nodes, p

    def parse_table(self, tb):
        from .tables import build_grid, parse_table

        rows = parse_table(tb.raw_lines, tb.attrs)
        nrows = len([r for r in rows if not r.delim])
        partition = None
        col_h = col_v = None
        widths = None
        a = tb.attrs
        if a is not None:
            hr = a.get("header-rows")
            fr = a.get("footer-rows")
            if any(a.has(k) for k in _BODY_KEYS):
                # explicit bodies: valid metadata is consumed, invalid metadata
                # leaves every row-group key an ordinary attribute
                partition = _body_partition(a, nrows)
                if partition is not None:
                    for k in ("header-rows", "footer-rows") + _BODY_KEYS:
                        a.remove(k)
            elif hr is not None or fr is not None:
                h, f = _row_count(hr, 0), _row_count(fr, 0)
                a.remove("header-rows")
                a.remove("footer-rows")
                if h is not None and f is not None and h + f <= nrows:
                    partition = (h, f, None)
                else:
                    partition = (0, 0, None)
            al = a.get("aligns")
            if al is not None:
                vals = [x.strip() for x in al.split(",")]
                if all(v in ("", "left", "right", "center") for v in vals):
                    col_h = [v or None for v in vals]
                    a.remove("aligns")
            vl = a.get("valigns")
            if vl is not None:
                vals = [x.strip() for x in vl.split(",")]
                if all(v in ("", "top", "middle", "bottom") for v in vals):
                    col_v = [v or None for v in vals]
                    a.remove("valigns")
            wd = a.get("widths")
            if wd is not None:
                vals = [x.strip() for x in wd.split(",")]
                ok = True
                ws = []
                for v in vals:
                    if v == "":
                        ws.append(None)
                        continue
                    try:
                        fv = float(v)
                    except ValueError:
                        ok = False
                        break
                    if not (0 < fv <= 100):
                        ok = False
                        break
                    ws.append(v)
                if ok:
                    widths = ws
                    a.remove("widths")
            if not a:
                tb.attrs = None
        g = build_grid(rows, partition, col_h, col_v)
        if widths is not None:
            g.widths = widths[: max(g.ncols, 0) or len(widths)]
        for row in g.rows:
            for cell in row.cells:
                if cell.covered:
                    continue
                cell.inlines, cell.parser = self.parse_inlines(
                    cell.content, in_cell=True
                )
        tb.grid = g

    # ---------------------------------------------------------------- main

    def run(self):
        doc = self.doc
        self.transform(doc.children)
        for fn in self.fndefs.values():
            self.transform(fn.children)
        self.parse_all(doc.children)
        for fn in self.fndefs.values():
            self.parse_all(fn.children)
        # 1. reference links against definitions
        self.resolve_refs_all(doc.children)
        for fn in self.fndefs.values():
            self.resolve_refs_all(fn.children)
        # 2. footnote numbering (body, then endnotes in order)
        self.number_notes()
        # 3. heading ids
        self.assign_ids()
        # 4. heading-index fallback for collapsed references
        self.resolve_heading_refs()
        # 5. block images, captions and numbering
        self.promote_images(doc.children)
        for num, kind, obj in self.notes:
            if kind == "def":
                self.promote_images(obj.children)
        self.number_captions()
        # 6. abbreviations
        if self.abbrs:
            self.apply_abbrs_blocks(doc.children)
            for num, kind, obj in self.notes:
                if kind == "def":
                    self.apply_abbrs_blocks(obj.children)
                else:
                    self.apply_abbrs_inlines(obj.children)
        # 7. admonition ids
        self.mint_admonition_ids()

    # ---------------------------------------------------------------- transforms

    def transform(self, blocks):
        """Consumed structural keys: `loose` on lists and definition lists,
        `table` on csv/tsv fences."""
        for k, b in enumerate(blocks):
            if isinstance(b, (ListBlock, DefList)) and b.attrs is not None:
                if b.attrs.has("loose") and b.attrs.get("loose") == "":
                    b.attrs.remove("loose")
                    if isinstance(b, ListBlock):
                        b.force_loose = True
                    else:
                        b.loose = True
                    if not b.attrs:
                        b.attrs = None
            elif (
                isinstance(b, CodeBlock)
                and b.attrs is not None
                and b.lang in ("csv", "tsv")
                and b.attrs.has("table")
                and b.attrs.get("table") == ""
            ):
                t = self.csv_table(b)
                if t is not None:
                    blocks[k] = t
                    continue
            for attr in ("children", "items"):
                ch = getattr(b, attr, None)
                if isinstance(ch, list) and not isinstance(b, (Paragraph, Heading)):
                    self.transform(ch)

    def csv_table(self, b):
        from .tables import Cell, Grid, Row

        content = "\n".join(b.lines)
        if b.lines and (b.closed or b.final_nl):
            content += "\n"
        recs = parse_csv(content, "," if b.lang == "csv" else "\t")
        if recs is None:
            return None
        attrs = b.attrs.copy()
        attrs.remove("table")
        # PART 9 §5 DELIMITED BODY: the first record is a header unless an
        # explicit count says otherwise; a value that is no count is absent
        n = len(recs)
        hr = attrs.get("header-rows")
        fr = attrs.get("footer-rows")
        explicit = hr is not None or fr is not None
        attrs.remove("header-rows")
        attrs.remove("footer-rows")
        head = _row_count(hr, None)
        foot = _row_count(fr, 0)
        scope = "col"
        if foot is None:
            head, foot = 0, 0
        elif head is None:
            head = 0 if n == 0 or foot >= n else 1
        elif head + foot > n:
            if foot == 0:
                # a count past the last row: every record a header cell, at
                # row scope, in one body (CARVE-P12-034)
                head, scope, explicit = n, "row", False
            else:
                head, foot = 0, 0
        width = max([len(r) for r in recs] + [0])
        tb = Table(attrs if attrs else None)
        g = Grid()
        for ri, rec in enumerate(recs):
            row = Row()
            for v in rec + [""] * (width - len(rec)):
                c = Cell()
                c.content = v
                c.inlines = [Text(v, -1)] if v else []
                if ri < head:
                    c.header = True
                    c.scope = scope
                row.cells.append(c)
            g.rows.append(row)
        if scope == "row":
            g.single_body = True
        g.head_count = head
        g.foot_count = foot
        g.explicit = explicit
        g.ncols = width
        tb.grid = g
        tb.csv = True
        tb.caption = b.caption
        return tb

    # ---------------------------------------------------------------- references

    def iter_inline_holders(self, blocks):
        for b in walk_blocks(blocks):
            t = type(b)
            if t in (Paragraph, Heading, DefTerm):
                if b.inlines is not None:
                    yield b.inlines
            elif t is Table and b.grid is not None:
                for row in b.grid.rows:
                    for c in row.cells:
                        if not c.covered and c.inlines is not None:
                            yield c.inlines
            elif t is Div:
                if b.title_inlines:
                    yield b.title_inlines
                if b.label_inlines:
                    yield b.label_inlines
            cap = (
                getattr(b, "caption", None)
                if t in (Paragraph, CodeBlock, BlockQuote, Table, Div)
                else None
            )
            if cap is not None and cap.inlines is not None:
                yield cap.inlines

    def resolve_refs_all(self, blocks):
        for nodes in self.iter_inline_holders(blocks):
            self.resolve_refs(nodes)

    def resolve_refs(self, nodes):
        for nd in nodes:
            t = type(nd)
            if t is RefLink:
                k = label_key(nd.label)
                d = self.linkdefs.get(k)
                if d is not None:
                    nd.resolved = d
                if nd.children is not None:
                    self.resolve_refs(nd.children)
            elif t in (Elem, Span, Link, Ext, Bracket, InlineNote):
                self.resolve_refs(nd.children)
            elif t is Subst:
                self.resolve_refs(nd.old)
                self.resolve_refs(nd.new)

    def resolve_heading_refs(self):
        index = {}
        for h, in_quote in self.headings_in_order():
            if h.id is None or in_quote:
                continue
            txt = plain_text(h.inlines)
            key = unicodedata.normalize("NFC", label_key(txt))
            if key and key not in index:
                index[key] = h.id
        if not index:
            return
        for nodes in self.all_inline_holders():
            self._heading_refs(nodes, index)

    def _heading_refs(self, nodes, index):
        for nd in nodes:
            t = type(nd)
            if t is RefLink:
                if (
                    nd.resolved is None
                    and nd.collapsed
                    and not nd.image
                    and nd.children is not None
                ):
                    txt = plain_text(nd.children)
                    key = unicodedata.normalize("NFC", label_key(txt))
                    hid = index.get(key)
                    if hid is not None:
                        nd.resolved = ("#" + hid, None, None)
                if nd.children is not None:
                    self._heading_refs(nd.children, index)
            elif t in (Elem, Span, Link, Ext, Bracket, InlineNote):
                self._heading_refs(nd.children, index)
            elif t is Subst:
                self._heading_refs(nd.old, index)
                self._heading_refs(nd.new, index)

    def all_inline_holders(self):
        yield from self.iter_inline_holders(self.doc.children)
        for num, kind, obj in self.notes:
            if kind == "def":
                yield from self.iter_inline_holders(obj.children)
            else:
                yield obj.children

    # ---------------------------------------------------------------- footnotes

    def number_notes(self):
        self.next_num = 1
        for nodes in self.iter_inline_holders(self.doc.children):
            self._notes(nodes, False)
        k = 0
        while k < len(self.notes):
            _, kind, obj = self.notes[k]
            if kind == "def":
                for nodes in self.iter_inline_holders(obj.children):
                    self._notes(nodes, False)
            k += 1

    def _notes(self, nodes, in_link):
        for nd in nodes:
            t = type(nd)
            if t is NoteRef:
                key = label_key(nd.label)
                fn = self.fndefs.get(key)
                if fn is None:
                    continue
                nd.resolved = True
                ent = self.note_by_key.get(key)
                if ent is None:
                    num = self.next_num
                    self.next_num += 1
                    ent = num
                    self.note_by_key[key] = num
                    self.notes.append((num, "def", fn))
                    fn.used = True
                    self.note_refs[num] = []
                num = ent
                refs = self.note_refs[num]
                kth = len(refs) + 1
                rid = nd.attrs.id() if nd.attrs is not None and nd.attrs.id() else None
                if rid is None:
                    rid = f"fnref{num}" if kth == 1 else f"fnref{num}-{kth}"
                refs.append(rid)
                nd.number = num
                nd.ref_id = rid
            elif t is InlineNote:
                num = self.next_num
                self.next_num += 1
                self.notes.append((num, "inline", nd))
                rid = nd.attrs.id() if nd.attrs is not None and nd.attrs.id() else None
                if rid is None:
                    rid = f"fnref{num}"
                self.note_refs[num] = [rid]
                nd.number = num
                nd.ref_id = rid
            elif t is RefLink:
                if nd.resolved is not None and nd.children is not None:
                    self._notes(nd.children, True)
            elif t is Link:
                self._notes(nd.children, True)
            elif t in (Elem, Span, Ext) or t is Bracket:
                self._notes(nd.children, in_link)
            elif t is Subst:
                self._notes(nd.old, in_link)
                self._notes(nd.new, in_link)

    # ---------------------------------------------------------------- ids

    def headings_in_order(self):
        res = []
        self._headings(self.doc.children, res, False, top=True)
        # a used footnote definition's headings follow, in definition order
        used = {id(obj) for num, kind, obj in self.notes if kind == "def"}
        for fn in self.bp.footnotes:
            if id(fn) in used:
                self._headings(fn.children, res, False, top=False)
        return res

    def _headings(self, blocks, res, in_quote, top):
        for b in blocks:
            if isinstance(b, Heading):
                res.append((b, in_quote))
            elif isinstance(b, BlockQuote):
                self._headings(b.children, res, True, False)
            elif isinstance(b, (Div, ListItem, DefDesc)):
                self._headings(b.children, res, in_quote, False)
            elif isinstance(b, (ListBlock, DefList)):
                self._headings(b.items, res, in_quote, False)

    def assign_ids(self):
        used = self.used_ids
        # explicit ids the document renders
        for b in walk_blocks(self.doc.children):
            self._collect_block_id(b, used)
        for num, kind, obj in self.notes:
            if kind == "def":
                for b in walk_blocks(obj.children):
                    self._collect_block_id(b, used)
        for nodes in self.all_inline_holders():
            self._collect_inline_ids(nodes, used)
        next_suffix = {}
        for h, in_quote in self.headings_in_order():
            if h.attrs is not None and h.attrs.id() is not None:
                h.id = h.attrs.id()
                if h.id not in self.heading_ids:
                    self.heading_ids[h.id] = h
                continue
            s = slugify(plain_text(h.inlines, for_id=True))
            cand = s
            if cand in used:
                # ids are never released, so the scan resumes where the last
                # duplicate of this base stopped
                k = next_suffix.get(s, 2)
                cand = f"{s}-{k}"
                while cand in used:
                    k += 1
                    cand = f"{s}-{k}"
                next_suffix[s] = k + 1
            used.add(cand)
            h.id = cand
            h.plain = None
            if cand not in self.heading_ids:
                self.heading_ids[cand] = h

    def _collect_block_id(self, b, used):
        a = getattr(b, "attrs", None)
        if a is not None and isinstance(a, Attrs):
            i = a.id()
            if i is not None:
                used.add(i)
        if isinstance(b, ListBlock):
            for it in b.items:
                if it.attrs is not None and it.attrs.id() is not None:
                    used.add(it.attrs.id())

    def _collect_inline_ids(self, nodes, used):
        for nd in nodes:
            t = type(nd)
            a = getattr(nd, "attrs", None)
            if t is RefLink and nd.resolved is None:
                continue
            if t is NoteRef and not nd.resolved:
                continue
            if a is not None and isinstance(a, Attrs):
                i = a.id()
                if i is not None:
                    used.add(i)
            ch = getattr(nd, "children", None)
            if ch and t is not InlineNote:
                self._collect_inline_ids(ch, used)
            if t is Subst:
                self._collect_inline_ids(nd.old, used)
                self._collect_inline_ids(nd.new, used)

    # ---------------------------------------------------------------- images & captions

    def promote_images(self, blocks):
        for b in list(walk_blocks(blocks)):
            if isinstance(b, Paragraph) and not b.line_block:
                vis = [n for n in (b.inlines or []) if not isinstance(n, Comment)]
                if len(vis) == 1:
                    n = vis[0]
                    if isinstance(n, Image) or (
                        isinstance(n, RefLink) and n.image and n.resolved is not None
                    ):
                        b.block_image = True
                if b.caption is not None and not b.block_image and not b.math_host:
                    # the slot's source lines return to the paragraph
                    b.lines = b.lines + b.caption.src_lines
                    b.caption = None
                    b.inlines, b.parser = self.parse_inlines("\n".join(b.lines))
                    self.resolve_refs(b.inlines)

    def number_captions(self):
        self.counters = {}
        entries = []
        self._caption_hosts(self.doc.children, entries)
        for num, kind, obj in self.notes:
            if kind == "def":
                self._caption_hosts(obj.children, entries)
        groups = {}
        for ent in entries:
            kind = ent[0]
            if kind == "host":
                host = ent[1]
                self._number(host, host.caption)
            elif kind == "group":
                g = ent[1]
                if g.caption is not None:
                    r = self._number(g, g.caption)
                    if r is not None:
                        groups[id(g)] = [r[0], r[1], 0]
            elif kind == "panel":
                c, g = ent[1], ent[2]
                info = groups.get(id(g))
                if info is not None:
                    lbl, n, k = info
                    info[2] = k + 1
                    hid = (
                        c.attrs.id() if getattr(c, "attrs", None) is not None else None
                    )
                    if hid is not None and hid not in self.caption_ids:
                        self.caption_ids[hid] = (lbl, f"{n}{_panel_letter(k)}")

    def _number(self, host, cap):
        """Replace the first bare `#` of a caption with its number.  Returns
        (label_nodes, number) or None."""
        nodes = cap.inlines
        for i, nd in enumerate(nodes):
            if not isinstance(nd, Text):
                continue
            k = _find_placeholder(nd, nodes, i)
            if k is None:
                continue
            label_nodes = nodes[:i] + (
                [Text(nd.s[:k], nd.start, nd.at_start)] if k > 0 else []
            )
            key = plain_text(label_nodes).rstrip(" \t\n")
            n = self.counters.get(key, 0) + 1
            self.counters[key] = n
            cap.number = n
            before = Text(nd.s[:k], nd.start, nd.at_start) if k > 0 else None
            after = Text(
                nd.s[k + 1 :], nd.start + k + 1 if nd.start >= 0 else -1, False
            )
            repl = (
                ([before] if before else [])
                + [CaptionNumber(str(n))]
                + ([after] if after.s else [])
            )
            cap.inlines = nodes[:i] + repl + nodes[i + 1 :]
            lbl = _trim_label(label_nodes)
            ha = getattr(host, "attrs", None)
            hid = ha.id() if ha is not None else None
            if hid is not None and hid not in self.caption_ids:
                self.caption_ids[hid] = (lbl, str(n))
            return lbl, n
        return None

    def _caption_hosts(self, blocks, out):
        for b in blocks:
            if isinstance(b, Div) and b.is_figure:
                out.append(("group", b))
                for c in b.children:
                    if _is_panel(c):
                        out.append(("panel", c, b))
                        if isinstance(c, BlockQuote):
                            self._caption_hosts(c.children, out)
                    else:
                        self._caption_hosts([c], out)
                continue
            cap = (
                getattr(b, "caption", None)
                if isinstance(b, (Paragraph, CodeBlock, BlockQuote, Table, Div))
                else None
            )
            if cap is not None and not (
                isinstance(b, Paragraph) and not (b.block_image or b.math_host)
            ):
                out.append(("host", b))
            if isinstance(b, (BlockQuote, Div, ListItem, DefDesc)):
                self._caption_hosts(b.children, out)
            elif isinstance(b, (ListBlock, DefList)):
                self._caption_hosts(b.items, out)

    # ---------------------------------------------------------------- abbreviations

    def apply_abbrs_blocks(self, blocks):
        for nodes in self.iter_inline_holders(blocks):
            self.apply_abbrs_inlines(nodes)

    def apply_abbrs_inlines(self, nodes):
        terms = sorted(self.abbrs.keys(), key=len, reverse=True)
        pat = re.compile("|".join(re.escape(t) for t in terms))
        self._abbr(nodes, pat)

    def _abbr(self, nodes, pat):
        k = 0
        while k < len(nodes):
            nd = nodes[k]
            t = type(nd)
            if t is Text:
                parts = self._abbr_text(nd, pat, nodes, k)
                if parts is not None:
                    nodes[k : k + 1] = parts
                    k += len(parts)
                    continue
            elif t in (Elem, Span, Link, Ext, Bracket):
                self._abbr(nd.children, pat)
            elif t is RefLink:
                if nd.resolved is not None and nd.children is not None:
                    self._abbr(nd.children, pat)
            elif t is Subst:
                self._abbr(nd.old, pat)
                self._abbr(nd.new, pat)
            k += 1

    def _abbr_text(self, nd, pat, siblings, k):
        s = nd.s
        res = []
        pos = 0
        for m in pat.finditer(s):
            a, b = m.start(), m.end()
            before = s[a - 1] if a > 0 else _edge_char(siblings, k, -1)
            after = s[b] if b < len(s) else _edge_char(siblings, k, 1)
            if (before is not None and is_alnum(before)) or (
                after is not None and is_alnum(after)
            ):
                continue
            if a > pos:
                res.append(Text(s[pos:a], -1))
            res.append(Abbr(m.group(0), self.abbrs[m.group(0)]))
            pos = b
        if not res:
            return None
        if pos < len(s):
            res.append(Text(s[pos:], -1))
        return res

    # ---------------------------------------------------------------- admonitions

    def mint_admonition_ids(self):
        used = self.used_ids
        divs = []
        for b in walk_blocks(self.doc.children):
            if isinstance(b, Div):
                divs.append(b)
        for num, kind, obj in self.notes:
            if kind == "def":
                for b in walk_blocks(obj.children):
                    if isinstance(b, Div):
                        divs.append(b)
        placed = None
        if self.notes:
            for b in self.doc.children:
                if isinstance(b, Div) and b.kind == "footnotes":
                    placed = b
                    break
        n = 0
        for d in divs:
            if (d.kind in CANON or d is placed) and d.title is not None:
                if d.attrs is not None and any(
                    e[0] in ("aria-label", "aria-labelledby") for e in d.attrs.entries
                ):
                    continue
                n += 1
                base = f"adm-{n}"
                cand = base
                k = 2
                while cand in used:
                    cand = f"{base}-{k}"
                    k += 1
                used.add(cand)
                d.adm_id = cand


def _is_panel(c):
    if isinstance(c, Table):
        return True
    if (
        isinstance(c, (Paragraph, CodeBlock, BlockQuote))
        and getattr(c, "caption", None) is not None
    ):
        if isinstance(c, Paragraph):
            return c.block_image or c.math_host
        return True
    return False


def _panel_letter(k):
    s = ""
    k += 1
    while k > 0:
        k, r = divmod(k - 1, 26)
        s = chr(97 + r) + s
    return s


def _literal_offsets(p):
    lb = p.literal_braces
    if not lb:
        return None
    out = set()
    off = 0
    for k, ln in enumerate(p.lines):
        if k in lb:
            out.add(off)
        off += len(ln) + 1
    return out


def _edge_char(siblings, k, direction):
    j = k + direction
    while 0 <= j < len(siblings):
        nd = siblings[j]
        if isinstance(nd, Comment):
            j += direction
            continue
        txt = plain_text([nd])
        if txt:
            return txt[0] if direction > 0 else txt[-1]
        return None
    return None


def _find_placeholder(nd, nodes, i):
    s = nd.s
    for k, ch in enumerate(s):
        if ch == "#":
            nx = s[k + 1] if k + 1 < len(s) else None
            if nx is None:
                if i + 1 < len(nodes) and not isinstance(
                    nodes[i + 1], (SoftBreak, HardBreak, NBSP)
                ):
                    # `#` directly before an element: not a tag start either
                    pass
                return k
            if nx in " \t\n:." or not (nx.isascii() and (nx.isalnum() or nx in "_-")):
                return k
    return None


def _trim_label(label_nodes):
    nodes = list(label_nodes)
    while nodes and isinstance(nodes[-1], Text) and nodes[-1].s.strip(" \t\n") == "":
        nodes.pop()
    if nodes and isinstance(nodes[-1], Text):
        last = nodes[-1]
        nodes[-1] = Text(last.s.rstrip(" \t\n"), last.start, last.at_start)
    return nodes


def _ends_gap(ln):
    # a trailing run of two or more columns is content in a line block
    k = len(ln)
    j = k
    while j > 0 and ln[j - 1] in " \t":
        j -= 1
    if j == k:
        return False
    # count columns of the trailing run from its start column
    col = 0
    for ch in ln[:j]:
        col = col + 4 - (col % 4) if ch == "\t" else col + 1
    start = col
    for ch in ln[j:]:
        col = col + 4 - (col % 4) if ch == "\t" else col + 1
    return col - start >= 2


def _verse_line(ln):
    """Leading whitespace -> NBSP per column; inner/trailing runs of two or
    more columns -> NBSPs; a lone inner space stays a space."""
    out = []
    col = 0
    i = 0
    n = len(ln)
    # leading run
    while i < n and ln[i] in " \t":
        nc = col + 4 - (col % 4) if ln[i] == "\t" else col + 1
        out.append("\u00a0" * (nc - col))
        col = nc
        i += 1
    while i < n:
        ch = ln[i]
        if ch in " \t":
            j = i
            c0 = col
            while j < n and ln[j] in " \t":
                col = col + 4 - (col % 4) if ln[j] == "\t" else col + 1
                j += 1
            w = col - c0
            if w >= 2:
                out.append("\u00a0" * w)
            else:
                if j >= n:
                    pass
                else:
                    out.append(" ")
            i = j
            continue
        out.append(ch)
        col += 1
        i += 1
    return "".join(out)


def _soft_to_hard(nodes, deep):
    out = []
    for nd in nodes:
        if isinstance(nd, SoftBreak):
            out.append(HardBreak(nd.start))
            continue
        if deep:
            ch = getattr(nd, "children", None)
            if ch is not None and not isinstance(nd, InlineNote):
                nd.children = _soft_to_hard(ch, deep)
            if isinstance(nd, InlineNote):
                nd.children = _soft_to_hard(nd.children, deep)
            if isinstance(nd, Subst):
                nd.old = _soft_to_hard(nd.old, deep)
                nd.new = _soft_to_hard(nd.new, deep)
        out.append(nd)
    return out


def parse_csv(content, sep):
    """RFC 4180 records; None when a field is malformed."""
    recs = []
    if content == "":
        return recs
    i = 0
    n = len(content)
    rec = []
    while True:
        # one field
        if i < n and content[i] == '"':
            i += 1
            buf = []
            while True:
                if i >= n:
                    return None
                c = content[i]
                if c == '"':
                    if i + 1 < n and content[i + 1] == '"':
                        buf.append('"')
                        i += 2
                        continue
                    i += 1
                    break
                buf.append(c)
                i += 1
            field = "".join(buf)
            if i < n and content[i] not in (sep, "\n"):
                return None
        else:
            j = i
            while j < n and content[j] not in (sep, "\n"):
                if content[j] == '"':
                    return None
                j += 1
            field = content[i:j]
            i = j
        rec.append(field)
        if i >= n:
            recs.append(rec)
            break
        if content[i] == sep:
            i += 1
            continue
        # newline
        recs.append(rec)
        rec = []
        i += 1
        if i >= n:
            break
    return recs
