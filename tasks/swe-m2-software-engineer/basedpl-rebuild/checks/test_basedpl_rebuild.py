"""Development checks: the original is one hardened build that both images install with their marker
and the reference solution without; the verifier counts what a submission does as that submission's
failed cases; the recorder keeps only steady answers that need an interpreter; the cases are
reproducible, unknown to the agent and rewritten so that their answers are not upstream's; and the
agent sees the binary and the documentation, nothing else.

Script and verifier code runs in processes of its own: another task's checks have modules named
`make_cases`, `seeds` and `verifier` too.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
STEP = TASK / "steps" / "01-rebuild-interpreter"
SCRIPTS = TASK / "scripts"
RUNNER = STEP / "tests" / "verifier" / "runcases.py"
RECORDER = STEP / "tests" / "verifier" / "recorder.py"
HARDENING = TASK / "common" / "hardening"


def scripts_call(code: str) -> object:
    """The JSON a snippet prints with the task's scripts importable, in a process of its own."""
    done = subprocess.run([sys.executable, "-B", "-c", f"import sys; sys.path.insert(0, {str(SCRIPTS)!r})\n" + code],
                          capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


def verifier_call(code: str) -> object:
    """The JSON a snippet prints with the verifier importable, in a process of its own."""
    done = subprocess.run([sys.executable, "-B", "-c", f"import sys; sys.path.insert(0, {str(STEP / 'tests')!r})\n" + code],
                          capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


# ---------------------------------------------------------------- an upstream stand-in

DOC_PROGRAM = "shown←3 4ρι12\n⌽shown"
NOTEBOOK = {"metadata": {"kernelspec": {"language": "bpl"}}, "cells": [
    {"cell_type": "markdown", "source": "# Demo\n"},
    {"cell_type": "code", "source": ["x←2 5 7\n", "+/x"], "outputs": [{"output_type": "execute_result", "data": {"text/plain": ["14"]}}]}]}
CORE = """⍝⍝ Values

⍝ sum-a — a sum of a few numbers
+/3 4 25   ⍝ 32

⍝ scale-b — a dfn that scales
scale←{α×ω} ◇ 7 scale 2 9   ⍝ 14 63

⍝ text-c — text and a count
≢"quiet garden window"   ⍝ 19

⍝ check-d — a check
(2+2)≡4   ⍝ $t

⍝ near-copy — the documentation's program with other numbers
mine←5 6ρι30 ◇ ⌽mine   ⍝ 5 6ρ0

⍝ random-e — random
¿6   ⍝ 3

⍝ clock-f — the clock
1714990830<•time 0   ⍝ $t

⍝ input-g — reads a line
x←⍎⎕ ◇ x+11
⍝ input: 31

⍝ error-h — a domain error
1÷'a'
⍝ error: DOMAIN ERROR

⍝ multi-i — two lines
total←+/4 9 12
total×3
⍝ =>
75

⍝ comment-j — a comment that states the answer
2×21   ⍝ 42
"""
APL = "⍝⍝ Ported\n\n" + "\n".join(f"⍝ apl:{i} — a port\n{i + 2}×{i + 5}-3   ⍝ {(i + 2) * (i + 2)}\n" for i in range(60))
MORE = "\n".join(f"⍝ one-{i} — a value\nv{i}←{i + 3} {i + 8} {i + 4} ◇ (+/v{i})×{i + 2}   ⍝ {i}\n" for i in range(60)) + "\n" + \
    "\n".join(f"⍝ two-{i} — two lines\nw←{i + 5} {i + 9}\nw⌈{i + 6}\n⍝ =>\n{i}\n" for i in range(25))
LIB = '⍝ — a library function\n[double:]←•load "lib/array.bpl"\ndouble 3 8   ⍝ 6 16\n'


def upstream(tmp_path: Path) -> Path:
    """A small upstream tree in a plain directory: documentation (a Quarto page holding a program, a
    glyph page, a notebook with a stored result), reference files and a library module."""
    root = tmp_path / "basedpl"
    files = {
        "LICENSE": "Apache License 2.0\n",
        "nbs/llms.txt": "# BPL\n",
        "nbs/guide.qmd": f"# Guide\n\n```bpl\n{DOC_PROGRAM}\n```\n",
        "nbs/glyphs/plus.qmd": "# `+` — Plus\n\n```bpl\n2+3      ⍝ 5\n```\n",
        "nbs/system/demo.ipynb": json.dumps(NOTEBOOK),
        "nbs/gallery/art.bpl": "•plot 1 2 3\n",
        "tests/reference/core.bpl": CORE + "\n" + MORE,
        "tests/reference/aplcart.bpl": APL,
        "tests/reference/lib.bpl": LIB,
        "lib/array.bpl": "double←2×\n",
    }
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    return root


def generate(tmp_path: Path, seed: int, scale: float = 0.05) -> list[dict]:
    """make_cases.py's cases for the stand-in tree."""
    root = upstream(tmp_path) if not (tmp_path / "basedpl").exists() else tmp_path / "basedpl"
    out = tmp_path / f"cases-{seed}.json"
    done = subprocess.run([sys.executable, "-B", str(SCRIPTS / "make_cases.py"), str(root), "--seed", str(seed), "--scale",
                           str(scale), "--out", str(out)], capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]
    return json.loads(out.read_text())["cases"]


def programs_of(case: dict) -> str:
    """Every piece of BPL a case holds: its files, its -e code and its standard input."""
    return "\n".join(list(case["files"].values()) + case["argv"] + [case["stdin"] or ""])


# ---------------------------------------------------------------- text, records and rewrites

def test_tokens_round_trip_and_names_end_where_bpl_ends_them():
    out = scripts_call(textwrap.dedent('''
        import json, bpl_text as t
        code = 'f←{α×ω+2.5ₓ} ◇ T.q1 ◇ x_1+"a""b" ◇ v₁←¯3 ◇ 1e5 2j3 1r3 3ₓ₈ ⍴z f2 ⍝ note\\n\\'\\'\\' \\'\\''
        tokens = t.tokenize(code)
        print(json.dumps([t.untokenize(tokens) == code, [(k.kind, k.text) for k in tokens if k.kind != "space"],
                          t.skeleton("scale←2×ι5 ⍝ c\\nscale+1"), t.statements("a←1 ◇ [b◇c]\\n⍝ x\\nd")]))
    '''))
    same, tokens, shape, parts = out
    assert same
    assert ["name", "f"] in tokens and ["number", "2.5ₓ"] in tokens and ["name", "q1"] in tokens
    assert ["string", '"a""b"'] in tokens and ["number", "¯3"] in tokens and ["glyph", "₁"] in tokens
    assert ["number", "1e5"] in tokens and ["number", "2j3"] in tokens and ["number", "1r3"] in tokens
    assert ["number", "3ₓ₈"] in tokens and ["name", "⍴z"] in tokens, "⍴ is no BPL glyph: it is part of a name"
    assert ["name", "f"] in tokens and ["number", "2"] in tokens, "a digit ends a name"
    assert ["char", "'''"] in tokens and ["char", "''"] in tokens and ["comment", "⍝ note"] in tokens
    assert shape == "X←N×ιN◇X+N" and parts == ["a←1", "[b◇c]", "d"]


def test_reference_records_read_as_upstreams_reader_reads_them():
    text = ('•prefs ["kinds":"static"]\n\n⍝⍝ setup\nbase←10\n\n⍝⍝ Things\n\n⍝ one — inline\n1+2   ⍝ 3\n\n⍝ two — split\nx←1\nx+1\n⍝ =>\n2\n\n'
            '⍝ three — an error\n÷\'a\'\n⍝ error: DOMAIN ERROR\n\n⍝ four — input\n⍎⎕   ⍝ 5\n⍝ input: 5\n\n⍝ five — timed\n+/ι9\n⍝⍝: 1 2 3\n')
    setup, records = scripts_call(f"import json, bpl_text\nprint(json.dumps(bpl_text.reference_records('static.bpl', {text!r})))")
    by_id = {record["id"]: record for record in records}
    assert setup == "base←10" and set(by_id) == {"one", "two", "three", "four", "five"}
    assert by_id["one"]["code"] == "1+2" and by_id["one"]["expected"] == "3" and by_id["one"]["prefs"] == '•prefs ["kinds":"static"]'
    assert by_id["two"]["code"] == "x←1\nx+1" and by_id["two"]["expected"] == "2"
    assert by_id["three"]["expected_error"] == "DOMAIN ERROR" and by_id["four"]["input"] == "5"
    assert by_id["five"].get("timed") and by_id["one"]["section"] == "Things"


def test_rewrites_leave_sizes_checks_keys_and_option_text_alone():
    out = scripts_call(textwrap.dedent('''
        import json, random, rewrite
        def sites(code):
            tokens = rewrite.tokenize(code)
            return [tokens[i].text for i in rewrite.number_sites(code)]
        cases = {
            "values": "7+3×12.5", "reshape": "3 4ρ7", "iota": "ι15+9", "rank": "+/⍤2⁝9", "take": "4↑12 13",
            "check": "(2+7)≡9", "prefs": '•prefs ["prec":4] ◇ 5', "keys": '["a":7 "b":9]', "zero": "0 1+9",
            "big": "1234567+5", "exponent": "1e5+2j3", "index": "v.[3]+9",
        }
        print(json.dumps({name: sites(code) for name, code in cases.items()} |
                         {"texts": [rewrite.text_sites(c) != [] for c in ('"quiet garden"', '"key":5', '"DOMAIN"::0', '"x" •c "Some Text"')],
                          "edited": rewrite.edited_text('"Quiet garden, OPEN"', random.Random(3)),
                          "number": [rewrite.edited_number(t, random.Random(4)) for t in ("12", "¯7", "2.50", "9ₓ₁", "6ᵣ")]}))
    '''))
    assert out["values"] == ["7", "3", "12.5"] and out["reshape"] == [] and out["iota"] == ["9"]
    assert out["rank"] == ["9"] and out["take"] == [] and out["check"] == [] and out["prefs"] == []
    assert out["keys"] == ["7", "9"] and out["zero"] == ["9"] and out["big"] == ["5"] and out["exponent"] == []
    assert out["index"] == ["9"]
    assert out["texts"] == [True, False, False, False]
    edited = out["edited"]
    assert len(edited) == len('"Quiet garden, OPEN"') and edited[1].isupper() and edited[-5:-1].isupper() and ", " in edited
    twelve, minus, decimal, byte, rational = out["number"]
    assert twelve != "12" and twelve.isdigit() and minus.startswith("¯") and re.fullmatch(r"\d+\.\d\d", decimal)
    assert byte.endswith("ₓ₁") and int(byte[:-2]) <= 100 and rational.endswith("ᵣ")


def test_renames_are_consistent_and_use_unused_words():
    out = scripts_call(textwrap.dedent('''
        import json, random, rewrite
        code = 'f←{α+ω} ◇ [a b]←1 2 ◇ T←["k":a] ◇ T.k f b ◇ Grid←2 2ρf/a b'
        mapping = rewrite.renaming(code, random.Random(9))
        print(json.dumps([mapping, rewrite.renamed(code, mapping), rewrite.renaming('x←"x" ◇ ⍎"x+1"', random.Random(9))]))
    '''))
    mapping, renamed, unsafe = out
    assert set(mapping) == {"f", "a", "b", "T", "Grid"} and len(set(mapping.values())) == 5
    assert mapping["Grid"][0].isupper() and not any(word[0] in "ejrEJ" for word in mapping.values())
    assert renamed.count(mapping["f"]) == 3 and '"k":' in renamed and f"{mapping['T']}.k" in renamed
    assert unsafe == {}, "code that runs text as code keeps its names"


def test_cases_are_reproducible_and_nothing_documented_or_excluded_becomes_a_case(tmp_path):
    first, again, other = generate(tmp_path, 5), generate(tmp_path, 5), generate(tmp_path, 6)
    assert first == again and first != other
    assert all(re.fullmatch(r"P\d{5}", case["id"]) for case in first) and len({c["id"] for c in first}) == len(first)
    held = "\n".join(programs_of(case) for case in first)
    for gone in ("¿", "•time", "mine", "⍝ 42"):
        assert gone not in held, gone
    assert "shown" not in held, "the documentation's own program"
    kinds = {case["kind"] for case in first}
    assert {"expr", "script", "apl", "error", "worker", "display", "stdin", "module", "program", "cli"} <= kinds, kinds
    reference = [case for case in first if case.get("suite")]
    assert sum(case["suite"] == "apl" for case in reference) <= 0.5 * len(reference)
    module = next(case for case in first if case["kind"] == "module")
    assert module["files"]["lib/array.bpl"] == "double←2×\n" and "main.bpl" in module["files"]
    rewritten = [case for case in first if case.get("record")]
    assert rewritten and all(variant != {key: case[key] for key in variant} for case in rewritten
                             for variant in case["record"]["variants"])


def test_cases_need_an_interpreter_carry_state_and_leave_out_what_the_docs_show():
    """QA waves 1 and 2: error cases print a computed value before the error, never a literal an
    echo could copy, and most of the uncaught ones (and every syntax error) run in the worker, whose
    reply carries the message and span; guards always print the message; worker sessions keep
    state between requests; piped input is several lines with a failing one among them; display
    cases name their setting for the recorder; derivatives are thinned; a `_` subscript needs a
    digit; a literal beside `=` is never rewritten; and runs of documented statements count as
    documented, in every rewrite too."""
    import random
    sys.path.insert(0, str(SCRIPTS))
    import bpl_text
    import make_cases
    import rewrite
    sys.path.insert(0, str(STEP / "tests" / "verifier"))
    import recorder
    assert [(token.kind, token.text) for token in bpl_text.tokenize("_←x¨ 1")][:3] == [("name", "_"), ("glyph", "←"), ("name", "x")]
    assert bpl_text.tokenize("x_12←3")[0].text == "x_12"
    assert not rewrite.number_sites("x←3 4=3 5") and rewrite.number_sites("x←3 4+3 5")
    assert all("$e.message" in handler or handler == "$e" for handler in make_cases.HANDLERS)
    assert make_cases.DERIVATIVE_KEEP <= 0.6
    rng = random.Random(3)
    for _ in range(200):  # no lead is a literal that an echo could copy
        lead = rng.choice(make_cases.LEADS)(rng)
        assert lead.startswith("⎕←") and recorder.literal_value(lead[2:]) is None, lead
    error = {"code": "1 2+3 4 5", "file": "core.bpl", "line": 7, "expected_error": "LENGTH ERROR"}
    forms = [make_cases.plain_error_case(error, "", random.Random(seed)) for seed in range(40)]
    assert {case["form"] for case in forms} == {"reply", "plain"} and sum(case["form"] == "reply" for case in forms) > 15
    reply = next(case for case in forms if case["form"] == "reply")
    requests = [json.loads(line) for line in reply["stdin"].splitlines()]
    assert reply["argv"] == ["--worker"] and requests[-1]["code"] == "1 2+3 4 5" and reply["record"]["scaffold_lines"] == [0]
    syntax = make_cases.plain_error_case(dict(error, code="(9+7", expected_error="SYNTAX ERROR"), "", random.Random(1), True)
    assert syntax["form"] == "reply"
    records = [({"code": f"{name}←{value} ◇ {name}×2", "file": "core.bpl", "line": value}, "") for value, name in ((3, "a"), (4, "b"))]
    sessions = [make_cases.worker_case(records, random.Random(seed)) for seed in range(10)]
    for session in sessions:
        lines = [json.loads(line) for line in session["stdin"].splitlines()]
        earlier, carried, setting = set(), False, False  # what an earlier request left (names, a display setting) in use later
        for line in lines:
            code = line.get("code", "")
            here = set(re.findall(r"([A-Za-z]+)←", code)) | set(line.get("bindings", {}))
            carried = carried or bool((set(re.findall(r"[A-Za-z]+", code)) - here) & earlier) or (setting and bool(code))
            earlier |= here
            setting = setting or "•prefs" in code
        assert carried, [line.get("code") for line in lines]
        assert set(session["record"]["scaffold_lines"]) and all(isinstance(number, int) for number in session["record"]["scaffold_lines"])
    multi = {"code": "total←3 4 5\ncount←≢total\ntotal÷count", "file": "core.bpl", "line": 9}
    piped = [make_cases.stdin_case(multi, "", random.Random(seed), "1 2+3 4 5") for seed in range(12)]
    pipe = next(case for case in piped if case["form"] == "pipe")
    assert pipe["argv"] == [] and pipe["stdin"].count("\n") == 4 and pipe["stdin"].splitlines()[1] == "1 2+3 4 5"
    shown = make_cases.display_case({"code": "2.5×ι12", "file": "core.bpl", "line": 3}, "", random.Random(2))
    assert shown["record"]["unset"][0] == "main.bpl" and shown["record"]["unset"][1] in shown["files"]["main.bpl"]
    pages = {"arrays.md": "# Arrays\n\n```bpl\nm←3 4ρι12\nx←[[+ ×] [- ÷]]\nf←1⊃0⊃x\n2 f 3\n```\n"}
    skeletons, texts = bpl_text.leak_index(pages)
    run = "y←[[+ ×] [- ÷]]\ng←1⊃0⊃y\n2 g 3"  # the block's last three statements, renamed
    assert bpl_text.skeleton(run) in skeletons, "a run of documented statements is the docs' program"
    case = {"kind": "script", "argv": ["main.bpl"], "files": {"main.bpl": "⎕←1\n"}, "stdin": None,
            "record": {"variants": [{"files": {"main.bpl": run + "\n"}}], "want": "same"}}
    assert make_cases.leaks([case], skeletons, texts) == ["0"], "a rewrite the recorder may settle on is checked too"


def test_command_line_cases_are_one_per_behaviour():
    cases = scripts_call("import json, make_cases\nprint(json.dumps(make_cases.cli_cases()))")
    keys = [json.dumps([case["argv"], case["files"], case["stdin"]], sort_keys=True) for case in cases]
    assert len(keys) == len(set(keys)) == len({case["source"] for case in cases})
    argvs = [case["argv"] for case in cases]
    for wanted in (["--help"], ["--version"], ["--costs", "speed.bpl"], ["--kernel", "-f", "connection.json"], ["/etc/passwd"]):
        assert wanted in argvs, wanted
    assert any(case["argv"] == ["--worker"] and "call" in case["stdin"] for case in cases)


def test_program_templates_give_programs_for_any_seed():
    out = scripts_call(textwrap.dedent('''
        import json, random, programs
        found = []
        for seed in range(6):
            for case in programs.program_cases(random.Random(seed), 25) + programs.display_cases(random.Random(seed), 12):
                found.append(case)
        print(json.dumps(found))
    '''))
    families = {case.get("family") for case in out if case["kind"] == "program"}
    assert len(families) == 25
    for case in out:
        assert case["argv"] and all(name.endswith(".bpl") for name in case["files"])
        text = programs_of(case)
        if case["kind"] == "program":
            assert text.count("{") == text.count("}") and text.count("[") == text.count("]"), case["source"]
        assert "⍳" not in text and "⍴" not in text and "∘." not in text, "APL spellings BPL does not have"
    by_family = {}
    for case in out:
        by_family.setdefault(case.get("family"), set()).add(programs_of(case))
    assert all(len(texts) > 1 for name, texts in by_family.items() if name), "the seed changes every program's data"


def test_the_documentation_is_upstreams_pages_without_notebook_results(tmp_path):
    root = upstream(tmp_path)
    pages = scripts_call(f"import json, bpl_text\nfrom pathlib import Path\nprint(json.dumps(bpl_text.documentation(Path({str(root)!r}))))")
    assert sorted(pages) == ["LICENSE", "glyphs/plus.md", "guide.md", "llms.txt", "system/demo.md"]
    assert "```bpl\nx←2 5 7\n+/x\n```" in pages["system/demo.md"] and "14" not in pages["system/demo.md"]
    assert pages["glyphs/plus.md"].startswith("# `+`") and "•plot" not in "".join(pages.values())


# ---------------------------------------------------------------- the verifier

def run_verifier(tmp_path: Path, script: str, cases: list[dict], expected: dict, case_sec: float = 2,
                 output_limit: int | None = None) -> dict:
    """grade() of the real verify.py, in a process of its own, with the workspace under tmp_path and
    no privilege drop (macOS and CI runners have no setpriv): what the submission can do to its
    workspace and its output is the same."""
    program = tmp_path / "bpl"
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
        verify.runcases.WORKSPACE = Path({str(tmp_path / 'tmp' / 'bpl-run')!r})
        verify.runcases.HOME = Path({str(tmp_path / 'tmp' / 'bpl-home')!r})
        verify.runcases.TEMP = Path({str(tmp_path / 'tmp' / 'bpl-tmp')!r})
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
    cases = [{"id": f"P{i}", "files": {"main.bpl": "1\n"}, "argv": argv, "stdin": None} for i, argv in enumerate(argvs)]
    for case, kind in zip(cases, kinds or []):
        case["kind"] = kind
    return cases, {case["id"]: {"exit": 0, "stdout": "ok\n"} for case in cases}


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
    cases, expected = plain_cases([["a"], ["b"], ["slow"], ["c"]], kinds=["expr", "expr", "worker", "display"])
    metrics = run_verifier(tmp_path, 'case "$1" in slow) exec sleep 5;; b) echo no; exit 0;; esac\necho ok\n', cases, expected,
                           case_sec=1.0)
    assert metrics["by_kind"] == {"expr": {"total": 2, "run": 2, "passed": 1, "failed": 1},
                                  "worker": {"total": 1, "run": 1, "passed": 0, "failed": 1},
                                  "display": {"total": 1, "run": 1, "passed": 1, "failed": 0}}
    assert metrics["cases_failed"] == 2 and metrics["timeouts"] == 1
    assert 1.0 <= metrics["seconds_max"] < 3 and metrics["seconds_max"] <= metrics["seconds_total"]


def test_case_files_standard_input_and_arguments_reach_the_program(tmp_path):
    cases = [{"id": "P1", "files": {"main.bpl": "⎕←1\n", "lib/a.bpl": "x←1\n"}, "argv": ["main.bpl", "-", "two words"],
              "stdin": "line one\nline two\n"}]
    script = 'printf "%s|" "$@"; cat main.bpl lib/a.bpl; cat; [ -z "$(ls -A "$HOME")$(ls -A "$TMPDIR")" ] && echo clean\n'
    expected = {"P1": {"exit": 0, "stdout": "main.bpl|-|two words|⎕←1\nx←1\nline one\nline two\nclean\n"}}
    assert run_verifier(tmp_path, script, cases, expected)["cases_passed"] == 1


def test_every_run_gets_the_same_limits_and_its_own_stack(tmp_path):
    report = verifier_call(textwrap.dedent(f"""
        import json, sys
        from pathlib import Path
        from verifier import runcases
        runcases.WORKSPACE = Path({str(tmp_path / 'bpl-run')!r})
        runcases.HOME, runcases.TEMP = Path({str(tmp_path / 'bpl-home')!r}), Path({str(tmp_path / 'bpl-tmp')!r})
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
    for name, mode in (("bpl", 0o4755), ("lib/helper", 0o2775), ("lib/data", 0o4666), ("lib", 0o1777)):
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
        unlisted = status.replace("NoNewPrivs:\\t1\\n", "")
        by_prctl = [verify.sandbox_problems(unlisted + f"PrctlNoNewPrivs:\\t{{value}}\\n", limits, (65534, 65534))[0]
                    for value in (1, 0, -1)] + [verify.sandbox_problems(unlisted, limits, (65534, 65534))[0]]
        print(json.dumps([good, bad, "--no-new-privs" in Path(verify.__file__).read_text(), by_prctl]))
    """))
    good, bad, no_new_privs, by_prctl = report
    assert good == [] and all(problems for problems in bad) and no_new_privs
    assert by_prctl[0] == [] and all(problems == ["no_new_privs is not set"] for problems in by_prctl[1:])
    modes = {path.relative_to(top).as_posix(): os.lstat(path).st_mode & 0o7777 for path in [top, *top.rglob("*")]}
    assert modes == {".": 0o755, "bpl": 0o755, "lib": 0o755, "lib/helper": 0o755, "lib/data": 0o644, "link": modes["link"]}
    assert (top / "link").is_symlink()


def test_nothing_a_submission_writes_reaches_a_later_case(tmp_path):
    """Each run has a new workspace, HOME and TMPDIR, and what the sandbox user left anywhere it
    can write (here `shared`, standing for /tmp and the other world-writable directories) is gone
    before the next case. kill_user is left out: here the sandbox user is the one running pytest."""
    shared = tmp_path / "shared"
    shared.mkdir()
    program = tmp_path / "bpl"
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
        verify.runcases.WORKSPACE = Path({str(tmp_path / 'bpl-run')!r})
        verify.runcases.HOME = Path({str(tmp_path / 'bpl-home')!r})
        verify.runcases.TEMP = Path({str(tmp_path / 'bpl-tmp')!r})
        verify.LEFTOVER_DIRS[:] = [{str(shared)!r}]
        verify.kill_user = lambda uid: None
        removed, real_run = [], verify.subprocess.run
        verify.subprocess.run = lambda argv, **kw: removed.append(argv) if argv[0] == "ipcrm" else real_run(argv, **kw)
        root = Path({str(ipc)!r})
        verify.remove_ipc = (lambda real: lambda uid: real(uid, root))(verify.remove_ipc)
        metrics = verify.grade(Path({str(program)!r}), Path({str(private)!r}), [], (os.getuid(), os.getgid()))
        verify.final_cleanup(os.getuid(), __import__("time").monotonic() + 30)
        print(json.dumps([metrics, removed]))
    """))
    assert metrics["cases_passed"] == 3, metrics
    assert removed and all(argv == ["ipcrm", "-m", "7"] for argv in removed), removed
    assert list(shared.iterdir()) == [], "the last case's files outlived the evaluation"


def test_a_deep_tree_never_turns_grading_into_an_error(tmp_path):
    script = 'case "$1" in deep) i=0; while [ $i -lt 1500 ]; do mkdir d && cd d || break; i=$((i+1)); done;; esac\necho ok\n'
    cases, expected = plain_cases([["deep"], ["after"], ["deep"], ["last"]], kinds=["deep", "after", "deep", "last"])
    metrics = run_verifier(tmp_path, script, cases, expected)
    assert metrics["cases_run"] == 4 and metrics["setup_errors"] == 0, metrics
    assert metrics["by_kind"]["after"]["passed"] == 1 and metrics["by_kind"]["last"]["passed"] == 1, metrics
    assert not list((tmp_path / "tmp").rglob("d")), "the deep tree was left behind"


def test_the_original_is_refused_by_its_marker_and_only_the_images_carry_one(tmp_path):
    marker = b"BPL-BUILD-MARKER-" + b"f" * 32
    top = tmp_path / "rebuild"
    (top / "bin").mkdir(parents=True)
    (top / "bpl").write_bytes(b"\x7fELF" + b"x" * ((1 << 20) - 10) + marker + b"tail")
    (top / "bin" / "clean").write_bytes(b"BPL-BUILD-MARKER-" + b"0" * 32)
    (top / "link").symlink_to(top / "bpl")
    fetched = tmp_path / "fetched"
    (fetched / "lib").mkdir(parents=True)
    (fetched / "bpl").write_text("#!/bin/sh\nexec python3 main.py\n")
    (fetched / "lib" / "_core.so").write_bytes(b"\x7fELF published build" * 1000)
    usage = tmp_path / "usage"
    usage.mkdir()
    (usage / "bpl").write_bytes(b"\x7fELF" + b"y" * ((1 << 20) - 12) + b"Use --kernel -f CONNECTION_FILE to run a kernel")
    published = hashlib.sha256((fetched / "lib" / "_core.so").read_bytes()).hexdigest()
    builds = tmp_path / "builds.json"
    builds.write_text(json.dumps({"builds": [{"sha256": published, "size": (fetched / "lib" / "_core.so").stat().st_size,
                                              "source": "PyPI"}]}))
    found = verifier_call(textwrap.dedent(f"""
        import json, verify
        from pathlib import Path
        top = Path({str(top)!r})
        needles = {{{marker!r}: "the marker", verify.UNHARDENED_USAGE: "the usage text"}}
        builds = verify.upstream_builds(Path({str(builds)!r}))
        shipped = verify.upstream_builds()
        print(json.dumps([verify.holds_original(top, needles), verify.holds_original(top / "bin", needles),
                          verify.identity(top / "bin" / "clean"), verify.identity(top / "bpl"),
                          verify.holds_original(Path({str(fetched)!r}), needles, builds),
                          verify.holds_original(Path({str(usage)!r}), needles, builds),
                          len(shipped), sorted(size for sizes in shipped.values() for size in sizes)[:1]]))
    """))
    assert found[0] == "/app/rebuild/bpl holds the marker" and found[1] is None, "found across a 1 MB chunk boundary, never through a link"
    assert found[2]["sha256"] == found[2]["sha256_without_marker"] and found[3]["sha256"] != found[3]["sha256_without_marker"]
    assert found[4] == "/app/rebuild/lib/_core.so is a build of BasedPL that upstream publishes"
    assert found[5] == "/app/rebuild/bpl holds the usage text", "found across a 1 MB chunk boundary"
    assert found[6] == 12 and found[7][0] > 30_000_000, "three release binaries and nine Python extensions, all distinct"
    shipped = json.loads((STEP / "tests" / "verifier" / "upstream_builds.json").read_text())["builds"]
    assert {build["source"].split(":")[0] for build in shipped} >= {"GitHub release v0.1.95"}
    assert sum("bpl-linux-x86_64" in build["source"] for build in shipped) == 1
    package = (SCRIPTS / "package_step.py").read_text()
    assert 'for place in ("environment", f"{STEP}/tests"):' in package and 'content[f"{place}/original/marker"] = marker' in package
    assert "solution/marker" not in package
    solve = (STEP / "solution" / "solve.sh").read_text()
    assert '"$here/build.txt" - /app/rebuild/bpl' in solve, "the solution installs the build with no marker"
    verify = (STEP / "tests" / "verify.py").read_text()
    assert verify.index("holds_original(SUBMISSION, needles, builds)") < verify.index("metrics = grade(")
    assert 'raise EvaluationError("The original\'s build marker is missing or malformed")' in verify, "never fails open"


def test_mark_writes_the_marker_only_into_the_recorded_build(tmp_path):
    import lzma
    zero = b"BPL-BUILD-MARKER-" + b"0" * 32
    binary = b"\x7fELF" + b"a" * 1000 + zero + b"b" * 1000
    (tmp_path / "bpl.xz").write_bytes(lzma.compress(binary))
    (tmp_path / "build.txt").write_text(f"link static\nsha256 {hashlib.sha256(binary).hexdigest()}\n")
    (tmp_path / "marker").write_text("f" + "1" * 31 + "\n")
    mark = lambda *args: subprocess.run([sys.executable, "-B", str(HARDENING / "mark.py"), *map(str, args)],  # noqa: E731
                                        capture_output=True, text=True, timeout=60)
    assert mark(tmp_path / "bpl.xz", tmp_path / "build.txt", tmp_path / "marker", tmp_path / "image" / "bpl").returncode == 0
    marked = (tmp_path / "image" / "bpl").read_bytes()
    assert marked.count(b"BPL-BUILD-MARKER-f" + b"1" * 31) == 1 and zero not in marked
    facts = (tmp_path / "image" / "build.txt").read_text()
    assert f"sha256_without_marker {hashlib.sha256(binary).hexdigest()}" in facts
    assert mark(tmp_path / "bpl.xz", tmp_path / "build.txt", "-", tmp_path / "solution" / "bpl").returncode == 0
    assert (tmp_path / "solution" / "bpl").read_bytes() == binary
    (tmp_path / "build.txt").write_text("sha256 " + "0" * 64 + "\n")
    assert mark(tmp_path / "bpl.xz", tmp_path / "build.txt", "-", tmp_path / "other" / "bpl").returncode != 0
    assert not (tmp_path / "other" / "bpl").exists(), "a build other than the recorded one is never installed"


def test_hashing_a_submission_is_bounded_and_never_raises(tmp_path):
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    (tmp_path / "linked").symlink_to(fifo)
    data = b"x" * ((1 << 20) - 20) + b"BPL-BUILD-MARKER-" + b"a" * 32 + b"y" * 5000 + b"BPL-BUILD-MARKER-" + b"b" * 32
    (tmp_path / "bpl").write_bytes(data)
    zeroed = re.sub(rb"BPL-BUILD-MARKER-[0-9a-f]{32}", b"BPL-BUILD-MARKER-" + b"0" * 32, data)
    out = verifier_call(textwrap.dedent(f"""
        import json, verify
        from pathlib import Path
        top = Path({str(tmp_path)!r})
        verify.MAX_PROGRAM = 1 << 22
        big = top / "big"
        with open(big, "wb") as handle:
            handle.truncate((1 << 22) + 1)
        print(json.dumps([verify.identity(top / "linked"), verify.identity(top / "fifo"), verify.identity(top / "bpl"),
                          verify.identity(big), verify.identity(top / "missing")]))
    """))
    linked, fifo_result, good, big, missing = out
    assert linked == {"error": "not a regular file"} and fifo_result == {"error": "not a regular file"}
    assert good["sha256"] == hashlib.sha256(data).hexdigest()
    assert good["sha256_without_marker"] == hashlib.sha256(zeroed).hexdigest()
    assert big["error"] == "too large to hash" and missing == {"error": "FileNotFoundError"}


def test_cleanup_cost_does_not_grow_with_what_a_run_leaves(tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir()
    program = tmp_path / "bpl"
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
        verify.runcases.WORKSPACE = Path({str(tmp_path / 'bpl-run')!r})
        verify.runcases.HOME = Path({str(tmp_path / 'bpl-home')!r})
        verify.runcases.TEMP = Path({str(tmp_path / 'bpl-tmp')!r})
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
    with open(big / "bpl", "wb") as handle:
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
    instruction = " ".join((STEP / "instruction.md").read_text().split())
    assert "at most 100,000 files and directories and 1 GB" in instruction and "at most 1 GB and 100,000 files and directories" in instruction


def test_results_are_reserved_written_in_place_and_limits_hold(tmp_path):
    reserved = tmp_path / ".reward.tmp"
    reserved.write_text("--------")
    metrics = tmp_path / "metrics.json"
    metrics.write_text("{}".ljust(4096))
    tree = tmp_path / "root"
    for name in ("tmp", "logs/artifacts/open", "var/tmp"):
        (tree / name).mkdir(parents=True)
        (tree / name).chmod(0o777)
    run = tmp_path / "run"
    (run / "deep" / "er").mkdir(parents=True)
    out = verifier_call(textwrap.dedent(f"""
        import json, os, verify
        from pathlib import Path
        verify.write_in_place(Path({str(reserved)!r}), b"0.731000")
        verify.write_in_place(Path({str(metrics)!r}), b'{{"reward": 0.731}}')
        found = verify.writable_dirs({str(tree)!r})
        rc = verify.runcases
        rc.memory_in_use = lambda group, uid: 0
        rc.WORKSPACE, rc.HOME, rc.TEMP = Path({str(run)!r}), Path({str(run / 'home')!r}), Path({str(run / 'tmp')!r})
        rc.DISK_LIMIT, rc.FILES_LIMIT = 1 << 20, 50
        free = {{"/tmp": (10 << 30, 1_000_000, 2_000_000), "/dev/shm": (1 << 30, 1000, 1000)}}
        rc.disk_baseline = lambda: dict(free)
        quiet = rc.over_limit(1, None, rc.disk_baseline())
        # Others write 2 GB and 200,000 files: the run's own files are few, so nothing stops, and the
        # count starts again from the figures now.
        start = rc.disk_baseline()
        free["/tmp"] = ((10 << 30) - (2 << 30), 800_000, 2_000_000)
        others = rc.over_limit(1, None, start)
        moved = start == rc.disk_baseline()
        # The run itself writes 2 MB, then 60 files: those stop it.
        with open(Path({str(run / 'deep' / 'er' / 'big')!r}), "wb") as handle:
            handle.write(os.urandom(2 << 20))
        start = rc.disk_baseline()
        free["/tmp"] = ((10 << 30) - (5 << 30), 800_000, 2_000_000)
        disk = rc.over_limit(1, None, start)
        os.remove(Path({str(run / 'deep' / 'er' / 'big')!r}))
        for index in range(60):
            Path({str(run / 'deep')!r}, f"f{{index}}").write_text("x")
        start = rc.disk_baseline()
        free["/dev/shm"] = (1 << 30, 900, 1000)
        files = rc.over_limit(1, None, start)
        free["/tmp"] = free["/dev/shm"] = (-1, -1, -1)
        unknown = rc.over_limit(1, None, start)
        print(json.dumps([sorted(found), quiet, others, moved, disk, files, unknown]))
    """))
    found, quiet, others, moved, disk, files, unknown = out
    assert reserved.read_text() == "0.731000" and json.loads(metrics.read_text()) == {"reward": 0.731}
    assert not any("logs" in path for path in found) and str(tree / "tmp") in found
    assert quiet is None and others is None and moved, "other writers on the filesystem never stop a run"
    assert disk == "disk limit" and files == "file limit" and unknown is None
    verify = (STEP / "tests" / "verify.py").read_text()
    main = verify[verify.index("def main() -> int:"):]
    assert main.index('(output / ".reward.tmp").write_text("--------")') < main.index("raise EvaluationError(f\"Less than") \
        < main.index("sandbox()") < main.index("final_cleanup(owner[0], min(deadline") \
        < main.index('write_in_place(output / ".reward.tmp"') < main.index('os.replace(output / ".reward.tmp", output / "reward.txt")')
    assert 'reward.txt").write_text' not in main, "no reward exists until the real end"
    assert "runcases.OWN_ROOTS[:] = LEFTOVER_DIRS" in main
    assert 'if str(uid) in (values.get("uid"), values.get("cuid"))' in RUNNER.read_text(), "shared memory by its creator too"
    assert "if os.geteuid() != 0 or uid == os.geteuid()" in verify, "never kill -1 as the verifier's own uid"


def test_a_case_stopped_by_a_resource_limit_runs_once_more(tmp_path):
    private = tmp_path / "private"
    private.mkdir()
    cases = [{"id": "C1", "kind": "expr", "argv": ["-e", "1"], "files": {}, "stdin": None},
             {"id": "C2", "kind": "expr", "argv": ["-e", "2"], "files": {}, "stdin": None}]
    (private / "cases.json").write_text(json.dumps({"cases": cases}))
    (private / "expected.json").write_text(json.dumps({"C1": {"exit": 0, "stdout": "1\n"}, "C2": {"exit": 0, "stdout": "2\n"}}))
    program = tmp_path / "bpl"
    program.write_text("#!/bin/sh\nexit 0\n")
    program.chmod(0o755)
    out = verifier_call(textwrap.dedent(f"""
        import json, verify
        from pathlib import Path
        calls = []
        def fake(program, case, prefix=None, owner=None):
            calls.append(case["id"])
            if case["id"] == "C1" and calls.count("C1") == 1:  # a spurious stop, then a clean run
                return {{"exit": None, "stdout": None, "error": "file limit", "seconds": 0.1}}
            if case["id"] == "C2":  # a real disk filler: stopped both times
                return {{"exit": None, "stdout": None, "error": "disk limit", "seconds": 0.1}}
            return {{"exit": 0, "stdout": b"1\\n", "seconds": 0.1}}
        verify.runcases.run_case = fake
        verify.low_on_disk = lambda: False
        metrics = verify.grade(Path({str(program)!r}), Path({str(private)!r}), [], None)
        print(json.dumps([calls, metrics["cases_passed"], metrics["limit_retries"], metrics["disk_limits"],
                          metrics["file_limits"]]))
    """))
    calls, passed, retries, disk, files = out
    assert calls == ["C1", "C1", "C2", "C2"] and passed == 1 and retries == 2 and disk == 1 and files == 0


DELIVERY = r"""
import json, os, subprocess, sys, tarfile
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import verify
hook, base = Path(sys.argv[2]).read_text(), Path(sys.argv[3])
session = hook.split("<<'EOF'\n")[1].split("\nEOF\n", 1)[0]  # egress and the agent's processes, as root
fixer = hook.split("<<'EOF'\n")[2].split("\nEOF\n", 1)[0]  # the link fixer, run as the agent's user
measure = hook.split("<<'EOF'\n")[3].split("\nEOF\n", 1)[0]  # the last script, run as root after it
FULL = ("import os\n_statvfs = os.statvfs\nclass Full:\n    f_bavail = f_favail = 0\n    f_frsize = 4096\n"
        "os.statvfs = lambda path: Full()\n")  # a disk with no room and no inode left
CLOSED = ("import socket\ndef refuse(address, timeout=None):\n    raise ConnectionRefusedError(111, 'refused')\n"
          "socket.create_connection = refuse\n")
SLOW = "import socket, time\nsocket.create_connection = lambda address, timeout=None: time.sleep(30)\n"


def deliver(name, build, entries="100000", size="1000000000", path="1000", seconds="100", start=None, tar=None, prelude=""):
    app = base / name / "app"
    rebuild, state, archives = app / "rebuild", base / name / "state", base / name / "tmp"
    for folder in (rebuild, state, archives):
        folder.mkdir(parents=True)
    if start is not None:
        (state / "free-at-start").write_text(start)
    (state / "session.json").write_text(json.dumps({"egress": {"pypi.org:443": "closed"}, "egress_open": False,
                                                    "agent_process_count": 1, "agent_processes": [{"pid": 7, "command": "sleep 99"}]}))
    (state / "turn-started").write_text("1700000000\n")
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
    environment = dict(os.environ)
    if tar is not None:  # a stand-in for the copy's tar, first on the PATH
        (base / name / "bin").mkdir()
        (base / name / "bin" / "tar").write_text("#!/bin/sh\n" + tar)
        (base / name / "bin" / "tar").chmod(0o755)
        environment["PATH"] = f"{base / name / 'bin'}:{environment['PATH']}"
    done = subprocess.run([sys.executable, "-I", "-", str(rebuild), entries, size, path, str(state), str(archives), seconds, "2", "0",
                           "1700030000"], input=prelude + measure, capture_output=True, text=True, timeout=300, env=environment)
    assert done.returncode == 0, done.stderr
    assert not os.listdir(archives), "the trial pack is removed"
    return app, rebuild


def mark(rebuild):
    return (rebuild / ".delivered").read_text().splitlines()


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
        return verify.delivery_notes(rebuild)
    except verify.EvaluationError as exc:
        return ["ERROR " + str(exc)]


def tree(rebuild):
    (rebuild / "src").mkdir()
    (rebuild / "src" / "main.py").write_text("print('hi')\n" * 50)
    (rebuild / "bpl").write_text("#!/bin/sh\nexec python3 src/main.py\n")
    (rebuild / "empty").mkdir()
    (rebuild / "inside").symlink_to("src/main.py")
    (rebuild / "outside").symlink_to("../../../../etc/hosts")
    (rebuild / "absolute").symlink_to("/etc/hosts")
    (rebuild / "src" / "b").mkdir()
    (rebuild / "src" / "b" / "up").symlink_to("..")  # resolves inside
    (rebuild / "esc").symlink_to("src/b/up/../..")  # lexically inside, resolves outside
    os.mkfifo(rebuild / "pipe")
    os.link(rebuild / "bpl", rebuild / "bpl-again")


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
    (rebuild / "bpl").write_text("#!/bin/sh\n")


out = {}
app, rebuild = deliver("good", tree)
out["mark"] = mark(rebuild)
out["left"] = sorted(path.name for path in rebuild.iterdir())
record = json.loads((rebuild / ".delivery.json").read_text())
out["record"] = [record["egress_open"], record["kill_rounds"], record["agent_processes_left"], record["delivered"],
                 record["listing_complete"], sorted(item["path"] for item in record["entries"]),
                 next(item for item in record["entries"] if item["path"] == "bpl")]
out["copies"] = [record["turn_started"], record["hook_started"], record["copies"], record["links"], record["notes"]]
out["summary"] = verify.delivery_record(rebuild)
out["complete"] = notes(copy(rebuild, base / "good" / "copied"))
partial = copy(rebuild, base / "good" / "partial")
(partial / "src" / "main.py").unlink()  # the mark arrived, a file did not
out["partial"] = notes(partial)
size = os.path.getsize(base / "good" / "copied.tar")
out["cut"] = notes(copy(rebuild, base / "good" / "cut", cut=size // 3))
out["nothing"] = notes(copy(rebuild, base / "good" / "empty", cut=0))
(rebuild / ".delivered").write_text("delivered ² 5\n")  # not ASCII digits: a mark the hook did not write
out["odd"] = notes(rebuild)
(rebuild / ".delivered").unlink()
out["unmarked"] = notes(copy(rebuild, base / "good" / "unmarked"))
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
out["nop"] = [mark(rebuild), notes(copy(rebuild, base / "nop" / "copied")), verify.delivery_record(base / "nop" / "copied")["entries"]]
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
done = subprocess.run([sys.executable, "-I", "-", str(fixed), "100000", "1000000000"], input=fixer, capture_output=True, text=True,
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
    done = subprocess.run([sys.executable, "-I", "-", str(base / f"session-{name}.json"), str(base / "processes.txt")],
                          input=prelude + session, capture_output=True, text=True, timeout=60)
    checks[name] = [done.returncode, json.loads((base / f"session-{name}.json").read_text()),
                    round(__import__("time").monotonic() - started)]
out["session"] = checks
long_mark = base / "long" / "rebuild"
long_mark.mkdir(parents=True)
(long_mark / "bpl").write_text("#!/bin/sh\n")
(long_mark / ".delivered").write_text("delivered 1 10\n" + "".join(f"removed decoy{i} -> /home/dev/x{i}: it leads outside\n" for i in range(60)))
out["long_mark"] = len(verify.delivery_notes(long_mark))
print(json.dumps(out))
"""


def test_the_delivery_is_bounded_recorded_and_marked_before_the_copy_and_graded_as_it_arrives(tmp_path):
    """The collect hook (environment/prepare-delivery, root, first and only [[verifier.collect]]) records whether the
    public internet answers (two hosts, 3 s each) and the agent's live processes, ends them with `kill -9 -1` as their
    user until none is left, gives back room and inodes set aside at setup, fixes links as the agent's user, then as
    root walks the delivery by directory descriptor, refuses on anything it cannot complete or past 100,000 entries,
    1 GB (each file once) or paths of 1,000 bytes, removes what the copy would refuse, packs it once the way the copy
    does within 100 s, and writes a record of every entry (path, size, times, sha256) and the mark. The verifier grades
    what arrived, with a note when the mark is missing or says refused; nothing arriving, or a mark that counts more
    than arrived, is an evaluation error (ported from the back-office task, rounds 6 and 7)."""
    done = subprocess.run([sys.executable, "-I", "-B", "-c", DELIVERY, str(STEP / "tests"), str(TASK / "environment" / "prepare-delivery"),
                           str(tmp_path)], capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stderr[-3000:]
    out = json.loads(done.stdout.strip().splitlines()[-1])
    run = len("#!/bin/sh\nexec python3 src/main.py\n")
    # src, src/main.py, src/b, src/b/up, bpl, bpl-again, empty, inside: 8 entries; bpl and bpl-again are one file
    assert out["mark"][0] == f"delivered 8 {600 + run}", out["mark"]
    assert out["mark"][1:3] == ["venv/bin/python3: a copy of /usr/bin/python3.12 (was a link to /usr/bin/python3.12)",
                                "removed vendor -> /home/dev/cache: it leads outside /app/rebuild to something that is not part of the "
                                "machine's installation (not owned by root), which is not copied"], "the fixer's notes, copies first"
    assert sorted(out["mark"][3:]) == ["removed absolute: a link that leads outside /app/rebuild", "removed esc: a link that leads outside /app/rebuild",
                                       "removed outside: a link that leads outside /app/rebuild", "removed pipe: not a file, a directory or a link"]
    turn_started, hook_started, copies, links, notes = out["copies"]
    assert (turn_started, hook_started) == (1700000000, 1700030000) and len(notes) == 6
    assert len(copies) == 1 and copies[0]["source"] == "/usr/bin/python3.12" and copies[0]["source_owner"] == 0
    assert copies[0]["source_inode"] == [66, 1234] and copies[0]["outside_delivery"] is True
    assert copies[0]["changed_since_session_started"] is False, "a system file from the image build"
    assert links[0]["kind"] == "refused" and links[0]["changed_since_session_started"] is True and links[0]["outside_delivery"] is True
    assert out["left"] == [".delivered", ".delivery.json", "bpl", "bpl-again", "empty", "inside", "src"]
    egress_open, rounds, left, delivered, complete, paths, bpl = out["record"]
    assert [egress_open, rounds, left, delivered, complete] == [False, 2, 0, out["mark"][0], True]
    assert paths == ["bpl", "bpl-again", "empty", "inside", "src", "src/b", "src/b/up", "src/main.py"]
    assert bpl["type"] == "file" and bpl["size"] == run and len(bpl["sha256"]) == 64 and bpl["ctime"] > 1.7e9
    summary = out["summary"]
    assert summary["egress_open"] is False and summary["entries"] == 8 and summary["kill_rounds"] == 2 and summary["bpl"] == bpl
    assert summary["agent_processes"] == [{"pid": 7, "command": "sleep 99"}] and summary["latest_ctime"] >= bpl["ctime"]
    assert summary["copies"] == copies and summary["links"] == links and summary["notes"] == notes, "the whole record reaches metrics.json"
    assert summary["copies_outside_delivery"] == 1 and summary["copies_changed_since_session_started"] == 0
    assert (summary["turn_started"], summary["hook_started"]) == (1700000000, 1700030000)
    assert out["long_mark"] == 60, "the verifier reads the whole mark, however many notes"
    assert out["complete"] == [f"collect hook: {line}" for line in out["mark"][1:]], out["complete"]
    assert out["cut"][0].startswith(("ERROR The copy arrived incomplete", "the delivery arrived without", "ERROR Nothing")), out["cut"]
    assert out["nothing"][0].startswith("ERROR Nothing arrived") and out["unmarked"][0].startswith("the delivery arrived without")
    assert out["partial"] == [f"ERROR The copy arrived incomplete: 7 of 8 entries and {run:,} of {600 + run:,} bytes"], out["partial"]
    assert out["odd"] == ["the collect hook's mark could not be read; the delivery was graded as it arrived"]
    assert out["many"] == [["refused", "it holds more than 3 entries, the most /app/rebuild may hold: it was not copied"],
                           [".delivered", ".delivery.json"], ["rebuild", "refused"]], out["many"]
    assert out["many_notes"][0] == "collect hook: it holds more than 3 entries, the most /app/rebuild may hold: it was not copied"
    assert out["sparse"] == ["refused", "it holds more than 1,000,000,000 bytes, the most /app/rebuild may hold: it was not copied"]
    assert out["deep"] == ["refused", "it holds a path longer than 1,000 bytes, the longest /app/rebuild may hold: it was not copied"]
    assert out["deep_seen"] == out["sparse"], out["deep_seen"]
    assert out["slow"] == ["refused", "the copy's pack of it took more than 1 seconds: it was not copied"]
    assert out["broken"] == ["refused", "the copy's pack of it failed (tar: ./x: Cannot open: Input/output error): it was not copied"]
    assert out["inodes"][0] == "refused" and "No space left on device" in out["inodes"][1], out["inodes"]
    assert out["never_room"][0].startswith("delivered ") and any("room the machine did not have" in line for line in out["never_room"])
    assert out["nop"] == [["delivered 0 0"], [], 0]
    code, kinds, copied, lib_left, one_left, sh_copied, inner = out["fixer"]
    assert code == 0 and kinds == {"lib": "refused", "one": "refused", "sh": "copied", "inner": "relinked"}, out["fixer"]
    assert copied["source"] == "/bin/sh" and copied["source_owner"] == 0 and len(copied["source_inode"]) == 2
    assert copied["source_ctime"] > 1e9 and copied["source_mtime"] > 1e9 and "a copy of /bin/sh" in copied["note"]
    assert not lib_left and not one_left and sh_copied and inner == "real.txt", "the user's own files outside are never copied in"
    closed, slow = out["session"]["closed"], out["session"]["slow"]
    assert closed[0] == 0 and closed[1]["egress_open"] is False and set(closed[1]["egress"]) == {"pypi.org:443", "github.com:443"}
    assert [process["command"] for process in closed[1]["agent_processes"]] == ["sleep 99", "/bin/sh -c curl x"], "from the frozen listing"
    assert closed[1]["agent_processes"][1]["running_seconds"] == 3 and closed[1]["agent_process_count"] == 2
    assert all(state.startswith("closed") for state in closed[1]["egress"].values())
    assert slow[0] == 0 and set(slow[1]["egress"].values()) == {"no answer within 3 s"} and slow[2] <= 9, slow
    hook = (TASK / "environment" / "prepare-delivery").read_text()
    order = ["kill -STOP -1", "ps -eo pid=,ppid=,uid=,etimes=,args= > \"$STATE/processes.txt\"", "kill -9 -1",
             "/usr/bin/python3 -I - \"$STATE/session.json\" \"$STATE/processes.txt\"", "rm -f /var/lib/delivery/room",
             "rm -rf /var/lib/delivery/inodes", 'mv -f "/app/rebuild/$name" "$aside/"',
             "timeout 120 setpriv --reuid dev --regid dev --clear-groups --no-new-privs /usr/bin/python3 -I -",
             '> "$STATE/fixer.jsonl"', 'exec /usr/bin/python3 -I - /app/rebuild']
    assert [hook.index(step) for step in order] == sorted(hook.index(step) for step in order)
    for setting in ("LIMIT_ENTRIES=100000", "LIMIT_BYTES=1000000000", "LIMIT_PATH=1000", "PACK_SECONDS=100", "STATE=/var/lib/delivery"):
        assert setting in hook, setting
    assert "rm -rf \"$" not in hook and "rm -f \"$" not in hook, "nothing is removed through a variable"
    setup = (TASK / "environment" / "reserve-delivery-room").read_text()
    assert "fallocate -l 64M /var/lib/delivery/room" in setup and '/var/lib/delivery/inodes/$spare' in setup and "seq 1 64" in setup
    assert "stat -f -c '%a %S %d' /tmp > /var/lib/delivery/free-at-start" in setup
    assert "date +%s > /var/lib/delivery/turn-started" in setup, "the session's start, for the record's flags"
    assert hook.index("kill -STOP -1") < hook.index("/usr/bin/python3"), "nothing runs before the freeze but the hook's own settings"
    import tomllib
    config = tomllib.loads((TASK / "task.toml").read_text())
    assert config["verifier"]["collect"] == [{"command": "/usr/local/sbin/prepare-delivery", "user": "root", "timeout_sec": 600}]
    for phase in ("setup_begin", "setup_complete"):
        assert config["agent"][phase] == [{"command": "/usr/local/sbin/reserve-delivery-room", "timeout_sec": 120}]
    docker = (TASK / "environment" / "Dockerfile").read_text()
    assert "COPY reserve-delivery-room prepare-delivery /usr/local/sbin/" in docker
    assert "chmod 0700 /usr/local/sbin/reserve-delivery-room /usr/local/sbin/prepare-delivery" in docker
    verify = (STEP / "tests" / "verify.py").read_text()
    main = verify[verify.index("def main() -> int:"):]
    assert main.index("delivery_notes(SUBMISSION)") < main.index("sandbox()") < main.index("seal(SUBMISSION)")
    assert "delivery_record=record" in main, "the record goes to metrics.json"
    assert "[:20]" not in verify[verify.index("def delivery_notes"):verify.index("def delivery_record")], "every note of the mark"
    instruction = " ".join((STEP / "instruction.md").read_text().split())
    assert "at most 100,000 files and directories and 1 GB, with no path inside it longer than 1,000 bytes" in instruction
    assert "only when that is part of the machine's installation (owned by root" in instruction
    assert "room left to copy it" in instruction


def test_a_host_short_of_disk_mid_evaluation_is_an_error_and_a_run_that_ended_in_time_is_read(tmp_path):
    """QA 11: after a cleanup has taken back everything the user held, a short disk is the host's
    doing, so the evaluation is an error rather than a reward that fails the remaining cases; and a
    run that ended before its deadline is read in full however late the verifier gets to it."""
    private = tmp_path / "private"
    private.mkdir()
    (private / "cases.json").write_text(json.dumps({"cases": [{"id": "C1", "kind": "expr", "argv": ["-e", "1"], "files": {},
                                                               "stdin": None}]}))
    (private / "expected.json").write_text(json.dumps({"C1": {"exit": 0, "stdout": "1\n"}}))
    program = tmp_path / "bpl"
    program.write_text("#!/bin/sh\necho 1\n")
    program.chmod(0o755)
    out = verifier_call(textwrap.dedent(f"""
        import json, os, subprocess, time, verify
        from pathlib import Path
        verify.reset = lambda uid: None
        verify.low_on_disk = lambda: True
        try:
            verify.grade(Path({str(program)!r}), Path({str(private)!r}), [], (os.getuid(), os.getgid()))
            outcome = "graded"
        except verify.EvaluationError as exc:
            outcome = str(exc)
        proc = subprocess.Popen(["printf", "late but in time"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        proc.wait()
        read = verify.runcases.read_output(proc, b"", time.monotonic() - 0.2, None, {{}})
        print(json.dumps([outcome, read[0].decode(), read[1]]))
    """))
    assert out[0].startswith("Less than") and "after a cleanup, mid-evaluation" in out[0], out
    assert out[1:] == ["late but in time", None]


def test_the_agent_cannot_replace_the_artifact_directory():
    docker = (TASK / "environment" / "Dockerfile").read_text()
    assert "chown -R root:root /app" in docker and "chmod 1777 /app " in docker and "chmod 0777 /app/rebuild" in docker
    assert "chown root:bpl /opt/bpl/bpl && chmod 2711 /opt/bpl/bpl" in docker


def test_every_run_fits_inside_the_step_verifier_time():
    """Every generated case at its full time limit, with a cleanup of 0.1 s before it, the margin no
    case starts in, and two minutes for sealing and scanning the delivery, fits in TOTAL_SEC, and
    that in both verifier timeouts with five minutes to spare."""
    per_run = int(re.search(r"^CASE_SEC = (\d+)$", RUNNER.read_text(), re.M).group(1))
    verify = (STEP / "tests" / "verify.py").read_text()
    total = int(re.search(r"^TOTAL_SEC = (\d+)", verify, re.M).group(1))
    margin = int(re.search(r"^MARGIN_SEC = (\d+)", verify, re.M).group(1))
    toml = (TASK / "task.toml").read_text()
    step_verifier = int(re.search(r"\[steps\.verifier\]\s*timeout_sec = (\d+)", toml).group(1))
    verifier = int(re.search(r"\[verifier\][^\[]*?timeout_sec = (\d+)", toml).group(1))
    sys.path.insert(0, str(SCRIPTS))
    import make_cases
    cases = sum(make_cases.KIND_COUNTS.values())
    assert cases * (per_run + 0.1) + margin + 120 <= total and total + 300 <= min(step_verifier, verifier)
    agent = int(re.search(r"\[steps\.agent\]\s*timeout_sec = (\d+)", toml).group(1))
    assert agent + step_verifier <= 11 * 3600, "the attempt stays inside the platform's 12 hours"
    assert f"Each run finishes within {per_run} seconds" in (STEP / "instruction.md").read_text()


# ---------------------------------------------------------------- the recorder

FAKE_BPL = """#!/usr/bin/env python3
import os, signal, sys
args = sys.argv[1:]
text = open(args[0]).read() if args and os.path.exists(args[0]) else (args[1] if args[:1] == ["-e"] else "")
if "RANDOM" in text: print(os.urandom(4).hex())
elif "HANG" in text:
    import time; time.sleep(5)
elif "PANIC" in text:
    sys.stderr.write("thread 'main' panicked at src/x.rs:1:1\\n"); sys.exit(101)
elif "SEGV" in text: os.kill(os.getpid(), signal.SIGSEGV)
elif "MEMORY" in text: print("LIMIT: an array of 9 items would take the process past its memory limit of 512 MiB")
elif "THREADS" in text: print(os.environ.get("RAYON_NUM_THREADS", "many"))
elif "STDERRMEM" in text:
    sys.stderr.write("LIMIT ERROR: an array would take the process past its memory limit of 64 MiB\\n"); sys.exit(1)
elif "BOXED" in text: print("boxed" if "•prefs" in text else "plain")
elif "SETTING" in text: print("same either way")
elif "ZERO" in text: print("0 0 0")
elif "FAIL" in text: print("partial"); sys.exit(1)
else: print(text.split()[0] if text.split() else "", sorted(os.listdir(".")))
"""


def record(tmp_path: Path, cases: list[dict]) -> tuple[subprocess.CompletedProcess, Path]:
    program = tmp_path / "fake-bpl"
    program.write_text(FAKE_BPL)
    program.chmod(0o755)
    source = tmp_path / "cases.json"
    source.write_text(json.dumps({"cases": cases}))
    # recorder.py's own main(), with the runs' directories under tmp_path rather than /tmp/bpl-*, so
    # that nothing else recording on this machine shares them.
    driver = textwrap.dedent(f"""
        import sys
        from pathlib import Path
        sys.path.insert(0, {str(RECORDER.parent)!r})
        import runcases
        runcases.WORKSPACE = Path({str(tmp_path / 'runs' / 'bpl-run')!r})
        runcases.HOME = Path({str(tmp_path / 'runs' / 'bpl-home')!r})
        runcases.TEMP = Path({str(tmp_path / 'runs' / 'bpl-tmp')!r})
        import recorder
        sys.argv = ["recorder.py", "record", {str(program)!r}, {str(source)!r}, {str(tmp_path / 'expected.json')!r},
                    "--keep", {str(tmp_path / 'kept.json')!r}, "--report", {str(tmp_path / 'report.json')!r}]
        recorder.main()
    """)
    (tmp_path / "runs").mkdir(exist_ok=True)
    done = subprocess.run([sys.executable, "-B", "-c", driver], capture_output=True, text=True, timeout=300)
    return done, tmp_path


def script(i: int, text: str, **plan) -> dict:
    return {"id": f"P{i}", "kind": "script", "files": {"main.bpl": text}, "argv": ["main.bpl"], "stdin": None,
            **({"record": plan} if plan else {})}


def test_the_recorder_keeps_steady_quick_answers_and_drops_crashes_and_machine_text(tmp_path):
    done, _ = record(tmp_path, [script(i, f"word{i}") for i in range(10)] + [script(90, "RANDOM"), script(91, "PANIC")])
    assert done.returncode != 0 and "crashed" in done.stdout + done.stderr, "a crash in twelve cases fails the recording"
    cases = [script(i, f"word{i}") for i in range(100)] + [script(90 + 100, "RANDOM"), script(91 + 100, "PANIC"),
                                                          script(92 + 100, "HANG"), script(93 + 100, "MEMORY"),
                                                          script(94 + 100, "THREADS"), script(95 + 100, "FAIL")]
    done, out = record(tmp_path, cases)
    assert done.returncode == 0, done.stdout + done.stderr
    report = json.loads((out / "report.json").read_text())
    kept = [case["id"] for case in json.loads((out / "kept.json").read_text())["cases"]]
    assert report["unsteady"] == ["P190"] and report["crashed"] == ["P191"] and report["slow"] == ["P192"]
    assert report["machine"] == ["P193"] and report["perturbed"] == ["P194"], "one worker thread changes this answer"
    assert "P195" in kept and len(kept) == 101 and len(report["kept_ids_sha256"]) == 64
    assert report["main_runs"] == 3 and len(report["seconds"]["P0"]) == 3 and report["main_env"] == {"RAYON_NUM_THREADS": "4"}
    expected = json.loads((out / "expected.json").read_text())
    assert expected["P195"] == {"exit": 1, "stdout": "partial\n"} and expected["P0"]["stdout"].startswith("word0 ['main.bpl']")


def test_the_recorder_settles_each_case_on_a_rewrite_that_changes_its_answer(tmp_path):
    cases = [script(1, "base", variants=[{"files": {"main.bpl": "FAIL"}}, {"files": {"main.bpl": "other"}}], want="same"),
             script(2, "base", variants=[{"files": {"main.bpl": "base  "}}], want="same"),
             script(3, "base", variants=[{"files": {"main.bpl": "PANIC"}}], want="same"),
             {"id": "P4", "kind": "expr", "files": {}, "argv": ["-e", "one"], "stdin": None,
              "record": {"variants": [{"argv": ["-e", "two"]}], "want": "same"}}]
    done, out = record(tmp_path, cases + [script(i, f"w{i}") for i in range(10, 80)])
    assert done.returncode == 0, done.stdout + done.stderr
    got = {case["id"]: case for case in json.loads((out / "kept.json").read_text())["cases"]}
    report = json.loads((out / "report.json").read_text())
    assert got["P1"]["files"] == {"main.bpl": "other"}, "the first rewrite that ends as the case does and prints otherwise"
    assert report["settled"]["P2"] == "variant 0, output as the base's" and report["settled"]["P3"] == "base"
    assert got["P4"]["argv"] == ["-e", "two"] and all("record" not in case for case in got.values())


def test_the_recorder_drops_settings_that_change_nothing_memory_text_on_stderr_and_trivial_rewrites(tmp_path):
    head = '•prefs ["box":$t]\n'
    cases = [script(300, head + "SETTING", unset=["main.bpl", head, ""]), script(301, head + "BOXED", unset=["main.bpl", head, ""]),
             script(302, "STDERRMEM"),
             script(303, "base", variants=[{"files": {"main.bpl": "ZERO"}}, {"files": {"main.bpl": "other"}}], want="same")]
    done, out = record(tmp_path, cases + [script(i, f"w{i}") for i in range(10, 90)])
    assert done.returncode == 0, done.stdout + done.stderr
    report = json.loads((out / "report.json").read_text())
    got = {case["id"]: case for case in json.loads((out / "kept.json").read_text())["cases"]}
    assert report["setting_changes_nothing"] == ["P300"] and "P301" in got, "a display setting must change what is shown"
    assert report["machine"] == ["P302"], "a memory limit named on standard error depends on the builder"
    assert got["P303"]["files"] == {"main.bpl": "other"}, "a rewrite whose answer is all zeros is passed over"


def test_answers_that_show_the_maths_librarys_last_bits_are_left_out():
    out = verifier_call(textwrap.dedent("""
        import json
        from verifier import recorder
        e = lambda code: {"id": "E", "kind": "expr", "files": {}, "argv": ["-e", code], "stdin": None}
        worker = lambda *codes: {"id": "W", "kind": "worker", "files": {}, "argv": ["--worker"], "stdin": None if not codes else
                                 "".join(json.dumps({"id": i, "code": code}) + "\\n" for i, code in enumerate(codes))}
        reply = lambda value: json.dumps({"id": 0, "result": {"value": value, "output": [], "error": None}})
        print(json.dumps([
            recorder.last_bits(e("1○1.2"), "0.9320390859672262\\n"),        # every digit of a sine
            recorder.last_bits(e("1○1.2"), "0.932039086\\n"),               # the default ten digits
            recorder.last_bits(e("÷3"), "0.3333333333333333\\n"),           # exact division, correctly rounded
            recorder.last_bits(e("(1○1.2)-0.932"), "3.9085967226ₑ¯17\\n"),  # a residue below 1e-12
            recorder.last_bits(e("1○1.2ₛ"), "0.93203914ₛ\\n"),              # a 32-bit float
            recorder.last_bits(e("•csv⁻ \\"1.5\\""), "1.234567890123456\\n"),  # a parse, no maths library
            recorder.last_bits(worker("x←÷3", "⌊100×1○1.2"), reply(0.3333333333333333) + "\\n" + reply(93) + "\\n"),
            recorder.last_bits(worker("x←÷3", "1○1.2"), reply(0.3333333333333333) + "\\n" + reply(0.9320390859672262) + "\\n"),
        ]))
    """))
    assert out == [True, False, False, True, True, False, False, True], out
    recorder = (STEP / "tests" / "verifier" / "recorder.py").read_text()
    assert 'dropped["prints the maths library\'s last bits"]' in recorder


def test_no_dispatcher_without_an_interpreter_passes_more_than_five_percent():
    out = verifier_call(textwrap.dedent("""
        import json
        from verifier import recorder
        cases, outputs = [], {}
        def add(i, kind, text, answer, argv=None):
            cases.append({"id": f"P{i:04d}", "kind": kind, "files": {"main.bpl": text} if argv is None else {}, "stdin": None,
                          "argv": argv or ["main.bpl"]})
            outputs[cases[-1]["id"]] = {"stdout": answer[0], "exit": answer[1]}
        for i in range(900):  # programs with answers of their own
            add(i, "script", f"x←{i}\\n⎕←x×2", (f"{2 * i}\\n", 0))
        for i in range(900, 1000):  # a literal lead, then an error: echo and exit 1 passes
            add(i, "error", f'⎕←"step {i}"\\n1 2+3 4 5', (f'"step {i}"\\n', 1))
        for i in range(1000, 1040):  # a computed lead cannot be echoed
            add(i, "error", f"⎕←+/ι{i}\\n1 2+3 4 5", (f"{i * (i - 1) // 2}\\n", 1))
        for i in range(1040, 1070):  # one answer for one shape of -e
            add(i, "expr", "", ("DOMAIN ERROR\\n", 0), argv=["-e", f"code{i}"])
        free = recorder.no_interpreter(cases, outputs)
        kept, dropped = recorder.select(cases, outputs)
        after = recorder.no_interpreter(kept, outputs)
        print(json.dumps([{how: len(ids) for how, ids in free.items()}, len(kept), sum(map(len, after.values())),
                          len(dropped.get("passed with no interpreter", []))]))
    """))
    before, kept, free_after, dropped = out
    assert before["echoed literals"] == 100 and before["constant for -e CODE"] == 30, before
    assert free_after <= 0.05 * kept and dropped > 0, out
    recorder = (STEP / "tests" / "verifier" / "recorder.py").read_text()
    assert "raise SystemExit(f\"{len(free)} of {len(kept)} kept cases pass with no interpreter" in recorder
    assert "FLOOR_SHARE = 0.05" in recorder


def test_selection_drops_shared_answers_answers_in_the_input_and_free_cases():
    report = verifier_call(textwrap.dedent("""
        import json
        from verifier import recorder
        case = lambda i, kind, text="⎕←1": {"id": f"P{i:04d}", "kind": kind, "files": {"main.bpl": text}, "argv": ["main.bpl"],
                                             "stdin": None}
        cases, outputs = [], {}
        for i in range(700):   # scripts: 40 print nothing and exit 1, the rest print their own line
            cases.append(case(i, "script"))
            outputs[cases[-1]["id"]] = {"exit": 1, "stdout": ""} if i < 40 else {"exit": 0, "stdout": f"line {i}\\n"}
        for i in range(700, 1000):   # errors: 60 print one message, the rest messages of their own
            cases.append(case(i, "error"))
            outputs[cases[-1]["id"]] = {"exit": 0, "stdout": "DOMAIN ERROR\\n" if i < 760 else f"LENGTH: lengths {i} and 2\\n"}
        cases.append(case(1000, "display", '⎕←"a long line of text to show"'))
        outputs["P1000"] = {"exit": 0, "stdout": "a long line of text to show\\n"}
        for i in range(1001, 1021):
            cases.append(case(i, "cli"))
            outputs[cases[-1]["id"]] = {"exit": 2, "stdout": ""}
        kept, dropped = recorder.select(cases, outputs)
        free = recorder.free_cases(kept, outputs)
        print(json.dumps({"kept": len(kept), "dropped": {k: len(v) for k, v in dropped.items()},
                          "quoted": dropped.get("input holds the answer"), "free": sum(map(len, free.values())),
                          "cli": sum(1 for c in kept if c["kind"] == "cli")}))
    """))
    assert report["quoted"] == ["P1000"] and report["cli"] == 20, "the command-line cases are never dropped"
    assert report["dropped"]["answer shared by many cases"] > 0
    assert report["free"] <= 0.05 * report["kept"], report
    assert report["kept"] > 900


def test_the_recording_report_counts_upstream_answers_and_the_baselines(tmp_path):
    run = {"files": {"main.bpl": "x"}, "argv": ["main.bpl"], "stdin": None}
    kept = [dict(run, id="P1", kind="expr", suite="own"), dict(run, id="P2", kind="expr", suite="own"),
            dict(run, id="P3", kind="apl", suite="apl"), dict(run, id="P6", kind="error", suite="own"),
            dict(run, id="P7", kind="program"), dict(run, id="P8", kind="program"),
            dict(run, id="P9", kind="display", form="built"), {"id": "P10", "kind": "cli", "files": {}, "argv": ["--help"], "stdin": None}]
    cases = kept + [dict(run, id="P4", kind="module"), dict(run, id="P5", kind="expr")]
    expected = {"P1": {"exit": 0, "stdout": "6\n"}, "P2": {"exit": 0, "stdout": "7\n"}, "P3": {"exit": 0, "stdout": "8\n"},
                "P6": {"exit": 0, "stdout": "DOMAIN: x\n"}, "P7": {"exit": 1, "stdout": ""}, "P8": {"exit": 1, "stdout": ""},
                "P9": {"exit": 0, "stdout": "y\n"}, "P10": {"exit": 0, "stdout": "usage\n"}}
    seconds = {i: [0.1, 0.2] for i in ("P1", "P2", "P3", "P6", "P7", "P8", "P9", "P10")}
    timing = {"keep_seconds": 1.0, "keep_cpu": 0.25, "seconds": dict(seconds, P4=[0.9, 0.8], P5=[0.1, 2]), "slow": ["P4"],
              "unsteady": ["P5"], "crashed": [], "machine": [], "dropped": {"answer shared by many cases": ["P5"]},
              "settled": {"P1": "variant 0", "P2": "base", "P3": "as generated", "P6": "base", "P9": "as generated"}}
    for name, data in (("cases.json", {"cases": cases}), ("kept.json", {"cases": kept}), ("expected.json", expected), ("timing.json", timing)):
        (tmp_path / name).write_text(json.dumps(data))
    (tmp_path / "build.txt").write_text("link static\nsha256 ab\nsha256_without_marker cd\n")
    subprocess.run([sys.executable, "-B", str(STEP / "tests" / "verifier" / "recording.py"),
                    *(str(tmp_path / name) for name in ("cases.json", "kept.json", "expected.json", "timing.json", "out.json")),
                    "--build", str(tmp_path / "build.txt")], check=True, capture_output=True, timeout=60, cwd=STEP / "tests" / "verifier")
    report = json.loads((tmp_path / "out.json").read_text())
    assert report["kept_as_upstream_code"] == {"apl": 1, "error": 1, "expr": 1}, "a built display is no upstream code"
    assert report["build"]["link"] == "static" and report["build"]["sha256_without_marker"] == "cd"
    assert report["empty_stdout_by_exit"] == {"1": 2} and report["apl_share"] == round(1 / 8, 4)
    assert report["dropped_slow"] == {"module": 1} and report["dropped_unsteady"] == {"expr": 1}
    baselines = report["baselines"]
    assert baselines["print_nothing_exit_1"] == round(2 / 8, 4) and baselines["print_nothing_exit_0"] == 0
    assert baselines["no_interpreter_dispatcher"] == round(3 / 8, 4), "the help case and the two silent programs"
    assert baselines["no_interpreter_dispatcher_by_strategy"] == {"command-line table": 1, "constant for FILE": 2}
    assert report["expected_sha256"] == hashlib.sha256(json.dumps(expected, sort_keys=True).encode()).hexdigest()
    assert baselines["largest_answer_share"] == round(2 / 8, 4)


# ---------------------------------------------------------------- hardening and images

def test_images_and_solution_install_one_build_and_ship_no_private_cases():
    agent = (TASK / "environment" / "Dockerfile").read_text()
    verifier = (STEP / "tests" / "Dockerfile").read_text()
    solve = (STEP / "solution" / "solve.sh").read_text()
    base = re.search(r"^FROM (ubuntu:24\.04@sha256:[0-9a-f]{64}) AS program$", agent, re.M).group(1)
    install = "RUN python3 /original/mark.py /original/bpl.xz /original/build.txt /original/marker /opt/bpl/bpl \\\n" \
              "    && bash /original/smoke.sh /opt/bpl/bpl\n"
    assert install in agent and install in verifier, "both images install the one build the same way and prove it"
    assert agent.count(f"FROM {base}") == 2 and verifier.count(f"FROM {base}") == 2, "every stage on the pinned base"
    final_agent = agent.split(f"\n\nFROM {base}\n", 1)[1]
    final_verifier = verifier.split(f"\n\nFROM {base}\n", 1)[1]
    assert "COPY --from=program /opt/bpl/bpl /opt/bpl/bpl" in final_agent and "build.txt" not in final_agent
    smoke = "COPY --from=program /original/smoke.sh /tmp/bpl-smoke.sh"  # the one script, removed in the step that runs it
    assert "original" not in final_agent.replace(smoke, "") and "original" not in final_verifier and "/opt/bpl" not in final_verifier
    assert "private" not in agent and "examples" not in agent and "recorder" not in agent
    assert "--build /opt/bpl/build.txt" in verifier and "cp /original/marker /record/marker" in verifier
    assert "COPY --from=program /record/kept.json /tests/private/cases.json" in final_verifier
    assert "COPY --from=program /record/marker /tests/private/marker" in final_verifier
    assert "cargo build" not in agent + verifier + solve and "git clone" not in agent + verifier
    assert 'mark.py" "$here/bpl.xz" "$here/build.txt" - /app/rebuild/bpl' in solve and "smoke.sh" in solve
    build = (SCRIPTS / "build_original.py").read_text()
    for fact in ('UPSTREAM_COMMIT = "af3609a9348471494d2bed952cbbf2a5ecdbd53e"', 'TOOLCHAIN = "1.100.0"',
                 'TARGET = "x86_64-unknown-linux-musl"', "target-cpu=x86-64-v3", '"--locked"', "apply.sh"):
        assert fact in build, fact


def test_the_hardening_patch_applies_once_and_its_refusals_are_the_ones_the_smoke_test_proves(tmp_path):
    patch = (HARDENING / "basedpl-hardening.patch").read_text()
    added = "\n".join(line[1:] for line in patch.splitlines() if line.startswith("+") and not line.startswith("+++"))
    removed = "\n".join(line[1:] for line in patch.splitlines() if line.startswith("-") and not line.startswith("---"))
    smoke = (HARDENING / "smoke.sh").read_text()
    patched = ["cli/src/cli.rs", "cli/src/editor.rs", "cli/src/main.rs", "cli/src/worker.rs", "jit/src/lib.rs", "src/data.rs",
               "src/files.rs", "src/host.rs", "src/lib.rs"]
    assert sorted(re.findall(r"^diff --git a/(\S+)", patch, re.M)) == patched
    for gone in ('Command::new("curl")', "std::fs::read(path)", "OpenOptions", "crate::kernel::run(file)", 'flag == "--costs"',
                 'request.get("case")', 'request.get("check")', 'request.get("reference")', "XDG_CONFIG_HOME", "self.compile()?",
                 "std::fs::read_to_string(file)", "mod kernel;"):
        assert gone in removed and gone not in added, gone
    for message in ("this build of bpl reads only files under its working directory", "this build of bpl writes no files",
                    "this build of bpl has no network access", "no file system functions apart from •path"):
        assert message in added and message.split("this build of bpl ")[-1] in smoke, message
    assert '["/proc", "/sys", "/dev"]' in added and "/proc/self/fd/" in added and "black_box(BUILD_MARKER)" in added
    for probe in ("/proc/self/maps", "/proc/self/mem", "/dev/stdin", "../outside/secret.txt", "ln -s /proc/self/maps",
                  "BASEDPL_COMPILE=always", "--kernel -f", "--costs", '"case"', '"check"', "curl-ran"):
        assert probe in smoke, probe
    # The sources the patch expects, rebuilt from its own context, take it once through apply.sh and refuse it twice.
    tree = tmp_path / "src-tree"
    for name, body in re.findall(r"^diff --git a/(\S+) .*?\n(.*?)(?=^diff --git |\Z)", patch, re.M | re.S):
        lines = [line[1:] for line in body.splitlines() if line[:1] in (" ", "-") and not line.startswith("---")]
        (tree / name).parent.mkdir(parents=True, exist_ok=True)
        (tree / name).write_text("\n".join(lines) + "\n")
    first = subprocess.run(["sh", str(HARDENING / "apply.sh"), str(tree)], capture_output=True, text=True, timeout=60)
    assert first.returncode == 0, first.stdout + first.stderr
    assert all("Hardened build" in (tree / name).read_text() for name in patched)
    assert (tree / "cli" / "src" / "build_marker.txt").read_text() == "BPL-BUILD-MARKER-" + "0" * 32
    assert (tree / "Cargo.lock").read_bytes() == (HARDENING / "Cargo.lock").read_bytes()
    second = subprocess.run(["sh", str(HARDENING / "apply.sh"), str(tree)], capture_output=True, text=True, timeout=60)
    assert second.returncode != 0


def test_the_lockfile_pins_every_dependency_of_the_build():
    lock = (HARDENING / "Cargo.lock").read_text()
    assert 'name = "rustymath"\nversion = "0.1.63"' in lock
    assert "git+https://github.com/AnswerDotAI/rustyline.git?branch=master#4b74b68d37cec5ac2e4713994297e9f0da873c61" in lock
    assert "git+https://github.com/AnswerDotAI/plotters.git?branch=master#649dc9900ab78b1ee6f46a65fbffaed8cb70ae6d" in lock


def test_the_smoke_test_fails_an_interpreter_that_is_not_hardened(tmp_path):
    lax = tmp_path / "bpl"
    lax.write_text(textwrap.dedent("""\
        #!/bin/sh
        case "$1" in
          --version) echo "basedpl 0.1.95";;
          -e) case "$2" in *'•nget "-"'*) cat;; *'•nget'*) cat "$(echo "$2" | sed 's/.*"\\(.*\\)".*/\\1/')";;
                *'•nput'*) echo written;; *) echo 45;; esac;;
          *) echo 5;;
        esac
    """))
    lax.chmod(0o755)
    shim = tmp_path / "bin"
    shim.mkdir()
    if shutil.which("timeout") is None:  # macOS has no coreutils timeout
        (shim / "timeout").write_text('#!/bin/sh\nshift\nexec "$@"\n')
        (shim / "timeout").chmod(0o755)
    done = subprocess.run([shutil.which("bash"), str(HARDENING / "smoke.sh"), str(lax)], capture_output=True, text=True,
                          timeout=120, env={"PATH": f"{shim}:/usr/bin:/bin"})
    assert done.returncode != 0 and "hardening smoke test failed" in done.stderr, done.stderr


def test_nothing_the_agent_sees_names_a_reference_answer_or_a_budget():
    seen = {"Dockerfile": (TASK / "environment" / "Dockerfile").read_text(), "instruction.md": (STEP / "instruction.md").read_text(),
            "task.toml": (TASK / "task.toml").read_text()}
    for name, text in seen.items():
        lowered = text.lower()
        for word in ("oracle", "reference solution", "hidden", "grade", "grading", "score", "test case", "working session",
                     "fresh context", "hours", "candidate", "bpl-case"):
            assert word not in lowered, (name, word)
        assert not re.search(r"\bcases?\b|-case\b", lowered), (name, "the runner's word for a run")
    sys.path.insert(0, str(STEP / "tests"))
    from verifier import runcases
    for place in (runcases.WORKSPACE, runcases.HOME, runcases.TEMP):
        assert str(place) not in seen["instruction.md"], place
    assert not re.search(r"\btests?\b", seen["instruction.md"].lower()), "no suite is implied"
    assert "#" not in seen["task.toml"]
    assert sorted(path.name for path in (TASK / "environment").iterdir()) == [".dockerignore", "Dockerfile", "prepare-delivery",
                                                                          "reserve-delivery-room"]
    instruction = seen["instruction.md"]
    assert "no example" not in instruction.lower() and "Out of scope:" in instruction
    flat = " ".join(instruction.split())
    assert "All of the manual is in scope" in flat and "derivatives with `∂` among them" in flat, "the scope is the whole manual"
    for excluded in ("¿", "•time", "•plot", "•storage", "•explain", "•hash", "timeout_ms", "]help"):
        assert excluded in instruction.split("Out of scope:", 1)[1], excluded


def test_only_the_documentation_and_the_binary_reach_the_agent():
    package = (SCRIPTS / "package_step.py").read_text()
    assert 'content[f"environment/docs/{name}"] = text.encode("utf-8")' in package
    assert "make_cases.leaks(cases, skeletons, texts)" in package
    agent = (TASK / "environment" / "Dockerfile").read_text()
    assert re.findall(r"^COPY .*$", agent, re.M) == ["COPY original/ /original/", "COPY --from=program /opt/bpl/bpl /opt/bpl/bpl",
                                                    "COPY --from=program /original/smoke.sh /tmp/bpl-smoke.sh",
                                                    "COPY docs/ /app/docs/", "COPY reserve-delivery-room prepare-delivery /usr/local/sbin/"]
    final = agent.split("\nFROM ", 1)[1]
    assert "sudo" not in agent, "no set-user-id helper the agent's user cannot use anyway"
    assert final.index("chmod 2711 /opt/bpl/bpl") < final.index(
        "setpriv --reuid dev --regid dev --clear-groups env HOME=/tmp bash /tmp/bpl-smoke.sh /opt/bpl/bpl") \
        < final.index("rm -f /tmp/bpl-smoke.sh"), "the installed build is proved as the agent runs it, set-group-id"
    smoke = (HARDENING / "smoke.sh").read_text()
    assert 'if [ "$(id -u)" -ne 0 ]; then' in smoke and 'for target in "$bpl" /proc/self/exe; do' in smoke
    assert sorted(path.name for path in HARDENING.iterdir()) == ["Cargo.lock", "apply.sh", "basedpl-hardening.patch", "mark.py",
                                                                 "smoke.sh"]
