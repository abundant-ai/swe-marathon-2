"""Character classes used by the Carve grammar."""

import re
import unicodedata

_cat_cache = {}


def category(c):
    r = _cat_cache.get(c)
    if r is None:
        r = unicodedata.category(c)
        _cat_cache[c] = r
    return r


def is_alnum(c):
    """Unicode letter or number (general category L or N)."""
    if c is None or c == "":
        return False
    o = ord(c)
    if o < 128:
        return ("a" <= c <= "z") or ("A" <= c <= "Z") or ("0" <= c <= "9")
    return category(c)[0] in "LN"


def is_letter(c):
    if c is None or c == "":
        return False
    o = ord(c)
    if o < 128:
        return ("a" <= c <= "z") or ("A" <= c <= "Z")
    return category(c)[0] == "L"


def is_number(c):
    if c is None or c == "":
        return False
    o = ord(c)
    if o < 128:
        return "0" <= c <= "9"
    return category(c)[0] == "N"


def is_ascii_letter(c):
    return c is not None and len(c) == 1 and (("a" <= c <= "z") or ("A" <= c <= "Z"))


def is_ascii_digit(c):
    return c is not None and len(c) == 1 and "0" <= c <= "9"


def is_grapheme_extender(c):
    if c is None or c == "":
        return False
    o = ord(c)
    if o < 0x300:
        return False
    if 0xFE00 <= o <= 0xFE0F or o == 0x200D:
        return True
    return category(c) in ("Mn", "Mc", "Me")


_WS = set(
    [
        0x09,
        0x0A,
        0x0B,
        0x0C,
        0x0D,
        0x20,
        0x85,
        0xA0,
        0x1680,
        0x2028,
        0x2029,
        0x202F,
        0x205F,
        0x3000,
    ]
    + list(range(0x2000, 0x200B))
)


def is_unicode_ws(c):
    """Unicode White_Space property."""
    return c is not None and c != "" and ord(c) in _WS


def is_cf(c):
    return c is not None and c != "" and category(c) == "Cf"


def is_cc(c):
    return c is not None and c != "" and category(c) == "Cc"


ASCII_PUNCT = set("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")


def is_flank(c):
    """typography_flank: whitespace, newline, no-break space."""
    return c == " " or c == "\t" or c == "\n" or c == "\r" or c == "\u00a0"


BIDI_CONTROLS = {
    chr(x) for x in list(range(0x202A, 0x202F)) + list(range(0x2066, 0x206A))
}


def strip_bidi(s):
    if not s:
        return s
    for ch in s:
        if ch in BIDI_CONTROLS:
            return "".join(c for c in s if c not in BIDI_CONTROLS)
    return s


_SPACES = re.compile(" *")
_SPTAB_RUN = re.compile("[ \t]*")


def indent_cols(s):
    """Columns of leading whitespace (spaces and tabs) in s."""
    sp = _SPACES.match(s).end()
    if sp == len(s) or s[sp] != "\t":
        return sp
    col = 0
    for ch in s:
        if ch == " ":
            col += 1
        elif ch == "\t":
            col += 4 - (col % 4)
        else:
            break
    return col


def strip_cols(s, k):
    """Remove up to k columns of leading whitespace from s (tab stops at
    multiples of 4).  A tab straddling the boundary keeps its remaining
    columns as spaces (PART 9 §24 C5).  Returns (residual, removed)."""
    if k <= 0:
        return s, 0
    sp = _SPACES.match(s).end()
    if sp >= k:
        return s[k:], k
    if sp == len(s) or s[sp] != "\t":
        return s[sp:], sp
    col = 0
    i = 0
    n = len(s)
    while i < n and col < k:
        ch = s[i]
        if ch == " ":
            col += 1
            i += 1
        elif ch == "\t":
            nc = col + 4 - (col % 4)
            if nc > k:
                # straddling tab
                return " " * (nc - k) + s[i + 1 :], k
            col = nc
            i += 1
        else:
            break
    return s[i:], col


def is_blank(s):
    return _SPTAB_RUN.match(s).end() == len(s)


def label_key(s):
    """A reference or footnote label's key: runs of U+0020 collapse to one and
    the ends are trimmed; case is kept (PART 9R R1, R2)."""
    s = s.strip(" ")
    return re.sub(r" +", " ", s)
