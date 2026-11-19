"""Rewrites of upstream's BPL code that change what it prints without changing what it is.

Used by scripts/make_cases.py on every case built from upstream's reference records and library
code. Three rewrites, all decided by the private case seed:

- names: every name the code assigns becomes an ordinary English word that the code does not
  use, consistently (`f` becomes `scale` wherever `f` is that name). Keys (after `.`, before
  `:`), names inside text the code evaluates, and module names are left alone.
- numbers: literals in value positions get another value of the same form (an integer stays an
  integer of a similar size, a decimal keeps its places, a suffix stays). Never a size, a count,
  a position, an axis, a rank, an iteration count or a code that selects a function, never a 0,
  1 or a boundary-sized constant, and never in code that checks a result (`≡`, or a record whose
  expected value is true or false).
- words: whole words inside text literals become other words of the same length and case, so
  every shape stays as it was. Keys, options, kinds, patterns, formats and code are left alone.

The recorder (tests/verifier/recorder.py) then runs the variants against the original and keeps
the first that ends as the unedited code does and prints something else.
"""

from __future__ import annotations

import random
import re

from bpl_text import NUMBER_SUFFIXES, Token, tokenize, untokenize

# Ordinary words, for names (lower case) and for words inside text (any length 3-9).
WORDS = """
able acid aged also area army away baby back ball band bank base bath bear beat bell belt bend
best bill bird blow blue boat body bone book boot born boss both bowl bulk burn bush busy cake
call calm camp card care cart case cash cast cell chat chip city clay club coal coat code cold
cook cool copy cord core corn cost crew crop cube curl cute dark data date dawn deal dear debt
deck deep deer desk dial dirt dish dock door dose down draw drop drum duck dust duty earn east
easy edge farm fast feed fern file fill film find fine fire firm fish flag flat flow foam fold
folk fond food foot ford form fort four free frog fuel full fund gain game gate gear gift girl
glad glow goal gold golf good grab gray grid grow gulf hall hand hang hard harm hawk head heap
heat herb hill hint hold hole home hook hope horn host hour huge hunt idea inch iron item jade
jazz join joke july jump june jury just keen keep kept kind king kite knee knot lace lake lamp
land lane last late lawn lead leaf lean left lens life lift lime line link lion list load loan
lock loft long look loop lord loud luck lung mail main make mall malt many maps mark mast meal
meat meet melt menu mild milk mill mind mine mint mist mode mole moon more moss most moth move
much mule nail name navy near neat neck need nest news next nice node noon norm nose note oaks
open oval oven pace pack page paid pain pair palm park part pass past path peak pear peel pile
pine pink pipe plan play plot plum poem pole pond pool port post pour pull pump pure push quiz
race rack raft rail rain ramp rank rare reed rice rich ride ring ripe road rock roof room root
rope rose ruby rule rush safe sage sail salt sand save seal seat seed sell send ship shoe shop
silk sink size skin slab slot slow snow soap sock soft soil sold song soup sour spin spot star
stem step stew stop such suit sung sure swan tail tale talk tall tank tape task team tent term
test text tide tile time tiny toad toll tone tool tour town tram tree trim trip tube tuna tune
twin type unit vase vast vest view vine vote wage wait walk wall ward warm wave week well west
wide wind wine wing wire wise wolf wood wool word work yard yarn year zone
amber apple badge baker beach berry birch blade blank block board bonus brass bread brick brook
brush cabin camel candy canoe cargo cedar chair chalk charm chart chess chord cider cliff clock
cloud coast cocoa coral couch crane creek crown curve cycle daisy delta depot diary dough draft
dream eagle earth easel elbow ember fable fence ferry field flame flask fleet flint flock flour
frame frost fruit glass glaze globe grain grape grass gravy grove guide habit harbor hazel heart
hedge honey horse hotel house image index ivory jelly jewel judge kayak kneel knife label ladle
lemon level light lilac linen lodge lunch maple march marsh melon metal meter mirror model money
month motor mound mouse music nerve night noble north novel ocean olive onion orbit order otter
owner paint panel paper party pasta patch peach pearl pedal penny piano pilot pitch plaza plume
point polar porch pound power press price prism proof prose pulse quail quart queen quest quilt
radar radio raven razor reply ridge river robin rotor round route ruler salad sauce scale scarf
scene scout shade shelf shell shore sight skate slate sleet slope smoke snack solar space spark
spice spoon squad stack staff stage stamp steam steel stone stool storm stove straw sugar suite
sunny swamp sweet table tally teeth thorn tiger toast token topic torch tower trace track trail
train trend tulip uncle union upper usage valve vapor verse video villa vinyl vital vivid voice
wagon waltz water wheat wheel whale wings world yacht yield zebra
anchor animal answer arrival autumn backup ballad banner barrel basket beacon bottle branch
bridge bronze bucket budget butter button camera candle canvas carbon carpet castle cattle
cellar cement center cereal chapel cherry circle closet cobalt coffee collar column copper
corner cotton crayon cursor dinner donkey drawer empire engine fabric falcon family farmer
feather fiddle figure finger flight flower forest friend garden garlic ginger glider goblet
gravel guitar hammer handle harvest helmet hollow island jacket jersey jungle kettle kitten
ladder lagoon lantern leader legend letter lizard locker magnet mammal marble market meadow
medal melody mentor minute mirror monkey mortar muffin museum napkin needle nickel number
office orange orchid oyster paddle palace parcel parrot pebble pencil pepper pickle pillow
planet pocket portal potato powder prairie public puzzle quarry rabbit ribbon rocket saddle
salmon sample season signal silver singer sister sketch spider spring square stable statue
summer sunset supply survey switch symbol tablet teapot temple ticket timber tomato tunnel
turkey turtle tuxedo valley velvet violet volume walnut wallet window winter wizard yogurt
""".split()

# Glyphs whose left argument is a size, count, position, axis or code: a literal on their left
# is never edited (reshape, take, drop, windows, rotate, transpose, index, replicate, partition,
# pick, encode, decode, circular, prime, format, interval index, index-of).
SIZE_ON_LEFT = set("ρ↑↓↕⌽⍉⌷#⊂⊆⊃⊤⊥○⍭⍕⍸ι⌹!")
# Glyphs whose right argument or operand is a size, count, rank or axis: a literal on their right
# is never edited (indices, range, rank, power, axis, stencil, shape, pairs, first, mix).
SIZE_ON_RIGHT = set("ι↦⍤⍣⍠⌺ρ↕↑⊃⊂⊆")
# Code a rename must not touch: it evaluates text as code, reads names by text, or loads modules.
NAME_SENSITIVE = ("⍎", "•ex", "•nc", "•src", "•nl", "•load", "•literal", "•explain", ".(", "•signal $e")
# System functions whose text arguments are options, kinds, patterns or formats, never prose.
TEXT_SENSITIVE = ("⍎", "•ex", "•r", "•replace", "•json", "•csv", "•xml", "•element", "•c", "•ucs", "•normalize", "•vfi",
                  "•hash", "•signal", "•host", "•prefs", "•special", "•distribution", "•path", "•mime", "•literal", "⍠[")
NO_LETTERS_START = ("e", "j", "r", "E", "J")


def assigned(tokens: list[Token]) -> set[str]:
    """Names the code assigns: a name followed by `←`, a name in a bracketed list of names that
    is assigned to, and names in a modified assignment (`x+←1`). Keys (after `.` or before `:`)
    are not included."""
    found: set[str] = set()
    solid = [(index, token) for index, token in enumerate(tokens) if token.kind not in ("space",)]
    for position, (index, token) in enumerate(solid):
        if token.kind != "name":
            continue
        after = solid[position + 1][1] if position + 1 < len(solid) else None
        if after is not None and after.text == "←":
            found.add(token.text)
        elif after is not None and after.kind == "glyph" and after.text not in "←.[]();:◇" and position + 2 < len(solid) \
                and solid[position + 2][1].text == "←":
            found.add(token.text)
    # [a b c]←… and (a b)←…
    for position, (index, token) in enumerate(solid):
        if token.text not in "[(":
            continue
        close = "]" if token.text == "[" else ")"
        names, scan = [], position + 1
        while scan < len(solid) and solid[scan][1].kind in ("name",) or (scan < len(solid) and solid[scan][1].text in ";◇"):
            if solid[scan][1].kind == "name":
                names.append(solid[scan][1].text)
            scan += 1
        if names and scan + 1 < len(solid) and solid[scan][1].text == close and solid[scan + 1][1].text == "←":
            found.update(names)
    return found


def keys_and_texts(tokens: list[Token]) -> set[str]:
    """Names that must keep their spelling: those used as keys (after `.`, before `:`), and every
    word inside text literals (a name may be read from text)."""
    keep: set[str] = set()
    for index, token in enumerate(tokens):
        if token.kind == "name":
            before = tokens[index - 1].text if index else ""
            after = tokens[index + 1].text if index + 1 < len(tokens) else ""
            if before == "." or after == ":":
                keep.add(token.text)
        elif token.kind == "string":
            keep.update(re.findall(r"[A-Za-z_∆⍙][A-Za-z0-9_∆⍙]*", token.text))
    return keep


def renaming(code: str, rng: random.Random, taken: set[str] = frozenset()) -> dict[str, str]:
    """A consistent renaming of the names `code` assigns to unused ordinary words, or {} where
    renaming is unsafe (`NAME_SENSITIVE`).

    Args:
        code: The program, all of its files joined, so that a name is renamed the same way in
            each.
        rng: The private seed's generator; the same seed gives the same names.
        taken: Further names that no new name may equal (another file's names, say).

    Returns:
        Old name to new name. A name that is also a key or appears in text keeps its spelling.
    """
    if any(marker in code for marker in NAME_SENSITIVE):
        return {}
    tokens = tokenize(code)
    names = sorted(assigned(tokens) - keys_and_texts(tokens))
    used = {token.text for token in tokens if token.kind == "name"} | set(taken)
    pool = [word for word in WORDS if not word.startswith(NO_LETTERS_START) and word not in used]
    rng.shuffle(pool)
    mapping = {}
    for name in names:
        if not pool or name in ("_",) or name.startswith("_"):
            continue
        word = pool.pop()
        mapping[name] = word.capitalize() if name[:1].isupper() else word
    return mapping


def renamed(code: str, mapping: dict[str, str]) -> str:
    """`code` with every name token in `mapping` replaced, except where it is a key (after `.`
    or before `:`)."""
    if not mapping:
        return code
    tokens = tokenize(code)
    out = []
    for index, token in enumerate(tokens):
        before = tokens[index - 1].text if index else ""
        after = tokens[index + 1].text if index + 1 < len(tokens) else ""
        if token.kind == "name" and token.text in mapping and before != "." and after != ":":
            out.append(Token("name", mapping[token.text]))
        else:
            out.append(token)
    return untokenize(out)


def _neighbour(tokens: list[Token], index: int, step: int) -> Token | None:
    """The nearest token before (step -1) or after (step 1) `index` that is not blank space."""
    index += step
    while 0 <= index < len(tokens) and tokens[index].kind == "space":
        index += step
    return tokens[index] if 0 <= index < len(tokens) else None


def _strand(tokens: list[Token], index: int) -> tuple[int, int]:
    """The first and last token index of the literal strand holding the number at `index`
    (numbers separated only by single spaces)."""
    first = last = index
    while first - 2 >= 0 and tokens[first - 1].kind == "space" and tokens[first - 2].kind == "number":
        first -= 2
    while last + 2 < len(tokens) and tokens[last + 1].kind == "space" and tokens[last + 2].kind == "number":
        last += 2
    return first, last


def number_sites(code: str) -> list[int]:
    """Token positions of the numbers in `code` that may take another value: in a value position,
    not 0, 1 or ¯1, at most six digits, with no exponent, complex or rational part, and in code
    that checks no result (no `≡`). See the module docstring for the positions left alone."""
    if "≡" in code or "•prefs" in code or "•float" in code or "⍠[" in code:
        return []
    tokens = tokenize(code)
    sites = []
    for index, token in enumerate(tokens):
        if token.kind != "number":
            continue
        core = token.text.lstrip("¯")
        digits = re.match(r"[0-9.]+", core).group(0)
        if core[len(digits):] not in ("",) + NUMBER_SUFFIXES:  # an exponent, complex or rational part
            continue
        if digits in ("0", "1") or len(digits.replace(".", "")) > 6:
            continue
        first, last = _strand(tokens, index)
        before, after = _neighbour(tokens, first, -1), _neighbour(tokens, last, 1)
        if after is not None and after.kind == "glyph" and (after.text in SIZE_ON_LEFT or after.text in "₀₁₂₃₄₅₆₇₈₉¹²³⁴⁵⁶⁷⁸⁹⁰⁻"):
            continue
        if before is not None and before.kind == "glyph" and (before.text in SIZE_ON_RIGHT or before.text in ".[;"):
            continue
        if before is not None and before.kind in ("system",):
            continue
        if after is not None and after.text in (":",):
            continue
        if any(near is not None and near.kind == "glyph" and near.text in "=≠" for near in (before, after)):
            continue  # a value compared with another: changing one side makes the check trivially false
        sites.append(index)
    return sites


def edited_number(text: str, rng: random.Random) -> str:
    """Another literal of the same form as `text`: the same sign and suffix, an integer of a
    similar size (and within a fixed width's range), or a decimal with the same places."""
    sign = "¯" if text.startswith("¯") else ""
    body = text[len(sign):]
    digits = re.match(r"[0-9.]+", body).group(0)
    suffix = body[len(digits):]
    if "." in digits:
        places = len(digits.split(".")[1])
        value = float(digits)
        for _ in range(20):
            new = round(rng.uniform(max(0.1, value * 0.3), value * 2.5 + 1), places)
            text_new = f"{new:.{places}f}"
            if text_new != digits and float(text_new) not in (0.0, 1.0):
                return sign + text_new + suffix
        return text
    value = int(digits)
    top = {"ₓ₁": 100, "ₓ₂": 30000}.get(suffix, max(9, value * 2 + 3))
    for _ in range(20):
        new = rng.randint(2, max(3, top))
        if new != value:
            return f"{sign}{new}{suffix}"
    return text


def text_sites(code: str) -> list[int]:
    """Token positions of the text literals in `code` whose words may change: prose made of
    letters, spaces and light punctuation, not a key (`"k":`), a kind (`"DOMAIN"::`), and not in
    code that hands text to a system function that reads it as options, patterns or formats."""
    if any(marker in code for marker in TEXT_SENSITIVE):
        return []
    tokens = tokenize(code)
    sites = []
    for index, token in enumerate(tokens):
        if token.kind != "string":
            continue
        inner = token.text[1:-1]
        if not re.fullmatch(r"[A-Za-z ,.!?'-]*", inner) or not re.search(r"[A-Za-z]{3,}", inner):
            continue
        after, before = _neighbour(tokens, index, 1), _neighbour(tokens, index, -1)
        if after is not None and after.text in (":", "⍕", "⍎"):
            continue
        if before is not None and before.kind == "system":
            continue
        sites.append(index)
    return sites


def edited_text(text: str, rng: random.Random) -> str:
    """The string literal `text` with each word of three letters or more replaced by another word
    of the same length and the same case pattern; spaces and punctuation stay."""
    def swap(match: re.Match) -> str:
        word = match.group(0)
        choices = [w for w in WORDS if len(w) == len(word) and w != word.lower()]
        if not choices:
            return word
        new = rng.choice(choices)
        if word.isupper():
            return new.upper()
        if word[0].isupper():
            return new.capitalize()
        return new
    return re.sub(r"[A-Za-z]{3,}", swap, text)


def edit(code: str, rng: random.Random, share: float) -> str:
    """`code` with about `share` of its editable numbers and texts (`number_sites`,
    `text_sites`) given new values, at least one where any is editable."""
    tokens = tokenize(code)
    sites = number_sites(code) + text_sites(code)
    if not sites:
        return code
    chosen = [site for site in sites if rng.random() < share] or [rng.choice(sites)]
    out = list(tokens)
    for site in chosen:
        token = out[site]
        out[site] = Token(token.kind, edited_number(token.text, rng) if token.kind == "number" else edited_text(token.text, rng))
    return untokenize(out)


def variants(code: str, rng: random.Random, count: int = 3) -> list[str]:
    """Up to `count` distinct edits of `code` (all sites, about half, one), none equal to `code`.
    Empty where nothing may be edited."""
    found: list[str] = []
    for share in (1.0, 0.5, 0.0)[:count]:
        candidate = edit(code, rng, share)
        if candidate != code and candidate not in found:
            found.append(candidate)
    return found
