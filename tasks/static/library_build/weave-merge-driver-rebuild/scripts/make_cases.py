"""Generate candidate merge triples for the Weave rebuild: typed, family-tagged edits to synthetic modules.

Each recipe builds a base module, applies one edit per side, and tags the case with the family and
feature it is meant to exercise. Candidates are filtered later (stubs, determinism, the original's
own behaviour); this script only proposes. Output: a JSON list of cases. Deterministic per seed.
The seed and the output are private and never enter the public repository.

The Phase C recipes (after the earlier ones, so those keep their ids and output) emit groups: the
case where a rule applies and its near misses, which share one BASE and one path and carry the same
`pair` id. With --per-recipe K each of them yields about K cases per language.

Usage: python3 -I gen_cases.py --seed N --per-recipe K --layout L --out cases.json
"""

from __future__ import annotations

import argparse
import copy
import json
import random
from dataclasses import dataclass, field
from pathlib import Path

WORDS = [
    "alpha",
    "beta",
    "gamma",
    "delta",
    "sigma",
    "omega",
    "token",
    "cache",
    "queue",
    "batch",
    "shard",
    "index",
    "cursor",
    "ledger",
    "invoice",
    "order",
    "refund",
    "payment",
    "ticket",
    "session",
    "route",
    "header",
    "payload",
    "buffer",
    "window",
    "record",
    "report",
    "metric",
    "sample",
    "signal",
    "bucket",
    "region",
    "tenant",
    "quota",
    "limit",
    "budget",
    "backoff",
    "retry",
]
VERBS = [
    "load",
    "parse",
    "build",
    "fetch",
    "merge",
    "apply",
    "render",
    "encode",
    "decode",
    "resolve",
    "compute",
    "check",
    "update",
    "sync",
]


@dataclass
class Item:
    """One top-level definition: its kind, its name and its text lines (no trailing blank lines)."""

    kind: str
    name: str
    lines: list[str]


@dataclass
class Module:
    """A synthetic source file: a language, a header (imports or package), and ordered items."""

    lang: str
    header: list[str] = field(default_factory=list)
    items: list[Item] = field(default_factory=list)


def gap(lang: str) -> str:
    """The separator between top-level items: two blank lines in Python, one elsewhere."""
    return "\n\n\n" if lang == "py" else "\n\n"


def render(m: Module) -> str:
    """Render a module with uniform layout and a final newline."""
    blocks = []
    if m.header:
        blocks.append("\n".join(m.header))
    blocks.extend("\n".join(it.lines) for it in m.items)
    return gap(m.lang).join(blocks) + "\n"


def ident(rng: random.Random, lang: str, used: set[str]) -> str:
    """A fresh identifier in the language's style, unique within `used`."""
    while True:
        verb, noun, noun2 = rng.choice(VERBS), rng.choice(WORDS), rng.choice(WORDS)
        name = (
            f"{verb}_{noun}_{noun2}"
            if lang == "py"
            else f"{verb}{noun.capitalize()}{noun2.capitalize()}"
        )
        if name not in used:
            used.add(name)
            return name


def func(
    rng: random.Random, lang: str, name: str, extra: list[str] | None = None
) -> Item:
    """A plain function whose body is unique to its name."""
    k, n = rng.randint(2, 40), rng.randint(41, 90)
    tag = name[-6:]
    extra = extra or []
    if lang == "py":
        body = [
            f"    value = helper(arg, {k})",
            f'    note = "{tag}"',
            f"    if value > {n}:",
            f"        return value - {k}",
            *extra,
            "    return value",
        ]
        return Item("func", name, [f"def {name}(arg):", *body])
    if lang == "ts":
        body = [
            f"  const value = helper(arg, {k});",
            f'  const note = "{tag}";',
            f"  if (value > {n}) {{",
            f"    return value - {k};",
            "  }",
            *extra,
            "  return value;",
        ]
        return Item(
            "func",
            name,
            [f"export function {name}(arg: number): number {{", *body, "}"],
        )
    body = [
        f"\tvalue := helper(arg, {k})",
        f'\tnote := "{tag}"',
        "\t_ = note",
        f"\tif value > {n} {{",
        f"\t\treturn value - {k}",
        "\t}",
        *extra,
        "\treturn value",
    ]
    return Item("func", name, [f"func {name}(arg int) int {{", *body, "}"])


def header(lang: str, imports: list[str]) -> list[str]:
    """The file header: Python imports, TS imports, or a Go package clause and import block."""
    if lang == "py":
        return [f"import {i}" for i in imports]
    if lang == "ts":
        return [f'import {{ {i} }} from "./{i}";' for i in imports]
    return ["package service", "", "import (", *[f'\t"{i}"' for i in imports], ")"]


IMPORT_POOL = {
    "py": ["os", "json", "re", "time", "math"],
    "ts": ["fmt", "net", "path", "url", "zlib"],
    "go": ["fmt", "strings", "sort", "strconv", "errors"],
}
EXTRA_IMPORTS = {
    "py": ["typing", "pathlib", "random", "shutil", "uuid", "glob"],
    "ts": ["crypto", "stream", "events", "buffer", "util", "tls"],
    "go": ["io", "bytes", "regexp", "context", "hash", "unicode"],
}


def module(rng: random.Random, lang: str, nfuncs: int, used: set[str]) -> Module:
    """A module with three imports and `nfuncs` functions."""
    imports = sorted(rng.sample(IMPORT_POOL[lang], 3))
    return Module(
        lang,
        header(lang, imports),
        [func(rng, lang, ident(rng, lang, used)) for _ in range(nfuncs)],
    )


def edit_line(rng: random.Random, it: Item, idx: int) -> None:
    """Change one body line of a function in place, keeping it valid."""
    line = it.lines[idx]
    if "helper(arg" in line:
        it.lines[idx] = line.replace(
            "helper(arg", f"helper(arg + {rng.randint(1, 9)}", 1
        )
    elif "note" in line and '"' in line:
        it.lines[idx] = line.replace('"', '"v2-', 1)
    elif "return value" in line:
        it.lines[idx] = line.replace(
            "return value", f"return value * {rng.randint(2, 9)}", 1
        )
    else:
        it.lines[idx] = line + (" " if line.endswith(";") else "")


def path_for(rng: random.Random, lang: str, test: bool = False) -> str:
    """A realistic repository path for the language."""
    stem = f"{rng.choice(WORDS)}_{rng.choice(WORDS)}"
    if lang == "py":
        return f"src/{rng.choice(WORDS)}/{'test_' if test else ''}{stem}.py"
    if lang == "ts":
        return f"src/{rng.choice(WORDS)}/{stem.replace('_', '-')}{'.test' if test else ''}.ts"
    if lang == "go":
        return f"internal/{rng.choice(WORDS)}/{stem}{'_test' if test else ''}.go"
    return f"config/{stem}.{lang}"


def sides(base: Module) -> tuple[Module, Module]:
    """Two independent copies of the base, for ours and theirs."""
    return copy.deepcopy(base), copy.deepcopy(base)


# ----------------------------------------------------------------------------- F1-F5


def r_insert_vs_header_edit(rng, lang):
    """F1: ours adds a function after f_k; theirs edits f_{k+1}'s first body line. Rules: [PLACE-5], [LAY-1]."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(3, 6), used)
    k = rng.randrange(len(base.items) - 1)
    ours, theirs = sides(base)
    ours.items.insert(k + 1, func(rng, lang, ident(rng, lang, used)))
    edit_line(rng, theirs.items[k + 1], 1)
    return base, ours, theirs, "F1", "disjoint.insert_next_to_edit"


def r_delete_vs_next_edit(rng, lang):
    """F1: ours deletes f_k; theirs edits f_{k+1}'s first body line. Rules: [CELL-9], [LAY-1]."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(3, 6), used)
    k = rng.randrange(len(base.items) - 1)
    ours, theirs = sides(base)
    del ours.items[k]
    edit_line(rng, theirs.items[k + 1], 1)
    return base, ours, theirs, "F1", "disjoint.delete_next_to_edit"


def r_both_add_same_anchor(rng, lang):
    """F2: both sides add a different function after the same anchor. Rules: [PLACE-5], [PLACE-6], [PLACE-7]."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(2, 5), used)
    k = rng.randrange(len(base.items))
    ours, theirs = sides(base)
    ours.items.insert(k + 1, func(rng, lang, ident(rng, lang, used)))
    theirs.items.insert(k + 1, func(rng, lang, ident(rng, lang, used)))
    return base, ours, theirs, "F2", "placement.same_anchor"


def r_both_add_two_vs_one(rng, lang):
    """F2: ours adds two functions after one anchor, theirs one. Rules: [PLACE-6], [PLACE-7]."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(2, 4), used)
    k = rng.randrange(len(base.items))
    ours, theirs = sides(base)
    ours.items[k + 1 : k + 1] = [
        func(rng, lang, ident(rng, lang, used)) for _ in range(2)
    ]
    theirs.items.insert(k + 1, func(rng, lang, ident(rng, lang, used)))
    return base, ours, theirs, "F2", "placement.input_order"


def r_reorder_vs_edit(rng, lang):
    """F2: ours swaps two neighbours; theirs edits the first of them. Rules: [PLACE-1], [PLACE-2]."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(3, 5), used)
    k = rng.randrange(len(base.items) - 1)
    ours, theirs = sides(base)
    ours.items[k], ours.items[k + 1] = ours.items[k + 1], ours.items[k]
    edit_line(rng, theirs.items[k], 1)
    return base, ours, theirs, "F2", "placement.one_side_reorder"


def rename_item(it: Item, new: str) -> None:
    """Rename a function in its header line."""
    it.lines[0] = it.lines[0].replace(f" {it.name}(", f" {new}(", 1)
    it.name = new


def r_rename_vs_edit(rng, lang):
    """F3: ours renames f (same body); theirs edits f's first body line."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(2, 5), used)
    k = rng.randrange(len(base.items))
    ours, theirs = sides(base)
    rename_item(ours.items[k], ident(rng, lang, used))
    edit_line(rng, theirs.items[k], 1)
    return base, ours, theirs, "F3", "rename.identical_body"


def r_rename_edit_vs_edit(rng, lang):
    """F3: ours renames f and edits its last line; theirs edits f's first body line. Rules: [MATCH-3], [MATCH-9], [CELL-12]."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(2, 5), used)
    k = rng.randrange(len(base.items))
    ours, theirs = sides(base)
    rename_item(ours.items[k], ident(rng, lang, used))
    edit_line(rng, ours.items[k], len(ours.items[k].lines) - (2 if lang != "py" else 1))
    edit_line(rng, theirs.items[k], 1)
    return base, ours, theirs, "F3", "rename.edited_body"


def r_rename_vs_rewrite(rng, lang):
    """F3 near-miss: ours renames f and rewrites its whole body (far below the thresholds: not a rename). Rules: [MATCH-3], [MATCH-9]."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(2, 5), used)
    k = rng.randrange(len(base.items))
    ours, theirs = sides(base)
    new = ident(rng, lang, used)
    fresh = func(rng, lang, new)
    body = {
        "py": ["    total = sum(range(arg))", "    return total * 3"],
        "ts": [
            "  let total = 0;",
            "  for (let i = 0; i < arg; i++) total += i;",
            "  return total * 3;",
        ],
        "go": [
            "\ttotal := 0",
            "\tfor i := 0; i < arg; i++ {",
            "\t\ttotal += i",
            "\t}",
            "\treturn total * 3",
        ],
    }[lang]
    fresh.lines = [fresh.lines[0], *body] + ([] if lang == "py" else ["}"])
    ours.items[k] = fresh
    edit_line(rng, theirs.items[k], 1)
    return base, ours, theirs, "F3", "rename.below_threshold"


def r_both_edit_adjacent(rng, lang):
    """F4: both sides edit neighbouring lines of one function; half also add at one anchor elsewhere. Rules: [SAME-2], [ELEM-1]."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(2, 5), used)
    k = rng.randrange(len(base.items))
    ours, theirs = sides(base)
    edit_line(rng, ours.items[k], 1)
    edit_line(rng, theirs.items[k], 2)
    feature = "same_entity.adjacent_lines"
    if rng.random() < 0.5 and len(base.items) > 1:
        j = (k + 1) % len(base.items)
        ours.items.insert(j + 1, func(rng, lang, ident(rng, lang, used)))
        theirs.items.insert(j + 1, func(rng, lang, ident(rng, lang, used)))
        feature = "same_entity.adjacent_lines_plus_placement"
    return base, ours, theirs, "F4", feature


def r_both_edit_same_line(rng, lang):
    """F4: both sides change one line of one function differently; ours also edits another function."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(2, 5), used)
    k = rng.randrange(len(base.items))
    ours, theirs = sides(base)
    edit_line(rng, ours.items[k], 1)
    theirs.items[k].lines[1] = (
        theirs.items[k].lines[1].replace("helper(arg", "helper(arg - 1", 1)
    )
    j = (k + 1) % len(base.items)
    if j != k:
        edit_line(rng, ours.items[j], 2)
    return base, ours, theirs, "F4", "same_entity.same_line"


def cls(rng: random.Random, lang: str, name: str, methods: list[str]) -> Item:
    """A class (Python, TS) with the given methods."""
    lines: list[str] = []
    if lang == "py":
        lines.append(f"class {name}:")
        for i, m in enumerate(methods):
            if i:
                lines.append("")
            lines += [
                f"    def {m}(self, arg):",
                f"        out = arg + {(sum(map(ord, m)) % 97) + 1}",
                "        return out",
            ]
        return Item("class", name, lines)
    lines.append(f"export class {name} {{")
    for i, m in enumerate(methods):
        if i:
            lines.append("")
        lines += [
            f"  {m}(arg: number): number {{",
            f"    const out = arg + {(sum(map(ord, m)) % 97) + 1};",
            "    return out;",
            "  }",
        ]
    lines.append("}")
    return Item("class", name, lines)


def class_module(rng, lang):
    """A module with one class among a few functions."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(1, 3), used)
    cname = "".join(w.capitalize() for w in rng.sample(WORDS, 2))
    methods = [ident(rng, lang, used) for _ in range(rng.randint(2, 4))]
    pos = rng.randrange(len(base.items) + 1)
    base.items.insert(pos, cls(rng, lang, cname, methods))
    return base, pos, cname, methods, used


def r_class_both_add_methods(rng, lang):
    """F5: both sides add a different method at the end of one class. Rules: [SAME-5], [SAME-7], [SAME-8]."""
    base, pos, cname, methods, used = class_module(rng, lang)
    ours, theirs = sides(base)
    ours.items[pos] = cls(rng, lang, cname, methods + [ident(rng, lang, used)])
    theirs.items[pos] = cls(rng, lang, cname, methods + [ident(rng, lang, used)])
    return base, ours, theirs, "F5", "container.both_add_members"


def r_class_add_vs_edit_next(rng, lang):
    """F5: ours adds a method after m_i; theirs edits m_{i+1}'s body."""
    base, pos, cname, methods, used = class_module(rng, lang)
    i = rng.randrange(len(methods) - 1)
    ours, theirs = sides(base)
    ours.items[pos] = cls(
        rng, lang, cname, methods[: i + 1] + [ident(rng, lang, used)] + methods[i + 1 :]
    )
    lines = theirs.items[pos].lines
    target = next(j for j, ln in enumerate(lines) if f" {methods[i + 1]}(" in ln) + 1
    lines[target] = lines[target].replace("arg + ", "arg * 2 + ", 1)
    return base, ours, theirs, "F5", "container.add_next_to_edit"


# ----------------------------------------------------------------------------- F6, F7: collections, imports


def py_dict_func(name: str, keys: list[tuple[str, int]]) -> Item:
    """A Python function holding a dict literal."""
    return Item(
        "func",
        name,
        [
            f"def {name}():",
            "    table = {",
            *[f'        "{k}": {v},' for k, v in keys],
            "    }",
            "    return table",
        ],
    )


def ts_obj_func(name: str, keys: list[tuple[str, int]]) -> Item:
    """A TS function holding an object literal."""
    return Item(
        "func",
        name,
        [
            f"export function {name}() {{",
            "  const table = {",
            *[f"    {k}: {v}," for k, v in keys],
            "  };",
            "  return table;",
            "}",
        ],
    )


def go_map_func(name: str, keys: list[tuple[str, int]]) -> Item:
    """A Go function holding a map literal."""
    return Item(
        "func",
        name,
        [
            f"func {name}() map[string]int {{",
            "\ttable := map[string]int{",
            *[f'\t\t"{k}": {v},' for k, v in keys],
            "\t}",
            "\treturn table",
            "}",
        ],
    )


COLLECTION = {"py": py_dict_func, "ts": ts_obj_func, "go": go_map_func}


def keyed(rng: random.Random, n: int) -> list[tuple[str, int]]:
    """Distinct keys with small values."""
    return [(k, rng.randint(1, 99)) for k in rng.sample(WORDS, n)]


def with_collection(rng, lang, keys):
    """A module with one collection-holding function at a random place."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(1, 3), used)
    name = ident(rng, lang, used)
    pos = rng.randrange(len(base.items) + 1)
    base.items.insert(pos, COLLECTION[lang](name, keys))
    return base, pos, name


def r_collection_both_add_same_point(rng, lang):
    """F6: both sides add a different key at the same point of one literal. Rules: [ELEM-1], [ELEM-3], [ELEM-6], [ELEM-10]."""
    keys = keyed(rng, 5)
    base, pos, name = with_collection(rng, lang, keys)
    a, b = rng.sample([w for w in WORDS if w not in dict(keys)], 2)
    at = rng.randrange(len(keys) + 1)
    ours, theirs = sides(base)
    ours.items[pos] = COLLECTION[lang](name, keys[:at] + [(a, 7)] + keys[at:])
    theirs.items[pos] = COLLECTION[lang](name, keys[:at] + [(b, 8)] + keys[at:])
    return base, ours, theirs, "F6", "elements.union_keys"


def r_collection_same_key_two_values(rng, lang):
    """F6: both sides add the same key with different values at one point."""
    keys = keyed(rng, 5)
    base, pos, name = with_collection(rng, lang, keys)
    a = rng.choice([w for w in WORDS if w not in dict(keys)])
    at = rng.randrange(len(keys) + 1)
    ours, theirs = sides(base)
    ours.items[pos] = COLLECTION[lang](name, keys[:at] + [(a, 7)] + keys[at:])
    theirs.items[pos] = COLLECTION[lang](name, keys[:at] + [(a, 8)] + keys[at:])
    return base, ours, theirs, "F6", "elements.refuse_same_key"


def switch_func(lang: str, name: str, cases: list[int]) -> Item:
    """A tagged switch (Go, TS) or a match (Python) with one return per case."""
    if lang == "go":
        body = [x for c in cases for x in (f"\tcase {c}:", f'\t\treturn "c{c}"')]
        return Item(
            "func",
            name,
            [
                f"func {name}(code int) string {{",
                "\tswitch code {",
                *body,
                "\tdefault:",
                '\t\treturn "other"',
                "\t}",
                "}",
            ],
        )
    if lang == "ts":
        body = [x for c in cases for x in (f"    case {c}:", f'      return "c{c}";')]
        return Item(
            "func",
            name,
            [
                f"export function {name}(code: number): string {{",
                "  switch (code) {",
                *body,
                "    default:",
                '      return "other";',
                "  }",
                "}",
            ],
        )
    body = [
        x for c in cases for x in (f"        case {c}:", f'            return "c{c}"')
    ]
    return Item(
        "func",
        name,
        [
            f"def {name}(code):",
            "    match code:",
            *body,
            "        case _:",
            '            return "other"',
        ],
    )


def with_switch(rng, lang, cases):
    """A module with one switch-holding function."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(1, 3), used)
    name = ident(rng, lang, used)
    pos = rng.randrange(len(base.items) + 1)
    base.items.insert(pos, switch_func(lang, name, cases))
    return base, pos, name


def r_switch_both_add_same_point(rng, lang):
    """F6: both sides add a different case at the same point of one switch. Rules: [ELEM-1], [ELEM-3], [ELEM-11]."""
    cases = sorted(rng.sample(range(1, 40), 5))
    base, pos, name = with_switch(rng, lang, cases)
    a, b = rng.sample(range(40, 80), 2)
    at = rng.randrange(len(cases) + 1)
    ours, theirs = sides(base)
    ours.items[pos] = switch_func(lang, name, cases[:at] + [a] + cases[at:])
    theirs.items[pos] = switch_func(lang, name, cases[:at] + [b] + cases[at:])
    return base, ours, theirs, "F6", "elements.union_cases"


def add_import(m: Module, lang: str, name: str, first: bool = False) -> None:
    """Add one import to a module's header, at the start or the end of the import list."""
    if lang == "go":
        at = m.header.index("import (") + 1 if first else m.header.index(")")
        m.header.insert(at, f'\t"{name}"')
        return
    line = f"import {name}" if lang == "py" else f'import {{ {name} }} from "./{name}";'
    m.header.insert(0 if first else len(m.header), line)


def r_imports_both_add(rng, lang):
    """F7: both sides add a different import at the end of the import block. Rules: [IMP-2], [IMP-5]."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(2, 4), used)
    a, b = rng.sample(EXTRA_IMPORTS[lang], 2)
    ours, theirs = sides(base)
    add_import(ours, lang, a)
    add_import(theirs, lang, b)
    return base, ours, theirs, "F7", "imports.union"


def r_decorators_both_add(rng, lang):
    """F7: both sides add a different decorator to one Python function."""
    used: set[str] = set()
    base = module(rng, "py", rng.randint(2, 4), used)
    k = rng.randrange(len(base.items))
    ours, theirs = sides(base)
    ours.items[k].lines.insert(0, "@cached")
    theirs.items[k].lines.insert(0, "@traced")
    return base, ours, theirs, "F7", "decorators.both_add"


# ----------------------------------------------------------------------------- F8: refusals and duals


def r_gate_dup_case(rng, lang):
    """F8 refusal: both sides add the same case label at distant points of one switch. Rules: [GATE-KEYS], [GATE-3], [GATE-5]."""
    cases = sorted(rng.sample(range(1, 40), 6))
    base, pos, name = with_switch(rng, lang, cases)
    new = rng.choice(range(40, 80))
    ours, theirs = sides(base)
    ours.items[pos] = switch_func(lang, name, cases[:1] + [new] + cases[1:])
    theirs.items[pos] = switch_func(lang, name, cases[:5] + [new] + cases[5:])
    return base, ours, theirs, "F8", "gate.keys_case_label"


def r_gate_dual_cases(rng, lang):
    """F8 accept-dual: both sides add different case labels at one point. Rules: [GATE-KEYS], [ELEM-11]."""
    base, ours, theirs, _, _ = r_switch_both_add_same_point(rng, lang)
    return base, ours, theirs, "F8", "gate.dual_case_labels"


def r_gate_dup_key(rng, lang):
    """F8 refusal: both sides add the same key at distant points of one literal. Rules: [GATE-KEYS], [GATE-3], [GATE-5]."""
    keys = keyed(rng, 6)
    base, pos, name = with_collection(rng, lang, keys)
    a = rng.choice([w for w in WORDS if w not in dict(keys)])
    ours, theirs = sides(base)
    ours.items[pos] = COLLECTION[lang](name, keys[:1] + [(a, 7)] + keys[1:])
    theirs.items[pos] = COLLECTION[lang](name, keys[:5] + [(a, 7)] + keys[5:])
    return base, ours, theirs, "F8", "gate.keys_literal"


def r_gate_dual_keys(rng, lang):
    """F8 accept-dual: both sides add different keys at one point. Rules: [GATE-KEYS], [ELEM-6]."""
    base, ours, theirs, _, _ = r_collection_both_add_same_point(rng, lang)
    return base, ours, theirs, "F8", "gate.dual_literal_keys"


def binding(lang: str, name: str, value: int) -> Item:
    """A top-level variable binding."""
    if lang == "py":
        return Item("const", name, [f"{name} = {value}"])
    if lang == "ts":
        return Item("const", name, [f"export const {name} = {value};"])
    return Item("const", name, [f"var {name} = {value}"])


def r_gate_dup_name(rng, lang):
    """F8 refusal: ours adds a function NAME at the top, theirs a variable NAME at the bottom. Rules: [GATE-BIND], [GATE-3], [GATE-5]."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(4, 6), used)
    name = ident(rng, lang, used)
    ours, theirs = sides(base)
    ours.items.insert(0, func(rng, lang, name))
    theirs.items.append(binding(lang, name, rng.randint(1, 9)))
    return base, ours, theirs, "F8", "gate.bindings_name"


def r_gate_dual_names(rng, lang):
    """F8 accept-dual: a function and a variable with different names added after one anchor. Rules: [GATE-BIND]."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(3, 5), used)
    k = rng.randrange(len(base.items))
    ours, theirs = sides(base)
    ours.items.insert(k + 1, func(rng, lang, ident(rng, lang, used)))
    theirs.items.insert(k + 1, binding(lang, ident(rng, lang, used), rng.randint(1, 9)))
    return base, ours, theirs, "F8", "gate.dual_names"


def r_gate_dup_import(rng, lang):
    """F8 refusal: both sides add the same import, one at the start of the block, one at the end. Rules: [GATE-BIND], [GATE-3], [GATE-5]."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(2, 4), used)
    a, *rest = rng.sample(EXTRA_IMPORTS[lang], 3)
    for extra in rest:
        add_import(base, lang, extra)
    ours, theirs = sides(base)
    add_import(ours, lang, a, first=True)
    add_import(theirs, lang, a)
    return base, ours, theirs, "F8", "gate.bindings_import"


def r_gate_dangling(rng, lang):
    """F8 refusal: ours removes an import and its only use; theirs adds a new use far away. Rules: [GATE-DANGLING], [GATE-3], [GATE-5]."""
    used: set[str] = set()
    mod = {"py": "json", "ts": "path", "go": "strings"}[lang]
    call = {"py": "json.dumps(arg)", "ts": "path(arg)", "go": 'strings.ToUpper("x")'}[
        lang
    ]
    use_line = {
        "py": f"    encoded = {call}",
        "ts": f"  const encoded = {call};",
        "go": f"\t_ = {call}",
    }[lang]
    base = module(rng, lang, rng.randint(4, 6), used)
    if not any(mod in h for h in base.header):
        add_import(base, lang, mod)
    base.items[0] = func(rng, lang, base.items[0].name, [use_line])
    ours, theirs = sides(base)
    ours.header = [h for h in ours.header if mod not in h]
    ours.items[0].lines = [ln for ln in ours.items[0].lines if ln != use_line]
    theirs.items.append(func(rng, lang, ident(rng, lang, used), [use_line]))
    return base, ours, theirs, "F8", "gate.dangling_name"


def r_gate_dual_imports(rng, lang):
    """F8 accept-dual: different imports added at one point. Rules: [GATE-DANGLING], [GATE-REVIVED], [IMP-8]."""
    base, ours, theirs, _, _ = r_imports_both_add(rng, lang)
    return base, ours, theirs, "F8", "gate.dual_imports"


def iota_block(names: list[str]) -> Item:
    """A Go iota constant block with its type."""
    return Item(
        "const",
        "iota",
        [
            "type State int",
            "",
            "const (",
            f"\t{names[0]} State = iota",
            *[f"\t{n}" for n in names[1:]],
            ")",
        ],
    )


def state_names(
    rng: random.Random, n: int, avoid: list[str] | None = None
) -> list[str]:
    """Distinct constant names for an iota block."""
    avoid = avoid or []
    pool = [w for w in WORDS if "State" + w.capitalize() not in avoid]
    return ["State" + w.capitalize() for w in rng.sample(pool, n)]


def r_gate_iota(rng, lang):
    """F8 refusal (Go): both sides insert a constant ahead of later ones, at distant points. Rules: [GATE-IOTA], [GATE-3], [GATE-5]."""
    used: set[str] = set()
    base = module(rng, "go", rng.randint(1, 3), used)
    names = state_names(rng, 6)
    base.items.insert(0, iota_block(names))
    a, b = state_names(rng, 2, names)
    ours, theirs = sides(base)
    ours.items[0] = iota_block(names[:1] + [a] + names[1:])
    theirs.items[0] = iota_block(names[:4] + [b] + names[4:])
    return base, ours, theirs, "F8", "gate.iota"


def r_gate_dual_iota(rng, lang):
    """F8 accept-dual (Go): both sides append after the last constant of an iota block."""
    used: set[str] = set()
    base = module(rng, "go", rng.randint(1, 3), used)
    names = state_names(rng, 5)
    base.items.insert(0, iota_block(names))
    a, b = state_names(rng, 2, names)
    ours, theirs = sides(base)
    ours.items[0] = iota_block(names + [a])
    theirs.items[0] = iota_block(names + [b])
    return base, ours, theirs, "F8", "gate.dual_iota"


def r_gate_dup_line(rng, lang):
    """F8 refusal: both sides add the same statement at distant points of one function."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(2, 4), used)
    k = rng.randrange(len(base.items))
    stmt = {
        "py": '    audit("enter")',
        "ts": '  audit("enter");',
        "go": '\taudit("enter")',
    }[lang]
    ours, theirs = sides(base)
    ours.items[k].lines.insert(1, stmt)
    theirs.items[k].lines.insert(
        len(theirs.items[k].lines) - (1 if lang == "py" else 2), stmt
    )
    return base, ours, theirs, "F8", "gate.lines_restated"


# ----------------------------------------------------------------------------- F1 routing sub-family


def comment(lang: str, text: str) -> str:
    """A whole-line comment in the language."""
    return f"# {text}" if lang == "py" else f"// {text}"


def padded(rng, lang, used, nbytes: int) -> Module:
    """A module whose text before its last function is at least `nbytes` long."""
    m = module(rng, lang, 3, used)
    while len(render(m)) < nbytes:
        m.items.insert(0, func(rng, lang, ident(rng, lang, used)))
    return m


def r_route_nul_between_git_and_driver(rng, lang):
    """F1 routing: a NUL byte at offset 8,001-8,191 of ours: the driver exits 2; git still merges. Rules: [CLI-7]."""
    used: set[str] = set()
    base = padded(rng, lang, used, 8300)
    ours, theirs = sides(base)
    edit_line(rng, theirs.items[-1], 1)
    text = render(ours)
    at = rng.randint(8010, 8180)
    cut = text.rfind("\n", 0, at) + 1
    ours_text = text[:cut] + comment(lang, "marker \x00 byte") + "\n" + text[cut:]
    return render(base), ours_text, render(theirs), "F1", "routing.binary_first_8192"


def r_route_nul_after_8192(rng, lang):
    """F1 routing dual: a NUL byte after offset 8,192 does not make the file binary. Rules: [CLI-7]."""
    used: set[str] = set()
    base = padded(rng, lang, used, 9000)
    k = len(base.items) - 2
    ours, theirs = sides(base)
    ours.items.insert(
        k + 1,
        func(rng, lang, ident(rng, lang, used), [comment(lang, "late \x00 byte")]),
    )
    edit_line(rng, theirs.items[k + 1], 1)
    return render(base), render(ours), render(theirs), "F1", "routing.nul_after_8192"


def r_route_not_utf8(rng, lang):
    """F1 routing: ours carries one byte that is not UTF-8 (in a comment): status 2. Rules: [CLI-6]."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(2, 4), used)
    ours, theirs = sides(base)
    ours.items[0].lines.insert(
        1,
        ("    " if lang == "py" else "  " if lang == "ts" else "\t")
        + comment(lang, "caf\udce9"),
    )
    edit_line(rng, theirs.items[0], 2)
    return render(base), render(ours), render(theirs), "F1", "routing.not_utf8"


def r_route_markers_in_theirs(rng, lang):
    """F1 routing: theirs already carries both marker strings: it is written back, status 1. Rules: [ROUTE-2], [BOX-7]."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(2, 4), used)
    ours, theirs = sides(base)
    edit_line(rng, ours.items[0], 1)
    theirs.items[-1].lines.insert(
        1,
        ("    " if lang == "py" else "  " if lang == "ts" else "\t")
        + comment(lang, "<<<<<<< ours >>>>>>> theirs"),
    )
    return render(base), render(ours), render(theirs), "F1", "routing.markers_in_input"


# ----------------------------------------------------------------------------- F9: rules that settle conflicts


def r_rule_subsumed_edit(rng, lang):
    """F9 (D1): both sides make the same change to one line; theirs also changes the next line."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(2, 5), used)
    k = rng.randrange(len(base.items))
    ours, theirs = sides(base)
    bump = rng.randint(1, 9)
    for side in (ours, theirs):
        side.items[k].lines[1] = (
            side.items[k].lines[1].replace("helper(arg", f"helper(arg + {bump}", 1)
        )
    edit_line(rng, theirs.items[k], 2)
    return base, ours, theirs, "F9", "rules.subsumption"


def r_rule_layout_only_side(rng, lang):
    """F9 (D6, Python): ours re-indents one function's body (layout only); theirs edits a line in it. Rules: [RULE-D6], [RULE-LAYOUT]."""
    used: set[str] = set()
    base = module(rng, "py", rng.randint(2, 5), used)
    k = rng.randrange(len(base.items))
    ours, theirs = sides(base)
    ours.items[k].lines = [
        ln.replace("    ", "  ") if ln.startswith("    ") else ln
        for ln in ours.items[k].lines
    ]
    edit_line(rng, theirs.items[k], 1)
    return base, ours, theirs, "F9", "rules.layout_only_side"


# ----------------------------------------------------------------------------- data formats


def json_text(obj: dict) -> str:
    """JSON with two-space indentation and a final newline."""
    return json.dumps(obj, indent=2) + "\n"


def toml_text(tables: dict[str, list[tuple[str, int]]]) -> str:
    """A flat TOML document of tables with integer values."""
    out: list[str] = []
    for t, kv in tables.items():
        if out:
            out.append("")
        out.append(f"[{t}]")
        out += [f"{k} = {v}" for k, v in kv]
    return "\n".join(out) + "\n"


def data_doc(lang: str, kv: list[tuple[str, int]]) -> str:
    """One object or table of keys inside a small document."""
    if lang == "json":
        return json_text({"service": {"name": "api", "limits": dict(kv)}, "version": 3})
    return toml_text({"service": [("port", 80)], "limits": kv})


def r_data_both_add_same_point(rng, lang):
    """F10: both sides add a different key at one point of one object or table. Rules: [DATA-6], [RULE-DATA-UNION]."""
    keys = keyed(rng, 5)
    a, b = rng.sample([w for w in WORDS if w not in dict(keys)], 2)
    at = rng.randrange(1, len(keys))
    return (
        data_doc(lang, keys),
        data_doc(lang, keys[:at] + [(a, 7)] + keys[at:]),
        data_doc(lang, keys[:at] + [(b, 8)] + keys[at:]),
        "F10",
        "data.union_keys",
    )


def r_data_edit_adjacent(rng, lang):
    """F10: both sides edit the values of two neighbouring keys. Rules: [DATA-3], [DATA-4]."""
    keys = keyed(rng, 5)
    i = rng.randrange(len(keys) - 1)
    o, t = list(keys), list(keys)
    o[i] = (o[i][0], o[i][1] + 100)
    t[i + 1] = (t[i + 1][0], t[i + 1][1] + 200)
    return (
        data_doc(lang, keys),
        data_doc(lang, o),
        data_doc(lang, t),
        "F10",
        "data.adjacent_edits",
    )


def r_data_dup_key(rng, lang):
    """F8 refusal (data): both sides add the same key at distant points of one object or table. Rules: [GATE-DATA-2], [GATE-3], [GATE-5]."""
    keys = keyed(rng, 6)
    a = rng.choice([w for w in WORDS if w not in dict(keys)])
    return (
        data_doc(lang, keys),
        data_doc(lang, keys[:1] + [(a, 7)] + keys[1:]),
        data_doc(lang, keys[:5] + [(a, 9)] + keys[5:]),
        "F8",
        "gate.data_duplicate_key",
    )


def r_data_dual_keys(rng, lang):
    """F8 accept-dual (data): different keys added at one point. Rules: [GATE-DATA-2], [DATA-6]."""
    b, o, t, _, _ = r_data_both_add_same_point(rng, lang)
    return b, o, t, "F8", "gate.dual_data_keys"


# ============================================================================= Phase C recipes
#
# Every recipe below returns a list of cases (base, ours, theirs, family, feature) with rendered
# texts. A list of two or more is one group, emitted with a shared `pair` id and one path: the
# first case is the one where the targeted rule applies, and each later one is a near miss that
# differs from it in one stated condition. They run after every earlier recipe, so the earlier
# cases keep their ids and their place in the random stream.

IND = {"py": "    ", "ts": "  ", "go": "\t"}
PY_TS = ("py", "ts")


def say(lang: str, text: str, depth: int = 1) -> str:
    """A one-line statement: indentation, the text and, in TypeScript, a semicolon."""
    return IND[lang] * depth + text + (";" if lang == "ts" else "")


def assign(lang: str, var: str, expr: str) -> str:
    """A statement declaring a local."""
    if lang == "py":
        return f"    {var} = {expr}"
    if lang == "ts":
        return f"  const {var} = {expr};"
    return f"\t{var} := {expr}"


def fn(lang: str, name: str, body: list[str], param: str = "arg") -> Item:
    """A function with the given (indented) body lines."""
    if lang == "py":
        return Item("func", name, [f"def {name}({param}):", *body])
    if lang == "ts":
        head = f"export function {name}({param}: number): number {{"
        return Item("func", name, [head, *body, "}"])
    return Item("func", name, [f"func {name}({param} int) int {{", *body, "}"])


def as_text(m: Module | str) -> str:
    """A module rendered, or a text as it is."""
    return m if isinstance(m, str) else render(m)


def case(base, ours, theirs, family: str, feature: str) -> tuple:
    """One case, its three versions rendered."""
    return as_text(base), as_text(ours), as_text(theirs), family, feature


def mod(rng: random.Random, lang: str, lo: int, hi: int) -> tuple[Module, set[str]]:
    """A module of plain functions, and the names it uses."""
    used: set[str] = set()
    return module(rng, lang, rng.randint(lo, hi), used), used


def cp(m: Module) -> Module:
    """A copy of a module."""
    return copy.deepcopy(m)


def side_pair(x_is_ours: bool, x, y) -> tuple:
    """(ours, theirs) for the side `x` and the other side `y`."""
    return (x, y) if x_is_ours else (y, x)


def last_return(it: Item, lang: str) -> int:
    """The index of a plain function's final return line."""
    return len(it.lines) - (1 if lang == "py" else 2)


def widen(it: Item, lang: str) -> None:
    """Add a parameter to a function's signature line."""
    extra = {"py": ", strict=False", "ts": ", strict = false", "go": ", strict bool"}[
        lang
    ]
    head = it.lines[0]
    at = head.index(")", head.index("("))
    it.lines[0] = head[:at] + extra + head[at:]


def const_name(rng: random.Random, lang: str, used: set[str]) -> str:
    """A fresh constant name: SCREAMING_CASE in Python and TypeScript, camelCase in Go."""
    while True:
        a, b = rng.sample(WORDS, 2)
        name = f"{a}{b.capitalize()}" if lang == "go" else f"{a}_{b}".upper()
        if name not in used:
            used.add(name)
            return name


def taps(lang: str, name: str) -> list[str]:
    """Three instrumentation statements about one function."""
    return [
        say(lang, f'audit("{name}.enter")'),
        say(lang, f'metrics.incr("{name}")'),
        say(lang, f'trace("{name}")'),
    ]


# ----------------------------------------------------------------------------- F1: the superset side


def r_superset_moved_line(rng, lang):
    """F1 superset.applies_deletions / superset.near_miss_moved_line ([ROUTE-4], [ROUTE-7] moves,
    [ROUTE-8], [CELL-9]). Y deletes f. Applies: X deletes f and the definition after it, so X's
    file is the result. Near miss: X also re-adds f unchanged at the end, a move, so no side holds
    the other's edits; the entity merge drops f (deleted against unchanged)."""
    base, _ = mod(rng, lang, 4, 6)
    k = rng.randrange(len(base.items) - 2)
    y, x = cp(base), cp(base)
    del y.items[k]
    del x.items[k : k + 2]
    x2 = cp(x)
    x2.items.append(copy.deepcopy(base.items[k]))
    xo = rng.random() < 0.5
    return [
        case(base, *side_pair(xo, x, y), "F1", "superset.applies_deletions"),
        case(base, *side_pair(xo, x2, y), "F1", "superset.near_miss_moved_line"),
    ]


def r_superset_deletion_rewritten(rng, lang):
    """F1 superset.applies_deletion_by_deletion / superset.near_miss_deletion_rewritten ([ROUTE-4],
    [ROUTE-7]: a deletion is carried only by a deletion; [CELL-10]). Y deletes one definition (a
    function in Python, a one-line binding in TypeScript and Go). Applies: X deletes it and its
    neighbour. Near miss: X's hunk over the same lines writes the definition again, rewritten under
    its own name, so there is no superset and the deletion meets an edit (modify/delete)."""
    base, used = mod(rng, lang, 3, 5)
    if lang == "py":
        k = rng.randrange(len(base.items) - 1)
        name = base.items[k].name
        lines = [
            f"def {name}(arg, limit=None):",
            "    cap = limit or 64",
            "    return min(arg * 2, cap)",
        ]
        new = Item("func", name, lines)
    else:
        k = rng.randrange(len(base.items) + 1)
        a, b = const_name(rng, lang, used), const_name(rng, lang, used)
        value = rng.randint(2, 9)
        base.items[k:k] = [
            binding(lang, a, value),
            binding(lang, b, rng.randint(10, 99)),
        ]
        new = binding(lang, a, value + 10)
    y, x = cp(base), cp(base)
    del y.items[k]
    del x.items[k : k + 2]
    x2 = cp(x)
    x2.items.insert(k, new)
    xo = rng.random() < 0.5
    return [
        case(base, *side_pair(xo, x, y), "F1", "superset.applies_deletion_by_deletion"),
        case(
            base, *side_pair(xo, x2, y), "F1", "superset.near_miss_deletion_rewritten"
        ),
    ]


def r_superset_insertion_point(rng, lang):
    """F1 superset.applies_insertions / superset.near_miss_insertion_point ([ROUTE-4], [ROUTE-7]:
    two insertions carry only at one point; [CELL-7], [PLACE-5], [PLACE-6]). Y adds h after a.
    Applies: X adds h and k there. Near miss: X adds k there and h after a later definition, so h
    is added by both, placed at the earlier anchor, after k."""
    base, used = mod(rng, lang, 3, 5)
    i = rng.randrange(len(base.items) - 1)
    j = rng.randrange(i + 1, len(base.items))
    h = func(rng, lang, ident(rng, lang, used))
    kk = func(rng, lang, ident(rng, lang, used))
    y, x, x2 = cp(base), cp(base), cp(base)
    y.items.insert(i + 1, copy.deepcopy(h))
    x.items[i + 1 : i + 1] = [copy.deepcopy(h), copy.deepcopy(kk)]
    x2.items.insert(j + 1, copy.deepcopy(h))
    x2.items.insert(i + 1, copy.deepcopy(kk))
    xo = rng.random() < 0.5
    return [
        case(base, *side_pair(xo, x, y), "F1", "superset.applies_insertions"),
        case(base, *side_pair(xo, x2, y), "F1", "superset.near_miss_insertion_point"),
    ]


def r_superset_unparsed(rng, lang):
    """F1 superset.applies_parses / superset.near_miss_does_not_parse ([ROUTE-8] (a),
    [RULE-REGIONS]). Y edits a line of f; X makes the same edit and adds a line after it. Applies:
    X parses, so X's file. Near miss: X's added line has a stray `)`, so X does not parse while Y
    does: X is refused, and no rule may take X's lines."""
    base, _ = mod(rng, lang, 2, 4)
    k = rng.randrange(len(base.items))
    bump = rng.randint(1, 9)
    y = cp(base)
    y.items[k].lines[1] = (
        y.items[k].lines[1].replace("helper(arg", f"helper(arg + {bump}", 1)
    )
    extra = {
        "py": "    value = clamp(value, 0, 99)",
        "ts": "  const capped = Math.min(value, 99);",
        "go": "\tvalue = clamp(value, 0, 99)",
    }[lang]
    x, x2 = cp(y), cp(y)
    x.items[k].lines.insert(2, extra)
    x2.items[k].lines.insert(2, extra.replace("99)", "99))", 1))
    xo = rng.random() < 0.5
    return [
        case(base, *side_pair(xo, x, y), "F1", "superset.applies_parses"),
        case(base, *side_pair(xo, x2, y), "F1", "superset.near_miss_does_not_parse"),
    ]


def r_superset_definition_count(rng, lang):
    """F1 superset.applies_other_name / superset.near_miss_same_name_moved ([ROUTE-8] (b),
    [CELL-10]). Y deletes a definition; X deletes it and its neighbour and adds one at the end.
    Applies: the addition has another name, so X's file. Near miss: it has the deleted one's kind
    and name and no line in common with it (moved and edited), so X still states it: refused, and
    the deletion meets an edit (modify/delete)."""
    base, used = mod(rng, lang, 3, 5)
    if lang == "py":
        k = rng.randrange(len(base.items) - 1)
        name = base.items[k].name
        other = func(rng, lang, ident(rng, lang, used))
        lines = [
            f"def {name}(arg, scale=1):",
            "    scaled = arg * scale",
            "    return round(scaled, 2)",
        ]
        moved = Item("func", name, lines)
    else:
        k = rng.randrange(len(base.items) + 1)
        a, b, c = (const_name(rng, lang, used) for _ in range(3))
        value = rng.randint(2, 9)
        base.items[k:k] = [
            binding(lang, a, value),
            binding(lang, b, rng.randint(10, 99)),
        ]
        other, moved = binding(lang, c, value + 1), binding(lang, a, value + 1)
    y, x = cp(base), cp(base)
    del y.items[k]
    del x.items[k : k + 2]
    x2 = cp(x)
    x.items.append(other)
    x2.items.append(moved)
    xo = rng.random() < 0.5
    return [
        case(base, *side_pair(xo, x, y), "F1", "superset.applies_other_name"),
        case(base, *side_pair(xo, x2, y), "F1", "superset.near_miss_same_name_moved"),
    ]


# ----------------------------------------------------------------------------- F1: files without definitions

SETTINGS = [
    "CACHE_TTL",
    "REQUEST_TIMEOUT",
    "MAX_RETRIES",
    "BATCH_SIZE",
    "POOL_SIZE",
    "QUEUE_DEPTH",
    "PAGE_SIZE",
    "LOCK_TIMEOUT",
    "IDLE_TIMEOUT",
    "RATE_LIMIT",
]


def camel(name: str) -> str:
    """CACHE_TTL -> cacheTtl."""
    head, *rest = name.lower().split("_")
    return head + "".join(p.capitalize() for p in rest)


def setting(lang: str, name: str, value: int) -> list[str]:
    """One top-level setting statement."""
    return (
        [f"{name} = {value}"]
        if lang == "py"
        else [f"settings.{camel(name)} = {value};"]
    )


def script(rng: random.Random, lang: str):
    """A script with no definitions: its import statements and its top-level statements (each a
    list of lines), and a setting name it does not use. Statements 1 to 6 are settings."""
    names = rng.sample(SETTINGS, 7)
    svc = rng.choice(WORDS)
    if lang == "py":
        head = [["import logging"], ["import os"]]
        body = [[f'LOG = logging.getLogger("{svc}")']]
        tail = [
            'if os.environ.get("APP_DEBUG") == "1":',
            "    LOG.setLevel(logging.DEBUG)",
        ]
    else:
        head = [
            ['import { logger } from "./logger";'],
            ['import { settings } from "./settings";'],
        ]
        body = [[f'logger.name = "{svc}";']]
        tail = [
            'if (process.env.APP_DEBUG === "1") {',
            '  logger.level = "debug";',
            "}",
        ]
    body += [setting(lang, n, rng.randint(2, 900)) for n in names[:6]]
    body.append(tail)
    return head, body, names[6]


def script_text(head, body) -> str:
    """The imports, a blank line, then the statements."""
    lines = [ln for s in head for ln in s] + [""] + [ln for s in body for ln in s]
    return "\n".join(lines) + "\n"


def retune(stmt: list[str], delta: int) -> list[str]:
    """A one-line setting statement with its value raised by `delta`."""
    left, _, right = stmt[0].rpartition(" = ")
    semi = ";" if right.endswith(";") else ""
    return [f"{left} = {int(right.rstrip(';')) + delta}{semi}"]


def nodefs_group(rng, lang, near):
    """The statement union of a file without definitions, and one near miss of kind `near`."""
    head, body, spare = script(rng, lang)
    i = rng.randrange(1, 6)
    d = rng.randint(1, 30)
    o, t = list(body), list(body)
    o[i] = retune(body[i], d)
    t[i + 1] = retune(body[i + 1], rng.randint(1, 30))
    o2, t2 = list(o), list(t)
    if near == "statement_inserted":
        o2.insert(i + 1, setting(lang, spare, rng.randint(2, 90)))
    elif near == "kinds_reordered":
        o2.insert(1, o2.pop())
    else:
        t2[i] = retune(body[i], d + rng.randint(1, 30))
    b = script_text(head, body)
    return [
        case(
            b,
            script_text(head, o),
            script_text(head, t),
            "F1",
            "nodefs.applies_statement_union",
        ),
        case(
            b,
            script_text(head, o2),
            script_text(head, t2),
            "F1",
            f"nodefs.near_miss_{near}",
        ),
    ]


def r_nodefs_inserted(rng, lang):
    """F1 nodefs.applies_statement_union / nodefs.near_miss_statement_inserted ([ROUTE-6] (c),
    [ROUTE-10], [ELEM-14]). A script of top-level statements only; the sides change two
    neighbouring settings, git conflicts, and the statement union in disjoint form applies. Near
    miss: ours also inserts a setting, so the statement counts differ: git's conflict stands."""
    return nodefs_group(rng, lang, "statement_inserted")


def r_nodefs_kinds(rng, lang):
    """F1 nodefs.applies_statement_union / nodefs.near_miss_kinds_reordered ([ROUTE-10], [ELEM-14]).
    As r_nodefs_inserted; near miss: ours also moves the `if` block up, so the statements no longer
    have the same kinds position by position."""
    return nodefs_group(rng, lang, "kinds_reordered")


def r_nodefs_both_rewrite(rng, lang):
    """F1 nodefs.applies_statement_union / nodefs.near_miss_both_rewrote_one ([ROUTE-10],
    [ELEM-14]). As r_nodefs_inserted; near miss: theirs also changes ours' setting, to another
    value, so one statement differs in all three."""
    return nodefs_group(rng, lang, "both_rewrote_one")


# ----------------------------------------------------------------------------- F1: markers and the line route

SAMPLE = ["<<<<<<< ours", "timeout = 30", "=======", "timeout = 60", ">>>>>>> theirs"]


def fixture(lang: str) -> Item:
    """A test fixture: a conflict sample whose marker lines start at column 0."""
    if lang == "py":
        lines = ['CONFLICT_SAMPLE = """\\', *SAMPLE, '"""']
    elif lang == "ts":
        lines = ["export const CONFLICT_SAMPLE = `", *SAMPLE, "`;"]
    else:
        lines = ["const conflictSample = `", *SAMPLE, "`"]
    return Item("const", "fixture", lines)


def marker_const(lang: str, name: str, text: str) -> str:
    """A string constant."""
    if lang == "py":
        return f'{name} = "{text}"'
    if lang == "ts":
        return f'export const {name} = "{text}";'
    return f'const {name} = "{text}"'


def r_route_markers_in_base(rng, lang):
    """F1 routing.markers_base_only ([ROUTE-2], [BOX-7], [CLI-10]). Only BASE carries markers: a
    conflict-sample fixture both sides removed, each also editing a different function. BASE is
    written, status 1, with the hint on the fixture's closing marker line."""
    base, _ = mod(rng, lang, 2, 4)
    a, b = rng.sample(range(len(base.items)), 2)
    ours, theirs = sides(base)
    edit_line(rng, ours.items[a], 1)
    edit_line(rng, theirs.items[b], 1)
    base.items.insert(rng.randrange(len(base.items) + 1), fixture(lang))
    return [case(base, ours, theirs, "F1", "routing.markers_base_only")]


def r_route_markers_in_ours(rng, lang):
    """F1 routing.markers_in_ours ([ROUTE-2], [BOX-7]). OURS adds a fixture whose marker lines start
    at column 0; theirs edits a function. OURS is written as it is, status 1, and the hint goes on
    the fixture's `>>>>>>> theirs` line."""
    base, _ = mod(rng, lang, 2, 4)
    a, b = rng.sample(range(len(base.items)), 2)
    ours, theirs = sides(base)
    edit_line(rng, ours.items[a], 1)
    ours.items.insert(rng.randrange(len(ours.items) + 1), fixture(lang))
    edit_line(rng, theirs.items[b], 1)
    return [case(base, ours, theirs, "F1", "routing.markers_in_ours")]


def r_route_open_marker_only(rng, lang):
    """F1 routing.markers_opening_string_only / routing.near_miss_both_marker_strings ([ROUTE-2],
    [GATE-MARK]). Ours widens f's signature; theirs adds a constant just above f (git conflicts).
    Applies: the constant holds only the opening string, so the merge goes on and composes both.
    Near miss: theirs adds the closing string too, so THEIRS carries markers and is written as it
    is, status 1 (no line starts with seven `>`, so no hint)."""
    base, _ = mod(rng, lang, 2, 4)
    k = rng.randrange(len(base.items))
    ours = cp(base)
    widen(ours.items[k], lang)
    o_name, c_name = (
        ("conflictOpen", "conflictClose")
        if lang == "go"
        else ("CONFLICT_OPEN", "CONFLICT_CLOSE")
    )
    opening = marker_const(lang, o_name, "<<<<<<< ")
    one, two = cp(base), cp(base)
    one.items.insert(k, Item("const", o_name, [opening]))
    two.items.insert(
        k, Item("const", o_name, [opening, marker_const(lang, c_name, ">>>>>>> ")])
    )
    return [
        case(base, ours, one, "F1", "routing.markers_opening_string_only"),
        case(base, ours, two, "F1", "routing.near_miss_both_marker_strings"),
    ]


def r_route_both_created(rng, lang):
    """F1 routing.both_created ([ROUTE-6] (b), [ROUTE-9]). BASE is empty and both sides created the
    file; one side also edited a function and added one, so neither holds the other's lines and
    the line route answers (git conflicts; let the filter decide)."""
    m, used = mod(rng, lang, 2, 4)
    t = cp(m)
    edit_line(rng, t.items[0], 1)
    t.items.append(func(rng, lang, ident(rng, lang, used)))
    return [case("", m, t, "F1", "routing.both_created")]


DUP_TYPES = {
    "py": ["str", "bytes", "int", "float", "bool", "list", "dict", "tuple", "set"],
    "ts": [
        "string",
        "number",
        "boolean",
        "Buffer",
        "Uint8Array",
        "URL",
        "Date",
        "RegExp",
        "bigint",
    ],
}


def same_named(lang: str, i: int, word: str) -> Item:
    """The i-th definition of a family sharing one name: Go `init`, a TS or Python overload."""
    if lang == "go":
        body = f'\tregister("{word}", new{word.capitalize()}Handler)'
        return Item("func", "init", ["func init() {", body, "}"])
    if lang == "ts":
        return Item(
            "func",
            "parse",
            [f"export function parse(input: {DUP_TYPES['ts'][i]}): Node;"],
        )
    return Item(
        "func",
        "parse",
        ["@overload", f"def parse(value: {DUP_TYPES['py'][i]}) -> Node: ..."],
    )


def r_route_many_same_name(rng, lang):
    """F1 routing.many_same_name_line_route / routing.near_miss_nine_same_name ([ROUTE-6] (d),
    [ENT-8]). A file with nine definitions of one name (Go `init` functions, TypeScript or Python
    overloads and their implementation) and plain functions; ours adds a function just above b,
    theirs widens b. Applies: ours also adds a tenth definition of that name, so the entity model is
    not used and git's merge (a conflict here) is the answer. Near miss: nine, so the entity merge
    composes the two edits."""
    base, used = mod(rng, lang, 2, 3)
    words = rng.sample(WORDS, 10)
    if lang == "go":
        family = [same_named(lang, i, words[i]) for i in range(9)]
        extra, at = same_named(lang, 9, words[9]), 9
    else:
        family = [same_named(lang, i, words[i]) for i in range(8)]
        extra, at = same_named(lang, 8, words[8]), 8
        if lang == "ts":
            impl = [
                "export function parse(input: unknown): Node {",
                "  return parseValue(input);",
                "}",
            ]
        else:
            impl = ["def parse(value):", "    return parse_value(value)"]
            base.header.append("from typing import overload")
        family.append(Item("func", "parse", impl))
    b = rng.randrange(len(base.items)) + len(family)
    base.items[0:0] = family
    o, t = cp(base), cp(base)
    o.items.insert(b, func(rng, lang, ident(rng, lang, used)))
    widen(t.items[b], lang)
    o2 = cp(o)
    o2.items.insert(at, extra)
    return [
        case(base, o2, t, "F1", "routing.many_same_name_line_route"),
        case(base, o, t, "F1", "routing.near_miss_nine_same_name"),
    ]


# ----------------------------------------------------------------------------- F9: rules that settle a conflict


def r_rule_d1(rng, lang):
    """F9 rules.d1_carried / rules.d1_near_miss_not_consecutive ([RULE-REGIONS], [RULE-D1],
    [SAME-11]). Both sides add instrumentation at one point of f (the fold boxes it) and each edits
    another function. Applies: X's lines hold Y's as one consecutive run, so X carries Y and the
    region settles. Near miss: X puts its extra line between Y's two, so it does not."""
    base, _ = mod(rng, lang, 3, 5)
    f, g, h = rng.sample(range(len(base.items)), 3)
    s = taps(lang, base.items[f].name)
    y, x = cp(base), cp(base)
    y.items[f].lines[2:2] = s[:2]
    edit_line(rng, y.items[g], 1)
    x.items[f].lines[2:2] = s
    edit_line(rng, x.items[h], 1)
    x2 = cp(x)
    x2.items[f] = copy.deepcopy(base.items[f])
    x2.items[f].lines[2:2] = [s[0], s[2], s[1]]
    xo = rng.random() < 0.5
    return [
        case(base, *side_pair(xo, x, y), "F9", "rules.d1_carried"),
        case(base, *side_pair(xo, x2, y), "F9", "rules.d1_near_miss_not_consecutive"),
    ]


IMPORT_USES = {
    "py": [
        ("import socket", "HOSTNAME = socket.gethostname()"),
        ("import platform", "PLATFORM = platform.system()"),
        ("import tempfile", "SCRATCH_DIR = tempfile.gettempdir()"),
        ("import getpass", "RUN_AS = getpass.getuser()"),
        ("import sys", "ARGS = sys.argv[1:]"),
    ],
    "ts": [
        ('import { hostname } from "node:os";', "logger.host = hostname();"),
        ('import { join } from "node:path";', 'settings.dataDir = join(".", "data");'),
        ('import { cwd } from "node:process";', "settings.root = cwd();"),
        ('import { randomUUID } from "node:crypto";', "logger.runId = randomUUID();"),
        ('import { cpus } from "node:os";', "settings.workers = cpus().length;"),
    ],
}
IMPORT_CLASH = {
    "py": [
        (
            "from json import loads",
            'DEFAULTS = loads(os.environ.get("APP_DEFAULTS", "{}"))',
        ),
        (
            "from orjson import loads",
            'OVERRIDES = loads(os.environ.get("APP_OVERRIDES", "{}"))',
        ),
    ],
    "ts": [
        ('import { parse } from "yaml";', 'settings.extra = parse("retries: 3");'),
        ('import { parse } from "toml";', 'settings.flags = parse("retries = 3");'),
    ],
}


def r_rule_d3_imports(rng, lang):
    """F9 rules.d3_import_union / rules.d3_near_miss_name_bound_twice ([RULE-D3], [ROUTE-10]). A
    script with no definitions; both sides add an import at the end of the import block and a
    statement using it elsewhere. git conflicts on the imports, and there is no statement union
    (both added statements). Applies: the imports bind different names, so the set union settles.
    Near miss: theirs' import binds ours' name from another module."""
    head, body, _ = script(rng, lang)

    def side(imp, use, at_end):
        stmts = list(body)
        if at_end:
            stmts.append([use])
        else:
            stmts.insert(1, [use])
        return script_text([*head, [imp]], stmts)

    mine = side(*IMPORT_CLASH[lang][0], True)
    b = script_text(head, body)
    return [
        case(
            b,
            mine,
            side(*rng.choice(IMPORT_USES[lang]), False),
            "F9",
            "rules.d3_import_union",
        ),
        case(
            b,
            mine,
            side(*IMPORT_CLASH[lang][1], False),
            "F9",
            "rules.d3_near_miss_name_bound_twice",
        ),
    ]


def r_rule_d3_go_imports(rng, lang):
    """F9 rules.d3_go_import_union / rules.d3_go_near_miss_name_bound_twice ([RULE-D3], [RULE-D1]).
    Go: both sides add an import at the end of the block and instrumentation at one point of f,
    one side's lines carrying the other's, so the entity merge conflicts and the rules decide every
    region. Applies: the imports bind different names. Near miss: "crypto/rand" against
    "math/rand", one name bound by two import lines."""
    base, _ = mod(rng, "go", 2, 4)
    f = rng.randrange(len(base.items))
    s = taps("go", base.items[f].name)

    def side(imp, run):
        m = cp(base)
        add_import(m, "go", imp)
        m.items[f].lines[2:2] = run
        return m

    x = side("crypto/rand", s)
    xo = rng.random() < 0.5
    other = side(rng.choice(EXTRA_IMPORTS["go"]), s[:2])
    return [
        case(base, *side_pair(xo, x, other), "F9", "rules.d3_go_import_union"),
        case(
            base,
            *side_pair(xo, x, side("math/rand", s[:2])),
            "F9",
            "rules.d3_go_near_miss_name_bound_twice",
        ),
    ]


def relayout(text: str) -> str:
    """The same program laid out differently ([RULE-LAYOUT]): no space after the comma in the
    helper calls, and a blank line after each."""
    out: list[str] = []
    for line in text.split("\n"):
        if "helper(arg, " in line:
            out += [line.replace("helper(arg, ", "helper(arg,", 1), ""]
        else:
            out.append(line)
    return "\n".join(out)


def r_rule_d4(rng, lang):
    """F9 rules.d4_layout_equal_creations / rules.d4_near_miss_content_differs ([RULE-D4],
    [RULE-LAYOUT], [ROUTE-6] (b)). BASE is empty and both sides created the file. Applies: one
    side is the other laid out differently (layout-equal), so the byte-wise smaller side is the
    answer. Near miss: that side also changes one string, so no rule settles git's conflict."""
    m, _ = mod(rng, lang, 2, 4)
    a = render(m)
    b = relayout(a)
    note = 'note := "' if lang == "go" else 'note = "'
    b2 = b.replace(note, note + "v2-", 1)
    lo = rng.random() < 0.5
    return [
        case("", *side_pair(lo, b, a), "F9", "rules.d4_layout_equal_creations"),
        case("", *side_pair(lo, b2, a), "F9", "rules.d4_near_miss_content_differs"),
    ]


def r_rule_d6(rng, lang):
    """F9 rules.d6_layout_only_side / rules.d6r_near_miss_comment_edited ([RULE-D6], [RULE-D6R],
    [RULE-LAYOUT]). One side drops the space after a comma in one line of f; the other adds an
    argument to the same call (the entity merge boxes it). Applies: the first side is layout-equal
    to BASE, so the other side's file. Near miss: the first side also rewords a comment above
    another function (comments are content), so the whole-file rule does not apply; the region,
    judged in context, takes the other side's line and keeps the reworded comment."""
    base, _ = mod(rng, lang, 3, 5)
    f, g = rng.sample(range(len(base.items)), 2)
    note = comment(lang, f"keep in sync with the {rng.choice(WORDS)} scheduler")
    base.items[g].lines.insert(0, note)
    lay, con = cp(base), cp(base)
    lay.items[f].lines[1] = lay.items[f].lines[1].replace(", ", ",", 1)
    arg = ", strict=True)" if lang == "py" else ", true)"
    con.items[f].lines[1] = con.items[f].lines[1].replace(")", arg, 1)
    lay2 = cp(lay)
    lay2.items[g].lines[0] = (
        lay2.items[g].lines[0].replace("keep in sync", "must stay in sync", 1)
    )
    lo = rng.random() < 0.5
    return [
        case(base, *side_pair(lo, lay, con), "F9", "rules.d6_layout_only_side"),
        case(
            base, *side_pair(lo, lay2, con), "F9", "rules.d6r_near_miss_comment_edited"
        ),
    ]


def r_rule_data_union(rng, lang):
    """F9 rules.data_key_union / rules.data_near_miss_shared_line ([RULE-DATA-UNION], [DATA-6],
    [DATA-5]). Both sides add two keys at one point of one object or table. Applies: the runs share
    no line, so the key union settles. Near miss: they share one line, so there is no union."""
    keys = keyed(rng, 5)
    a, b, c, d = rng.sample([w for w in WORDS if w not in dict(keys)], 4)
    at = rng.randrange(1, len(keys))

    def doc(run):
        return data_doc(lang, keys[:at] + run + keys[at:])

    ours = doc([(a, 7), (c, 9)])
    return [
        case(
            data_doc(lang, keys),
            ours,
            doc([(b, 8), (d, 6)]),
            "F9",
            "rules.data_key_union",
        ),
        case(
            data_doc(lang, keys),
            ours,
            doc([(a, 7), (d, 6)]),
            "F9",
            "rules.data_near_miss_shared_line",
        ),
    ]


def r_rule_d3c(rng, lang):
    """F9 rules.d3c_container_union / rules.d3c_near_miss_key_two_texts ([RULE-D3C], [IMP-2],
    [ELEM-14]). The file header holds a set container (a Python dict, a TypeScript object passed to
    configure()); both sides add an entry at one point. The header gap is a box (both rewrote one
    statement) and git conflicts. Applies: different keys, so the container insertion union
    settles. Near miss: one key with two values, so no union."""
    base, _ = mod(rng, lang, 2, 4)
    keys = keyed(rng, 4)
    a, b = rng.sample([w for w in WORDS if w not in dict(keys)], 2)
    at = rng.randrange(1, len(keys))

    def with_entries(run):
        m = cp(base)
        pairs = keys[:at] + run + keys[at:]
        if lang == "py":
            m.header += [
                "",
                "DEFAULTS = {",
                *[f'    "{k}": {v},' for k, v in pairs],
                "}",
            ]
        else:
            m.header.insert(0, 'import { configure } from "./configure";')
            m.header += ["", "configure({", *[f"  {k}: {v}," for k, v in pairs], "});"]
        return m

    b0, mine = with_entries([]), with_entries([(a, 7)])
    return [
        case(b0, mine, with_entries([(b, 8)]), "F9", "rules.d3c_container_union"),
        case(
            b0, mine, with_entries([(a, 8)]), "F9", "rules.d3c_near_miss_key_two_texts"
        ),
    ]


def r_rule_never(rng, lang):
    """F9 rules.d1_settles_body_edit / rules.never_rename_against_edit ([RULE-NEVER], [RULE-D1],
    [CELL-12]). Both sides add instrumentation at one point of f, one side's lines carrying the
    other's, and the carrying side also edits f's return line; the other edits another function.
    Applies: D1 settles the region, clean. Near miss: the other side also renames f (a rename
    against an edit); D1 would settle the same region, but the settled text is refused because a
    declaration one side removed was changed by the other, so the conflict stays."""
    base, used = mod(rng, lang, 3, 5)
    f, g = rng.sample(range(len(base.items)), 2)
    s = taps(lang, base.items[f].name)
    y, x = cp(base), cp(base)
    y.items[f].lines[2:2] = s[:2]
    edit_line(rng, y.items[g], 1)
    x.items[f].lines[2:2] = s
    edit_line(rng, x.items[f], last_return(x.items[f], lang))
    y2 = cp(y)
    rename_item(y2.items[f], ident(rng, lang, used))
    yo = rng.random() < 0.5
    return [
        case(base, *side_pair(yo, y, x), "F9", "rules.d1_settles_body_edit"),
        case(base, *side_pair(yo, y2, x), "F9", "rules.never_rename_against_edit"),
    ]


# ----------------------------------------------------------------------------- F5: containers


def member(lang: str, name: str, k: int) -> list[str]:
    """A method of a store-backed class; each of its lines but the closing one names it."""
    if lang == "py":
        return [
            f"    def {name}(self, key):",
            f'        row = self.store.get("{name}", key)',
            f'        self.audit("{name}", row)',
            f"        return self.finish(row, {k})",
        ]
    return [
        f"  {name}(key: string): number {{",
        f'    const row = this.store.get("{name}", key);',
        f'    this.audit("{name}", row);',
        f"    return this.finish(row, {k});",
        "  }",
    ]


def ctor(lang: str) -> list[str]:
    """The constructor member."""
    if lang == "py":
        return ["    def __init__(self, store):", "        self.store = store"]
    return ["  constructor(private readonly store: Store) {}"]


def factory(lang: str, cname: str) -> list[str]:
    """A factory member written above the constructor."""
    if lang == "py":
        return [
            "    @classmethod",
            "    def from_env(cls):",
            "        return cls(Store.connect())",
        ]
    return [
        "  static fromEnv(): " + cname + " {",
        f"    return new {cname}(Store.connect());",
        "  }",
    ]


def klass(
    lang: str, cname: str, members: list[list[str]], head: str | None = None
) -> Item:
    """A class whose members are separated by one blank line."""
    lines = [
        head or (f"class {cname}:" if lang == "py" else f"export class {cname} {{")
    ]
    for i, m in enumerate(members):
        if i:
            lines.append("")
        lines += m
    if lang == "ts":
        lines.append("}")
    return Item("class", cname, lines)


def resig(m: list[str], lang: str) -> list[str]:
    """A member with one more parameter."""
    old, new = (
        ("key)", "key, fresh=False)")
        if lang == "py"
        else ("key: string)", "key: string, fresh = false)")
    )
    return [m[0].replace(old, new, 1), *m[1:]]


def rebody(m: list[str], lang: str, at: int = 1) -> list[str]:
    """A member with its lookup line (at=1) or its return line (at=3) changed."""
    out = list(m)
    if at == 1:
        out[1] = out[1].replace(
            "key)", "key, timeout=5)" if lang == "py" else "key, 5)", 1
        )
    else:
        out[3] = out[3].replace("(row, ", "(row, 2 * ", 1)
    return out


def class_parts(rng: random.Random, lang: str, n: int):
    """A module, the class's slot in it, the class name, its members (constructor first) and the
    names used."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(1, 2), used)
    cname = "".join(w.capitalize() for w in rng.sample(WORDS, 2))
    members = [ctor(lang)] + [
        member(lang, ident(rng, lang, used), rng.randint(2, 60)) for _ in range(n)
    ]
    return base, rng.randrange(len(base.items) + 1), cname, members, used


def placed(base: Module, pos: int, item: Item) -> Module:
    """The module with one more item at `pos`."""
    m = cp(base)
    m.items.insert(pos, item)
    return m


def class_case(base, pos, lang, cname, b, o, t, feature, heads=(None, None, None)):
    """One F5 case from the three versions' member lists (and class lines)."""
    versions = [
        placed(base, pos, klass(lang, cname, ms, h)) for ms, h in zip((b, o, t), heads)
    ]
    return case(*versions, "F5", feature)


def r_class_add_above_edited(rng, lang):
    """F5 container.add_above_edited_member ([SAME-5], [SAME-7], [SAME-8]). Ours widens member A's
    signature; theirs adds member B just above A. diffy and git refuse the class; the member merge
    keeps both, B before A."""
    base, pos, cname, ms, used = class_parts(rng, lang, rng.randint(2, 4))
    i = rng.randrange(1, len(ms))
    o, t = list(ms), list(ms)
    o[i] = resig(o[i], lang)
    t.insert(i, member(lang, ident(rng, lang, used), rng.randint(2, 60)))
    return [
        class_case(
            base, pos, lang, cname, ms, o, t, "container.add_above_edited_member"
        )
    ]


def r_class_both_add_one_point(rng, lang):
    """F5 container.both_add_between_members ([SAME-7], [SAME-8]). Both sides add a different member
    at one point between two members; the member merge keeps both, ordered by name."""
    base, pos, cname, ms, used = class_parts(rng, lang, rng.randint(2, 4))
    i = rng.randrange(1, len(ms))
    o, t = list(ms), list(ms)
    o.insert(i, member(lang, ident(rng, lang, used), rng.randint(2, 60)))
    t.insert(i, member(lang, ident(rng, lang, used), rng.randint(2, 60)))
    return [
        class_case(
            base, pos, lang, cname, ms, o, t, "container.both_add_between_members"
        )
    ]


def r_class_delete_member(rng, lang):
    """F5 container.delete_vs_untouched / container.delete_vs_edit ([SAME-8], [BOX-3]). Ours deletes
    member A; theirs widens the member after it. Applies: theirs left A as in BASE, so A is dropped,
    clean. Near miss: theirs also edits A's body, so A is a member conflict with ours' section
    empty, its frame cut over BASE and theirs."""
    base, pos, cname, ms, _ = class_parts(rng, lang, rng.randint(3, 4))
    i = rng.randrange(1, len(ms) - 1)
    o = ms[:i] + ms[i + 1 :]
    t = list(ms)
    t[i + 1] = resig(t[i + 1], lang)
    t2 = list(t)
    t2[i] = rebody(t2[i], lang)
    return [
        class_case(base, pos, lang, cname, ms, o, t, "container.delete_vs_untouched"),
        class_case(base, pos, lang, cname, ms, o, t2, "container.delete_vs_edit"),
    ]


def fields_parts(rng: random.Random, lang: str):
    """A module, a slot, a class name, four fields with defaults, and two spare field names."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(1, 2), used)
    cname = "".join(w.capitalize() for w in rng.sample(WORDS, 2)) + "Policy"
    names = rng.sample(WORDS, 6)
    if lang == "py":
        base.header.append("from dataclasses import dataclass")
    fields = [(n, rng.randint(1, 500)) for n in names[:4]]
    return base, rng.randrange(len(base.items) + 1), cname, fields, names[4:]


def fields_item(
    lang: str, cname: str, fields: list[tuple[str, int]], summed: tuple[str, str]
) -> Item:
    """A frozen dataclass (Python), or a class with properties and a method summing two of them
    (TypeScript; `summed` names BASE's first two fields, the same in every version)."""
    if lang == "py":
        rows = [f"    {n}: int = {v}" for n, v in fields]
        return Item(
            "class", cname, ["@dataclass(frozen=True)", f"class {cname}:", *rows]
        )
    rows = [f"  {n} = {v};" for n, v in fields]
    total = [
        "  total(): number {",
        f"    return this.{summed[0]} + this.{summed[1]};",
        "  }",
    ]
    return Item("class", cname, [f"export class {cname} {{", *rows, "", *total, "}"])


def r_class_fields_both_edit(rng, lang):
    """F5 container.both_edit_neighbouring_fields ([SAME-5], [SAME-6], [SAME-8]). A dataclass
    (Python: fields are indentation members) or a class's properties (TypeScript: sem-core
    children); the sides change the defaults of two neighbouring fields. diffy and git conflict;
    the member merge keeps both changes."""
    base, pos, cname, fields, _ = fields_parts(rng, lang)
    summed = (fields[0][0], fields[1][0])
    i = rng.randrange(len(fields) - 1)
    o, t = list(fields), list(fields)
    o[i] = (o[i][0], o[i][1] + rng.randint(1, 50))
    t[i + 1] = (t[i + 1][0], t[i + 1][1] + rng.randint(1, 50))
    versions = [
        placed(base, pos, fields_item(lang, cname, fs, summed)) for fs in (fields, o, t)
    ]
    return [case(*versions, "F5", "container.both_edit_neighbouring_fields")]


def r_class_field_added_after_edited(rng, lang):
    """F5 container.field_added_after_edited ([SAME-6], [SAME-7], [SAME-8]). Ours changes a field's
    default; theirs adds a field right after it. The new field is anchored after the edited one."""
    base, pos, cname, fields, spare = fields_parts(rng, lang)
    summed = (fields[0][0], fields[1][0])
    i = rng.randrange(len(fields))
    o, t = list(fields), list(fields)
    o[i] = (o[i][0], o[i][1] + rng.randint(1, 50))
    t.insert(i + 1, (spare[0], rng.randint(1, 500)))
    versions = [
        placed(base, pos, fields_item(lang, cname, fs, summed)) for fs in (fields, o, t)
    ]
    return [case(*versions, "F5", "container.field_added_after_edited")]


def r_class_reorder_vs_edit(rng, lang):
    """F5 container.one_side_reorders ([SAME-7]: survivors take the order of the only side that
    reordered). Ours swaps two neighbouring members; theirs widens the second of them. The members
    come out in ours' order, with theirs' edit."""
    base, pos, cname, ms, _ = class_parts(rng, lang, rng.randint(2, 4))
    i = rng.randrange(1, len(ms) - 1)
    o, t = list(ms), list(ms)
    o[i], o[i + 1] = o[i + 1], o[i]
    t[i + 1] = resig(t[i + 1], lang)
    return [class_case(base, pos, lang, cname, ms, o, t, "container.one_side_reorders")]


TS_TYPES = ["string", "number", "boolean", "Date", "string[]", "number | null"]


def r_interface_both_add(rng, lang):
    """F5 container.interface_both_add ([SAME-5], [SAME-7], [SAME-8]), TypeScript. Both sides add a
    different property at one point of an interface; both are kept, ordered by name."""
    used: set[str] = set()
    base = module(rng, "ts", rng.randint(1, 2), used)
    cname = "".join(w.capitalize() for w in rng.sample(WORDS, 2)) + "Row"
    names = rng.sample(WORDS, 7)
    props = [f"  {n}: {rng.choice(TS_TYPES)};" for n in names[:5]]
    at = rng.randrange(1, len(props))
    o = props[:at] + [f"  {names[5]}: {rng.choice(TS_TYPES)};"] + props[at:]
    t = props[:at] + [f"  {names[6]}?: {rng.choice(TS_TYPES)};"] + props[at:]
    pos = rng.randrange(len(base.items) + 1)
    versions = [
        placed(
            base,
            pos,
            Item("interface", cname, [f"export interface {cname} {{", *ps, "}"]),
        )
        for ps in (props, o, t)
    ]
    return [case(*versions, "F5", "container.interface_both_add")]


def r_enum_both_add(rng, lang):
    """F5 container.enum_both_add ([SAME-5], [SAME-6] indentation members, [SAME-7], [SAME-8]),
    TypeScript. Both sides add a different member at one point of a string enum; both are kept,
    ordered by name."""
    used: set[str] = set()
    base = module(rng, "ts", rng.randint(1, 2), used)
    cname = "".join(w.capitalize() for w in rng.sample(WORDS, 2)) + "State"
    names = rng.sample(WORDS, 7)
    rows = [f'  {n.capitalize()} = "{n}",' for n in names]
    at = rng.randrange(1, 5)
    o = rows[:at] + [rows[5]] + rows[at:5]
    t = rows[:at] + [rows[6]] + rows[at:5]
    pos = rng.randrange(len(base.items) + 1)
    versions = [
        placed(base, pos, Item("enum", cname, [f"export enum {cname} {{", *rs, "}"]))
        for rs in (rows[:5], o, t)
    ]
    return [case(*versions, "F5", "container.enum_both_add")]


def r_class_header_vs_member(rng, lang):
    """F5 container.header_and_new_first_member ([SAME-5] header cut, [SAME-7], [SAME-8]). Ours
    changes the class line (a base class in Python, an implemented interface in TypeScript); theirs
    adds a factory member right below it, above the constructor."""
    base, pos, cname, ms, _ = class_parts(rng, lang, rng.randint(2, 3))
    head = (
        f"class {cname}(Base{cname}):"
        if lang == "py"
        else f"export class {cname} implements {cname}Api {{"
    )
    t = [factory(lang, cname), *ms]
    return [
        class_case(
            base,
            pos,
            lang,
            cname,
            ms,
            ms,
            t,
            "container.header_and_new_first_member",
            (None, head, None),
        )
    ]


def r_class_member_lines_merge(rng, lang):
    """F5 container.member_merged_by_lines ([SAME-8]: a member both changed merges by diffy first).
    The sides change two lines of member A that an unchanged line separates; ours also widens member
    B and theirs adds a member above B, so diffy and git refuse the class as a whole."""
    base, pos, cname, ms, used = class_parts(rng, lang, rng.randint(2, 4))
    a, b = rng.sample(range(1, len(ms)), 2)
    o, t = list(ms), list(ms)
    o[a] = rebody(o[a], lang, 1)
    t[a] = rebody(t[a], lang, 3)
    o[b] = resig(o[b], lang)
    t.insert(b, member(lang, ident(rng, lang, used), rng.randint(2, 60)))
    return [
        class_case(base, pos, lang, cname, ms, o, t, "container.member_merged_by_lines")
    ]


# ----------------------------------------------------------------------------- F7: decorators


def deco_parts(rng: random.Random, lang: str):
    """A module and the index of a decoratable definition: a function (Python) or a class
    (TypeScript, where decorators belong to classes)."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(2, 3), used)
    if lang == "py":
        return base, rng.randrange(len(base.items))
    cname = "".join(w.capitalize() for w in rng.sample(WORDS, 2)) + "Service"
    ms = [ctor(lang)] + [
        member(lang, ident(rng, lang, used), rng.randint(2, 60)) for _ in range(2)
    ]
    pos = rng.randrange(len(base.items) + 1)
    base.items.insert(pos, klass(lang, cname, ms))
    return base, pos


def reshape(it: Item, lang: str) -> None:
    """Change a definition's own line: one more parameter, or an implemented interface."""
    if lang == "py":
        widen(it, lang)
        return
    i = next(j for j, line in enumerate(it.lines) if line.startswith("export class "))
    it.lines[i] = it.lines[i].replace(" {", " implements Disposable {", 1)


def r_decorator_vs_own_line(rng, lang):
    """F7 decorators.add_vs_own_line / decorators.near_miss_both_add_different ([DEC-1], [SAME-1]).
    Ours adds a decorator; theirs changes the definition's own line just below it, so diffy
    refuses. Applies: only ours added one, so the decorator merge puts it over theirs' text. Near
    miss: theirs adds a different one too; ours adding one theirs did not means no answer, and the
    definition is a conflict."""
    base, k = deco_parts(rng, lang)
    d1, d2 = (
        ("@cached", "@traced") if lang == "py" else ("@Injectable()", "@Singleton()")
    )
    o, t = cp(base), cp(base)
    o.items[k].lines.insert(0, d1)
    reshape(t.items[k], lang)
    t2 = cp(t)
    t2.items[k].lines.insert(0, d2)
    return [
        case(base, o, t, "F7", "decorators.add_vs_own_line"),
        case(base, o, t2, "F7", "decorators.near_miss_both_add_different"),
    ]


def r_decorator_removed_vs_added(rng, lang):
    """F7 decorators.removed_vs_added / decorators.near_miss_ours_adds_changed ([DEC-1]). BASE has
    one decorator; ours removes it and theirs adds another just below it (diffy refuses). Applies:
    ours added none, so the merge drops the removed one and keeps theirs' new one. Near miss: ours
    changes it instead (an addition theirs did not make): no answer, a conflict."""
    base, k = deco_parts(rng, lang)
    if lang == "py":
        old, new, mine = "@retry(times=3)", "@timed", "@retry(times=5)"
    else:
        old, new, mine = "@Throttle(500)", "@Logged()", "@Throttle(250)"
    base.items[k].lines.insert(0, old)
    o, t, o2 = cp(base), cp(base), cp(base)
    del o.items[k].lines[0]
    t.items[k].lines.insert(1, new)
    o2.items[k].lines[0] = mine
    return [
        case(base, o, t, "F7", "decorators.removed_vs_added"),
        case(base, o2, t, "F7", "decorators.near_miss_ours_adds_changed"),
    ]


def r_decorator_both_same(rng, lang):
    """F7 decorators.both_add_same ([DEC-1], [RULE-D1]). Both sides add the same decorator; theirs
    also changes the definition's own line and ours edits another function. The decorator merge
    composes them (without it, the D1 region rule would settle the same text)."""
    base, k = deco_parts(rng, lang)
    d = "@cached" if lang == "py" else "@Injectable()"
    o, t = cp(base), cp(base)
    reshape(t.items[k], lang)
    o.items[k].lines.insert(0, d)
    t.items[k].lines.insert(0, d)
    j = next(i for i, it in enumerate(base.items) if i != k and it.kind == "func")
    edit_line(rng, o.items[j], 1)
    return [case(base, o, t, "F7", "decorators.both_add_same")]


# ----------------------------------------------------------------------------- F3: names, re-homes, call sites


def r_names_both_added(rng, lang):
    """F3 names.both_added_identical / names.near_miss_both_added_different ([MATCH-10], [CELL-7],
    [CELL-8], [PLACE-5]). Both sides add a function of one name at different places, and theirs
    edits another function. Applies: the same text, so one copy at the earlier anchor (git writes
    two). Near miss: one line differs, a both-added conflict with BASE's section empty."""
    base, used = mod(rng, lang, 3, 5)
    i = rng.randrange(len(base.items) - 1)
    j = rng.randrange(i + 1, len(base.items))
    h = func(rng, lang, ident(rng, lang, used))
    o, t = cp(base), cp(base)
    o.items.insert(i + 1, copy.deepcopy(h))
    edit_line(rng, t.items[rng.randrange(len(t.items))], 1)
    t2 = cp(t)
    h2 = copy.deepcopy(h)
    edit_line(rng, h2, 1)
    t.items.insert(j + 1, copy.deepcopy(h))
    t2.items.insert(j + 1, h2)
    return [
        case(base, o, t, "F3", "names.both_added_identical"),
        case(base, o, t2, "F3", "names.near_miss_both_added_different"),
    ]


def r_names_rename_onto_added(rng, lang):
    """F3 names.rename_onto_name_other_added / names.near_miss_rename_to_free_name ([MATCH-7],
    [CELL-8], [CELL-9], [CELL-11]). Ours renames f; theirs adds a function just above f. Applies:
    theirs' function has ours' new name, so names outrank bodies: the rename is withheld, f is
    dropped (deleted against unchanged) and the name is a both-added conflict. Near miss: theirs'
    function has another name, so the rename stands and the merge is clean."""
    base, used = mod(rng, lang, 2, 4)
    k = rng.randrange(len(base.items))
    new, other = ident(rng, lang, used), ident(rng, lang, used)
    o = cp(base)
    rename_item(o.items[k], new)
    g = func(rng, lang, new)
    g2 = copy.deepcopy(g)
    rename_item(g2, other)
    t, t2 = cp(base), cp(base)
    t.items.insert(k, g)
    t2.items.insert(k, g2)
    return [
        case(base, o, t, "F3", "names.rename_onto_name_other_added"),
        case(base, o, t2, "F3", "names.near_miss_rename_to_free_name"),
    ]


VARS = [
    "raw",
    "base",
    "scaled",
    "bounded",
    "rounded",
    "shifted",
    "weighted",
    "capped",
    "adjusted",
]
STEPS = [
    "normalize",
    "scale",
    "clamp",
    "quantize",
    "shift",
    "weight",
    "limit",
    "offset",
    "smooth",
    "bias",
]


def chain(rng: random.Random, n: int) -> list[tuple[str, str, int]]:
    """n pipeline steps: (variable, helper, constant)."""
    return [
        (VARS[i], s, rng.randint(2, 40)) for i, s in enumerate(rng.sample(STEPS, n))
    ]


def chain_body(lang: str, steps, src: str = "arg") -> tuple[list[str], str]:
    """The statements running the steps from `src`, and the last variable."""
    body, prev = [], src
    for var, step, k in steps:
        body.append(assign(lang, var, f"{step}({prev}, {k})"))
        prev = var
    return body, prev


def chain_fn(lang: str, name: str, steps, src: str = "arg") -> Item:
    """A function that runs the steps and returns the last variable."""
    body, last = chain_body(lang, steps, src)
    return fn(lang, name, [*body, say(lang, f"return {last}")], param=src)


def retuned(steps, i: int, delta: int):
    """The steps with step i's constant raised by `delta`."""
    out = list(steps)
    var, step, k = out[i]
    out[i] = (var, step, k + delta)
    return out


def chain_module(rng: random.Random, lang: str, n: int):
    """A module with one pipeline function of n steps: module, used names, index, name, steps."""
    base, used = mod(rng, lang, 2, 4)
    k = rng.randrange(len(base.items))
    steps = chain(rng, n)
    base.items[k] = chain_fn(lang, base.items[k].name, steps)
    return base, used, k, base.items[k].name, steps


def suffixed(lang: str, name: str, word: str) -> str:
    """A helper name derived from a function name."""
    return f"{name}_{word}" if lang == "py" else f"{name}{word.capitalize()}"


def extracted(
    lang: str, base: Module, k: int, name: str, steps, cut: int, word: str
) -> Module:
    """The module with f keeping its first `cut` steps and calling a new helper for the rest."""
    m = cp(base)
    body, last = chain_body(lang, steps[:cut])
    helper = suffixed(lang, name, word)
    m.items[k] = fn(lang, name, [*body, say(lang, f"return {helper}({last})")])
    m.items.insert(k + 1, chain_fn(lang, helper, steps[cut:], src=last))
    return m


def r_rehome_extract(rng, lang):
    """F3 rehome.extract_edit_lands_in_helper / rehome.near_miss_edit_left_behind ([MATCH-8],
    [BIND-6]). Ours moves all but the first step of f into a new helper that f calls. Applies:
    theirs edits one moved line, and the edit lands in the helper; f is ours' text, clean. Near
    miss: theirs also edits the line that stayed in f, a removed line that did not move, so the
    triple is a both-modified conflict."""
    base, _, k, name, steps = chain_module(rng, lang, 6)
    o = extracted(lang, base, k, name, steps, 1, "steps")
    t, t2 = cp(base), cp(base)
    t.items[k] = chain_fn(lang, name, retuned(steps, 3, 7))
    t2.items[k] = chain_fn(lang, name, retuned(retuned(steps, 3, 7), 0, 5))
    return [
        case(base, o, t, "F3", "rehome.extract_edit_lands_in_helper"),
        case(base, o, t2, "F3", "rehome.near_miss_edit_left_behind"),
    ]


def r_rehome_moved_twice(rng, lang):
    """F3 rehome.body_moved_twice / rehome.near_miss_variant_shares_nothing ([MATCH-8], [BIND-5],
    [CELL-11]). Ours renames f and adds a variant of it; theirs adds a function just above f.
    Applies: the variant repeats all of f's steps but one, so f's body is re-homed into it besides
    the rename: a both-modified conflict. Near miss: the variant shares no line with f, so only
    the rename counts (it is the triple's own definition) and the merge is clean."""
    base, used, k, _, steps = chain_module(rng, lang, 6)
    new, variant = ident(rng, lang, used), ident(rng, lang, used)
    o, o2 = cp(base), cp(base)
    rename_item(o.items[k], new)
    rename_item(o2.items[k], new)
    o.items.insert(k + 1, chain_fn(lang, variant, retuned(steps, 2, 3)))
    o2.items.insert(k + 1, func(rng, lang, variant))
    t = cp(base)
    t.items.insert(k, func(rng, lang, ident(rng, lang, used)))
    return [
        case(base, o, t, "F3", "rehome.body_moved_twice"),
        case(base, o2, t, "F3", "rehome.near_miss_variant_shares_nothing"),
    ]


def r_rehome_both_extract(rng, lang):
    """F3 rehome.both_extract_differently ([BIND-7], [MATCH-8]). Both sides move the tail of f into
    a new helper, cut at different steps; f is a conflict, rebuilt over BASE's text and, per side,
    its helper and its own text."""
    base, _, k, name, steps = chain_module(rng, lang, 6)
    o = extracted(lang, base, k, name, steps, 2, "tail")
    t = extracted(lang, base, k, name, steps, 3, "rest")
    return [case(base, o, t, "F3", "rehome.both_extract_differently")]


def r_calls_rename_new_caller(rng, lang):
    """F3 calls.rename_reaches_new_caller / calls.near_miss_passed_as_value ([BIND-1],
    [GATE-DANGLING]). Ours renames f; theirs adds a function just above f that uses f. Applies: it
    calls f, so the call is carried to the new name (clean). Near miss: it passes f as a value, not
    a call, so nothing is repaired, the result would leave f dangling, and the merge falls back."""
    base, used = mod(rng, lang, 2, 4)
    k = rng.randrange(len(base.items))
    old = base.items[k].name
    o = cp(base)
    rename_item(o.items[k], ident(rng, lang, used))
    caller = ident(rng, lang, used)
    t, t2 = cp(base), cp(base)
    t.items.insert(k, fn(lang, caller, [say(lang, f"return {old}(arg) + 1")]))
    t2.items.insert(k, fn(lang, caller, [say(lang, f"return register({old}, arg)")]))
    return [
        case(base, o, t, "F3", "calls.rename_reaches_new_caller"),
        case(base, o, t2, "F3", "calls.near_miss_passed_as_value"),
    ]


def r_calls_deleted_callee(rng, lang):
    """F3 calls.deleted_but_newly_called / calls.near_miss_other_callee ([BIND-2], [CELL-9]). Ours
    deletes f; theirs adds a function just above f. Applies: it calls f, so the deletion becomes a
    modify/delete conflict. Near miss: it calls another function, so f is dropped, clean."""
    base, used = mod(rng, lang, 3, 5)
    k, j = rng.sample(range(len(base.items)), 2)
    o = cp(base)
    del o.items[k]
    caller = ident(rng, lang, used)
    t, t2 = cp(base), cp(base)
    t.items.insert(
        k, fn(lang, caller, [say(lang, f"return {base.items[k].name}(arg) * 2")])
    )
    t2.items.insert(
        k, fn(lang, caller, [say(lang, f"return {base.items[j].name}(arg) * 2")])
    )
    return [
        case(base, o, t, "F3", "calls.deleted_but_newly_called"),
        case(base, o, t2, "F3", "calls.near_miss_other_callee"),
    ]


def r_calls_new_callee(rng, lang):
    """F3 calls.new_definition_newly_called / calls.near_miss_calls_existing ([BIND-3]). Both sides
    add a function after one anchor; ours' is h. Applies: theirs' calls h, which only ours defines:
    a both-added conflict over h. Near miss: theirs' calls an existing function, so both are kept,
    ordered by name."""
    base, used = mod(rng, lang, 2, 4)
    i = rng.randrange(len(base.items))
    h, n = ident(rng, lang, used), ident(rng, lang, used)
    o = cp(base)
    o.items.insert(i + 1, func(rng, lang, h))
    t, t2 = cp(base), cp(base)
    t.items.insert(i + 1, fn(lang, n, [say(lang, f"return {h}(arg) - 1")]))
    t2.items.insert(
        i + 1, fn(lang, n, [say(lang, f"return {base.items[i].name}(arg) - 1")])
    )
    return [
        case(base, o, t, "F3", "calls.new_definition_newly_called"),
        case(base, o, t2, "F3", "calls.near_miss_calls_existing"),
    ]


def guarded(lang: str, name: str, k: int, n: int) -> Item:
    """A function whose local `limit` guards its result."""
    tag = name[-6:]
    if lang == "py":
        lines = [
            f"def {name}(arg):",
            f"    limit = threshold(arg, {n})",
            f"    value = helper(arg, {k})",
            "    if value > limit:",
            "        return limit",
            f'    note = "{tag}"',
            "    record(note)",
            "    return value",
        ]
    elif lang == "ts":
        lines = [
            f"export function {name}(arg: number): number {{",
            f"  const limit = threshold(arg, {n});",
            f"  const value = helper(arg, {k});",
            "  if (value > limit) {",
            "    return limit;",
            "  }",
            f'  const note = "{tag}";',
            "  record(note);",
            "  return value;",
            "}",
        ]
    else:
        lines = [
            f"func {name}(arg int) int {{",
            f"\tlimit := threshold(arg, {n})",
            f"\tvalue := helper(arg, {k})",
            "\tif value > limit {",
            "\t\treturn limit",
            "\t}",
            f'\tnote := "{tag}"',
            "\trecord(note)",
            "\treturn value",
            "}",
        ]
    return Item("func", name, lines)


def r_calls_local_unassigned(rng, lang):
    """F3 calls.local_no_longer_assigned / calls.near_miss_local_still_assigned ([BIND-4],
    [SAME-2]). Ours drops f's local `limit` and inlines its value; theirs adds a line near the end
    of f; diffy composes the two. Applies: theirs' line uses `limit`, which the composed text no
    longer assigns: a both-modified conflict. Near miss: it uses `value`, clean."""
    base, _ = mod(rng, lang, 2, 4)
    k = rng.randrange(len(base.items))
    n = rng.randint(30, 90)
    base.items[k] = guarded(lang, base.items[k].name, rng.randint(2, 20), n)
    o = cp(base)
    lines = o.items[k].lines
    lines[3] = lines[3].replace("limit", str(n), 1)
    lines[4] = lines[4].replace("limit", str(n), 1)
    del lines[1]
    t, t2 = cp(base), cp(base)
    for m, var in ((t, "limit"), (t2, "value")):
        m.items[k].lines.insert(
            last_return(m.items[k], lang), say(lang, f"audit({var})")
        )
    return [
        case(base, o, t, "F3", "calls.local_no_longer_assigned"),
        case(base, o, t2, "F3", "calls.near_miss_local_still_assigned"),
    ]


# ----------------------------------------------------------------------------- F4: one definition, the fold, boxes


def docstring_fn(rng: random.Random, name: str) -> Item:
    """A Python function with a docstring of several lines."""
    return Item(
        "func",
        name,
        [
            f"def {name}(arg):",
            '    """Return the adjusted value for one ledger row.',
            "",
            "    The value is capped by the tenant quota and rounded down.",
            "    Raises ValueError when the argument is negative.",
            '    """',
            f"    value = helper(arg, {rng.randint(2, 40)})",
            f"    return value - {rng.randint(2, 9)}",
        ],
    )


def r_samedef_diffy_clean(rng, lang):
    """F4 samedef.diffy_clean ([SAME-1], [SAME-2]). Both sides edit f where diffy's merge is clean
    (an unchanged line between): two lines of its docstring in Python (one string, which the
    element union would not split), its signature and its last line in TypeScript and Go (the
    body's brace shares the signature's line, so the union would refuse). Ours also widens g while
    theirs adds a function just above g, so git conflicts there and the entity merge does not."""
    base, used = mod(rng, lang, 3, 5)
    f, g = rng.sample(range(len(base.items)), 2)
    if lang == "py":
        base.items[f] = docstring_fn(rng, base.items[f].name)
    o, t = cp(base), cp(base)
    if lang == "py":
        o.items[f].lines[1] = (
            o.items[f].lines[1].replace("one ledger row", "one ledger row, in cents", 1)
        )
        t.items[f].lines[4] = (
            t.items[f].lines[4].replace("ValueError", "ValueError or TypeError", 1)
        )
    else:
        widen(o.items[f], lang)
        edit_line(rng, t.items[f], last_return(t.items[f], lang))
    widen(o.items[g], lang)
    t.items.insert(g, func(rng, lang, ident(rng, lang, used)))
    return [case(base, o, t, "F4", "samedef.diffy_clean")]


def r_samedef_json_diffy(rng, lang):
    """F4 samedef.data_diffy_clean ([SAME-1], [SAME-2]), JSON. Both sides change a different value
    of one nested object, an unchanged key between (diffy merges it; no element union reads JSON).
    Ours also changes `version` while theirs adds a root key just above it, so git conflicts."""
    keys = keyed(rng, 5)
    i = rng.randrange(0, 3)

    def doc(kv, extra, version):
        root = {"service": {"name": "api", "limits": dict(kv)}}
        root.update(extra)
        root["version"] = version
        return json_text(root)

    o, t = list(keys), list(keys)
    o[i] = (o[i][0], o[i][1] + 100)
    t[i + 2] = (t[i + 2][0], t[i + 2][1] + 200)
    region = {"region": rng.choice(["eu-west-1", "us-east-2", "ap-south-1"])}
    return [
        case(
            doc(keys, {}, 3),
            doc(o, {}, 4),
            doc(t, region, 3),
            "F4",
            "samedef.data_diffy_clean",
        )
    ]


def r_samedef_whitespace_side(rng, lang):
    """F4 samedef.whitespace_only_side / samedef.near_miss_reindent_with_edit ([SAME-3]),
    TypeScript and Go. Ours re-indents f's body (whitespace only) and edits another function;
    theirs edits f's first body line. diffy refuses f and the whitespace shortcut takes theirs'
    text. Near miss: ours' re-indent also changes a string, so the shortcut does not apply."""
    base, _ = mod(rng, lang, 2, 4)
    f, g = rng.sample(range(len(base.items)), 2)
    o = cp(base)
    lines = o.items[f].lines
    inner = [
        ("  " + ln) if lang == "ts" else ln.replace("\t", "    ") for ln in lines[1:-1]
    ]
    o.items[f].lines = [lines[0], *inner, lines[-1]]
    edit_line(rng, o.items[g], 1)
    t = cp(base)
    edit_line(rng, t.items[f], 1)
    o2 = cp(o)
    o2.items[f].lines[2] = o2.items[f].lines[2].replace('"', '"v2-', 1)
    return [
        case(base, o, t, "F4", "samedef.whitespace_only_side"),
        case(base, o2, t, "F4", "samedef.near_miss_reindent_with_edit"),
    ]


def r_fold_statement_box(rng, lang):
    """F4 fold.statement_scoped_box / fold.near_miss_no_box ([SAME-9], [SAME-10], [SAME-11],
    [BOX-4]). f is a pipeline of eight steps. Both sides change step 2's constant differently;
    ours also changes step 5, and theirs adds a statement just above it. The element union refuses
    and the fold writes one box around step 2, the rest merged. Near miss: both change step 2 the
    same way, so the fold holds no box, is not used, and f is one box over the definition."""
    base, _, k, name, steps = chain_module(rng, lang, 8)
    o = cp(base)
    o.items[k] = chain_fn(lang, name, retuned(retuned(steps, 2, 1), 5, 3))

    def theirs(delta):
        m = cp(base)
        m.items[k] = chain_fn(lang, name, retuned(steps, 2, delta))
        m.items[k].lines.insert(6, say(lang, f'audit("{name}.{steps[4][0]}")'))
        return m

    return [
        case(base, o, theirs(2), "F4", "fold.statement_scoped_box"),
        case(base, o, theirs(1), "F4", "fold.near_miss_no_box"),
    ]


DECLS = ["retries", "timeout", "budget", "window_ms", "attempts", "backoff"]


def declare(lang: str, name: str, value: int) -> str:
    """A local declaration as [SAME-11] reads one (Go's `:=` is not one, `var` is)."""
    if lang == "py":
        return f"    {name} = {value}"
    if lang == "ts":
        return f"  const {name} = {value};"
    return f"\tvar {name} = {value}"


def r_fold_declarations(rng, lang):
    """F4 fold.declaration_blocks_both / fold.near_miss_declared_name_shared ([SAME-11]: two blocks
    of declarations). Both sides declare a new local at one point of f and change step 4
    differently (a box). Applies: the names differ, so the fold writes both declarations, the
    smaller first. Near miss: both declare one name, so the insertion is a second box."""
    base, _, k, name, steps = chain_module(rng, lang, 6)
    a, b = rng.sample(DECLS, 2)

    def side(decl, value, delta):
        m = cp(base)
        m.items[k] = chain_fn(lang, name, retuned(steps, 4, delta))
        m.items[k].lines.insert(3, declare(lang, decl, value))
        return m

    o = side(a, rng.randint(2, 9), 1)
    return [
        case(
            base,
            o,
            side(b, rng.randint(10, 99), 2),
            "F4",
            "fold.declaration_blocks_both",
        ),
        case(
            base,
            o,
            side(a, rng.randint(10, 99), 2),
            "F4",
            "fold.near_miss_declared_name_shared",
        ),
    ]


def r_box_coalesce(rng, lang):
    """F4 boxes.coalesced / boxes.near_miss_seven_lines_apart ([BOX-5], [BOX-4]). Both sides change
    one line of f and one line of the next function g, differently: two boxes. Applies: f's last
    line and g's first body line, at most six unchanged lines apart, so one box is written. Near
    miss: f's first body line instead, seven or more lines apart, so two boxes."""
    base, _ = mod(rng, lang, 2, 4)
    k = rng.randrange(len(base.items) - 1)

    def side(at_end, mult, minus):
        m = cp(base)
        f, g = m.items[k], m.items[k + 1]
        if at_end:
            i = last_return(f, lang)
            f.lines[i] = f.lines[i].replace("return value", f"return value * {mult}", 1)
        else:
            f.lines[1] = f.lines[1].replace("helper(arg", f"helper(arg + {mult}", 1)
        g.lines[1] = g.lines[1].replace("helper(arg", f"helper(arg - {minus}", 1)
        return m

    return [
        case(base, side(True, 2, 1), side(True, 3, 2), "F4", "boxes.coalesced"),
        case(
            base,
            side(False, 2, 1),
            side(False, 3, 2),
            "F4",
            "boxes.near_miss_seven_lines_apart",
        ),
    ]


# ----------------------------------------------------------------------------- F2: the order of survivors


def r_order_one_side_moves(rng, lang):
    """F2 placement.one_side_moves_one / placement.near_miss_both_reorder ([PLACE-1], [PLACE-2],
    [PLACE-3]). Ours moves the first definition to the end; theirs widens the one that followed it
    (git conflicts there). Applies: only ours reordered, so ours' order. Near miss: theirs also
    swaps two other definitions, so both reordered and BASE's order stands."""
    base, _ = mod(rng, lang, 4, 6)
    o = cp(base)
    o.items.append(o.items.pop(0))
    t = cp(base)
    widen(t.items[1], lang)
    t2 = cp(t)
    t2.items[2], t2.items[3] = t2.items[3], t2.items[2]
    return [
        case(base, o, t, "F2", "placement.one_side_moves_one"),
        case(base, o, t2, "F2", "placement.near_miss_both_reorder"),
    ]


def r_order_deletion_not_reorder(rng, lang):
    """F2 placement.deletion_is_not_reorder / placement.near_miss_deleter_also_moves ([PLACE-1],
    [PLACE-2], [PLACE-3]). Ours deletes b; theirs swaps the two definitions after it. Applies: ours'
    survivors keep BASE's order (a deletion is no reorder), so theirs' order. Near miss: ours also
    moves a below c, so both reordered and BASE's order stands."""
    base, _ = mod(rng, lang, 5, 6)
    o = cp(base)
    del o.items[1]
    t = cp(base)
    t.items[2], t.items[3] = t.items[3], t.items[2]
    o2 = cp(o)
    o2.items.insert(1, o2.items.pop(0))
    return [
        case(base, o, t, "F2", "placement.deletion_is_not_reorder"),
        case(base, o2, t, "F2", "placement.near_miss_deleter_also_moves"),
    ]


ALL3 = ("py", "ts", "go")
CODE_RECIPES = [
    (r_insert_vs_header_edit, ALL3),
    (r_delete_vs_next_edit, ALL3),
    (r_both_add_same_anchor, ALL3),
    (r_both_add_two_vs_one, ALL3),
    (r_reorder_vs_edit, ALL3),
    (r_rename_vs_edit, ALL3),
    (r_rename_edit_vs_edit, ALL3),
    (r_rename_vs_rewrite, ALL3),
    (r_both_edit_adjacent, ALL3),
    (r_both_edit_same_line, ALL3),
    (r_class_both_add_methods, ("py", "ts")),
    (r_class_add_vs_edit_next, ("py", "ts")),
    (r_collection_both_add_same_point, ALL3),
    (r_collection_same_key_two_values, ALL3),
    (r_switch_both_add_same_point, ALL3),
    (r_imports_both_add, ALL3),
    (r_decorators_both_add, ("py",)),
    (r_gate_dup_case, ALL3),
    (r_gate_dual_cases, ALL3),
    (r_gate_dup_key, ALL3),
    (r_gate_dual_keys, ALL3),
    (r_gate_dup_name, ALL3),
    (r_gate_dual_names, ALL3),
    (r_gate_dup_import, ALL3),
    (r_gate_dangling, ALL3),
    (r_gate_dual_imports, ALL3),
    (r_gate_dup_line, ALL3),
    (r_gate_iota, ("go",)),
    (r_gate_dual_iota, ("go",)),
    (r_rule_subsumed_edit, ALL3),
    (r_rule_layout_only_side, ("py",)),
]
DATA_RECIPES = [
    r_data_both_add_same_point,
    r_data_edit_adjacent,
    r_data_dup_key,
    r_data_dual_keys,
]
ROUTING_RECIPES = [
    r_route_nul_between_git_and_driver,
    r_route_nul_after_8192,
    r_route_not_utf8,
    r_route_markers_in_theirs,
]
LAYOUT_SOURCES = [
    r_insert_vs_header_edit,
    r_delete_vs_next_edit,
    r_both_add_same_anchor,
]
PHASE_C_RECIPES = [
    # F1: routing beyond markers
    (r_superset_moved_line, ALL3),
    (r_superset_deletion_rewritten, ALL3),
    (r_superset_insertion_point, ALL3),
    (r_superset_unparsed, ALL3),
    (r_superset_definition_count, ALL3),
    (r_nodefs_inserted, PY_TS),
    (r_nodefs_kinds, PY_TS),
    (r_nodefs_both_rewrite, PY_TS),
    (r_route_markers_in_base, ALL3),
    (r_route_markers_in_ours, ALL3),
    (r_route_open_marker_only, ALL3),
    (r_route_both_created, ALL3),
    (r_route_many_same_name, ALL3),
    # F9: rules that settle a conflict
    (r_rule_d1, ALL3),
    (r_rule_d3_imports, PY_TS),
    (r_rule_d3_go_imports, ("go",)),
    (r_rule_d4, ALL3),
    (r_rule_d6, ALL3),
    (r_rule_data_union, ("json", "toml")),
    (r_rule_d3c, PY_TS),
    (r_rule_never, ALL3),
    # F5: containers
    (r_class_add_above_edited, PY_TS),
    (r_class_both_add_one_point, PY_TS),
    (r_class_delete_member, PY_TS),
    (r_class_fields_both_edit, PY_TS),
    (r_class_field_added_after_edited, PY_TS),
    (r_class_reorder_vs_edit, PY_TS),
    (r_interface_both_add, ("ts",)),
    (r_enum_both_add, ("ts",)),
    (r_class_header_vs_member, PY_TS),
    (r_class_member_lines_merge, PY_TS),
    # F7: decorators
    (r_decorator_vs_own_line, PY_TS),
    (r_decorator_removed_vs_added, PY_TS),
    (r_decorator_both_same, PY_TS),
    # F3: names, re-homes, call sites
    (r_names_both_added, ALL3),
    (r_names_rename_onto_added, ALL3),
    (r_rehome_extract, ALL3),
    (r_rehome_moved_twice, ALL3),
    (r_rehome_both_extract, ALL3),
    (r_calls_rename_new_caller, ALL3),
    (r_calls_deleted_callee, ALL3),
    (r_calls_new_callee, ALL3),
    (r_calls_local_unassigned, ALL3),
    # F4: one definition, the statement fold, coalescing
    (r_samedef_diffy_clean, ALL3),
    (r_samedef_json_diffy, ("json",)),
    (r_samedef_whitespace_side, ("ts", "go")),
    (r_fold_statement_box, ALL3),
    (r_fold_declarations, ALL3),
    (r_box_coalesce, ALL3),
    # F2: the order of survivors
    (r_order_one_side_moves, ALL3),
    (r_order_deletion_not_reorder, ALL3),
]
# Every input of a Phase C case stays below this many bytes (the stated limit is 100,000).
PHASE_C_MAX_BYTES = 10_000


def layout_variant(
    rng: random.Random, texts: tuple[str, str, str]
) -> tuple[tuple[str, str, str], str]:
    """Rewrite all three versions with CRLF, no final newline, or a BOM (F1's layout sub-family)."""
    kind = rng.choice(["crlf", "no_final_newline", "bom"])
    if kind == "crlf":
        return tuple(t.replace("\n", "\r\n") for t in texts), "layout.crlf"
    if kind == "no_final_newline":
        return tuple(t.rstrip("\n") for t in texts), "layout.no_final_newline"
    return tuple("﻿" + t for t in texts), "layout.bom"


def main() -> None:
    """Write the candidate cases."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--per-recipe", type=int, default=20)
    ap.add_argument("--layout", type=int, default=60, help="layout-variant cases")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    cases: list[dict] = []

    def emit(texts, path, family, feature, lang, recipe, pair=None):
        rec = {
            "id": f"c{len(cases):05d}",
            "family": family,
            "feature": feature,
            "lang": lang,
            "recipe": recipe,
            "path": path,
            "base": texts[0],
            "ours": texts[1],
            "theirs": texts[2],
        }
        if pair is not None:
            rec["pair"] = pair
        cases.append(rec)

    for recipe, langs in CODE_RECIPES:
        for lang in langs:
            for _ in range(args.per_recipe):
                base, ours, theirs, fam, feat = recipe(rng, lang)
                emit(
                    tuple(render(m) for m in (base, ours, theirs)),
                    path_for(rng, lang),
                    fam,
                    feat,
                    lang,
                    recipe.__name__,
                )
    for recipe in ROUTING_RECIPES:
        for lang in ALL3:
            for _ in range(max(2, args.per_recipe // 4)):
                b, o, t, fam, feat = recipe(rng, lang)
                emit((b, o, t), path_for(rng, lang), fam, feat, lang, recipe.__name__)
    for recipe in DATA_RECIPES:
        for lang in ("json", "toml"):
            for _ in range(args.per_recipe):
                b, o, t, fam, feat = recipe(rng, lang)
                emit((b, o, t), path_for(rng, lang), fam, feat, lang, recipe.__name__)
    for _ in range(args.layout):
        recipe, lang = rng.choice(LAYOUT_SOURCES), rng.choice(ALL3)
        base, ours, theirs, _, _ = recipe(rng, lang)
        texts, feat = layout_variant(
            rng, tuple(render(m) for m in (base, ours, theirs))
        )
        emit(texts, path_for(rng, lang), "F1", feat, lang, recipe.__name__ + "+layout")
    groups = 0
    for recipe, langs in PHASE_C_RECIPES:
        for lang in langs:
            made = 0
            while made < args.per_recipe:
                group = recipe(rng, lang)
                path = path_for(rng, lang)
                pair = None
                if len(group) > 1:
                    pair = f"g{groups:05d}"
                    groups += 1
                for b, o, t, fam, feat in group:
                    size = max(len(x.encode("utf-8")) for x in (b, o, t))
                    if size > PHASE_C_MAX_BYTES:
                        raise SystemExit(
                            f"{recipe.__name__} ({lang}): an input of {size} bytes"
                        )
                    emit((b, o, t), path, fam, feat, lang, recipe.__name__, pair)
                made += len(group)
    Path(args.out).write_text(json.dumps(cases), encoding="utf-8")
    print(f"{len(cases)} candidate cases")


if __name__ == "__main__":
    main()
