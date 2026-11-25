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
import signal
import socket
import subprocess
import sys
import tarfile
import textwrap
import time
import uuid
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
    for _ in range(200):  # no lead is a literal that an echo could copy, and every lead form is one the recorder evaluates
        lead = rng.choice(make_cases.LEADS)(rng)
        assert lead.startswith("⎕←") and recorder.literal_value(lead[2:]) is None, lead
        assert recorder.literal_value(lead[2:], evaluate=True) is not None, lead
    assert [recorder.literal_value(code, True) for code in ("+/ι10", '⌽"plum"', '≢"size palm"', "3×ι4", "⌈/5 9 2", "18+4×9")] \
        == ["45", '"mulp"', "9ₓ", "0 3 6 9", "9", "54"]
    pooled = make_cases.plain_error_case({"code": "1 2+3 4 5", "file": "core.bpl", "line": 7, "expected_error": "LENGTH ERROR"}, "",
                                         random.Random(5), lead_record=({"code": "2×3 4", "file": "core.bpl", "line": 1}, ""))
    lead_line = (pooled["files"]["main.bpl"].splitlines()[0] if pooled["form"] == "plain"
                 else json.loads(pooled["stdin"].splitlines()[0])["code"])
    assert "2×" in lead_line and "4" in lead_line and recorder.literal_value(lead_line.removeprefix("⎕←"), True) is None, \
        "a lead from the record pool is no form the dispatcher evaluates"
    assert next(case for case in make_cases.cli_cases() if case["source"] == "cli:pipe-errors")["stdin"].count("1 2+1 2 3") == 1
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
    """65 runs past their limit, then 45 programs given after -e that each print an output of their own, not a copy
    of the code (enough of them for a reward: see the distinct-output checks): every case is run and the reward is
    the share passed."""
    cases, expected = plain_cases([["slow"]] * 65)
    fast = [{"id": f"F{i}", "kind": "expr", "files": {}, "argv": ["-e", str(i)], "stdin": None} for i in range(45)]
    expected.update({case["id"]: {"exit": 0, "stdout": f"w{case['argv'][1]}\n"} for case in fast})
    metrics = run_verifier(tmp_path, 'case "$1" in slow) exec sleep 5;; esac\necho "w$2"\n', cases + fast, expected, case_sec=0.05)
    assert metrics["cases_run"] == 110 and metrics["timeouts"] == 65 and metrics["cases_passed"] == 45
    assert metrics["reward"] == round(45 / 110, 6) and metrics["stopped"] is None and not metrics["notes"]


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
    quoted = tmp_path / "quoted"
    quoted.mkdir()
    (quoted / "bpl").write_text("#!/bin/sh\necho hi\n")
    (quoted / "NOTES.md").write_text("upstream also had `--kernel -f CONNECTION_FILE`, which this build lacks\n")
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
        marker_only = {{{marker!r}: "the marker"}}
        binary = {{verify.UNHARDENED_USAGE: "the usage text"}}
        print(json.dumps([verify.holds_original(top, needles), verify.holds_original(top / "bin", needles),
                          verify.identity(top / "bin" / "clean"), verify.identity(top / "bpl"),
                          verify.holds_original(Path({str(fetched)!r}), needles, builds),
                          verify.holds_original(Path({str(usage)!r}), marker_only, builds, binary),
                          len(shipped), sorted(size for sizes in shipped.values() for size in sizes)[:1],
                          verify.holds_original(Path({str(quoted)!r}), marker_only, builds, binary)]))
    """))
    assert found[0] == "/app/rebuild/bpl holds the marker" and found[1] is None, "found across a 1 MB chunk boundary, never through a link"
    assert found[2]["sha256"] == found[2]["sha256_without_marker"] and found[3]["sha256"] != found[3]["sha256_without_marker"]
    assert found[4] == "/app/rebuild/lib/_core.so is a build of BasedPL that upstream publishes"
    assert found[5] == "/app/rebuild/bpl holds the usage text", "found across a 1 MB chunk boundary"
    assert found[6] == 12 and found[7][0] > 30_000_000, "three release binaries and nine Python extensions, all distinct"
    assert found[8] is None, "the usage text in a note or a script is no fetched build"
    shipped = json.loads((STEP / "tests" / "verifier" / "upstream_builds.json").read_text())["builds"]
    assert {build["source"].split(":")[0] for build in shipped} >= {"GitHub release v0.1.95"}
    assert sum("bpl-linux-x86_64" in build["source"] for build in shipped) == 1
    package = (SCRIPTS / "package_step.py").read_text()
    assert 'for place in ("environment", f"{STEP}/tests"):' in package and 'content[f"{place}/original/marker"] = marker' in package
    assert "solution/marker" not in package
    solve = (STEP / "solution" / "solve.sh").read_text()
    assert '"$here/build.txt" - /app/rebuild/bpl' in solve, "the solution installs the build with no marker"
    verify = (STEP / "tests" / "verify.py").read_text()
    assert verify.index("holds_original(SUBMISSION, needles, builds, binary_needles)") < verify.index("metrics = grade(")
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
    assert [line.split(" ", 1)[0] for line in facts.splitlines()] == ["link", "sha256", "sha256_without_marker"], facts
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


# ---------------------------------------------------------------- a reward needs programs run

def least_distinct_outputs() -> int:
    """runcases.DISTINCT_OUTPUTS, the different outputs a reward needs, read from the verifier in a process of its
    own (verify.DISTINCT_OUTPUTS is the same value).

    Returns:
        The count, a positive integer.
    """
    least, same = verifier_call("import json, verify\nprint(json.dumps([verify.runcases.DISTINCT_OUTPUTS, verify.DISTINCT_OUTPUTS]))")
    assert isinstance(least, int) and least > 1 and least == same, (least, same)
    return least


LOOKUP = r'''import json, sys
table = json.load(open(sys.argv[1], "rb"))
argv, stdin = sys.argv[2:], sys.stdin.buffer.read().decode("utf-8")
def holds(files):
    for name, text in files.items():
        try:
            if open(name, "rb").read().decode("utf-8") != text:
                return False
        except (OSError, UnicodeDecodeError):
            return False
    return True
for row in table:
    if row["argv"] == argv and (row["stdin"] or "") == stdin and holds(row["files"]):
        sys.stdout.buffer.write(row["stdout"].encode("utf-8"))
        sys.stdout.flush()
        sys.exit(row["exit"])
sys.exit(3)
'''


def answering(tmp_path: Path, name: str, cases: list[dict], expected: dict, ids: set[str]) -> str:
    """A program for run_verifier that answers exactly the cases `ids`, each with its recorded answer (matched by
    its arguments, its standard input and the files in its working directory, from a table beside the program), and
    exits 3 with nothing for any other.

    Args:
        tmp_path: The check's scratch directory; the table and its reader are written there.
        name: This program's table's name, unique within the check.
        cases: The cases, as the private cases.json holds them.
        expected: Their recorded answers by id.
        ids: The ids of the cases the program answers.

    Returns:
        The program's shell text, without its #! line (run_verifier adds it).
    """
    (tmp_path / "lookup.py").write_text(LOOKUP)
    table = tmp_path / f"{name}.json"
    table.write_text(json.dumps([dict(argv=case["argv"], stdin=case["stdin"], files=case["files"], **expected[case["id"]])
                                 for case in cases if case["id"] in ids], ensure_ascii=False))
    return f'exec python3 "{tmp_path / "lookup.py"}" "{table}" "$@"\n'


def gate_cases(least: int) -> tuple[list[dict], dict, dict[str, list[str]]]:
    """Cases shaped as the kept ones are, for the distinct-output checks, in families.

    - "cli": the command line's own cases (options, wrong arguments, and one that runs a program from standard input);
    - "own": least + 10 programs given after -e, each printing an output of its own;
    - "echo": least + 5 programs given after -e that print a literal of their own code back;
    - "message": least + 5 error cases whose guard prints what it caught, in each of the four forms the generator
      writes (the error record, the message, the kind and message, the line, column and message), each another
      message;
    - "empty": 8 programs in a file that print nothing and exit 1;
    - "common": 8 programs in a file that all print one common answer;
    - "blank", "worker", "stdin": a program whose output is empty, a worker session, a program on standard input.

    Args:
        least: runcases.DISTINCT_OUTPUTS.

    Returns:
        The cases, as the private cases.json holds them; their recorded answers by id; and the ids by family.
    """
    cases, expected, families = [], {}, {}

    def add(family: str, kind: str, argv: list[str], stdout: str, code: int = 0, files: dict | None = None,
            stdin: str | None = None) -> None:
        ident = f"G{len(cases):03d}"
        cases.append({"id": ident, "kind": kind, "argv": argv, "files": files or {}, "stdin": stdin})
        expected[ident] = {"stdout": stdout, "exit": code}
        families.setdefault(family, []).append(ident)

    add("cli", "cli", ["--version"], "basedpl 0.1.95\n")
    add("cli", "cli", ["--help"], "Usage: bpl [-e EXPR [ARG...] | FILE [ARG...] | - [ARG...] | --worker]\n")
    add("cli", "cli", ["--verbose"], "", 2)
    add("cli", "cli", ["-e"], "", 2)
    add("cli", "cli", ["-", "alpha"], '["alpha"]\n', stdin='⎕←•host "args"\n')
    for i in range(least + 10):
        add("own", "expr", ["-e", f"v{i}+1"], f"w{i}\n")
    for i in range(least + 5):
        add("echo", "expr", ["-e", f'"e{i}"'], f'"e{i}"\n')
    shown = (("$e", lambda i: f'["kind":"DOMAIN" "message":"m{i}" "source":"main.bpl" "line":1ₓ "column":9ₓ]'),
             ("$e.message", lambda i: f'"m{i}"'), ('$e.kind,": ",$e.message', lambda i: f'"DOMAIN: m{i}"'),
             ('(⍕$e.line),":",(⍕$e.column),": ",$e.message', lambda i: f'"1ₓ:9ₓ: m{i}"'))
    for i in range(least + 5):
        handler, answer = shown[i % 4]
        add("message", "error", ["main.bpl"], answer(i) + "\n", files={"main.bpl": f'{{∞::{handler} ◇ {i}÷"a"}}0\n'})
    for i in range(8):
        add("empty", "error", ["main.bpl"], "", 1, files={"main.bpl": f"x{i}←1 2+1 2 3\n"})
    for i in range(8):
        add("common", "script", ["main.bpl"], "common\n", files={"main.bpl": f"y{i}←1\n"})
    add("blank", "expr", ["-e", "⍬⍴0"], "")
    add("worker", "worker", ["--worker"], '{"id":1,"result":2}\n', stdin='{"id":1,"code":"1+1"}\n')
    add("stdin", "stdin", ["-"], "6\n", stdin="⎕←2×3\n")
    return cases, expected, families


def test_a_case_counts_toward_a_reward_only_when_only_a_run_of_its_code_gives_its_answer():
    """v5's verdict: two launchers that run nothing earned 6 and 1 of 1,673 cases with the command line's documented
    strings and with empty output; the re-check of round 13 then built, with no hidden data, programs that echo
    literals and look the build's error messages up in a table, for every form a guard prints them in (its round-14
    follow-up, M2). A reward needs DISTINCT_OUTPUTS different outputs among the passed cases that give code of their
    own to run (after -e, a file of the case's own named first, a program or worker requests on standard input),
    leaving out empty outputs, outputs whose every line occurs in the case's own input, every error case whose code
    runs under a guard (whatever its handler prints: the generator's "guarded" mark, or a guard that catches every
    error in main.bpl), and the command line's own cases. An output counts once however many passed cases share it."""
    found = verifier_call(textwrap.dedent('''
        import json
        from verifier import recorder, runcases
        def case(ident, kind, argv, files=None, stdin=None, form=None):
            return {"id": ident, "kind": kind, "argv": argv, "files": files or {}, "stdin": stdin, **({"form": form} if form else {})}
        guard = lambda handler: {"main.bpl": "{∞::" + handler + ' ◇ 1÷"a"}0\\n'}
        shapes = [case("e", "expr", ["-e", "1+1"]), case("file", "script", ["main.bpl", "x"], {"main.bpl": "1+1"}),
                  case("dash", "stdin", ["-", "a"], stdin="1+1\\n"), case("bare", "stdin", [], stdin="1+1\\n"),
                  case("worker", "worker", ["--worker"], stdin='{"id":1,"code":"1"}\\n'),
                  case("version", "expr", ["--version"]), case("help", "expr", ["--help"]), case("lone-e", "expr", ["-e"]),
                  case("missing", "error", ["gone.bpl"], {"main.bpl": "1"}), case("no-input", "stdin", ["-"]),
                  case("empty-input", "stdin", [], stdin=""), case("worker-args", "worker", ["--worker", "now"], stdin="{}"),
                  case("cli-e", "cli", ["-e", "•host \\"version\\""]), case("cli-file", "cli", ["run.bpl"], {"run.bpl": "5"}),
                  case("cli-stdin", "cli", ["-", "alpha"], stdin="1\\n"),
                  case("copied", "expr", ["-e", '⊢"abc"']), case("copied-lines", "script", ["main.bpl"], {"main.bpl": 'x←"Hip" "Hop"'}),
                  case("copied-library", "module", ["main.bpl"], {"main.bpl": "f 2", "lib/a.bpl": "f←{ω} ⍝ 42"}),
                  case("partly-copied", "script", ["main.bpl"], {"main.bpl": 'x←"Hip" ◇ x,"!"'}),
                  case("message", "error", ["main.bpl"], guard("$e.message")),
                  case("kind-message", "error", ["main.bpl"], guard('$e.kind,": ",$e.message')),
                  case("other-handler", "error", ["main.bpl"], guard('"caught"')),
                  case("record", "error", ["main.bpl"], guard("$e")),
                  case("position", "error", ["main.bpl"], guard('(⍕$e.line),":",(⍕$e.column),": ",$e.message')),
                  case("form-only", "error", ["main.bpl"], {"main.bpl": '{DOMAIN::⍕$e ◇ 1÷"a"}0\\n'}, form="guarded"),
                  case("message-elsewhere", "script", ["main.bpl"], guard("$e.message"))]
        answers = {"e": "2\\n", "file": "2\\n", "dash": "2\\n", "bare": "", "worker": "{}\\n", "version": "v\\n", "help": "h\\n",
                   "lone-e": "", "missing": "", "no-input": "", "empty-input": "", "worker-args": "", "cli-e": "c\\n",
                   "cli-file": "7\\n", "cli-stdin": "a\\n", "copied": '"abc"\\n', "copied-lines": "Hip\\nHop\\n",
                   "copied-library": "42\\n", "partly-copied": "Hip!\\n", "message": '"DOMAIN: no"\\n',
                   "kind-message": '"DOMAIN: no"\\n', "other-handler": '"handled"\\n', "message-elsewhere": '"DOMAIN: no"\\n',
                   "record": '["kind":"DOMAIN" "message":"no" "source":"main.bpl" "line":1ₓ "column":8ₓ]\\n',
                   "position": '"1ₓ:8ₓ: no"\\n', "form-only": '"DOMAIN no"\\n'}
        expected = {ident: {"stdout": text, "exit": 0} for ident, text in answers.items()}
        every = set(answers)
        counted = {c["id"]: runcases.counts(c, expected[c["id"]]) for c in shapes}
        guarded = [sorted(c["id"] for c in shapes if runcases.guarded_error(c)), sorted(i for i, *_ in recorder.error_instances(shapes, expected))]
        totals = [runcases.distinct_outputs(shapes, expected, every), runcases.distinct_outputs(shapes, expected, every - {"worker"}),
                  runcases.distinct_outputs(shapes, expected, {"version", "help", "cli-e", "cli-file", "cli-stdin", "bare", "copied",
                                                               "copied-lines", "copied-library", "message", "kind-message"}),
                  runcases.distinct_outputs(shapes, expected, set())]
        print(json.dumps([{c["id"]: runcases.runs_a_program(c) for c in shapes}, counted, guarded, totals]))
    '''))
    runs, counted, guarded, totals = found
    assert {ident for ident, value in runs.items() if not value} == {
        "version", "help", "lone-e", "missing", "no-input", "empty-input", "worker-args", "cli-e", "cli-file", "cli-stdin"}, runs
    assert {ident for ident, value in counted.items() if value} == {
        "e", "file", "dash", "worker", "partly-copied", "message-elsewhere"}, counted
    assert guarded[0] == ["form-only", "kind-message", "message", "other-handler", "position", "record"], guarded
    assert set(guarded[1]) <= set(guarded[0]), "every case the recorder's error lookup reads is left out too"
    # "2" (three cases, once), "{}", "Hip!" and the message outside an error case
    assert totals == [4, 3, 0, 0], totals
    # The rule, its note and the build's guard are worded as what a program must do, never as who checks it or why.
    verify, runner = (STEP / "tests" / "verify.py").read_text(), RUNNER.read_text()
    recording = (STEP / "tests" / "verifier" / "recording.py").read_text()
    between = lambda text, start, end: text[text.index(start):text.index(end, text.index(start))]  # noqa: E731
    gate = (between(verify, "# The least runcases.distinct_outputs", "METRICS_SPACE = ") + between(verify, "def withheld(", "def grade(")
            + between(runner, "# The least distinct_outputs a reward needs.", "\n\n\ndef limit(")
            + runner[runner.index("def runs_a_program("):] + between(recording, "def dispatcher_too_close(", "def main("))
    assert "DISTINCT_OUTPUTS = 12" in gate and "DISTINCT_OUTPUTS = runcases.DISTINCT_OUTPUTS" in gate and "def counts(" in gate
    assert "MESSAGE_HANDLERS" not in runner and "def guarded_error(" in gate, "no list of handlers to fall behind the generator's"
    assert runner.rstrip().endswith("if case[\"id\"] in passed and counts(case, expected[case[\"id\"]])})"), "the runner's last function"
    words = re.compile(r"platform|trial|evaluat|benchmark|stub|exploit|adversar|cheat|hack|oddish|harbor|modal|verdict|"
                       r"\bQA\b|launcher|grader", re.I)
    assert not words.findall(gate), words.findall(gate)


def test_only_a_program_that_runs_what_it_is_given_earns_a_reward(tmp_path):
    """The real grade() on cases shaped as the kept ones, against the programs v5's two replays delivered (the
    command line's documented strings and exit 2 for everything else; exit 0 for everything), every constant answer
    the cases share, an echo of literals, a table of what the guarded cases print (re-check 10's err-table shape:
    the record, the message, the kind and message, the line:column form), and a table one counted output short
    (which also answers the command line's own program, every echo, every guarded case and every empty output):
    each passes cases and scores exactly 0, with the note in metrics.json. One more counted output (the program on
    standard input) and the same table earns its share."""
    least = least_distinct_outputs()
    cases, expected, families = gate_cases(least)
    total = len(cases)
    docs = ('case "$*" in --version) echo "basedpl 0.1.95";; '
            '--help) echo "Usage: bpl [-e EXPR [ARG...] | FILE [ARG...] | - [ARG...] | --worker]";; *) exit 2;; esac\n')
    shared = sorted({(answer["stdout"], answer["exit"]) for answer in expected.values()
                     if sum(other == answer for other in expected.values()) > 1})
    assert len(shared) == 3, shared  # nothing and exit 1, the common answer, nothing and exit 2
    few = set(families["own"][:least - 3] + families["common"] + families["worker"] + families["echo"] + families["message"]
              + families["empty"] + families["blank"] + [families["cli"][-1]])
    programs = {"docs": docs, "exit 0": "exit 0\n",
                **{f"constant {stdout!r} {code}": f"printf '%s' '{stdout}'\nexit {code}\n" for stdout, code in shared},
                "echo": 'case "$1" in -e) printf \'%s\\n\' "$2"; exit 0;; esac\nexit 3\n',
                "messages": answering(tmp_path, "messages", cases, expected, set(families["message"])),
                "too few": answering(tmp_path, "too-few", cases, expected, few),
                "enough": answering(tmp_path, "enough", cases, expected, few | set(families["stdin"]))}
    results = {name: run_verifier(tmp_path, script, cases, expected) for name, script in programs.items()}
    for name, metrics in results.items():
        assert metrics["cases_total"] == total and metrics["distinct_outputs_needed"] == least, (name, metrics)
        if name == "enough":
            continue
        assert metrics["cases_passed"] > 0 and metrics["reward"] == 0.0, (name, metrics["cases_passed"], metrics["reward"])
        assert metrics["withheld"] and metrics["notes"][-1] == metrics["withheld"], (name, metrics["notes"])
        passed, distinct = metrics["cases_passed"], metrics["distinct_outputs"]
        prefix = (f"reward 0: the {passed} {'case' if passed == 1 else 'cases'} passed {'holds' if passed == 1 else 'hold'} "
                  f"{distinct} different {'output' if distinct == 1 else 'outputs'}")
        assert metrics["withheld"].startswith(prefix), (prefix, metrics["withheld"])
    assert (results["docs"]["cases_passed"], results["docs"]["distinct_outputs"]) == (4, 0), "--version, --help and two exit 2s"
    assert (results["exit 0"]["cases_passed"], results["exit 0"]["distinct_outputs"]) == (1, 0)
    assert max(results[name]["distinct_outputs"] for name in results if name.startswith("constant")) == 1
    assert (results["echo"]["cases_passed"], results["echo"]["distinct_outputs"]) == (least + 5, 0), "echoes never count"
    assert (results["messages"]["cases_passed"], results["messages"]["distinct_outputs"]) == (least + 5, 0), \
        "nor what a guard prints, in any of its four forms (re-check 10, M2: the record and the line:column form)"
    too_few, enough = results["too few"], results["enough"]
    # (least - 3) own outputs, the common answer once, the worker's reply: one short, whatever the others add
    assert too_few["distinct_outputs"] == least - 1 and too_few["cases_passed"] == len(few), too_few
    assert enough["distinct_outputs"] == least and enough["cases_passed"] == len(few) + 1, enough
    assert enough["reward"] == round(enough["cases_passed"] / total, 6) > 0 and not enough["notes"] and enough["withheld"] is None
    verify = (STEP / "tests" / "verify.py").read_text()
    grade = verify[verify.index("def grade("):verify.index("def final_cleanup(")]
    assert grade.index('metrics["reward"] = round(') < grade.index("runcases.distinct_outputs(kept, expected, passed)") \
        < grade.index('metrics["reward"] = 0.0'), "the share is computed, then withheld below the least"


def test_a_partial_interpreter_shaped_as_v4s_glm_run_keeps_its_share(tmp_path):
    """Re-check 10, M1: round 13's rule (40 outputs of programs, echoes and messages included) zeroed v4's GLM-5.3 run
    -33, an honest partial interpreter the platform graded 0.037059 and classed a good failure. Its passes, as
    graded locally: 11 of the command line's own cases, 6 programs that print nothing, 8 whose answer is copied
    from their input (6 different outputs) and 32 more, among them one output three times (30 different). The
    same pattern, answered by a table on cases of the same shapes and kinds, keeps its share: 30 counted outputs,
    two and a half times the least."""
    least = least_distinct_outputs()
    cases, expected, passing = [], {}, set()

    def add(kind: str, argv: list[str], stdout: str, code: int = 0, files: dict | None = None, stdin: str | None = None,
            answered: bool = True) -> None:
        ident = f"V{len(cases):03d}"
        cases.append({"id": ident, "kind": kind, "argv": argv, "files": files or {}, "stdin": stdin})
        expected[ident] = {"stdout": stdout, "exit": code}
        if answered:
            passing.add(ident)

    for i in range(11):
        add("cli", [f"--option-{i}"], f"usage {i}\n" if i % 2 else "", 0 if i % 2 else 2)
    for i in range(6):
        add("error", ["main.bpl"], "", 1, files={"main.bpl": f"x{i}←1 2+1 2 3\n"})
    for i, line in enumerate(["5", "7", "1", "Hip\nHop", "1", "2ₓ", "7", '"bar"']):
        add("expr", ["-e", f"c{i}←{' '.join(line.splitlines())} ◇ c{i}"], line + "\n")
    outputs = ["r0", "r0", "r0"] + [f"r{j}" for j in range(1, 30)]
    for j, (kind, output) in enumerate(zip(["stdin"] * 8 + ["apl"] * 7 + ["script"] * 4 + ["expr"] * 13, outputs)):
        if kind == "stdin":
            add(kind, ["-"], output + "\n", stdin=f"⎕←p{j}\n")
        elif kind == "script":
            add(kind, ["main.bpl"], output + "\n", files={"main.bpl": f"p{j}\n"})
        else:
            add(kind, ["-e", f"p{j}"], output + "\n")
    for k in range(200 - len(cases)):  # what the partial interpreter got wrong
        add("expr", ["-e", f"q{k}"], f"s{k}\n", answered=False)
    metrics = run_verifier(tmp_path, answering(tmp_path, "glm", cases, expected, passing), cases, expected)
    assert (metrics["cases_total"], metrics["cases_passed"], metrics["distinct_outputs"]) == (200, 57, 30), metrics
    assert metrics["distinct_outputs"] >= 2.5 * least and metrics["withheld"] is None and not metrics["notes"], metrics
    assert metrics["reward"] == round(57 / 200, 6), metrics["reward"]


def test_the_build_stops_when_the_cases_bring_a_program_with_no_interpreter_near_a_reward(tmp_path):
    """Re-check 10, N2: recording.py stops the verifier image's build (exit status 1, the reason on standard error)
    when the strongest program with no interpreter in it that the recorder knows answers kept cases holding more
    than a third of DISTINCT_OUTPUTS counted outputs, so that a new seed or template cannot bring such a program
    near a reward unnoticed. Here its one constant per visible shape gives one counted output per shape: a third of
    the least passes the build, one more stops it."""
    least = least_distinct_outputs()
    most = least // 3  # the most the build allows
    shapes = [(["-e", "aa"], ["-e", "ab"], {}, None), (["main.bpl"], ["main.bpl"], {"main.bpl": "aa"}, None),
              (["-"], ["-"], {}, "aa"), (["main.bpl", "x"], ["main.bpl", "x"], {"main.bpl": "ac"}, None),
              (["main.bpl", "x", "y"], ["main.bpl", "x", "y"], {"main.bpl": "ad"}, None),
              (["-", "x"], ["-", "x"], {}, "ae"), (["main.bpl", "x", "y", "z"], ["main.bpl", "x", "y", "z"], {"main.bpl": "af"}, None)]
    assert most + 1 <= len(shapes), "enough shapes to pass the bound by one"

    def recorded(count: int) -> subprocess.CompletedProcess:
        folder = tmp_path / f"shapes-{count}"
        folder.mkdir()
        kept, expected = [], {}
        for n, (first, second, files, stdin) in enumerate(shapes[:count]):
            for m, argv in enumerate((first, second)):
                ident = f"P{n}{m}"
                own = {name: text + str(m) for name, text in files.items()}
                kept.append({"id": ident, "kind": "script", "argv": argv, "files": own, "stdin": None if stdin is None else stdin + str(m)})
                expected[ident] = {"stdout": f"{42 + n}\n", "exit": 0}
        timing = {"keep_seconds": 1.0, "keep_cpu": 0.25, "seconds": {case["id"]: [0.1] for case in kept}, "slow": [], "unsteady": [],
                  "crashed": [], "machine": [], "dropped": {}, "settled": {}}
        for name, data in (("cases.json", {"cases": kept}), ("kept.json", {"cases": kept}), ("expected.json", expected),
                           ("timing.json", timing)):
            (folder / name).write_text(json.dumps(data))
        return subprocess.run([sys.executable, "-B", str(STEP / "tests" / "verifier" / "recording.py"),
                               *(str(folder / name) for name in ("cases.json", "kept.json", "expected.json", "timing.json", "out.json"))],
                              capture_output=True, text=True, timeout=60, cwd=STEP / "tests" / "verifier")

    allowed, stopped = recorded(most), recorded(most + 1)
    assert allowed.returncode == 0, allowed.stderr[-2000:]
    assert json.loads((tmp_path / f"shapes-{most}" / "out.json").read_text())["baselines"]["no_interpreter_dispatcher_distinct_outputs"] == most
    assert stopped.returncode == 1 and (tmp_path / f"shapes-{most + 1}" / "out.json").is_file(), stopped.stderr[-2000:]
    assert (f"hold {most + 1} different outputs that only a run of the code given produces, more than a third of the {least}"
            in stopped.stderr), stopped.stderr[-2000:]
    docker = (STEP / "tests" / "Dockerfile").read_text()
    assert "&& python3 /record/recording.py " in docker, "the guard runs in the step that records, so its exit stops the build"


DELIVERY = r"""
import json, os, subprocess, sys, tarfile
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import verify
hook, base = Path(sys.argv[2]).read_text(), Path(sys.argv[3])
# [1] is what the frozen processes hold open for writing, before the kill
prescan = hook.split("<<'EOF'\n")[2].split("\nEOF\n", 1)[0]  # every entry's times before the hook, then the permissions, as root
session = hook.split("<<'EOF'\n")[3].split("\nEOF\n", 1)[0]  # connectivity and the agent's processes, as root
fixer = hook.split("<<'EOF'\n")[4].split("\nEOF\n", 1)[0]  # the link fixer, run as the agent's user
measure = hook.split("<<'EOF'\n")[5].split("\nEOF\n", 1)[0]  # the last script, run as root after it
FULL = ("import os\n_statvfs = os.statvfs\nclass Full:\n    f_bavail = f_favail = 0\n    f_frsize, f_blocks, f_files = 4096, 1000000, 1000000\n"
        "os.statvfs = lambda path: Full()\n")  # a disk with no room and no inode left
CLOSED = ("import socket\ndef refuse(address, timeout=None):\n    raise ConnectionRefusedError(111, 'refused')\n"
          "socket.create_connection = refuse\n")
SLOW = "import socket, time\nsocket.create_connection = lambda address, timeout=None: time.sleep(30)\n"
STARTED = str(int(__import__("time").time()))  # when the hook began: its last script refuses what it cannot finish in time


def deliver(name, build, entries="100000", size="1000000000", path="1000", seconds="100", start=None, tar=None, prelude="",
            fixer_status="0", aside=()):
    app = base / name / "app"
    rebuild, state, archives = app / "rebuild", base / name / "state", base / name / "tmp"
    for folder in (rebuild, state, archives):
        folder.mkdir(parents=True)
    if start is not None:
        (state / "free-at-start").write_text(start)
    (state / "session.json").write_text(json.dumps({"connectivity": {"pypi.org:443": "closed"}, "connectivity_open": False,
                                                    "user_process_count": 1, "user_processes": [{"pid": 7, "command": "sleep 99"}]}))
    (state / "turn-started").write_text(f"{int(STARTED) - 100}\n")  # well inside the session's limit
    if aside:  # the names the shell moved out of the directory before the fixer ran
        (state / "aside.txt").write_text("".join(f"{moved}\n" for moved in aside))
    if name == "good":  # what the link fixer printed: a copy of a system file, and a refused link to the user's own files
        (state / "fixer.jsonl").write_text(json.dumps({
            "kind": "copied", "path": "venv/bin/python3", "source": "/usr/bin/python3.12", "source_owner": 0,
            "source_mtime": 1690000000.0, "source_ctime": 1690000000.0, "source_inode": [66, 1234],
            "source_latest_ctime": 1690000000.0, "source_latest_mtime": 1690000000.0,
            "note": "venv/bin/python3: a copy of /usr/bin/python3.12 (was a link to /usr/bin/python3.12)"}) + "\n" + json.dumps({
            "kind": "refused", "path": "vendor", "source": "/home/dev/cache", "source_owner": 10001,
            "source_mtime": int(STARTED) - 60.0, "source_ctime": int(STARTED) - 50.0, "source_inode": [66, 99],
            "source_latest_ctime": int(STARTED) - 50.0, "source_latest_mtime": int(STARTED) - 60.0,
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
                           STARTED, *([fixer_status] if fixer_status is not None else [])], input=prelude + measure,
                          capture_output=True, text=True, timeout=300, env=environment)
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
        return verify.delivery_notes(rebuild)
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
record = json.loads((rebuild / ".manifest.json").read_text())
out["record"] = [record["connectivity_open"], record["kill_rounds"], record["user_processes_left"], record["delivered"],
                 record["listing_complete"], sorted(item["path"] for item in record["entries"]),
                 next(item for item in record["entries"] if item["path"] == "bpl")]
out["copies"] = [record["turn_started"], record["hook_started"], record["copies"], record["links"], record["notes"]]
out["started"] = int(STARTED)
out["end"] = [record["work_end"], record["late_entries"], verify.delivery_record(rebuild)["late_entries"]]
earlier = EARLIER["good"]
out["times"] = [all(item["ctime"] == earlier[item["path"]][1] and item["mtime"] == earlier[item["path"]][0]
                    for item in record["entries"] if item["path"] in earlier),
                sorted(item["path"] for item in record["entries"] if item.get("hook_changed_ctime")),
                sorted(item["path"] for item in record["entries"] if item["path"] not in earlier),
                record["prescan_complete"], record["hook_changed_entries"],
                oct(os.stat(rebuild / "ro").st_mode & 0o777), oct(os.stat(rebuild / "secret").st_mode & 0o777)]
out["summary"] = verify.delivery_record(rebuild)
out["latest"] = max(earlier[item["path"]][1] for item in record["entries"])  # the latest change the session itself made
out["complete"] = notes(copy(rebuild, base / "good" / "copied"))
partial = copy(rebuild, base / "good" / "partial")
(partial / "src" / "main.py").unlink()  # the mark arrived, a file did not
out["partial"] = notes(partial)
size = os.path.getsize(base / "good" / "copied.tar")
out["cut"] = notes(copy(rebuild, base / "good" / "cut", cut=size // 3))
out["nothing"] = notes(copy(rebuild, base / "good" / "empty", cut=0))
(rebuild / ".manifest").write_text("delivered ² 5\n")  # not ASCII digits: a mark the hook did not write
out["odd"] = notes(rebuild)
(rebuild / ".manifest").unlink()
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
out["end"].append(verify.delivery_record(base / "nop" / "copied")["late_entries"])
app, rebuild = deliver("cut-short", tree, fixer_status="143", aside=(".manifest", ".manifest.json"))  # the fixer was ended by a signal
record = json.loads((rebuild / ".manifest.json").read_text())
out["cut_short"] = [mark(rebuild), record["fixer_status"], notes(copy(rebuild, base / "cut-short" / "copied"))]
app, rebuild = deliver("old-arguments", lambda rebuild: None, fixer_status=None)  # without the status: no note, never an error
out["old_arguments"] = [mark(rebuild), json.loads((rebuild / ".manifest.json").read_text())["fixer_status"]]
app, rebuild = deliver("unwritable", tree)
out["unwritable"] = mark(rebuild)[:2]
linked = base / "linked" / "app" / "rebuild"
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
(long_mark / ".manifest").write_text("delivered 1 10\n" + "".join(f"removed decoy{i} -> /home/dev/x{i}: it leads outside\n" for i in range(60)))
out["long_mark"] = len(verify.delivery_notes(long_mark))
print(json.dumps(out))
"""


def test_the_delivery_is_bounded_recorded_and_marked_before_the_copy_and_graded_as_it_arrives(tmp_path):
    """The collect hook (environment/reclaim-scratch, root, first and only [[verifier.collect]]) records whether the
    public internet answers (two hosts, 3 s each) and the agent's live processes, ends them with `kill -9 -1` as their
    user until none is left, gives back room and inodes set aside at setup, fixes links as the agent's user, then as
    root walks the delivery by directory descriptor, refuses on anything it cannot complete or past 100,000 entries,
    1 GB (each file once) or paths of 1,000 bytes, removes what the copy would refuse, packs it once the way the copy
    does within 100 s, and writes a record of every entry (path, size, times, sha256) and the mark. The verifier grades
    what arrived, with a note when the mark is missing or says refused; nothing arriving, or a mark that counts more
    than arrived, is an evaluation error (ported from the back-office task, rounds 6 and 7)."""
    done = subprocess.run([sys.executable, "-I", "-B", "-c", DELIVERY, str(STEP / "tests"), str(TASK / "environment" / "reclaim-scratch"),
                           str(tmp_path)], capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stderr[-3000:]
    out = json.loads(done.stdout.strip().splitlines()[-1])
    run = len("#!/bin/sh\nexec python3 src/main.py\n")
    # src, src/main.py, src/b, src/b/up, bpl, bpl-again, empty, inside, ro, ro/lnk, secret: 11 entries; bpl and bpl-again are one file
    assert out["mark"][0] == f"delivered 11 {601 + run}", out["mark"]
    assert out["mark"][1:3] == ["removed vendor -> /home/dev/cache: it leads outside /app/rebuild to something that is not part of the "
                                "machine's installation (not owned by root), which is not copied",
                                "venv/bin/python3: a copy of /usr/bin/python3.12 (was a link to /usr/bin/python3.12)"], \
        "the fixer's notes, dropped links first"
    assert sorted(out["mark"][3:8]) == ["removed absolute: a link that leads outside /app/rebuild",
                                        "removed esc -> src/b/up/../..: a link through another link, or to nothing",
                                        "removed outside: a link that leads outside /app/rebuild", "removed pipe: not a file, a directory or a link",
                                        "removed ro/a -> lnk/../../..: a link through another link, or to nothing"], "through links, or leaving"
    assert sorted(out["mark"][8:]) == ["ro: made writable for its owner (a directory the hook has to work in)", "secret: made readable by its owner"]
    turn_started, hook_started, copies, links, notes = out["copies"]
    assert (turn_started, hook_started) == (out["started"] - 100, out["started"]) and len(notes) == 9
    untouched, changed, made, prescan_complete, changed_count, ro_mode, secret_mode = out["times"]
    assert untouched, "every entry's mtime and ctime are the ones from before the hook ran"
    assert changed == ["ro", "secret"] and changed_count == 2, "the hook's own chmods are flagged, with the later ctime kept apart"
    assert made == [] and prescan_complete is True and (ro_mode, secret_mode) == ("0o755", "0o400")
    assert out["end"] == [out["started"] - 100 + 34561, 0, 0, 0], "the end of the work, and nothing changed after it"
    assert len(copies) == 1 and copies[0]["source"] == "/usr/bin/python3.12" and copies[0]["source_owner"] == 0
    assert copies[0]["source_inode"] == [66, 1234] and copies[0]["outside_delivery"] is True
    assert copies[0]["changed_since_session_started"] is False, "a system file from the image build"
    assert links[0]["kind"] == "refused" and links[0]["changed_since_session_started"] is True and links[0]["outside_delivery"] is True
    assert out["left"] == [".manifest", ".manifest.json", "bpl", "bpl-again", "empty", "inside", "ro", "secret", "src"]
    connectivity_open, rounds, left, delivered, complete, paths, bpl = out["record"]
    assert [connectivity_open, rounds, left, delivered, complete] == [False, 2, 0, out["mark"][0], True]
    assert paths == ["bpl", "bpl-again", "empty", "inside", "ro", "ro/lnk", "secret", "src", "src/b", "src/b/up", "src/main.py"]
    assert bpl["type"] == "file" and bpl["size"] == run and len(bpl["sha256"]) == 64 and bpl["ctime"] > 1.7e9
    summary = out["summary"]
    assert summary["connectivity_open"] is False and summary["entries"] == 11 and summary["kill_rounds"] == 2 and summary["bpl"] == bpl
    assert summary["hashing_complete"] is True and summary["prescan_complete"] is True and summary["hook_changed_entries"] == 2
    assert summary["latest_ctime"] == out["latest"], "the latest ctime in metrics is the session's own, not the hook's"
    assert summary["user_processes"] == [{"pid": 7, "command": "sleep 99"}] and summary["latest_ctime"] >= bpl["ctime"]
    assert summary["copies"] == copies and summary["links"] == links and summary["notes"] == notes, "the whole record reaches metrics.json"
    assert summary["copies_outside_delivery"] == 1 and summary["copies_changed_since_session_started"] == 0
    assert (summary["turn_started"], summary["hook_started"]) == (out["started"] - 100, out["started"])
    assert out["long_mark"] == 60, "the verifier reads the whole mark, however many notes"
    verify_text = (STEP / "tests" / "verify.py").read_text()
    assert "handle.read(MARK_LIMIT + 1)" in verify_text and "MARK_LIMIT = 1 << 20" in verify_text, "bounded all the same"
    hook_text = (TASK / "environment" / "reclaim-scratch").read_text()
    assert "pgrep -u dev -r R,S,D,T" in hook_text and "pgrep -u dev -r R,S >" in hook_text, "zombies are never survivors"
    assert "chmod -R" not in hook_text, "no chmod of every entry: that would set every ctime to the hook's time (07c F1)"
    assert hook_text.index("for visit in (record, restore):") < hook_text.index("timeout 120 setpriv"), "times first, then permissions, then the fixer"
    assert "def destination(path, target):" in hook_text and "HASH_SECONDS = 240" in hook_text and "if inode in digests:" in hook_text
    assert out["complete"] == [f"maintenance step: {line}" for line in out["mark"][1:]], out["complete"]
    assert out["cut"][0].startswith(("ERROR The copy arrived incomplete", "the delivery arrived without", "ERROR Nothing")), out["cut"]
    assert out["nothing"][0].startswith("ERROR Nothing arrived") and out["unmarked"][0].startswith("the delivery arrived without")
    assert out["partial"] == [f"ERROR The copy arrived incomplete: 10 of 11 entries and {run + 1:,} of {601 + run:,} bytes"], out["partial"]
    assert out["more"] == ["more arrived than the collect hook marked: 32 entries and 1,048,598 bytes against 31 and 1,048,576 "
                           "(hard links split, or files the transport added)"], "more than marked is a note, not an error"
    assert out["unwritable"] == ["refused", "its permissions could not be restored for its owner: it was not copied"]
    assert out["linked"] == ["delivered 31 1048576", 1, True], "31 names of one file: one hash, counted once"
    assert out["odd"] == ["the collect hook's mark could not be read; the delivery was graded as it arrived"]
    assert out["many"][0][:2] == ["refused", "it holds more than 3 entries, the most /app/rebuild may hold: it was not copied"], out["many"]
    assert out["many"][0][2:] == ["the listing before the hook stopped at more than 3 entries",
                                  "ro: made writable for its owner (a directory the hook has to work in)", "secret: made readable by its owner"]
    assert out["many"][1:] == [[".manifest", ".manifest.json"], ["rebuild", "refused"]], out["many"]
    assert out["many_notes"][0] == "maintenance step: it holds more than 3 entries, the most /app/rebuild may hold: it was not copied"
    assert out["sparse"] == ["refused", "it holds more than 1,000,000,000 bytes, the most /app/rebuild may hold: it was not copied"]
    assert out["deep"] == ["refused", "it holds a path longer than 1,000 bytes, the longest /app/rebuild may hold: it was not copied"]
    assert out["deep_seen"] == out["sparse"], out["deep_seen"]
    assert out["slow"] == ["refused", "the copy's pack of it took more than 1 seconds: it was not copied"]
    assert out["broken"] == ["refused", "the copy's pack of it failed (tar: ./x: Cannot open: Input/output error): it was not copied"]
    assert out["inodes"][0] == "refused" and "No space left on device" in out["inodes"][1], out["inodes"]
    assert out["never_room"][0].startswith("delivered ") and any("room the machine did not have" in line for line in out["never_room"])
    assert out["nop"] == [["delivered 0 0"], [], 0]
    cut_mark, cut_status, cut_notes = out["cut_short"]  # QA 07e F1 and F5: neither is silent any more
    assert cut_mark[0] == out["mark"][0] and cut_status == 143 and len(cut_mark) == 11, cut_mark
    assert cut_mark[1] == ("the link fixer ended with status 143: the links it had not reached were not fixed, and those that lead "
                           "outside /app/rebuild are removed"), "a fixer that was cut short is said first, before the links removed for it"
    assert cut_mark[7:9] == [f"moved {name} out of /app/rebuild: this step writes a file of that name there"
                             for name in (".manifest", ".manifest.json")], "a file the session left under the hook's own names is noted"
    assert cut_notes == [f"maintenance step: {line}" for line in cut_mark[1:]], "and both reach the trial's notes"
    assert out["old_arguments"] == [["delivered 0 0"], -1]
    assert "never a reason to change the reward" in (STEP / "tests" / "verify.py").read_text(), "the late count is never scored"
    code, kinds, copied, lib_left, one_left, sh_copied, inner = out["fixer"]
    assert code == 0 and kinds == {"lib": "refused", "one": "refused", "sh": "copied", "inner": "relinked"}, out["fixer"]
    assert copied["source"] == "/bin/sh" and copied["source_owner"] == 0 and len(copied["source_inode"]) == 2
    assert copied["source_ctime"] > 1e9 and copied["source_mtime"] > 1e9 and "a copy of /bin/sh" in copied["note"]
    assert not lib_left and not one_left and sh_copied and inner == "real.txt", "the user's own files outside are never copied in"
    closed, slow = out["session"]["closed"], out["session"]["slow"]
    assert closed[0] == 0 and closed[1]["connectivity_open"] is False and set(closed[1]["connectivity"]) == {"pypi.org:443", "github.com:443"}
    assert [process["command"] for process in closed[1]["user_processes"]] == ["sleep 99", "/bin/sh -c curl x"], "from the frozen listing"
    assert closed[1]["user_processes"][1]["running_seconds"] == 3 and closed[1]["user_process_count"] == 2
    assert all(state.startswith("closed") for state in closed[1]["connectivity"].values())
    assert slow[0] == 0 and set(slow[1]["connectivity"].values()) == {"no answer within 3 s"} and slow[2] <= 9, slow
    hook = (TASK / "environment" / "reclaim-scratch").read_text()
    order = [': > "$STATE/collect-began"', 'kill -KILL -- "-$holder"', "--clear-groups kill -STOP -1 >",
             "ps -eo pid=,ppid=,uid=,etimes=,args= > \"$STATE/processes.txt\"", 'cat > "$STATE/writers.py" <<',
             'timeout 30 /usr/bin/python3 -I - /proc /app/rebuild "$(id -u dev 2>/dev/null)"', '> "$STATE/writers.json" 2>/dev/null\n',
             'if [ $? -eq 3 ]; then', "timeout 30 setpriv --reuid dev --regid dev --clear-groups --no-new-privs /usr/bin/python3 -I - /proc",
             '> "$STATE/writers-user.json"', "kill -9 -1",
             'timeout 300 /usr/bin/python3 -I - /app/rebuild "$LIMIT_ENTRIES" "$LIMIT_PATH" "$STATE"',
             "/usr/bin/python3 -I - \"$STATE/session.json\" \"$STATE/processes.txt\"", "rm -f /var/lib/scratch/room",
             "rm -rf /var/lib/scratch/inodes", 'mv -f "/app/rebuild/$name" "$aside/"', 'echo "$name" >> "$STATE/aside.txt"',
             "timeout 120 setpriv --reuid dev --regid dev --clear-groups --no-new-privs /usr/bin/python3 -I -",
             '> "$STATE/fixer.jsonl"', "\nEOF\nfixer_status=$?\n",
             '\n/usr/bin/python3 -I - /app/rebuild "$LIMIT_ENTRIES" "$LIMIT_BYTES" "$LIMIT_PATH" "$STATE" /tmp "$PACK_SECONDS" "$rounds" '
             '"$left" "$HOOK_STARTED" "$fixer_status" <<']
    assert [hook.index(step) for step in order] == sorted(hook.index(step) for step in order)
    assert hook.endswith('print(line.encode(errors="backslashreplace").decode(), flush=True)\nEOF\n'), "the last script ends the hook"
    for setting in ("LIMIT_ENTRIES=100000", "LIMIT_BYTES=1000000000", "LIMIT_PATH=1000", "PACK_SECONDS=100", "STATE=/var/lib/scratch"):
        assert setting in hook, setting
    assert "rm -rf \"$" not in hook and "rm -f \"$" not in hook, "nothing is removed through a variable"
    setup = (TASK / "environment" / "provision-scratch").read_text()
    assert "fallocate -l 64M /var/lib/scratch/room" in setup and '/var/lib/scratch/inodes/$spare' in setup and "seq 1 64" in setup
    assert "stat -f -c '%a %S %d' /tmp > /var/lib/scratch/free-at-start" in setup
    assert "date +%s > /var/lib/scratch/turn-started" in setup, "the session's start, for the record's flags"
    assert hook.index("--clear-groups kill -STOP -1 >") < hook.index("/usr/bin/python3"), "before the freeze: the hook's settings and the mark"
    import tomllib
    config = tomllib.loads((TASK / "task.toml").read_text())
    assert config["verifier"]["collect"] == [{"command": "/usr/local/sbin/reclaim-scratch", "user": "root", "timeout_sec": 600}]
    assert config["agent"]["setup_begin"] == [{"command": "/usr/local/sbin/provision-scratch", "timeout_sec": 120}]
    assert config["agent"]["setup_complete"] == [{"command": "/usr/local/sbin/provision-scratch", "timeout_sec": 120}]
    docker = (TASK / "environment" / "Dockerfile").read_text()
    assert "COPY provision-scratch reclaim-scratch /usr/local/sbin/" in docker
    assert "chmod 0700 /usr/local/sbin/provision-scratch /usr/local/sbin/reclaim-scratch \\\n" in docker
    verify = (STEP / "tests" / "verify.py").read_text()
    main = verify[verify.index("def main() -> int:"):]
    assert main.index("delivery_notes(SUBMISSION)") < main.index("sandbox()") < main.index("seal(SUBMISSION)")
    assert "delivery_record=record" in main, "the record goes to metrics.json"
    assert "[:20]" not in verify[verify.index("def delivery_notes"):verify.index("def delivery_record")], "every note of the mark"
    instruction = " ".join((STEP / "instruction.md").read_text().split())
    assert "at most 100,000 files and directories and 1 GB, with no path inside it longer than 1,000 bytes" in instruction
    assert "only when that is part of the machine's installation (owned by root" in instruction
    assert instruction.index("A link to files of your own anywhere outside the directory is dropped") < instruction.index("only when that is part")
    assert "must be one of the machine's own or copied into `/app/rebuild`" in instruction
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
    runner = RUNNER.read_text()
    assert "or alive(proc.pid, uid)" in runner and "def alive(group: int, uid: int | None) -> bool:" in runner, \
        "a child that holds the pipe open past the deadline is a timeout"


# ---------------------------------------------------------------- the hook's freeze, and no session timer

def hook_prologue(top: Path) -> str:
    """The first lines of environment/reclaim-scratch as shipped, everything before its listing of the user's processes
    (the settings and the freeze), with only the state directory rewritten into `top`. Run it with prologue_env(top)."""
    hook = (TASK / "environment" / "reclaim-scratch").read_text()
    text = hook[:hook.index("ps -eo pid=")]
    assert "kill -STOP -1" in text and text.count("setpriv") == 1, "the freeze"
    assert "python3" not in text and "kill -9" not in text and "pkill -KILL -u" not in text, "nothing of the later steps"
    assert "/var/lib/scratch" in text
    return text.replace("/var/lib/scratch", str(top / "state"))


def prologue_env(top: Path) -> dict:
    """The environment hook_prologue(top) runs in: stand-ins first on PATH for the freeze's two Linux tools, so that
    nothing is ever stopped here. `pgrep` answers that a process of the user runs until one freeze has been sent, and
    none after; `setpriv` runs nothing and adds its arguments to `top/trace`."""
    tools, trace = top / "freeze-tools", top / "trace"
    tools.mkdir(parents=True, exist_ok=True)
    (tools / "pgrep").write_text(f'#!/bin/sh\necho "pgrep $*" >> "{trace}"\ngrep -q "^setpriv " "{trace}" && exit 1\nexit 0\n')
    (tools / "setpriv").write_text(f'#!/bin/sh\necho "setpriv $*" >> "{trace}"\n')
    for tool in ("pgrep", "setpriv"):
        (tools / tool).chmod(0o755)
    return dict(os.environ, PATH=f"{tools}:{os.environ['PATH']}")


def test_reclaim_scratch_freezes_the_users_processes_before_anything_else(tmp_path):
    """QA 07f G1. Public connectivity is back shortly after the turn, so the user's processes are frozen at once: after
    its settings and its state directory, the hook's first act as the user is `kill -STOP -1`, repeated while any of
    them runs. Before it come only its mark and the end of the process the set-up hook left (round 12, third commit),
    neither of which runs anything as the user. Run as shipped, with the freeze's tools stood in."""
    top = tmp_path / "order"
    top.mkdir()
    (top / "prologue").write_text(hook_prologue(top))
    ran = subprocess.run(["sh", str(top / "prologue")], env=prologue_env(top), capture_output=True, text=True, timeout=30)
    assert ran.returncode == 0 and ran.stdout == "" and ran.stderr == "", ran
    trace = (top / "trace").read_text().splitlines()
    assert trace == ["pgrep -u dev -r R,S", "setpriv --reuid dev --regid dev --clear-groups kill -STOP -1", "pgrep -u dev -r R,S"], trace
    hook = (TASK / "environment" / "reclaim-scratch").read_text()
    start, freeze = 'mkdir -p "$STATE" && chmod 0700 "$STATE"\n', "for _ in $(seq 1 100); do\n  pgrep -u dev -r R,S >"
    steps = [start, freeze, "--clear-groups kill -STOP -1 >", "ps -eo pid=", "timeout 120 setpriv"]
    assert [hook.index(step) for step in steps] == sorted(hook.index(step) for step in steps), "the freeze, then the rest"
    between = hook[hook.index(start) + len(start):hook.index(freeze)]
    code = [line.strip() for line in between.splitlines() if not line.lstrip().startswith("#")]
    assert code[0] == ': > "$STATE/collect-began"' and 'kill -KILL -- "-$holder"' in between, code
    assert "setpriv" not in between and "python3" not in between and "pgrep" not in between, "nothing as the user before the freeze"


def test_nothing_ends_the_session_before_the_agents_limit():
    """Round 12 (harbor-lh ops/swe-marathon-v2/decisions/2026-11-24-timer-round3-flat-bundles-DECISION.md). The verdict
    rejects any stop the task makes before the agent's limit: v2's timer at 660 s before it, v4's at 60 s. The session
    timer is gone: its script, its setup hook, the image's lines for it and every mention in what ships; every agent
    limit is 34,560 s again, with no comment. A session that runs to its limit is bounded after the fact instead
    (test_a_capped_turn_counts_nothing_written_after_its_end)."""
    import tomllib
    assert not (TASK / "environment" / "session-timer").exists()
    toml = (TASK / "task.toml").read_text()
    config = tomllib.loads(toml)
    assert [config["agent"]["timeout_sec"], *(step["agent"]["timeout_sec"] for step in config["steps"])] == [34560, 34560]
    assert "#" not in toml and config["agent"]["setup_complete"] == [{"command": "/usr/local/sbin/provision-scratch", "timeout_sec": 120}]
    ours = [TASK / "task.toml", *sorted(path for path in (TASK / "environment").iterdir() if path.is_file()), HARDENING / "mark.py",
            HARDENING / "smoke.sh", STEP / "instruction.md", STEP / "solution" / "solve.sh", STEP / "tests" / "test.sh",
            STEP / "tests" / "Dockerfile", STEP / "tests" / "verify.py", *sorted((STEP / "tests" / "verifier").glob("*.py"))]
    named = re.compile(r"session.timer|maintenance timer|\btimer\b|ended_by_timer|timer_log|33,?9[06]0|reclaiming", re.I)
    found = {path.relative_to(TASK).as_posix(): named.findall(path.read_text()) for path in ours}
    assert not any(found.values()), {name: words for name, words in found.items() if words}


# ---------------------------------------------------------------- the stop after the limit (round 12, fourth commit)

HOLD = (" -I - hold", "provision-scratch hold")  # what `ps` shows of the process the set-up hook leaves (the second:
# before this commit), whatever the interpreter's path


def holder_alive(pid: int | None, wait: float = 0) -> bool:
    """Whether `pid` is the process the set-up hook leaves (`python3 -I - hold`), still there after `wait` s."""
    until = time.monotonic() + wait
    while True:
        args = subprocess.run(["ps", "-ww", "-o", "args=", "-p", str(pid)], capture_output=True, text=True).stdout if pid else ""
        if not any(mark in args for mark in HOLD) or time.monotonic() >= until:
            return any(mark in args for mark in HOLD)
        time.sleep(0.05)


def holder_started(state: Path, earlier: int | None = None, wait: float = 5) -> int:
    """The pid of the process a run of provision-scratch left, once it is named (another than `earlier`) and runs."""
    until = time.monotonic() + wait
    while time.monotonic() < until:
        text = (state / "holder.pid").read_text().strip() if (state / "holder.pid").exists() else ""
        if text.isdigit() and int(text) != earlier and holder_alive(int(text)):
            return int(text)
        time.sleep(0.05)
    raise AssertionError("no process was left by the set-up hook")


def end_holder(state: Path) -> None:
    """Ends the process the set-up hook left, after a check that failed half-way."""
    text = (state / "holder.pid").read_text().strip() if (state / "holder.pid").exists() else ""
    if text.isdigit() and holder_alive(int(text)):
        for target in (-int(text), int(text)):
            try:
                os.kill(target, signal.SIGKILL)
            except OSError:
                pass


STAMP = "$(perl -MTime::HiRes=time -e 'printf \"%.3f\", time')"
TICKS = os.sysconf("SC_CLK_TCK")
ME, MY_UID = __import__("pwd").getpwuid(os.getuid()).pw_name, os.getuid()


class FakeProc:
    """A stand-in for the /proc the set-up hook's process reads: `uptime`, which the check moves on at will, and for
    each process its `status` (user ids) and `stat` (its parent, field 4, and its start in clock ticks since boot,
    field 22). Starts with a root process 1 and the root `su` 40 the agent's exec runs under."""

    def __init__(self, top: Path, uptime: float):
        self.root = top / "proc"
        self.root.mkdir(parents=True)
        self.at(uptime)
        self.process(1, 0, 0, 1.0)
        self.process(40, 0, 1, 900.0)

    def at(self, uptime: float) -> None:
        (self.root / "uptime.new").write_text(f"{uptime:.2f} 1.00\n")
        os.replace(self.root / "uptime.new", self.root / "uptime")

    def process(self, pid: int, uid: int, parent: int, start: float) -> None:
        base = self.root / str(pid)
        base.mkdir()
        (base / "status").write_text(f"Name:\tworker\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\n")
        rest = f"S {parent} {pid} {pid} 0 -1 4194304 0 0 0 0 0 0 0 0 20 0 1 0 {round(start * TICKS)} 0 0"
        (base / "stat.new").write_text(f"{pid} (worker one) {rest}\n")  # a name with a space and parentheses' worth
        os.replace(base / "stat.new", base / "stat")


def setup_hook(top: Path, proc: Path | None, stand_ins: dict[str, str], hosts: tuple = (), port: int = 443,
               old_limit: int | None = None) -> tuple[Path, dict]:
    """provision-scratch as shipped, its state directory moved into `top`, its process reading `proc` as /proc, run by
    this Python as this machine's user, watching `hosts` at `port` (none by default: nothing goes to the network),
    with short sleeps; and the environment it runs in, `stand_ins` (name: shell body) first on PATH, with `setsid`
    (macOS has none), `fallocate` (an empty room) and GNU `stat -f -c` stood in. `old_limit` sets the limit of a
    set-up hook from before round 12's fourth commit, which counted from the set-up run's own time."""
    state, tools = top / "state", top / "bin"
    tools.mkdir(parents=True)
    text = (TASK / "environment" / "provision-scratch").read_text().replace("/var/lib/scratch", str(state))
    text = text.replace("/usr/bin/python3", sys.executable).replace('"/proc", "dev"', f'"{proc or top / "no-proc"}", "{ME}"')
    text = text.replace('HOSTS, PORT, CONNECT_SECONDS = ("pypi.org", "github.com"), 443, 0.3', f"HOSTS, PORT, CONNECT_SECONDS = {hosts!r}, {port}, 0.3")
    text = text.replace("POLL_SECONDS, STEP_SECONDS = 0.5, 30", "POLL_SECONDS, STEP_SECONDS = 0.05, 0.1")
    if old_limit is not None:
        text = text.replace("LIMIT_SECONDS=34560\n", f"LIMIT_SECONDS={old_limit}\n")
    (top / "provision-scratch").write_text(text)
    bodies = {"setsid": f'exec "{sys.executable}" -c "import os, sys; os.setsid(); os.execvp(sys.argv[1], sys.argv[1:])" "$@"\n',
              "fallocate": ': > "$3"\n', "stat": 'echo "2500000 4096 1300000"\n', **stand_ins}
    for name, body in bodies.items():
        (tools / name).write_text("#!/bin/sh\n" + body)
        (tools / name).chmod(0o755)
    return top / "provision-scratch", dict(os.environ, PATH=f"{tools}:{os.environ['PATH']}")


def stamped(trace: Path) -> list[tuple[float, str]]:
    return [(float(line.split(" ", 1)[0]), line.split(" ", 1)[1]) for line in trace.read_text().splitlines()] if trace.exists() else []


def traced(trace: Path) -> dict[str, str]:
    """Stand-ins for the stop's two tools that only write their calls, with the time, to `trace`: `pgrep -r` finds a
    process running until a stop has been sent, and `pgrep` alone always one."""
    return {"pgrep": f'echo "{STAMP} pgrep $*" >> "{trace}"\ncase "$*" in *"-r R,S,D"*) grep -q " setpriv " "{trace}" && exit 1; '
                     f'echo 4242; exit 0 ;; esac\necho 4242\n',
            "setpriv": f'echo "{STAMP} setpriv $*" >> "{trace}"\n'}


def set_up(top: Path, proc: FakeProc | None, trace: Path, **kwargs) -> tuple[Path, int]:
    """Runs provision-scratch as the last set-up run does; its state directory and the pid of the process it left."""
    script, env = setup_hook(top, proc.root if proc else None, traced(trace), **kwargs)
    done = subprocess.run(["sh", str(script)], env=env, capture_output=True, text=True, timeout=60)
    assert done.returncode == 0 and done.stdout == "" and done.stderr == "", done
    state = top / "state"
    return state, holder_started(state)


def test_the_stop_after_the_limit_counts_from_the_sessions_first_process_even_tens_of_seconds_after_set_up(tmp_path):
    """OB-1 of the re-check of option B (harbor-lh `ops/swe-marathon-v2/qa/basedpl/08-recheck-v3.md`): harbor starts the
    agent's clock after the set-up hook and a network-policy call, and pauses it while a trial is paused, so a stop
    timed from the set-up run's clock can land before the limit. The process now counts from the start of the
    session's first process, the first process of the user to begin after it whose parent is not the user's, read
    from /proc in seconds since boot, and acts LIMIT_SECONDS + 2 s after that, never sooner. Against a stand-in /proc
    whose clock this check moves: a process of the user from before set-up and the child of another of the user's
    are passed over; the first process starts 30 s after set-up; at its start + 34,561.5 s nothing is sent, at
    + 34,562.05 s the stop comes, and its record names the process."""
    trace, proc = tmp_path / "trace", FakeProc(tmp_path / "t", 1000.0)
    proc.process(50, MY_UID, 40, 990.0)  # set-up's: began before the set-up hook's process
    state, holder = set_up(tmp_path / "t", proc, trace)
    try:
        time.sleep(0.5)  # the process has read its own start
        proc.process(60, MY_UID, 50, 1010.0)  # forked after set-up by set-up's own process of the user
        proc.at(1029.0)
        time.sleep(0.5)
        proc.process(70, MY_UID, 40, 1030.0)  # the session's first process, under root's su
        proc.process(80, MY_UID, 70, 1031.0)
        proc.at(1031.5)
        time.sleep(0.5)
        assert not stamped(trace), "nothing before the end"
        due = 1030.0 + 34560 + 2
        proc.at(due - 0.5)
        time.sleep(1.0)
        assert not stamped(trace) and holder_alive(holder), "nothing at the first process's start + 34,561.5 s"
        proc.at(due + 0.05)
        until = time.monotonic() + 10
        while time.monotonic() < until and not (state / "stopped").exists():
            time.sleep(0.05)
        record = json.loads((state / "stopped").read_text())
        assert record["first_process"] == 70 and record["network_watched"] is False and record["rounds"] == 1, record
        assert (record["processes"], record["still_running"]) == (1, 0) and record["at"] >= record["due"] - 0.2, record
        assert [call for _, call in stamped(trace) if call.startswith("setpriv")] == ["setpriv --reuid " + ME + " --regid " + ME +
                                                                                    " --clear-groups kill -STOP -1"]
        assert not holder_alive(holder, wait=2), "it exits once it has stopped them"
    finally:
        end_holder(state)


def test_the_stop_after_the_limit_does_nothing_without_a_first_process(tmp_path):
    """OB-1: with no process of the user beginning after set-up (a no-op agent, or one whose first process is gone
    before it is seen and leaves none), the process has nothing to count from and does nothing at all, however long,
    until the collect hook has begun; then it exits. (A set-up hook from before this commit counted from its own
    time: with a limit of 0 there, it would have stopped within 3 s.)"""
    trace, proc = tmp_path / "trace", FakeProc(tmp_path / "t", 1000.0)
    proc.process(50, MY_UID, 40, 990.0)  # set-up's
    proc.process(60, MY_UID, 50, 1001.0)  # its child
    state, holder = set_up(tmp_path / "t", proc, trace, old_limit=0)
    try:
        proc.at(1000.0 + 34562 * 3)
        time.sleep(5)
        assert not stamped(trace) and not (state / "stopped").exists() and holder_alive(holder), "no action"
        (state / "collect-began").write_text("")
        assert not holder_alive(holder, wait=2) and not stamped(trace), "it exits once the collect hook has begun"
    finally:
        end_holder(state)


def test_the_stop_after_the_limit_waits_for_the_network_where_it_can_be_watched(tmp_path):
    """OB-1, the later of the two anchors: the network comes back when harbor ends the session's network policy, which
    a paused clock delays too. Where the network can be watched (the hosts resolved at set-up), the stop waits, past
    the first process's start + 34,562 s, until one of them answers. A local port stands in for the hosts: closed
    past the due time, nothing is sent; once it listens, the stop comes."""
    trace, proc = tmp_path / "trace", FakeProc(tmp_path / "t", 1000.0)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    state, holder = set_up(tmp_path / "t", proc, trace, hosts=("127.0.0.1",), port=port)
    listener = socket.socket()
    try:
        time.sleep(0.5)
        proc.process(70, MY_UID, 40, 1010.0)
        time.sleep(0.5)
        proc.at(1010.0 + 34562 + 5)
        time.sleep(1.5)
        assert not stamped(trace), "the network has not come back: nothing is sent"
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", port))
        listener.listen(8)
        back = time.time()
        until = time.monotonic() + 10
        while time.monotonic() < until and not (state / "stopped").exists():
            time.sleep(0.05)
        record = json.loads((state / "stopped").read_text())
        assert record["network_watched"] is True and record["network_back"] >= back - 0.5 and record["at"] >= record["network_back"], record
    finally:
        listener.close()
        end_holder(state)


# Shell processes the stop must leave stopped, each with WORD in its command line ($0). A forker whose subshells are
# forked 20 ms apart, and two that wake each other with SIGCONT whenever they run, each reading the other's pid once.
FORKER = 'i=0; while [ "$i" -lt 20 ]; do (while :; do sleep 0.01; done) & i=$((i + 1)); sleep 0.02; done; while :; do sleep 0.01; done'
BUSY = "while :; do sleep 0.01; done"
CONTINUER = 'while [ ! -s "$1" ]; do sleep 0.01; done; peer=$(cat "$1"); while :; do kill -CONT "$peer" 2>/dev/null; sleep 0.005; done'


def test_the_stop_after_the_limit_reaches_forked_setsid_and_continuing_processes(tmp_path):
    """Option B's stop repeats `kill -STOP -1` as the user until no process of the user runs (R, S, D), so that what is
    forked meanwhile, a process in a session of its own, and two that send each other SIGCONT are all left stopped; it
    never ends any. The user's processes are stood in by this machine's own, picked by a random word in their command
    lines: the stand-in for `kill -STOP -1` stops those one after another (`pkill -STOP -f`), and the stand-in for
    `pgrep -r R,S,D` finds those not stopped. The session's first process is stood in in /proc, and its due time
    passed at once."""
    word = f"qa{uuid.uuid4().hex[:10]}"
    pattern = f"[{word[0]}]{word[1:]}"  # matches the processes, never the grep or pkill that looks for them
    listing = f'ps -axo pid=,stat=,command= | grep -- "{pattern}"'
    top, procs, proc = tmp_path / "t", [], FakeProc(tmp_path / "t", 1000.0)
    script, env = setup_hook(top, proc.root, {
        "pgrep": f'case "$*" in *"-r R,S,D"*) {listing} | awk \'$2 !~ /^[TZ]/ {{print $1; found = 1}} END {{exit !found}}\' ;; '
                 f'*) {listing} | awk \'$2 !~ /^Z/ {{print $1}}\' ;; esac\n',
        "setpriv": f'case "$*" in *"kill -STOP -1") pkill -STOP -f -- "{pattern}" ;; esac\nexit 0\n'})
    state = top / "state"
    peers = [tmp_path / "a.pid", tmp_path / "b.pid"]
    try:
        procs.append(subprocess.Popen(["sh", "-c", FORKER, word], start_new_session=True))
        procs.append(subprocess.Popen([str(top / "bin" / "setsid"), "sh", "-c", BUSY, word]))  # a session of its own
        procs += [subprocess.Popen(["sh", "-c", CONTINUER, word, str(peer)], start_new_session=True) for peer in (peers[1], peers[0])]
        peers[0].write_text(str(procs[2].pid))
        peers[1].write_text(str(procs[3].pid))
        done = subprocess.run(["sh", str(script)], env=env, capture_output=True, text=True, timeout=60)
        assert done.returncode == 0, done
        holder_started(state)
        time.sleep(0.5)
        proc.process(70, MY_UID, 40, 1001.0)
        time.sleep(0.5)
        proc.at(1001.0 + 34562 + 1)  # the forker's subshells are all there by now
        until = time.monotonic() + 30
        while time.monotonic() < until and not (state / "stopped").exists():
            time.sleep(0.1)
        states = subprocess.run(["sh", "-c", f'{listing} | awk \'{{print $2}}\''], capture_output=True, text=True).stdout.split()
        assert len(states) >= 24 and all(state_.startswith(("T", "Z")) for state_ in states), states
        record = json.loads((state / "stopped").read_text())
        assert record["rounds"] >= 1 and record["still_running"] == 0, record
        assert record["processes"] == sum(1 for state_ in states if not state_.startswith("Z")), record
        assert all(proc_.poll() is None for proc_ in procs), "stopped, never ended"
    finally:
        end_holder(state)
        subprocess.run(["pkill", "-KILL", "-f", "--", pattern], capture_output=True)
        for proc_ in procs:
            proc_.wait(timeout=10)


def test_the_stop_after_the_limit_ends_once_the_collect_hook_has_begun(tmp_path):
    """Option B: once the collect hook has begun, the process the set-up hook left stops nothing and exits; the hook
    writes its mark first, then ends that process, before it runs anything as the user. The process alone sees the
    mark too: with the mark there from the start, or once its stop is due, it stops nothing and records nothing."""
    trace = tmp_path / "trace"
    top, proc = tmp_path / "hooked", FakeProc(tmp_path / "hooked", 1000.0)
    state, holder = set_up(top, proc, trace)
    try:
        hook = (TASK / "environment" / "reclaim-scratch").read_text()
        start = hook[:hook.index("# Freeze every process of the unprivileged user next")].replace("/var/lib/scratch", str(state))
        (top / "start").write_text(start)
        ran = subprocess.run(["sh", str(top / "start")], capture_output=True, text=True, timeout=30)
        assert ran.returncode == 0 and ran.stderr == "", ran
        assert (state / "collect-began").exists() and not holder_alive(holder, wait=2), "the hook ends it"
    finally:
        end_holder(state)
    for name in ("mark first", "mark when due"):
        top, proc = tmp_path / name.replace(" ", "-"), FakeProc(tmp_path / name.replace(" ", "-"), 1000.0)
        if name == "mark first":
            (top / "state").mkdir()
            (top / "state" / "collect-began").write_text("")
        script, env = setup_hook(top, proc.root, traced(trace))
        done = subprocess.run(["sh", str(script)], env=env, capture_output=True, text=True, timeout=60)
        assert done.returncode == 0, done
        state = top / "state"
        try:
            if name == "mark when due":
                holder = holder_started(state)
                time.sleep(0.5)
                proc.process(70, MY_UID, 40, 1001.0)
                time.sleep(0.5)
                (state / "collect-began").write_text("")
                proc.at(1001.0 + 34562 + 1)
            pid = int((state / "holder.pid").read_text())
            assert not holder_alive(pid, wait=2), name
        finally:
            end_holder(state)
    assert not stamped(trace) and not (tmp_path / "hooked" / "state" / "stopped").exists(), "nothing was stopped"


def test_both_hooks_run_whole_with_the_root_and_linux_tools_stood_in(tmp_path):
    """QA 07e F3: every shell line of provision-scratch and reclaim-scratch, as shipped, under `sh`, with only their
    absolute paths rewritten into a directory of the test's and, first on PATH, stand-ins for what needs root or Linux
    (after the reviewer's replay): setpriv drops its options and never runs a kill; pgrep and pkill find none of the
    user's processes; `ps -eo` prints a fixed listing; fallocate fails, so the fallback writes the room; GNU `stat -f
    -c` and `timeout` are stood in, and `setsid` (macOS has none); python3 is this Python with outbound connections
    refused. The session left both of the hook's own names, links for the fixer and a pipe. Each set-up run leaves the
    process that stops the user's processes after the limit in place of the earlier one; the hook ends the last."""
    top = tmp_path / "t"
    shims, rebuild, state = top / "bin", top / "app" / "rebuild", top / "state"
    for folder in (shims, rebuild, top / "tmp"):
        folder.mkdir(parents=True)
    (shims / "run_stdin.py").write_text(
        "import socket, sys\n\n\ndef refuse(address, timeout=None, *args, **kwargs):\n    raise ConnectionRefusedError(111, 'refused')\n\n\n"
        "socket.create_connection = refuse\nassert sys.argv[1:3] == ['-I', '-'], sys.argv\nsys.argv = ['-'] + sys.argv[3:]\n"
        "exec(compile(sys.stdin.read(), '<stdin>', 'exec'), {'__name__': '__main__', '__builtins__': __builtins__})\n")
    stand_ins = {
        "python3": f'exec "{sys.executable}" -I "{shims}/run_stdin.py" "$@"\n',
        "setpriv": 'for word in "$@"; do case "$word" in kill) exit 0 ;; esac; done\n'
                   'while [ $# -gt 0 ]; do case "$1" in --reuid|--regid) shift 2 ;; --clear-groups|--no-new-privs) shift ;; *) break ;; esac; done\n'
                   'exec "$@"\n',
        "pgrep": "exit 1\n",
        "pkill": "exit 1\n",
        "ps": 'case "$*" in "-ww -o args= -p "*) exec /bin/ps "$@" ;; esac\n'
              'printf "    1     0     0 100 /sbin/init\\n  777     1 10001  65 sleep 99\\n"\n',
        "setsid": f'exec "{sys.executable}" -c "import os, sys; os.setsid(); os.execvp(sys.argv[1], sys.argv[1:])" "$@"\n',
        "fallocate": "exit 1\n",
        "stat": 'echo "2500000 4096 1300000"\n',
        "timeout": 'shift\nexec "$@"\n',
    }
    for name, body in stand_ins.items():
        (shims / name).write_text("#!/bin/sh\n" + body)
        (shims / name).chmod(0o755)
    rewrites = [("/usr/bin/python3", f"{shims}/python3"), ("/app/.aside.XXXXXX", f"{top}/app/.aside.XXXXXX"), ("/app/rebuild", str(rebuild)),
                ("/var/lib/scratch", str(state)), ('"$STATE" /tmp "$PACK_SECONDS"', f'"$STATE" {top}/tmp "$PACK_SECONDS"'),
                ('"/proc", "dev"', f'"/proc", "{ME}"'), ('("pypi.org", "github.com"), 443, 0.3', "(), 443, 0.3")]
    setup_only = {'"/proc", "dev"', '("pypi.org", "github.com"), 443, 0.3'}  # the set-up hook's process: this user, no network
    for name in ("provision-scratch", "reclaim-scratch"):
        text = (TASK / "environment" / name).read_text()
        for old, new in rewrites:
            assert old in text or (name == "provision-scratch") != (old in setup_only), (name, old)  # each where it belongs
            text = text.replace(old, new)
        (top / name).write_text(text)
        for _, new in rewrites:
            text = text.replace(new, "")
        assert not any(place in text for place in ("/app/", "/var/", "/run/", "/usr/")), f"{name}: every absolute path is rewritten"
    hook_env = dict(os.environ, PATH=f"{shims}:{os.environ['PATH']}", LC_ALL="C")
    holders = []
    for _ in ("setup_begin", "setup_complete"):  # as task.toml runs it
        done = subprocess.run(["sh", str(top / "provision-scratch")], env=hook_env, capture_output=True, text=True, timeout=120)
        assert done.returncode == 0 and done.stdout == "" and done.stderr == "", done
        holders.append(holder_started(state, holders[-1] if holders else None))
    assert not holder_alive(holders[0]) and holder_alive(holders[1]), "the second run's process replaces the first's"
    assert (state / "room").stat().st_size == 64 << 20 and len(list((state / "inodes").iterdir())) == 64
    assert state.stat().st_mode & 0o777 == 0o700 and (state / "free-at-start").read_text() == "2500000 4096 1300000\n"
    turn_started = int((state / "turn-started").read_text())
    rebuild.chmod(0o777)
    (rebuild / "bpl").write_text("#!/bin/sh\necho hi\n")
    (rebuild / "bpl").chmod(0o755)
    (rebuild / "LICENSE").write_text("Apache License\n")
    (rebuild / "tools").mkdir()
    (rebuild / "tools" / "sh").symlink_to("/bin/sh")            # the machine's own: copied
    (rebuild / "abs").symlink_to(rebuild / "LICENSE")           # inside, absolute: made relative
    (rebuild / "gone").symlink_to("nowhere")                    # points at nothing: removed
    os.mkfifo(rebuild / "pipe")                                 # removed
    (rebuild / ".manifest").symlink_to("/etc/hosts")            # the hook's own two names, left by the session
    (rebuild / ".manifest.json").write_text('{"delivered": "delivered 999 999"}\n')
    ran = subprocess.run(["sh", str(top / "reclaim-scratch")], env=hook_env, cwd=top / "app", capture_output=True, text=True, timeout=300)
    assert not holder_alive(holders[1], wait=2), "the hook ends the process the set-up hook left"
    assert ran.returncode == 0 and ran.stderr == "", ran
    mark = [line.replace(str(top), "") for line in (rebuild / ".manifest").read_text().splitlines()]
    assert mark[0].startswith("delivered 5 ") and mark[1:] == [
        "tools/sh: a copy of /bin/sh (was a link to /bin/sh)", "removed pipe: not a file, a directory or a link",
        "removed gone -> nowhere: it points at nothing", "abs -> LICENSE (was /app/rebuild/LICENSE)",
        "moved .manifest out of /app/rebuild: this step writes a file of that name there",
        "moved .manifest.json out of /app/rebuild: this step writes a file of that name there"], mark
    assert ran.stdout.replace(str(top), "").splitlines() == mark[1:], "what the hook prints is the mark's notes"
    assert not (rebuild / ".manifest").is_symlink() and (rebuild / ".manifest").stat().st_mode & 0o777 == 0o644
    assert sorted(path.name for path in rebuild.iterdir()) == [".manifest", ".manifest.json", "LICENSE", "abs", "bpl", "tools"]
    assert (rebuild / "tools" / "sh").is_file() and not (rebuild / "tools" / "sh").is_symlink() and os.readlink(rebuild / "abs") == "LICENSE"
    aside = sorted(path for path in (top / "app").iterdir() if path.name.startswith(".aside."))
    assert sorted(item.name for folder in aside for item in folder.iterdir()) == [".manifest", ".manifest.json"], "moved, never followed"
    assert sorted(path.name for path in state.iterdir()) == ["aside.txt", "before.jsonl", "collect-began", "fixer.jsonl", "free-at-start",
                                                             "holder.pid", "holder.py", "prescan.json", "processes.txt", "session.json", "turn-started",
                                                             "writers.json", "writers.py"], \
        "the room and the spare inodes are given back"
    record = json.loads((rebuild / ".manifest.json").read_text())
    assert record["delivered"] == mark[0] and record["fixer_status"] == 0 and record["listing_complete"] is True, record["delivered"]
    assert [record["kill_rounds"], record["user_processes_left"], record["user_process_count"]] == [0, 0, 1]
    assert record["user_processes"][0]["command"] == "sleep 99" and record["connectivity_open"] is False
    assert set(record["connectivity"]) == {"pypi.org:443", "github.com:443"} and record["turn_started"] == turn_started
    assert record["hook_started"] >= turn_started and (record["work_end"], record["late_entries"]) == (turn_started + 34561, 0)


# ---------------------------------------------------------------- what a tree can do to the copy

def hook_scripts() -> dict[str, str]:
    """The Python scripts of environment/reclaim-scratch as shipped: what the frozen processes hold open for writing
    (from round 12's R1; a hook from before it has no such script), the times before anything, connectivity, the link
    fixer and the last script."""
    text = (TASK / "environment" / "reclaim-scratch").read_text()
    parts = [part.split("\nEOF\n", 1)[0] for part in text.split("<<'EOF'\n")[1:]]
    assert len(parts) in (4, 5), len(parts)
    return dict(zip(("writers", "prescan", "session", "fixer", "measure")[5 - len(parts):], parts))


def run_script(script: str, *args, prelude: str = "", env: dict | None = None, timeout: float = 300) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-I", "-", *map(str, args)], input=prelude + script, capture_output=True, text=True,
                          timeout=timeout, env=env)


# What the hook's first listing prints when no process of the user holds anything open for writing.
NOTHING_HELD = {"complete": True, "processes": 0, "held": [], "unread": [], "outside": 0}


def collected(top: Path, build, *, started_ago: float = 0, prelude: str = "", tar: str | None = None,
              start: str = "2500000 4096 1300000\n", state_files: dict | None = None, timeout: float = 300,
              times: dict | None = None) -> Path:
    """`build`'s tree in top/app/rebuild after the hook's scripts as they run there: the times before anything, then the
    last script, as if the step began `started_ago` seconds before it and the session 100 s before that (`build` may
    write another turn-started), its run's seconds going into `times["last"]`,
    with `prelude` run before it and `tar` (a shell
    body) first on its PATH. The link fixer does not run: one cut short, or ended at once by a chain of links, leaves
    the links it had not reached to the last script (`state_files` can give what it printed). By default the machine
    had room when the session began (`start`, its free blocks, block size and free inodes)."""
    scripts = hook_scripts()
    rebuild, state, archives = top / "app" / "rebuild", top / "state", top / "tmp"
    for folder in (rebuild, state, archives):
        folder.mkdir(parents=True)
    (state / "turn-started").write_text(f"{int(time.time() - started_ago) - 100}\n")  # 100 s before the step: well inside the limit
    (state / "writers.json").write_text(json.dumps(NOTHING_HELD))  # `build` may list what its processes hold
    (state / "free-at-start").write_text(start)
    for name, text in (state_files or {}).items():
        (state / name).write_text(text)
    env = dict(os.environ)
    if tar is not None:  # a stand-in for the copy's tar, first on the PATH
        (top / "bin").mkdir()
        (top / "bin" / "tar").write_text("#!/bin/sh\n" + tar)
        (top / "bin" / "tar").chmod(0o755)
        env["PATH"] = f"{top / 'bin'}:{env['PATH']}"
    build(rebuild)
    done = run_script(scripts["prescan"], rebuild, 100000, 1000, state)
    assert done.returncode == 0, done.stderr
    began = time.monotonic()
    done = run_script(scripts["measure"], rebuild, 100000, 1000000000, 1000, state, archives, 100, 0, 0,
                      int(time.time() - started_ago), 0, prelude=prelude, env=env, timeout=timeout)
    if times is not None:
        times["last"] = time.monotonic() - began
    assert done.returncode == 0, done.stderr
    assert not os.listdir(archives), "the trial pack is removed"
    return rebuild


def arrival(rebuild: Path, target: Path) -> tuple[str | None, list[str]]:
    """What reaches the verifier: the tree packed with tar and extracted with tarfile's data filter, as the copy does it
    (what was extracted before a member the filter refuses stays), and what the verifier's delivery_notes makes of it."""
    archive = target.parent / (target.name + ".tar")
    subprocess.run(["tar", "-cf", str(archive), "-C", str(rebuild), "."], check=True, capture_output=True, timeout=120,
                   env=dict(os.environ, COPYFILE_DISABLE="1"))  # macOS's tar would add ._ files for extended attributes
    target.mkdir()
    stopped = None
    try:
        with tarfile.open(archive) as bundle:
            bundle.extractall(target, filter="data")
    except (tarfile.TarError, OSError) as exc:
        stopped = type(exc).__name__
    return stopped, verifier_call(textwrap.dedent(f"""
        import json, verify
        from pathlib import Path
        try:
            print(json.dumps(verify.delivery_notes(Path({str(target)!r}))))
        except verify.EvaluationError as exc:
            print(json.dumps(["EVALUATION ERROR " + str(exc)]))
    """))


def test_a_link_that_climbs_past_the_root_is_kept_only_as_a_direct_one(tmp_path):
    """Carve QA 22 F5, here. The copy resolves a link from where it lands, where a `..` that stops at / in this sandbox
    climbs on. A link that climbs past / and back into the tree, in its own text or through a link that leads up, is
    inside here and outside there: the copy stopped at it and an honest delivery arrived short, an evaluation error
    ("the copy arrived incomplete") instead of a score. The link fixer makes every link it reaches direct, but the last
    script kept one it had not reached: under the image's Python 3.12 a chain of a thousand links ends the fixer at once
    (RecursionError, reproduced on 6a93903's hook). The last script now keeps a link that stays inside only as the
    direct relative path to what it reaches, and notes each one it made so; since round 11 it reads links by name
    against its own listing (QA 08 M1), so one that leads through another link is removed, with a note."""
    def build(rebuild):
        (rebuild / "bpl").write_text("#!/bin/sh\necho hi\n")
        root = os.path.realpath(rebuild)
        (rebuild / "zz").mkdir()
        (rebuild / "zz" / "x").symlink_to("../" * (root.count("/") + 2) + root.lstrip("/") + "/bpl")  # past /, then back in
        depth = root.count("/") + 1
        lower = rebuild.joinpath(*["d"] * depth)
        lower.mkdir(parents=True)
        (lower / "up").symlink_to("/".join([".."] * depth))  # leads up to the tree's own root, and is already direct
        (rebuild / "y").symlink_to("d/" * depth + "up/" + "../" * depth + root.lstrip("/") + "/bpl")  # lexically inside

    rebuild = collected(tmp_path / "climb", build)
    mark = (rebuild / ".manifest").read_text().splitlines()
    assert mark[0].startswith("delivered ") and len(mark) == 3, mark
    assert [line.split(" (was ")[0] for line in mark[1:] if " (was " in line] == ["zz/x -> ../bpl"], mark
    removed = [line for line in mark[1:] if line.startswith("removed ")]
    assert len(removed) == 1 and removed[0].startswith("removed y -> d/") and removed[0].endswith(": a link through another link, or to nothing")
    assert os.readlink(rebuild / "zz" / "x") == "../bpl" and not os.path.lexists(rebuild / "y"), "made direct; removed"
    record = json.loads((rebuild / ".manifest.json").read_text())
    made = {item["path"]: item for item in record["entries"] if item["path"] in ("y", "zz/x")}
    assert list(made) == ["zz/x"] and made["zz/x"]["target"] == "../bpl" and made["zz/x"]["hook_changed_ctime"], made
    stopped, notes = arrival(rebuild, tmp_path / "climb" / "copied")
    assert stopped is None and notes == [f"maintenance step: {line}" for line in mark[1:]], (stopped, notes)
    assert (tmp_path / "climb" / "copied" / "zz" / "x").read_text() == "#!/bin/sh\necho hi\n"


def test_a_tree_the_last_script_cannot_finish_in_time_is_refused_not_left_to_the_copy(tmp_path):
    """Carve QA 22 F3 and QA 23 N1, here. Every stage of the hook had a limit of its own but the last one: under the
    image's Python 3.12, os.path.realpath follows a chain one link at a time, so one realpath per link costs N²/2 links
    over a chain (6a93903's last script: 2,000 links 5.95 s, 4,000 24.4 s, 8,000 101.5 s on this Mac; ten chains of
    9,999 stay under the entry limit). The hook's 600 s then ran out before the mark, with the links the copy refuses
    still in the tree: "nothing arrived", an evaluation error, when such a link comes first. The last script now
    refuses a tree it has not measured within 420 s of the hook's start, and packs only by 510 s; the earlier stages'
    own limits leave it that time, or it refuses at once."""
    rebuild = collected(tmp_path / "late", lambda rebuild: (rebuild / "bpl").write_text("#!/bin/sh\n"), started_ago=10_000)
    mark = (rebuild / ".manifest").read_text().splitlines()
    assert mark == ["refused", "it could not be measured within 420 s: it was not copied"], mark
    assert json.loads((rebuild / ".manifest.json").read_text())["delivered"] == "refused"
    stopped, notes = arrival(rebuild, tmp_path / "late" / "copied")
    assert stopped is None and notes == [f"maintenance step: {mark[1]}"], (stopped, notes)
    rebuild = collected(tmp_path / "in-time", lambda rebuild: (rebuild / "bpl").write_text("#!/bin/sh\n"), started_ago=400)
    assert (rebuild / ".manifest").read_text().splitlines() == ["delivered 1 10"], "a start 400 s ago is still in time"
    hook, measure = (TASK / "environment" / "reclaim-scratch").read_text(), hook_scripts()["measure"]
    assert "MEASURE_UNTIL, PACK_UNTIL = 420, 510" in measure and "STARTED = HOOK_STARTED if HOOK_STARTED > 0 else" in measure
    assert "seconds = min(PACK_SECONDS, STARTED + PACK_UNTIL - time.time())" in measure and "timeout=seconds)" in measure
    assert measure.count("in_time()") == 3, "defined once, then called for every entry the walk lists and for every link"
    import tomllib
    limit = tomllib.loads((TASK / "task.toml").read_text())["verifier"]["collect"][0]["timeout_sec"]
    earlier = [int(value) for value in re.findall(r"^\s*timeout (\d+) ", hook, re.M)]  # R1's two listings, then the rest
    assert earlier == [30, 30, 300, 30, 120] and sum(earlier) + 60 < limit == 600 and 510 + 60 <= limit, (earlier, limit)


def test_the_link_fixer_copies_only_with_room_to_spare(tmp_path):
    """Carve QA 22 F4 (a), here. The room and the inodes setup sets aside are given back before the link fixer, so that
    the record, the mark and the copy's own pack can be written however full the session left the disk. The fixer
    copied a link's root-owned target with no regard to the disk: on a disk the session had filled, the copy took that
    room, and the last script then could not write its record or make the empty directory a refusal needs ("nothing
    arrived"). It copies now only when the disk keeps twice the copy's bytes and 64 MiB, and its entries and 64 inodes,
    to spare, and otherwise removes the link with a note."""
    fixer = hook_scripts()["fixer"]
    full = ("import os\nclass Full:\n    f_bavail = f_favail = 0\n    f_frsize, f_blocks, f_files = 4096, 1000000, 1000000\n"
            "os.statvfs = lambda path: Full()\n")
    results = {}
    for name, prelude in (("room", ""), ("full", full)):
        tree = tmp_path / name / "rebuild"
        (tree / "tools").mkdir(parents=True)
        (tree / "tools" / "sh").symlink_to("/bin/sh")  # part of the machine's installation
        done = run_script(fixer, tree, 100000, 1000000000, prelude=prelude)
        assert done.returncode == 0, done.stderr
        changes = [json.loads(line) for line in done.stdout.splitlines()]
        results[name] = [[change["kind"] for change in changes], os.path.lexists(tree / "tools" / "sh"), changes[0]["note"]]
    assert results["room"][:2] == [["copied"], True] and not os.path.islink(tmp_path / "room" / "rebuild" / "tools" / "sh"), results
    assert results["full"] == [["refused"], False, "removed tools/sh -> /bin/sh: the disk has no room to spare for a copy of it"], results
    assert "KEEP_BYTES, KEEP_INODES = 64 << 20, 64" in fixer and "fallocate -l 64M" in (TASK / "environment" / "provision-scratch").read_text()


def test_the_hook_names_a_bounded_number_of_changes_and_counts_the_rest(tmp_path):
    """Carve QA 22 F1 and F4, here. Every change the hook made was a line of the link fixer's output, of the mark and of
    the record, without a bound: a tree of pipes, each one a note (about 98 bytes from the fixer), filled the room set
    aside for the last script on a full disk, and millions of them were memory it might not have. The fixer now prints
    10,000 changes and then how many more there were; the first and the last script name theirs while they take 64 KiB
    as written (round 11: bytes, not counts, QA 08 M2) and count the rest, and the mark's notes take 32 KiB. The
    verifier reads at most 1 MiB of the mark and decides on its first line, as before."""
    def pipes(count):
        def build(rebuild):
            for number in range(count):
                os.mkfifo(rebuild / f"p{number}")
        return build

    tree = tmp_path / "fixer" / "rebuild"
    tree.mkdir(parents=True)
    pipes(10_050)(tree)
    done = run_script(hook_scripts()["fixer"], tree, 100000, 1000000000)
    printed = done.stdout.splitlines()
    assert done.returncode == 0 and len(printed) == 10_001 and not any(tree.iterdir()), (done.returncode, len(printed))
    assert json.loads(printed[-1]) == {"kind": "more", "path": "", "note": "and 50 more changes of the link fixer"}
    rebuild = collected(tmp_path / "last", pipes(2_000))  # the pipes the fixer did not reach: the last script removes them
    record = json.loads((rebuild / ".manifest.json").read_text())
    named = [note for note in record["notes"] if note.startswith("removed p")]
    more = re.fullmatch(r"and ([\d,]+) more entries removed or relinked by this step", record["notes"][len(named)])
    assert more and len(named) + int(more.group(1).replace(",", "")) == 2_000, record["notes"][len(named)]
    assert sum(len(note.encode()) + 1 for note in named) <= 64 << 10, "its own notes take 64 KiB at most"
    mark = (rebuild / ".manifest").read_text().splitlines()
    assert mark[0] == "delivered 0 0" and re.fullmatch(r"and [\d,]+ more notes", mark[-1]), mark[-1]
    assert len("\n".join(mark[1:-1]).encode()) + 1 <= 32 << 10, "the mark's notes take 32 KiB at most"

    def locked(rebuild):
        for number in range(1_050):
            (rebuild / f"d{number}").mkdir(mode=0o555)

    rebuild = collected(tmp_path / "first", locked)
    prescan = json.loads((tmp_path / "first" / "state" / "prescan.json").read_text())
    more = re.fullmatch(r"and ([\d,]+) more entries made accessible to their owner", prescan["notes"][-1])
    assert more and len(prescan["notes"]) - 1 + int(more.group(1).replace(",", "")) == 1_050, prescan["notes"][-1]
    assert sum(len(json.dumps(note)) for note in prescan["notes"][:-1]) <= 64 << 10, "the first script's notes take 64 KiB at most"
    assert (rebuild / ".manifest").read_text().splitlines()[0] == "delivered 1050 0" and (rebuild / "d7").stat().st_mode & 0o777 == 0o755


def test_a_tree_the_disk_cannot_pack_beside_the_record_is_refused_and_its_record_lists_nothing(tmp_path):
    """Carve QA 22 F4 (b), here. The copy packs the tree into /tmp after this step has written its record beside it, but
    the last script's pack had proved room for the tree alone: a session that left the disk just full enough had its
    tree marked delivered, then the copy's pack failed ("nothing arrived"). The last script now refuses a tree the disk
    cannot pack beside twice its record and 16 MiB, when the machine had room at the start (when it never had, the copy
    is left to fail, the machine's fault). A refused tree's record counts its entries and lists none, so that it fits in
    the room set aside at setup however many there were."""
    small = ("import os\nclass Small:\n    f_bavail, f_frsize, f_favail, f_files, f_blocks = 256, 4096, 1000000, 2000000, 2000000\n"
             "os.statvfs = lambda path: Small()\n")  # 1 MiB free, inodes plenty

    def build(rebuild):
        (rebuild / "bpl").write_text("#!/bin/sh\necho hi\n")
        for number in range(40):
            (rebuild / f"f{number}").write_text("x" * 100)

    rebuild = collected(tmp_path / "small", build, prelude=small)
    mark = (rebuild / ".manifest").read_text().splitlines()
    assert mark == ["refused", "the disk has no room for the copy's pack of it beside this step's record: it was not copied"], mark
    record = json.loads((rebuild / ".manifest.json").read_text())
    assert record["delivered"] == "refused" and record["entries"] == [] and record["entries_not_listed"] == 41, record.get("entries_not_listed")
    assert sorted(path.name for path in rebuild.iterdir()) == [".manifest", ".manifest.json"]
    stopped, notes = arrival(rebuild, tmp_path / "small" / "copied")
    assert stopped is None and notes == [f"maintenance step: {mark[1]}"], (stopped, notes)
    rebuild = collected(tmp_path / "room", build)  # the control: the same tree on a disk with room
    assert (rebuild / ".manifest").read_text().splitlines() == [f"delivered 41 {18 + 40 * 100}"]


# A process of a session that ran to its limit, still running when the hook comes: it "fetches" a build once the network
# is back, swaps it in for the program, links to it, and keeps appending to a log until the hook's freeze and kill.
LATE_WRITER = textwrap.dedent("""
    import os, sys, time
    from pathlib import Path
    tree = Path(sys.argv[1])
    (tree / "fetched").mkdir()
    (tree / "fetched" / "upstream.tar").write_bytes(b"fetched after the end")
    (tree / "bpl").write_text("#!/bin/sh\\necho fetched\\n")
    os.symlink("fetched/upstream.tar", tree / "latest")
    print("fetched", flush=True)
    while True:
        with open(tree / "progress.log", "a") as log:
            log.write("still working\\n")
        time.sleep(0.05)
""")


def test_a_capped_turn_counts_nothing_written_after_its_end(tmp_path):
    """Round 12 (decision 2026-11-24, item 2). With no timer, a session that runs to the agent's limit (34,560 s) keeps
    its processes running until this hook freezes them, and the network is open again by then: a process can keep
    writing into /app/rebuild, and fetch. The end of the work is the session's start (turn-started, written at set-up)
    plus 34,560 s, and nothing is killed to enforce it: every file and link whose change time, as recorded before the
    hook touched anything, is later than that end is taken out, noted and counted (`late_entries`, `work_end`). Here a
    session's work is written, its end passes, and a process of it fetches, swaps the program, links and keeps
    writing, until it is killed as the hook's freeze and kill would."""
    when = {}

    def build(rebuild):
        (rebuild / "bpl").write_text("#!/bin/sh\necho mine\n")
        (rebuild / "src").mkdir()
        (rebuild / "src" / "main.py").write_text("print(1)\n")
        (rebuild / "notes.txt").write_text("in time\n")
        (rebuild / "progress.log").write_text("step 0\n")
        when["end"] = int(time.time()) + 1  # the end of the work falls between the work and what follows it
        (rebuild.parent.parent / "state" / "turn-started").write_text(f"{when['end'] - 34560 - 1}\n")
        while time.time() < when["end"] + 0.2:
            time.sleep(0.05)
        writer = subprocess.Popen([sys.executable, "-c", LATE_WRITER, str(rebuild)], stdout=subprocess.PIPE, text=True)
        try:
            assert writer.stdout.readline().strip() == "fetched"
            time.sleep(0.3)  # still writing
        finally:
            writer.kill()
            writer.wait(timeout=10)
            writer.stdout.close()

    rebuild = collected(tmp_path / "capped", build)
    mark = (rebuild / ".manifest").read_text().splitlines()
    late = sorted(line.split(":")[0].removeprefix("removed ") for line in mark[1:])
    assert mark[0] == f"delivered 4 {len('print(1)\n') + len('in time\n')}" and late == ["bpl", "fetched/upstream.tar", "latest", "progress.log"], mark
    assert all(line.endswith(": changed after the end of the work, 34560 s after the session began") for line in mark[1:]), mark
    assert sorted(str(path.relative_to(rebuild)) for path in rebuild.rglob("*")) == [".manifest", ".manifest.json", "fetched", "notes.txt",
                                                                                   "src", "src/main.py"]
    record = json.loads((rebuild / ".manifest.json").read_text())
    assert (record["work_end"], record["late_entries"]) == (when["end"], 4), (record["work_end"], record["late_entries"])
    stopped, notes = arrival(rebuild, tmp_path / "capped" / "copied")
    assert stopped is None and notes == [f"maintenance step: {line}" for line in mark[1:]], (stopped, notes)
    measure = hook_scripts()["measure"]
    assert "SESSION_SECONDS = 34560" in measure and "late_entries, held_entries = take_out_late()" in measure
    assert measure.index("late_entries, held_entries = take_out_late()") < measure.index('walk(top, "")'), "taken out before the walk counts"


def test_a_capped_turn_that_delivered_nothing_or_lost_its_listing(tmp_path):
    """Round 12. A session that ran to its limit with nothing in /app/rebuild is delivered as empty, never refused (its
    complete listing holds no entry); one whose listing from before the hook is missing or short is refused, since
    what changed after the end could not be told apart from the rest."""
    def ran_out(rebuild):
        (rebuild.parent.parent / "state" / "turn-started").write_text(f"{int(time.time()) - 34561 - 30}\n")

    empty = collected(tmp_path / "empty", ran_out)
    record = json.loads((empty / ".manifest.json").read_text())
    assert (empty / ".manifest").read_text() == "delivered 0 0\n" and record["late_entries"] == 0 and record["work_end"] < time.time()

    def kept(rebuild):
        ran_out(rebuild)
        (rebuild / "bpl").write_text("#!/bin/sh\n")

    lost = 'import os, sys\nos.remove(os.path.join(sys.argv[5], "before.jsonl"))\n'
    refused = collected(tmp_path / "lost", kept, prelude=lost)
    mark = (refused / ".manifest").read_text().splitlines()
    assert mark == ["refused", "the session ran to its limit, and the listing of what it changed before then is missing: it was not copied"], mark


def fake_proc(top: Path, processes: dict) -> Path:
    """A stand-in for /proc. `processes` maps a pid to its `uids` and `gids` (real, effective, saved, filesystem), its
    `command` (cmdline's bytes), its `maps` lines, and its `tasks`: for each thread, a descriptor table mapping each
    descriptor to (the file it holds, its open flags in octal), written as fd/N (a link to the file) and fdinfo/N, and
    the process's memory map as its own maps, as every live thread shows it. With `leader_exited`, the first thread
    has exited while others live: the process's maps and that thread's are empty. A process `unreadable` gives every
    maps of its mode 0, so that reading them fails as /proc refuses another user's; `unreadable_tasks`, those threads'."""
    proc = top / "proc"
    (proc / "self").mkdir(parents=True)  # a name that is not a process
    for pid, spec in processes.items():
        base = proc / str(pid)
        uids, gids = ("\t".join(map(str, spec[key])) for key in ("uids", "gids"))
        maps, exited = "".join(line + "\n" for line in spec.get("maps", [])), spec.get("leader_exited", False)
        (base / "task").mkdir(parents=True)
        (base / "status").write_text(f"Name:\tworker\nState:\tT (stopped)\nUid:\t{uids}\nGid:\t{gids}\n")
        (base / "cmdline").write_bytes(spec.get("command", b"worker\0--busy\0"))
        (base / "maps").write_text("" if exited else maps)
        for tid, table in spec.get("tasks", {pid: {}}).items():
            for part in ("fd", "fdinfo"):
                (base / "task" / str(tid) / part).mkdir(parents=True)
            (base / "task" / str(tid) / "maps").write_text("" if exited and tid == pid else maps)
            for fd, (target, flags) in table.items():
                os.symlink(target, base / "task" / str(tid) / "fd" / str(fd))
                (base / "task" / str(tid) / "fdinfo" / str(fd)).write_text(f"pos:\t0\nflags:\t{flags}\nmnt_id:\t25\n")
        for tid in spec.get("unreadable_tasks", []):
            (base / "task" / str(tid) / "maps").chmod(0)
        if spec.get("unreadable"):
            for name in [base / "maps", *sorted((base / "task").glob("*/maps"))]:
                name.chmod(0)
    return proc


def maps_line(path: Path, perms: str, dev: int | None = None, ino: int | None = None, shown: str | None = None) -> str:
    """One line of maps for `path`, with its own device and inode unless others are given, and the path shown."""
    info = os.stat(path)
    dev, ino = info.st_dev if dev is None else dev, info.st_ino if ino is None else ino
    return f"7f0000000000-7f0000001000 {perms} 00000000 {os.major(dev):02x}:{os.minor(dev):02x} {ino} {shown or path}"


def frozen(rebuild: Path, processes, *, capped: bool, user_run: bool = True) -> dict:
    """In a `build` for collected(): end the session's work now that its tree is written (`capped`: its end passes; else
    the session is still within its limit), then list what `processes(tree)` hold open for writing with the hook's
    script, against a stand-in /proc, as the hook does: as root, and again as the user when a process could not be
    read (`user_run`). Returns the first listing."""
    tree, state = Path(os.path.realpath(rebuild)), rebuild.parent.parent / "state"
    if capped:
        end = int(time.time()) + 1
        (state / "turn-started").write_text(f"{end - 34561}\n")
        while time.time() < end + 0.2:
            time.sleep(0.05)
    proc = fake_proc(rebuild.parent.parent, processes(tree))
    script = hook_scripts()["writers"]
    first = run_script(script, proc, tree, os.getuid(), os.getgid())
    assert first.returncode in (0, 3) and first.stderr == "", first
    (state / "writers.json").write_text(first.stdout)
    if first.returncode == 3 and user_run:
        again = run_script(script, proc, tree, os.getuid(), os.getgid())
        (state / "writers-user.json").write_text(again.stdout)
    return json.loads(first.stdout)


def test_a_capped_turn_takes_out_what_its_frozen_processes_held_open_for_writing(tmp_path):
    """R1 of the re-check of round 12 (harbor-lh `ops/swe-marathon-v2/qa/basedpl/08-recheck-v3.md`). With no timer, a
    capped turn's processes run on until the hook freezes them, with the network back, and a write through a shared
    writable mapping set up before the end can leave the change time as it was (tmpfs sets it on a page's first write
    fault only). So the hook lists, before the kill, what each process of the user holds open for writing (every task's
    descriptor table, with fdinfo's flags) or maps shared and writable (maps), and in a session that ran to its limit
    every name of each such file of the tree is taken out, noted and counted; nothing else is. Against a stand-in /proc:
    shared writable mappings matched by path (one with a hard link in the tree) and by device and inode (shown under a
    name outside the tree), a file open for appending, one open read-write through a name outside the tree, one in a
    thread's own table; and what must stay: a read-only descriptor, shared read-only and private writable mappings, a
    pipe, a root process's file. A process that ran a set-id program and cannot be read is recorded, not refused."""
    outside, seen = tmp_path / "elsewhere", {}
    outside.mkdir()

    def build(rebuild):
        files = {"bpl": "#!/bin/sh\necho mine\n", "notes.txt": "notes\n", "keep.txt": "keep\n", "mapped.bin": "M" * 64,
                 "shared.dat": "S" * 32, "deep/view.bin": "V" * 8, "log.txt": "log\n", "other.txt": "other\n",
                 "data/out.bin": "O" * 16, "src/main.py": "print(1)\n"}
        for name, text in files.items():
            (rebuild / name).parent.mkdir(parents=True, exist_ok=True)
            (rebuild / name).write_text(text)
        os.link(rebuild / "mapped.bin", rebuild / "data" / "alias.bin")  # a second name of a mapped file
        for name in ("data/out.bin", "deep/view.bin"):  # held through a name outside the tree
            os.link(rebuild / name, outside / Path(name).name)
        os.mkfifo(outside / "pipe")
        me, group = os.getuid(), os.getgid()
        seen["first"] = frozen(rebuild, lambda tree: {
            4242: {"uids": [me] * 4, "gids": [group] * 4,
                   "maps": [maps_line(tree / "mapped.bin", "rw-s"), maps_line(tree / "shared.dat", "rw-s", dev=os.makedev(0, 0), ino=7),
                            maps_line(tree / "deep" / "view.bin", "rw-s", shown=str(outside / "view.bin")),
                            maps_line(tree / "notes.txt", "r--s"), maps_line(tree / "keep.txt", "rw-p"),
                            maps_line(tree / "bpl", "rw-s", dev=os.makedev(0, 0), ino=8, shown=f"{tree / 'bpl'} (deleted)"),  # gone: not bpl
                            "7f0000002000-7f0000003000 rw-s 00000000 00:01 1029 /dev/zero (deleted)"],
                   "tasks": {4242: {3: (str(tree / "log.txt"), "0102001"), 4: (str(tree / "bpl"), "0100000"),
                                    5: (str(outside / "out.bin"), "02"), 6: (str(outside / "pipe"), "01")},
                             4243: {7: (str(tree / "src" / "main.py"), "0100001")}}},
            1: {"uids": [0] * 4, "gids": [0] * 4, "tasks": {1: {3: (str(tree / "other.txt"), "02")}}},
            4300: {"uids": [me] * 4, "gids": [group, 99, 99, 99], "unreadable": True, "command": b"/opt/bpl/bpl\0-e\0x\0"}},
            capped=True)

    rebuild = collected(tmp_path / "capped", build)
    mark = (rebuild / ".manifest").read_text().splitlines()
    held = {"data/alias.bin": "mapped shared and writable", "data/out.bin": "open for writing", "deep/view.bin": "mapped shared and writable",
            "log.txt": "open for writing", "mapped.bin": "mapped shared and writable", "shared.dat": "mapped shared and writable",
            "src/main.py": "open for writing"}
    assert sorted(mark[1:]) == sorted(f"removed {name}: a process of the session still had it {how} after the end of the work"
                                      for name, how in held.items()), mark
    assert sorted(str(path.relative_to(rebuild)) for path in rebuild.rglob("*") if path.is_file()) == [
        ".manifest", ".manifest.json", "bpl", "keep.txt", "notes.txt", "other.txt"]
    record = json.loads((rebuild / ".manifest.json").read_text())
    assert (record["late_entries"], record["held_for_writing"]) == (7, 7), "counted with the late entries, and apart"
    writers = record["writers"]
    assert writers["listed"] is True and writers["not_read_count"] == 1 and writers["not_read"][0]["pid"] == 4300
    assert writers["not_read"][0]["command"] == "/opt/bpl/bpl -e x" and writers["held"] == 2 * 7, writers  # both runs' entries
    first = seen["first"]
    assert first["complete"] is True and first["processes"] == 2 and first["outside"] == 1, first
    assert sorted(entry["how"] for entry in first["held"]) == ["mapped"] * 4 + ["open"] * 3, first["held"]  # the gone bpl's too
    assert {entry["pid"] for entry in first["held"]} == {4242}, "a thread's own table is its process's"
    stopped, notes = arrival(rebuild, tmp_path / "capped" / "copied")
    assert stopped is None and notes == [f"maintenance step: {line}" for line in mark[1:]], (stopped, notes)


def test_what_was_held_counts_only_after_a_capped_turn_and_a_hidden_process_refuses_one(tmp_path):
    """Round 12, R1. The listing changes nothing for a session that ended within its limit: what its processes held
    open is delivered as it stands, since nothing of it can be later than an end that has not come. A session that
    ran to its limit and whose processes held nothing of the tree loses nothing. One with a process that could be read
    neither as root nor as its user though every id of it is the user's (it made itself undumpable, so no listing
    shows what it maps) is refused, as is one whose listing is missing or incomplete."""
    me, group = os.getuid(), os.getgid()

    def tree_with(processes, capped, **kwargs):
        def build(rebuild):
            (rebuild / "bpl").write_text("#!/bin/sh\n")
            (rebuild / "log.txt").write_text("log\n")
            frozen(rebuild, processes, capped=capped, **kwargs)
        return build

    appending = lambda tree: {4242: {"uids": [me] * 4, "gids": [group] * 4, "tasks": {4242: {3: (str(tree / "log.txt"), "0102001")}}}}
    reading = lambda tree: {4242: {"uids": [me] * 4, "gids": [group] * 4, "tasks": {4242: {3: (str(tree / "log.txt"), "0100000")}}}}
    hidden = lambda tree: {4400: {"uids": [me] * 4, "gids": [group] * 4, "unreadable": True, "command": b"python3\0-c\0hold()\0"}}
    in_time = collected(tmp_path / "in-time", tree_with(appending, capped=False))
    record = json.loads((in_time / ".manifest.json").read_text())
    assert (in_time / ".manifest").read_text() == "delivered 2 14\n" and record["held_for_writing"] == 0 and record["writers"]["held"] == 1
    nothing = collected(tmp_path / "nothing", tree_with(reading, capped=True))
    assert (nothing / ".manifest").read_text() == "delivered 2 14\n", "a read-only descriptor takes nothing out"
    refused = {}
    refused["hidden"] = collected(tmp_path / "hidden", tree_with(hidden, capped=True))
    refused["no user run"] = collected(tmp_path / "no-user-run", tree_with(hidden, capped=True, user_run=False))
    lost = 'import os, sys\nos.remove(os.path.join(sys.argv[5], "writers.json"))\n'
    refused["lost"] = collected(tmp_path / "lost", tree_with(reading, capped=True), prelude=lost)
    cut_short = 'import json, os, sys\nopen(os.path.join(sys.argv[5], "writers.json"), "w").write(json.dumps({"complete": False, "why": "it was not done within 20 s"}))\n'
    refused["cut short"] = collected(tmp_path / "cut-short", tree_with(appending, capped=True), prelude=cut_short)
    marks = {name: (tree / ".manifest").read_text().splitlines() for name, tree in refused.items()}
    start = "the session ran to its limit, and "
    assert marks == {
        "hidden": ["refused", start + "its process 4400 (python3 -c hold()) could not be read for what it held open for writing: it was not copied"],
        "no user run": ["refused", start + "what its processes held open for writing could not be listed as their user: it was not copied"],
        "lost": ["refused", start + "what its processes held open for writing could not be listed: it was not copied"],
        "cut short": ["refused", start + "what its processes held open for writing could not be listed (it was not done within 20 s): "
                      "it was not copied"]}, marks


def test_a_thread_whose_leader_has_exited_is_read_and_an_unreadable_thread_counts(tmp_path):
    """R1a of the re-check of R1 (harbor-lh `ops/swe-marathon-v2/qa/basedpl/08-recheck-v3.md`). Once a process's first
    thread has exited (`pthread_exit`) while others live, /proc/PID/maps, the first thread's, is empty, and the others,
    sharing the memory map, show it at task/TID/maps. The listing reads every thread's maps, so a shared writable
    mapping that only such threads hold is listed and, after a capped turn, its file taken out; and a thread whose maps
    cannot be read leaves its process unread, as a process does (refused when its ids are all the user's)."""
    me, group = os.getuid(), os.getgid()

    def tree_with(processes):
        def build(rebuild):
            (rebuild / "bpl").write_text("#!/bin/sh\n")
            (rebuild / "kept.txt").write_text("kept\n")
            frozen(rebuild, processes, capped=True)
        return build

    exited = lambda tree: {5000: {"uids": [me] * 4, "gids": [group] * 4, "leader_exited": True,
                                  "maps": [maps_line(tree / "bpl", "rw-s")], "tasks": {5000: {}, 5001: {}}}}
    rebuild = collected(tmp_path / "exited", tree_with(exited))
    assert (rebuild / ".manifest").read_text().splitlines() == [
        "delivered 1 5", "removed bpl: a process of the session still had it mapped shared and writable after the end of the work"]
    thread = lambda tree: {5100: {"uids": [me] * 4, "gids": [group] * 4, "tasks": {5100: {}, 5101: {}}, "unreadable_tasks": [5101]}}
    refused = collected(tmp_path / "thread", tree_with(thread))
    assert (refused / ".manifest").read_text().splitlines() == [
        "refused", "the session ran to its limit, and its process 5100 (worker --busy) could not be read for what it held open for "
        "writing: it was not copied"]


def listing_order(folder: Path, names: list[str]) -> list[str]:
    """`names` in the order this filesystem lists them in `folder` (placeholders made and removed here): the order the
    walk meets them in, which a test cannot set."""
    for name in names:
        (folder / name).touch()
    order = [entry.name for entry in os.scandir(folder) if entry.name in names]
    for name in names:
        (folder / name).unlink()
    return order


def every_link_reached(rebuild: Path, leaves: int = 16_000) -> str:
    """QA 08 M1's tree, at this machine's 1,023-byte link targets: in a store directory, `leaves` links that each lead
    back to it through 199 pairs of `d/..`, then links whose targets pass through about 140 of them each, and, before
    the store in the listing, one link whose target passes through all of those. Python's realpath follows every link
    the last one meets; the system stops at 40 in a row. Returns the last link's name."""
    order = listing_order(rebuild, [f"n{number}" for number in range(16)])
    head, store = order[0], rebuild / order[-1]
    (store / "d").mkdir(parents=True)
    back = "d/.." + "/d/.." * 198
    for number in range(leaves):
        (store / f"l{number:05d}").symlink_to(back)
    per = 1_000 // len("l00000/")
    middles = [f"m{index:03d}" for index in range(-(-leaves // per))]
    for index, name in enumerate(middles):
        (store / name).symlink_to("/".join(f"l{number:05d}" for number in range(index * per, min(leaves, (index + 1) * per))))
    (rebuild / head).symlink_to("/".join([store.name, *middles]))
    (rebuild / "bpl").write_text("#!/bin/sh\n")
    return head


def test_no_one_link_holds_the_last_script_past_its_time(tmp_path):
    """QA 08 M1. The last script checked its time between links, never inside one, and resolved each link with
    os.path.realpath, which under the image's Python 3.12 follows every link a target meets, past the system's own
    limit of 40: one link whose resolution reaches every other one held it inside a single call past the hook's 600 s
    at the stated limits, and the copy then met the links as the session left them ("nothing arrived" when one of them
    climbs past / and comes first). The last script now reads every link by name against its own listing (nothing
    follows a link), and an alarm ends the walk and the links at 420 s, inside any call. Started 418 s after the hook,
    it refuses QA 08's tree within about two seconds; started at once, it finishes it, the long link removed."""
    measure = hook_scripts()["measure"]
    assert [line.strip() for line in measure.splitlines() if "realpath(" in line] == ["ROOT = os.path.realpath(sys.argv[1])"]
    assert measure.index("signal.setitimer(signal.ITIMER_REAL, max(0.001,") < measure.index("walk(top, \"\")") \
        < measure.index("signal.setitimer(signal.ITIMER_REAL, 0)") < measure.index("pack_once()\n    if failed is None")
    times = {}
    rebuild = collected(tmp_path / "late", every_link_reached, started_ago=418, timeout=120, times=times)
    mark = (rebuild / ".manifest").read_text().splitlines()
    assert mark[:2] == ["refused", "it could not be measured within 420 s: it was not copied"], mark[:3]
    assert times["last"] < 4, times  # 9433aa9's last script spends several seconds more inside the one link's realpath
    now = tmp_path / "now"
    head = []
    rebuild = collected(now, lambda rebuild: head.append(every_link_reached(rebuild, leaves=3_000)), timeout=120)
    mark = (rebuild / ".manifest").read_text().splitlines()
    assert mark[0].startswith("delivered ") and not os.path.lexists(rebuild / head[0]), mark[:3]
    record = json.loads((rebuild / ".manifest.json").read_text())
    assert any(note.startswith(f"removed {head[0]} -> ") and note.endswith("a link through another link, or to nothing")
               for note in record["notes"]), record["notes"][:3]


def test_the_link_fixer_lets_the_system_resolve_a_link_before_following_it(tmp_path):
    """QA 08 M1, in the link fixer: it resolved a link with os.path.realpath alone, which follows any number of links
    in a row (and under Python 3.12 ended the fixer with RecursionError on a chain of a thousand). It now asks the
    system first (os.stat, which stops at 40 links in a row, 32 on this Mac) and removes, with a note, a link the
    system does not resolve, so no one link costs it more than the system allows; and one entry it cannot fix no
    longer ends it."""
    tree = tmp_path / "chain" / "rebuild"
    (tree / "sub").mkdir(parents=True)
    (tree / "sub" / "end").write_text("x")
    (tree / "c0").symlink_to("sub/c1")
    for number in range(1, 50):
        (tree / "sub" / f"c{number}").symlink_to(f"c{number + 1}" if number < 49 else "end")
    fixer = hook_scripts()["fixer"]
    done = run_script(fixer, tree, 100000, 1000000000)
    changes = {change["path"]: change for change in map(json.loads, done.stdout.splitlines())}
    assert done.returncode == 0 and not os.path.lexists(tree / "c0"), changes.get("c0")
    assert changes["c0"]["kind"] == "removed" and "the system does not resolve it" in changes["c0"]["note"], changes["c0"]
    assert fixer.index("os.stat(path)  # the system's own resolution first") < fixer.index("resolved = os.path.realpath(path)")
    assert "except Exception as exc:  # one entry it cannot fix never ends the others" in fixer


def test_what_the_hook_writes_stays_far_inside_the_room_set_aside(tmp_path):
    """QA 08 M2. The caps counted notes, not bytes: with long names each of the fixer's lines held the name twice and
    the target (2.5 KB here, about 6 KB on Linux), so its 10,000 lines, the refused record (every change and note
    again) and the mark reached 87 MB on this Mac and 210-420 MB on Linux, against the 64 MiB setup sets aside for a
    full disk. Now every name and note is cut to a few hundred bytes, the fixer prints 2 MiB at most, the last script's
    own notes take 64 KiB and the mark's 32 KiB, a refused tree's record lists only the first notes and counts the
    rest, and the room check of a delivered tree counts the mark too. Here, at this machine's limits (1,000-byte link
    targets, paths of about 600 bytes), a refusal writes about 2 MiB in all."""
    deep = ["n" * 100] * 5
    tree = tmp_path / "fixer" / "rebuild"
    place = tree.joinpath(*deep)
    place.mkdir(parents=True)
    for number in range(3_000):
        os.symlink("x" * 1_000, place / f"{number:05d}{'y' * 100}")  # each points at nothing: removed, with a note
    done = run_script(hook_scripts()["fixer"], tree, 100000, 1000000000)
    printed = done.stdout.splitlines()
    assert done.returncode == 0 and len(done.stdout.encode()) <= (2 << 20) + 200, len(done.stdout.encode())
    assert re.fullmatch(r"and [\d,]+ more changes of the link fixer", json.loads(printed[-1])["note"]), printed[-1][:200]
    assert max(len(line) for line in printed) <= 1_600, "each name and note is cut"

    def pipes(rebuild):  # what the fixer did not reach: the last script removes them, with a note each
        folder = rebuild.joinpath(*deep)
        folder.mkdir(parents=True)
        for number in range(3_000):
            os.mkfifo(folder / f"{number:05d}{'p' * 100}")

    small = ("import os\nclass Small:\n    f_bavail, f_frsize, f_favail, f_files, f_blocks = 256, 4096, 1000000, 2000000, 2000000\n"
             "os.statvfs = lambda path: Small()\n")  # 1 MiB free: the tree is refused for want of room beside its record
    rebuild = collected(tmp_path / "last", pipes, prelude=small, state_files={"fixer.jsonl": done.stdout})
    mark = (rebuild / ".manifest").read_text().splitlines()
    assert mark[:2] == ["refused", "the disk has no room for the copy's pack of it beside this step's record: it was not copied"]
    sizes = [len(done.stdout.encode()), (rebuild / ".manifest").stat().st_size, (rebuild / ".manifest.json").stat().st_size]
    assert sizes[1] <= (32 << 10) + 1_000 and sizes[2] <= 1 << 20 and sum(sizes) <= 4 << 20, sizes
    record = json.loads((rebuild / ".manifest.json").read_text())
    assert record["links"] == record["entries"] == [] and record["links_not_listed"] >= 2_000 and record["notes_not_listed"] > 0, \
        {key: record[key] for key in ("links_not_listed", "notes_not_listed", "entries_not_listed")}
    fixer, measure = hook_scripts()["fixer"], hook_scripts()["measure"]
    assert "NOTE_LIMIT, PRINT_BYTES = 10_000, 2 << 20" in fixer and "NOTE_BYTES, MARK_BYTES = 64 << 10, 32 << 10" in measure
    assert "NOTE_BYTES = 64 << 10" in hook_scripts()["prescan"] and "packed + 2 * (kept + MARK_BYTES) + (16 << 20)" in measure
    assert (2 << 20) + 2 * (64 << 10) + (32 << 10) + (1 << 20) < 64 << 20, "the fixer, both scripts' notes, the mark, a refused record"


def test_the_freeze_and_the_kill_end_in_time_and_a_task_in_d_holds_neither(tmp_path):
    """QA 08 S1. The freeze repeated while any process of the user was running, sleeping or in D, up to 100 passes
    with no limit in time, and `dev` can hold a task in D (a parent waiting on a vfork child that the freeze itself
    stopped): every pass scans /proc, so the stretch before the set-aside of the hook's own names could grow. A task
    in D runs nothing of its own until it leaves D, and the kill ends it, so the freeze now asks for R and S only; and
    the freeze and the kill each stop after LOOP_SECONDS (15 s; 2 s here for a process that never stops), with a note.
    Run as shipped up to the count of what is left, with stand-ins for pgrep, setpriv, pkill and ps. (Round 12: the
    task in D runs with the shipped 15 s and a bound of 8 s, since stalls of this machine under other jobs' load wrote
    the note at 2 s, or took the run past the old bound of 3 s, in four runs of twelve.)"""
    hook = (TASK / "environment" / "reclaim-scratch").read_text()
    for mode in ("d", "running"):
        top = tmp_path / mode
        tools, trace = top / "bin", top / "trace"
        tools.mkdir(parents=True)
        stand_ins = {
            "pgrep": f'echo "pgrep $*" >> "{trace}"\nsleep 0.05\ncase "{mode}:$*" in\n  running:*) exit 0 ;;\n'
                     f'  d:*"R,S,D"*) grep -q "kill -9 -1" "{trace}" && exit 1; exit 0 ;;\nesac\nexit 1\n',
            "setpriv": f'echo "setpriv $*" >> "{trace}"\n', "pkill": "exit 1\n", "ps": 'echo "  777     1 10001  65 sleep 99"\n'}
        for name, body in stand_ins.items():
            (tools / name).write_text("#!/bin/sh\n" + body)
            (tools / name).chmod(0o755)
        text = hook[:hook.index("left=$(")].replace("/usr/bin/python3", sys.executable)  # (R1's listing, before the kill)
        if mode == "running":
            text = text.replace("LOOP_SECONDS=15", "LOOP_SECONDS=2")  # whole seconds, as date gives them
        text = text.replace("/var/lib/scratch", str(top / "state"))
        (top / "hook").write_text(text)
        began = time.monotonic()
        ran = subprocess.run(["sh", str(top / "hook")], env=dict(os.environ, PATH=f"{tools}:{os.environ['PATH']}"), capture_output=True,
                             text=True, timeout=10)
        spent, calls = time.monotonic() - began, trace.read_text().splitlines()
        loops = (top / "state" / "loops.txt").read_text().splitlines() if (top / "state" / "loops.txt").exists() else []
        assert ran.returncode == 0, ran
        if mode == "d":  # the task in D is not running: no freeze is sent, and the kill ends it
            assert calls[0] == "pgrep -u dev -r R,S" and not any("kill -STOP" in call for call in calls), calls[:4]
            assert sum("kill -9 -1" in call for call in calls) == 1 and loops == [] and spent < 8, (calls, loops, spent)
        else:  # a process that never stops: each loop gives up after its second, and says so
            assert loops == ["the freeze stopped after 2 s with a process of dev still running",
                             "the kill stopped after 2 s with a process of dev left"] and spent < 7, (loops, spent)
    assert "LOOP_SECONDS=15" in hook and "pgrep -u dev -r R,S >/dev/null" in hook


def test_a_name_that_is_not_utf8_keeps_the_listing_before_the_hook(tmp_path):
    """QA 08 S3. Linux allows any byte in a name, and Python reads one that is not UTF-8 as a lone surrogate, which the
    first script wrote raw into its UTF-8 record: the write raised, the listing before the hook was lost with every
    entry's own times, and a chmod that failed no longer refused. Both of its files are now written in ASCII, escapes
    and all. This Mac's filesystem refuses such a name, so the walk's listing and lstat are stood in for one entry."""
    not_utf8 = textwrap.dedent('''
        import os
        _scandir, _stat = os.scandir, os.stat
        ODD = b"odd\\xff".decode("utf-8", "surrogateescape")
        class _Odd:
            name = ODD
        class _Listing:
            def __init__(self, inner):
                self.inner = inner
            def __enter__(self):
                return self
            def __exit__(self, *exc):
                self.inner.close()
            def __iter__(self):
                yield from self.inner
                yield _Odd()
        os.scandir = lambda *args: _Listing(_scandir(*args))
        os.stat = lambda name, *args, **kwargs: _stat("bpl" if name == ODD else name, *args, **kwargs)
    ''')
    rebuild, state = tmp_path / "rebuild", tmp_path / "state"
    rebuild.mkdir()
    state.mkdir()
    (rebuild / "bpl").write_text("#!/bin/sh\n")
    done = run_script(hook_scripts()["prescan"], rebuild, 100000, 1000, state, prelude=not_utf8)
    assert done.returncode == 0, done.stderr[-500:]
    listed = [json.loads(line)["path"] for line in (state / "before.jsonl").read_text().splitlines()]
    assert sorted(listed) == ["bpl", b"odd\xff".decode("utf-8", "surrogateescape")], listed
    assert json.loads((state / "prescan.json").read_text())["complete"] is True and (state / "before.jsonl").read_text().isascii()


def test_a_filesystem_that_counts_no_inodes_is_judged_by_its_bytes(tmp_path):
    """QA 08 S4. The fixer counted inodes only where the filesystem reports them, but the last script did not: on one
    that reports none (f_files 0), every pack that failed counted as a disk short of inodes the machine never had, so
    the tree went on to the copy with only a note, the new refusal beside the record included. Both now leave out
    figures the filesystem does not give (sizes too), and the record keeps the disk's free figures as they read."""
    no_inodes = ("import os\nclass NoInodes:\n    f_bavail, f_frsize, f_blocks, f_favail, f_files = 0, 4096, 1000000, 0, 0\n"
                 "os.statvfs = lambda path: NoInodes()\n")
    failing = "echo 'tar: /tmp/x: Cannot write: No space left on device' >&2; exit 2\n"
    rebuild = collected(tmp_path / "no-inodes", lambda rebuild: (rebuild / "bpl").write_text("#!/bin/sh\n"), prelude=no_inodes,
                        tar=failing, start="2500000 4096 0\n")
    mark = (rebuild / ".manifest").read_text().splitlines()
    assert mark[0] == "refused" and "No space left on device" in mark[1], mark
    record = json.loads((rebuild / ".manifest.json").read_text())
    assert record["disk_free_bytes"] == 0 and record["disk_free_inodes"] is None, record


# ---------------------------------------------------------------- the whole evaluation, with root and Linux stood in

WHOLE_RUN = r'''
"""One evaluation through verify.main() itself, on a delivery the collect hook's own scripts marked and Harbor's
copy carried. Stand-ins only for what needs root or Linux, in verify's and runcases' namespaces: the effective uid
reads 0; chown and lchown demand integer ids, as the real calls do (a string raises TypeError before any system call),
and change nothing; setpriv is "found"; a command behind the privilege drop is answered as a correct unprivileged
Linux process would answer it (the set-id copy of id(1) with sys.argv[4]), or, for a case, started without the drop
once the drop's arguments are checked against the ids sandbox() returned; kill -1, ipcrm and find are counted, not
run; /logs and the verifier's own directory map into the scratch directory; writable_dirs() does not walk this
machine."""
import collections, json, os, shutil, subprocess, sys, tarfile
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
import verify
rc = verify.runcases
hook, base, set_id_answer, delivery = Path(sys.argv[2]).read_text(), Path(sys.argv[3]), sys.argv[4], sys.argv[5]
prefix = "" if delivery == "echo" else "w"  # "echo": each program prints its own code back, which never counts
prescan, measure = (hook.split("<<'EOF'\n")[n].split("\nEOF\n", 1)[0] for n in (2, 5))
agent, state, archives = base / "agent" / "app" / "rebuild", base / "agent" / "state", base / "agent" / "tmp"
for folder in (agent, state, archives, base / "tmp", base / "tmpdir", base / "tests" / "private", base / "v" / "app" / "rebuild",
               base / "logs" / "artifacts"):
    folder.mkdir(parents=True)
if delivery in ("program", "echo"):
    (agent / "bpl").write_text(f'#!/bin/sh\necho "{prefix}$2"\n')
    (agent / "bpl").chmod(0o755)
    (agent / "LICENSE").write_text("Apache License\n")
(state / "session.json").write_text(json.dumps({"checked_at": "2026-11-20T01:00:00Z", "connectivity": {"pypi.org:443": "closed (OSError)"},
                                                "connectivity_open": False, "user_process_count": 0, "user_processes": []}))
(state / "turn-started").write_text(f"{int(__import__('time').time()) - 100}\n")  # well inside the session's limit
for script, arguments in ((prescan, ["100000", "1000", str(state)]),
                          (measure, ["100000", "1000000000", "1000", str(state), str(archives), "100", "0", "0",
                                     str(int(__import__("time").time())), "0"])):
    done = subprocess.run([sys.executable, "-I", "-", str(agent), *arguments], input=script, capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stderr
copied = base / "v" / "app" / "rebuild"
subprocess.run(["tar", "-cf", str(base / "copy.tar"), "-C", str(agent), "."], check=True, capture_output=True, timeout=120,
               env=dict(os.environ, COPYFILE_DISABLE="1"))
with tarfile.open(base / "copy.tar") as bundle:
    bundle.extractall(copied, filter="data")
cases = [{"id": f"C{i}", "kind": kind, "argv": ["-e", str(i)], "files": {"main.bpl": "1\n"}, "stdin": None}
         for i, kind in enumerate(["expr", "expr", "script", "worker"] * 12)]  # 48 different outputs: a reward needs 40
(base / "tests" / "private" / "cases.json").write_text(json.dumps({"cases": cases}))
(base / "tests" / "private" / "expected.json").write_text(json.dumps({case["id"]: {"exit": 0, "stdout": prefix + case["argv"][1] + "\n"}
                                                                     for case in cases}))
(base / "tests" / "private" / "marker").write_text("0123456789abcdef0123456789abcdef\n")

RealPath = Path
events = {"chown": 0, "lchown_in_seal": 0, "lchown_in_prepare": 0, "not_run": collections.Counter(), "probes": [], "through_the_drop": 0,
          "sandbox": None}
STATUS = ("Name:\tpython3\nUid:\t{u}\t{u}\t{u}\t{u}\nGid:\t{u}\t{u}\t{u}\t{u}\nGroups:\t \nNoNewPrivs:\t1\nCapPrm:\t0000000000000000\n"
          "CapEff:\t0000000000000000\nCapBnd:\t000001ffffffffff\nCapAmb:\t0000000000000000\n")
LIMITS = ("Limit                     Soft Limit           Hard Limit           Units     \n"
          "Max file size             268435456            268435456            bytes     \n"
          "Max data size             274877906944         274877906944         bytes     \n"
          "Max stack size            8388608              8388608              bytes     \n"
          "Max core file size        0                    0                    bytes     \n"
          "Max processes             512                  512                  processes \n")
MAPPED = {"/logs/verifier": base / "logs" / "verifier", "/logs/artifacts": base / "logs" / "artifacts",
          str(RealPath(verify.__file__)): base / "tests" / "verify.py"}


def integers(*values):
    for value in values:
        if type(value) is not int:  # what os.chown and os.lchown do with anything else
            raise TypeError(f"an integer is required (got type {type(value).__name__})")


class StandIn:
    def __init__(self, real):
        self.__dict__["_real"] = real

    def __getattr__(self, name):
        return getattr(self._real, name)


class VerifyOs(StandIn):
    def geteuid(self):
        return 0

    def chown(self, path, uid, gid, **options):
        integers(uid, gid)
        events["chown"] += 1

    def lchown(self, path, uid, gid):
        integers(uid, gid)
        events["lchown_in_seal"] += 1

    def kill(self, pid, sig):
        raise AssertionError("the verifier signalled a process of this machine")


class VerifyShutil(StandIn):
    def which(self, name, *args, **options):
        return "/usr/bin/setpriv" if name == "setpriv" else self._real.which(name, *args, **options)


class VerifySubprocess(StandIn):
    def run(self, argv, **options):
        argv = [str(item) for item in argv]
        if argv[0] == "setpriv":
            assert argv[1] == "--reuid" and argv[3] == "--regid" and argv[5] == "--clear-groups", argv
            assert argv[2].isdigit() and argv[2] == argv[4], argv
            rest = argv[6:]
            while rest and rest[0] in ("--no-new-privs", "--"):
                rest = rest[1:]
            if rest[:1] in (["kill"], ["ipcrm"]):
                events["not_run"][" ".join(rest)] += 1
                return subprocess.CompletedProcess(argv, 0, stdout=b"", stderr=b"")
            if rest[:3] == [sys.executable, "-I", "-c"]:
                answer = STATUS.format(u=argv[2]) + "PrctlNoNewPrivs:\t1\n"
            elif rest == ["cat", "/proc/self/limits"]:
                answer = LIMITS
            elif len(rest) == 2 and rest[0].endswith("/.setid-probe/id") and rest[1] in ("-u", "-g"):
                assert os.stat(rest[0]).st_mode & 0o4000, "the probe file is set-id when it is run"
                answer = (argv[2] if set_id_answer == "own" else set_id_answer) + "\n"
            else:
                raise AssertionError(f"an unexpected command behind the drop: {rest}")
            events["probes"].append(" ".join(rest[-2:])[-24:])
            return subprocess.CompletedProcess(argv, 0, stdout=answer, stderr="")
        if argv[0] in ("find", "ipcrm"):
            events["not_run"][argv[0]] += 1
            return subprocess.CompletedProcess(argv, 0, stdout=b"", stderr=b"")
        if argv[:3] == ["chmod", "-R", "a+rX"] and argv[3].startswith(str(base)):
            return subprocess.run(argv, **options)
        raise AssertionError(f"an unexpected command from the verifier: {argv}")


class RunOs(StandIn):
    def lchown(self, path, uid, gid):
        integers(uid, gid)
        events["lchown_in_prepare"] += 1


class RunSubprocess(StandIn):
    def Popen(self, argv, **options):  # noqa: N802 - subprocess's own name
        argv = [str(item) for item in argv]
        if argv[0] == "setpriv":  # the drop itself cannot run here: its arguments are checked, then the command starts directly
            uid = events["sandbox"][1][0]
            assert argv[:7] == ["setpriv", "--reuid", str(uid), "--regid", str(uid), "--clear-groups", "--no-new-privs"], argv[:7]
            argv = argv[7:]
            events["through_the_drop"] += 1
        return subprocess.Popen(argv, **options)

    def run(self, argv, **options):
        argv = [str(item) for item in argv]
        assert argv[:3] == ["rm", "-rf", "--"] and len(argv) == 4 and argv[3].startswith(str(base / "tmp") + os.sep), argv
        return subprocess.run(argv, **options)


def path_stand_in(*parts):
    made = RealPath(*parts)
    return MAPPED.get(str(made), made)


real_sandbox = verify.sandbox


def sandbox_recorded():
    events["sandbox"] = real_sandbox()
    return events["sandbox"]


verify.os, verify.shutil, verify.subprocess, verify.Path = VerifyOs(os), VerifyShutil(shutil), VerifySubprocess(subprocess), path_stand_in
rc.os, rc.subprocess = RunOs(os), RunSubprocess(subprocess)
verify.sandbox = sandbox_recorded
verify.SUBMISSION, verify.MARKER = copied, base / "tests" / "private" / "marker"
verify.LEFTOVER_DIRS[:] = [str(base / "tmp")]
verify.writable_dirs = lambda root="/": []
verify.RESERVE_BYTES = 1 << 20  # this machine's free space is not what is checked here
verify.tempfile.tempdir = str(base / "tmpdir")
rc.WORKSPACE, rc.HOME, rc.TEMP = base / "tmp" / "bpl-run", base / "tmp" / "bpl-home", base / "tmp" / "bpl-tmp"
code = verify.main()
results = base / "logs" / "verifier"
metrics = json.loads((results / "metrics.json").read_text())
prefix, owner, limits = events["sandbox"] or ([], (), {})
print(json.dumps({"exit": code, "reward": (results / "reward.txt").read_text() if (results / "reward.txt").exists() else None,
                  "left": sorted(path.name for path in results.iterdir()), "metrics": metrics, "prefix": prefix, "owner": list(owner),
                  "owner_types": [type(value).__name__ for value in owner], "limits": limits,
                  "events": dict(events, not_run=dict(events["not_run"]), sandbox=None),
                  "probe_left": (copied.parent / ".setid-probe").exists(), "scratch": sorted(path.name for path in (base / "tmp").iterdir())}))
'''


def whole_run(tmp_path: Path, set_id_answer: str, delivery: str) -> dict:
    done = subprocess.run([sys.executable, "-B", "-c", WHOLE_RUN, str(STEP / "tests"), str(TASK / "environment" / "reclaim-scratch"),
                           str(tmp_path), set_id_answer, delivery], capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-3000:]
    lines = done.stdout.strip().splitlines()
    return dict(json.loads(lines[-1]), printed=lines[:-1])


def test_the_whole_evaluation_runs_with_only_root_and_linux_stood_in(tmp_path):
    """QA 07e F3. No other check enters main(), sandbox() or probe(), or reaches prepare()'s chown walk with an owner:
    the gap in which the sibling task returned the set-id probe's strings as the run's ids, so that every case of its
    first trial on the platform was a setup error. Here main() runs whole, four times: a delivery whose program answers
    every case, the same program echoing every case's code (re-check 10, S2: the reward withheld says why on the reward
    line too), the hook's mark over nothing, and a sandbox in which a set-id root file runs as root."""
    graded = whole_run(tmp_path / "graded", "own", "program")
    metrics, events = graded["metrics"], graded["events"]
    assert graded["exit"] == 0 and graded["reward"] == "1.000000" and metrics["status"] == "completed", graded
    assert graded["left"] == ["metrics.json", "reward.txt"], "the reserved reward file is renamed, nothing else is left"
    assert [metrics[key] for key in ("cases_total", "cases_run", "cases_passed", "setup_errors", "timeouts")] == [48, 48, 48, 0, 0], metrics
    assert metrics["notes"] == [] and metrics["seconds_total"] > 0 and metrics["by_kind"]["expr"]["passed"] == 24, metrics
    assert (metrics["distinct_outputs"], metrics["distinct_outputs_needed"], metrics["withheld"]) == (48, 12, None), metrics
    assert graded["printed"] == ["reward: 1.000000 (48/48 cases)"], graded["printed"]
    uid = graded["owner"][0]
    assert graded["owner_types"] == ["int", "int"] and graded["owner"] == [uid, uid] and 20000 <= uid < 60000, graded["owner"]
    assert graded["prefix"] == ["setpriv", "--reuid", str(uid), "--regid", str(uid), "--clear-groups", "--no-new-privs"]
    assert events["through_the_drop"] == 48, "every case started through the prefix sandbox() returned"
    assert events["lchown_in_prepare"] >= 48 * 4 and events["lchown_in_seal"] == 5, "integer ids reached every chown (a string raises)"
    assert events["chown"] == 2, "the scratch directory, and the set-id probe file"
    assert len(events["probes"]) == 4 and [probe.split()[-1] for probe in events["probes"][2:]] == ["-u", "-g"], events["probes"]
    assert events["not_run"]["kill -KILL -1"] >= 5 and events["not_run"]["find"] >= 5 and events["not_run"]["ipcrm --all"] >= 5
    assert graded["limits"]["Max processes"] == "512" and metrics["limits"] == graded["limits"]
    assert not graded["probe_left"] and graded["scratch"] == [], "the probe and the workspaces are removed"
    record = metrics["delivery_record"]
    size = len('#!/bin/sh\necho "w$2"\n') + len("Apache License\n")
    assert record["delivered"] == f"delivered 2 {size}", record
    assert record["entries"] == 2 and record["connectivity_open"] is False and record["late_entries"] == 0
    assert metrics["submission"]["size"] == record["bpl"]["size"] and record["listing_complete"] is True

    echo = whole_run(tmp_path / "echo", "own", "echo")
    assert echo["exit"] == 0 and echo["reward"] == "0.000000" and echo["metrics"]["cases_passed"] == 48, echo["metrics"]
    assert echo["metrics"]["distinct_outputs"] == 0 and echo["metrics"]["notes"] == [echo["metrics"]["withheld"]], echo["metrics"]
    assert echo["printed"] == [f"reward: 0.000000 (48/48 cases); {echo['metrics']['withheld']}"], echo["printed"]
    assert echo["metrics"]["withheld"].startswith("reward 0: the 48 cases passed hold 0 different outputs"), echo["metrics"]["withheld"]

    nothing = whole_run(tmp_path / "nothing", "own", "nothing")
    assert nothing["exit"] == 0 and nothing["reward"] == "0.000000" and nothing["metrics"]["cases_passed"] == 0, nothing
    assert nothing["metrics"]["notes"] == ["/app/rebuild/bpl is missing or not executable"], nothing["metrics"]["notes"]
    assert nothing["metrics"]["delivery_record"]["delivered"] == "delivered 0 0" and nothing["events"]["through_the_drop"] == 0
    assert nothing["printed"] == ["reward: 0.000000 (0/48 cases)"] and nothing["metrics"]["withheld"] is None, nothing["printed"]

    escape = whole_run(tmp_path / "escape", "0", "program")
    assert escape["exit"] == 1 and escape["reward"] is None and escape["left"] == ["metrics.json"], escape
    assert escape["metrics"]["status"] == "evaluation_error", escape["metrics"]
    assert "a set-id root file ran with user and group ('0', '0')" in escape["metrics"]["error"], escape["metrics"]
    assert escape["events"]["through_the_drop"] == 0, "no case runs in a sandbox that does not hold"


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
    import tomllib
    agent = tomllib.loads(toml)["steps"][0]["agent"]["timeout_sec"]
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
            recorder.last_bits(e("∧3j4"), "5 0.9272952180016123\\n"),            # polar: the build's own atan2 (12b F1)
            recorder.last_bits(e("{¯1+*ω}1E¯17"), "1ₑ¯17\\n"),                  # an exact tiny literal, not a residue (12b F7)
            recorder.last_bits(e("¯2√8"), "0.35355339059327373\\n"),            # a root other than the square root
            recorder.last_bits(e("√2"), "1.4142135623730951\\n"),               # the square root is correctly rounded
            recorder.last_bits(worker("x←÷3", "⌊100×1○1.2"), reply(0.3333333333333333) + "\\n" + reply(93) + "\\n"),
            recorder.last_bits(worker("x←÷3", "1○1.2"), reply(0.3333333333333333) + "\\n" + reply(0.9320390859672262) + "\\n"),
        ]))
    """))
    assert out == [True, False, False, True, True, False, True, False, True, False, False, True], out
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
        for i in range(1000, 1040):  # one of the generator's own lead forms: evaluated without an interpreter
            add(i, "error", f"⎕←+/ι{i}\\n1 2+3 4 5", (f"{i * (i - 1) // 2}\\n", 1))
        for i in range(1040, 1070):  # one answer for one shape of -e
            add(i, "expr", "", ("DOMAIN ERROR\\n", 0), argv=["-e", f"code{i}"])
        for i in range(1070, 1080):  # a value assigned and then named: its last strand is the answer
            add(i, "script", f"x←{i} 7\\nx", (f"{i} 7\\n", 0))
        for i, body in enumerate(["(1 2 3)+4 5", "(1 2 3)-4 5", "(1 2 3)×4 5", "(1 2 3)÷4 5", '(ι"a")+1', '(ι"b")+2'], 1080):
            same = "lengths 3 and 2 don't agree" if i < 1084 else "ι needs a number"  # a lookup trained on the others gets the four
            add(i, "error", "{∞::$e.message ◇ " + body + "}0", (f'"{same}"\\n', 0))
        free = recorder.no_interpreter(cases, outputs)
        kept, dropped = recorder.select(cases, outputs)
        after = recorder.no_interpreter(kept, outputs)
        print(json.dumps([{how: len(ids) for how, ids in free.items()}, len(kept), len(recorder.free_union(after)),
                          len(dropped.get("passed with no interpreter", []))]))
    """))
    before, kept, free_after, dropped = out
    assert before["echoed literals"] == 100 and before["lead forms evaluated"] == 40 and before["constant for -e CODE"] == 30, before
    # the ten, and `x←0 ◇ ⎕←x×2`; the two ι cases are each other's nearest, and the `+` length case's nearest is one of them
    assert before["last literal echoed"] == 11 and before["error lookup"] == 5, before
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
    # the different outputs of programs given to run: 6, 7, 8, the message and y (the help case is the command
    # line's own, and the two silent programs print nothing); the dispatcher's three cases hold none of them
    assert baselines["distinct_outputs_kept"] == 5 and baselines["no_interpreter_dispatcher_distinct_outputs"] == 0, baselines


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
    assert 'mark.py" "$here/bpl.xz" "$here/build.txt" - /app/rebuild/bpl' in solve
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
    assert sorted(path.name for path in (TASK / "environment").iterdir()) == [".dockerignore", "Dockerfile", "provision-scratch",
                                                                          "reclaim-scratch"]
    instruction = seen["instruction.md"]
    assert "no example" not in instruction.lower() and "Out of scope:" in instruction
    flat = " ".join(instruction.split())
    assert "All of the manual is in scope" in flat and "derivatives with `∂` among them" in flat, "the scope is the whole manual"
    for excluded in ("¿", "•time", "•plot", "•storage", "•explain", "•hash", "timeout_ms", "]help"):
        assert excluded in instruction.split("Out of scope:", 1)[1], excluded


def test_the_instruction_states_the_requirement_and_never_a_comparison_of_the_work():
    """A sibling task's verdict: a solver that read its completion sentence ("cannot be told apart from ...") called its
    own run an evaluation, which the platform counts as info leakage at must-fix tier. Here the sentence states the
    requirement in the requester's terms, and nothing of ours in the agent's image or instruction uses that phrase
    class. Upstream's manual, which ships as it is, speaks only of evaluation order, APL's grade and Python benchmarks."""
    instruction = " ".join((STEP / "instruction.md").read_text().split())
    assert ("The work is complete when, for every script, input and command line we run, your program writes to standard "
            "output exactly what the sandboxed build writes and exits with the same status.") in instruction
    phrases = re.compile(r"told apart|tell (?:them |it )?apart|indistinguishab|\bgrad(?:ed|ing|er)\b|evaluat|test corpus|"
                         r"hidden test|held.out|benchmark|rubric|\bjudged?\b", re.I)
    ours = [STEP / "instruction.md", TASK / "environment" / "Dockerfile", HARDENING / "mark.py",
            *(TASK / "environment" / name for name in ("provision-scratch", "reclaim-scratch"))]
    found = {path.name: phrases.findall(path.read_text()) for path in ours}
    assert not any(found.values()), {name: words for name, words in found.items() if words}


def test_no_shipped_file_of_ours_outside_the_verifier_uses_a_word_the_audit_scan_flags():
    """QA 07f G3. The pre-trial audit's word scan stops on these words. They appear in no file of ours that ships
    outside the verifier image's own sources (whose vocabulary is their job) and task.toml (whose `[verifier]` tables
    are the schema's): the agent image's files and installed scripts, the hardening tools both images take (the solution
    takes mark.py), the instruction and the solution."""
    flagged = re.compile(r"grade|score|verif|harness|oddish|modal|harbor|\bcap\b|budget|attempt|audit|QA|round [0-9]|trial", re.I)
    assert 'SHIPPED_TOOLS = ("mark.py", "smoke.sh")' in (SCRIPTS / "package_step.py").read_text(), "what of common/hardening ships"
    assert sorted(path.name for path in (STEP / "solution").iterdir() if path.name != "__pycache__") == ["solve.sh"]
    shipped = [*sorted((TASK / "environment").iterdir()), HARDENING / "mark.py", HARDENING / "smoke.sh", STEP / "instruction.md",
               *sorted((STEP / "solution").iterdir())]
    found = {path.relative_to(TASK).as_posix(): flagged.findall(path.read_text()) for path in shipped if path.is_file()}
    assert len(found) == 8 and not any(found.values()), {name: words for name, words in found.items() if words}
    # task.toml holds no comment at all: the pre-trial audit flagged one that spoke of the platform, its trials and the
    # verifier image (its tables name the verifier, as the schema does)
    assert not [line for line in (TASK / "task.toml").read_text().splitlines() if line.lstrip().startswith("#")]


def test_the_reference_solution_installs_the_original_and_its_licence_and_nothing_else():
    """The pre-trial audit's one must-fix on round 8's bundle: the solution kept an author-only probe (probe.c, built
    with gcc and run as the agent's user, its output copied into the run's logs). The solution's one job is the
    install: the original with the zero marker, and upstream's licence, in /app/rebuild. It runs nothing else, writes
    nowhere else, and is packaged with only what the install needs. No shipped file of ours outside the verifier names
    an author, the run's logs, a sandbox of its own, or a file that does not ship."""
    solve = (STEP / "solution" / "solve.sh").read_text()
    commands = [line for line in solve.splitlines() if line.strip() and not line.startswith("#")]
    assert commands == ["set -euo pipefail", 'here="$(cd "$(dirname "$0")" && pwd)"', "mkdir -p /app/rebuild",
                        'python3 "$here/mark.py" "$here/bpl.xz" "$here/build.txt" - /app/rebuild/bpl',
                        "rm -f /app/rebuild/build.txt", 'install -m 0644 "$here/LICENSE" /app/rebuild/LICENSE'], commands
    packaged = sorted(re.findall(r'content\[f"\{STEP\}/solution/([^"]+)"\]', (SCRIPTS / "package_step.py").read_text()))
    assert packaged == ["LICENSE", "bpl.xz", "build.txt", "mark.py"], packaged
    ours = [*sorted((TASK / "environment").iterdir()), HARDENING / "mark.py", HARDENING / "smoke.sh", STEP / "instruction.md",
            STEP / "solution" / "solve.sh"]
    unwanted = re.compile(r"\bauthors?\b|/logs/|this sandbox|not part of the solution|\bprobe\.c\b|scripts/|apply\.sh|"
                          r"make_cases|build_original|experiment/", re.I)
    found = {path.relative_to(TASK).as_posix(): unwanted.findall(path.read_text()) for path in ours if path.is_file()}
    assert len(found) == 8 and not any(found.values()), {name: words for name, words in found.items() if words}


def test_the_bundle_holds_only_what_is_read_of_the_private_cases_and_the_build_facts():
    """A sibling task's pre-trial audit flagged a provenance record in its hidden data. Here the private cases ship
    with only the keys the verifier image reads: the generator's notes on where each case came from and how it was put
    together stay in the private file. build.txt ships with only the lines mark.py reads: upstream's commit, the
    toolchain, the target and the size stay in experiment/build/build.txt. The leak check still reads the whole file."""
    found = scripts_call(textwrap.dedent('''
        import json, package_step
        cases = [{"id": "P00001", "kind": "worker", "source": "core.bpl:12", "suite": "own", "argv": ["--worker"], "files": {},
                  "stdin": "{}", "record": {"variants": [{"stdin": "[]"}], "want": "same", "scaffold_lines": [0]}},
                 {"id": "P00002", "kind": "program", "source": "ledger", "family": "ledger", "argv": ["main.bpl"],
                  "files": {"main.bpl": "x"}, "stdin": None},
                 {"id": "P00003", "kind": "display", "source": "display", "form": "built", "argv": ["show.bpl"],
                  "files": {"show.bpl": "1"}, "stdin": None, "record": {"variants": [], "want": "same", "unset": ["show.bpl", "", ""]}}]
        build = b"commit af36\\ntoolchain 1.100.0\\ntarget x86_64-unknown-linux-musl\\nlink static\\nsize 3\\nsha256 ff\\n"
        try:
            package_step.shipped_build(b"commit af36\\nsha256 ff\\n")
            missing = None
        except ValueError as exc:
            missing = str(exc)
        print(json.dumps({"cases": package_step.shipped_cases(cases).decode(), "build": package_step.shipped_build(build).decode(),
                          "missing": missing, "keys": [package_step.CASE_KEYS, package_step.PLAN_KEYS]}, ensure_ascii=False))
    '''))
    shipped = json.loads(found["cases"])["cases"]
    assert shipped == [{"argv": ["--worker"], "files": {}, "id": "P00001", "kind": "worker", "record": {"variants": [{"stdin": "[]"}]},
                        "stdin": "{}"},
                       {"argv": ["main.bpl"], "files": {"main.bpl": "x"}, "id": "P00002", "kind": "program", "stdin": None},
                       {"argv": ["show.bpl"], "files": {"show.bpl": "1"}, "form": "built", "id": "P00003", "kind": "display",
                        "record": {"unset": ["show.bpl", "", ""], "variants": []}, "stdin": None}], shipped
    assert found["cases"] == json.dumps({"cases": shipped}, ensure_ascii=False, sort_keys=True), "written as make_cases.py writes it"
    assert found["build"] == "link static\nsha256 ff\n" and "link" in found["missing"]
    # Every key the verifier image reads of a case, and of its "record" entry, is one the bundle keeps.
    case_keys, plan_keys = map(set, found["keys"])
    sources = "\n".join(path.read_text() for path in [STEP / "tests" / "verify.py", *sorted((STEP / "tests" / "verifier").glob("*.py"))])
    read = set(re.findall(r'\bcase(?:\.get\(|\[)"(\w+)"', sources))
    assert {"id", "kind", "argv", "files", "stdin", "form", "record"} <= read <= case_keys | {"record"}, read
    assert set(re.findall(r'\bplan(?:\.get\(|\[)"(\w+)"', sources)) == plan_keys
    package = (SCRIPTS / "package_step.py").read_text()
    assert 'content[f"{STEP}/tests/private/cases.json"] = shipped_cases(cases)' in package and "build = shipped_build(build)" in package
    assert package.index("make_cases.leaks(cases, skeletons, texts)") < package.index("= shipped_cases(cases)")


def test_the_verifier_names_neither_the_platform_nor_how_the_task_was_made():
    """The verifier's sources speak of grading, which is their job, but not of the platform they run on or of the
    scripts the task was made with: three comments named scripts/upstream_builds.py, gVisor and make_cases.LEADS."""
    tests = STEP / "tests"
    sources = [tests / "verify.py", tests / "test.sh", tests / "Dockerfile", *sorted((tests / "verifier").glob("*.py"))]
    named = re.compile(r"scripts/|make_cases|build_original|apply\.sh|gvisor|experiment/|oddish|\bmodal\b|harbor|daytona|"
                       r"\bauthors?\b|\bQA\b|round [0-9]|re-check", re.I)
    found = {path.relative_to(TASK).as_posix(): named.findall(path.read_text()) for path in sources}
    assert len(found) == 7 and not any(found.values()), {name: words for name, words in found.items() if words}


def test_only_the_documentation_and_the_binary_reach_the_agent():
    package = (SCRIPTS / "package_step.py").read_text()
    assert 'content[f"environment/docs/{name}"] = text.encode("utf-8")' in package
    assert "make_cases.leaks(cases, skeletons, texts)" in package
    agent = (TASK / "environment" / "Dockerfile").read_text()
    assert re.findall(r"^COPY .*$", agent, re.M) == ["COPY original/ /original/", "COPY --from=program /opt/bpl/bpl /opt/bpl/bpl",
                                                    "COPY --from=program /original/smoke.sh /tmp/bpl-smoke.sh",
                                                    "COPY docs/ /app/docs/",
                                                    "COPY provision-scratch reclaim-scratch /usr/local/sbin/"]
    final = agent.split("\nFROM ", 1)[1]
    assert "sudo" not in agent, "no set-user-id helper the agent's user cannot use anyway"
    assert final.index("chmod 2711 /opt/bpl/bpl") < final.index(
        "setpriv --reuid dev --regid dev --clear-groups env HOME=/tmp bash /tmp/bpl-smoke.sh /opt/bpl/bpl") \
        < final.index("rm -f /tmp/bpl-smoke.sh"), "the installed build is proved as the agent runs it, set-group-id"
    smoke = (HARDENING / "smoke.sh").read_text()
    assert 'if [ "$(id -u)" -ne 0 ] && [ ! -r "$bpl" ]; then' in smoke and 'for target in "$bpl" /proc/self/exe; do' in smoke
    assert sorted(path.name for path in HARDENING.iterdir()) == ["Cargo.lock", "apply.sh", "basedpl-hardening.patch", "mark.py",
                                                                 "smoke.sh"]


def test_the_agent_image_holds_no_record_of_the_originals_source_or_build(tmp_path):
    """A sibling task's re-check found a world-readable requirements file in its agent image that named the original's
    project and pinned its stack. Here the agent image's final stage takes from the build stage only the installed
    binary (execute-only) and the smoke test, which it deletes in the same step: not the build.txt that mark.py writes
    beside the binary there, nor /original. Its own files are the three maintenance scripts (root-only) and the
    documentation, which packaging takes from upstream's site pages alone (.qmd and .ipynb under nbs/, as Markdown),
    with llms.txt and the licence: never a requirements, lock, build or configuration file, nor a source file."""
    final = (TASK / "environment" / "Dockerfile").read_text().split("\nFROM ", 1)[1]
    assert re.findall(r"^COPY --from=program (\S+) ", final, re.M) == ["/opt/bpl/bpl", "/original/smoke.sh"]
    assert "rm -f /tmp/bpl-smoke.sh" in final and "/original/" not in final.replace("COPY --from=program /original/smoke.sh", "")
    assert re.findall(r"^COPY (?!--from)(.+)$", final, re.M) == ["docs/ /app/docs/", "provision-scratch reclaim-scratch /usr/local/sbin/"]
    root = upstream(tmp_path)
    decoys = {"requirements.txt": "basedpl==0.1.95\n", "Cargo.toml": '[package]\nname = "basedpl"\n', "Cargo.lock": "version = 3\n",
              "src/main.rs": "fn main() {}\n", "nbs/settings.ini": "[DEFAULT]\nrequirements = rustymath\n", "nbs/_quarto.yml": "project: {}\n",
              "nbs/requirements.txt": "jupyter\n", "nbs/glyphs/notes.txt": "x\n", "nbs/study/data.json": "{}\n",
              "nbs/build/lib.rs": "pub fn f() {}\n", "nbs/deps/page.qmd": "# a page below a folder the site does not publish\n"}
    for name, text in decoys.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    pages = scripts_call(f"import json, bpl_text\nfrom pathlib import Path\nprint(json.dumps(sorted(bpl_text.documentation(Path({str(root)!r})))))")
    assert pages == ["LICENSE", "glyphs/plus.md", "guide.md", "llms.txt", "system/demo.md"], pages
    package = (SCRIPTS / "package_step.py").read_text()
    assert 'content[f"environment/docs/{name}"] = text.encode("utf-8")' in package and "for name, text in pages.items():" in package


def test_the_flat_bundle_is_the_same_task_under_the_same_name():
    """Round 12 (decision 2026-11-24, item 3). The upload is a flat single-step bundle, as SymPy's is (its capped runs
    were graded), under the task's own name, so that it is the next version of the same task: `--flat --keep-name`.
    The one step's files move to the top; task.toml loses its [[steps]] tables, whose limits equal the top-level
    ones (packaging refuses otherwise), and its multi-step reward strategy (one step: its reward is the trial's).
    Everything else is the same bytes."""
    found = scripts_call(textwrap.dedent(f'''
        import json, tomllib, package_step
        from pathlib import Path
        toml = Path({str(TASK / "task.toml")!r}).read_bytes()
        content = {{"task.toml": toml, "environment/Dockerfile": b"FROM x\\n", "steps/01-rebuild-interpreter/instruction.md": b"# I\\n",
                   "steps/01-rebuild-interpreter/tests/test.sh": b"#!/bin/sh\\n", "steps/01-rebuild-interpreter/solution/solve.sh": b"x\\n"}}
        flat = package_step.flatten(content, keep_name=True)
        renamed = package_step.flatten(content)
        print(json.dumps({{"names": sorted(flat), "same": [flat[name] == content.get(name, content.get("steps/01-rebuild-interpreter/" + name))
                                                            for name in sorted(flat) if name != "task.toml"],
                          "toml": flat["task.toml"].decode(), "renamed": tomllib.loads(renamed["task.toml"].decode())["task"]["name"]}}))
    '''))
    import tomllib
    assert found["names"] == ["environment/Dockerfile", "instruction.md", "solution/solve.sh", "task.toml", "tests/test.sh"], found["names"]
    assert all(found["same"]), "every file but task.toml is the same bytes"
    steps, flat = tomllib.loads((TASK / "task.toml").read_text()), tomllib.loads(found["toml"])
    assert flat["task"] == steps["task"] and found["renamed"] == steps["task"]["name"] + "-single"
    assert "steps" not in flat and "multi_step_reward_strategy" not in flat and steps["multi_step_reward_strategy"] == "final"
    for key in ("schema_version", "artifacts", "metadata", "agent", "environment", "verifier"):
        assert flat[key] == steps[key], key
    assert len(steps["steps"]) == 1 and steps["steps"][0]["agent"] == {"timeout_sec": steps["agent"]["timeout_sec"]}
    assert steps["steps"][0]["verifier"] == {"timeout_sec": steps["verifier"]["timeout_sec"]}
