"""Pipe tables (PART 9 §5 table model) and delimited CSV/TSV bodies."""

import re

from .attrs import items_to_attrs, parse_attr_block
from .chars import ASCII_PUNCT

_DELIM_CELL_RE = re.compile(r" *:?-+:? *$")
HALIGN = {"<": "left", ">": "right", "~": "center"}
VALIGN = {"^": "top", "~": "middle", "v": "bottom"}


class Cell:
    __slots__ = (
        "attrs",
        "col",
        "colspan",
        "content",
        "covered",
        "explicit_header",
        "halign",
        "header",
        "header_kind_span",
        "inlines",
        "origin",
        "parser",
        "row",
        "rowspan",
        "scope",
        "set_default",
        "span",
        "valign",
        "wraps",
    )

    def __init__(self):
        self.header = False
        self.content = ""
        self.attrs = None
        self.halign = None
        self.valign = None
        self.span = None  # None | '^' | '<'
        self.rowspan = 1
        self.colspan = 1
        self.row = 0
        self.col = 0
        self.origin = None
        self.header_kind_span = False
        self.wraps = []
        self.covered = False
        self.inlines = None
        self.parser = None
        self.scope = None
        self.explicit_header = False
        self.set_default = False


class Row:
    __slots__ = ("attrs", "cells", "delim")

    def __init__(self):
        self.cells = []
        self.attrs = None
        self.delim = False


def split_cells(body):
    """T1: split the interior of a row (between the first and last pipe).
    Returns a list of raw cell strings with `\\|` unescaped outside code
    spans."""
    cells = []
    cur = []
    i = 0
    n = len(body)
    while i < n:
        c = body[i]
        if c == "\\" and i + 1 < n and body[i + 1] in ASCII_PUNCT:
            if body[i + 1] == "|":
                cur.append("|")
            else:
                cur.append(body[i : i + 2])
            i += 2
            continue
        if c == "`":
            j = i
            while j < n and body[j] == "`":
                j += 1
            ln = j - i
            k = j
            found = -1
            while True:
                k = body.find("`", k)
                if k < 0:
                    break
                m = k
                while m < n and body[m] == "`":
                    m += 1
                if m - k == ln:
                    found = m
                    break
                k = m
            if found < 0:
                cur.append(body[i:])
                i = n
                break
            cur.append(body[i:found])
            i = found
            continue
        if c == "|":
            cells.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(c)
        i += 1
    cells.append("".join(cur))
    return cells


def _parse_alignment(s, i):
    """Glued alignment symbol run at s[i].  Returns (h, v, j) or None."""
    n = len(s)
    if i >= n:
        return None
    c = s[i]
    if c == "?":
        if i + 1 < n and s[i + 1] in VALIGN:
            return None, VALIGN[s[i + 1]], i + 2
        return None
    if c in HALIGN:
        h = HALIGN[c]
        if i + 1 < n and s[i + 1] in VALIGN:
            return h, VALIGN[s[i + 1]], i + 2
        return h, None, i + 1
    return None


def _cell_block(s, i):
    """A cell attribute block at s[i] == '{' (alignment symbols first).
    Returns (h, v, items, j, align_only) or None."""
    n = len(s)
    j = i + 1
    h = v = None
    al = _parse_alignment(s, j)
    if al is not None:
        h, v, k = al
        # the run must end at a space or `}`
        if k < n and s[k] == "}":
            return h, v, [], k + 1, True
        if k < n and s[k] == " ":
            k2 = k
            while k2 < n and s[k2] == " ":
                k2 += 1
            if k2 < n and s[k2] == "}":
                return h, v, [], k2 + 1, True
            r = parse_attr_block("{" + s[k2:], 0)
            if r is None:
                return None
            items, e = r
            if not items:
                return None
            return h, v, items, k2 + e - 1, False
        return None
    r = parse_attr_block(s, i)
    if r is None or not r[0]:
        return None
    return None, None, r[0], r[1], False


def parse_cell(raw):
    """Classify one raw cell (T3, T4, T10, T11, deprecated prefixes)."""
    c = Cell()
    s = raw
    n = len(s)
    i = 0
    header = False
    h = v = None
    items = None
    prefix = False
    if s.startswith("="):
        # header kind marker
        j = 1
        if j < n and s[j] == "{":
            cb = _cell_block(s, j)
            if cb is not None:
                h, v, items, j2, _ = cb
                if j2 < n and s[j2] == " ":
                    header = True
                    prefix = True
                    i = j2 + 1
        elif j < n and s[j] == " ":
            header = True
            prefix = True
            i = j + 1
        elif j < n and s[j] in "<>~?":
            al = _parse_alignment(s, j)
            if al is not None:
                k = al[2]
                if k < n and s[k] == "{":
                    r = parse_attr_block(s, k)
                    if r is not None and r[0]:
                        items = r[0]
                        k = r[1]
                if k < n and s[k] == " ":
                    header = True
                    prefix = True
                    h, v = al[0], al[1]
                    i = k + 1
    elif s.startswith("{"):
        cb = _cell_block(s, 0)
        if cb is not None:
            h2, v2, it2, j2, _ = cb
            if j2 < n and s[j2] == " ":
                h, v, items = h2, v2, it2
                prefix = True
                i = j2 + 1
    elif n and s[0] in "<>~?":
        al = _parse_alignment(s, 0)
        if al is not None:
            k = al[2]
            it = None
            if k < n and s[k] == "{":
                r = parse_attr_block(s, k)
                if r is not None and r[0]:
                    it = r[0]
                    k = r[1]
            if k < n and s[k] == " " and s[k:].strip(" ") != "":
                h, v = al[0], al[1]
                items = it
                prefix = True
                i = k + 1
    content = s[i:] if prefix else s
    content = content.strip(" ")
    c.header = header
    c.explicit_header = header
    c.halign = h
    c.valign = v
    if items:
        a = items_to_attrs(items)
        a.remove("colspan")
        a.remove("rowspan")
        c.attrs = a if a else None
    # span markers
    if content in ("^", "<") and not items and (prefix or s.strip(" ") in ("^", "<")):
        c.span = content
        c.header_kind_span = header
        c.content = ""
        return c
    c.content = content
    return c


def parse_table(lines, attrs):
    """Build the cell grid from raw row lines."""
    rows = []
    prev_line_kind = None
    for k, line in enumerate(lines):
        if line.startswith("+"):
            # continuation row
            if not rows or prev_line_kind == "delim":
                prev_line_kind = "cont-bad"
                continue
            body = line[1:-1] if line.endswith("|") else line[1:]
            parts = split_cells(body)
            row = rows[-1]
            for ci, part in enumerate(parts):
                frag = part.strip(" ")
                if ci < len(row.cells):
                    if frag:
                        cell = row.cells[ci]
                        cell.wraps.append(frag)
                else:
                    if frag:
                        while len(row.cells) < ci:
                            nc = Cell()
                            row.cells.append(nc)
                        nc = Cell()
                        nc.content = frag
                        others = [x for x in row.cells if x.span != "<"]
                        nc.header = bool(row.cells) and all(
                            x.header and x.span != "^" for x in others
                        )
                        row.cells.append(nc)
            prev_line_kind = "cont"
            continue
        from .blocks import split_row_attrs

        body, rattrs = split_row_attrs(line)
        inner = body[1:-1]
        parts = split_cells(inner)
        row = Row()
        if rattrs:
            row.attrs = items_to_attrs(rattrs)
        if (
            len(rows) == 1
            and prev_line_kind == "row"
            and all(_DELIM_CELL_RE.match(p) for p in parts)
        ):
            row.delim = True
            row.cells = []
            for p in parts:
                c = Cell()
                q = p.strip(" ")
                if q.startswith(":") and q.endswith(":") and len(q) > 1:
                    c.halign = "center"
                elif q.startswith(":"):
                    c.halign = "left"
                elif q.endswith(":"):
                    c.halign = "right"
                row.cells.append(c)
            rows.append(row)
            prev_line_kind = "delim"
            continue
        for p in parts:
            row.cells.append(parse_cell(p))
        rows.append(row)
        prev_line_kind = "row"
    return rows


def is_delim_row(line):
    from .blocks import split_row_attrs

    body, _ = split_row_attrs(line)
    if len(body) < 2 or body[0] != "|" or body[-1] != "|":
        return False
    parts = split_cells(body[1:-1])
    return all(_DELIM_CELL_RE.match(p) for p in parts)


class Grid:
    __slots__ = (
        "bodies",
        "explicit",
        "foot_count",
        "head_count",
        "ncols",
        "rows",
        "single_body",
        "widths",
    )

    def __init__(self):
        self.rows = []
        self.head_count = 0
        self.single_body = False
        self.ncols = 0
        self.foot_count = 0
        self.widths = None
        self.explicit = False
        self.bodies = None


def build_grid(rows, partition=None, col_h=None, col_v=None):
    """T5 span walk, T6 joins, T7 delimiter row, T9 head-row run and the
    alignment defaults.  Returns a Grid whose rows hold the cells to render.
    partition: explicit row groups (head, foot, bodies) or None, where bodies
    is None for one body between head and foot, else a list of
    (header_rows, data_rows, header_cols) per body (PART 12 §15)."""
    g = Grid()
    delim = None
    body_rows = []
    for k, row in enumerate(rows):
        if row.delim:
            delim = row
            continue
        body_rows.append(row)
    if delim is not None and body_rows:
        for c in body_rows[0].cells:
            c.header = True
            c.explicit_header = True
    owner = {}
    for r, row in enumerate(body_rows):
        cells = row.cells
        for c, cell in enumerate(cells):
            if (r, c) in owner:
                continue
            if cell.span == "<":
                o = owner.get((r, c - 1))
                if o is not None and o.row == r and not o.covered:
                    o.colspan += 1
                    owner[(r, c)] = o
                    cell.covered = True
                    cell.origin = o
                    continue
            elif cell.span == "^":
                o = owner.get((r - 1, c))
                if o is not None and o.col == c:
                    ok = True
                    for cc in range(c + 1, c + o.colspan):
                        if (r, cc) in owner:
                            ok = False
                            break
                        if cc < len(cells) and cells[cc].span is None:
                            ok = False
                            break
                    if ok:
                        o.rowspan += 1
                        for cc in range(c, c + o.colspan):
                            owner[(r, cc)] = o
                            if cc < len(cells):
                                cells[cc].covered = True
                                cells[cc].origin = o
                        continue
            cell.row = r
            cell.col = c
            owner[(r, c)] = cell
    # continuation fragments join the owning cell
    for r, row in enumerate(body_rows):
        for cell in row.cells:
            if cell.wraps:
                tgt = cell.origin if cell.covered and cell.origin is not None else cell
                for frag in cell.wraps:
                    tgt.content = (tgt.content + " " + frag) if tgt.content else frag
                cell.wraps = []
    # head-row run
    head = 0
    native_head = 0
    for r, row in enumerate(body_rows) if partition is None else []:
        owned = [c for c in row.cells if not c.covered]
        if not owned:
            break
        hdr = True
        for c in owned:
            if c.span is not None and not c.header_kind_span:
                continue
            if not c.header:
                hdr = False
                break
        if hdr and any(c.header for c in owned):
            head += 1
            for c in owned:
                if c.span is not None and not c.header_kind_span:
                    c.header = True
        else:
            break
    native_head = head
    col_rows = set(range(head))
    if partition is not None:
        ph, pf, bodies = partition
        head = ph
        g.foot_count = pf
        g.explicit = True
        col_rows = set(range(min(ph, len(body_rows))))
        if bodies is not None:
            # each body's leading header rows hold column headers, and its
            # leading row-header columns hold row headers in its data rows
            g.bodies = []
            r = ph
            for hk, dk, ck in bodies:
                g.bodies.append((r, r + hk + dk))
                col_rows.update(range(r, r + hk))
                for d in range(r + hk, r + hk + dk):
                    for c in body_rows[d].cells:
                        if ck and not c.covered and c.col < ck:
                            c.header = True
                r += hk + dk
        for r in col_rows:
            for c in body_rows[r].cells:
                c.header = True
        # the native head-row run still sets column defaults
        for r, row in enumerate(body_rows):
            owned = [c for c in row.cells if not c.covered]
            if owned and all(
                c.explicit_header or (c.span is not None and c.header_kind_span)
                for c in owned
                if not (c.span is not None and not c.header_kind_span)
            ):
                native_head = r + 1
            else:
                break
    g.head_count = head
    # orphan placeholders take their row's kind
    for r, row in enumerate(body_rows):
        owned = [c for c in row.cells if not c.covered]
        others = [c for c in owned if c.span is None]
        for c in owned:
            if (
                c.span is not None
                and not c.header_kind_span
                and (r in col_rows or (others and all(o.header for o in others)))
            ):
                c.header = True
    # column defaults
    ncols = max([len(r.cells) for r in body_rows] + [0])
    g.ncols = ncols
    defaults_h = {}
    defaults_v = {}
    if delim is not None:
        for c, dc in enumerate(delim.cells):
            if dc.halign:
                defaults_h[c] = dc.halign
    native_h = {}
    native_v = {}
    for r in range(native_head):
        for c, cell in enumerate(body_rows[r].cells):
            if cell.covered:
                continue
            if cell.explicit_header or cell.span is not None:
                if cell.halign:
                    native_h[c] = cell.halign
                if cell.valign:
                    native_v[c] = cell.valign
    defaults_h.update(native_h)
    defaults_v.update(native_v)
    if col_h:
        for c, v in enumerate(col_h):
            if v and c not in defaults_h:
                defaults_h[c] = v
    if col_v:
        for c, v in enumerate(col_v):
            if v and c not in defaults_v:
                defaults_v[c] = v
    # a rowspan crossing a section boundary keeps the rows in one body
    bounds = {head}
    if g.foot_count:
        bounds.add(len(body_rows) - g.foot_count)
    for st, _ in g.bodies or ():
        bounds.add(st)
    for r, row in enumerate(body_rows):
        for cell in row.cells:
            if cell.covered:
                continue
            if cell.rowspan > 1 and any(r < b < r + cell.rowspan for b in bounds):
                g.single_body = True
            cell.scope = None
            if cell.header:
                cell.scope = "col" if r in col_rows else "row"
            h = cell.halign or defaults_h.get(cell.col)
            v = cell.valign or defaults_v.get(cell.col)
            cell.halign = h
            cell.valign = v
    g.rows = body_rows
    return g
