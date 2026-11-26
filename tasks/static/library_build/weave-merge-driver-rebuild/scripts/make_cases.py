"""Generate candidate merge triples for the Weave rebuild: typed, family-tagged edits to synthetic modules.

Each recipe builds a base module, applies one edit per side, and tags the case with the family and
feature it is meant to exercise. Candidates are filtered later (stubs, determinism, the original's
own behaviour); this script only proposes. Output: a JSON list of cases. Deterministic per seed.
The seed and the output are private and never enter the public repository.

Usage: python3 -I make_cases.py --seed N --per-recipe K --out cases.json
"""

from __future__ import annotations

import argparse
import copy
import json
import random
from dataclasses import dataclass, field

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
    """F1: ours adds a function after f_k; theirs edits f_{k+1}'s first body line."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(3, 6), used)
    k = rng.randrange(len(base.items) - 1)
    ours, theirs = sides(base)
    ours.items.insert(k + 1, func(rng, lang, ident(rng, lang, used)))
    edit_line(rng, theirs.items[k + 1], 1)
    return base, ours, theirs, "F1", "disjoint.insert_next_to_edit"


def r_delete_vs_next_edit(rng, lang):
    """F1: ours deletes f_k; theirs edits f_{k+1}'s first body line."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(3, 6), used)
    k = rng.randrange(len(base.items) - 1)
    ours, theirs = sides(base)
    del ours.items[k]
    edit_line(rng, theirs.items[k + 1], 1)
    return base, ours, theirs, "F1", "disjoint.delete_next_to_edit"


def r_both_add_same_anchor(rng, lang):
    """F2: both sides add a different function after the same anchor."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(2, 5), used)
    k = rng.randrange(len(base.items))
    ours, theirs = sides(base)
    ours.items.insert(k + 1, func(rng, lang, ident(rng, lang, used)))
    theirs.items.insert(k + 1, func(rng, lang, ident(rng, lang, used)))
    return base, ours, theirs, "F2", "placement.same_anchor"


def r_both_add_two_vs_one(rng, lang):
    """F2: ours adds two functions after one anchor, theirs one."""
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
    """F2: ours swaps two neighbours; theirs edits the first of them."""
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
    """F3: ours renames f and edits its last line; theirs edits f's first body line."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(2, 5), used)
    k = rng.randrange(len(base.items))
    ours, theirs = sides(base)
    rename_item(ours.items[k], ident(rng, lang, used))
    edit_line(rng, ours.items[k], len(ours.items[k].lines) - (2 if lang != "py" else 1))
    edit_line(rng, theirs.items[k], 1)
    return base, ours, theirs, "F3", "rename.edited_body"


def r_rename_vs_rewrite(rng, lang):
    """F3 near-miss: ours renames f and rewrites its whole body (far below the thresholds: not a rename)."""
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
    """F4: both sides edit neighbouring lines of one function; half also add at one anchor elsewhere."""
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
    """F5: both sides add a different method at the end of one class."""
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
    """F6: both sides add a different key at the same point of one literal."""
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
    """F6: both sides add a different case at the same point of one switch."""
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
    """F7: both sides add a different import at the end of the import block."""
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
    """F8 refusal: both sides add the same case label at distant points of one switch."""
    cases = sorted(rng.sample(range(1, 40), 6))
    base, pos, name = with_switch(rng, lang, cases)
    new = rng.choice(range(40, 80))
    ours, theirs = sides(base)
    ours.items[pos] = switch_func(lang, name, cases[:1] + [new] + cases[1:])
    theirs.items[pos] = switch_func(lang, name, cases[:5] + [new] + cases[5:])
    return base, ours, theirs, "F8", "gate.keys_case_label"


def r_gate_dual_cases(rng, lang):
    """F8 accept-dual: both sides add different case labels at one point."""
    base, ours, theirs, _, _ = r_switch_both_add_same_point(rng, lang)
    return base, ours, theirs, "F8", "gate.dual_case_labels"


def r_gate_dup_key(rng, lang):
    """F8 refusal: both sides add the same key at distant points of one literal."""
    keys = keyed(rng, 6)
    base, pos, name = with_collection(rng, lang, keys)
    a = rng.choice([w for w in WORDS if w not in dict(keys)])
    ours, theirs = sides(base)
    ours.items[pos] = COLLECTION[lang](name, keys[:1] + [(a, 7)] + keys[1:])
    theirs.items[pos] = COLLECTION[lang](name, keys[:5] + [(a, 7)] + keys[5:])
    return base, ours, theirs, "F8", "gate.keys_literal"


def r_gate_dual_keys(rng, lang):
    """F8 accept-dual: both sides add different keys at one point."""
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
    """F8 refusal: ours adds a function NAME at the top, theirs a variable NAME at the bottom."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(4, 6), used)
    name = ident(rng, lang, used)
    ours, theirs = sides(base)
    ours.items.insert(0, func(rng, lang, name))
    theirs.items.append(binding(lang, name, rng.randint(1, 9)))
    return base, ours, theirs, "F8", "gate.bindings_name"


def r_gate_dual_names(rng, lang):
    """F8 accept-dual: a function and a variable with different names added after one anchor."""
    used: set[str] = set()
    base = module(rng, lang, rng.randint(3, 5), used)
    k = rng.randrange(len(base.items))
    ours, theirs = sides(base)
    ours.items.insert(k + 1, func(rng, lang, ident(rng, lang, used)))
    theirs.items.insert(k + 1, binding(lang, ident(rng, lang, used), rng.randint(1, 9)))
    return base, ours, theirs, "F8", "gate.dual_names"


def r_gate_dup_import(rng, lang):
    """F8 refusal: both sides add the same import, one at the start of the block, one at the end."""
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
    """F8 refusal: ours removes an import and its only use; theirs adds a new use far away."""
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
    """F8 accept-dual: different imports added at one point."""
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
    """F8 refusal (Go): both sides insert a constant ahead of later ones, at distant points."""
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
    """F1 routing: a NUL byte at offset 8,001-8,191 of ours: the driver exits 2; git still merges."""
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
    """F1 routing dual: a NUL byte after offset 8,192 does not make the file binary."""
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
    """F1 routing: ours carries one byte that is not UTF-8 (in a comment): status 2."""
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
    """F1 routing: theirs already carries both marker strings: it is written back, status 1."""
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
    """F9 (D6, Python): ours re-indents one function's body (layout only); theirs edits a line in it."""
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
    """F10: both sides add a different key at one point of one object or table."""
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
    """F10: both sides edit the values of two neighbouring keys."""
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
    """F8 refusal (data): both sides add the same key at distant points of one object or table."""
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
    """F8 accept-dual (data): different keys added at one point."""
    b, o, t, _, _ = r_data_both_add_same_point(rng, lang)
    return b, o, t, "F8", "gate.dual_data_keys"


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

    def emit(texts, path, family, feature, lang, recipe):
        cases.append(
            {
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
        )

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
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(cases, fh)
    print(f"{len(cases)} candidate cases")


if __name__ == "__main__":
    main()
