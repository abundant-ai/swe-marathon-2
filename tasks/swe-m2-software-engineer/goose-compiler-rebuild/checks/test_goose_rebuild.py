"""Development checks: the original is built hardened, identically by both images and the reference
solution; the verifier counts what a submission does as that submission's failed cases; the cases are
reproducible, unknown to the agent, built so that their answers differ from upstream's, and their format
inputs keep every token and carry comments."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
STEP = TASK / "steps" / "01-rebuild-compiler"
SCRIPTS = TASK / "scripts"
RUNNER = STEP / "tests" / "verifier" / "runcases.py"
RECORDER = STEP / "tests" / "verifier" / "recorder.py"
HARDENING = TASK / "common" / "hardening"

RUN_PROGRAM = ("import std;\n// prints the sum\nfn main() {\n    var total = 0;\n    for i in 0..{n} {\n        total += i * 2;\n"
               "    }\n    print(total);\n}\n")
ERROR_PROGRAM = ("// error: expected a value of type i32, got const u8[:]\n// the literal is text\nfn main() {\n"
                 "    let x: i32 = \"a{n}\";\n    print(x);\n}\n")
SHOWN = ("fn shown_helper(shown_value: i64) -> i64 {\n    return shown_value * 3;\n}\n\nfn main() {\n"
         "    let shown_total = shown_helper(4);\n    let shown_more = shown_total + 1;\n    print(shown_total, shown_more);\n}\n")


def visible(key: str) -> bool:
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF < 0.15


def private_name(stem: str, directory: str) -> str:
    """A file name in test/<directory> whose key lands on the private side."""
    return next(f"{stem}{n}.goose" for n in range(100) if not visible(f"test/{directory}/{stem}{n}.goose"))


def checkout(tmp_path: Path) -> Path:
    """A small upstream tree with every kind of program the generator takes, and three private
    programs that shipped files also hold: in a design note, in the README and in the standard library."""
    root = tmp_path / "goose"
    for directory in ("test/codegen", "test/typing", "test/stdlib", "test/syntax/ns", "test/errors_tc", "test/expected",
                      "test/gfx", "bench/goose", "samples", "docs/design", "stdlib"):
        (root / directory).mkdir(parents=True, exist_ok=True)
    for index in range(40):
        directory = "codegen" if index % 2 else "typing"
        (root / "test" / directory / f"prog{index}.goose").write_text(RUN_PROGRAM.replace("{n}", str(index + 3)))
        (root / "test" / "expected" / f"prog{index}.out").write_text("0\n")
        (root / "test" / "errors_tc" / f"bad{index}.goose").write_text(ERROR_PROGRAM.replace("{n}", str(index)))
    for index in range(12):
        (root / "test" / "stdlib" / f"lib{index}.goose").write_text(
            f"import std;\nimport json;\n\nfn main() {{\n    let text = \"[{index}, 2]\";\n    print(text.len);\n}}\n")
        (root / "test" / "expected" / f"lib{index}.out").write_text("6\n")
        (root / "bench" / "goose" / f"work{index}.goose").write_text(
            f"import rng;\n\nlet N = {100000 + index}; // BENCH_N\n\nfn main() {{\n    var x: u64 = {7 + index};\n"
            f"    for i in 0..N {{ x = xs_next(x); }}\n    print(x);\n}}\n")
    (root / "bench" / "goose" / "rng.goose").write_text("fn xs_next(x: u64) -> u64 {\n    var v = x;\n    v ^= v << 13;\n    v\n}\n")
    (root / "test" / "typing" / "warned.goose").write_text("// warning: unused\nfn main() {\n    let unused = 3;\n}\n")
    (root / "test" / "expected" / "warned.out").write_text("")
    (root / "test" / "syntax" / "uses_tally.goose").write_text("import ns.tally;\n\nfn main() {\n    print(tally_count(3));\n}\n")
    (root / "test" / "syntax" / "ns" / "tally.goose").write_text("fn tally_count(n: i64) -> i64 {\n    return n + 1;\n}\n")
    (root / "test" / "expected" / "uses_tally.out").write_text("4\n")
    (root / "test" / "gfx" / "draw.goose").write_text("import gfx;\nfn main() {}\n")
    (root / "test" / "codegen" / "skip.goose").write_text("// no-jit\nfn main() {}\n")
    (root / "test" / "codegen" / "threads.goose").write_text("thread_fn w() {}\nfn main() { thread_wait(thread_spawn(w)); }\n")
    (root / "test" / "expected" / "threads.out").write_text("")
    (root / "test" / "expected" / "skip.out").write_text("")
    # Three private programs that a shipped file also holds, comments and layout aside.
    leaked = {"typing": ("design_marker", "docs/design/notes.md"), "codegen": ("readme_marker", "README.md")}
    for directory, (marker, shipped) in leaked.items():
        name = private_name(marker, directory)
        program = f"fn main() {{\n    let {marker} = 5;\n    print({marker} + 1);\n}}\n"
        (root / "test" / directory / name).write_text(program)
        (root / "test" / "expected" / name.replace(".goose", ".out")).write_text("6\n")
        (root / shipped).write_text(f"Notes.\n\n```goose\n// the original\n{program.replace('    ', '  ')}```\n")
    name = private_name("stdlib_marker", "typing")
    (root / "test" / "typing" / name).write_text("fn main() {\n    let stdlib_marker = 2;\n    print(stdlib_marker);\n}\n")
    (root / "test" / "expected" / name.replace(".goose", ".out")).write_text("2\n")
    (root / "stdlib" / "std.goose").write_text("// std\nfn helper_in_std(x: i64) -> i64 { x }\nfn main() {\n    let stdlib_marker = 2;\n"
                                               "    print(stdlib_marker);\n}\n")
    for module in ("json", "os", "ffi"):
        (root / "stdlib" / f"{module}.goose").write_text(f"// {module}\nfn {module}_entry() {{}}\n")
    kostya = root / "bench" / "kostya" / "goose" / "src"
    kostya.mkdir(parents=True)
    (kostya / "main.goose").write_text(
        "import std;\nimport os;\nimport bench;\nimport helper;\nimport small;\n\nfn dispatch(b: Bench&) -> u32, bool {\n"
        "    let n = b.name;\n    if n == \"Small::One\" || n == \"Small::Two\" {\n        var s = small::new_small();\n"
        "        return execute(b, s, small::prepare, small::run, small::checksum), true;\n    }\n    return 0, false;\n}\n\n"
        "fn main() { run_main(dispatch); }\n")
    (kostya / "small.goose").write_text(
        "namespace small;\n\nimport std;\nimport bench;\nimport helper;\n\nstruct Small { total: u32 }\n\n"
        "fn new_small() -> Small { Small { total: config_i64(\"Small::One\", \"size\") as u32 } }\n\n"
        "fn prepare(s: Small&) { s.total += 1; }\n\nfn run(s: Small&, iteration_id: i64) {\n    s.total += 7;\n}\n\n"
        "fn checksum(s: Small&) -> u32 { s.total }\n")
    (kostya / "helper.goose").write_text("import std;\n\nfn reset() {}\n\n// --- exact fixed-point float text ----\n\n"
                                         "extern fn frexp(x: f64, e: i32&) -> f64;\n")
    (kostya / "bench.goose").write_text("import os;\n")
    (root / "samples" / "hello.goose").write_text(SHOWN)
    (root / "docs" / "reference.md").write_text(
        "Text.\n\n```goose\n" + SHOWN.replace("shown_", "shown_doc_") + "```\n\n<!-- fragment -->\n```goose\nlet y = 3;\n```\n")
    return root


def generate(tmp_path: Path, seed: int, root: Path | None = None) -> tuple[list[dict], list[dict], dict]:
    root = root or (tmp_path / "goose" if (tmp_path / "goose").exists() else checkout(tmp_path))
    private, visible_out = tmp_path / f"p{seed}.json", tmp_path / f"v{seed}.json"
    done = subprocess.run([sys.executable, "-B", str(SCRIPTS / "make_cases.py"), str(root), "--count", "240", "--seed", str(seed),
                           "--visible", "40", "--out-private", str(private), "--out-visible", str(visible_out)],
                          capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]
    return json.loads(private.read_text())["cases"], json.loads(visible_out.read_text())["cases"], json.loads(done.stdout)


def scripts_call(code: str, *args: str) -> str:
    """Run `code` with the task's scripts importable, in a process of its own (another task's
    scripts have the same module names)."""
    done = subprocess.run([sys.executable, "-B", "-c", f"import sys; sys.path.insert(0, {str(SCRIPTS)!r})\n" + code, *args],
                          capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]
    return done.stdout


def inputs(case: dict) -> list[str]:
    return list(case["files"].values()) + ([case["stdin"]] if case["stdin"] else [])


# ---------------------------------------------------------------- cases

def test_cases_are_reproducible_and_carry_comments_only_where_formatted(tmp_path):
    private, visible_cases, summary = generate(tmp_path, 5)
    again, _, _ = generate(tmp_path, 5)
    assert private == again and generate(tmp_path, 6)[0] != private
    assert len(private) == 200 and len(visible_cases) == 40
    assert all(case["id"].startswith("P") for case in private) and all(case["id"].startswith("E") for case in visible_cases)
    assert {"run", "library", "modules", "rejected", "check", "format", "cli"} <= {case["kind"] for case in private}
    assert all("kind" not in case and "upstream" not in case for case in visible_cases)
    for case in private + visible_cases:
        texts = inputs(case)
        if case["argv"][0] == "format" and case["argv"][1:2] != ["--help"] and "missing.goose" not in case["argv"]:
            assert all("//" in text or "/*" in text for text in texts), case
        else:  # the error tests name their errors in comments, and run tests their output
            assert not any("//" in text or "/*" in text for text in texts + [text for variant in case.get(
                "record", {}).get("variants", []) for text in variant.values()]), case
        assert not any(re.search(r"\b(extern|thread_fn|thread_spawn)\b|import (gfx|os|ffi)\b", text) for text in texts)
        assert not any("no-jit" in text for text in texts)
    assert any(len(case["files"]) > 1 and case["kind"] == "modules" for case in private)
    assert all(case["argv"][2:4] == ["--diagnostics", "json"] or case["argv"] == ["run", "main.goose"]
               for case in private if case["kind"] == "rejected")
    rejected = [case for case in private + visible_cases if case["argv"][:2] == ["run", "main.goose"] and
                any(text.count("\"a") for text in case["files"].values())]
    assert sum(case["argv"] == ["run", "main.goose"] for case in rejected) <= max(1, len(rejected) // 10)
    assert not any("--" in case["argv"] for case in private + visible_cases), "no program arguments: no program reads them"
    scaled = json.loads(scripts_call(textwrap.dedent("""
        import json, random, make_cases as mc
        rng = random.Random(1)
        print(json.dumps([mc.scale_bench(f"let {name} = {value}; // BENCH_N\\n", rng)
                          for name, value in (("N", 8000000), ("DEPTH", 20), ("W", 2048), ("N", 250000))]))
    """)))
    values = [int(re.search(r"= (\d+);", line).group(1)) for line in scaled]
    assert 20000 <= values[0] <= 80000 and 11 <= values[1] <= 14 and values[2] in (64, 128) and values[3] in (2500, 1250, 1000)
    assert all(line.endswith("// BENCH_N\n") for line in scaled)


def test_no_private_case_is_built_on_a_shipped_program_or_holds_a_shipped_text(tmp_path):
    private, visible_cases, summary = generate(tmp_path, 7)
    excluded = summary["excluded"]
    assert sorted(re.sub(r"\d+\.goose$", "", Path(key).name) for key in excluded) == ["design_marker", "readme_marker",
                                                                                    "stdlib_marker"]
    texts = [text for case in private for text in inputs(case)]
    assert not any(marker in text for text in texts for marker in ("design_marker", "readme_marker", "stdlib_marker"))
    assert not any("shown_" in text for text in texts), "a variant of a shipped program reached a private case"
    assert summary["private_unchanged_from_upstream"] == {}


def test_the_leak_check_refuses_a_known_input():
    out = scripts_call(textwrap.dedent("""
        import json, make_cases as mc
        program = "fn main() {\\n    print(1);\\n}\\n"
        case = lambda i, text: {"id": i, "files": {"main.goose": text}, "argv": ["run", "main.goose"], "stdin": None}
        shipped = mc.normalise("Docs.\\n```goose\\n// a comment\\nfn main() {\\n  print(1);\\n}\\n```\\n")
        print(json.dumps([mc.leaks([case("P1", program)], [], shipped, set()),
                          mc.leaks([case("P2", "fn main() { print(2); }\\n")], [case("E1", "fn main() {print(2);}")], "", set()),
                          mc.leaks([case("P3", "fn main() { print(3); }\\n")], [case("E2", program)], shipped, set())]))
    """))
    assert json.loads(out) == [["P1"], ["P2"], []]


def test_format_inputs_keep_every_token_and_renames_are_consistent():
    out = scripts_call(textwrap.dedent("""
        import json, random, make_cases as mc
        text = ("fn sum(xs: i64[:]) -> i64 {\\n    var t = 0;\\n    for x in xs { t += x; }\\n    if t >= 10 && t != 12 { t -= 1; }\\n"
                "    return t;\\n}\\nfn main() {\\n    let v = [1, 2, 3];\\n    print(sum(v[..]), 1.5e3, 'a', \\"s // t\\");\\n    let r = 0..3;\\n}\\n")
        results = []
        for seed in range(200):
            rng = random.Random(seed)
            commented = mc.add_comments(rng, text, 4)
            moved = mc.disturb(rng, commented)
            renamed, mapping = mc.rename(rng, {"main.goose": text}, {"print", "main"}, 3)
            results.append([mc.code(mc.lex(moved)) == mc.code(mc.lex(text)), moved != commented,
                            sum(t.kind == "comment" for t in mc.lex(commented)) > 0, mapping,
                            [(t.kind, mapping.get(t.text, t.text)) for t in mc.lex(text)] == [(t.kind, t.text) for t in mc.lex(renamed["main.goose"])],
                            mc.shift(rng, text) != text and mc.code(mc.lex(mc.shift(random.Random(seed), text))) == mc.code(mc.lex(text))])
        print(json.dumps(results))
    """))
    results = json.loads(out)
    assert all(same and changed and commented and consistent and shifted for same, changed, commented, _, consistent, shifted in results)
    names = {new for *_, mapping, _, _ in results for new in mapping.values()}
    assert names and not names & {"sum", "xs", "t", "x", "v", "r", "print", "main", "fn", "let"}
    assert all(set(mapping) <= {"sum", "xs", "t", "x", "v", "r"} for *_, mapping, _, _ in results)
    assert not any(re.search(r"\d", name) for name in names), "ordinary names, no numbered words"


def test_inputs_look_like_code_people_write(tmp_path):
    """No marks of a generator: no numbered names, no comment upstream's runner reads, no tabs but
    in a file indented with tabs throughout, block comments only as argument labels, no input
    starting with a blank line."""
    private, visible_cases, summary = generate(tmp_path, 11)
    for case in private + visible_cases:
        variants = [text for variant in case.get("record", {}).get("variants", []) for text in variant.values()]
        for text in inputs(case) + variants:
            assert not re.search(r"//\s*(error|warning):|//\s*(runtime-define|bce):|// spec ", text), case["id"]
            assert not text.startswith("\n"), case["id"]
            assert not re.search(r"\b(amber|basil|cedar|yarrow|zircon)\d+\b", text, re.I), case["id"]
            tabbed = [line for line in text.split("\n") if line.startswith("\t")]
            spaced = [line for line in text.split("\n") if line.startswith("    ")]
            assert not (tabbed and spaced), case["id"]
            assert all(re.fullmatch(r"/\*\w+=\*/", block) for block in re.findall(r"/\*.*?\*/", text)), case["id"]
        for phrase in ("edge case", "checked by hand", "worth a second look", "same as before", "nothing special here"):
            assert not any(phrase in text for text in inputs(case)), (case["id"], phrase)
    assert summary["fingerprints"]["private"]["runner_markers"] == 0


def test_literal_and_string_edits_leave_asserts_sizes_and_indexes_alone():
    out = scripts_call(textwrap.dedent("""
        import json, random, make_cases as mc
        text = ("fn main() {\\n    var tab: i64[4] = [0; 4];\\n    assert(tab.len == 4);\\n    let k = tab[2] << 3;\\n"
                "    for i in 0..10 { print(i * 7, \\"items left\\"); }\\n    let msg = \\"internal word\\";\\n}\\n")
        spots = sorted(t.text + "@" + str(t.start) for t in mc.literal_spots(text))
        strings = {mc.mutate_string(random.Random(seed), text) for seed in range(40)}
        print(json.dumps([spots, sorted(strings)]))
    """))
    spots, strings = json.loads(out)
    assert [spot.split("@")[0] for spot in spots] == ["0", "10", "7"], "a loop's bounds and a printed product only"
    assert all("internal word" in text and "assert(tab.len == 4)" in text for text in strings)
    assert all('"items left"' not in text and re.search(r'"(\w+) left"|"items (\w+)"', text) for text in strings)


def test_run_and_check_cases_carry_variants_for_the_recorder(tmp_path):
    private, visible_cases, _ = generate(tmp_path, 13)
    runs = [case for case in private if case["kind"] in ("run", "library", "modules") and "record" in case]
    assert len(runs) > 20
    for case in runs:
        plan = case["record"]
        assert plan["want"] == "same" and plan["variants"] and set(plan["variants"][-1]) == set(case["files"])
        assert case["files"] != plan["variants"][-1], "the case's own files are an edit of the base"
        assert isinstance(plan["complete"], bool)
    broken = [case for case in private if case["kind"] == "check" and "record" in case]
    assert broken and all(case["record"]["want"] == "diagnostics" for case in broken)
    assert all("upstream_messages" in case for case in private if case["kind"] == "rejected")
    workspaces = [case for case in private + visible_cases if case["argv"][:2] == ["format", "--check"]]
    marked = [name for case in workspaces for name in case.get("record", {}).get("formatted", [])]
    assert all(name in case["files"] for case in workspaces for name in case.get("record", {}).get("formatted", []))
    assert workspaces and marked
    kostya = [case for case in private + visible_cases if "bench.goose" in case["files"]]
    assert kostya and all({"helper.goose", "small.goose"} <= set(case["files"]) for case in kostya)
    assert all("clock" not in case["files"]["bench.goose"] and "extern" not in case["files"]["helper.goose"] for case in kostya)


def test_families_split_together_and_every_library_module_and_warnings_reach_both_sides():
    out = scripts_call(textwrap.dedent("""
        import json, make_cases as mc
        print(json.dumps([mc.family("test/errors_tc/shrink_class_copy_a.goose"), mc.family("test/errors_tc/shrink_class_copy_b.goose"),
                          mc.family("test/stdlib/stdlib_csv.goose"), mc.family("test/stdlib/stdlib_json.goose"),
                          mc.family("bench/goose/lru_indices.goose"), mc.family("bench/goose/lru.goose"),
                          mc.family("bench/kostya/goose/src#json_parse_dom"), mc.family("bench/kostya/goose/src#json_generate")]))
    """))
    a, b, csv, json_, lru1, lru2, dom, gen = json.loads(out)
    assert a == b and csv != json_ and lru1 == lru2 and dom == gen


def test_the_tokenizer_never_lets_a_layout_change_split_an_operator():
    out = scripts_call(textwrap.dedent("""
        import json, make_cases as mc
        tokens = ["->", "=>", "==", "!=", "<=", ">=", "<<=", ">>=", "&&", "||", "+=", "-=", "::", "..", ".==", ".!=", "++", "--"]
        lexed = [[t.text for t in mc.lex(f"a {op} b")] for op in tokens]
        glued = [mc._glues(*mc.lex("- >")), mc._glues(*mc.lex("= =")), mc._glues(*mc.lex("a (")), mc._glues(*mc.lex("1 e5")),
                 mc._glues(*mc.lex("/ /* c */")), mc._glues(*mc.lex("x // c"))]
        print(json.dumps([lexed, glued, [t.kind for t in mc.lex('let s = \\"\\"\\"\\n  a // b\\n  \\"\\"\\";')]]))
    """))
    lexed, glued, raw = json.loads(out)
    assert all(parts[1] == op for parts, op in zip(lexed, ["->", "=>", "==", "!=", "<=", ">=", "<<=", ">>=", "&&", "||", "+=",
                                                           "-=", "::", "..", ".==", ".!=", "++", "--"]))
    assert glued == [False, False, True, False, False, True]
    assert raw == ["keyword", "ident", "punct", "string", "punct"]


def test_command_line_cases_are_one_per_behaviour():
    out = scripts_call("import json, make_cases as mc; print(json.dumps([mc.CLI_PRIVATE, mc.CLI_VISIBLE, mc.KINDS]))")
    private, visible_cases, kinds = json.loads(out)
    assert len({tuple(argv) for argv in private}) == len(private) and len(private) <= 22
    aliases = [["--version"], ["help", "help"], ["run", "--help"], ["format", "--help"], ["run", "main.goose", "-o", "out.c"]]
    assert not any(argv in private for argv in visible_cases + aliases), "nothing the examples show, no alias, no -o"
    assert abs(sum(share for _, share in kinds) - 1) < 1e-9 and dict(kinds)["format"] <= 0.08


# ---------------------------------------------------------------- verifier

def run_verifier(tmp_path: Path, script: str, cases: list[dict], expected: dict, case_sec: float = 2,
                 output_limit: int | None = None) -> dict:
    """grade() of the real verify.py, in a process of its own, with the workspace under tmp_path and
    no privilege drop (macOS and CI runners have no setpriv): what the submission can do to its
    workspace and its output is the same."""
    program = tmp_path / "goose"
    program.write_text("#!/bin/sh\n" + script)
    program.chmod(0o755)
    private = tmp_path / "private"
    private.mkdir(exist_ok=True)
    (private / "cases.json").write_text(json.dumps({"cases": cases}))
    (private / "expected.json").write_text(json.dumps(expected))
    driver = textwrap.dedent(f"""
        import json, sys
        from pathlib import Path
        sys.path.insert(0, {str(STEP / 'tests')!r})
        import verify
        verify.runcases.WORKSPACE = Path({str(tmp_path / 'tmp' / 'goose-case')!r})
        verify.runcases.HOME = Path({str(tmp_path / 'tmp' / 'goose-home')!r})
        verify.runcases.TEMP = Path({str(tmp_path / 'tmp' / 'goose-tmp')!r})
        verify.runcases.CASE_SEC = {case_sec}
        if {output_limit!r} is not None:
            verify.runcases.OUTPUT_LIMIT = {output_limit!r}
        print(json.dumps(verify.grade(Path({str(program)!r}), Path({str(private)!r}), [], None)))
    """)
    (tmp_path / "tmp").mkdir(exist_ok=True)
    done = subprocess.run([sys.executable, "-B", "-c", driver], capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


def plain_cases(argvs: list[list[str]], kinds: list[str] | None = None) -> tuple[list[dict], dict]:
    cases = [{"id": f"P{i}", "files": {"main.goose": "fn main() {}\n"}, "argv": argv, "stdin": None} for i, argv in enumerate(argvs)]
    for case, kind in zip(cases, kinds or []):
        case["kind"] = kind
    return cases, {case["id"]: {"exit": 0, "stdout": "ok\n"} for case in cases}


def verifier_call(code: str) -> object:
    """The JSON a snippet prints with the verifier importable, in a process of its own (another
    task's checks have a package named `verifier` too)."""
    done = subprocess.run([sys.executable, "-B", "-c", f"import sys; sys.path.insert(0, {str(STEP / 'tests')!r})\n" + code],
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_many_slow_runs_do_not_stop_the_count(tmp_path):
    cases, expected = plain_cases([["slow"]] * 65 + [["fast"]] * 5)
    metrics = run_verifier(tmp_path, 'case "$1" in slow) exec sleep 5;; esac\necho ok\n', cases, expected, case_sec=0.05)
    assert metrics["cases_run"] == 70 and metrics["timeouts"] == 65 and metrics["cases_passed"] == 5
    assert metrics["reward"] == round(5 / 70, 6) and metrics["stopped"] is None and not metrics["notes"]


def test_a_swapped_or_stuck_workspace_is_a_failed_case_not_an_evaluation_error(tmp_path):
    target = tmp_path / "elsewhere"
    target.mkdir()
    script = textwrap.dedent(f"""\
        case "$1" in
          swap) mv "$PWD" "$PWD.moved" && ln -s {target} "$PWD";;
          stuck) mkdir -p locked/inner && chmod 0 locked;;
        esac
        echo ok
    """)
    cases, expected = plain_cases([["a"], ["swap"], ["b"], ["c"], ["stuck"], ["d"]])
    metrics = run_verifier(tmp_path, script, cases, expected)
    assert metrics["cases_run"] == 6 and metrics["cases_passed"] == 5, metrics
    assert metrics["setup_errors"] == 1 and list(target.iterdir()) == [], "the verifier wrote through the submission's link"
    for locked in tmp_path.rglob("locked"):
        locked.chmod(0o755)


def test_output_is_read_up_to_a_bound_and_compared_as_bytes(tmp_path):
    cases, expected = plain_cases([["flood"], ["ok"], ["bad"], ["other"]])
    expected["P2"] = {"exit": 0, "stdout": b"\x80\n".decode("utf-8", "surrogateescape")}
    expected["P3"] = {"exit": 0, "stdout": b"\xff\n".decode("utf-8", "surrogateescape")}
    script = "case \"$1\" in flood) head -c 20000000 /dev/zero; exit 0;; bad|other) printf '\\200\\n'; exit 0;; esac\necho ok\n"
    metrics = run_verifier(tmp_path, script, cases, expected, output_limit=4096)
    assert metrics["output_limits"] == 1 and metrics["cases_passed"] == 2, metrics
    assert metrics["failed_sample"] == ["P0", "P3"], "two different invalid bytes compared equal"


def test_metrics_count_each_kind_and_the_time_runs_took(tmp_path):
    cases, expected = plain_cases([["a"], ["b"], ["slow"], ["c"]], kinds=["run", "run", "check", "format"])
    metrics = run_verifier(tmp_path, 'case "$1" in slow) exec sleep 5;; b) echo no; exit 0;; esac\necho ok\n', cases, expected,
                           case_sec=1.0)
    assert metrics["by_kind"] == {"run": {"total": 2, "run": 2, "passed": 1, "failed": 1},
                                  "check": {"total": 1, "run": 1, "passed": 0, "failed": 1},
                                  "format": {"total": 1, "run": 1, "passed": 1, "failed": 0}}
    assert metrics["cases_failed"] == 2 and metrics["timeouts"] == 1
    assert 1.0 <= metrics["seconds_max"] < 3 and metrics["seconds_max"] <= metrics["seconds_total"]


def test_every_run_gets_the_same_limits_and_its_own_stack(tmp_path):
    report = verifier_call(textwrap.dedent(f"""
        import json, sys
        from pathlib import Path
        from verifier import runcases
        runcases.WORKSPACE = Path({str(tmp_path / 'goose-case')!r})
        runcases.HOME, runcases.TEMP = Path({str(tmp_path / 'goose-home')!r}), Path({str(tmp_path / 'goose-tmp')!r})
        code = "import resource, json; print(json.dumps([resource.getrlimit(r) for r in "
        code += "(resource.RLIMIT_STACK, resource.RLIMIT_FSIZE, resource.RLIMIT_CORE)]))"
        case = {{"id": "P1", "files": {{}}, "argv": ["-c", code], "stdin": None}}
        got = runcases.run_case([sys.executable], case)
        print(json.dumps([json.loads(got["stdout"]), [runcases.LIMITS[r] for r in (runcases.resource.RLIMIT_STACK,
              runcases.resource.RLIMIT_FSIZE, runcases.resource.RLIMIT_CORE)]]))
    """))
    limits, wanted = report
    assert [soft for soft, _ in limits] == wanted and [hard for _, hard in limits] == wanted


def test_a_set_id_file_gains_nothing(tmp_path):
    """The submission loses its set-id bits and its write permission before anything runs, and the
    privilege check refuses a process that keeps no_new_privs off, an id, a group or a capability."""
    top = tmp_path / "rebuild"
    (top / "lib").mkdir(parents=True)
    for name, mode in (("goose", 0o4755), ("lib/helper", 0o2775), ("lib/data", 0o4666), ("lib", 0o1777)):
        (top / name).touch() if name != "lib" else None
        (top / name).chmod(mode)
    os.mkfifo(top / "lib" / "pipe")
    (top / "link").symlink_to("/etc/passwd")
    report = verifier_call(textwrap.dedent(f"""
        import json, os
        from pathlib import Path
        import verify
        verify.seal(Path({str(top)!r}), (os.getuid(), os.getgid()))
        status = "Uid:\\t65534\\t65534\\t65534\\t65534\\nGid:\\t65534\\t65534\\t65534\\t65534\\nGroups:\\t\\nNoNewPrivs:\\t1\\n"
        status += "CapPrm:\\t0000000000000000\\nCapEff:\\t0000000000000000\\nCapAmb:\\t0000000000000000\\n"
        limits = "Max processes             512                  512                  processes\\n"
        limits += "Max file size             268435456            268435456            bytes\\n"
        limits += "Max core file size        0                    0                    bytes\\n"
        good = verify.sandbox_problems(status, limits, (65534, 65534))[0]
        bad = [verify.sandbox_problems(status.replace(old, new), limits, (65534, 65534))[0] for old, new in
               (("NoNewPrivs:\\t1", "NoNewPrivs:\\t0"), ("Uid:\\t65534\\t65534", "Uid:\\t65534\\t0"), ("Groups:\\t", "Groups:\\t0"),
                ("CapEff:\\t0000000000000000", "CapEff:\\t0000000000000400"))]
        bad.append(verify.sandbox_problems(status, limits.replace("512 ", "9999"), (65534, 65534))[0])
        # A kernel whose status file has no NoNewPrivs line (gVisor's may not): prctl decides.
        unlisted = status.replace("NoNewPrivs:\\t1\\n", "")
        by_prctl = [verify.sandbox_problems(unlisted + f"PrctlNoNewPrivs:\\t{{value}}\\n", limits, (65534, 65534))[0]
                    for value in (1, 0, -1)] + [verify.sandbox_problems(unlisted, limits, (65534, 65534))[0]]
        import subprocess, sys
        probed = subprocess.run([sys.executable, "-I", "-c", verify.NNP_PROBE], capture_output=True, text=True).stdout
        print(json.dumps([good, bad, "--no-new-privs" in Path(verify.__file__).read_text(), by_prctl,
                          (probed.splitlines() or [""])[-1].split(":")[0], "Uid:" in probed]))
    """))
    good, bad, no_new_privs, by_prctl, last, status_first = report
    assert good == [] and all(problems for problems in bad) and no_new_privs
    assert by_prctl[0] == [] and all(problems == ["no_new_privs is not set"] for problems in by_prctl[1:])
    assert last == "PrctlNoNewPrivs" and status_first or sys.platform != "linux", "the probe runs where /proc exists"
    modes = {path.relative_to(top).as_posix(): os.lstat(path).st_mode & 0o7777 for path in [top, *top.rglob("*")]}
    assert modes == {".": 0o755, "goose": 0o755, "lib": 0o755, "lib/helper": 0o755, "lib/data": 0o644, "link": modes["link"]}
    assert (top / "link").is_symlink()


def test_nothing_a_submission_writes_reaches_a_later_case(tmp_path):
    """Each run has a new workspace, HOME and TMPDIR, and what the sandbox user left anywhere it
    can write (here `shared`, standing for /tmp and the other world-writable directories) is gone
    before the next case. kill_user is left out: here the sandbox user is the one running pytest."""
    shared = tmp_path / "shared"
    shared.mkdir()
    program = tmp_path / "goose"
    program.write_text(textwrap.dedent(f"""\
        #!/bin/sh
        found=""
        for place in "$PWD" "$HOME" "$TMPDIR" "{shared}" "{shared}/stash.d"; do
            [ -e "$place/carried" ] && found="$found $place"
        done
        for place in "$PWD" "$HOME" "$TMPDIR" "{shared}"; do
            echo x > "$place/carried"
        done
        mkdir -p "{shared}/stash.d" && echo y > "{shared}/stash.d/carried"
        if [ -n "$found" ]; then echo "found:$found"; else echo ok; fi
    """))
    program.chmod(0o755)
    private = tmp_path / "private"
    private.mkdir()
    cases, expected = plain_cases([["a"], ["b"], ["c"]])
    (private / "cases.json").write_text(json.dumps({"cases": cases}))
    (private / "expected.json").write_text(json.dumps(expected))
    ipc = tmp_path / "sysvipc"
    ipc.mkdir()
    (ipc / "shm").write_text("key shmid perms size cpid lpid nattch uid gid cuid cgid\n"
                             f"0 7 600 4096 1 1 0 {os.getuid()} 0 {os.getuid()} 0\n0 8 600 4096 1 1 0 4242 0 4242 0\n")
    metrics, removed = verifier_call(textwrap.dedent(f"""
        import json, os
        from pathlib import Path
        import verify
        verify.runcases.WORKSPACE = Path({str(tmp_path / 'goose-case')!r})
        verify.runcases.HOME = Path({str(tmp_path / 'goose-home')!r})
        verify.runcases.TEMP = Path({str(tmp_path / 'goose-tmp')!r})
        verify.LEFTOVER_DIRS[:] = [{str(shared)!r}]
        verify.kill_user = lambda uid: None
        removed, real_run = [], verify.subprocess.run
        verify.subprocess.run = lambda argv, **kw: removed.append(argv) if argv[0] == "ipcrm" else real_run(argv, **kw)
        root = Path({str(ipc)!r})
        verify.remove_ipc = (lambda real: lambda uid: real(uid, root))(verify.remove_ipc)
        metrics = verify.grade(Path({str(program)!r}), Path({str(private)!r}), [], (os.getuid(), os.getgid()))
        verify.final_cleanup(os.getuid(), __import__("time").monotonic() + 30)  # main() does this before the reward
        print(json.dumps([metrics, removed]))
    """))
    assert metrics["cases_passed"] == 3, metrics
    assert removed and all(argv == ["ipcrm", "-m", "7"] for argv in removed), removed
    assert list(shared.iterdir()) == [], "the last case's files outlived the evaluation"
    tree = tmp_path / "tree"
    for name, mode in (("open", 0o777), ("closed", 0o755), ("open/inner", 0o1777)):
        (tree / name).mkdir(parents=True)
        (tree / name).chmod(mode)
    found = verifier_call(f"import json, verify\nprint(json.dumps(verify.writable_dirs({str(tree)!r})))")
    assert sorted(found) == [str(tree / "open"), str(tree / "open" / "inner")]


def test_recorder_keeps_only_cases_that_finish_the_same_way_twice_and_soon(tmp_path):
    program = tmp_path / "fake-goose"
    program.write_text("#!/usr/bin/env python3\nimport os, sys, time\n"
                       "if 'help' in sys.argv: print(os.urandom(4).hex())\n"
                       "elif 'version' in sys.argv: time.sleep(5)\n"
                       "elif 'lag' in sys.argv: time.sleep(1.2); print('late')\n"
                       "else: print(' '.join(sys.argv[1:]), sorted(os.listdir('.')))\n"
                       "sys.exit(2 if 'check' in sys.argv else 0)\n")
    program.chmod(0o755)
    cases = [{"id": f"P{i}", "files": {"main.goose": "fn main() {}\n"}, "argv": argv, "stdin": None}
             for i, argv in enumerate([["run", "main.goose"], ["check", "main.goose"], ["help"], ["version"], ["format"]])]
    source, outputs, kept, timing = (tmp_path / name for name in ("cases.json", "outputs.json", "kept.json", "timing.json"))
    source.write_text(json.dumps({"cases": cases}))
    done = subprocess.run([sys.executable, "-B", str(RECORDER), "record", str(program), str(source), str(outputs), "--keep", str(kept)],
                          capture_output=True, text=True, timeout=120)
    out = done.stdout + done.stderr
    assert done.returncode != 0 and "1 did not finish the same way twice" in out and "1 were slow" in out, "a hang is slow"
    cases = cases[:2] + [dict(cases[4], files={f"f{index}.goose": ""}) for index in range(8)]
    for index, case in enumerate(cases):
        cases[index] = dict(case, id=f"P{index}")
    cases += [{"id": "P98", "files": {}, "argv": ["lag"], "stdin": None}, {"id": "P99", "files": {}, "argv": ["help"], "stdin": None}]
    source.write_text(json.dumps({"cases": cases}))
    done = subprocess.run([sys.executable, "-B", str(RECORDER), "record", str(program), str(source), str(outputs), "--keep", str(kept),
                           "--report", str(timing)], capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stdout + done.stderr
    assert [c["id"] for c in json.loads(kept.read_text())["cases"]] == [f"P{i}" for i in range(10)]
    report = json.loads(timing.read_text())
    assert report["slow"] == ["P98"] and report["unsteady"] == ["P99"] and report["keep_seconds"] == 1.0
    assert min(report["seconds"]["P98"]) >= 1.2 and max(max(report["seconds"][f"P{i}"]) for i in range(10)) < 1.0
    assert report["perturbed"] == [] and len(report["kept_ids_sha256"]) == 64 and report["wall_seconds"] > 0
    check = subprocess.run([sys.executable, "-B", str(RUNNER), "check", str(program), str(kept), str(outputs)],
                           capture_output=True, text=True, timeout=120)
    assert check.stdout.strip().splitlines()[-1] == "10 of 10 cases pass"


FAKE_COMPILER = """#!/usr/bin/env python3
import os, signal, sys
args = sys.argv[1:]
if args[:2] == ["format", "-"]:
    sys.stdout.write(sys.stdin.read().replace("  ", " "))
    sys.exit(0)
text = open(args[1]).read() if len(args) > 1 and os.path.exists(args[1]) else ""
if "CRASH" in text:
    sys.stderr.write("internal error: boom\\n")
    sys.exit(2)
if "SEGV" in text:
    os.kill(os.getpid(), signal.SIGSEGV)
if args[0] == "check":
    print('[{"severity": "error", "message": "bad thing"}]' if "BAD" in text else "[]")
    sys.exit(1 if "BAD" in text else 0)
if args[0] == "format":
    print(sorted(os.listdir(".")), open("a.goose").read() if os.path.exists("a.goose") else "")
    sys.exit(0)
if "ABORT" in text:
    sys.exit(1)
print(text.split()[0] if text.split() else "")
"""


def test_the_recorder_settles_each_case_by_its_rule_and_drops_crashes(tmp_path):
    program = tmp_path / "fake-goose"
    program.write_text(FAKE_COMPILER)
    program.chmod(0o755)
    run = lambda i, text, **plan: {"id": f"P{i}", "files": {"main.goose": text}, "argv": ["run", "main.goose"],  # noqa: E731
                                   "stdin": None, **({"record": plan} if plan else {})}
    cases = [run(1, "ABORT one", variants=[{"main.goose": "two"}, {"main.goose": "base"}], want="same"),
             run(2, "CRASH", variants=[{"main.goose": "base2"}], want="same", complete=True),
             {"id": "P3", "files": {"main.goose": "fine"}, "argv": ["check", "main.goose", "--diagnostics", "json"], "stdin": None,
              "record": {"variants": [{"main.goose": "fine too"}, {"main.goose": "BAD"}], "want": "diagnostics"}},
             run(4, "x", variants=[{"main.goose": "ABORT"}], want="same", complete=True),
             {"id": "P5", "files": {"a.goose": "x  y", "b.goose": "p  q"}, "argv": ["format", "--check", "."], "stdin": None,
              "record": {"formatted": ["a.goose"]}},
             run(6, "SEGV"), run(7, "CRASH"), run(8, "same", variants=[{"main.goose": "same"}], want="same"),
             run(9, "plain"), {"id": "P10", "files": {}, "argv": ["help"], "stdin": None, "record": {"cli": True}}]
    source, outputs, kept, timing = (tmp_path / name for name in ("cases.json", "outputs.json", "kept.json", "timing.json"))
    source.write_text(json.dumps({"cases": cases}))
    done = subprocess.run([sys.executable, "-B", str(RECORDER), "record", str(program), str(source), str(outputs), "--keep", str(kept),
                           "--report", str(timing)], capture_output=True, text=True, timeout=120)
    assert "crashed" in done.stdout + done.stderr and done.returncode != 0, "two crashes in ten cases fail the recording"
    cases = [case for case in cases if case["id"] not in ("P6", "P7")] + [run(i, f"word{i}") for i in range(20, 120)]
    source.write_text(json.dumps({"cases": cases + [run(6, "SEGV")]}))
    done = subprocess.run([sys.executable, "-B", str(RECORDER), "record", str(program), str(source), str(outputs), "--keep", str(kept),
                           "--report", str(timing)], capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stdout + done.stderr
    got = {case["id"]: case for case in json.loads(kept.read_text())["cases"]}
    report = json.loads(timing.read_text())
    assert got["P1"]["files"] == {"main.goose": "two"}, "the first candidate that ends as the base does and prints otherwise"
    assert got["P2"]["files"] == {"main.goose": "base2"}, "a crashing candidate is passed over for the base"
    assert got["P3"]["files"] == {"main.goose": "BAD"}, "a check is settled on the first edit that reports something"
    assert "P4" not in got and report["dropped"]["base does not complete"] == ["P4"]
    assert got["P5"]["files"] == {"a.goose": "x y", "b.goose": "p  q"}, "only the marked file is formatted"
    assert report["crashed"] == ["P6"] and "P6" not in got
    assert report["settled"]["P8"] == "variant 0, output as the base's" and report["cli"] == ["P10"]
    assert all("record" not in case for case in got.values())


def test_selection_drops_shared_answers_quoted_answers_and_free_cases():
    report = verifier_call(textwrap.dedent("""
        import json
        from verifier import recorder as runcases
        case = lambda i, argv, stdin=None, text="fn main() {}": {"id": f"P{i:04d}", "files": {"main.goose": text},
                                                               "argv": argv, "stdin": stdin}
        cases, outputs = [], {}
        for i in range(600):   # run cases: 40 print nothing and exit 1, the rest print their own line
            cases.append(case(i, ["run", "main.goose"]))
            outputs[cases[-1]["id"]] = {"exit": 1, "stdout": ""} if i < 40 else {"exit": 0, "stdout": f"line {i}\\n"}
        for i in range(600, 1000):   # check cases: 60 answer [], the rest report something of their own
            cases.append(case(i, ["check", "main.goose", "--diagnostics", "json"]))
            message = json.dumps([{"severity": "error", "message": f"unknown variable: name{i}"}])
            outputs[cases[-1]["id"]] = {"exit": 0, "stdout": "[]\\n"} if i < 660 else {"exit": 1, "stdout": message + "\\n"}
        cases.append(case(1000, ["format"], stdin="fn main() {}\\n"))
        outputs["P1000"] = {"exit": 0, "stdout": "fn main() {}\\n"}
        cases.append(case(1001, ["format"], stdin="// we hit unknown variable: name700 here\\nfn  main() {}\\n"))
        outputs["P1001"] = {"exit": 0, "stdout": "// we hit unknown variable: name700 here\\nfn main() {}\\n"}
        cases.append(case(1022, ["format"], stdin="// a comment of its own, long enough\\nfn  main() {}\\n"))
        outputs["P1022"] = {"exit": 0, "stdout": "// a comment of its own, long enough\\nfn main() {}\\n"}
        for i in range(1002, 1022):
            cases.append(case(i, ["help", str(i)]))
            outputs[cases[-1]["id"]] = {"exit": 1, "stdout": ""}
        kept, dropped = runcases.select(cases, outputs, {f"P{i:04d}" for i in range(1002, 1022)})
        free = runcases.free_cases(kept, outputs, {f"P{i:04d}" for i in range(1002, 1022)})
        empty = sum(1 for c in kept if outputs[c["id"]] == {"exit": 1, "stdout": ""})
        checks_empty = sum(1 for c in kept if outputs[c["id"]]["stdout"] == "[]\\n")
        print(json.dumps({"kept": len(kept), "dropped": {k: len(v) for k, v in dropped.items()},
                          "quoted": dropped.get("comment quotes an answer"), "echo": dropped.get("input already formatted"),
                          "free": sum(map(len, free.values())), "empty": empty, "checks_empty": checks_empty,
                          "checks": sum(1 for c in kept if c["argv"][0] == "check")}))
    """))
    assert report["quoted"] == ["P1001"] and report["echo"] == ["P1000"]
    assert report["empty"] <= int(0.012 * 1020) + 20, "the command-line cases are never dropped"
    assert report["checks_empty"] <= max(1, int(0.05 * report["checks"]))
    assert report["free"] <= 0.045 * report["kept"], report
    assert report["kept"] > 900


def test_the_shipped_runner_only_runs_and_compares():
    """The agent's run_examples.py is runcases.py: it runs cases with the limits and compares, and
    says nothing of how answers were recorded or which cases were kept."""
    runner = RUNNER.read_text()
    for phrase in ("original", "asked to copy", "no compiler", "collect", "slower machines", "settle", "variant",
                   "SHARE", "record", "KEEP_SEC", "hidden", "grade"):
        assert phrase not in runner, phrase
    assert not re.search(r"(?<![.\w])select\b", runner), "no selection of cases"
    for name in ("def limit(", "def prepare(", "def run_case(", "def matches(", "def remove_path(", "MEMORY_LIMIT"):
        assert name in runner, name
    done = subprocess.run([sys.executable, "-B", str(RUNNER), "record", "x", "y", "z"], capture_output=True, text=True)
    assert done.returncode != 0 and "usage" in done.stdout + done.stderr


def test_a_deep_tree_never_turns_grading_into_an_error(tmp_path):
    """A run that leaves 1,500 nested directories behind: the next case's cleanup (rm -rf) removes
    them, and grading completes."""
    script = 'case "$1" in deep) i=0; while [ $i -lt 1500 ]; do mkdir d && cd d || break; i=$((i+1)); done;; esac\necho ok\n'
    cases, expected = plain_cases([["deep"], ["after"], ["deep"], ["last"]])
    metrics = run_verifier(tmp_path, script, cases, expected)
    assert metrics["cases_run"] == 4 and metrics["setup_errors"] == 0, metrics
    assert metrics["by_kind"]["after"]["passed"] == 1 and metrics["by_kind"]["last"]["passed"] == 1, metrics
    assert not list((tmp_path / "tmp").rglob("d")), "the deep tree was left behind"


def test_the_original_is_refused_by_its_marker_a_published_build_or_upstreams_help_text(tmp_path):
    """A delivery holding the images' build marker, a file with the sha256 of any build upstream
    publishes (every release archive, the compiler inside each, Homebrew's bottles), or an ELF file
    with a line of upstream's help text that the hardened build lacks, is refused; a note or a script
    that quotes the text is not; only the images carry a marker, the solution none."""
    marker = b"GOOSE-BUILD-MARKER-" + b"f" * 32
    top = tmp_path / "rebuild"
    (top / "bin").mkdir(parents=True)
    (top / "goose").write_bytes(b"\x7fELF" + b"x" * ((1 << 20) - 10) + marker + b"tail")
    (top / "bin" / "clean").write_bytes(b"GOOSE-BUILD-MARKER-" + b"0" * 32)
    (top / "link").symlink_to(top / "goose")
    fetched = tmp_path / "fetched"
    (fetched / "lib").mkdir(parents=True)
    (fetched / "goose").write_text("#!/bin/sh\nexec \"$(dirname \"$0\")/lib/engine\" \"$@\"\n")
    (fetched / "lib" / "engine").write_bytes(b"\x7fELF published build" * 1000)
    usage = tmp_path / "usage"
    usage.mkdir()
    (usage / "goose").write_bytes(b"\x7fELF" + b"y" * ((1 << 20) - 12) + b"goose help c covers writing the C yourself (goose -o out.c), and")
    quoted = tmp_path / "quoted"
    quoted.mkdir()
    (quoted / "goose").write_text("#!/bin/sh\necho hi\n")
    (quoted / "NOTES.md").write_text("upstream's help ends: goose help c covers writing the C yourself (goose -o out.c); ours does not\n")
    published = hashlib.sha256((fetched / "lib" / "engine").read_bytes()).hexdigest()
    builds = tmp_path / "builds.json"
    builds.write_text(json.dumps({"builds": [{"sha256": published, "size": (fetched / "lib" / "engine").stat().st_size,
                                              "source": "GitHub release"}]}))
    found = verifier_call(textwrap.dedent(f"""
        import json, verify
        from pathlib import Path
        top = Path({str(top)!r})
        marker_only = {{{marker!r}: "the marker"}}
        binary = {{text: "the usage text" for text in verify.UNHARDENED_USAGE}}
        builds = verify.upstream_builds(Path({str(builds)!r}))
        shipped = verify.upstream_builds()
        print(json.dumps([verify.holds_original(top, marker_only), verify.holds_original(top / "bin", marker_only),
                          verify.identity(top / "bin" / "clean"), verify.identity(top / "goose"),
                          verify.holds_original(Path({str(fetched)!r}), marker_only, builds),
                          verify.holds_original(Path({str(usage)!r}), marker_only, builds, binary),
                          len(shipped), min(size for sizes in shipped.values() for size in sizes),
                          verify.holds_original(Path({str(quoted)!r}), marker_only, builds, binary),
                          verify.holds_original(Path({str(usage)!r}), marker_only, builds)]))
    """))
    assert found[0] == "/app/rebuild/goose holds the marker" and found[1] is None, "found across a 1 MB chunk boundary, never through a link"
    assert found[2]["sha256"] == found[2]["sha256_without_marker"] and found[3]["sha256"] != found[3]["sha256_without_marker"]
    assert found[4] == "/app/rebuild/lib/engine is a build of Goose that upstream publishes", "behind a wrapper, under any name"
    assert found[5] == "/app/rebuild/goose holds the usage text", "found across a 1 MB chunk boundary"
    assert found[6] >= 40 and found[7] > 1_000_000, "every release archive, the compiler inside each, and Homebrew's bottles, all distinct"
    assert found[8] is None and found[9] is None, "the usage text in a note or a script is no fetched build; nor is an ELF file checked without it"
    shipped = json.loads((STEP / "tests" / "verifier" / "upstream_builds.json").read_text())
    sources = [build["source"] for build in shipped["builds"]]
    assert {source.split(":")[0] for source in sources} >= {f"GitHub release v2026.{n}" for n in (1, 2, 3, 4)} | \
        {"Homebrew bottle goose-lang 2026.4 x86_64_linux", "Homebrew bottle goose-lang 2026.4 arm64_linux"}
    assert sum(source.endswith("linux-x64.tar.gz") for source in sources) == 4, "each Linux release archive once"
    assert sum(source.endswith("linux-x64/goose") for source in sources) == 4, "and the compiler inside each"
    assert sum("/bin/goose" in source for source in sources) == 5, "the compiler inside each bottle"
    compilers = [build for build in shipped["builds"] if "usage_text" in build]
    lacking = sorted(build["source"] for build in compilers if not all(build["usage_text"].values()))
    assert len(compilers) == 21 and len(lacking) == 4 and all(source.startswith("GitHub release v2026.1:") for source in lacking), \
        "every published compiler from v2026.2 on holds both lines of the help text the verifier refuses; v2026.1 (older help) by hash alone"
    assert not any(source.endswith((".o", ".a")) for source in sources), "never TinyCC's objects, which the task's own build also makes"
    verify = (STEP / "tests" / "verify.py").read_text()
    assert all(f'b"{text}"' in verify for text in shipped["usage_text"]) and len(shipped["usage_text"]) == 2
    docs = TASK / "environment" / "docs"
    if docs.is_dir():  # a staged checkout's documentation: nothing in it quotes the refused lines
        for page in docs.rglob("*"):
            if page.is_file():
                assert not any(text.encode() in page.read_bytes() for text in shipped["usage_text"]), page
    package = (SCRIPTS / "package_step.py").read_text()
    assert 'for place in ("environment", f"{STEP}/tests"):\n        content[f"{place}/hardening/marker"] = marker' in package
    build = (HARDENING / "build.sh").read_text()
    assert 'if [ -f "$here/marker" ]' in build and "goose_marker.h" in build and 'grep -qF "$marker"' in build
    assert "marker" not in (STEP / "solution" / "solve.sh").read_text().split("hardening/build.sh", 1)[0]
    assert verify.index("holds_original(SUBMISSION, needles, builds, binary_needles)") < verify.index("metrics = grade(")
    assert 'raise EvaluationError("The original\'s build marker is missing or malformed")' in verify, "never fails open"
    assert verify.index("builds = upstream_builds()") < verify.index("prefix, owner, limits = sandbox()"), "the list is read before anything runs"


def test_hashing_a_submission_is_bounded_and_never_raises(tmp_path):
    """identity() reads only a regular file, not a link, of at most MAX_PROGRAM bytes, in chunks;
    its marker-free hash equals build.sh's whole-file one, a marker cut by a chunk's end included."""
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    (tmp_path / "linked").symlink_to(fifo)
    data = b"x" * ((1 << 20) - 20) + b"GOOSE-BUILD-MARKER-" + b"a" * 32 + b"y" * 5000 + b"GOOSE-BUILD-MARKER-" + b"b" * 32
    (tmp_path / "goose").write_bytes(data)
    zeroed = re.sub(rb"GOOSE-BUILD-MARKER-[0-9a-f]{32}", b"GOOSE-BUILD-MARKER-" + b"0" * 32, data)
    out = verifier_call(textwrap.dedent(f"""
        import json, verify
        from pathlib import Path
        top = Path({str(tmp_path)!r})
        verify.MAX_PROGRAM = 1 << 22
        big = top / "big"
        with open(big, "wb") as handle:
            handle.truncate((1 << 22) + 1)
        print(json.dumps([verify.identity(top / "linked"), verify.identity(top / "fifo"), verify.identity(top / "goose"),
                          verify.identity(big), verify.identity(top / "missing")]))
    """))
    linked, fifo_result, good, big, missing = out
    assert linked == {"error": "not a regular file"} and fifo_result == {"error": "not a regular file"}
    assert good["sha256"] == hashlib.sha256(data).hexdigest()
    assert good["sha256_without_marker"] == hashlib.sha256(zeroed).hexdigest()
    assert big["error"] == "too large to hash" and missing == {"error": "FileNotFoundError"}


def test_cleanup_cost_does_not_grow_with_what_a_run_leaves(tmp_path):
    """A run that leaves 20,000 directories in a swept directory: each sweep is one find, and grading
    stops at its deadline, so the whole evaluation stays within it plus a small constant."""
    shared = tmp_path / "shared"
    shared.mkdir()
    program = tmp_path / "goose"
    program.write_text(f'#!/bin/sh\ncd "{shared}" && seq 1 20000 | sed "s/^/$$-/" | xargs mkdir\necho ok\n')
    program.chmod(0o755)
    private = tmp_path / "private"
    private.mkdir()
    cases, expected = plain_cases([[f"c{i}"] for i in range(50)])
    (private / "cases.json").write_text(json.dumps({"cases": cases}))
    (private / "expected.json").write_text(json.dumps(expected))
    elapsed, metrics, calls = verifier_call(textwrap.dedent(f"""
        import json, os, time
        from pathlib import Path
        import verify
        verify.runcases.WORKSPACE = Path({str(tmp_path / 'goose-case')!r})
        verify.runcases.HOME = Path({str(tmp_path / 'goose-home')!r})
        verify.runcases.TEMP = Path({str(tmp_path / 'goose-tmp')!r})
        verify.runcases.CASE_SEC = 10
        verify.LEFTOVER_DIRS[:] = [{str(shared)!r}]
        verify.kill_user = lambda uid: None
        verify.MARGIN_SEC = 0.5
        calls, real_run = [], verify.subprocess.run
        verify.subprocess.run = lambda argv, **kw: (calls.append(argv[0]), real_run(argv, **kw))[1]
        started = time.monotonic()
        metrics = verify.grade(Path({str(program)!r}), Path({str(private)!r}), [], (os.getuid(), os.getgid()),
                               time.monotonic() + 8)
        print(json.dumps([time.monotonic() - started, metrics, calls]))
    """))
    assert metrics["stopped"] and metrics["cases_run"] < 50, metrics
    assert elapsed < 8 + 10, elapsed
    assert calls.count("find") <= metrics["cases_run"] + 1, "one find per sweep"
    assert calls.count("rm") <= 3 * (metrics["cases_run"] + 1), "rm for the run's own three directories, never per leftover"


def test_the_sandbox_id_is_one_the_namespace_maps(tmp_path):
    for name, text in (("wide", "0 0 4294967295\n"), ("rootless", "0 100000 65536\n"), ("tight", "0 1000 1\n")):
        (tmp_path / name).write_text(text)
    ids = verifier_call(textwrap.dedent(f"""
        import json, verify
        top = {str(tmp_path)!r}
        print(json.dumps([[verify.pick_id((f"{{top}}/{{name}}", f"{{top}}/{{name}}")) for _ in range(30)]
                          for name in ("wide", "rootless", "tight")]))
    """))
    wide, rootless, tight = ids
    assert all(20000 <= i < 60000 and i != 10001 for i in wide + rootless) and len(set(wide)) > 1
    assert tight == [65534] * 30


def test_an_oversized_submission_is_not_run(tmp_path):
    many, big = tmp_path / "many", tmp_path / "big"
    many.mkdir()
    big.mkdir()
    for index in range(30):
        (many / f"f{index}").write_text("x")
    with open(big / "goose", "wb") as handle:
        handle.truncate(5000)
    out = verifier_call(textwrap.dedent(f"""
        import json, os, verify
        from pathlib import Path
        verify.MAX_ENTRIES, verify.MAX_BYTES = 20, 4096
        results = []
        for top in ({str(many)!r}, {str(big)!r}):
            try:
                verify.seal(Path(top), (os.getuid(), os.getgid()))
                results.append("sealed")
            except verify.EvaluationError as exc:
                results.append(str(exc))
        print(json.dumps(results))
    """))
    assert "more than 20 entries" in out[0] and "more than 4096 bytes" in out[1]


def test_results_are_reserved_written_in_place_and_logs_never_swept(tmp_path):
    """The reward and metrics take their space at the start and are overwritten in place; /logs
    (the agent's own artifacts) is never a directory to sweep; a run past the disk or file limit
    fails."""
    reserved = tmp_path / ".reward.tmp"
    reserved.write_text("--------")
    metrics = tmp_path / "metrics.json"
    metrics.write_text("{}".ljust(4096))
    tree = tmp_path / "root"
    for name in ("tmp", "logs/artifacts/open", "var/tmp"):
        (tree / name).mkdir(parents=True)
        (tree / name).chmod(0o777)
    out = verifier_call(textwrap.dedent(f"""
        import json, verify
        from pathlib import Path
        verify.write_in_place(Path({str(reserved)!r}), b"0.731000")
        verify.write_in_place(Path({str(metrics)!r}), b'{{"reward": 0.731}}')
        found = verify.writable_dirs({str(tree)!r})
        rc = verify.runcases
        rc.memory_in_use = lambda group, uid: 0
        before = (10 << 30, 1_000_000, 2_000_000)
        rc.disk_free = lambda path=None: ((10 << 30) - (2 << 30), 1_000_000, 2_000_000)
        disk = rc.over_limit(1, None, before)
        rc.disk_free = lambda path=None: (10 << 30, 1_000_000 - 200_000, 2_000_000)
        files = rc.over_limit(1, None, before)
        rc.disk_free = lambda path=None: (10 << 30, 1_000_000 - 200_000, 1_900_000)  # XFS, APFS: the total moves
        moving = rc.over_limit(1, None, before)
        rc.disk_free = lambda path=None: (-1, -1, -1)
        unknown = rc.over_limit(1, None, before)
        print(json.dumps([sorted(found), disk, files, unknown, moving]))
    """))
    found, disk, files, unknown, moving = out
    assert reserved.read_text() == "0.731000" and json.loads(metrics.read_text()) == {"reward": 0.731}
    assert not any("logs" in path for path in found) and str(tree / "tmp") in found
    assert disk == "disk limit" and files == "file limit" and unknown is None and moving is None
    verify = (STEP / "tests" / "verify.py").read_text()
    main = verify[verify.index("def main() -> int:"):]
    assert main.index('(output / ".reward.tmp").write_text("--------")') < main.index("raise EvaluationError(f\"Less than") \
        < main.index("sandbox()") < main.index("final_cleanup(owner[0], min(deadline") \
        < main.index('write_in_place(output / ".reward.tmp"') < main.index('os.replace(output / ".reward.tmp", output / "reward.txt")')
    assert 'reward.txt").write_text' not in main, "no reward exists until the real end"
    assert 'if str(uid) in (values.get("uid"), values.get("cuid"))' in RUNNER.read_text(), "shared memory by its creator too"
    assert "as_user(uid, [\"kill\", \"-KILL\", \"-1\"], 10)" in verify and 'as_user(uid, ["ipcrm", "--all"], 60)' in verify
    assert "if os.geteuid() != 0 or uid == os.geteuid()" in verify, "never kill -1 as the verifier's own uid"
    instruction = (STEP / "instruction.md").read_text()
    assert "under 4 GB and 200,000 files" in instruction and "writes at most 1 GB and 100,000 files" in instruction


def test_the_entry_cap_stops_the_walk(tmp_path):
    many = tmp_path / "many"
    many.mkdir()
    for index in range(500):
        (many / f"f{index}").write_text("")
    out = verifier_call(textwrap.dedent(f"""
        import json, os, verify
        from pathlib import Path
        verify.MAX_ENTRIES = 50
        seen = []
        real = verify.os.scandir
        def counting(path):
            listing = real(path)
            class Wrapped:
                def __enter__(self): return self
                def __exit__(self, *a): listing.close()
                def __iter__(self):
                    for entry in listing:
                        seen.append(entry.name)
                        yield entry
            return Wrapped()
        verify.os.scandir = counting
        try:
            verify.seal(Path({str(many)!r}), (os.getuid(), os.getgid()))
            print(json.dumps(["sealed", len(seen)]))
        except verify.EvaluationError as exc:
            print(json.dumps([str(exc), len(seen)]))
    """))
    message, read = out
    assert "more than 50 entries" in message and read <= 51, "the walk stops at the cap"


# ---------------------------------------------------------------- app-manifest (the collect hook) and proc-reaper

DELIVERY = r"""
import json, os, subprocess, sys, tarfile
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import verify
hook, base = Path(sys.argv[2]).read_text(), Path(sys.argv[3])
prescan = hook.split("<<'EOF'\n")[1].split("\nEOF\n", 1)[0]  # every entry's times before the hook, then the permissions, as root
session = hook.split("<<'EOF'\n")[2].split("\nEOF\n", 1)[0]  # egress and the agent's processes, as root
fixer = hook.split("<<'EOF'\n")[3].split("\nEOF\n", 1)[0]  # the link fixer, run as the agent's user
measure = hook.split("<<'EOF'\n")[4].split("\nEOF\n", 1)[0]  # the last script, run as root after it
FULL = ("import os\n_statvfs = os.statvfs\nclass Full:\n    f_bavail = f_favail = 0\n    f_frsize = 4096\n"
        "os.statvfs = lambda path: Full()\n")  # a disk with no room and no inode left
CLOSED = ("import socket\ndef refuse(address, timeout=None):\n    raise ConnectionRefusedError(111, 'refused')\n"
          "socket.create_connection = refuse\n")
SLOW = "import socket, time\nsocket.create_connection = lambda address, timeout=None: time.sleep(30)\n"


def deliver(name, build, entries="200000", size="4000000000", path="1000", seconds="300", start=None, tar=None, prelude="", fixer="0"):
    app = base / name / "app"
    rebuild, state, archives = app / "rebuild", base / name / "state", base / name / "tmp"
    for folder in (rebuild, state, archives):
        folder.mkdir(parents=True)
    if start is not None:
        (state / "free-at-start").write_text(start)
    (state / "status.json").write_text(json.dumps({"egress": {"pypi.org:443": "closed"}, "egress_open": False,
                                                   "process_count": 1, "processes": [{"pid": 7, "command": "sleep 99"}]}))
    (state / "started").write_text("1700000000\n")
    if name == "good":  # proc-reaper fired in this session
        (state / "reaper.txt").write_text("2026-11-19T12:00:00Z armed pid 77: ending the processes selected by '-u dev' in 33900 s\n"
                                          "2026-11-19T21:25:00Z fired after 33900 s: SIGTERM to the processes selected by '-u dev'\n"
                                          "2026-11-19T21:25:05Z done: 0 process(es) of the selection left\n")
    if name == "good":  # what the link fixer printed: a copy of a system file, and a refused link to the user's own files
        (state / "fixer.jsonl").write_text(json.dumps({
            "kind": "copied", "path": "venv/bin/python3", "source": "/usr/bin/python3.12", "source_owner": 0,
            "source_mtime": 1690000000.0, "source_ctime": 1690000000.0, "source_inode": [66, 1234],
            "source_latest_ctime": 1690000000.0, "source_latest_mtime": 1690000000.0,
            "note": "venv/bin/python3: a copy of /usr/bin/python3.12 (was a link to /usr/bin/python3.12)"}) + "\n" + json.dumps({
            "kind": "refused", "path": "vendor", "source": "/home/dev/cache", "source_owner": 10001,
            "source_mtime": 1700000500.0, "source_ctime": 1700000600.0, "source_inode": [66, 99],
            "source_latest_ctime": 1700000600.0, "source_latest_mtime": 1700000500.0,
            "note": "removed vendor -> /home/dev/cache: it leads outside /app/rebuild to something that is not part of the machine's "
                    "installation (not owned by root), which is not copied"}) + "\n")
    build(rebuild)
    earlier = {}  # what the test itself sees before the hook runs (paths past PATH_MAX, in the deep tree, are left out)
    for folder, folders, files in os.walk(rebuild):
        for entry in folders + files:
            full = os.path.join(folder, entry)
            try:
                info = os.lstat(full)
            except OSError:
                continue
            earlier[os.path.relpath(full, rebuild)] = (round(info.st_mtime, 3), round(info.st_ctime, 3))
    __import__("time").sleep(0.02)
    scanned = subprocess.run([sys.executable, "-I", "-", str(rebuild), entries, path, str(state)], input=prescan, capture_output=True,
                             text=True, timeout=300)
    assert scanned.returncode == 0, scanned.stderr
    if name == "unwritable":
        (state / "prescan.json").write_text(json.dumps({"complete": True, "entries": 3, "notes": [], "chmod_failed": ["ro: PermissionError"]}))
    environment = dict(os.environ)
    if tar is not None:  # a stand-in for the copy's tar, first on the PATH
        (base / name / "bin").mkdir()
        (base / name / "bin" / "tar").write_text("#!/bin/sh\n" + tar)
        (base / name / "bin" / "tar").chmod(0o755)
        environment["PATH"] = f"{base / name / 'bin'}:{environment['PATH']}"
    done = subprocess.run([sys.executable, "-I", "-", str(rebuild), entries, size, path, str(state), str(archives), seconds, "2", "0",
                           "1700030000", fixer], input=prelude + measure, capture_output=True, text=True, timeout=300, env=environment)
    assert done.returncode == 0, done.stderr
    assert not os.listdir(archives), "the trial pack is removed"
    EARLIER[name] = earlier
    return app, rebuild


EARLIER = {}


def mark(rebuild):
    return (rebuild / ".manifest").read_text().splitlines()


def copy(rebuild, target, cut=None):  # what Harbor does: tar on the agent's machine, extract with the data filter
    archive = target.parent / (target.name + ".tar")
    subprocess.run(["tar", "-cf", str(archive), "-C", str(rebuild), "."], check=True, capture_output=True, timeout=120,
                   env=dict(os.environ, COPYFILE_DISABLE="1"))  # macOS's tar would add ._ files for extended attributes
    if cut is not None:
        archive.write_bytes(archive.read_bytes()[:cut])
    target.mkdir()
    try:
        with tarfile.open(archive) as bundle:
            bundle.extractall(target, filter="data")
    except (tarfile.TarError, OSError):
        pass  # the copy failed part way: what was extracted stays, as on the platform
    return target


def notes(rebuild):
    try:
        return verify.manifest_notes(rebuild)
    except verify.EvaluationError as exc:
        return ["ERROR " + str(exc)]


def tree(rebuild):
    (rebuild / "src").mkdir()
    (rebuild / "src" / "main.py").write_text("print('hi')\n" * 50)
    (rebuild / "ro").mkdir()
    (rebuild / "ro" / "lnk").symlink_to("../src")
    (rebuild / "ro" / "a").symlink_to("lnk/../../..")  # resolves to the root itself, lexically leaves it: the copy would abort
    (rebuild / "ro").chmod(0o555)                        # read-only: the hook gives its owner rwx back, after recording its times
    (rebuild / "secret").write_text("x")
    (rebuild / "secret").chmod(0o000)                    # unreadable even to its owner: made u+r, after recording its times
    (rebuild / "goose").write_text("#!/bin/sh\nexec python3 src/main.py\n")
    (rebuild / "empty").mkdir()
    (rebuild / "inside").symlink_to("src/main.py")
    (rebuild / "outside").symlink_to("../../../../etc/hosts")
    (rebuild / "absolute").symlink_to("/etc/hosts")
    (rebuild / "src" / "b").mkdir()
    (rebuild / "src" / "b" / "up").symlink_to("..")  # resolves inside
    (rebuild / "esc").symlink_to("src/b/up/../..")  # lexically inside, resolves outside
    os.mkfifo(rebuild / "pipe")
    os.link(rebuild / "goose", rebuild / "goose-again")


def deep(rebuild, levels=6, length=200, pad=1 << 32):
    # a path longer than this machine's PATH_MAX (1,024 bytes on macOS, 4,096 on Linux), made by directory descriptor
    fd = os.open(rebuild, os.O_RDONLY)
    for _ in range(levels):
        os.mkdir("d" * length, dir_fd=fd)
        child = os.open("d" * length, os.O_RDONLY, dir_fd=fd)
        os.close(fd)
        fd = child
    padding = os.open("pad", os.O_WRONLY | os.O_CREAT, 0o644, dir_fd=fd)
    os.ftruncate(padding, pad)  # takes no room: the copy's tar would read every byte
    os.close(padding)
    os.close(fd)
    (rebuild / "goose").write_text("#!/bin/sh\n")


out = {}
app, rebuild = deliver("good", tree)
out["mark"] = mark(rebuild)
out["left"] = sorted(path.name for path in rebuild.iterdir())
record = json.loads((rebuild / ".manifest.json").read_text())
out["record"] = [record["egress_open"], record["kill_rounds"], record["processes_left"], record["manifest"],
                 record["listing_complete"], sorted(item["path"] for item in record["entries"]),
                 next(item for item in record["entries"] if item["path"] == "goose")]
out["copies"] = [record["started"], record["manifest_started"], record["copies"], record["links"], record["notes"]]
out["watchdog"] = [record["ended_by_reaper"], len(record["reaper_log"]), verify.manifest_record(rebuild)["ended_by_reaper"]]
out["fixer_ok"] = [record["fixer_status"], record["fixer_timed_out"], verify.manifest_record(rebuild)["fixer_timed_out"]]
earlier = EARLIER["good"]
out["times"] = [all(item["ctime"] == earlier[item["path"]][1] and item["mtime"] == earlier[item["path"]][0]
                    for item in record["entries"] if item["path"] in earlier),
                sorted(item["path"] for item in record["entries"] if item.get("changed_after_listing")),
                sorted(item["path"] for item in record["entries"] if item["path"] not in earlier),
                record["prescan_complete"], record["changed_entries"],
                oct(os.stat(rebuild / "ro").st_mode & 0o777), oct(os.stat(rebuild / "secret").st_mode & 0o777)]
out["summary"] = verify.manifest_record(rebuild)
out["complete"] = notes(copy(rebuild, base / "good" / "copied"))
partial = copy(rebuild, base / "good" / "partial")
(partial / "src" / "main.py").unlink()  # the mark arrived, a file did not
out["partial"] = notes(partial)
size = os.path.getsize(base / "good" / "copied.tar")
out["cut"] = notes(copy(rebuild, base / "good" / "cut", cut=size // 3))
out["nothing"] = notes(copy(rebuild, base / "good" / "empty", cut=0))
(rebuild / ".manifest").write_text("manifest ² 5\n")  # not ASCII digits: a mark app-manifest did not write
out["odd"] = notes(rebuild)
(rebuild / ".manifest").unlink()
out["unmarked"] = notes(copy(rebuild, base / "good" / "unmarked"))
app, rebuild = deliver("cut-fixer", tree, fixer="124")  # the link fixer stopped by its time limit
record = json.loads((rebuild / ".manifest.json").read_text())
out["cut_fixer"] = [mark(rebuild), record["fixer_status"], record["fixer_timed_out"], verify.manifest_record(rebuild)["fixer_timed_out"],
                    notes(copy(rebuild, base / "cut-fixer" / "copied"))]
app, rebuild = deliver("many", tree, entries="3")
out["many"] = [mark(rebuild), sorted(path.name for path in rebuild.iterdir()),
               sorted(path.name.split(".")[1] if path.name.startswith(".") else path.name for path in app.iterdir())]
out["many_notes"] = notes(copy(rebuild, base / "many" / "copied"))
app, rebuild = deliver("sparse", lambda rebuild: deep(rebuild, levels=0))
out["sparse"] = mark(rebuild)[:2]
app, rebuild = deliver("deep", deep)  # past PATH_MAX, the path limit refuses it
out["deep"] = mark(rebuild)[:2]
app, rebuild = deliver("deep-seen", deep, path="100000")  # with no path limit, the walk still sees the 4 GiB below
out["deep_seen"] = mark(rebuild)[:2]
app, rebuild = deliver("slow", tree, seconds="1", tar="sleep 30\n")
out["slow"] = mark(rebuild)[:2]
app, rebuild = deliver("broken", tree, tar="echo 'tar: ./x: Cannot open: Input/output error' >&2; exit 2\n")
out["broken"] = mark(rebuild)[:2]
failing = "echo 'tar: /tmp/x: Cannot open: No space left on device' >&2; exit 2\n"
app, rebuild = deliver("inodes", tree, start="2500000 4096 1300000\n", tar=failing, prelude=FULL)
out["inodes"] = mark(rebuild)[:2]
app, rebuild = deliver("never-room", tree, tar=failing, prelude=FULL)
out["never_room"] = mark(rebuild)
app, rebuild = deliver("nop", lambda rebuild: None)
out["nop"] = [mark(rebuild), notes(copy(rebuild, base / "nop" / "copied")), verify.manifest_record(base / "nop" / "copied")["entries"]]
out["watchdog"].append(verify.manifest_record(base / "nop" / "copied")["ended_by_reaper"])
app, rebuild = deliver("unwritable", tree)
out["unwritable"] = mark(rebuild)[:2]
app, rebuild = deliver("linked", lambda rebuild: [(rebuild / "big").write_bytes(os.urandom(1 << 20)),
                                                   *(os.link(rebuild / "big", rebuild / f"big{i}") for i in range(30))])
record = json.loads((rebuild / ".manifest.json").read_text())
out["linked"] = [mark(rebuild)[0], len({item["sha256"] for item in record["entries"]}), record["hashing_complete"]]
more = copy(rebuild, base / "linked" / "copied")
(more / "extra").write_text("added by the transport")
out["more"] = notes(more)
outside = base / "venv-like"
outside.mkdir()
for number in range(20):
    (outside / str(number)).write_text("x")
fixed = base / "fixer" / "rebuild"
fixed.mkdir(parents=True)
(fixed / "lib").symlink_to(outside)              # the user's own files outside: refused, whatever their count
(fixed / "one").symlink_to(outside / "3")        # one file of the user's own: refused
(fixed / "sh").symlink_to("/bin/sh")             # part of the machine's installation (root's): copied, with its source's facts
(fixed / "real.txt").write_text("x")
(fixed / "inner").symlink_to(fixed / "real.txt")  # inside, absolute: made relative
done = subprocess.run([sys.executable, "-I", "-", str(fixed), "200000", "4000000000"], input=fixer, capture_output=True, text=True,
                      timeout=60)
changes = [json.loads(line) for line in done.stdout.splitlines()]
out["fixer"] = [done.returncode, {change["path"]: change["kind"] for change in changes},
                next(change for change in changes if change["kind"] == "copied"),
                os.path.lexists(fixed / "lib"), os.path.lexists(fixed / "one"), os.path.isfile(fixed / "sh") and not os.path.islink(fixed / "sh"),
                os.readlink(fixed / "inner")]
(base / "processes.txt").write_text("    1     0     0 100 /sbin/init\n  777     1 10001  65 sleep 99\n  778   777 10001   3 /bin/sh -c curl x\n")
checks = {}
for name, prelude in (("closed", CLOSED), ("slow", SLOW)):
    started = __import__("time").monotonic()
    done = subprocess.run([sys.executable, "-I", "-", str(base / f"status-{name}.json"), str(base / "processes.txt")],
                          input=prelude + session, capture_output=True, text=True, timeout=60)
    checks[name] = [done.returncode, json.loads((base / f"status-{name}.json").read_text()),
                    round(__import__("time").monotonic() - started)]
out["session"] = checks
long_mark = base / "long" / "rebuild"
long_mark.mkdir(parents=True)
(long_mark / "goose").write_text("#!/bin/sh\n")
(long_mark / ".manifest").write_text("manifest 1 10\n" + "".join(f"removed decoy{i} -> /home/dev/x{i}: it leads outside\n" for i in range(60)))
out["long_mark"] = len(verify.manifest_notes(long_mark))
print(json.dumps(out))
"""


def test_the_delivery_is_bounded_recorded_and_marked_before_the_copy_and_graded_as_it_arrives(tmp_path):
    """The collect hook (environment/app-manifest, root, the one [[verifier.collect]]) freezes and lists the agent's
    processes, ends them with `kill -9 -1` as their user until none is left, stops proc-reaper's sleeper, records whether
    the public internet answers (two hosts, 3 s each), records every entry's own times before touching anything, gives
    back room and inodes set aside at setup, fixes links as the agent's user (copies only root-owned targets, with the
    source's facts), then as root walks the delivery by directory descriptor, refuses on anything it cannot complete or
    past 200,000 entries, 4 GB (each file once) or paths of 1,000 bytes, removes what the copy would refuse, packs it once
    the way the copy does within 300 s, and writes a record of every entry (path, size, times, sha256) and the mark. The
    verifier grades what arrived, with a note when the mark is missing or says refused; nothing arriving, or a mark that
    counts more than arrived, is an evaluation error (ported from the BasedPL task, dd2a450..42c6007)."""
    done = subprocess.run([sys.executable, "-I", "-B", "-c", DELIVERY, str(STEP / "tests"), str(TASK / "environment" / "app-manifest"),
                           str(tmp_path)], capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stderr[-3000:]
    out = json.loads(done.stdout.strip().splitlines()[-1])
    run = len("#!/bin/sh\nexec python3 src/main.py\n")
    # src, src/main.py, src/b, src/b/up, goose, goose-again, empty, inside, ro, ro/lnk, secret: 11 entries; goose and goose-again are one file
    assert out["mark"][0] == f"manifest 11 {601 + run}", out["mark"]
    assert out["mark"][1:3] == ["removed vendor -> /home/dev/cache: it leads outside /app/rebuild to something that is not part of the "
                                "machine's installation (not owned by root), which is not copied",
                                "venv/bin/python3: a copy of /usr/bin/python3.12 (was a link to /usr/bin/python3.12)"], \
        "the fixer's notes, dropped links first"
    assert sorted(out["mark"][3:8]) == ["removed absolute: a link that leads outside /app/rebuild", "removed esc: a link that leads outside /app/rebuild",
                                        "removed outside: a link that leads outside /app/rebuild", "removed pipe: not a file, a directory or a link",
                                        "removed ro/a: a link that leads outside /app/rebuild"], "a link that leaves lexically goes too"
    assert sorted(out["mark"][8:]) == ["ro: made writable for its owner (a directory to work in)", "secret: made readable by its owner"]
    turn_started, hook_started, copies, links, notes = out["copies"]
    assert (turn_started, hook_started) == (1700000000, 1700030000) and len(notes) == 9
    untouched, changed, made, prescan_complete, changed_count, ro_mode, secret_mode = out["times"]
    assert untouched, "every entry's mtime and ctime are the ones from before the hook ran"
    assert changed == ["ro", "secret"] and changed_count == 2, "the hook's own chmods are flagged, with the later ctime kept apart"
    assert made == [] and prescan_complete is True and (ro_mode, secret_mode) == ("0o755", "0o400")
    assert out["watchdog"] == [True, 3, True, False], "a session the reaper ended is visible in the record and in metrics"
    assert out["fixer_ok"] == [0, False, False], "a fixer that finished is recorded as such"
    assert len(copies) == 1 and copies[0]["source"] == "/usr/bin/python3.12" and copies[0]["source_owner"] == 0
    assert copies[0]["source_inode"] == [66, 1234] and copies[0]["outside_tree"] is True
    assert copies[0]["changed_since_start"] is False, "a system file from the image build"
    assert links[0]["kind"] == "refused" and links[0]["changed_since_start"] is True and links[0]["outside_tree"] is True
    assert out["left"] == [".manifest", ".manifest.json", "empty", "goose", "goose-again", "inside", "ro", "secret", "src"]
    egress_open, rounds, left, delivered, complete, paths, goose = out["record"]
    assert [egress_open, rounds, left, delivered, complete] == [False, 2, 0, out["mark"][0], True]
    assert paths == ["empty", "goose", "goose-again", "inside", "ro", "ro/lnk", "secret", "src", "src/b", "src/b/up", "src/main.py"]
    assert goose["type"] == "file" and goose["size"] == run and len(goose["sha256"]) == 64 and goose["ctime"] > 1.7e9
    summary = out["summary"]
    assert summary["egress_open"] is False and summary["entries"] == 11 and summary["kill_rounds"] == 2 and summary["goose"] == goose
    assert summary["hashing_complete"] is True and summary["prescan_complete"] is True and summary["changed_entries"] == 2
    assert summary["processes"] == [{"pid": 7, "command": "sleep 99"}] and summary["latest_ctime"] >= goose["ctime"]
    assert summary["copies"] == copies and summary["links"] == links and summary["notes"] == notes, "the whole record reaches metrics.json"
    assert summary["copies_outside_tree"] == 1 and summary["copies_changed_since_start"] == 0
    assert (summary["started"], summary["manifest_started"]) == (1700000000, 1700030000)
    assert out["long_mark"] == 60, "the verifier reads the whole mark, however many notes"
    verify_text = (STEP / "tests" / "verify.py").read_text()
    assert "handle.read(MARK_LIMIT + 1)" in verify_text and "MARK_LIMIT = 1 << 20" in verify_text, "bounded all the same"
    hook_text = (TASK / "environment" / "app-manifest").read_text()
    assert "pgrep -u dev -r R,S,D,T" in hook_text and "pgrep -u dev -r R,S,D " in hook_text + " ", "zombies are never survivors"
    assert "chmod -R" not in hook_text, "no chmod of every entry: that would set every ctime to the hook's time"
    assert hook_text.index("for visit in (record, restore):") < hook_text.index("timeout 120 setpriv"), "times first, then permissions, then the fixer"
    assert "lexical = os.path.normpath" in hook_text and "HASH_SECONDS = 240" in hook_text and "if inode in digests:" in hook_text
    assert out["complete"] == [f"app-manifest: {line}" for line in out["mark"][1:]], out["complete"]
    assert out["cut"][0].startswith(("ERROR The copy arrived incomplete", "/app/rebuild arrived without", "ERROR Nothing")), out["cut"]
    assert out["nothing"][0].startswith("ERROR Nothing arrived") and out["unmarked"][0].startswith("/app/rebuild arrived without")
    assert out["partial"] == [f"ERROR The copy arrived incomplete: 10 of 11 entries and {run + 1:,} of {601 + run:,} bytes"], out["partial"]
    assert out["more"] == ["more arrived than app-manifest marked: 32 entries and 1,048,598 bytes against 31 and 1,048,576 "
                           "(hard links split, or files the transport added)"], "more than marked is a note, not an error"
    assert out["unwritable"] == ["refused", "its permissions could not be restored for its owner: it was not copied"]
    assert out["linked"] == ["manifest 31 1048576", 1, True], "31 names of one file: one hash, counted once"
    assert out["odd"] == ["app-manifest's mark could not be read; /app/rebuild was graded as it arrived"]
    assert out["many"][0][:2] == ["refused", "it holds more than 3 entries, the most /app/rebuild may hold: it was not copied"], out["many"]
    assert out["many"][0][2:] == ["the first listing stopped at more than 3 entries",
                                  "ro: made writable for its owner (a directory to work in)", "secret: made readable by its owner"]
    assert out["many"][1:] == [[".manifest", ".manifest.json"], ["rebuild", "refused"]], out["many"]
    assert out["many_notes"][0] == "app-manifest: it holds more than 3 entries, the most /app/rebuild may hold: it was not copied"
    assert out["sparse"] == ["refused", "it holds more than 4,000,000,000 bytes, the most /app/rebuild may hold: it was not copied"]
    assert out["deep"] == ["refused", "it holds a path longer than 1,000 bytes, the longest /app/rebuild may hold: it was not copied"]
    assert out["deep_seen"] == out["sparse"], out["deep_seen"]
    assert out["slow"] == ["refused", "the copy's pack of it took more than 1 seconds: it was not copied"]
    assert out["broken"] == ["refused", "the copy's pack of it failed (tar: ./x: Cannot open: Input/output error): it was not copied"]
    assert out["inodes"][0] == "refused" and "No space left on device" in out["inodes"][1], out["inodes"]
    assert out["never_room"][0].startswith("manifest ") and any("room the machine did not have" in line for line in out["never_room"])
    assert out["nop"] == [["manifest 0 0"], [], 0], "an empty delivery is marked, arrives, and grades as 0, never as an error"
    cut_mark, cut_status, cut_flag, cut_summary, cut_notes = out["cut_fixer"]
    assert cut_mark[0] == out["mark"][0] and "the link fixer was stopped after 120 s; copies may be incomplete" in cut_mark, cut_mark
    assert (cut_status, cut_flag, cut_summary) == (124, True, True), "a fixer cut by its time limit is flagged in the record and in metrics"
    assert "app-manifest: the link fixer was stopped after 120 s; copies may be incomplete" in cut_notes, "and noted in the verifier's notes"
    assert "never a reason to change the reward" in verify_text, "the reaper flag is never scored"
    code, kinds, copied, lib_left, one_left, sh_copied, inner = out["fixer"]
    assert code == 0 and kinds == {"lib": "refused", "one": "refused", "sh": "copied", "inner": "relinked"}, out["fixer"]
    assert copied["source"] == "/bin/sh" and copied["source_owner"] == 0 and len(copied["source_inode"]) == 2
    assert copied["source_ctime"] > 1e9 and copied["source_mtime"] > 1e9 and "a copy of /bin/sh" in copied["note"]
    assert not lib_left and not one_left and sh_copied and inner == "real.txt", "the user's own files outside are never copied in"
    closed, slow = out["session"]["closed"], out["session"]["slow"]
    assert closed[0] == 0 and closed[1]["egress_open"] is False and set(closed[1]["egress"]) == {"pypi.org:443", "github.com:443"}
    assert [process["command"] for process in closed[1]["processes"]] == ["sleep 99", "/bin/sh -c curl x"], "from the frozen listing"
    assert closed[1]["processes"][1]["running_seconds"] == 3 and closed[1]["process_count"] == 2
    assert all(state.startswith("closed") for state in closed[1]["egress"].values())
    assert slow[0] == 0 and set(slow[1]["egress"].values()) == {"no answer within 3 s"} and slow[2] <= 9, slow
    order = ["kill -STOP -1", "ps -eo pid=,ppid=,uid=,etimes=,args= > \"$STATE/processes.txt\"", "kill -9 -1",
             'reaper=$(cat /run/proc-reaper.pid 2>/dev/null)', 'tail -n 20 /var/log/proc-reaper.log > "$STATE/reaper.txt"',
             'timeout 300 /usr/bin/python3 -I - /app/rebuild "$LIMIT_ENTRIES" "$LIMIT_PATH" "$STATE"',
             "/usr/bin/python3 -I - \"$STATE/status.json\" \"$STATE/processes.txt\"", "rm -f /var/lib/app-manifest/reserve",
             "rm -rf /var/lib/app-manifest/inodes", 'mv -f "/app/rebuild/$name" "$aside/"',
             "timeout 120 setpriv --reuid dev --regid dev --clear-groups --no-new-privs /usr/bin/python3 -I -",
             '> "$STATE/fixer.jsonl"', "fixer_status=$?", 'exec /usr/bin/python3 -I - /app/rebuild']
    assert [hook_text.index(step) for step in order] == sorted(hook_text.index(step) for step in order)
    for setting in ("LIMIT_ENTRIES=200000", "LIMIT_BYTES=4000000000", "LIMIT_PATH=1000", "PACK_SECONDS=300", "STATE=/var/lib/app-manifest"):
        assert setting in hook_text, setting
    assert "rm -rf \"$" not in hook_text and "rm -f \"$" not in hook_text, "nothing is removed through a variable"
    assert 'pkill -P "$reaper"' in hook_text and 'kill "$reaper"' in hook_text, "the reaper's sleeper is stopped before the fixer runs as dev"
    setup = (TASK / "environment" / "fs-reserve").read_text()
    assert "fallocate -l 64M /var/lib/app-manifest/reserve" in setup and '/var/lib/app-manifest/inodes/$spare' in setup and "seq 1 64" in setup
    assert "stat -f -c '%a %S %d' /tmp > /var/lib/app-manifest/free-at-start" in setup
    assert "date +%s > /var/lib/app-manifest/started" in setup, "the session's start, for the record's flags"
    assert hook_text.index("kill -STOP -1") < hook_text.index("/usr/bin/python3"), "nothing runs before the freeze but the hook's own settings"
    import tomllib
    config = tomllib.loads((TASK / "task.toml").read_text())
    assert config["verifier"]["collect"] == [{"command": "/usr/local/sbin/app-manifest", "user": "root", "timeout_sec": 900}]
    assert config["agent"]["setup_begin"] == [{"command": "/usr/local/sbin/fs-reserve", "timeout_sec": 120}]
    assert config["agent"]["setup_complete"] == [{"command": "/usr/local/sbin/fs-reserve", "timeout_sec": 120},
                                                 {"command": "/usr/local/sbin/proc-reaper", "user": "root", "timeout_sec": 60}]
    docker = (TASK / "environment" / "Dockerfile").read_text()
    assert "COPY fs-reserve app-manifest proc-reaper /usr/local/sbin/" in docker
    assert "chmod 0700 /usr/local/sbin/fs-reserve /usr/local/sbin/app-manifest /usr/local/sbin/proc-reaper" in docker
    assert docker.index("COPY fs-reserve") > docker.index("\nFROM "), "in the final image only"
    main = verify_text[verify_text.index("def main() -> int:"):]
    assert main.index("manifest_notes(SUBMISSION)") < main.index("sandbox()") < main.index("seal(SUBMISSION)")
    assert "manifest=record" in main, "the record goes to metrics.json"
    assert "[:20]" not in verify_text[verify_text.index("def manifest_notes"):verify_text.index("def manifest_record")], "every note of the mark"
    assert int(re.search(r"^MAX_ENTRIES = ([\d_]+)", verify_text, re.M).group(1).replace("_", "")) >= 200_000 + 3, \
        "the verifier's cap leaves room for the hook's 200,000 entries, its two files and the root"
    instruction = " ".join((STEP / "instruction.md").read_text().split())
    assert "under 4 GB and 200,000 files, with no path inside it longer than 1,000 bytes" in instruction
    assert "only when that is part of the machine's installation (owned by root" in instruction
    assert instruction.index("A link to files of your own anywhere outside the directory is dropped") < instruction.index("only when that is part")
    assert "must be one of the machine's own or copied into `/app/rebuild`" in instruction
    assert "room to copy it" in instruction


def test_proc_reaper_arms_once_fires_and_ends_the_users_processes(tmp_path):
    """The root reaper started at setup_complete ends the agent's session shortly before the
    platform's cap, since a turn that runs into the cap is not graded today while one that ends by
    itself is. It arms one sleeper however often it is started, fires after AFTER_SECONDS (waiting
    in short sleeps, so that no long timer shows in ps), ends every selected process (a tree, and a
    process in a session of its own), and logs each step. Nothing in its text or name says why."""
    import uuid
    marker = f"reaper-sleep-{uuid.uuid4().hex[:12]}"
    sleeper = tmp_path / marker
    shutil.copy(shutil.which("sleep"), sleeper)
    sleeper.chmod(0o755)
    env = dict(os.environ, REAPER_AFTER_SECONDS="2", REAPER_PIDFILE=str(tmp_path / "reaper.pid"), REAPER_LOG=str(tmp_path / "reaper.log"),
               REAPER_SELECT=f"-f {marker}")
    tree = subprocess.Popen(["sh", "-c", f"{sleeper} 300 & {sleeper} 300"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    alone = subprocess.Popen([str(sleeper), "300"], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        first = subprocess.run(["sh", str(TASK / "environment" / "proc-reaper")], env=env, capture_output=True, text=True, timeout=30)
        assert first.returncode == 0 and "armed for 2 s" in first.stdout, first
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not (tmp_path / "reaper.pid").read_text().strip():
            time.sleep(0.05)
        armed_pid = (tmp_path / "reaper.pid").read_text().strip()
        second = subprocess.run(["sh", str(TASK / "environment" / "proc-reaper")], env=env, capture_output=True, text=True, timeout=30)
        assert second.returncode == 0 and second.stdout == "", "a second start arms nothing"
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline and "done:" not in (tmp_path / "reaper.log").read_text():
            time.sleep(0.2)
        log = (tmp_path / "reaper.log").read_text()
        assert log.count(" armed pid ") == 1 and f"armed pid {armed_pid}" in log and "already armed" in log, log
        assert " fired after 2 s" in log and "done: 0 process(es)" in log, log
        assert tree.wait(timeout=10) != 0 and alone.wait(timeout=10) != 0, "the tree and the process in its own session are ended"
        left = subprocess.run(["pgrep", "-f", marker], capture_output=True, text=True)
        assert left.stdout.strip() == "", left.stdout
        assert not (tmp_path / "reaper.pid").exists(), "the pid file goes with the sleeper"
    finally:
        for proc in (tree, alone):
            if proc.poll() is None:
                proc.kill()
    script = (TASK / "environment" / "proc-reaper").read_text()
    assert "AFTER_SECONDS=${REAPER_AFTER_SECONDS:-33900}" in script, "the agent's 34,560 s less eleven minutes"
    assert "umask 077" in script and 'LOG=${REAPER_LOG:-/var/log/proc-reaper.log}' in script, "a root-only log"
    assert "sleep 60" in script and 'sleep "$AFTER_SECONDS"' not in script, "no sleep of the whole wait, which ps would show"
    agent = int(re.search(r"\[agent\]\s*timeout_sec = (\d+)", (TASK / "task.toml").read_text()).group(1))
    assert agent - 33900 == 660
    instruction = (STEP / "instruction.md").read_text().lower()
    assert "watchdog" not in instruction and "cap" not in instruction and "budget" not in instruction


def test_the_agent_cannot_replace_the_artifact_directory():
    """/app is root's and sticky, /app/rebuild root's and writable by all: the agent cannot swap the
    artifact for a link to the original, which the root-run collector would follow."""
    docker = (TASK / "environment" / "Dockerfile").read_text()
    owned = docker.index("chown -R dev:dev /app")
    assert owned < docker.index("chown root:root /app /app/rebuild") and "chmod 1777 /app " in docker
    assert "chmod 0777 /app/rebuild" in docker


def test_the_recorder_renumbers_the_examples_it_keeps(tmp_path):
    program = tmp_path / "fake-goose"
    program.write_text(FAKE_COMPILER)
    program.chmod(0o755)
    cases = [{"id": f"E{i:05d}", "files": {"main.goose": f"word{i}"}, "argv": ["run", "main.goose"], "stdin": None}
             for i in (3, 7, 8, 20)] + [{"id": "E00030", "files": {"main.goose": "SEGV"}, "argv": ["run", "main.goose"],
                                         "stdin": None}]
    source, outputs, kept = tmp_path / "c.json", tmp_path / "o.json", tmp_path / "k.json"
    source.write_text(json.dumps({"cases": cases * 1}))
    done = subprocess.run([sys.executable, "-B", str(RECORDER), "record", str(program), str(source), str(outputs), "--keep",
                           str(kept), "--renumber", "E"], capture_output=True, text=True, timeout=120)
    assert done.returncode != 0, "one crash in five fails the recording"
    source.write_text(json.dumps({"cases": cases[:4] + [dict(c, id=f"E{40 + i:05d}", files={"main.goose": f"w{i}"})
                                                        for i, c in enumerate(cases[:1] * 60)]}))
    done = subprocess.run([sys.executable, "-B", str(RECORDER), "record", str(program), str(source), str(outputs), "--keep",
                           str(kept), "--renumber", "E"], capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stdout + done.stderr
    ids = [case["id"] for case in json.loads(kept.read_text())["cases"]]
    assert ids == [f"E{i:05d}" for i in range(1, len(ids) + 1)] and sorted(json.loads(outputs.read_text())) == ids


def test_the_recording_report_counts_upstream_answers_and_the_baselines(tmp_path):
    digest = hashlib.sha256(b"6\n").hexdigest()
    message = lambda text: hashlib.sha256(text.encode()).hexdigest()  # noqa: E731
    run = {"files": {"main.goose": ""}, "argv": ["run", "main.goose"], "stdin": None}
    check = {"files": {"main.goose": ""}, "argv": ["check", "main.goose", "--diagnostics", "json"], "stdin": None}
    kept = [dict(run, id="P1", kind="run", upstream=digest), dict(run, id="P2", kind="run", upstream=digest),
            dict(check, id="P3", kind="check", upstream_messages=[message("unknown variable: a")]),
            dict(check, id="P6", kind="check", upstream_messages=[message("unknown variable: a"), message("other")]),
            dict(run, id="P7", kind="run"), dict(run, id="P8", kind="run"),
            {"id": "P9", "kind": "format", "files": {}, "argv": ["format"], "stdin": "x\n"},
            {"id": "P10", "kind": "cli", "files": {}, "argv": ["help"], "stdin": None}]
    cases = kept + [dict(run, id="P4", kind="modules"), dict(run, id="P5", kind="run")]
    diagnostic = lambda text: json.dumps([{"severity": "error", "message": text}]) + "\n"  # noqa: E731
    expected = {"P1": {"exit": 0, "stdout": "6\n"}, "P2": {"exit": 0, "stdout": "7\n"},
                "P3": {"exit": 1, "stdout": diagnostic("unknown variable: a")},
                "P6": {"exit": 1, "stdout": diagnostic("unknown variable: renamed")},
                "P7": {"exit": 1, "stdout": ""}, "P8": {"exit": 1, "stdout": ""}, "P9": {"exit": 0, "stdout": "y\n"},
                "P10": {"exit": 0, "stdout": "usage\n"}}
    seconds = {i: [0.1, 0.2] for i in ("P1", "P2", "P3", "P6", "P7", "P8", "P9", "P10")}
    timing = {"keep_seconds": 0.5, "seconds": dict(seconds, P4=[0.9, 0.8], P5=[0.1, 2]), "slow": ["P4"], "unsteady": ["P5"],
              "crashed": [], "dropped": {"answer shared by many cases": ["P5"]}, "settled": {"P1": "variant 0"}, "cli": ["P10"]}
    for name, data in (("cases.json", {"cases": cases}), ("kept.json", {"cases": kept}), ("expected.json", expected), ("timing.json", timing)):
        (tmp_path / name).write_text(json.dumps(data))
    (tmp_path / "build.txt").write_text("link static\nsha256 ab\nsha256_without_marker cd\n")
    subprocess.run([sys.executable, "-B", str(STEP / "tests" / "verifier" / "recording.py"),
                    *(str(tmp_path / name) for name in ("cases.json", "kept.json", "expected.json", "timing.json", "out.json")),
                    "--build", str(tmp_path / "build.txt")], check=True, capture_output=True, timeout=60)
    report = json.loads((tmp_path / "out.json").read_text())
    assert report["run_cases_with_upstream_output"] == 2 and report["run_cases_printing_upstream_output"] == 1
    assert report["error_cases_with_upstream_messages"] == 2 and report["error_cases_all_messages_verbatim"] == 1
    assert report["error_cases_some_message_verbatim"] == 1 and report["build"]["link"] == "static"
    assert report["build"]["sha256_without_marker"] == "cd"
    assert report["empty_stdout_by_exit"] == {"1": 2} and report["kinds_kept"] == {"check": 2, "cli": 1, "format": 1, "run": 4}
    assert report["dropped_slow"] == {"modules": 1} and report["dropped_unsteady"] == {"run": 1}
    assert report["dropped"] == {"answer shared by many cases": {"run": 1}} and report["settled"] == {"variant 0": 1}
    baselines = report["baselines"]
    assert baselines["print_nothing_exit_1"] == round(2 / 8, 4) and baselines["print_nothing_exit_0"] == 0
    assert baselines["command_line_table_and_constants"] == round(3 / 8, 4), "the help case and the two silent runs"
    assert baselines["formatter_only"] == round(4 / 8, 4)


# ---------------------------------------------------------------- hardening and images

def test_images_and_solution_build_one_hardened_compiler_and_ship_no_private_cases():
    agent = (TASK / "environment" / "Dockerfile").read_text()
    verifier = (STEP / "tests" / "Dockerfile").read_text()
    solve = (STEP / "solution" / "solve.sh").read_text()
    base = re.search(r"^FROM (ubuntu:24\.04@sha256:[0-9a-f]{64}) AS program$", agent, re.M).group(1)
    builder = agent.split(f"\n\nFROM {base}\n", 1)[0]
    build_part = builder[:builder.index("bash /hardening/smoke.sh /opt/goose/goose") + 42]
    assert verifier.startswith(build_part), "both images must build the compiler the same way"
    assert agent.count(f"FROM {base}") == 2 and verifier.count(f"FROM {base}") == 2, "every stage on the pinned base"
    build = (HARDENING / "build.sh").read_text()
    for flag in ("-DGOOSE_VERSION=745901f", "-DGOOSE_STDLIB_PATH=/usr/local/share/goose/stdlib", 'make_goose "-static -s"',
                 'make_goose "-s"', 'bash "$here/smoke.sh" "$build/goose"'):
        assert flag in build, flag
    assert not any(step in text for step in ("cmake -S", "cmake --build") for text in (builder, solve)), "one build, in build.sh"
    assert builder.index("sh /hardening/apply.sh /src") < builder.index("cp -a /src/stdlib /usr/local/share/goose/stdlib") \
        < builder.index("sh /hardening/build.sh /src /build 4") < builder.index("bash /hardening/smoke.sh /opt/goose/goose")
    assert solve.index('sh "$here/hardening/apply.sh" "$src"') < solve.index('sh "$here/hardening/build.sh" "$src" "$build"') \
        < solve.index("install -m 0755")
    assert "--build /build/build.txt" in verifier and "cp /hardening/marker /record/marker" in verifier
    assert 'cp "$build/build.txt" /logs/agent/build.txt' in solve and 'smoke.sh" /app/rebuild/goose' in solve
    final_agent = agent.split(f"\n\nFROM {base}\n", 1)[1]
    final_verifier = verifier.split(f"\n\nFROM {base}\n", 1)[1]
    assert "recorder.py record /opt/goose/goose /record/examples.json" in builder and "--renumber E" in builder
    assert "recorder" not in final_agent and "COPY run_examples.py /app/examples/" in final_agent
    assert "COPY --from=program /record/kept.json /app/examples/examples.json" in final_agent
    assert "COPY --from=program /record/marker /tests/private/marker" in final_verifier
    assert "hardening" not in final_agent and "hardening" not in final_verifier
    assert "private" not in agent and "chown root:goose /opt/goose/goose && chmod 2711 /opt/goose/goose" in final_agent
    assert "/opt/goose" not in final_verifier, "the verifier image holds no copy of the compiler"
    assert "COPY --from=program /record/kept.json /tests/private/cases.json" in final_verifier
    assert "stdlib" not in solve.split("install -m 0755", 1)[1], "the solution ships no stdlib beside its binary"
    assert "git clone" not in agent + verifier


def test_the_hardening_patch_applies_and_its_refusals_are_the_ones_the_build_proves(tmp_path):
    patch = (HARDENING / "goose-hardening.patch").read_text()
    added = "\n".join(line[1:] for line in patch.splitlines() if line.startswith("+") and not line.startswith("+++"))
    removed = "\n".join(line[1:] for line in patch.splitlines() if line.startswith("-") and not line.startswith("---"))
    smoke = (HARDENING / "smoke.sh").read_text()
    patched = ["src/gfx.h", "src/jit.h", "src/main.cpp", "src/packages.h", "src/parser.h", "src/typecheck_builtins.h",
               "src/utils.h"]
    assert sorted(re.findall(r"^diff --git a/(\S+)", patch, re.M)) == patched
    for gone in ('getenv("GOOSE_TCCLIB")', 'getenv("GOOSE_STDLIB")', 'arg == "-D"', 'arg == "--include"', 'arg == "--stdlib"',
                 'arg == "--unsafe-no-rf-check"', 'cands.push_back("stdlib/")', 'arg == "-o"', 'arg == "--standalone"',
                 'arg == "--header"', 'arg == "--emit-runtime"', 'arg == "--gen-runtime-header"', "RuntimeObjectSource()"):
        assert gone in removed and gone not in added, gone
    assert "if (!LoadFile(path, bytes)) Error(c, cat(\"embed_file: cannot open \", path));" in removed
    assert "extern \"C\" const char goose_build_marker[] = GOOSE_BUILD_MARKER;" in added
    for gone in ("  -D NAME[=VALUE]       Define a C macro in the generated program (or -DNAME).",
                 "  --emit-runtime out.c  Write the runtime's C.", "  --unsafe-no-rf-check  Leave out the checks after calls"):
        assert gone in removed, gone
    assert "goose help $topic still offers a removed option" in smoke
    assert "if (SystemFile(f, path)) {" in added and '"run /proc/self/environ"' in smoke and "envmod.goose" in smoke
    for message in ("extern fn is only allowed in the standard library", "sidecar files are not supported",
                    "goose build is not available", "is outside the directory of the file that embeds it",
                    "embed_shader is not available in this build of goose"):
        assert message in added and message in smoke
    for option in ("-D", "--include", "--stdlib", "--unsafe-no-rf-check", "-o", "--standalone", "--header", "--emit-runtime",
                   "--gen-runtime-header"):
        assert f'"unknown option: {option}' in smoke, option
    for refused in ("GOOSE_TCCLIB", "GOOSE_STDLIB", "cannot find the module os", "cannot find the module ffi", "main.build",
                    "embed_case /proc/self/maps", "embed_case ../data.txt", "ln -s /proc/self/maps"):
        assert refused in smoke, refused
    # The sources the patch expects, rebuilt from its own context, take it once through apply.sh and refuse it twice.
    tree = tmp_path / "src-tree"
    for name, body in re.findall(r"^diff --git a/(\S+) .*?\n(.*?)(?=^diff --git |\Z)", patch, re.M | re.S):
        lines = [line[1:] for line in body.splitlines() if line[:1] in (" ", "-") and not line.startswith("---")]
        (tree / name).parent.mkdir(parents=True, exist_ok=True)
        (tree / name).write_text("\n".join(lines) + "\n")
    (tree / "stdlib").mkdir()
    for module in ("std", "os", "ffi"):
        (tree / "stdlib" / f"{module}.goose").write_text(f"// {module}\n")
    first = subprocess.run(["sh", str(HARDENING / "apply.sh"), str(tree)], capture_output=True, text=True, timeout=60)
    assert first.returncode == 0, first.stdout + first.stderr
    assert sorted(p.name for p in (tree / "stdlib").iterdir()) == ["std.goose"]
    assert all("Hardened build" in (tree / name).read_text() for name in patched)
    second = subprocess.run(["sh", str(HARDENING / "apply.sh"), str(tree)], capture_output=True, text=True, timeout=60)
    assert second.returncode != 0


def test_the_smoke_test_fails_a_compiler_that_is_not_hardened(tmp_path):
    lax = tmp_path / "goose"
    lax.write_text('#!/bin/sh\n[ "$1" = run ] && echo "hardened 8 true"\nexit 0\n')
    lax.chmod(0o755)
    shim = tmp_path / "bin"
    shim.mkdir()
    if shutil.which("timeout") is None:  # macOS has no coreutils timeout
        (shim / "timeout").write_text('#!/bin/sh\nshift\nexec "$@"\n')
        (shim / "timeout").chmod(0o755)
    done = subprocess.run([shutil.which("bash"), str(HARDENING / "smoke.sh"), str(lax)], capture_output=True, text=True,
                          timeout=120, env={"PATH": f"{shim}:/usr/bin:/bin"})
    assert done.returncode != 0 and "hardening smoke test failed" in done.stderr


def test_nothing_the_agent_sees_names_a_reference_answer_or_a_budget():
    seen = {"Dockerfile": (TASK / "environment" / "Dockerfile").read_text(), "instruction.md": (STEP / "instruction.md").read_text(),
            "run_examples.py": RUNNER.read_text(), "task.toml": (TASK / "task.toml").read_text()}
    for name, text in seen.items():
        lowered = text.lower()
        for word in ("oracle", "reference solution", "hidden", "grade", "grading", "working session", "fresh context", "hours",
                     "candidate"):
            assert word not in lowered, (name, word)
    assert "#" not in seen["task.toml"]
    assert sorted(path.name for path in (TASK / "environment").iterdir()) == [".dockerignore", "Dockerfile", "app-manifest", "fs-reserve",
                                                                          "proc-reaper"]
    assert "extern" in seen["instruction.md"].split("Out of scope:", 1)[1]
    # The root-only scripts and their paths look like ordinary system housekeeping: nothing in their names, their
    # state and log paths or their text says what the submission is for or that the session is timed.
    for name in ("app-manifest", "fs-reserve", "proc-reaper"):
        lowered = (TASK / "environment" / name).read_text().lower()
        for word in ("deliver", "watchdog", "grad", "harbor", "platform", "verif", "submission", "session", "agent", "collect",
                     "budget", "deadline", "cap ", "capped", "trial", "oddish"):
            assert word not in lowered, (name, word)
    for text in (seen["Dockerfile"], seen["task.toml"]):
        for word in ("deliver", "watchdog", "precap", "collect-", "grad"):
            assert word not in text.lower(), word


def test_every_run_fits_inside_the_step_verifier_time():
    per_run = int(re.search(r"^CASE_SEC = (\d+)$", RUNNER.read_text(), re.M).group(1))
    total = int(re.search(r"^TOTAL_SEC = (\d+)", (STEP / "tests" / "verify.py").read_text(), re.M).group(1))
    toml = (TASK / "task.toml").read_text()
    step_verifier = int(re.search(r"\[steps\.verifier\]\s*timeout_sec = (\d+)", toml).group(1))
    assert 1500 * per_run <= total < step_verifier
    agent = int(re.search(r"\[steps\.agent\]\s*timeout_sec = (\d+)", toml).group(1))
    assert agent + step_verifier <= 11 * 3600, "the attempt stays inside the platform's 12 hours"
    assert f"Each run finishes within {per_run} seconds" in (STEP / "instruction.md").read_text()


def test_only_documentation_samples_and_the_reduced_standard_library_reach_the_agent():
    spec = importlib.util.spec_from_file_location("goose_rebuild_package_step", SCRIPTS / "package_step.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in ("README.md", "LICENSE", "docs/reference.md", "docs/design/packages.md", "samples/hello.goose", "samples/README.md"):
        assert module.shipped_docs(name) and module.agent_visible(name), name
    for name in ("docs/testing.md", "test/errors_tc/a.goose", "test/expected/a.out", "samples/data/alice.txt", "tree-sitter/grammar.js",
                 "src/main.cpp", "docs/site/index.html", "vscode/package.json", "bench/goose/lru.goose"):
        assert not module.shipped_docs(name) and not module.agent_visible(name), name
    assert module.agent_visible("stdlib/std.goose") and not module.agent_visible("stdlib/os.goose")
    assert set(module.DROPPED) == {"stdlib/os.goose", "stdlib/ffi.goose"}
    assert sorted(path.name for path in HARDENING.iterdir()) == ["apply.sh", "build.sh", "goose-hardening.patch", "smoke.sh"]
