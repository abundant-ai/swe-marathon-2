"""HTML escaping and attribute serialization with the PART 9 §25 hardening."""

from .chars import is_unicode_ws


def esc_text(s):
    if not s:
        return s
    if "&" in s:
        s = s.replace("&", "&amp;")
    if "<" in s:
        s = s.replace("<", "&lt;")
    if ">" in s:
        s = s.replace(">", "&gt;")
    if "\u00a0" in s:
        s = s.replace("\u00a0", "&nbsp;")
    return s


def esc_attr(s):
    if not s:
        return s
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


DENIED_SCHEMES = {
    "javascript",
    "vbscript",
    "data",
    "file",
    "ms-msdt",
    "ms-office",
    "ms-word",
    "ms-excel",
    "ms-powerpoint",
    "ms-access",
    "ms-visio",
    "ms-project",
    "ms-publisher",
    "ms-infopath",
    "ms-spd",
    "ms-search",
    "search-ms",
    "ms-cxh",
    "ms-cxh-full",
    "shell",
    "vscode",
    "vscode-insiders",
    "jar",
}


def _probe_strip(v):
    out = []
    for ch in v:
        o = ord(ch)
        if o < 0x20 or 0x7F <= o <= 0x9F:
            continue
        if is_unicode_ws(ch) or o == 0xFEFF:
            continue
        out.append(ch)
    return "".join(out)


def scheme_denied(v):
    """True when v's URL scheme (after stripping controls and Unicode
    whitespace) is on the denylist."""
    if not v:
        return False
    t = _probe_strip(v)
    k = t.find(":")
    if k <= 0:
        return False
    scheme = t[:k]
    c0 = scheme[0]
    if not (("a" <= c0 <= "z") or ("A" <= c0 <= "Z")):
        return False
    for ch in scheme:
        if not (ch.isascii() and (ch.isalnum() or ch in "+-.")):
            return False
    return scheme.lower() in DENIED_SCHEMES


def _css_decode(v):
    out = []
    i = 0
    n = len(v)
    while i < n:
        c = v[i]
        if c == "\\":
            if i + 1 >= n:
                i += 1
                continue
            j = i + 1
            hx = []
            while j < n and len(hx) < 6 and v[j] in "0123456789abcdefABCDEF":
                hx.append(v[j])
                j += 1
            if hx:
                try:
                    out.append(chr(int("".join(hx), 16)))
                except (ValueError, OverflowError):
                    pass
                if j < n and v[j] in " \t\n\r\x0c":
                    if v[j] == "\r" and j + 1 < n and v[j + 1] == "\n":
                        j += 1
                    j += 1
                i = j
                continue
            if v[j] == "\n":
                i = j + 1
                continue
            out.append(v[j])
            i = j + 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


_STYLE_BAD = ("expression(", "url(", "@import", "behavior:", "-moz-binding")


def style_denied(v):
    d = _css_decode(v)
    d = "".join(ch for ch in d if not (is_unicode_ws(ch) or ch in " \t\n\r\x0c"))
    d = d.lower()
    for pat in _STYLE_BAD:
        if pat in d:
            return True
    return False


_URL_LIST = {"srcset": ",", "imagesrcset": ",", "ping": "", "attributionsrc": ""}


def _url_list_denied(name, v):
    sep = _URL_LIST[name]
    toks = []
    cur = []
    for ch in v:
        if ch in " \t\n\x0c\r" or (sep and ch == ","):
            if cur:
                toks.append("".join(cur))
                cur = []
        else:
            cur.append(ch)
    if cur:
        toks.append("".join(cur))
    for t in toks:
        if t and scheme_denied(t):
            return True
    return scheme_denied(v)


class Gen(str):
    """A value the renderer derives (structural or generated): exempt from
    the authored-value probes of PART 9 §25."""

    __slots__ = ()


def class_value(base=(), authored=(), generated=()):
    """The `class` value: base tokens, then authored, then generated ones,
    each once.  Every authored token is an authored value of its own
    (CARVE-P4-007), so a token whose scheme is denied is blanked and leaves
    the list while the others stand (CARVE-P9-054)."""
    toks = list(base)
    for t in authored:
        if t not in toks and not scheme_denied(t):
            toks.append(t)
    for t in generated:
        if t not in toks:
            toks.append(t)
    return Gen(" ".join(toks))


def harden(name, value):
    """Returns the value to emit, or None to drop the attribute."""
    ln = name.lower()
    if isinstance(value, Gen):
        return value
    if ln.startswith("on") or ln == "srcdoc" or ln == "formaction":
        return None
    if ln == "id":
        return value
    if ln == "style":
        if style_denied(value):
            return ""
        return value
    if ln in _URL_LIST:
        if _url_list_denied(ln, value):
            return ""
        return value
    if scheme_denied(value):
        return ""
    return value


def render_attr_list(pairs):
    """pairs: list of (name, value) already ordered.  Values pass through
    hardening; returns the attribute string with a leading space each."""
    out = []
    for name, value in pairs:
        v = harden(name, value)
        if v is None:
            continue
        out.append(f' {name}="{esc_attr(v)}"')
    return "".join(out)
