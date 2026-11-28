"""HTML serialization (PART 10)."""

from .chars import strip_bidi
from .htmlattrs import Gen, class_value, esc_attr, esc_text, harden, render_attr_list
from .nodes import (
    NBSP,
    Abbr,
    Autolink,
    Bracket,
    CaptionNumber,
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
    Mention,
    NoteRef,
    RawInline,
    RefLink,
    Smart,
    SoftBreak,
    Span,
    Subst,
    Symbol,
    Text,
    Verbatim,
)

ELEM_TAG = {
    "em": "em",
    "strong": "strong",
    "u": "u",
    "s": "s",
    "mark": "mark",
    "sup": "sup",
    "sub": "sub",
    "ins": "ins",
    "del": "del",
}


def attr_pairs(
    authored=None,
    structural=(),
    base_class=None,
    base_lead=True,
    gen_class=None,
    generated=(),
    omit=(),
):
    """Order an element's attributes in the PART 10 §1 ranks.

    structural: R1 pairs; base_class: R2 class tokens (list); base_lead:
    True when the base class holds the R2 slot even with authored classes
    (admonitions, core divs), False when it is prepended inside the authored
    class slot (task lists, math); gen_class: R4 marker-derived class tokens
    appended after the authored ones; generated: R4 pairs, omitted when an
    authored attribute of the same name exists."""
    pairs = []
    struct_names = set()
    for n, v in structural:
        pairs.append((n, Gen(v)))
        struct_names.add(n.lower())
    entries = authored.entries if authored else []
    auth_names = {e[0] for e in entries}
    has_auth_class = "class" in auth_names
    class_done = False
    if base_class and (base_lead or not has_auth_class):
        cname = "class"
        auth = ()
        for e in entries:
            if e[0] == "class":
                cname = e[1]
                auth = e[2]
        pairs.append((cname, class_value(base_class, auth, gen_class or ())))
        class_done = True
    for e in entries:
        ln = e[0]
        if ln in struct_names or ln in omit:
            continue
        if ln == "class":
            if class_done:
                continue
            pairs.append((e[1], class_value(base_class or (), e[2], gen_class or ())))
            class_done = True
        else:
            pairs.append((e[1], e[2]))
    if gen_class and not class_done:
        pairs.append(("class", Gen(" ".join(gen_class))))
    for n, v in generated:
        if n.lower() not in auth_names:
            pairs.append((n, Gen(v)))
    return pairs


def align_style(pairs, decl):
    """Merge a `text-align` (etc.) declaration into an authored style."""
    for k, (n, v) in enumerate(pairs):
        if n.lower() == "style":
            v = harden(n, v) or ""
            v2 = v.strip()
            if v2:
                if not v2.endswith(";"):
                    v2 += ";"
                v2 += " " + decl
            else:
                v2 = decl
            pairs[k] = (n, Gen(v2))
            return pairs
    pairs.append(("style", Gen(decl)))
    return pairs


class InlineRenderer:
    """Renders inline nodes; `ctx` supplies document-level state."""

    def __init__(self, ctx):
        self.ctx = ctx

    def render(self, nodes, in_link=False):
        out = []
        for nd in nodes:
            out.append(self.node(nd, in_link))
        return "".join(out)

    def node(self, nd, in_link):
        t = type(nd)
        if t is Text:
            return esc_text(strip_bidi(nd.s))
        if t is Esc:
            return esc_text(nd.ch)
        if t is NBSP:
            return "&nbsp;"
        if t is SoftBreak:
            return "\n"
        if t is HardBreak:
            return "<br>\n"
        if t is Smart:
            return esc_text(nd.glyph)
        if t is Verbatim:
            return esc_text(strip_bidi(nd.s))
        if t is Elem:
            tag = ELEM_TAG[nd.kind]
            return f"<{tag}{self.attrs(nd.attrs)}>{self.render(nd.children, in_link)}</{tag}>"
        if t is Code:
            return (
                f"<code{self.attrs(nd.attrs)}>{esc_text(strip_bidi(nd.value))}</code>"
            )
        if t is Math:
            base = ["math", "display" if nd.display else "inline"]
            pairs = attr_pairs(
                nd.attrs, base_class=base, base_lead=False, generated=[("role", "math")]
            )
            if nd.display:
                body = "\\[" + esc_text(strip_bidi(nd.value)) + "\\]"
            else:
                body = "\\(" + esc_text(strip_bidi(nd.value)) + "\\)"
            return f"<span{render_attr_list(pairs)}>{body}</span>"
        if t is Literal:
            v = esc_text(strip_bidi(nd.value))
            if nd.attrs:
                return f"<span{self.attrs(nd.attrs)}>{v}</span>"
            return v
        if t is RawInline:
            if nd.fmt == "html":
                if self.ctx.safe:
                    return esc_text(nd.value)
                return nd.value
            return ""
        if t is Comment:
            return ""
        if t is CriticComment:
            return (
                f'<span class="critic-comment">{esc_text(strip_bidi(nd.value))}</span>'
            )
        if t is Autolink:
            if in_link:
                return esc_text(strip_bidi(nd.text))
            href = nd.href
            from .htmlattrs import scheme_denied

            if scheme_denied(href):
                href = ""
            pairs = attr_pairs(nd.attrs, structural=[("href", href)])
            return f"<a{self._plain_attrs(pairs, nd.href)}>{esc_text(strip_bidi(nd.text))}</a>"
        if t is Link:
            return self.link(nd.children, nd.dest, nd.title, nd.attrs, in_link)
        if t is Image:
            return self.image(nd.alt, nd.dest, nd.title, nd.attrs)
        if t is RefLink:
            return self.reflink(nd, in_link)
        if t is Span:
            return self.span(nd, in_link)
        if t is Bracket:
            return ("![" if nd.bang else "[") + self.render(nd.children, in_link) + "]"
        if t is Subst:
            return f"<del>{self.render(nd.old, in_link)}</del><ins>{self.render(nd.new, in_link)}</ins>"
        if t is Ext:
            pairs = attr_pairs(nd.attrs, base_class=["ext-" + nd.name], base_lead=True)
            return f"<span{render_attr_list(pairs)}>{self.render(nd.children, in_link)}</span>"
        if t is Mention:
            cls = "mention" if nd.sigil == "@" else "tag"
            return f'<span class="{cls}"><strong>{esc_text(nd.sigil + nd.name)}</strong></span>'
        if t is Symbol:
            txt = esc_text(":" + nd.name + ":")
            if nd.attrs:
                return f"<span{self.attrs(nd.attrs)}>{txt}</span>"
            return txt
        if t is Abbr:
            return f'<abbr title="{esc_attr(nd.title)}">{esc_text(nd.term)}</abbr>'
        if t is CaptionNumber:
            return esc_text(nd.value)
        if t is Crossref:
            return self.ctx.crossref(nd, in_link, self)
        if t is NoteRef or t is InlineNote:
            return self.ctx.noteref(nd, in_link, self)
        return ""

    def _plain_attrs(self, pairs, raw_href):
        return render_attr_list(pairs)

    def attrs(self, attrs):
        if not attrs:
            return ""
        return render_attr_list(attr_pairs(attrs))

    def link(self, children, dest, title, attrs, in_link):
        if in_link:
            return self.render(children, True)
        from .htmlattrs import scheme_denied

        href = "" if scheme_denied(dest) else dest
        st = [("href", href)]
        if title is not None:
            st.append(("title", strip_bidi(title)))
        pairs = attr_pairs(attrs, structural=st)
        return f"<a{render_attr_list(pairs)}>{self.render(children, True)}</a>"

    def image(self, alt, dest, title, attrs):
        from .htmlattrs import scheme_denied

        src = "" if scheme_denied(dest) else dest
        st = [("src", src), ("alt", strip_bidi(alt))]
        if title is not None:
            st.append(("title", strip_bidi(title)))
        pairs = attr_pairs(attrs, structural=st)
        return f"<img{render_attr_list(pairs)}>"

    def reflink(self, nd, in_link):
        if nd.resolved is None:
            return esc_text(strip_bidi(nd.src))
        dest, title, def_attrs = nd.resolved
        attrs = None
        if def_attrs is not None or nd.attrs is not None:
            from .attrs import Attrs

            attrs = Attrs()
            if def_attrs is not None:
                attrs.merge(def_attrs)
            if nd.attrs is not None:
                attrs.merge(nd.attrs)
        if nd.image:
            return self.image(nd.alt, dest, title, attrs)
        return self.link(nd.children, dest, title, attrs, in_link)

    def span(self, nd, in_link):
        attrs = nd.attrs
        if attrs is not None and attrs.has("abbr"):
            # an explicit abbr is authoritative: no nested <abbr>
            inner = self.render(_abbr_as_text(nd.children), in_link)
        else:
            inner = self.render(nd.children, in_link)
        if attrs is None:
            return f"<span>{inner}</span>"
        sem = [e for e in attrs.entries if e[0] in ("abbr", "time", "kbd")]
        if not sem:
            return f"<span{self.attrs(attrs)}>{inner}</span>"
        names = {e[0] for e in sem}
        vals = {e[0]: e[2] for e in sem}
        rest = [e for e in attrs.entries if e[0] not in ("abbr", "time", "kbd")]
        from .attrs import Attrs

        leftover = Attrs()
        leftover.entries = rest
        order = [n for n in ("abbr", "time", "kbd") if n in names]
        cur = inner
        for k, name in enumerate(order):
            outer = k == len(order) - 1
            derived = []
            if name == "abbr" and vals["abbr"] != "":
                derived = [("title", vals["abbr"])]
            elif name == "time" and vals["time"] != "":
                derived = [("datetime", vals["time"])]
            if outer:
                pairs = []
                auth_names = {e[0] for e in rest}
                for dn, dv in derived:
                    if dn not in auth_names:
                        pairs.append((dn, dv))
                pairs.extend(attr_pairs(leftover))
                cur = f"<{name}{render_attr_list(pairs)}>{cur}</{name}>"
            else:
                cur = f"<{name}{render_attr_list(derived)}>{cur}</{name}>"
        return cur


# ====================================================================== blocks

from .nodes import (
    BlockQuote,
    CodeBlock,
    DefList,
    DefTerm,
    Div,
    Heading,
    ListBlock,
    Paragraph,
    RawBlock,
    Table,
    ThematicBreak,
)
from .resolve import CANON, plain_text

ADM_LABEL = {
    "note": "Note",
    "tip": "Tip",
    "warning": "Warning",
    "danger": "Danger",
    "info": "Info",
    "success": "Success",
    "example": "Example",
    "quote": "Quote",
}


def _align_pairs(pairs):
    """Text-block alignment: an authored `align` of left/right/center becomes
    `style="text-align: VALUE;"` at the align slot (or merged into style)."""
    idx = None
    for k, (n, v) in enumerate(pairs):
        if n.lower() == "align" and v.strip().lower() in ("left", "right", "center"):
            idx = k
    if idx is None:
        return pairs
    val = pairs[idx][1].strip().lower()
    decl = f"text-align: {val};"
    sidx = None
    for k, (n, v) in enumerate(pairs):
        if n.lower() == "style":
            sidx = k
    out = list(pairs)
    if sidx is None:
        out[idx] = ("style", Gen(decl))
        return out
    sv = harden(out[sidx][0], out[sidx][1])
    if sv is None:
        sv = ""
    sv = sv.strip()
    if sv:
        if not sv.endswith(";"):
            sv += ";"
        sv = sv + " " + decl
    else:
        sv = decl
    out[sidx] = (out[sidx][0], Gen(sv))
    del out[idx]
    return out


class Renderer:
    def __init__(self, resolver, safe=False):
        self.res = resolver
        self.safe = safe
        self.inl = InlineRenderer(self)
        self.panel_mode = False
        self.placement = None
        if resolver.notes:
            for b in resolver.doc.children:
                if isinstance(b, Div) and b.kind == "footnotes":
                    self.placement = b
                    break

    # ------------------------------------------------------------ inline ctx

    def crossref(self, nd, in_link, r):
        res = self.res
        h = res.heading_ids.get(nd.target)
        if h is not None:
            inner = r.render(_clone_for_xref(h.inlines, res), True)
            if in_link:
                return inner
            return f'<a href="#{esc_attr(nd.target)}">{inner}</a>'
        c = res.caption_ids.get(nd.target)
        if c is not None:
            label, num = c
            lbl = r.render(_clone_for_xref(label, res), True)
            text = (lbl + " " + str(num)) if lbl else str(num)
            if in_link:
                return text
            return f'<a href="#{esc_attr(nd.target)}">{text}</a>'
        return esc_text(strip_bidi(nd.src))

    def noteref(self, nd, in_link, r):
        if isinstance(nd, NoteRef) and not nd.resolved:
            return esc_text(strip_bidi(nd.src))
        n = nd.number
        if n is None:
            return ""
        rid = nd.ref_id
        a = nd.attrs
        rest = []
        if a is not None:
            rest = [
                (e[1], class_value((), e[2]) if e[0] == "class" else e[2])
                for e in a.entries
                if e[0] != "id"
            ]
        if in_link:
            return f"<sup{render_attr_list([('id', Gen(rid))] + rest)}>{n}</sup>"
        pairs = [
            ("id", Gen(rid)),
            ("href", Gen(f"#fn{n}")),
            ("role", Gen("doc-noteref")),
        ]
        pairs += [(k, v) for k, v in rest if k.lower() not in ("href", "role")]
        return f"<a{render_attr_list(pairs)}><sup>{n}</sup></a>"

    # ------------------------------------------------------------ document

    def render(self):
        doc = self.res.doc
        out = self.render_top(doc.children)
        if self.placement is None:
            en = self.render_endnotes("")
            if en:
                out.append(en)
        return "\n".join(out)

    def render_top(self, blocks):
        out = []
        stack = []  # (level, list)
        cur = out
        for b in blocks:
            if isinstance(b, Heading):
                while stack and stack[-1][0] >= b.level:
                    _, lst, parent, ind = stack.pop()
                    parent.append(self._close_section(lst, ind))
                    cur = stack[-1][1] if stack else out
                ind = "  " * len(stack)
                sec = []
                stack.append((b.level, sec, cur, ind))
                sec_attrs = [("id", Gen(b.id))]
                pairs = self.heading_pairs(b, top=True)
                sec.append(f"{ind}<section{render_attr_list(sec_attrs)}>")
                sec.append(
                    f"{ind}  <h{b.level}{render_attr_list(pairs)}>{self.inl.render(b.inlines)}</h{b.level}>"
                )
                cur = sec
                continue
            ind = "  " * len(stack)
            s = self.block(b, ind)
            if s is not None:
                cur.append(s)
        while stack:
            _, lst, parent, ind = stack.pop()
            parent.append(self._close_section(lst, ind))
        return out

    def _close_section(self, lst, ind):
        return "\n".join(lst) + "\n" + ind + "</section>"

    def heading_pairs(self, h, top):
        a = h.attrs
        if top:
            pairs = attr_pairs(a, omit=("id",))
        else:
            if a is not None and a.id() is not None:
                pairs = attr_pairs(a)
            else:
                pairs = attr_pairs(a, generated=[("id", h.id)])
        return _align_pairs(pairs)

    def blocks(self, blocks, ind):
        out = []
        for b in blocks:
            s = self.block(b, ind)
            if s is not None:
                out.append(s)
        return out

    def container(self, open_tag, close_tag, children, ind):
        body = self.blocks(children, ind + "  ")
        if not body:
            return f"{ind}{open_tag}\n\n{ind}{close_tag}"
        return "{}{}\n{}\n{}{}".format(ind, open_tag, "\n".join(body), ind, close_tag)

    # ------------------------------------------------------------ dispatch

    def block(self, b, ind):
        t = type(b)
        if t is Paragraph:
            return self.paragraph(b, ind)
        if t is Heading:
            pairs = self.heading_pairs(b, top=False)
            return f"{ind}<h{b.level}{render_attr_list(pairs)}>{self.inl.render(b.inlines)}</h{b.level}>"
        if t is ThematicBreak:
            return f"{ind}<hr{render_attr_list(attr_pairs(b.attrs))}>"
        if t is CodeBlock:
            return self.code(b, ind)
        if t is RawBlock:
            return self.raw(b, ind)
        if t is BlockQuote:
            return self.quote(b, ind)
        if t is ListBlock:
            return self.list(b, ind)
        if t is DefList:
            return self.deflist(b, ind)
        if t is Table:
            return self.table(b, ind)
        if t is Div:
            return self.div(b, ind)
        return None

    # ------------------------------------------------------------ leaves

    def para_inner(self, p):
        return self.inl.render(p.inlines)

    def para_renders_nothing(self, p):
        if not p.inlines:
            return True
        return all(isinstance(n, Comment) for n in p.inlines)

    def paragraph(self, p, ind, tight=False):
        if self.para_renders_nothing(p) and not p.line_block:
            return None
        if p.block_image:
            img = None
            for n in p.inlines:
                if not isinstance(n, Comment):
                    img = n
            if p.caption is not None:
                inner = self.image_html(img, None)
                return self.figure(p.attrs, ind, ind + "  " + inner, p.caption)
            return ind + self.image_html(img, p.attrs)
        if p.caption is not None and p.math_host:
            inner = ind + f"  <p>{self.para_inner(p)}</p>"
            return self.figure(p.attrs, ind, inner, p.caption)
        pairs = _align_pairs(attr_pairs(p.attrs))
        if tight and not p.attrs:
            return ind + self.para_inner(p)
        return f"{ind}<p{render_attr_list(pairs)}>{self.para_inner(p)}</p>"

    def image_html(self, img, extra_attrs):
        if isinstance(img, Image):
            attrs = img.attrs
            if extra_attrs is not None:
                from .attrs import Attrs

                a = Attrs()
                a.merge(extra_attrs)
                if attrs is not None:
                    a.merge(attrs)
                attrs = a
            return self.inl.image(img.alt, img.dest, img.title, attrs)
        dest, title, def_attrs = img.resolved
        from .attrs import Attrs

        a = Attrs()
        if extra_attrs is not None:
            a.merge(extra_attrs)
        if def_attrs is not None:
            a.merge(def_attrs)
        if img.attrs is not None:
            a.merge(img.attrs)
        return self.inl.image(img.alt, dest, title, a if a else None)

    def figure(self, attrs, ind, inner, caption):
        cap = self.caption_html(caption)
        if self.panel_mode:
            self.panel_mode = False
            pairs = attr_pairs(attrs, base_class=["carve-figure-panel"], base_lead=True)
        else:
            pairs = attr_pairs(attrs)
        return f"{ind}<figure{render_attr_list(pairs)}>\n{inner}\n{ind}  <figcaption>{cap}</figcaption>\n{ind}</figure>"

    def caption_html(self, cap):
        return self.inl.render(cap.inlines)

    def code(self, b, ind, attrs_on_pre=True):
        content = "\n".join(b.lines)
        if b.lines and (b.closed or b.final_nl):
            content += "\n"
        cls = ""
        if b.lang:
            cls = f' class="language-{esc_attr(b.lang)}"'
        if b.caption is not None:
            pre = f"<pre{self.pre_attrs(b, None)}><code{cls}>{esc_text(strip_bidi(content))}</code></pre>"
            return self.figure(b.attrs, ind, ind + "  " + pre, b.caption)
        pre = f"<pre{self.pre_attrs(b, b.attrs)}><code{cls}>{esc_text(strip_bidi(content))}</code></pre>"
        return ind + pre

    def pre_attrs(self, b, attrs):
        pairs = attr_pairs(attrs)
        if b.title is not None and not any(n.lower() == "title" for n, _ in pairs):
            pairs.append(("title", b.title))
        return render_attr_list(pairs)

    def raw(self, b, ind):
        if b.fmt != "html":
            return None
        content = "\n".join(b.lines)
        if b.lines and (b.closed or b.final_nl):
            content += "\n"
        if self.safe:
            return f'{ind}<pre><code class="language-html">{esc_text(content)}</code></pre>'
        if content and content.strip("\n") != "":
            content = content.removesuffix("\n")
        elif not content:
            return ind
        else:
            # an all-blank payload keeps its newlines
            pass
        return ind + content

    # ------------------------------------------------------------ containers

    def visible_children(self, children, ind):
        out = []
        for c in children:
            s = self.block(c, ind)
            if s is not None:
                out.append((c, s))
        return out

    def quote(self, b, ind):
        pairs = attr_pairs(b.attrs) if b.caption is None else []
        vis = self.visible_children(b.children, ind + "  ")
        if (
            len(vis) == 1
            and isinstance(vis[0][0], Paragraph)
            and vis[0][0].caption is None
            and not vis[0][0].block_image
        ):
            p = vis[0][0]
            s = "<blockquote{}>{}</blockquote>".format(
                render_attr_list(pairs), self.paragraph(p, "")
            )
            if b.caption is not None:
                return self.figure(b.attrs, ind, ind + "  " + s, b.caption)
            return ind + s
        if b.caption is not None:
            body = self.visible_children(b.children, ind + "    ")
            inner = self._wrap(
                ind + "  ", "<blockquote>", "</blockquote>", [s for _, s in body]
            )
            return self.figure(b.attrs, ind, inner, b.caption)
        return self._wrap(
            ind,
            f"<blockquote{render_attr_list(pairs)}>",
            "</blockquote>",
            [s for _, s in vis],
        )

    def _wrap(self, ind, open_tag, close_tag, parts):
        if not parts:
            return f"{ind}{open_tag}\n\n{ind}{close_tag}"
        return "{}{}\n{}\n{}{}".format(ind, open_tag, "\n".join(parts), ind, close_tag)

    def list(self, b, ind):
        tight = not (b.loose or b.force_loose)
        if b.ordered:
            st = []
            d = b.dialect
            start = b.first_value
            fm = b.first_marker
            if fm is not None and fm.ambiguous:
                if not b.decided:
                    up = fm.text.isupper()
                    if fm.text in ("i", "I"):
                        d = "ROMAN" if up else "roman"
                    else:
                        d = "ALPHA" if up else "alpha"
                if d in ("roman", "ROMAN"):
                    from .blocks import roman_value

                    start = roman_value(fm.text)
                else:
                    start = ord(fm.text.lower()) - 96
            if d in ("alpha", "ALPHA", "roman", "ROMAN"):
                st.append(
                    (
                        "type",
                        {"alpha": "a", "ALPHA": "A", "roman": "i", "ROMAN": "I"}[d],
                    )
                )
            if start is not None and start != 1:
                st.append(("start", str(start)))
            if b.delim == ")":
                st.append(("data-delim", ")"))
            pairs = attr_pairs(b.attrs, structural=st)
            open_tag = f"<ol{render_attr_list(pairs)}>"
            close_tag = "</ol>"
        else:
            if b.task:
                pairs = attr_pairs(b.attrs, base_class=["task-list"], base_lead=False)
            else:
                pairs = attr_pairs(b.attrs)
            open_tag = f"<ul{render_attr_list(pairs)}>"
            close_tag = "</ul>"
        items = [self.item(it, ind + "  ", tight, b.task) for it in b.items]
        return "{}{}\n{}\n{}{}".format(ind, open_tag, "\n".join(items), ind, close_tag)

    def item(self, it, ind, tight, task):
        st = []
        box = ""
        if it.task_state is not None:
            s = it.task_state
            if s in "xX":
                st.append(("data-task-state", "x"))
            elif s != " ":
                st.append(("data-task-state", s))
        pairs = attr_pairs(it.attrs, structural=st)
        open_tag = f"{ind}<li{render_attr_list(pairs)}>"
        vis = self.visible_children(it.children, ind + "  ")
        if it.task_state is not None:
            checked = it.task_state in "xX"
            name = None
            if vis and isinstance(vis[0][0], Paragraph) and not vis[0][0].block_image:
                name = _collapse_ws(plain_text(vis[0][0].inlines))
            bp = [("type", "checkbox")]
            if checked:
                bp.append(("checked", None))
            bp.append(("disabled", None))
            if name:
                bp.append(("aria-label", name))
            box = (
                "<input"
                + "".join(
                    f" {n}" if v is None else f' {n}="{esc_attr(v)}"' for n, v in bp
                )
                + ">"
            )
        return self._item_body(open_tag, box, vis, ind, tight, "</li>")

    def _item_body(self, open_tag, box, vis, ind, tight, close):
        if not vis:
            return open_tag + (box + " " if box else "") + close
        first = vis[0][0]
        lead = open_tag + (box + " " if box else "")
        if (
            isinstance(first, Paragraph)
            and not first.block_image
            and first.caption is None
        ):
            fhtml = self.paragraph(first, "", tight=tight)
            if len(vis) == 1:
                return lead + fhtml + close
            rest = []
            for c, s in vis[1:]:
                if isinstance(c, Paragraph):
                    rest.append(self.paragraph(c, ind + "  ", tight=tight))
                else:
                    rest.append(s)
            return lead + fhtml + "\n" + "\n".join(rest) + "\n" + ind + close
        parts = []
        for c, s in vis:
            if isinstance(c, Paragraph):
                parts.append(self.paragraph(c, ind + "  ", tight=tight))
            else:
                parts.append(s)
        return lead + "\n" + "\n".join(parts) + "\n" + ind + close

    def deflist(self, b, ind):
        pairs = attr_pairs(b.attrs)
        out = []
        for it in b.items:
            if isinstance(it, DefTerm):
                out.append(
                    f"{ind}  <dt{render_attr_list(attr_pairs(it.attrs))}>{self.inl.render(it.inlines)}</dt>"
                )
            else:
                vis = self.visible_children(it.children, ind + "    ")
                tight = not b.loose and len(vis) < 2
                open_tag = f"{ind}  <dd{render_attr_list(attr_pairs(it.attrs))}>"
                if (
                    len(vis) == 1
                    and isinstance(vis[0][0], Paragraph)
                    and not vis[0][0].block_image
                    and vis[0][0].caption is None
                ):
                    out.append(
                        open_tag + self.paragraph(vis[0][0], "", tight=tight) + "</dd>"
                    )
                elif not vis:
                    out.append(open_tag + "</dd>")
                else:
                    parts = []
                    for c, sv in vis:
                        if isinstance(c, Paragraph):
                            parts.append(self.paragraph(c, ind + "    ", tight=tight))
                        else:
                            parts.append(sv)
                    out.append(
                        open_tag + "\n" + "\n".join(parts) + "\n" + ind + "  </dd>"
                    )
        if not out:
            return f"{ind}<dl{render_attr_list(pairs)}>\n\n{ind}</dl>"
        return "{}<dl{}>\n{}\n{}</dl>".format(
            ind, render_attr_list(pairs), "\n".join(out), ind
        )

    def div(self, d, ind):
        if d is self.placement:
            parts = self.blocks(d.children, ind)
            parts.append(self.render_endnotes(ind, d))
            return "\n".join(parts)
        kind = d.kind
        a = d.attrs
        head = []
        if d.title is not None:
            if d.adm_id is not None:
                head.append(
                    f'<p class="admonition-title" id="{esc_attr(d.adm_id)}">{self.inl.render(d.title_inlines)}</p>'
                )
            else:
                head.append(
                    f'<p class="admonition-title">{self.inl.render(d.title_inlines)}</p>'
                )
        if d.label is not None:
            head.append(f'<p class="div-label">{self.inl.render(d.label_inlines)}</p>')
        if d.is_figure:
            return self.figure_group(d, ind)
        if kind in CANON:
            gen = []
            if not (
                a is not None
                and any(e[0] in ("aria-label", "aria-labelledby") for e in a.entries)
            ):
                if d.adm_id is not None:
                    gen = [("aria-labelledby", d.adm_id)]
                elif d.title is None:
                    gen = [("aria-label", ADM_LABEL[kind])]
            pairs = attr_pairs(
                a, base_class=["admonition", kind], base_lead=True, generated=gen
            )
            open_tag = f"<aside{render_attr_list(pairs)}>"
            close_tag = "</aside>"
        elif kind == "|":
            pairs = _align_pairs(attr_pairs(a, gen_class=["line-block"]))
            open_tag = f"<div{render_attr_list(pairs)}>"
            close_tag = "</div>"
        elif kind == "\\":
            pairs = _align_pairs(attr_pairs(a, gen_class=["hardbreaks"]))
            open_tag = f"<div{render_attr_list(pairs)}>"
            close_tag = "</div>"
        elif kind is None:
            pairs = _align_pairs(attr_pairs(a))
            open_tag = f"<div{render_attr_list(pairs)}>"
            close_tag = "</div>"
        else:
            pairs = _align_pairs(attr_pairs(a, base_class=[kind], base_lead=True))
            open_tag = f"<div{render_attr_list(pairs)}>"
            close_tag = "</div>"
        parts = [ind + "  " + h for h in head]
        for c in d.children:
            s = self.block(c, ind + "  ")
            if s is not None:
                parts.append(s)
        return self._wrap(ind, open_tag, close_tag, parts)

    def figure_group(self, d, ind):
        pairs = attr_pairs(d.attrs, base_class=["carve-figure-group"], base_lead=True)
        parts = []
        for c in d.children:
            if is_panel(c):
                s = self.panel(c, ind + "  ")
            else:
                s = self.block(c, ind + "  ")
            if s is not None:
                parts.append(s)
        if d.caption is not None:
            parts.append(
                f"{ind}  <figcaption>{self.caption_html(d.caption)}</figcaption>"
            )
        return self._wrap(ind, f"<figure{render_attr_list(pairs)}>", "</figure>", parts)

    def panel(self, c, ind):
        if isinstance(c, Table):
            return '{}<figure class="carve-figure-panel">\n{}\n{}</figure>'.format(
                ind, self.table(c, ind + "  "), ind
            )
        self.panel_mode = True
        try:
            return self.block(c, ind)
        finally:
            self.panel_mode = False

    # ------------------------------------------------------------ tables

    def table(self, tb, ind):
        g = tb.grid
        pairs = attr_pairs(tb.attrs)
        lines = [f"{ind}<table{render_attr_list(pairs)}>"]
        if tb.caption is not None:
            lines.append(f"{ind}  <caption>{self.caption_html(tb.caption)}</caption>")
        if g.widths:
            lines.append(f"{ind}  <colgroup>")
            for w in g.widths:
                if w is None:
                    lines.append(f"{ind}    <col>")
                else:
                    lines.append(f'{ind}    <col style="width: {_fmt_width(w)}%;">')
            lines.append(f"{ind}  </colgroup>")
        rows = g.rows
        head = g.head_count
        foot = g.foot_count
        if g.single_body:
            groups = [("tbody", rows)] if rows else []
        elif g.explicit:
            groups = []
            if head:
                groups.append(("thead", rows[:head]))
            if g.bodies is not None:
                # every stated body renders, an empty one included
                groups.extend(("tbody", rows[st:en]) for st, en in g.bodies)
            else:
                mid = rows[head : len(rows) - foot] if foot else rows[head:]
                if mid:
                    groups.append(("tbody", mid))
            if foot:
                groups.append(("tfoot", rows[len(rows) - foot :]))
        elif head == 0:
            groups = [("tbody", rows)] if rows else []
        else:
            groups = [("thead", rows[:head])]
            if rows[head:]:
                groups.append(("tbody", rows[head:]))
        for tag, rs in groups:
            lines.append(f"{ind}  <{tag}>")
            for row in rs:
                lines.append(
                    "{}    <tr{}>{}</tr>".format(
                        ind,
                        render_attr_list(attr_pairs(row.attrs)),
                        "".join(self.cell(c) for c in row.cells if not c.covered),
                    )
                )
            lines.append(f"{ind}  </{tag}>")
        lines.append(f"{ind}</table>")
        return "\n".join(lines)

    def cell(self, c):
        tag = "th" if c.header else "td"
        st = []
        if c.header and c.scope:
            st.append(("scope", c.scope))
        if c.rowspan > 1:
            st.append(("rowspan", str(c.rowspan)))
        if c.colspan > 1:
            st.append(("colspan", str(c.colspan)))
        a = c.attrs
        auth = attr_pairs(a)
        auth_names = {n.lower() for n, v in auth}
        pairs = []
        for n, v in st:
            if n.lower() not in auth_names:
                pairs.append((n, v))
        pairs.extend(auth)
        decl = []
        if c.halign:
            decl.append(f"text-align: {c.halign};")
        if c.valign:
            decl.append(f"vertical-align: {c.valign};")
        if decl:
            pairs = align_style(pairs, " ".join(decl))
        inner = self.inl.render(c.inlines) if c.inlines is not None else ""
        return f"<{tag}{render_attr_list(pairs)}>{inner}</{tag}>"

    # ------------------------------------------------------------ endnotes

    def render_endnotes(self, ind, marker=None):
        res = self.res
        if not res.notes:
            return ""
        head = []
        name = ' aria-label="Footnotes"'
        if marker is not None:
            if marker.title is not None:
                if marker.adm_id is not None:
                    name = f' aria-labelledby="{esc_attr(marker.adm_id)}"'
                    head.append(
                        f'{ind}  <p class="admonition-title" id="{esc_attr(marker.adm_id)}">{self.inl.render(marker.title_inlines)}</p>'
                    )
                else:
                    head.append(
                        f'{ind}  <p class="admonition-title">{self.inl.render(marker.title_inlines)}</p>'
                    )
            if marker.label is not None:
                head.append(
                    f'{ind}  <p class="div-label">{self.inl.render(marker.label_inlines)}</p>'
                )
        lines = (
            [f'{ind}<section role="doc-endnotes"{name}>']
            + head
            + [f"{ind}  <hr>", f"{ind}  <ol>"]
        )
        for num, kind, obj in res.notes:
            refs = res.note_refs.get(num, [])
            backs = []
            # CARVE-P9-026: a lone backlink is named by the label alone; the
            # k-th of several, the first included, shows and names its ordinal.
            for k, rid in enumerate(refs, 1):
                if len(refs) == 1:
                    backs.append(
                        f'<a href="#{esc_attr(rid)}" role="doc-backlink" aria-label="Back to reference">↩</a>'
                    )
                else:
                    backs.append(
                        f'<a href="#{esc_attr(rid)}" role="doc-backlink" '
                        f'aria-label="Back to reference {k}">↩<sup>{k}</sup></a>'
                    )
            back = " ".join(backs)
            li_ind = ind + "    "
            if kind == "inline":
                body = [f"{li_ind}  <p>{self.inl.render(obj.children)}{back}</p>"]
            else:
                vis = self.visible_children(obj.children, li_ind + "  ")
                body = []
                if (
                    vis
                    and isinstance(vis[-1][0], Paragraph)
                    and not vis[-1][0].block_image
                    and vis[-1][0].caption is None
                ):
                    for c, s in vis[:-1]:
                        body.append(s)
                    lastp = vis[-1][0]
                    pairs = _align_pairs(attr_pairs(lastp.attrs))
                    body.append(
                        f"{li_ind}  <p{render_attr_list(pairs)}>{self.para_inner(lastp)}{back}</p>"
                    )
                else:
                    for c, s in vis:
                        body.append(s)
                    body.append(f"{li_ind}  <p>{back}</p>")
            lines.append(f'{li_ind}<li id="fn{num}">')
            lines.extend(body)
            lines.append(f"{li_ind}</li>")
        lines.append(f"{ind}  </ol>")
        lines.append(f"{ind}</section>")
        return "\n".join(lines)


def _abbr_as_text(nodes):
    out = []
    for nd in nodes:
        if isinstance(nd, Abbr):
            out.append(Text(nd.term, -1))
        else:
            out.append(nd)
    return out


def _fmt_width(w):
    try:
        f = float(w)
    except ValueError:
        return w
    if f == int(f):
        return str(int(f))
    return (f"{f:f}").rstrip("0").rstrip(".")


def is_panel(c):
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


def _collapse_ws(s):
    import re

    return re.sub(r"[ \t\n\r\x0c]+", " ", s).strip(" ")


def _clone_for_xref(nodes, res=None, depth=0):
    """Heading clone for a cross-reference: ids dropped, note refs omitted,
    abbreviations as plain text; an inner cross-reference contributes its
    target's inline text without a link, one level deep."""
    import copy

    out = []
    for nd in nodes:
        t = type(nd)
        if t in (NoteRef, InlineNote):
            continue
        if t is Crossref:
            tgt = (
                res.heading_ids.get(nd.target)
                if res is not None and depth == 0
                else None
            )
            if tgt is not None:
                out.extend(_clone_for_xref(tgt.inlines, res, depth + 1))
            elif res is not None and depth == 0 and nd.target in res.caption_ids:
                label, num = res.caption_ids[nd.target]
                out.extend(_clone_for_xref(label, res, depth + 1))
                out.append(Text((" " if label else "") + str(num), -1))
            else:
                out.append(Text(nd.src, -1))
            continue
        if t is Abbr:
            out.append(Text(nd.term, -1))
            continue
        a = getattr(nd, "attrs", None)
        if a is not None and a.id() is not None:
            nd2 = copy.copy(nd)
            a2 = a.copy()
            a2.remove("id")
            nd2.attrs = a2 if a2 else None
            nd = nd2
        ch = getattr(nd, "children", None)
        if ch:
            nd2 = copy.copy(nd)
            nd2.children = _clone_for_xref(ch, res, depth)
            nd = nd2
        out.append(nd)
    return out
