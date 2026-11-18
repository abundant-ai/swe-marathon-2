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
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
STEP = TASK / "steps" / "01-rebuild-compiler"
SCRIPTS = TASK / "scripts"
RUNNER = STEP / "tests" / "verifier" / "runcases.py"
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
            assert not any("//" in text or "/*" in text for text in texts), case
        assert not any(re.search(r"\b(extern|thread_fn|thread_spawn)\b|import (gfx|os|ffi)\b", text) for text in texts)
        assert not any("no-jit" in text for text in texts)
    assert any(len(case["files"]) > 1 and case["kind"] == "modules" for case in private)
    assert all(case["argv"][2:4] == ["--diagnostics", "json"] or case["argv"] == ["run", "main.goose"]
               for case in private if case["kind"] == "rejected")
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
        print(json.dumps([mc.leaks([case("P1", program)], [], shipped),
                          mc.leaks([case("P2", "fn main() { print(2); }\\n")], [case("E1", "fn main() {print(2);}")], ""),
                          mc.leaks([case("P3", "fn main() { print(3); }\\n")], [case("E2", program)], shipped)]))
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
            moved = mc.relayout(rng, commented)
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
    assert len({tuple(argv) for argv in private}) == len(private) and len(private) <= 40
    assert all(argv in private for argv in visible_cases)
    assert abs(sum(share for _, share in kinds) - 1) < 1e-9


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
        print(json.dumps([good, bad, "--no-new-privs" in Path(verify.__file__).read_text()]))
    """))
    good, bad, no_new_privs = report
    assert good == [] and all(problems for problems in bad) and no_new_privs
    modes = {path.relative_to(top).as_posix(): os.lstat(path).st_mode & 0o7777 for path in [top, *top.rglob("*")]}
    assert modes == {".": 0o755, "goose": 0o755, "lib": 0o755, "lib/helper": 0o755, "lib/data": 0o644, "link": modes["link"]}
    assert (top / "link").is_symlink()


def test_recorder_keeps_only_cases_that_finish_the_same_way_twice_and_soon(tmp_path):
    program = tmp_path / "fake-goose"
    program.write_text("#!/usr/bin/env python3\nimport os, sys, time\n"
                       "if 'help' in sys.argv: print(os.urandom(4).hex())\n"
                       "elif 'version' in sys.argv: time.sleep(5)\n"
                       "elif 'lag' in sys.argv: time.sleep(0.8); print('late')\n"
                       "else: print(' '.join(sys.argv[1:]), sorted(os.listdir('.')))\n"
                       "sys.exit(2 if 'check' in sys.argv else 0)\n")
    program.chmod(0o755)
    cases = [{"id": f"P{i}", "files": {"main.goose": "fn main() {}\n"}, "argv": argv, "stdin": None}
             for i, argv in enumerate([["run", "main.goose"], ["check", "main.goose"], ["help"], ["version"], ["format"]])]
    source, outputs, kept, timing = (tmp_path / name for name in ("cases.json", "outputs.json", "kept.json", "timing.json"))
    source.write_text(json.dumps({"cases": cases}))
    done = subprocess.run([sys.executable, "-B", str(RUNNER), "record", str(program), str(source), str(outputs), "--keep", str(kept)],
                          capture_output=True, text=True, timeout=120)
    assert done.returncode != 0 and "2 did not finish the same way twice" in done.stdout + done.stderr
    cases = cases[:2] + [cases[4]] * 8
    for index, case in enumerate(cases):
        cases[index] = dict(case, id=f"P{index}")
    cases += [{"id": "P98", "files": {}, "argv": ["lag"], "stdin": None}, {"id": "P99", "files": {}, "argv": ["help"], "stdin": None}]
    source.write_text(json.dumps({"cases": cases}))
    done = subprocess.run([sys.executable, "-B", str(RUNNER), "record", str(program), str(source), str(outputs), "--keep", str(kept),
                           "--report", str(timing)], capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stdout + done.stderr
    assert [c["id"] for c in json.loads(kept.read_text())["cases"]] == [f"P{i}" for i in range(10)]
    report = json.loads(timing.read_text())
    assert report["slow"] == ["P98"] and report["unsteady"] == ["P99"] and report["keep_seconds"] == 0.5
    assert min(report["seconds"]["P98"]) >= 0.8 and max(max(report["seconds"][f"P{i}"]) for i in range(10)) < 0.5
    check = subprocess.run([sys.executable, "-B", str(RUNNER), "check", str(program), str(kept), str(outputs)],
                           capture_output=True, text=True, timeout=120)
    assert check.stdout.strip().splitlines()[-1] == "10 of 10 cases pass"


def test_the_recording_report_counts_outputs_equal_to_upstream_and_the_floor(tmp_path):
    digest = hashlib.sha256(b"6\n").hexdigest()
    kept = [{"id": "P1", "kind": "run", "upstream": digest}, {"id": "P2", "kind": "run", "upstream": digest},
            {"id": "P3", "kind": "check"}]
    cases = kept + [{"id": "P4", "kind": "modules"}, {"id": "P5", "kind": "run"}]
    expected = {"P1": {"exit": 0, "stdout": "6\n"}, "P2": {"exit": 0, "stdout": "7\n"}, "P3": {"exit": 1, "stdout": ""}}
    timing = {"keep_seconds": 0.5, "seconds": {"P1": [0.1, 0.2], "P2": [0.3, 0.1], "P3": [0.05, 0.05], "P4": [0.9, 0.8], "P5": [0.1, 2]},
              "slow": ["P4"], "unsteady": ["P5"]}
    for name, data in (("cases.json", {"cases": cases}), ("kept.json", {"cases": kept}), ("expected.json", expected), ("timing.json", timing)):
        (tmp_path / name).write_text(json.dumps(data))
    subprocess.run([sys.executable, "-B", str(STEP / "tests" / "verifier" / "recording.py"),
                    *(str(tmp_path / name) for name in ("cases.json", "kept.json", "expected.json", "timing.json", "out.json"))],
                   check=True, capture_output=True, timeout=60)
    report = json.loads((tmp_path / "out.json").read_text())
    assert report["run_cases_with_upstream_output"] == 2 and report["run_cases_printing_upstream_output"] == 1
    assert report["empty_stdout_by_exit"] == {"1": 1} and report["kinds_kept"] == {"check": 1, "run": 2}
    assert report["dropped_slow"] == {"modules": 1} and report["dropped_unsteady"] == {"run": 1}
    assert report["kept_seconds_max"] == 0.3 and report["cases_kept"] == 3 and report["cases_recorded"] == 5


# ---------------------------------------------------------------- hardening and images

def test_images_and_solution_build_one_hardened_compiler_and_ship_no_private_cases():
    agent = (TASK / "environment" / "Dockerfile").read_text()
    verifier = (STEP / "tests" / "Dockerfile").read_text()
    solve = (STEP / "solution" / "solve.sh").read_text()
    builder = agent.split("\n\nFROM ubuntu:24.04\n", 1)[0]
    assert verifier.startswith(builder), "both images must build the compiler the same way"
    build = (HARDENING / "build.sh").read_text()
    for flag in ("-DGOOSE_VERSION=745901f", "-DGOOSE_STDLIB_PATH=/usr/local/share/goose/stdlib", 'make_goose "-static -s"',
                 'make_goose "-s"', 'bash "$here/smoke.sh" "$build/goose"'):
        assert flag in build, flag
    assert not any(step in text for step in ("cmake -S", "cmake --build") for text in (builder, solve)), "one build, in build.sh"
    assert builder.index("sh /hardening/apply.sh /src") < builder.index("cp -a /src/stdlib /usr/local/share/goose/stdlib") \
        < builder.index("sh /hardening/build.sh /src /build 4") < builder.index("bash /hardening/smoke.sh /opt/goose/goose")
    assert solve.index('sh "$here/hardening/apply.sh" "$src"') < solve.index('sh "$here/hardening/build.sh" "$src" "$build"') \
        < solve.index("install -m 0755")
    assert "--link /build/link" in verifier
    final_agent = agent.split("\n\nFROM ubuntu:24.04\n", 1)[1]
    final_verifier = verifier.split("\n\nFROM ubuntu:24.04\n", 1)[1]
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
    patched = ["src/gfx.h", "src/jit.h", "src/main.cpp", "src/packages.h", "src/parser.h", "src/typecheck_builtins.h"]
    assert sorted(re.findall(r"^diff --git a/(\S+)", patch, re.M)) == patched
    for gone in ('getenv("GOOSE_TCCLIB")', 'getenv("GOOSE_STDLIB")', 'arg == "-D"', 'arg == "--include"', 'arg == "--stdlib"',
                 'arg == "--unsafe-no-rf-check"', 'cands.push_back("stdlib/")', 'arg == "-o"', 'arg == "--standalone"',
                 'arg == "--header"', 'arg == "--emit-runtime"', 'arg == "--gen-runtime-header"', "RuntimeObjectSource()"):
        assert gone in removed and gone not in added, gone
    assert "if (!LoadFile(path, bytes)) Error(c, cat(\"embed_file: cannot open \", path));" in removed
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
    assert sorted(path.name for path in (TASK / "environment").iterdir()) == [".dockerignore", "Dockerfile"]
    assert "extern" in seen["instruction.md"].split("Out of scope:", 1)[1]


def test_every_run_fits_inside_the_step_verifier_time():
    per_run = int(re.search(r"^CASE_SEC = (\d+)$", RUNNER.read_text(), re.M).group(1))
    total = int(re.search(r"^TOTAL_SEC = (\d+)", (STEP / "tests" / "verify.py").read_text(), re.M).group(1))
    step_verifier = int(re.search(r"\[steps\.verifier\]\s*timeout_sec = (\d+)", (TASK / "task.toml").read_text()).group(1))
    assert 1500 * per_run <= total < step_verifier
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
