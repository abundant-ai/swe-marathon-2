"""Cases for the documented items that the other kinds leave without a graded case, and for the
file-read rule of the sandboxed build (round 17).

Used by scripts/make_cases.py, which appends these cases after every other one (ids from
P01778 on), drawn from a generator of their own (`cases`), so that no other case changes. Two
kinds:

- coverage: one documented function, setting or glyph per case, with its corner conditions and
  its errors: `"-" •nput`, `•nget` on a file, `•path` and `•path⁻`, the deterministic `•uuid`
  versions, `•normalize`, `•element`, `•xml` and `•xml⁻`, `•detach`, `•prefs ⍬` and the settings
  `fns`, `dissect`, `hanzi_aliases`, `int`, `float`, `trees`, `width` and `batch`, `⊘`, `⍢`, `⊽`
  and `⍀`, and `•ucs⁻`, `•edge`, `•special`, `•host "version"`, `•literal`, `•src` and `•ex`;
- sandbox: what the build reads through each of its read paths (the program file, `•nget`,
  `•load`): a file elsewhere by an absolute path, a path that climbs out with `..`, a link that
  leads out, files under `/proc`, `/sys` and `/dev`, and the reads it allows (a file in the
  working directory, in a directory under it, through a link that stays inside).

A case may name files outside its working directory (`outside`, by path under the directory
beside it, runcases.outside) and links in it (`links`, by path, to their targets); the runner
makes both before each run, the same way when the original's answers are recorded and when a
rebuild is graded. Guarded cases (`form` "guarded") print an error's kind and message. The
templates are public with the generator; their data (names, words, numbers) come from the
private seed. Nothing here runs BPL: the answers are recorded from the original when the
verifier image is built.

`ITEMS` names what each family covers, for the coverage check (`documented_items`, `missing`).
"""

from __future__ import annotations

import json
import random
import re

import bpl_text
import programs

# The most cases `cases` gives: with every other kind's count (make_cases.KIND_COUNTS), the cases a
# grading runs at their time limit still fit its deadline (a development check reads both).
MOST = 70
GUARD = '{{∞::$e.kind,": ",$e.message ◇ {body}}}0'
WORDS = programs.TEXT_WORDS
PLACES = programs.PLACES
ITEMS_WORDS = programs.ITEMS
OUTSIDE = "../bpl-outside"  # the directory beside the working directory where `outside` files go


def case(kind: str, source: str, argv: list[str], files: dict[str, str] | None = None, stdin: str | None = None,
         **extra) -> dict:
    """One case as the recorder and the verifier read it (as make_cases.case builds them)."""
    return {"kind": kind, "source": source, "argv": argv, "files": files or {}, "stdin": stdin, **extra}


def guarded(*bodies: str) -> str:
    """Statements that each run one expression under a guard printing what it caught."""
    return "".join(GUARD.format(body=body) + "\n" for body in bodies)


def script(family: str, text: str, files: dict[str, str] | None = None, guards: bool = False, **extra) -> dict:
    """A coverage case: `text` as main.bpl, beside `files`."""
    return case("coverage", f"coverage:{family}", ["main.bpl"], dict(files or {}, **{"main.bpl": text}), family=family,
                **({"form": "guarded"} if guards else {}), **extra)


def word(rng: random.Random) -> str:
    return rng.choice(WORDS + PLACES + ITEMS_WORDS)


def nput(rng: random.Random) -> list[dict]:
    """`"-" •nput`: text with no line ending, bytes, the prompt of a read of `⎕`; and the refusals
    and errors."""
    a, n = word(rng), rng.randint(3, 9)
    accented = rng.choice(["café", "naïve", "über", "señor", "façade", "crème"]) + str(rng.randint(1, 9))
    data = " ".join(str(byte) for byte in accented.encode()) + " 10"
    prompt, answer = rng.choice(["name", "city", "code", "item"]), rng.choice(PLACES)
    return [
        script("nput", f'w←"{a}"\n"-" •nput w,"/",⌽w\n⎕←{n}×≢w\n"-" •nput ⍕{n}+ι3\n⎕←""\n'),
        script("nput", f"b←{data}\nn←\"-\" •nput b\n⎕←n\n⎕←≢b\n"),
        case("coverage", "coverage:nput", ["main.bpl"], {"main.bpl": f'"-" •nput "{prompt}? "\nx←⎕\n⎕←⌽x\n⎕←≢x\n'},
             f"{answer}\n", family="nput"),
        script("nput", guarded(f'"{a}.txt" •nput "{word(rng)}"', '"-" •nput 300 1', '"-" •nput 255 254',
                               f'["path":"{a}.out" "overwrite":1] •nput "x"', '"-" •nput 2 2ρ"abcd"'), guards=True),
    ]


def nget(rng: random.Random) -> list[dict]:
    """`•nget` on a file: a whole file, its bytes, a path relative to the file holding the code;
    and its errors."""
    rows = [f"{rng.choice(PLACES)},{rng.randint(1, 99)}" for _ in range(rng.randint(3, 6))]
    table = "\n".join(rows) + "\n"
    accented = ", ".join(rng.choice(["café", "über", "naïve", "olé", "señor"]) for _ in range(rng.randint(2, 4))) + "."
    inner, outer = word(rng), word(rng)
    return [
        script("nget", 't←•nget "rows.csv"\n⎕←≢t\n⎕←+/t=","\nlines←(t≠•ucs 10)⊆t\n⎕←≢lines\n⎕←⌽⊃⌽lines\n',
               {"rows.csv": table}),
        script("nget", 'b←["binary":1] •nget "notes.txt"\nt←•nget "notes.txt"\n⎕←(≢b) (≢t)\n⎕←+/b>127\n⎕←•ucs 3↑b\n',
               {"notes.txt": accented + "\n"}),
        script("nget", 'm←•load "sub/m.bpl"\n⎕←m.here\n⎕←m.up\n⎕←≢•nget "note.txt"\n',
               {"sub/m.bpl": 'here←⌽•nget "./note.txt"\nup←≢•nget "../note.txt"\n',
                "sub/note.txt": inner + "\n", "note.txt": outer + " " + inner + "\n"}),
        script("nget", guarded('•nget "missing.txt"', '•nget "sub"', '["binary":2] •nget "data.txt"',
                               '["encoding":"latin1"] •nget "data.txt"', "•nget 5"),
               {"data.txt": word(rng) + "\n", "sub/x.txt": "x\n"}, guards=True),
    ]


def path(rng: random.Random) -> list[dict]:
    """`•path` and `•path⁻`: the parts of paths and arrays of paths, joining parts back, a change
    under `@`, `absolute`; and the errors."""
    folder, stem, other = rng.sample(PLACES, 3)
    ext, ext2 = rng.sample(["csv", "txt", "json", "bpl", "log", "dat"], 2)
    return [
        script("path", f'p←•path "{folder}/{stem}.{ext}" "{other}" ".{ext2}" "{folder}/archive.tar.gz"\n'
                       f"⎕←p.parent\n⎕←p.stem\n⎕←p.extension\n⎕←p.name\n"),
        script("path", f'r←•path "{folder}/sub/{stem}.{ext}"\nr.stem←⌽r.stem\n⎕←•path⁻ r\n'
                       f'⎕←•path⁻ ["parent":"" "stem":"{other}" "extension":"" "name":"x"]\n'
                       f'⎕←•path⁻ ["parent":"{folder}" "stem":"{stem}" "extension":"{ext2}" "name":"x"]\n'),
        script("path", f'⎕←{{ω.stem←ω.stem,"_{rng.randint(2, 99)}" ◇ ω}}@•path "{folder}/{stem}.{ext}"\n'
                       f'q←["absolute":1] •path "{other}/{stem}.{ext2}"\n⎕←q.name\n⎕←\'/\'=↑q.parent\n'
                       f'⎕←(≢q.parent)>≢"{other}"\n'),
        script("path", guarded("•path 5", f'•path⁻ ["parent":"{folder}" "size":3]', '["absolute":1] •path ""',
                               f'["deep":1] •path "{stem}"'), guards=True),
    ]


def uuid(rng: random.Random) -> list[dict]:
    """The `•uuid` versions that give the same UUID every time: 0, 3 and 5 from a namespace and a
    name, 8 from 16 bytes; and the errors."""
    host = f"{word(rng)}.{rng.choice(['org', 'com', 'net', 'io'])}"
    name = word(rng)
    data = " ".join(str(rng.randint(0, 255)) for _ in range(16))
    return [
        script("uuid", f'n←•uuid 0\n⎕←n\n⎕←≢n\n⎕←"dns" "{host}" •uuid 5\n⎕←"dns" "{host}" •uuid 3\n'
                       f'⎕←"url" "https://{host}/{name}" •uuid 5\n'),
        script("uuid", f'⎕←"oid" "1.3.6.1.4.1.{rng.randint(100, 9999)}" •uuid 3\n⎕←"x500" "cn={name},o={host}" •uuid 5\n'
                       f'ns←"dns" "{host}" •uuid 5\n⎕←[ns "{name}"] •uuid 5\n⎕←[ns "{name}"] •uuid 3\n'),
        script("uuid", f"⎕←({data}) •uuid 8\n⎕←(ι16) •uuid 8\nu←({data}) •uuid 8\nv←(⌽{data}) •uuid 8\n⎕←u≡v\n⎕←≢∪u v\n"),
        script("uuid", guarded("•uuid 2", f'"dns" •uuid 5', "(ι15) •uuid 8", f'"dns" "{host}" •uuid 0',
                               f'"ftp" "{host}" •uuid 5'), guards=True),
    ]


def normalize(rng: random.Random) -> list[dict]:
    """`•normalize`: NFC by default, each named form on accents and compatibility characters; and
    the errors."""
    base = rng.choice(["e", "a", "o", "u", "i"])
    mark = rng.choice([769, 768, 776, 770])
    letters = rng.choice(["ﬁ", "ﬂ", "ﬃ", "①", "²", "Ⅻ", "ｶ"])
    return [
        script("normalize", f"t←•ucs {ord(base)} {mark} {ord(rng.choice('nmrst'))}\n⎕←•ucs •normalize t\n"
                            f'⎕←≢•normalize t\n⎕←•ucs "NFD" •normalize •normalize t\n'),
        script("normalize", f'f←"NFC" "NFD" "NFKC" "NFKD"\nt←"{letters}{rng.choice(["é", "ñ", "ü", "å"])}"\n'
                            f"r←f •normalize¨⊂t\n⎕←≢¨r\n⎕←•ucs¨r\n"),
        script("normalize", guarded('"NFX" •normalize "a"', "•normalize 65 66", '"nfc" •normalize "a"'), guards=True),
    ]


def element(rng: random.Random) -> list[dict]:
    """`•element`: element functions with attributes and children, nested, shown as the call that
    made them; and the errors."""
    outer, inner = rng.sample(["ul", "ol", "tr", "nav", "div", "section", "table", "menu"], 2)
    leaf = rng.choice(["li", "td", "span", "em", "b", "a"])
    a, b, c = (word(rng) for _ in range(3))
    return [
        script("element", f'o←•element "{outer}"\nl←•element "{leaf}"\n⎕←o l¨"{a}" "{b}"\nl\no\n'),
        script("element", f'e←•element "{leaf}"\nt←["class":"{a}" "data-n":{rng.randint(1, 99)}] e "{b} & <{c}>"\n'
                          f"⎕←t.tag\n⎕←t.attrs\n⎕←t.children\n⎕←e [\"id\":\"{c}\"]\n⎕←e \"\"\n"),
        script("element", f'e←•element "{leaf}"\n' + guarded(f'•element "{rng.randint(1, 9)}{leaf}"',
                                                              f'e ["{rng.randint(1, 9)}x":1]', 'e ["a b":1]', "•element 5"),
               guards=True),
    ]


def xml(rng: random.Random) -> list[dict]:
    """`•xml` and `•xml⁻`: reading attributes, children, prefixes and namespaces (comments and
    blank text dropped), writing escapes, numeric attributes and empty elements, a changed tree;
    and the errors."""
    root, child = rng.sample(["list", "order", "item", "entry", "row", "note", "part", "record"], 2)
    key, value, text = rng.choice(["kind", "status", "unit", "lang"]), word(rng), word(rng)
    n = rng.randint(2, 9)
    return [
        script("xml", f't←•xml "<{root} {key}=""{value}""><!-- {word(rng)} --><{child}>{text}</{child}>  <{child}/></{root}>"\n'
                      f"⎕←t.tag\n⎕←t.attrs\n⎕←≢t.children\n⎕←(↑t.children).children\n⎕←(↑⌽t.children).children\n"),
        script("xml", f'e←•element "{root}"\nc←•element "{child}"\n'
                      f'⎕←•xml⁻ ["{key}":({n} {n + 1} {n + 2})] e (c "{text} < & > ""q""") (c ["{key}":"{value}"])\n'
                      f'⎕←•xml⁻ e ""\n'),
        script("xml", f't←•xml "<{root}><{child} {key}=""{n}"">{text}</{child}></{root}>"\n'
                      f'c←↑t.children\nc.attrs←["{key}":"{n * 3}" "extra":"{value}"]\nt.children←c c\n⎕←•xml⁻ t\n'),
        script("xml", f't←•xml "<p:{root} xmlns:p=""urn:{value}""><p:{child} p:{key}=""{n}""/></p:{root}>"\n'
                      f"⎕←t.tag\n⎕←t.attrs\n⎕←(↑t.children).tag\n⎕←(↑t.children).attrs\n"),
        script("xml", guarded(f'•xml "<{root}><{child}></{root}>"', f'•xml "<{root}>"', f'•xml "{text}"',
                              f'•xml⁻ ["tag":"{n}{root}" "attrs":(⍬:⍬) "children":""]',
                              f'•xml⁻ ["tag":"{root}" "attrs":["a b":"{value}"] "children":""]', "•xml⁻ 5"), guards=True),
    ]


def detach(rng: random.Random) -> list[dict]:
    """`•detach`: no derivative through it under `∂` and nested `∂`, and the value itself outside."""
    v = " ".join(str(rng.randint(1, 9)) for _ in range(rng.randint(2, 5)))
    k = rng.randint(2, 7)
    return [
        script("detach", f"⎕←{{+/ω×•detach ω}}∂ {v}\n⎕←{{+/ω×ω}}∂ {v}\n⎕←{{+/{k}×•detach ω×ω}}∂ {v}\n"),
        script("detach", f"⎕←{{ω×•detach ω}}∂∂ {k}\n⎕←{{ω×ω}}∂∂ {k}\n⎕←{{(•detach ω)+ω×ω}}∂ {k}\n"),
        script("detach", f'r←["a":{v} "b":"{word(rng)}"]\n⎕←(•detach r)≡r\n⎕←•detach 2 2ρ{v} {k}\n⎕←•detach ⍬\n'),
    ]


def prefs(rng: random.Random, hanzi: dict[str, str]) -> list[dict]:
    """`•prefs ⍬` (every setting, those the agent need not implement reported with their values),
    and the settings no reference record sets: `fns`, `dissect`, `hanzi_aliases`; and more of
    `int`, `float`, `trees`, `width` and `batch`."""
    p, limit = rng.choice([3, 4, 6, 7]), rng.choice([5, 8, 12])
    values = " ".join(str(rng.randint(1, 40)) for _ in range(rng.randint(3, 6)))
    found = [
        script("prefs", f'•prefs ["prec":{p} "box":$t]\n⎕←•prefs ⍬\n⎕←÷7\n'),
        script("prefs", f's←•prefs ⍬\n⎕←≢s\n⎕←s.limit\n⎕←"threads"⊃s\n⎕←"fusion"⊃s\n•prefs ["limit":{limit}]\n'
                        f'⎕←(•prefs ⍬).limit\n'),
        script("prefs", f'•prefs ["box":$t "fns":$f]\nf←{{⎕←2 2ρω ◇ ω}}\nr←f {values} {rng.randint(1, 9)}\n'
                        f"⎕←2 2ρr\n"),
        script("prefs", f'•prefs ["box":$t]\nf←{{⎕←2 2ρω ◇ +/ω}}\n⎕←f ι{rng.randint(4, 9)}\n⎕←(•prefs ⍬).fns\n'),
        script("prefs", f'•prefs ["dissect":$t]\nx←{rng.randint(2, 9)}×{rng.randint(2, 9)}\nx+{rng.randint(1, 9)}\n'
                        f"⌽{values}\n"),
        script("prefs", f'•prefs ["dissect":$t "trees":$t]\nv←{values}\n+/v×2\n(⌈/v)-⌊/v\n'),
        script("prefs", f'•prefs ["kinds":"static" "int":64]\n⎕←2147483647ₓ+{rng.randint(1, 99)}ₓ\n'
                        f'•prefs ["int":32]\n⎕←2147483647ₓ+{rng.randint(1, 99)}ₓ\n'),
        script("prefs", f'•prefs ["float":32]\nx←÷{rng.choice([3, 7, 9, 11])}\n⎕←x\n•prefs ["float":16]\ny←÷{rng.choice([3, 7, 9])}\n'
                        f"⎕←y\n"),
        script("prefs", f'•prefs ["trees":$t]\nf←+/÷≢\nf\n•prefs ["width":{rng.randint(12, 20)}]\nι{rng.randint(20, 40)}\n'),
        script("prefs", f'•prefs ["batch":$f]\n⎕←{{ω×2}}¨{values}\n•prefs ["batch":$t]\n⎕←(•prefs ⍬).batch\n'),
    ]
    if hanzi:
        plus, times, count, reverse = (hanzi.get(glyph, "").split("/")[-1] for glyph in "+×≢⌽")
        assign = hanzi.get("←", "").split("/")[0]
        if all((plus, times, count, reverse, assign)):
            x, y = rng.randint(2, 9), rng.randint(2, 9)
            found += [
                script("prefs", f'•prefs ["hanzi_aliases":$t]\nv{assign}{values}\n⎕←{count}v\n⎕←{reverse}v\n'
                                f"⎕←{x}{plus}{y}{times}{rng.randint(2, 9)}\n"),
                script("prefs", f'•prefs ["hanzi_aliases":$t]\n⎕←{x}{times}{y}\n'
                                f"t{assign}{x} {y}{plus}1\n⎕←{reverse}t\n"),
            ]
    return found


def glyphs(rng: random.Random) -> list[dict]:
    """The glyphs no reference record uses, or almost none: `⊘`, `⍢`, `⊽` and `⍀`."""
    n, m = rng.randint(2, 9), rng.randint(2, 9)
    v = " ".join(str(rng.randint(1, 30)) for _ in range(rng.randint(3, 6)))
    return [
        script("valences", f"f←(-)⊘×\n⎕←(f {n}) ({m} f {n})\ng←{{α 0⊘1 ω}}\n⎕←(g {n}) ({m} g {n})\n⎕←(÷⊘-)⁻{n}\n"),
        script("valences", f"h←{{≢ω}}⊘{{α+≢ω}}\n⎕←h {v}\n⎕←{m} h {v}\n⎕←+⊘×/{v}\n"),
        script("operator-recursion", f"op←{{ω=0?0;≥⍶⍢≤ω}}\n⎕←+op {n}\n⎕←×op {m}\n"
                                     f"fact←{{ω≤1?1;ω×⍶⍢≤ω}}\n⎕←+fact {rng.randint(3, 7)}\n"),
        script("operator-recursion", f"sum←{{0=≢ω?0;(⍶↑ω)+⍶⍢1↓ω}}\n⎕←+sum {v}\n"),
        script("double-nor", f"⎕←⊽{v}\n⎕←1 0 1 0⊽1 1 0 0\n⎕←⊽¯{n}.5\n"),
        script("scan-first", f"m←{rng.randint(2, 4)} {rng.randint(2, 4)}ρ{v}\n⎕←+⍀m\n⎕←×⍀m\n⎕←⌈⍀⌽m\n"),
    ]


def systems(rng: random.Random) -> list[dict]:
    """More of the system functions that few records use: `•ucs⁻`, `•edge`, `•special`,
    `•host "version"`, `•literal` and `•literal⁻`, `•src` and `•ex`."""
    text = word(rng)
    k = rng.randint(3, 8)
    return [
        script("ucs", f'c←•ucs "{text}"\n⎕←•ucs⁻ c\n⎕←"UTF-8" •ucs⁻ "{text}é"\n⎕←•ucs⁻ •ucs⁻ "{text}"\n'),
        script("edge", f"p←¯{rng.randint(2, 4)}+ι{k + 4}ₓ\n[c w r s]←•edge \"clamp\" \"wrap\" \"reflect\" \"symmetric\"\n"
                       f"⎕←{k}•edge p\n⎕←{k} c p\n⎕←{k} w p\n⎕←{k} r p\n⎕←{k} s p\nw\n⎕←0 s ι3\n"),
        script("special", f'[er ga]←•special "erfc" "gammaln"\n•prefs ["prec":6]\n⎕←er {rng.randint(1, 3)}.5\n'
                          f"⎕←ga {k}\nbeta←•special \"beta\"\n⎕←{rng.randint(2, 5)} beta {rng.randint(2, 5)}\nbeta\n"),
        script("host", f'v←•host "version"\n⎕←v\n⎕←≢v\n⎕←+/v="."\n'),
        script("literal", f's←•literal⁻ {rng.randint(2, 4)} {rng.randint(2, 4)}ρι{k}ₓ\n⎕←s\n⎕←•literal s\n'
                          f'⎕←•literal "[1 [{k} {k + 1}ₓ] ""{text}""]"\n'),
        script("src-ex", f"f←{{\n  ⍝ adds {k}\n  ω+{k}\n}}\n⎕←•src \"f\"\nx←{k}\n⎕←•nc \"x\"\n⎕←•ex \"x\"\n⎕←•nc \"x\"\n"
                         f"⎕←•ex \"x\" \"⎕x\"\n"),
    ]


def sandbox(rng: random.Random) -> list[dict]:
    """The file-read rule on each read path: a file elsewhere by an absolute path, a path that
    climbs out with `..`, links that lead out, and /proc, /sys and /dev, all refused; and a file
    here, one in a directory under here, and one through a link that stays inside, all read. The
    program file is given on the command line: a refused program prints nothing and ends with
    status 1, where a reader without the rule prints what the program prints."""
    secret = f"{word(rng)} {rng.randint(1000, 9999)}"
    module = f'msg←"{word(rng)}"\nn←{rng.randint(10, 99)}\n'
    shout = f'⎕←"{word(rng)} {rng.randint(100, 999)}"\n⎕←{rng.randint(2, 9)}×{rng.randint(2, 9)}\n'
    outside = {"secret.txt": secret + "\n", "mod.bpl": module, "prog.bpl": shout}
    links = {"esc.txt": f"{OUTSIDE}/secret.txt", "esc.bpl": f"{OUTSIDE}/mod.bpl", "run.bpl": f"{OUTSIDE}/prog.bpl",
             "abs.txt": "/etc/passwd", "info.txt": "data/info.txt", "m.bpl": "data/m.bpl", "p.bpl": "data/p.bpl"}
    inside = {"data/info.txt": f"{word(rng)} {word(rng)}\n", "data/m.bpl": module, "data/p.bpl": shout,
              "top.txt": f"{word(rng)} {rng.randint(10, 99)}\n", "here.bpl": f'k←{rng.randint(2, 9)}\nsquares←k×ι k\n'}
    # Paths of the kernel's trees that every machine has: /sys itself is a directory, which the
    # rule refuses before any read; the program file is also given a file under /sys.
    kernel = ("/proc/self/stat", "/sys", "/dev/null")

    def reads(name: str, text: str, **more) -> dict:
        return case("sandbox", f"sandbox:{name}", ["main.bpl"], dict(inside, **{"main.bpl": text}), links=links,
                    outside=outside, family=name, **more)

    def runs(name: str, program: str) -> dict:
        return case("sandbox", f"sandbox:{name}", [program], dict(inside), links=links, outside=outside, family=name)

    return [
        reads("nget-out", guarded('•nget "/etc/passwd"', f'•nget "{OUTSIDE}/secret.txt"',
                                  '•nget "data/../../bpl-outside/secret.txt"'), form="guarded"),
        reads("nget-link", guarded('•nget "esc.txt"', '•nget "abs.txt"', *(f'•nget "{path}"' for path in kernel)),
              form="guarded"),
        reads("load-out", guarded('•load "/etc/hosts"', f'•load "{OUTSIDE}/mod.bpl"', '•load "esc.bpl"',
                                  '•load "data/../../bpl-outside/mod.bpl"'), form="guarded"),
        reads("load-kernel", guarded(*(f'•load "{path}"' for path in kernel)), form="guarded"),
        reads("reads-inside", 'a←•nget "data/info.txt"\nb←•nget "info.txt"\n⎕←a≡b\n⎕←⌽a\n⎕←≢•nget "top.txt"\n'
                              '[msg: n:]←•load "m.bpl"\n⎕←msg n\nr←•load "data/m.bpl"\n⎕←r.n×(•load "here.bpl").k\n'),
        runs("program-out", f"{OUTSIDE}/prog.bpl"),
        # The same program by its absolute path: the runner's working directory is /tmp/bpl-run whenever answers
        # are recorded or graded, so the directory beside it is /tmp/bpl-outside.
        runs("program-abs", "/tmp/bpl-outside/prog.bpl"),
        runs("program-link", "run.bpl"),
        runs("program-proc", "/proc/self/stat"),
        runs("program-sys", "/sys/devices/system/cpu/online"),
        runs("program-dev", "/dev/null"),
        runs("program-inside", "data/p.bpl"),
        runs("program-staying", "p.bpl"),
    ]


# What the instruction puts out of scope ("Out of scope: ..."), as documented items: random numbers,
# the clock, drawing, the functions it names, the settings that describe upstream's engine (which
# `•prefs ⍬` still reports), and the REPL's own commands. Everything else documented is in scope.
OUT_OF_SCOPE = frozenset({
    "glyph ¿", "glyph ⇄", "system •rand", "system •distribution", "system •time", "system •date", "system •date⁻",
    "system •delay", "system •plot", "system •svg", "system •image", "system •image⁻", "system •canvas", "system •fetch",
    "system •readdir", "system •metadata", "system •copy", "system •rename", "system •remove", "system •mkdir",
    "system •hash", "system •deflate", "system •deflate⁻", "system •mime", "system •js", "system •storage",
    "system •memory", "system •explain", "system •index", "prefs fusion", "prefs threads", "prefs seed",
})
SYNTAX = {"⍝": "comment", '"': "string", "'": "char"}  # glyph pages whose glyph is a token of its own kind


def code_of(case: dict) -> list[str]:
    """The code a case gives the interpreter: its files but library ones, the code after -e, a
    program or lines on standard input, and the code and functions of its worker requests."""
    texts = [text for path, text in sorted(case["files"].items()) if not path.startswith("lib/")]
    argv, stdin = case["argv"], case.get("stdin") or ""
    if argv[:1] == ["-e"] and len(argv) > 1:
        texts.append(argv[1])
    if argv[:1] == ["--worker"]:
        for line in stdin.splitlines():
            try:
                request = json.loads(line)
            except ValueError:
                continue
            if isinstance(request, dict):
                texts += [request[key] for key in ("code", "call") if isinstance(request.get(key), str)]
    elif stdin and (not argv or argv[0] == "-"):
        texts.append(stdin)
    return texts


def documented_items(pages: dict[str, str]) -> list[str]:
    """Every item of the documentation that the instruction puts in scope: each glyph page's glyph
    (or glyphs, or syntax), each system page's function and the inverse form it documents, each `$`
    name, each `•prefs` setting and `•prefs ⍬`, the `•host` names "args" and "version", the worker's
    `code`, `call` and `bindings` requests, `]display`, `]dissect` and `⎕←`, less OUT_OF_SCOPE.

    Args:
        pages: The documentation, as bpl_text.documentation gives it.

    Returns:
        The items' names, sorted.
    """
    found = set()
    for name, text in pages.items():
        lines = text.splitlines()
        if not lines:
            continue
        if name.startswith("glyphs/"):
            found |= {f"glyph {glyph}" for glyph in re.findall(r"`([^`]+)`", lines[0]) if glyph != "•"}
        elif name.startswith("system/"):
            for function in sorted(set(re.findall(r"•[A-Za-z]+", lines[0]))):
                found.add(f"system {function}")
                if f"`{function}⁻" in text:
                    found.add(f"system {function}⁻")
            found |= {f"constant {dollar}" for dollar in re.findall(r"`(\$[a-z])`", text) if name == "system/constants.md"}
            if name == "system/prefs.md":
                found |= {f"prefs {key}" for key in re.findall(r"^\| `([a-z_]+)` \|", text, re.M)} | {"prefs ⍬"}
    found |= {'host "args"', 'host "version"', "worker code", "worker call", "worker bindings", "magic ]display",
              "magic ]dissect", "output ⎕←"}
    return sorted(found - OUT_OF_SCOPE)


def read(case: dict) -> dict:
    """What `uses` reads of a case, once: its code (code_of) as one text and as tokens, and the keys
    of its worker requests."""
    texts = code_of(case)
    tokens = []
    for text in texts:
        try:
            tokens += bpl_text.tokenize(text)
        except Exception:  # noqa: BLE001 - a fragment that does not tokenize holds nothing to count
            continue
    keys = set()
    if case["argv"][:1] == ["--worker"]:
        for line in (case.get("stdin") or "").splitlines():
            try:
                request = json.loads(line)
            except ValueError:
                continue
            if isinstance(request, dict):
                keys |= set(request)
    return {"raw": "\n".join(texts), "tokens": tokens, "keys": keys}


def uses(case: dict, item: str, seen: dict | None = None) -> bool:
    """Whether a case's own code (code_of) uses a documented item: as a token where the item is a
    glyph, a system function or a `$` name, outside strings and comments. `seen` is read(case),
    where the caller has it."""
    seen = seen or read(case)
    kind, _, what = item.partition(" ")
    raw, tokens = seen["raw"], seen["tokens"]
    if kind == "worker":
        return what in seen["keys"]
    if kind in ("magic", "output"):
        return what in raw
    if kind == "prefs":
        return "•prefs" in raw and bool(re.search(r"•prefs\s*⍬" if what == "⍬" else rf'"{what}"\s*:', raw))
    if kind == "host":
        return bool(re.search(rf"•host\s*{re.escape(what)}", raw))
    if kind == "constant":
        return any(token.text == what for token in tokens if token.kind == "constant")
    if kind == "system":
        name, inverse = (what[:-1], True) if what.endswith("⁻") else (what, False)
        follows = tokens[1:] + [bpl_text.Token("space", "")]
        return any(a.kind == "system" and a.text.lower() == name.lower() and (not inverse or b.text == "⁻")
                   for a, b in zip(tokens, follows))
    if what in SYNTAX:
        return any(token.kind == SYNTAX[what] for token in tokens)
    if len(what) == 1:
        return any(token.text == what and (token.kind in ("glyph", "constant") or what in "⎕∞¯⍬") for token in tokens)
    return all(part in raw for part in what.split())


READ_PATHS = ("program", "•nget", "•load")
READ_KINDS = ("absolute", "climbs out", "link out", "/proc", "/sys", "/dev", "here", "subdirectory", "link inside")
READ = re.compile(r'(•nget|•load)\s*"((?:[^"]|"")*)"')


def read_items() -> list[str]:
    """The file-read rule's items: each read path (the program file, `•nget`, `•load`) for each kind
    of path (READ_KINDS: refused outside the working directory and under the kernel's trees, read
    here, in a directory under here and through a link that stays inside)."""
    return [f"read {path} {kind}" for path in READ_PATHS for kind in READ_KINDS]


def read_kind(case: dict, path: str, base: str = "") -> str | None:
    """The kind of path (READ_KINDS) a read of `path` makes, from a file in directory `base` of the
    working directory: a path that starts with ./ or ../ is relative to the file holding the code,
    another relative path to the working directory. None for standard input ("-")."""
    import posixpath  # noqa: PLC0415
    if path == "-":
        return None
    for tree in ("/proc", "/sys", "/dev"):
        if path == tree or path.startswith(tree + "/"):
            return tree
    if path.startswith("/"):
        return "absolute"
    joined = posixpath.normpath(posixpath.join(base, path) if path.startswith(("./", "../")) else path)
    if joined == ".." or joined.startswith("../"):
        return "climbs out"
    links = case.get("links") or {}
    if joined in links:
        target = links[joined]
        reached = target if target.startswith("/") else posixpath.normpath(posixpath.join(posixpath.dirname(joined), target))
        return "link out" if reached.startswith(("/", "..")) else "link inside"
    return "subdirectory" if "/" in joined else "here"


def reads(case: dict) -> set[str]:
    """The read items (read_items) a case exercises: its program file, given on the command line, and
    each `•nget` and `•load` of a literal path in its own files, its `-e` code and a program on
    standard input."""
    found = set()
    argv = case["argv"]
    if argv and not argv[0].startswith("-"):
        kind = read_kind(case, argv[0])
        found |= {f"read program {kind}"} if kind else set()
    sources = [(path, text) for path, text in case["files"].items() if not path.startswith("lib/")]
    if argv[:1] == ["-e"] and len(argv) > 1:
        sources.append(("", argv[1]))
    if argv[:1] == ["-"] and case.get("stdin"):
        sources.append(("", case["stdin"]))
    for path, text in sources:
        base = path.rsplit("/", 1)[0] if "/" in path else ""
        for function, target in READ.findall(text):
            kind = read_kind(case, target.replace('""', '"'), base)
            if kind:
                found.add(f"read {function} {kind}")
    return found


def missing(cases: list[dict], pages: dict[str, str]) -> list[str]:
    """The documented items in scope (documented_items), the forms the instruction names (`"-" •nput`,
    `•nget` of a file) and the file-read rule's items (read_items) that no case in `cases` uses."""
    seen = [read(case) for case in cases]
    absent = [item for item in documented_items(pages) if not any(uses(case, item, read_) for case, read_ in zip(cases, seen))]
    forms = {'"-" •nput': re.compile(r'"-"\s*•nput'), "•nget of a file": re.compile(r'•nget\s*"(?!-")')}
    absent += [form for form, pattern in forms.items() if not any(pattern.search(read_["raw"]) for read_ in seen)]
    exercised = set().union(*(reads(case) for case in cases)) if cases else set()
    return absent + [item for item in read_items() if item not in exercised]


def hanzi_aliases(pages: dict[str, str]) -> dict[str, str]:
    """Each glyph's Hanzi spelling(s), from its glyph page's "Hanzi:" note (monadic/dyadic where
    there are two), by glyph."""
    found = {}
    for name, text in pages.items():
        if name.startswith("glyphs/"):
            lines = text.splitlines()
            glyph = re.match(r"# `([^`]+)`", lines[0]) if lines else None
            spelled = re.search(r"Hanzi: `([^`]+)`", "\n".join(lines[:4]))
            if glyph and spelled:
                found[glyph[1]] = spelled[1]
    return found


def cases(seed: int, pages: dict[str, str]) -> list[dict]:
    """Every coverage and sandbox case, without ids, from a generator of their own seeded by the
    private case seed, so that adding them changes no other case."""
    rng = random.Random(f"coverage:{seed}")
    built = (nput(rng) + nget(rng) + path(rng) + uuid(rng) + normalize(rng) + element(rng) + xml(rng) + detach(rng)
             + prefs(rng, hanzi_aliases(pages)) + glyphs(rng) + systems(rng) + sandbox(rng))
    rng.shuffle(built)
    return built
