"""Block and inline node classes.

Inline nodes carry `start` source offsets (into the inline source string of
their block) where boundary tests need them.
"""


class Node:
    __slots__ = ()
    is_inline = False


# ---------------------------------------------------------------- inline


class Text(Node):
    __slots__ = ("at_start", "s", "start")
    is_inline = True

    def __init__(self, s, start=-1, at_start=False):
        self.s = s
        self.start = start
        self.at_start = at_start

    def __repr__(self):
        return f"Text({self.s!r})"


class Esc(Node):
    """An escaped ASCII punctuation character (escaped_text)."""

    __slots__ = ("ch", "start")
    is_inline = True

    def __init__(self, ch, start=-1):
        self.ch = ch
        self.start = start

    def __repr__(self):
        return f"Esc({self.ch!r})"


class NBSP(Node):
    __slots__ = ("start",)
    is_inline = True

    def __init__(self, start=-1):
        self.start = start


class SoftBreak(Node):
    __slots__ = ("start",)
    is_inline = True

    def __init__(self, start=-1):
        self.start = start

    def __repr__(self):
        return "SoftBreak"


class HardBreak(Node):
    __slots__ = ("start",)
    is_inline = True

    def __init__(self, start=-1):
        self.start = start

    def __repr__(self):
        return "HardBreak"


class Code(Node):
    __slots__ = ("attrs", "value")
    is_inline = True

    def __init__(self, value, attrs=None):
        self.value = value
        self.attrs = attrs

    def __repr__(self):
        return f"Code({self.value!r})"


class Math(Node):
    __slots__ = ("attrs", "display", "value")
    is_inline = True

    def __init__(self, value, display, attrs=None):
        self.value = value
        self.display = display
        self.attrs = attrs


class Literal(Node):
    __slots__ = ("attrs", "value")
    is_inline = True

    def __init__(self, value, attrs=None):
        self.value = value
        self.attrs = attrs


class RawInline(Node):
    __slots__ = ("fmt", "value")
    is_inline = True

    def __init__(self, fmt, value):
        self.fmt = fmt
        self.value = value


class Autolink(Node):
    __slots__ = ("attrs", "href", "text")
    is_inline = True

    def __init__(self, text, href, attrs=None):
        self.text = text
        self.href = href
        self.attrs = attrs


class Crossref(Node):
    __slots__ = ("children", "href", "resolved", "src", "target")
    is_inline = True

    def __init__(self, target, src):
        self.target = target
        self.src = src
        self.resolved = False
        self.children = None
        self.href = None


class Comment(Node):
    """Braced inline comment: renders nothing."""

    __slots__ = ()
    is_inline = True


class CriticComment(Node):
    __slots__ = ("value",)
    is_inline = True

    def __init__(self, value):
        self.value = value


class InlineNote(Node):
    __slots__ = ("attrs", "children", "counted", "number", "ref_id")
    is_inline = True

    def __init__(self, children, attrs=None):
        self.children = children
        self.attrs = attrs
        self.number = None
        self.ref_id = None
        self.counted = False


class NoteRef(Node):
    __slots__ = ("attrs", "label", "number", "ref_id", "resolved", "src")
    is_inline = True

    def __init__(self, label, attrs, src):
        self.label = label
        self.attrs = attrs
        self.src = src
        self.number = None
        self.ref_id = None
        self.resolved = False


class Ext(Node):
    __slots__ = ("attrs", "children", "name")
    is_inline = True

    def __init__(self, name, children, attrs=None):
        self.name = name
        self.children = children
        self.attrs = attrs


class Link(Node):
    __slots__ = ("attrs", "children", "dest", "title")
    is_inline = True

    def __init__(self, children, dest, title=None, attrs=None):
        self.children = children
        self.dest = dest
        self.title = title
        self.attrs = attrs


class Image(Node):
    __slots__ = ("alt", "attrs", "dest", "title")
    is_inline = True

    def __init__(self, alt, dest, title=None, attrs=None):
        self.alt = alt
        self.dest = dest
        self.title = title
        self.attrs = attrs


class RefLink(Node):
    """A reference link or image awaiting resolution."""

    __slots__ = (
        "alt",
        "attrs",
        "children",
        "collapsed",
        "dest",
        "image",
        "label",
        "resolved",
        "src",
        "text_label",
        "title",
    )
    is_inline = True

    def __init__(
        self,
        children,
        label,
        collapsed,
        attrs,
        src,
        image=False,
        alt=None,
        text_label=None,
    ):
        self.children = children
        self.label = label
        self.collapsed = collapsed
        self.attrs = attrs
        self.src = src
        self.image = image
        self.alt = alt
        self.resolved = None  # None = unresolved
        self.dest = None
        self.title = None
        self.text_label = text_label


class Span(Node):
    __slots__ = ("attrs", "children")
    is_inline = True

    def __init__(self, children, attrs=None):
        self.children = children
        self.attrs = attrs


class Bracket(Node):
    """A literal bracket run: `[` children `]` (with optional leading `!`)."""

    __slots__ = ("bang", "children")
    is_inline = True

    def __init__(self, children, bang=False):
        self.children = children
        self.bang = bang


class Elem(Node):
    """Emphasis-family span: kind in em, strong, u, s, mark, sup, sub, ins, del."""

    __slots__ = ("attrs", "children", "kind")
    is_inline = True

    def __init__(self, kind, children, attrs=None):
        self.kind = kind
        self.children = children
        self.attrs = attrs

    def __repr__(self):
        return f"Elem({self.kind}, {self.children!r})"


class Subst(Node):
    __slots__ = ("new", "old")
    is_inline = True

    def __init__(self, old, new):
        self.old = old
        self.new = new


class Mention(Node):
    __slots__ = ("name", "sigil")
    is_inline = True

    def __init__(self, sigil, name):
        self.sigil = sigil
        self.name = name


class Symbol(Node):
    __slots__ = ("attrs", "name")
    is_inline = True

    def __init__(self, name, attrs=None):
        self.name = name
        self.attrs = attrs


class Smart(Node):
    """Smart punctuation: glyph plus authored source run."""

    __slots__ = ("glyph", "src")
    is_inline = True

    def __init__(self, glyph, src):
        self.glyph = glyph
        self.src = src

    def __repr__(self):
        return f"Smart({self.glyph!r})"


class Abbr(Node):
    __slots__ = ("term", "title")
    is_inline = True

    def __init__(self, term, title):
        self.term = term
        self.title = title


class CaptionNumber(Node):
    __slots__ = ("value",)
    is_inline = True

    def __init__(self, value):
        self.value = value


# ---------------------------------------------------------------- blocks


class Block(Node):
    __slots__ = ()


class Document(Block):
    __slots__ = ("children",)

    def __init__(self):
        self.children = []


class Paragraph(Block):
    __slots__ = (
        "attrs",
        "block_image",
        "caption",
        "hardbreaks",
        "inlines",
        "lb_info",
        "line_block",
        "lines",
        "literal_braces",
        "math_host",
        "parser",
    )

    def __init__(self, lines=None, attrs=None):
        self.lines = lines if lines is not None else []
        self.attrs = attrs
        self.inlines = None
        self.parser = None
        self.block_image = False
        self.caption = None
        self.literal_braces = None
        self.math_host = False
        self.line_block = False
        self.hardbreaks = False
        self.lb_info = None


class Heading(Block):
    __slots__ = (
        "attrs",
        "id",
        "in_footnote",
        "in_quote",
        "inlines",
        "level",
        "parser",
        "plain",
        "text",
        "top",
    )

    def __init__(self, level, text, attrs=None):
        self.level = level
        self.text = text
        self.attrs = attrs
        self.inlines = None
        self.parser = None
        self.id = None
        self.top = False
        self.in_quote = False
        self.in_footnote = None
        self.plain = None


class ThematicBreak(Block):
    __slots__ = ("attrs",)

    def __init__(self, attrs=None):
        self.attrs = attrs


class CodeBlock(Block):
    __slots__ = (
        "attrs",
        "caption",
        "closed",
        "content",
        "final_nl",
        "label",
        "lang",
        "lines",
        "title",
    )

    def __init__(self, lang=None, title=None, label=None, attrs=None):
        self.lang = lang
        self.title = title
        self.label = label
        self.lines = []
        self.content = None
        self.attrs = attrs
        self.caption = None
        self.closed = False
        self.final_nl = True


class RawBlock(Block):
    __slots__ = ("attrs", "closed", "content", "final_nl", "fmt", "lines")

    def __init__(self, fmt, attrs=None):
        self.fmt = fmt
        self.lines = []
        self.content = None
        self.attrs = attrs
        self.closed = False
        self.final_nl = True


class BlockQuote(Block):
    __slots__ = ("attrs", "caption", "children", "fenced", "has_content")

    def __init__(self, attrs=None, fenced=False):
        self.children = []
        self.attrs = attrs
        self.fenced = fenced
        self.caption = None
        self.has_content = False


class ListBlock(Block):
    __slots__ = (
        "attrs",
        "bare",
        "bullet",
        "decided",
        "delim",
        "dialect",
        "first_marker",
        "first_value",
        "force_loose",
        "items",
        "loose",
        "ordered",
        "sealed",
        "start",
        "task",
    )

    def __init__(
        self, ordered, bullet=None, dialect=None, delim=None, task=False, attrs=None
    ):
        self.ordered = ordered
        self.bullet = bullet
        self.dialect = dialect
        self.delim = delim
        self.start = None
        self.task = task
        self.items = []
        self.attrs = attrs
        self.loose = False
        self.force_loose = False
        self.first_value = None
        self.first_marker = None
        self.bare = False
        self.sealed = False
        self.decided = False


class ListItem(Block):
    __slots__ = ("attrs", "blank_before", "children", "marker", "task_state", "value")

    def __init__(self, attrs=None, task_state=None):
        self.children = []
        self.attrs = attrs
        self.task_state = task_state
        self.blank_before = False
        self.marker = None
        self.value = None


class DefList(Block):
    __slots__ = ("attrs", "items", "loose", "sealed")

    def __init__(self, attrs=None):
        self.items = []
        self.attrs = attrs
        self.loose = False
        self.sealed = False


class DefTerm(Block):
    __slots__ = ("attrs", "inlines", "parser", "text")

    def __init__(self, text, attrs=None):
        self.text = text
        self.attrs = attrs
        self.inlines = None
        self.parser = None


class DefDesc(Block):
    __slots__ = ("attrs", "children")

    def __init__(self, attrs=None):
        self.children = []
        self.attrs = attrs


class Table(Block):
    __slots__ = ("attrs", "caption", "csv", "grid", "raw_lines", "rows")

    def __init__(self, attrs=None):
        self.rows = []
        self.attrs = attrs
        self.caption = None
        self.grid = None
        self.raw_lines = []
        self.csv = None


class Div(Block):
    """Colon-fence container: kind None (generic div), a type word, or one of
    the sigil kinds '|', '\\\\', '>' (quote block) and 'figure'."""

    __slots__ = (
        "adm_id",
        "attrs",
        "caption",
        "children",
        "closed",
        "fence_len",
        "is_figure",
        "kind",
        "label",
        "label_inlines",
        "stanzas",
        "title",
        "title_inlines",
    )

    def __init__(self, kind, title=None, label=None, attrs=None, fence_len=3):
        self.kind = kind
        self.title = title
        self.label = label
        self.children = []
        self.attrs = attrs
        self.fence_len = fence_len
        self.caption = None
        self.closed = False
        self.stanzas = None
        self.title_inlines = None
        self.label_inlines = None
        self.adm_id = None
        self.is_figure = False


class FootnoteDef(Block):
    __slots__ = ("attrs", "children", "label", "used")

    def __init__(self, label):
        self.label = label
        self.children = []
        self.attrs = None
        self.used = False


class Caption:
    """Unparsed caption slot: source lines and the parsed inline content."""

    __slots__ = ("inlines", "label_key", "lines", "number", "parser", "src_lines")

    def __init__(self, lines, src_lines=None):
        self.lines = lines
        self.src_lines = src_lines if src_lines is not None else lines
        self.inlines = None
        self.parser = None
        self.number = None
        self.label_key = None


class Verbatim(Node):
    """Source characters emitted as typed (a declining reference run)."""

    __slots__ = ("s",)
    is_inline = True

    def __init__(self, s):
        self.s = s
