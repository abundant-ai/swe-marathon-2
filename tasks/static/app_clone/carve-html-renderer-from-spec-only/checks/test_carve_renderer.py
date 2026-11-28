"""Development checks: the rewrites keep what a renderer reads and change what it prints; nothing
the agent can read becomes a case; the generators make documents for any seed; the verifier counts
what a submission does as that submission's failed cases and reads the delivery the sweep hook
marked; the hook lets an honest delivery through the platform's copy; the recorder keeps only steady
answers that need a renderer; and the agent's image holds the specification and the documentation,
nothing else.

Script and verifier code runs in processes of its own: another task's checks have modules named
`make_cases`, `seeds` and `verifier` too. Nothing here needs the upstream checkouts, the original's
binary, Node or experiment/.
"""

from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import pwd
import re
import resource
import shutil
import struct
import subprocess
import sys
import tarfile
import textwrap
import time
import tomllib
from pathlib import Path

import pytest

TASK = Path(__file__).resolve().parent.parent
STEP = TASK
SCRIPTS = TASK / "scripts"
TESTS = STEP / "tests"
RUNNER = TESTS / "verifier" / "runcases.py"
RECORDER = TESTS / "verifier" / "recorder.py"
HOOK = TASK / "environment" / "fsmaint-sweep"
SETUP = TASK / "environment" / "fsmaint-reserve"


def scripts_call(code: str) -> object:
    """The JSON a snippet prints with the task's scripts importable, in a process of its own."""
    done = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            f"import sys; sys.path.insert(0, {str(SCRIPTS)!r})\n" + code,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


def verifier_call(code: str) -> object:
    """The JSON a snippet prints with the verifier importable, in a process of its own."""
    done = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            f"import sys; sys.path.insert(0, {str(TESTS)!r})\n" + code,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


# ---------------------------------------------------------------- rewrites and generators

SAMPLE = textwrap.dedent("""\
    # Getting Started

    {#intro .lead key=value}
    It's the *Setup* page &amp; more (tm). See </#Getting-Started> and [Getting Started][].
    Visit <https://example.com/setup> or [mail](mailto:team@example.org) at 10:30.

    ::: warning "Heads up"
    Check [^note] and the API.[^note]
    :::

    ```python "setup.py"
    import setup
    ```

    - [x] done item
    - [ ] open item

    a.  alpha
    iv.  four

    *[API]: Application Programming Interface

    [^note]: A footnote about setup.
""")


def test_renaming_is_consistent_keeps_syntax_and_letter_case():
    out = scripts_call(
        textwrap.dedent(f"""
        import json, random, rewrite
        source = {SAMPLE!r}
        variants = rewrite.renamings(source, random.Random(4), 3)
        print(json.dumps([variants, sorted(rewrite.protected_words(source))]))
    """)
    )
    variants, protected = out
    assert len(variants) == 3 and len(set(variants)) == 3
    for variant in variants:
        assert variant != SAMPLE
        assert [len(line) for line in variant.splitlines()] == [
            len(line) for line in SAMPLE.splitlines()
        ], "same lengths"
        for kept in (
            "::: warning",
            "```python",
            "key=value",
            "&amp;",
            "(tm)",
            "- [x]",
            "a.  ",
            "iv.  ",
            "https://",
            "mailto:",
            "'s ",
            "{#",
            "10:30",
        ):
            assert kept in variant, kept
        heading = re.search(r"^# (\w+) (\w+)$", variant, re.MULTILINE).groups()
        assert (
            f"</#{heading[0]}-{heading[1]}>" in variant
            and f"[{heading[0]} {heading[1]}][]" in variant
        ), "a cross-reference and a heading reference still name their heading"
        assert (
            variant.count("[^note]") == 0
            and len(set(re.findall(r"\[\^(\w+)\]", variant))) == 1
        ), "one label, renamed alike"
        abbreviation = re.search(r"^\*\[(\w+)\]:", variant, re.MULTILINE).group(1)
        assert (
            abbreviation.isupper()
            and len(abbreviation) == 3
            and variant.count(abbreviation) >= 2
        ), "the abbreviation and its use"
    assert {
        "warning",
        "python",
        "key",
        "value",
        "amp",
        "tm",
        "x",
        "a",
        "iv",
        "https",
        "mailto",
    } <= set(protected)


def test_structure_ignores_words_and_numbers_and_keeps_tags():
    out = scripts_call(
        textwrap.dedent("""
        import json, rewrite
        a = '<section id="Getting-Started">\\n  <h1>Getting Started</h1>\\n  <p>See <a href="#x1">it</a> 12.</p>\\n</section>\\n'
        b = '<section id="Tall-Window">\\n  <h1>Tall Window</h1>\\n  <p>Run <a href="#q7">ox</a> 345.</p>\\n</section>\\n'
        c = '<section id="Tall-Window">\\n  <h2>Tall Window</h2>\\n  <p>Run <a href="#q7">ox</a> 345.</p>\\n</section>\\n'
        print(json.dumps([rewrite.structure(a) == rewrite.structure(b), rewrite.structure(a) == rewrite.structure(c)]))
    """)
    )
    assert out == [True, False]


def test_mutations_are_local_edits_for_any_seed():
    out = scripts_call(
        textwrap.dedent("""
        import json, random, rewrite
        rng = random.Random(9)
        found = []
        for seed in range(200):
            mutant, edits = rewrite.mutate("- one\\n  - two\\n\\n> quote\\n", rng, ["# H\\n", "| a |\\n"])
            found.append([mutant.endswith("\\n"), all(edit in rewrite.MUTATORS for edit in edits), 1 <= len(edits) <= 3])
        print(json.dumps(found))
    """)
    )
    assert all(all(row) for row in out)


def test_leak_index_catches_copies_and_near_copies():
    pages = {
        "docs/guide.md": "# Guide\n\n```carve\n::: note\nShort body.\n:::\n```\n\nWrite `/slanted words/` for italic.\n\n"
        "```\n- one\n- two\n```\n\n    -{.c} x         Djot:  <p>...</p>\n",
        "spec/07.ebnf": "(* kind is text in that region: {/a/b/} -> <em>a/b</em>, and `*b*` too *)\n",
        "spec/cases.json": json.dumps(
            {"cases": [{"source": "[t]()", "html": '<p><a href="">t</a></p>'}]}
        ),
    }
    out = scripts_call(
        textwrap.dedent(f"""
        import json, carve_text as ct, make_cases
        skeletons, blob = ct.leak_index({pages!r})
        probe = lambda s: make_cases.leaks(s, skeletons, blob)
        print(json.dumps([probe("::: tip\\nOther words.\\n:::\\n"), probe("- six\\n- ten\\n"), probe("{{/q/r/}}"),
                          probe("[w]()"), probe("-{{.z}} y"), probe("Write /slanted words/ often."),
                          probe("# A heading\\n\\nA paragraph with *bold* text that the docs never show.\\n"),
                          ct.holds_include("text {{{{ part.crv }}}} more"), ct.holds_include("{{ not one }}")]))
    """)
    )
    assert out[:6] == [True, True, True, True, True, False], (
        "a shown example or a renamed copy of one is a leak"
    )
    assert out[6] is False and out[7] is True and out[8] is False


def test_documents_and_constructs_for_any_seed():
    out = scripts_call(
        textwrap.dedent("""
        import json, random, documents
        kinds, areas, bad = set(), set(), []
        for seed in range(60):
            kind, source = documents.document(random.Random(seed))
            area, small = documents.construct(random.Random(1000 + seed))
            kinds.add(kind); areas.add(area)
            for text in (source, small):
                if not text.strip() or not text.endswith("\\n") or "{{" in text:
                    bad.append([kind, area, text[:80]])
        print(json.dumps([sorted(kinds), sorted(areas), bad, len(source.splitlines())]))
    """)
    )
    kinds, areas, bad, _ = out
    assert (
        len(kinds) >= 10
        and areas
        == ["attributes", "block", "divergence", "inline", "layout", "resolution"]
        and bad == []
    )


def test_the_djot_rewrite_is_the_obvious_one():
    out = scripts_call(
        textwrap.dedent("""
        import json, features as f
        print(json.dumps([f.to_djot("/i/ *b* _u_ ~s~ =h= H{,2,}O x{^2^} `/c/`\\n"), f.to_djot(". one\\n. two\\n"),
                          f.to_djot("|= A |= B |\\n| 1 | 2 |\\n"), f.to_djot(":: term\\n: meaning\\n"), f.to_djot("x %% note\\n"),
                          f.to_djot("```\\n/kept/\\n```\\n"), f.normalized("<p>a</p>\\n  <p>b  c</p>\\n")]))
    """)
    )
    inline, ordered, table, definition, comment, fence, normal = out
    assert inline == "_i_ *b* {+u+} {-s-} {=h=} H~2~O x^2^ `/c/`\n"
    assert (
        ordered == "1. one\n1. two\n" and table == "| A | B |\n|---|---|\n| 1 | 2 |\n"
    )
    assert (
        definition == ": term\n\n  meaning\n"
        and comment == "x {% note %}\n"
        and fence == "```\n/kept/\n```\n"
    )
    assert normal == "<p>a</p><p>b c</p>"


def test_features_and_areas_read_the_source():
    out = scripts_call(
        textwrap.dedent("""
        import json, features as f
        print(json.dumps([f.area("- a\\n+\\n> q\\n"), f.area("- a\\n  - b\\n"), f.area("> q\\nlazy\\n"), f.area("# H\\n\\nSee </#H>.\\n"),
                          f.area("{.c}\\n# H\\n"), f.area("- a\\n- b\\n"), f.area("just *text*\\n"),
                          f.features("::: note\\nx\\n:::\\n"), f.features("- [/] going\\n")]))
    """)
    )
    assert out[:7] == [
        "layout",
        "layout",
        "layout",
        "resolution",
        "attributes",
        "block",
        "inline",
    ]
    assert (
        "typed-containers" in out[7]
        and "colon-fences" in out[7]
        and "task-states" in out[8]
    )


def test_settle_keeps_a_variant_only_when_the_host_and_lookup_cannot_reach_it():
    out = scripts_call(
        textwrap.dedent("""
        import json, make_cases, corpus_lookup
        empty = corpus_lookup.Lookup({}, {})
        def item(kind, variants, parts=1, origin="x:0"):
            return {"kind": kind, "index": 0, "variants": [(f"v{i}", s) for i, s in enumerate(variants)],
                    "files": {"a.crv": "base"}, "stdin": None, "argv": ["a.crv"], "source": "base",
                    "origin": origin, "parts": ["p"] * parts}
        def run(it, outputs, corpus_html=None):
            chosen, how, reasons = make_cases.settle(it, outputs, empty, corpus_html or {})
            return [None if chosen is None else chosen["source"], how, dict(reasons)]
        base = {"exit": 0, "stdout": "<p>base</p>\\n"}
        # a snippet whose only variant renders exactly as the plain document is dropped
        same = run(item("snippet", ["s0"]), {(0, -1): base, (0, 0): dict(base), (0, 100): {"exit": 0, "stdout": "<p>h</p>\\n"},
                                             (0, 200): {"exit": 0, "stdout": "<p>base</p>\\n"}})
        # a snippet whose variant differs, the lookup misses, the host/part render and the splice differs is kept
        got = {"exit": 0, "stdout": "<blockquote>\\n<p>word</p>\\n</blockquote>\\n"}
        kept = run(item("snippet", ["s0"]), {(0, -1): base, (0, 0): got, (0, 100): {"exit": 0, "stdout": "<p>HOST</p>\\n"},
                                             (0, 200): {"exit": 0, "stdout": "<p>word</p>\\n"}})
        # a mutant whose edits leave the published structure is dropped
        mut = run(item("mutant", ["m0"], origin="doc:0"),
                  {(0, -1): base, (0, 0): {"exit": 0, "stdout": "<p>other</p>\\n"}},
                  corpus_html={"doc": "<p>published</p>"})
        nov = run(item("snippet", []), {(0, -1): base})
        timed = run(item("snippet", ["s0"]), {(0, -1): {"exit": None, "error": "timeout"}})
        doc = run(item("document", []), {(0, -1): base})
        print(json.dumps([same, kept, mut, nov, timed, doc,
                          make_cases.js_trim("\\ufeff\\u00a0 x \\u2028\\n"), make_cases.answer_sha256(0, "<p>x</p>\\n")]))
    """)
    )
    same, kept, mut, nov, timed, doc = out[:6]
    assert (
        same[0] is None
        and same[1] == "no variant kept"
        and same[2] == {"same answer as the plain document": 1}
    )
    assert kept[0] and kept[1] == "snippet: v0" and kept[2] == {}, kept
    assert mut[0] is None and mut[2] == {"the edits kept the published structure": 1}, (
        mut
    )
    assert nov == [None, "no variant", {}] and timed[1] == "the original timed out"
    assert doc == ["base", "as generated", {}]
    assert out[6] == "x"
    digest = verifier_call(
        'import json\nfrom verifier import recorder\nprint(json.dumps(recorder.digest(0, b"<p>x</p>\\n")))'
    )
    assert out[7] == digest, (
        "the build's recording compares the digest the generator stored"
    )


def test_command_line_cases_are_one_per_behaviour():
    out = scripts_call(
        textwrap.dedent("""
        import json, make_cases
        cases = make_cases.cli_cases()
        print(json.dumps([[c["origin"] for c in cases], [json.dumps([c["argv"], c["files"], c["stdin"]], sort_keys=True) for c in cases]]))
    """)
    )
    origins, inputs = out
    assert len(origins) == len(set(origins)) == len(set(inputs)) >= 20
    for behaviour in (
        "missing-file",
        "directory",
        "two-files",
        "unknown-long-option",
        "double-dash",
        "stdin-dash",
        "invalid-utf8",
        "byte-order-mark",
        "crlf",
        "empty-file",
        "file-then-safe",
    ):
        assert f"cli:{behaviour}" in origins, behaviour


# ---------------------------------------------------------------- the verifier


def run_verifier(
    tmp_path: Path,
    script: str,
    cases: list[dict],
    expected: dict,
    case_sec: float = 2,
    output_limit: int | None = None,
) -> dict:
    """grade() of the real verify.py, in a process of its own, with the workspace under tmp_path and
    no privilege drop (macOS and CI runners have no setpriv): what the submission can do to its
    workspace and its output is the same."""
    program = tmp_path / "carve"
    program.write_text("#!/bin/sh\n" + script)
    program.chmod(0o755)
    private = tmp_path / "private"
    private.mkdir(exist_ok=True)
    (private / "cases.json").write_text(json.dumps({"cases": cases}))
    (private / "expected.json").write_text(json.dumps(expected))
    driver = textwrap.dedent(f"""
        import json, sys
        from pathlib import Path
        sys.path.insert(0, {str(TESTS)!r})
        import verify
        verify.runcases.WORKSPACE = Path({str(tmp_path / "tmp" / "carve-case")!r})
        verify.runcases.HOME = Path({str(tmp_path / "tmp" / "carve-home")!r})
        verify.runcases.TEMP = Path({str(tmp_path / "tmp" / "carve-tmp")!r})
        verify.runcases.CASE_SEC = {case_sec}
        verify.PREEXEC = verify.runcases.limit  # no seccomp here; the filter has checks of its own
        if {output_limit!r} is not None:
            verify.runcases.OUTPUT_LIMIT = {output_limit!r}
        print(json.dumps(verify.run_cases(Path({str(program)!r}), Path({str(private)!r}), [], None)))
    """)
    (tmp_path / "tmp").mkdir(exist_ok=True)
    done = subprocess.run(
        [sys.executable, "-B", "-c", driver],
        check=False,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


def plain_cases(
    argvs: list[list[str]], kinds: list[str] | None = None
) -> tuple[list[dict], dict]:
    cases = [
        {"id": f"P{i}", "files": {"page.crv": "# T\n"}, "argv": argv, "stdin": None}
        for i, argv in enumerate(argvs)
    ]
    for case, kind in zip(cases, kinds or []):
        case["kind"] = kind
        case["area"] = {"document": "document", "snippet": "layout"}.get(kind, "inline")
    return cases, {case["id"]: {"exit": 0, "stdout": "ok\n"} for case in cases}


def test_many_slow_runs_do_not_stop_the_count(tmp_path):
    cases, expected = plain_cases([["slow"]] * 65 + [["fast"]] * 5)
    metrics = run_verifier(
        tmp_path,
        'case "$1" in slow) exec sleep 5;; esac\necho ok\n',
        cases,
        expected,
        case_sec=0.05,
    )
    assert (
        metrics["cases_run"] == 70
        and metrics["timeouts"] == 65
        and metrics["cases_passed"] == 5
    )
    assert (
        metrics["reward"] == round(5 / 70, 6)
        and metrics["stopped"] is None
        and not metrics["notes"]
    )


def test_a_swapped_or_stuck_workspace_is_a_failed_case_not_an_evaluation_error(
    tmp_path,
):
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
    assert metrics["setup_errors"] == 1 and list(target.iterdir()) == [], (
        "the verifier wrote through the submission's link"
    )
    for locked in tmp_path.rglob("locked"):
        locked.chmod(0o755)


def test_output_is_read_up_to_a_bound_and_compared_as_bytes(tmp_path):
    cases, expected = plain_cases([["flood"], ["ok"], ["bad"], ["other"]])
    expected["P2"] = {"exit": 0, "stdout": b"\x80\n".decode("utf-8", "surrogateescape")}
    expected["P3"] = {"exit": 0, "stdout": b"\xff\n".decode("utf-8", "surrogateescape")}
    script = "case \"$1\" in flood) head -c 20000000 /dev/zero; exit 0;; bad|other) printf '\\200\\n'; exit 0;; esac\necho ok\n"
    metrics = run_verifier(tmp_path, script, cases, expected, output_limit=4096)
    assert metrics["output_limits"] == 1 and metrics["cases_passed"] == 2, metrics
    assert metrics["failed_sample"] == ["P0", "P3"], (
        "two different invalid bytes compared equal"
    )


def test_metrics_count_each_kind_and_area(tmp_path):
    cases, expected = plain_cases(
        [["a"], ["b"], ["slow"], ["c"]],
        kinds=["document", "document", "snippet", "construct"],
    )
    metrics = run_verifier(
        tmp_path,
        'case "$1" in slow) exec sleep 5;; b) echo no; exit 0;; esac\necho ok\n',
        cases,
        expected,
        case_sec=1.0,
    )
    assert metrics["by_kind"] == {
        "document": {"total": 2, "run": 2, "passed": 1, "failed": 1},
        "snippet": {"total": 1, "run": 1, "passed": 0, "failed": 1},
        "construct": {"total": 1, "run": 1, "passed": 1, "failed": 0},
    }
    assert metrics["by_area"] == {
        "document": {"total": 2, "passed": 1},
        "layout": {"total": 1, "passed": 0},
        "inline": {"total": 1, "passed": 1},
    }
    assert metrics["cases_failed"] == 2 and metrics["timeouts"] == 1
    assert (
        1.0 <= metrics["seconds_max"] < 3
        and metrics["seconds_max"] <= metrics["seconds_total"]
    )


def test_case_files_standard_input_and_arguments_reach_the_program(tmp_path):
    latin = b"caf\xe9\n".decode("utf-8", "surrogateescape")
    cases = [
        {
            "id": "P1",
            "files": {"docs/page.crv": latin},
            "argv": ["--safe", "docs/page.crv"],
            "stdin": "piped\n",
        }
    ]
    script = 'printf "%s|" "$@"; od -An -c docs/page.crv | tr -s " "; cat; [ -z "$(ls -A "$HOME")$(ls -A "$TMPDIR")" ] && echo clean\n'
    done = subprocess.run(
        ["sh", "-c", "printf 'caf\\351\\n' | od -An -c | tr -s ' '"],
        check=False,
        capture_output=True,
        text=True,
    )
    expected = {
        "P1": {
            "exit": 0,
            "stdout": "--safe|docs/page.crv|" + done.stdout + "piped\nclean\n",
        }
    }
    assert run_verifier(tmp_path, script, cases, expected)["cases_passed"] == 1, (
        "bytes that are not UTF-8 reach the file"
    )


def test_every_run_gets_the_same_limits(tmp_path):
    report = verifier_call(
        textwrap.dedent(f"""
        import json, sys
        from pathlib import Path
        from verifier import runcases
        runcases.WORKSPACE = Path({str(tmp_path / "carve-case")!r})
        runcases.HOME, runcases.TEMP = Path({str(tmp_path / "carve-home")!r}), Path({str(tmp_path / "carve-tmp")!r})
        code = "import resource, json; print(json.dumps([resource.getrlimit(r) for r in "
        code += "(resource.RLIMIT_STACK, resource.RLIMIT_FSIZE, resource.RLIMIT_CORE)]))"
        case = {{"id": "P1", "files": {{}}, "argv": ["-c", code], "stdin": None}}
        got = runcases.run_case([sys.executable], case)
        print(json.dumps([json.loads(got["stdout"]), [runcases.LIMITS[r] for r in (runcases.resource.RLIMIT_STACK,
              runcases.resource.RLIMIT_FSIZE, runcases.resource.RLIMIT_CORE)]]))
    """)
    )
    limits, wanted = report
    assert [soft for soft, _ in limits] == wanted and [
        hard for _, hard in limits
    ] == wanted


X86_64, AARCH64, I386, ARM = 0xC000003E, 0xC00000B7, 0x40000003, 0x40000028
ALLOW, DENY = 0x7FFF0000, 0x00050000 | 13


def filter_verdict(code: bytes, arch: int, nr: int, arg0: int = 0) -> int:
    """What a classic BPF seccomp program returns for one system call: a small interpreter of the
    four instructions the filter uses, over seccomp_data (nr, arch, ip, args)."""
    data = struct.pack("=iIQ6Q", nr, arch, 0, arg0, 0, 0, 0, 0, 0)
    program = [
        struct.unpack("=HBBI", code[at : at + 8]) for at in range(0, len(code), 8)
    ]
    pc = acc = 0
    for _ in range(len(program) + 1):
        opcode, true, false, k = program[pc]
        if opcode == 0x20:
            acc, pc = struct.unpack_from("=I", data, k)[0], pc + 1
        elif opcode == 0x15:
            pc += 1 + (true if acc == k else false)
        elif opcode == 0x35:
            pc += 1 + (true if acc >= k else false)
        elif opcode == 0x06:
            return k
        else:
            raise AssertionError(f"unexpected opcode {opcode:#x}")
    raise AssertionError("the program did not return")


def test_the_network_filter_denies_every_socket_but_a_local_one():
    """The seccomp filter every run of the program starts under: socket() and socketpair() fail
    with EACCES for any family but AF_UNIX (the kernel reads the family's low 32 bits), io_uring
    cannot be set up, and x32 or 32-bit system calls fail; everything else is allowed. On x86_64
    and on aarch64."""
    code = bytes.fromhex(
        verifier_call(
            "import json\nfrom verifier import runcases\nprint(json.dumps(runcases.FILTER.hex()))"
        )
    )
    wanted = [
        (X86_64, 41, 2, DENY),  # socket(AF_INET)
        (X86_64, 41, 10, DENY),  # AF_INET6
        (X86_64, 41, 16, DENY),  # AF_NETLINK
        (X86_64, 41, 17, DENY),  # AF_PACKET
        (X86_64, 41, (1 << 32) | 2, DENY),
        (X86_64, 41, 1, ALLOW),  # AF_UNIX
        (X86_64, 41, (5 << 32) | 1, ALLOW),  # the kernel's int: AF_UNIX
        (X86_64, 53, 2, DENY),  # socketpair
        (X86_64, 53, 1, ALLOW),
        (X86_64, 425, 0, DENY),  # io_uring_setup, _enter, _register
        (X86_64, 426, 0, DENY),
        (X86_64, 427, 0, DENY),
        (X86_64, 0, 0, ALLOW),  # read, write, clone, execve, openat, connect
        (X86_64, 1, 0, ALLOW),
        (X86_64, 56, 0, ALLOW),
        (X86_64, 59, 0, ALLOW),
        (X86_64, 257, 0, ALLOW),
        (X86_64, 42, 2, ALLOW),
        (X86_64, 0x40000000 | 41, 1, DENY),  # the x32 ABI
        (X86_64, 0x40000000 | 39, 0, DENY),
        (I386, 102, 1, DENY),  # 32-bit socketcall, getpid
        (I386, 20, 0, DENY),
        (AARCH64, 198, 2, DENY),
        (AARCH64, 198, 1, ALLOW),
        (AARCH64, 199, 10, DENY),
        (AARCH64, 425, 0, DENY),
        (AARCH64, 172, 0, ALLOW),
        (AARCH64, 41, 2, ALLOW),  # not socket() on aarch64
        (ARM, 281, 1, DENY),
    ]
    got = [
        (arch, nr, arg0, filter_verdict(code, arch, nr, arg0))
        for arch, nr, arg0, _ in wanted
    ]
    assert got == wanted


def test_a_run_that_is_not_denied_the_network_is_an_evaluation_error():
    """Before any case the verifier starts a process exactly as the program is and needs EACCES
    from socket(AF_INET) and socket(AF_INET6), a working AF_UNIX socket and a failing
    io_uring_setup; anything else, or a sandbox that cannot be set up, is an evaluation error. The
    probe of the verifier's own network is gone: what the machine's network allows decides nothing."""
    results = verifier_call(
        textwrap.dedent("""
        import json, verify
        answers = {
            "denied": {"AF_INET": 13, "AF_INET6": 13, "AF_UNIX": 0, "io_uring_setup": 13},
            "open": {"AF_INET": 0, "AF_INET6": 13, "AF_UNIX": 0, "io_uring_setup": 13},
            "another errno": {"AF_INET": 1, "AF_INET6": 1, "AF_UNIX": 0, "io_uring_setup": 13},
            "io_uring": {"AF_INET": 13, "AF_INET6": 13, "AF_UNIX": 0, "io_uring_setup": 0},
            "no AF_UNIX": {"AF_INET": 13, "AF_INET6": 13, "AF_UNIX": 13, "io_uring_setup": 13},
        }
        results = {}
        for name, seen in answers.items():
            verify.probe = lambda prefix, argv, fallback=None, seen=seen: json.dumps(seen) + "\\n"
            try:
                results[name] = verify.network_denied([])
            except verify.EvaluationError as exc:
                results[name] = str(exc)
        verify.probe = lambda prefix, argv, fallback=None: "not json\\n"
        try:
            verify.network_denied([])
        except verify.EvaluationError as exc:
            results["unreadable"] = str(exc)
        print(json.dumps(results))
        """)
    )
    assert results.pop("denied") == {
        "AF_INET": 13,
        "AF_INET6": 13,
        "AF_UNIX": 0,
        "io_uring_setup": 13,
    }
    assert results.pop("unreadable") == "The network denial could not be checked"
    assert all(
        text.startswith("The network is not denied to the program's runs")
        for text in results.values()
    ), results
    unconfined = verifier_call(
        textwrap.dedent("""
        import json, sys, verify
        def refuse():
            raise OSError("no seccomp here")
        verify.PREEXEC = refuse
        try:
            verify.network_denied([])
            print(json.dumps(None))
        except verify.EvaluationError as exc:
            print(json.dumps(str(exc)))
        """)
    )
    assert unconfined.startswith("The program's sandbox could not be set up"), (
        unconfined
    )
    verify = (TESTS / "verify.py").read_text()
    main = verify[verify.index("def main()") :]
    assert all(
        gone not in verify
        for gone in ("network_open", "NETWORK_HOSTS", "create_connection")
    )
    assert (
        main.index("sandbox()")
        < main.index("network_denied(prefix)")
        < main.index("seal(REBUILD)")
    )
    assert verify.count("preexec=PREEXEC") == 2 and "preexec_fn=PREEXEC" in verify


@pytest.mark.skipif(
    sys.platform != "linux", reason="seccomp filters are Linux's; checked in Docker"
)
def test_a_confined_process_and_its_children_get_no_network_socket():
    report = verifier_call(
        textwrap.dedent("""
        import json, subprocess, sys
        from verifier import runcases
        import verify
        code = verify.NETWORK_PROBE
        child = "import subprocess, sys; print(subprocess.run([sys.executable, '-I', '-c', " + repr(code) + "], capture_output=True, text=True).stdout)"
        direct = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, preexec_fn=runcases.confine)
        nested = subprocess.run([sys.executable, "-I", "-c", child], capture_output=True, text=True, preexec_fn=runcases.confine)
        print(json.dumps([json.loads(direct.stdout), json.loads(nested.stdout.strip())]))
        """)
    )
    for seen in report:
        assert (
            seen["AF_INET"] == 13 and seen["AF_INET6"] == 13 and seen["AF_UNIX"] == 0
        ), report
        assert seen["io_uring_setup"] != 0, report


PULLED = TASK / "checks" / "fixtures" / "pulled-d3bd3d08-v2-trial10"

# sandbox() itself, with only what needs root or Linux stood in: the id it draws is this user's,
# chown is a no-op and lchown gives files to this user (both still demand integer ids, as the real
# calls do: os.lchown raises TypeError for a string before any system call), setpriv is "found", and
# the probes answer as a correct unprivileged process would (the set-id probe with the answer
# given). The prefix it builds is never run here.
SANDBOX_STAND_IN = """
import json, os
from pathlib import Path
import verify
real_lchown = os.lchown


def lchown_as_this_user(path, uid, gid, *args, **kw):
    if not (isinstance(uid, int) and isinstance(gid, int)):
        raise TypeError(f"an integer is required, not {type(uid).__name__}")
    return real_lchown(path, os.getuid(), os.getgid(), *args, **kw)


verify.os.lchown = lchown_as_this_user
u = str(os.getuid())
STATUS = ("Uid:\\t" + "\\t".join([u] * 4) + "\\nGid:\\t" + "\\t".join([u] * 4) + "\\nGroups:\\t\\nNoNewPrivs:\\t1\\n"
          "CapPrm:\\t0000000000000000\\nCapEff:\\t0000000000000000\\nCapAmb:\\t0000000000000000\\n")
LIMITS = ("Max processes             512                  512                  processes\\n"
          "Max file size             268435456            268435456            bytes\\n"
          "Max core file size        0                    0                    bytes\\n")


def probe_answering(set_id_answer):
    def probe(prefix, argv, fallback=None):
        if argv[-1] == "/proc/self/limits":
            return LIMITS
        if argv[-1] == verify.NETWORK_PROBE:
            return json.dumps({"AF_INET": 13, "AF_INET6": 13, "AF_UNIX": 0, "io_uring_setup": 13}) + "\\n"
        if argv[-1] in ("-u", "-g"):
            return set_id_answer + "\\n"
        return STATUS
    return probe


verify.pick_id = lambda maps=None: os.getuid()
verify.os.chown = lambda *args, **kw: None
verify.shutil.which = lambda name: "/usr/bin/id" if name == "id" else "/usr/bin/setpriv"
verify.probe = probe_answering(u)
"""


def test_sandbox_hands_the_run_the_integer_ids_it_drew_and_refuses_a_set_id_escape(
    tmp_path,
):
    """sandbox() returns the ids it drew as integers (os.lchown needs them: the first v2 oracle
    trial on the platform, 2026-11-19, returned the set-id probe's strings instead, and every case
    was a setup error), and refuses a sandbox in which a set-id root file runs as root."""
    report = verifier_call(
        SANDBOX_STAND_IN
        + textwrap.dedent(f"""
        verify.REBUILD = Path({str(tmp_path / "rebuild")!r})
        prefix, ids, found = verify.sandbox()
        verify.probe = probe_answering("0")
        try:
            verify.sandbox()
            escaped = None
        except verify.EvaluationError as exc:
            escaped = str(exc)
        print(json.dumps([prefix[:2], list(ids), [type(value).__name__ for value in ids], sorted(found), escaped]))
    """)
    )
    prefix, ids, kinds, found, escaped = report
    assert (
        prefix == ["setpriv", "--reuid"]
        and ids == [os.getuid(), os.getuid()]
        and kinds == ["int", "int"]
    ), report
    assert (
        found
        and escaped
        and "a set-id root file ran with user and group ('0', '0')" in escaped
    ), report


def test_the_tree_pulled_from_the_v2_oracle_trial_replays_through_the_whole_run(
    tmp_path,
):
    """The mark and record /app/rebuild carried in the first v2 oracle trial on the platform
    (2026-11-19, task ...-d3bd3d08, trial 10: reward 0.0, every case a setup error), replayed on a
    tree of the same shape through main()'s own steps: manifest, record, sandbox (stood in only
    where it needs root or Linux), seal, the tripwires, the cases, the fingerprint and the cleanup.
    The stand-in `carve` answers every case and the privilege-drop prefix is not run."""
    top = tmp_path / "rebuild"
    top.mkdir()
    shutil.copy(PULLED / ".fsmaint", top / ".fsmaint")
    shutil.copy(PULLED / ".fsmaint.json", top / ".fsmaint.json")
    (top / "LICENSE").write_bytes(
        b"MIT License\n".ljust(1086, b".")
    )  # the pulled LICENSE's size
    script = b"#!/bin/sh\necho ok\n"
    (top / "carve").write_bytes(
        script + b"#" * (16216144 - len(script) - 1) + b"\n"
    )  # the pulled binary's size
    (top / "carve").chmod(0o755)
    assert (
        sum(
            path.stat().st_size
            for path in top.iterdir()
            if not path.name.startswith(".")
        )
        == 16217230
    )
    private = tmp_path / "private"
    private.mkdir()
    cases, expected = plain_cases(
        [["a"], ["b"], ["c"], ["d"]], kinds=["document", "snippet", "inline", "command"]
    )
    (private / "cases.json").write_text(json.dumps({"cases": cases}))
    (private / "expected.json").write_text(json.dumps(expected))
    probe = {
        "id": "F1",
        "files": {"page.crv": "# T\n"},
        "argv": ["--probe"],
        "stdin": None,
        "kind": "disagreement",
    }
    (private / "probes.json").write_text(json.dumps({"probes": [probe]}))
    (private / "probes_expected.json").write_text(
        json.dumps({"F1": {"exit": 0, "stdout": "ok\n"}})
    )
    leftovers = tmp_path / "leftovers"
    leftovers.mkdir()
    (tmp_path / "tmp").mkdir()
    report = verifier_call(
        SANDBOX_STAND_IN
        + textwrap.dedent(f"""
        import time
        verify.REBUILD = Path({str(top)!r})
        verify.PROGRAM = verify.REBUILD / "carve"
        verify.runcases.WORKSPACE = Path({str(tmp_path / "tmp" / "carve-case")!r})
        verify.runcases.HOME = Path({str(tmp_path / "tmp" / "carve-home")!r})
        verify.runcases.TEMP = Path({str(tmp_path / "tmp" / "carve-tmp")!r})
        verify.LEFTOVER_DIRS[:] = [{str(leftovers)!r}]
        verify.kill_user = lambda uid: None
        verify.remove_ipc = lambda *args, **kw: None
        verify.PREEXEC = verify.runcases.limit
        notes, refused = verify.manifest(verify.REBUILD)
        record = verify.manifest_record(verify.REBUILD)
        prefix, ids, limits = verify.sandbox()
        network = verify.network_denied(prefix)
        verify.seal(verify.REBUILD, (os.getuid(), os.getgid()))   # main() seals to root, itself; here to this user
        fetched = verify.fetched_build(verify.REBUILD, verify.upstream_builds())
        cutoff_at = time.monotonic() + 600
        private = Path({str(private)!r})
        metrics = verify.run_cases(verify.PROGRAM, private, [], ids, cutoff_at)
        metrics["fingerprint"] = verify.fingerprint(verify.PROGRAM, private, [], ids)
        verify.final_cleanup(ids[0], time.monotonic() + 30)
        print(json.dumps([notes, refused, record, list(ids), fetched, metrics]))
    """)
    )
    notes, refused, record, ids, fetched, metrics = report
    assert (
        notes == []
        and refused is False
        and fetched is None
        and ids == [os.getuid(), os.getuid()]
    ), report[:5]
    assert (
        record["listed"] == "listed 2 16217230"
        and record["entries_listed"] == 2
        and record["listing_complete"] is True
    )
    assert "any_open" not in record and record["end_from"] == "start"
    assert (
        record["process_count"] == 0
        and record["kill_passes"] == 0
        and record["late_entries"] == 0
    ), record
    assert record["flags"] == [], record["flags"]
    assert (
        metrics["cases_run"] == 4
        and metrics["setup_errors"] == 0
        and metrics["cases_passed"] == 4
    ), metrics
    assert metrics["reward"] == 1.0 and metrics["fingerprint"] == {
        "total": 1,
        "matches_original": 1,
        "by_kind": {"disagreement": {"total": 1, "matches": 1}},
    }, metrics


def test_a_set_id_file_gains_nothing(tmp_path):
    """The submission loses its set-id bits and its write permission before anything runs, and the
    privilege check refuses a process that keeps no_new_privs off, an id, a group or a capability."""
    top = tmp_path / "rebuild"
    (top / "lib").mkdir(parents=True)
    for name, mode in (
        ("carve", 0o4755),
        ("lib/helper", 0o2775),
        ("lib/data", 0o4666),
        ("lib", 0o1777),
    ):
        (top / name).touch() if name != "lib" else None
        (top / name).chmod(mode)
    os.mkfifo(top / "lib" / "pipe")
    (top / "link").symlink_to("/etc/passwd")
    report = verifier_call(
        textwrap.dedent(f"""
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
    """)
    )
    good, bad, no_new_privs, by_prctl = report
    assert good == [] and all(problems for problems in bad) and no_new_privs
    assert by_prctl[0] == [] and all(
        problems == ["no_new_privs is not set"] for problems in by_prctl[1:]
    )
    modes = {
        path.relative_to(top).as_posix(): os.lstat(path).st_mode & 0o7777
        for path in [top, *top.rglob("*")]
    }
    assert modes == {
        ".": 0o755,
        "carve": 0o755,
        "lib": 0o755,
        "lib/helper": 0o755,
        "lib/data": 0o644,
        "link": modes["link"],
    }
    assert (top / "link").is_symlink()


def test_nothing_a_submission_writes_reaches_a_later_case(tmp_path):
    """Each run has a new workspace, HOME and TMPDIR, and what the sandbox user left anywhere it
    can write (here `shared`, standing for /tmp and the other world-writable directories) is gone
    before the next case. kill_user is left out: here the sandbox user is the one running pytest."""
    shared = tmp_path / "shared"
    shared.mkdir()
    program = tmp_path / "carve"
    program.write_text(
        textwrap.dedent(f"""\
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
    """)
    )
    program.chmod(0o755)
    private = tmp_path / "private"
    private.mkdir()
    cases, expected = plain_cases([["a"], ["b"], ["c"]])
    (private / "cases.json").write_text(json.dumps({"cases": cases}))
    (private / "expected.json").write_text(json.dumps(expected))
    ipc = tmp_path / "sysvipc"
    ipc.mkdir()
    (ipc / "shm").write_text(
        "key shmid perms size cpid lpid nattch uid gid cuid cgid\n"
        f"0 7 600 4096 1 1 0 {os.getuid()} 0 {os.getuid()} 0\n0 8 600 4096 1 1 0 4242 0 4242 0\n"
    )
    metrics, removed = verifier_call(
        textwrap.dedent(f"""
        import json, os
        from pathlib import Path
        import verify
        verify.runcases.WORKSPACE = Path({str(tmp_path / "carve-case")!r})
        verify.runcases.HOME = Path({str(tmp_path / "carve-home")!r})
        verify.runcases.TEMP = Path({str(tmp_path / "carve-tmp")!r})
        verify.LEFTOVER_DIRS[:] = [{str(shared)!r}]
        verify.kill_user = lambda uid: None
        verify.PREEXEC = verify.runcases.limit
        removed, real_run = [], verify.subprocess.run
        verify.subprocess.run = lambda argv, **kw: removed.append(argv) if argv[0] == "ipcrm" else real_run(argv, **kw)
        root = Path({str(ipc)!r})
        verify.remove_ipc = (lambda real: lambda uid: real(uid, root))(verify.remove_ipc)
        metrics = verify.run_cases(Path({str(program)!r}), Path({str(private)!r}), [], (os.getuid(), os.getgid()))
        verify.final_cleanup(os.getuid(), __import__("time").monotonic() + 30)
        print(json.dumps([metrics, removed]))
    """)
    )
    assert metrics["cases_passed"] == 3, metrics
    assert removed and all(argv == ["ipcrm", "-m", "7"] for argv in removed), removed
    assert list(shared.iterdir()) == [], "the last case's files outlived the evaluation"


def test_a_deep_tree_never_turns_grading_into_an_error(tmp_path):
    script = 'case "$1" in deep) i=0; while [ $i -lt 1500 ]; do mkdir d && cd d || break; i=$((i+1)); done;; esac\necho ok\n'
    cases, expected = plain_cases(
        [["deep"], ["after"], ["deep"], ["last"]],
        kinds=["deep", "after", "deep", "last"],
    )
    metrics = run_verifier(tmp_path, script, cases, expected)
    assert metrics["cases_run"] == 4 and metrics["setup_errors"] == 0, metrics
    assert (
        metrics["by_kind"]["after"]["passed"] == 1
        and metrics["by_kind"]["last"]["passed"] == 1
    ), metrics
    assert not list((tmp_path / "tmp").rglob("d")), "the deep tree was left behind"


def test_hashing_a_submission_is_bounded_and_never_raises(tmp_path):
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    (tmp_path / "linked").symlink_to(fifo)
    data = b"x" * ((1 << 20) + 77)
    (tmp_path / "carve").write_bytes(data)
    out = verifier_call(
        textwrap.dedent(f"""
        import json, verify
        from pathlib import Path
        top = Path({str(tmp_path)!r})
        verify.MAX_PROGRAM = 1 << 22
        big = top / "big"
        with open(big, "wb") as handle:
            handle.truncate((1 << 22) + 1)
        print(json.dumps([verify.identity(top / "linked"), verify.identity(top / "fifo"), verify.identity(top / "carve"),
                          verify.identity(big), verify.identity(top / "missing")]))
    """)
    )
    linked, fifo_result, good, big, missing = out
    assert linked == {"error": "not a regular file"} and fifo_result == {
        "error": "not a regular file"
    }
    assert good == {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    assert big["error"] == "too large to hash" and missing == {
        "error": "FileNotFoundError"
    }


def test_cleanup_cost_does_not_grow_with_what_a_run_leaves(tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir()
    program = tmp_path / "carve"
    program.write_text(
        f'#!/bin/sh\ncd "{shared}" && seq 1 20000 | sed "s/^/$$-/" | xargs mkdir\necho ok\n'
    )
    program.chmod(0o755)
    private = tmp_path / "private"
    private.mkdir()
    cases, expected = plain_cases([[f"c{i}"] for i in range(50)])
    (private / "cases.json").write_text(json.dumps({"cases": cases}))
    (private / "expected.json").write_text(json.dumps(expected))
    elapsed, metrics, calls = verifier_call(
        textwrap.dedent(f"""
        import json, os, time
        from pathlib import Path
        import verify
        verify.runcases.WORKSPACE = Path({str(tmp_path / "carve-case")!r})
        verify.runcases.HOME = Path({str(tmp_path / "carve-home")!r})
        verify.runcases.TEMP = Path({str(tmp_path / "carve-tmp")!r})
        verify.runcases.CASE_SEC = 10
        verify.LEFTOVER_DIRS[:] = [{str(shared)!r}]
        verify.kill_user = lambda uid: None
        verify.PREEXEC = verify.runcases.limit
        verify.MARGIN_SEC = 0.5
        calls, real_run = [], verify.subprocess.run
        verify.subprocess.run = lambda argv, **kw: (calls.append(argv[0]), real_run(argv, **kw))[1]
        started = time.monotonic()
        metrics = verify.run_cases(Path({str(program)!r}), Path({str(private)!r}), [], (os.getuid(), os.getgid()),
                               time.monotonic() + 8)
        print(json.dumps([time.monotonic() - started, metrics, calls]))
    """)
    )
    assert metrics["stopped"] and metrics["cases_run"] < 50, metrics
    assert elapsed < 8 + 10, elapsed
    assert calls.count("find") <= metrics["cases_run"] + 1, "one find per sweep"
    assert calls.count("rm") <= 3 * (metrics["cases_run"] + 1), (
        "rm for the run's own three directories, never per leftover"
    )


def test_the_sandbox_id_is_one_the_namespace_maps(tmp_path):
    for name, text in (
        ("wide", "0 0 4294967295\n"),
        ("rootless", "0 100000 65536\n"),
        ("tight", "0 1000 1\n"),
    ):
        (tmp_path / name).write_text(text)
    ids = verifier_call(
        textwrap.dedent(f"""
        import json, verify
        top = {str(tmp_path)!r}
        print(json.dumps([[verify.pick_id((f"{{top}}/{{name}}", f"{{top}}/{{name}}")) for _ in range(30)]
                          for name in ("wide", "rootless", "tight")]))
    """)
    )
    wide, rootless, tight = ids
    assert (
        all(20000 <= i < 60000 and i != 10001 for i in wide + rootless)
        and len(set(wide)) > 1
    )
    assert tight == [65534] * 30


def test_an_oversized_submission_is_not_run(tmp_path):
    many, big = tmp_path / "many", tmp_path / "big"
    many.mkdir()
    big.mkdir()
    for index in range(30):
        (many / f"f{index}").write_text("x")
    with open(big / "carve", "wb") as handle:
        handle.truncate(5000)
    out = verifier_call(
        textwrap.dedent(f"""
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
    """)
    )
    assert "more than 20 entries" in out[0] and "more than 4096 bytes" in out[1]
    instruction = " ".join((STEP / "instruction.md").read_text().split())
    assert (
        "keep it under 2 GB (2,000,000,000 bytes) and 200,000 files, directories and links, with no "
        "file that has more than 1,000 hard links and no path inside it longer than 2,048 bytes"
    ) in instruction
    assert "adds at most 1 GB and 100,000 files and directories" in instruction
    assert "writes at most 1 MB (1,000,000 bytes) to standard output" in instruction
    hook = HOOK.read_text()
    assert "LIMIT_ENTRIES=200000" in hook and "LIMIT_BYTES=2000000000" in hook
    assert 'PATH_BYTES = int(os.environ.get("FSMAINT_PATH_BYTES", 2048))' in hook
    verify = (TESTS / "verify.py").read_text()
    assert "MAX_ENTRIES = 200_000" in verify and "MAX_BYTES = 2_000_000_000" in verify
    runner = RUNNER.read_text()
    assert "OUTPUT_LIMIT = 1_000_000" in runner and "CASE_SEC = 2\n" in runner


def test_the_sweeps_own_files_do_not_count_against_the_trees_limits(tmp_path):
    """A tree right at the limits stays runnable however large the sweep's record is: the mark and
    the record are the sweep's, so the seal does not count them (a long-path tree's record can pass
    the margin between the sweep's 2,000,000,000 bytes and the verifier's 2 GiB)."""
    top = tmp_path / "rebuild"
    top.mkdir()
    for index in range(5):
        (top / f"f{index}").write_text("x" * 100)
    (top / ".fsmaint").write_text("listed 5 500\n")
    (top / ".fsmaint.json").write_text("{" + '"pad": "' + "y" * 5000 + '"}')
    out = verifier_call(
        textwrap.dedent(f"""
        import json, os, verify
        from pathlib import Path
        verify.MAX_ENTRIES, verify.MAX_BYTES = 5, 500
        try:
            verify.seal(Path({str(top)!r}), (os.getuid(), os.getgid()))
            print(json.dumps("sealed"))
        except verify.EvaluationError as exc:
            print(json.dumps(str(exc)))
    """)
    )
    assert out == "sealed"


def run_measuring(
    top: Path, env: dict[str, str] | None = None, notes_text: str = ""
) -> list[str]:
    """The hook's last block (measuring and marking, as root) alone on `top`, with the link fixing's
    notes `notes_text` and no state, as the hook runs it after the link fixing; the mark's lines."""
    measuring = hook_programs()["measuring"]
    state, notes = top.parent / ".state", top.parent / ".notes"
    state.mkdir(exist_ok=True)
    notes.write_text(notes_text)
    now = f"{time.time()}"
    done = subprocess.run(
        [
            sys.executable,
            "-I",
            "-",
            str(top),
            "200000",
            "2000000000",
            str(notes),
            str(state),
            "1",
            "0",
            now,
            now,
            now,
            "start",
        ],
        check=False,
        input=measuring,
        text=True,
        capture_output=True,
        timeout=300,
        env=dict(os.environ, **(env or {})),
    )
    assert done.returncode == 0, done.stdout + done.stderr
    return (top / ".fsmaint").read_text().splitlines()


def test_a_missing_or_replaced_tree_is_refused_never_an_error(tmp_path):
    """Whatever stands at /app/rebuild when the work ends, the sweep leaves a directory with a mark:
    a link (to a directory elsewhere, whose contents stay where they are), a regular file, or
    nothing at all becomes an empty directory marked refused, which the verifier scores 0."""
    cases = {}
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "carve").write_text("#!/bin/sh\n")
    link = tmp_path / "link" / "rebuild"
    link.parent.mkdir()
    link.symlink_to(elsewhere)
    cases["link"] = link
    plain = tmp_path / "file" / "rebuild"
    plain.parent.mkdir()
    plain.write_text("not a directory")
    cases["file"] = plain
    missing = tmp_path / "missing" / "rebuild"
    missing.parent.mkdir()
    cases["missing"] = missing
    reasons = {
        "link": "/app/rebuild was a link",
        "file": "/app/rebuild was not a directory",
        "missing": "/app/rebuild was missing",
    }
    for name, top in cases.items():
        lines = run_measuring(top)
        assert (
            lines[0] == "refused" and lines[1] == f"{reasons[name]}: it was not copied"
        ), (name, lines)
        assert top.is_dir() and not top.is_symlink(), name
        assert sorted(os.listdir(top)) == [".fsmaint", ".fsmaint.json"], name
    assert (elsewhere / "carve").read_text() == "#!/bin/sh\n", (
        "a link's target is never touched"
    )
    assert any(entry.startswith(".refused.") for entry in os.listdir(link.parent)), (
        "the link itself is moved aside"
    )
    out = verifier_call(
        textwrap.dedent(f"""
        import json, verify
        from pathlib import Path
        print(json.dumps({{name: list(verify.manifest(Path(top))) for name, top in {json.dumps({k: str(v) for k, v in cases.items()})}.items()}}))
    """)
    )
    assert all(out[name][1] is True for name in cases), out


def test_no_reward_exists_until_the_real_end_and_the_reward_comes_first(tmp_path):
    reserved = tmp_path / ".reward.tmp"
    reserved.write_text("--------")
    metrics = tmp_path / "metrics.json"
    metrics.write_text("{}".ljust(4096))
    tree = tmp_path / "root"
    for name in ("tmp", "logs/artifacts/open", "var/tmp"):
        (tree / name).mkdir(parents=True)
        (tree / name).chmod(0o777)
    out = verifier_call(
        textwrap.dedent(f"""
        import json, verify
        from pathlib import Path
        verify.write_in_place(Path({str(reserved)!r}), b"0.731000")
        verify.write_in_place(Path({str(metrics)!r}), b'{{"reward": 0.731}}')
        found = verify.writable_dirs({str(tree)!r})
        rc = verify.runcases
        rc.memory_in_use = lambda group, uid: 0
        # The free figures drop past a limit, but the run's own files are the real measure (QA 10).
        base = {{place: (10 << 30, 1_000_000, 2_000_000) for place in rc.WATCHED_FILESYSTEMS}}
        rc.disk_free = lambda path=None: ((10 << 30) - (2 << 30), 1_000_000, 2_000_000)
        rc.own_use = lambda uid, most_bytes=0, most_files=0: ((2 << 30), 10)   # the run itself holds 2 GiB
        disk = rc.over_limit(1, 999, dict(base))
        rc.own_use = lambda uid, most_bytes=0, most_files=0: (1000, 200_001)   # and 200,001 entries
        files = rc.over_limit(1, 999, dict(base))
        rc.own_use = lambda uid, most_bytes=0, most_files=0: (1000, 10)        # a neighbour wrote the difference
        moved = dict(base)
        neighbour = rc.over_limit(1, 999, moved)
        rc.disk_free = lambda path=None: (-1, -1, -1)
        unknown = rc.over_limit(1, 999, dict(base))
        print(json.dumps([sorted(found), disk, files, neighbour, unknown, moved != base]))
    """)
    )
    found, disk, files, neighbour, unknown, rebased = out
    assert reserved.read_text() == "0.731000" and json.loads(metrics.read_text()) == {
        "reward": 0.731
    }
    assert not any("logs" in path for path in found) and str(tree / "tmp") in found
    assert (
        disk == "disk limit"
        and files == "file limit"
        and neighbour is None
        and unknown is None
    )
    assert rebased, "when the run's own files are within the limits, the baseline moves"
    verify = (TESTS / "verify.py").read_text()
    main = verify[verify.index("def main() -> int:") :]
    order = [
        '(output / ".reward.tmp").write_text("--------")',
        "manifest(REBUILD)",
        "sandbox()",
        "network_denied(prefix)",
        "seal(REBUILD)",
        "fetched_build(REBUILD",
        "probes = fingerprint(PROGRAM",
        "refused = fingerprint_refusal(probes)",
        "metrics = run_cases(PROGRAM",
        "final_cleanup(ids[0], min(cutoff_at",
        'write_in_place(output / ".reward.tmp"',
        'os.replace(output / ".reward.tmp", output / "reward.txt")',
        'output / "metrics.json",',
    ]
    assert [main.index(step) for step in order] == sorted(
        main.index(step) for step in order
    )
    assert '(output / "reward.txt").write_text' not in verify, (
        "no valid reward before the real end"
    )
    assert "if os.geteuid() != 0 or uid == os.geteuid()" in verify, (
        "never kill -1 as the verifier's own uid"
    )


# ---------------------------------------------------------------- delivery

HOOK_ROLES = {
    "List the processes": "processes",
    "Put a mark": "mark",
    "Make /app/rebuild safe": "fixing",
    "Measure /app/rebuild": "measuring",
    "Move aside what": "artifacts",
}


def hook_programs() -> dict[str, str]:
    """The sweep hook's Python blocks by what each does, read from the start of its docstring (the
    end-bound reader has none: "bound")."""
    found = {}
    for program in re.findall(r"<<'EOF'\n(.*?)\nEOF", HOOK.read_text(), re.DOTALL):
        head = program.lstrip('"')
        found[
            next(
                (role for start, role in HOOK_ROLES.items() if head.startswith(start)),
                "bound",
            )
        ] = program
    return found


def run_hook(
    top: Path,
    entries: int = 200000,
    size: int = 2000000000,
    turn_end: float | None = None,
    env: dict[str, str] | None = None,
    turn_from: str = "start",
    started: float | None = None,
    measure: bool = True,
    preexec=None,
    user: str | None = None,
) -> list[str]:
    """The sweep hook's Python blocks on `top`, in the hook's order: the process listing (into a
    state dir), the refused mark, the link fixing (as the agent's user) and the measuring (as root,
    handed the notes and the state; `env`, `preexec` and `started`, the sweep's start, apply to it
    alone; `measure` false stops before it; `user`, where given, stands for `dev` in the measuring's
    last listing of threads). `turn_end` defaults far in the future, so nothing read now is
    flagged as changed after the turn; the mark's lines."""
    programs = hook_programs()
    state = top.parent / f".{top.name}-state"
    state.mkdir(exist_ok=True)
    assert (
        subprocess.run(
            [sys.executable, "-I", "-", str(state / "procs.json")],
            check=False,
            input=programs["processes"],
            text=True,
            capture_output=True,
            timeout=60,
        ).returncode
        == 0
    )
    if "mark" in programs:
        done = subprocess.run(
            [sys.executable, "-I", "-", str(top), str(state)],
            check=False,
            input=programs["mark"],
            text=True,
            capture_output=True,
            timeout=60,
        )
        assert done.returncode == 0, done.stdout + done.stderr
    end = f"{time.time() + 10**9 if turn_end is None else turn_end}"
    notes = top.parent / f".{top.name}-notes"
    with open(notes, "w") as handle:
        done = subprocess.run(
            [
                sys.executable,
                "-I",
                "-",
                str(top),
                str(entries),
                str(size),
                end,
                turn_from,
            ],
            check=False,
            input=programs["fixing"],
            text=True,
            stdout=handle,
            stderr=subprocess.STDOUT,
            timeout=300,
        )
    assert done.returncode == 0, notes.read_text()[-3000:]
    if not measure:
        return (
            (top / ".fsmaint").read_text().splitlines()
            if (top / ".fsmaint").is_file()
            else []
        )
    began = end if started is None else f"{started}"
    done = subprocess.run(
        [
            sys.executable,
            "-I",
            "-",
            str(top),
            str(entries),
            str(size),
            str(notes),
            str(state),
            "1",
            "0",
            began,
            end,
            end,
            turn_from,
        ],
        check=False,
        input=programs["measuring"].replace(
            'getpwnam("dev")', f'getpwnam("{user or "dev"}")'
        ),
        text=True,
        capture_output=True,
        timeout=300,
        env=dict(os.environ, **(env or {})),
        preexec_fn=preexec,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert not notes.exists(), "the notes file is consumed"
    return (top / ".fsmaint").read_text().splitlines()


def platform_copy(top: Path, dest: Path) -> None:
    """The platform's copy of a delivery: a tar of it as it is (links kept, hard links as links; Python's
    tarfile here, where the platform runs GNU tar, so that macOS's tar adds no AppleDouble files), then
    Python's tarfile unpacking it with the `data` filter (harbor's tar_transfer.extract_dir)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    archive = dest.parent / "delivery.tar.gz"
    with tarfile.open(archive, mode="w:gz") as tar:
        tar.add(top, arcname=".")
    dest.mkdir(parents=True)
    with tarfile.open(archive, mode="r:*") as tar:
        tar.extractall(dest, filter="data")


def test_the_collect_hook_lets_honest_deliveries_through_the_copy(tmp_path):
    outside = tmp_path / "usr" / "bin"
    outside.mkdir(parents=True)
    (outside / "python3.12").write_bytes(b"\x7fELF interpreter" * 100)
    (tmp_path / "home-tool").mkdir()
    (tmp_path / "home-tool" / "lib.py").write_text("x = 1\n")
    top = tmp_path / "rebuild"
    venv = top / "venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "lib" / "python3.12" / "site-packages").mkdir(parents=True)
    (venv / "bin" / "python3").symlink_to(
        outside / "python3.12"
    )  # absolute, outside: a venv's interpreter
    (venv / "bin" / "python").symlink_to("python3")  # relative, inside
    (venv / "lib64").symlink_to("lib")
    (venv / "pyvenv.cfg").write_text(f"home = {outside}\n")
    target = top / "src" / "target" / "release"
    (target / "deps").mkdir(parents=True)
    (target / "deps" / "carve-0123abcd").write_bytes(b"\x7fELF binary")
    os.link(target / "deps" / "carve-0123abcd", target / "carve")  # cargo's hard link
    (top / "carve").symlink_to(target / "carve")  # absolute, inside
    (top / "helpers").symlink_to(tmp_path / "home-tool")  # absolute directory outside
    (top / "dangling").symlink_to(tmp_path / "gone")
    os.mkfifo(top / "pipe")
    lines = run_hook(top)
    assert lines[0].startswith("listed ") and any(
        "dangling" in line for line in lines[1:]
    ), lines
    assert any("pipe" in line for line in lines[1:]) and any(
        "a copy of" in line for line in lines[1:]
    ), lines
    assert (
        os.readlink(top / "carve") == "src/target/release/carve"
        and (top / "helpers" / "lib.py").is_file()
    )
    assert (venv / "bin" / "python3").is_file() and not (
        venv / "bin" / "python3"
    ).is_symlink()
    copied = tmp_path / "arrived" / "rebuild"
    platform_copy(top, copied)
    arrived = verifier_call(
        textwrap.dedent(f"""
        import json, verify
        from pathlib import Path
        top = Path({str(copied)!r})
        print(json.dumps([list(verify.arrived(top)), verify.manifest(top)]))
    """)
    )
    _, counted, size = lines[0].split()
    assert arrived[0] == [int(counted), int(size)] and arrived[1][1] is False, (
        lines,
        arrived,
    )
    assert (copied / "carve").read_bytes() == b"\x7fELF binary"
    record = json.loads((copied / ".fsmaint.json").read_text())
    assert (
        record["listed"] == lines[0]
        and record["listing_complete"] is True
        and record["kill_passes"] == 1
    )
    assert not {"hosts", "any_open", "netcheck", "netcheck_open"} & set(record), (
        "the sweep probes no network"
    )
    assert record["late_entries"] == 0 and record["late_paths"] == [], (
        "nothing was written after the (far-future) turn end"
    )
    listed = {item["path"]: item for item in record["entries"]}
    assert len(listed) == int(counted) and listed["carve"]["type"] == "link"
    assert (
        listed["src/target/release/deps/carve-0123abcd"]["sha256"]
        == hashlib.sha256(b"\x7fELF binary").hexdigest()
    )
    assert all("ctime" in item and "mtime" in item for item in record["entries"])
    sources = {copy["path"]: copy for copy in record["copies"]}
    assert "venv/bin/python3" in sources and "helpers" in sources, record["copies"]
    assert all(
        "source_ctime" in copy and "source_uid" in copy for copy in record["copies"]
    ), "each copy records its source"


def test_the_delivery_mark_decides_between_an_error_a_zero_and_grading(tmp_path):
    def delivered(name: str, mark: str | None, files: dict[str, str]) -> Path:
        top = tmp_path / name / "rebuild"
        top.mkdir(parents=True)
        for path, text in files.items():
            (top / path).parent.mkdir(parents=True, exist_ok=True)
            (top / path).write_text(text)
        if mark is not None:
            (top / ".fsmaint").write_text(mark)
        return top

    tops = {
        "empty": delivered("empty", None, {}),
        "unmarked": delivered("unmarked", None, {"carve": "x"}),
        "refused": delivered(
            "refused",
            "refused\nit holds more than 2,000,000,000 bytes: it was not copied\n",
            {},
        ),
        "short": delivered("short", "listed 3 30\n", {"carve": "x"}),
        "whole": delivered(
            "whole",
            "listed 2 4\nremoved pipe: not a file, a directory or a link\n",
            {"a/carve": "xyzw"},
        ),
        "garbled": delivered("garbled", "listed many\n", {"carve": "x"}),
    }
    out = verifier_call(
        textwrap.dedent(f"""
        import json, verify
        from pathlib import Path
        results = {{}}
        for name, top in {json.dumps({k: str(v) for k, v in tops.items()})}.items():
            try:
                results[name] = list(verify.manifest(Path(top)))
            except verify.EvaluationError as exc:
                results[name] = "error: " + str(exc)
        print(json.dumps(results))
    """)
    )
    assert out["empty"].startswith("error: Nothing arrived") and out[
        "unmarked"
    ].startswith("error:")
    assert out["refused"][1] is True and "it was not copied" in out["refused"][0][0]
    assert out["short"].startswith("error: The copy arrived cut short") and out[
        "garbled"
    ].startswith("error:")
    assert out["whole"] == [
        ["sweep: removed pipe: not a file, a directory or a link"],
        False,
    ]
    small = tmp_path / "over" / "rebuild"
    small.mkdir(parents=True)
    for index in range(12):
        (small / f"f{index}").write_text("x" * 100)
    assert run_hook(small, entries=10)[0] == "refused" and sorted(
        os.listdir(small)
    ) == [".fsmaint", ".fsmaint.json"]
    toml = (TASK / "task.toml").read_text()
    assert (
        '[[verifier.collect]]\ncommand = "/usr/local/lib/fsmaint/fsmaint-sweep"' in toml
    )
    for phase in ("setup_begin", "setup_complete"):
        assert (
            f'[[agent.{phase}]]\ncommand = "/usr/local/lib/fsmaint/fsmaint-reserve'
            in toml
        ), phase
    assert 'command = "/usr/local/lib/fsmaint/fsmaint-reserve --begin"' in toml, (
        "setup-complete records when the work began"
    )


def manifest_of(top: Path) -> object:
    """verify.manifest() on `top`, in a process of its own: [notes, refused], or "error: ..." for
    an evaluation error."""
    return verifier_call(
        textwrap.dedent(f"""
        import json, verify
        from pathlib import Path
        try:
            print(json.dumps(list(verify.manifest(Path({str(top)!r})))))
        except verify.EvaluationError as exc:
            print(json.dumps("error: " + str(exc)))
    """)
    )


def test_a_mark_of_any_size_is_read_from_its_start_and_the_sweep_keeps_it_short(
    tmp_path,
):
    """QA 22 F1: the verifier reads the mark's first 64 KiB whatever its size, so a 2 MB mark that
    starts `listed` is graded and one that starts `refused` scores 0 (round 8 took both for no
    mark: an evaluation error). And the sweep writes at most 200 changes and 32 KiB of them into the
    mark, then how many more the record holds: 5,000 pipes with 240-byte names left a 1.4 MB mark."""
    for name, head, files in (
        ("listed", "listed 1 4\n", {"carve": "abcd"}),
        (
            "refused",
            "refused\nit holds more than 200,000 files and directories: it was not copied\n",
            {},
        ),
    ):
        top = tmp_path / name / "rebuild"
        top.mkdir(parents=True)
        for path, text in files.items():
            (top / path).write_text(text)
        (top / ".fsmaint").write_text(
            head + "removed x: not a file, a directory or a link\n" * 50_000
        )
    listed, refused = (
        manifest_of(tmp_path / "listed" / "rebuild"),
        manifest_of(tmp_path / "refused" / "rebuild"),
    )
    assert isinstance(listed, list) and listed[1] is False, str(listed)[:300]
    assert isinstance(refused, list) and refused[1] is True, str(refused)[:300]
    top = tmp_path / "pipes" / "rebuild"
    top.mkdir(parents=True)
    (top / "carve").write_text("#!/bin/sh\n")
    for index in range(5000):
        os.mkfifo(top / f"{index:05d}{'p' * 235}")
    lines = run_hook(top)
    assert lines[0] == "listed 1 10" and (top / ".fsmaint").stat().st_size < 40_000, (
        lines[:3],
        (top / ".fsmaint").stat(),
    )
    assert 100 <= len(lines) <= 202 and re.fullmatch(
        r"and [\d,]+ more changes: see \.fsmaint\.json", lines[-1]
    ), lines[-1]
    record = json.loads((top / ".fsmaint.json").read_text())
    assert (
        sum("not a file, a directory or a link" in line for line in record["notes"])
        == 5000
    )
    assert manifest_of(top)[1] is False


def test_a_path_too_long_to_copy_is_moved_out_and_the_rest_copies(tmp_path):
    """QA 22 F2: an entry whose path in the tree is longer than the bound (2,048 bytes; 600 here,
    since macOS's own 1,024-byte limit would stop this machine's copy first) is moved out with
    everything below it and one note, so every path listed can be measured and copied; round 8
    listed it, and the copy or the verifier's count failed on it."""
    top = tmp_path / "rebuild"
    top.mkdir()
    (top / "carve").write_text("#!/bin/sh\n")
    folder = os.open(top, os.O_RDONLY)
    for _ in range(
        5
    ):  # five levels of 240 bytes, each made from its parent: 1,204 bytes deep
        os.mkdir("d" * 240, dir_fd=folder)
        child = os.open("d" * 240, os.O_RDONLY, dir_fd=folder)
        os.close(folder)
        folder = child
    os.close(os.open("leaf", os.O_WRONLY | os.O_CREAT, 0o644, dir_fd=folder))
    os.close(folder)
    lines = run_hook(top, env={"FSMAINT_PATH_BYTES": "600"})
    record = json.loads((top / ".fsmaint.json").read_text())
    assert (
        lines[0] == "listed 3 10"
        and max(len(item["path"]) for item in record["entries"]) <= 600
    ), (lines, record["entries"])
    assert record["moved_out_long"] == 1 and any(
        "longer than 600 bytes" in line for line in lines[1:]
    ), lines
    copied = tmp_path / "arrived" / "rebuild"
    platform_copy(top, copied)
    assert manifest_of(copied) == [[f"sweep: {line}" for line in lines[1:]][:20], False]


def test_a_long_chain_of_links_is_cut_in_linear_time(tmp_path):
    """QA 22 F3: a chain of 6,000 links (its head at the top, the rest in one directory, the last to
    the program) ended round 8's link fixer with a RecursionError under the image's Python 3.12, and
    its measuring took time quadratic in the chain's length (4.4 s for 2,000 links, 17.9 s for 4,000
    here; about 22,000 passed the hook's 600 s). Now the fixer removes a link the system itself
    cannot follow (more in a row than it allows) and points every other straight at the program;
    the measuring alone (as when the fixer is stopped) keeps only a link that leads straight to a
    file or a directory; both take well under a second."""

    def chain(top: Path, count: int = 6000) -> None:
        (top / "sub").mkdir(parents=True)
        (top / "carve").write_text("#!/bin/sh\n")
        (top / "sub" / f"l{count - 1}").symlink_to("../carve")
        for index in range(count - 2, 0, -1):
            (top / "sub" / f"l{index}").symlink_to(f"l{index + 1}")
        (top / "l0").symlink_to("sub/l1")

    top = tmp_path / "rebuild"
    chain(top)
    started = time.monotonic()
    lines = run_hook(top)
    elapsed = time.monotonic() - started
    kept = [path for path in (top / "sub").iterdir() if path.is_symlink()]
    assert lines[0] == f"listed {len(kept) + 2} 10" and not os.path.lexists(
        top / "l0"
    ), lines[:4]
    assert kept and all(os.readlink(path) == "../carve" for path in kept), [
        os.readlink(path) for path in kept[:5]
    ]
    assert elapsed < 60, elapsed
    copied = tmp_path / "arrived" / "rebuild"
    platform_copy(top, copied)
    assert manifest_of(copied)[1] is False
    alone = tmp_path / "alone" / "rebuild"
    chain(alone)
    started = time.monotonic()
    lines = run_measuring(alone)
    elapsed = time.monotonic() - started
    assert lines[0] == "listed 3 10" and [
        path.name for path in (alone / "sub").iterdir()
    ] == ["l5999"], lines[:3]
    assert elapsed < 15, elapsed


def test_a_sweep_that_stops_early_leaves_an_empty_tree_marked_refused(tmp_path):
    """QA 22 F3 and F4(a): the mark says `refused` before the links are fixed, and the measuring
    moves the tree out of /app/rebuild before anything slow. A measuring killed after that (here
    while it waits on its notes), or one whose every write fails (as on a disk filled to the last
    block), leaves /app/rebuild holding that refused mark alone; one past its time (480 s from the
    sweep's start, round 10: the moving out included) leaves the tree where it was under a refused
    mark. The verifier scores each 0; round 8 left the tree unmarked (an evaluation error) or
    crashed on the mark's write."""

    def tree(name: str) -> Path:
        top = tmp_path / name / "rebuild"
        (top / "sub").mkdir(parents=True)
        (top / "carve").write_text("#!/bin/sh\n")
        (top / "sub" / "x").symlink_to("../carve")
        os.mkfifo(top / "sub" / "pipe")
        return top

    killed = tree("killed")
    run_hook(killed, measure=False)
    notes = killed.parent / "notes-fifo"
    os.mkfifo(notes)
    now = f"{time.time()}"
    measuring = subprocess.Popen(
        [
            sys.executable,
            "-I",
            "-",
            str(killed),
            "200000",
            "2000000000",
            str(notes),
            str(killed.parent / ".rebuild-state"),
            "1",
            "0",
            now,
            now,
            now,
            "start",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    measuring.stdin.write(hook_programs()["measuring"])
    measuring.stdin.close()
    waited = time.monotonic() + 10
    while time.monotonic() < waited and sorted(os.listdir(killed)) != [".fsmaint"]:
        time.sleep(0.05)
    measuring.kill()
    measuring.wait(timeout=30)
    assert sorted(os.listdir(killed)) == [".fsmaint"], sorted(os.listdir(killed))
    assert (
        killed / ".fsmaint"
    ).read_text() == "refused\nthe sweep did not finish: it was not copied\n"
    late = tree("late")
    lines = run_hook(late, started=time.time() - 500)
    assert lines[:2] == [
        "refused",
        "it was not moved out within 480 seconds: it was not copied",
    ], lines
    full = tree("full")
    lines = run_hook(
        full, preexec=lambda: resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    )
    assert lines == ["refused", "the sweep did not finish: it was not copied"], lines
    assert sorted(os.listdir(late)) == [
        ".fsmaint",
        ".fsmaint.json",
        "carve",
        "sub",
    ] and sorted(os.listdir(full)) == [".fsmaint"]
    assert all(manifest_of(top)[1] is True for top in (killed, late, full))


def test_a_tree_the_disk_has_no_room_to_pack_is_refused(tmp_path):
    """QA 22 F4(b): the copy first packs the tree into /tmp on the same machine, so a tree the disk
    has too little room left to pack (its bytes, a header and a long name per entry, the record
    twice and the mark, then 32 MiB and 16 inodes besides; each margin raised here past any disk in
    turn) is refused with the figures, and only its mark and record are left to pack; round 8 listed
    it, and the pack failed."""
    for name, env in (
        ("bytes", {"FSMAINT_PACK_ROOM": str(10**18)}),
        ("inodes", {"FSMAINT_PACK_INODES": str(10**15)}),
    ):
        top = tmp_path / name / "rebuild"
        top.mkdir(parents=True)
        (top / "carve").write_text("#!/bin/sh\n")
        lines = run_hook(top, env=env)
        assert lines[0] == "refused" and re.fullmatch(
            r"the disk had \d+ bytes and \d+ inodes free, too few to pack it into "
            r"/tmp \(about [\d,]+ bytes and \d+ inodes\): it was not copied",
            lines[1],
        ), (name, lines)
        assert ".fsmaint" in os.listdir(top) and set(os.listdir(top)) <= {
            ".fsmaint",
            ".fsmaint.json",
        }, os.listdir(top)
        assert manifest_of(top)[1] is True
    hook = HOOK.read_text()
    assert (
        'PACK_DIR = "/tmp"' in hook
        and "(info.f_bavail * info.f_frsize if info.f_blocks else None), (info.f_favail if info.f_files else None)"
        in hook
    ), "a filesystem that reports no size, or no inode table, refuses nothing for it"


def test_every_kept_link_stays_inside_wherever_the_tree_is_unpacked(tmp_path):
    """QA 22 F5: a link that climbs above / and comes back in resolves inside where the tree stands,
    but outside when the copy unpacks the tree deeper (round 8 kept it, and the copy stopped). The
    measuring, here without the link fixing (as when that is stopped or cannot read a directory),
    rewrites every link it keeps as the shortest relative path inside, an absolute one into the
    tree too, and removes one that leads through another link."""
    top = tmp_path / "rebuild"
    (top / "zz").mkdir(parents=True)
    (top / "carve").write_text("#!/bin/sh\n")
    (top / "zz" / "x").symlink_to(
        "../" * (len(top.parts) + 2) + str(top).lstrip("/") + "/carve"
    )
    (top / "abs").symlink_to(top / "carve")
    (top / "here").symlink_to(".")
    (top / "via").symlink_to("here/carve")
    lines = run_measuring(top)
    assert lines[0] == "listed 5 10", lines
    assert (
        os.readlink(top / "zz" / "x") == "../carve"
        and os.readlink(top / "abs") == "carve"
    ), lines
    assert os.readlink(top / "here") == "." and not os.path.lexists(top / "via"), lines
    copied = tmp_path / "arrived" / "rebuild"
    platform_copy(top, copied)
    assert (
        manifest_of(copied)[1] is False
        and (copied / "zz" / "x").read_text() == "#!/bin/sh\n"
    )


def test_the_sweep_sets_aside_what_holds_its_names_and_reports_a_failure_once(tmp_path):
    """QA 22 F6, F8-F10: a directory under the mark's name is set aside, never a crash (the measuring
    alone, as when every step before it failed), and the shell removes what it cannot set aside
    instead of exiting unmarked; the link fixer's notes go to the root-only state directory, never
    to /dev/null that root then unlinks; an entry the fixer cannot fix is reported once, not once
    per pass; the verifier's note for a refused tree says the sweep refused it."""
    top = tmp_path / "rebuild"
    (top / ".fsmaint" / "inner").mkdir(parents=True)
    (top / "carve").write_text("#!/bin/sh\n")
    assert run_measuring(top)[0] == "listed 1 10" and (top / ".fsmaint").is_file()
    hook = HOOK.read_text()
    assert "|| exit 0" not in hook and '|| rm -rf -- "/app/rebuild/$name"' in hook
    assert 'notes="$STATE/notes"' in hook and "notes=/dev/null" not in hook
    assert "so no depth hides anything" not in hook
    stuck = tmp_path / "stuck" / "rebuild"
    (stuck / "ro").mkdir(parents=True)
    (stuck / "carve").write_text("x")
    (stuck / "ro" / "abs").symlink_to(stuck / "carve")
    (stuck / "ro").chmod(0o555)
    try:
        done = subprocess.run(
            [
                sys.executable,
                "-I",
                "-",
                str(stuck),
                "200000",
                "2000000000",
                f"{time.time() + 10**9}",
                "start",
            ],
            check=False,
            input=hook_programs()["fixing"],
            text=True,
            capture_output=True,
            timeout=120,
        )
    finally:
        (stuck / "ro").chmod(0o755)
    said = [line for line in done.stdout.splitlines() if "ro/abs" in line]
    assert done.returncode == 0 and len(said) == 1, done.stdout[-2000:]
    assert (
        'refused = "the sweep refused the tree: not run" if refused_tree else None'
        in (TESTS / "verify.py").read_text()
    )


# ---------------------------------------------------------------- round 10: where the sweep got to


def hook_shell(name: str) -> str:
    """A part of the sweep hook's shell, by name: "progress" (the function that writes where the
    sweep got to), "processes" (the functions that find, count and signal the processes of `dev`),
    "freeze" and "kill" (the two phases). The hook of round 9 and before had no functions, and its
    phases were loops of 50 and 100 passes; those are returned for them, so the checks below can
    show how that hook behaved."""
    hook = HOOK.read_text()
    patterns = {
        "progress": r"progress\(\) \{[^\n]*\n.*?\n\}\n",
        "processes": r"TASKS=\$\(cat <<'TASKS'\n.*?\nas_dev\(\) \{[^\n]*\n.*?\n\}\n",
        "freeze": r"as_dev kill -STOP -1\nfroze=1\n.*?\ndone\n",
        "kill": r"as_dev kill -9 -1\n.*?> \"\$STATE/kill\.json\"\n",
    }
    found = re.search(patterns[name], hook, re.DOTALL)
    if found:
        return found.group(0)
    old = {
        "progress": r"(?!)",
        "processes": r"(?!)",
        "freeze": r"for _ in \$\(seq 1 50\); do\n.*?\ndone\n",
        "kill": r"passes=0\n.*?\nleft=\$\(.*?\n",
    }
    found = re.search(old[name], hook, re.DOTALL)
    return found.group(0) if found else ""


def stand_in_commands(folder: Path) -> dict[str, str]:
    """A PATH whose pkill, setpriv and kill do nothing: the phases run here signal no process."""
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("pkill", "setpriv", "kill"):
        (folder / name).write_text("#!/bin/sh\nexit 0\n")
        (folder / name).chmod(0o755)
    return dict(os.environ, PATH=f"{folder}:{os.environ['PATH']}")


def stand_in_proc(top: Path, processes: dict[int, list[tuple[int, str, int]]]) -> Path:
    """A /proc holding `processes`: for each pid, its threads as (tid, state, uid), the main thread
    being the one whose tid is the pid; only what the sweep reads (the status of each process and
    of each of its tasks, and its command line)."""
    for pid, threads in processes.items():
        for tid, state, uid in threads:
            folder = top / str(pid) / "task" / str(tid)
            folder.mkdir(parents=True, exist_ok=True)
            status = f"Name:\tstand-in\nState:\t{state} (x)\nPPid:\t1\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\n"
            (folder / "status").write_text(status)
            if tid == pid:
                (top / str(pid) / "status").write_text(status)
        (top / str(pid) / "cmdline").write_bytes(b"stand-in\0")
    return top


def test_the_sweep_says_it_began_first_and_marks_the_tree_before_ending_processes(
    tmp_path,
):
    """QA 23 N1 (W1) and the coordinator's points 1 and 3: before anything else the sweep writes, in
    place into the 4,096 bytes fsmaint-reserve made for it (no new room needed), that it has begun;
    that file is copied beside the tree as an artifact of its own. Right after the freeze it gives
    back the reserve, sets aside what holds the mark's or the record's name, and puts the refused
    mark in; only then does it list and end the processes. Round 9 marked the tree after the kill
    loop and had no such file."""
    hook = HOOK.read_text()
    begun = hook.find('progress "{\\"stage\\": \\"started\\"')
    marks = hook.find('"""Put a mark into /app/rebuild')
    assert begun != -1 and marks != -1, "the sweep says it began, and marks the tree"
    assert (
        begun
        < hook.index("as_dev kill -STOP -1")
        < hook.index('rm -f "$STATE/room"')
        < hook.index("for name in .fsmaint .fsmaint.json")
        < marks
        < hook.index('"""List the processes of the user')
        < hook.index("as_dev kill -9 -1")
    ), "began, then freeze, reserve back, set aside, mark, list, end"
    assert (
        "printf '%-4095s\\n' '{\"stage\": \"setup\"}'" in SETUP.read_text()
        and '"$STATE/out"' in SETUP.read_text()
    )
    assert (
        'artifacts = ["/app/rebuild", "/var/lib/fsmaint/out"]'
        in (TASK / "task.toml").read_text()
    )
    out = tmp_path / "out"
    out.mkdir()
    (out / "sweep.json").write_text('{"stage": "setup"}'.ljust(4095) + "\n")
    inode = (out / "sweep.json").stat().st_ino
    done = subprocess.run(
        [
            "sh",
            "-c",
            f'OUT="{out}"\n'
            + hook_shell("progress")
            + 'progress \'{"stage": "started"}\'\n',
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    data = (out / "sweep.json").read_bytes()
    assert (
        done.returncode == 0
        and len(data) == 4096
        and json.loads(data) == {"stage": "started"}
    ), (done.stderr, data[:80])
    assert (out / "sweep.json").stat().st_ino == inode, "written in place"


def test_the_kill_phase_counts_live_threads_and_ends_in_time(tmp_path):
    """Both phases make one pass whatever a listing says, then repeat while a thread of `dev` is
    still running (the freeze) or alive (the ending): threads are read from /proc/<pid>/task, so a
    process whose main thread has exited (a zombie leader) while another thread runs counts as
    alive, and a zombie with no live thread does not. Each listing and signal has PROBE seconds,
    each phase a set time, and kill.json records the passes, whether a phase ran out and how many
    threads were left. Here with stand-in commands that signal nothing and a stand-in /proc (the
    sweep's user is this one): zombies only, other users' threads, a zombie leader with a live
    thread, and a /proc that cannot be read."""
    uid = os.getuid()
    me = pwd.getpwuid(uid).pw_name

    def phases(
        name: str, proc: Path
    ) -> tuple[subprocess.CompletedProcess, float, Path]:
        state = tmp_path / name
        state.mkdir()
        script = (
            f'STATE="{state}"\nPROBE=5\nFREEZE=2\nENDING=3\nPROC="{proc}"\n'
            + hook_shell("processes").replace('getpwnam("dev")', f'getpwnam("{me}")')
            + hook_shell("freeze")
            + hook_shell("kill")
            + 'echo "passes=$passes left=$left"\n'
        )
        began = time.monotonic()
        try:
            done = subprocess.run(
                ["sh", "-c", script],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
                env=stand_in_commands(tmp_path / f"{name}-bin"),
            )
        except subprocess.TimeoutExpired:
            done = subprocess.CompletedProcess(
                script, -1, "", "the phases ran past 60 s"
            )
        return done, time.monotonic() - began, state

    other = uid + 1
    quiet = {
        "zombies": {
            4242: [(4242, "Z", uid)],
            4250: [(4250, "Z", uid), (4251, "X", uid)],
        },
        "others": {77: [(77, "R", other), (78, "S", other)], 4242: [(4242, "Z", uid)]},
    }
    for name, processes in quiet.items():
        done, elapsed, state = phases(
            name, stand_in_proc(tmp_path / f"{name}-proc", processes)
        )
        assert done.stdout.split() == ["passes=1", "left=0"] and elapsed < 5, (
            name,
            done.stdout,
            done.stderr,
            elapsed,
        )
        assert json.loads((state / "kill.json").read_text()) == {
            "freeze_passes": 1,
            "freeze_ran_out": False,
            "kill_passes": 1,
            "kill_ran_out": False,
            "processes_left": "0",
        }, name
    leader = stand_in_proc(
        tmp_path / "leader-proc", {4242: [(4242, "Z", uid), (4243, "S", uid)]}
    )
    done, elapsed, state = phases("leader", leader)
    ending = json.loads((state / "kill.json").read_text())
    assert (
        ending["freeze_ran_out"] is True
        and ending["kill_ran_out"] is True
        and ending["freeze_passes"] > 1
        and ending["kill_passes"] > 1
        and ending["processes_left"] == "1"
    ), (ending, done.stderr)
    assert elapsed < 30, elapsed
    unreadable = tmp_path / "not-a-proc"
    unreadable.write_text("")
    done, elapsed, state = phases("unreadable", unreadable)
    ending = json.loads((state / "kill.json").read_text())
    assert (
        ending["freeze_ran_out"] is True
        and ending["kill_ran_out"] is True
        and ending["processes_left"] == "unknown"
    ), (ending, done.stderr)
    assert elapsed < 30, elapsed
    hook = HOOK.read_text()
    assert "pgrep" not in hook, "no listing by the main thread's state"
    assert hook.index("as_dev kill -STOP -1\nfroze=1") < hook.index(
        "while alive T,t,Z,X"
    )
    assert hook.index("as_dev kill -9 -1\n") < hook.index("while alive Z,X")


def test_a_thread_left_alive_when_the_tree_is_listed_refuses_it(tmp_path):
    """Just before it writes the listing, the measuring lists the threads of `dev` again: one left
    alive (a process whose main thread had exited, with another thread running) could change the
    tree while it is packed, so the tree is refused; zombies alone are no reason to refuse."""
    me = pwd.getpwuid(os.getuid()).pw_name
    results = {}
    for name, threads in (
        ("zombies", [(4242, "Z", os.getuid())]),
        ("live thread", [(4242, "Z", os.getuid()), (4243, "S", os.getuid())]),
    ):
        proc = stand_in_proc(tmp_path / f"{name}-proc", {4242: threads})
        top = tmp_path / name / "rebuild"
        top.mkdir(parents=True)
        (top / "carve").write_text("#!/bin/sh\nexit 0\n")
        lines = run_hook(top, env={"FSMAINT_PROC": str(proc)}, user=me)
        results[name] = (lines, json.loads((top / ".fsmaint.json").read_text()))
    lines, record = results["zombies"]
    assert lines[0].startswith("listed 1 ") and record["threads_left"] == 0, lines
    lines, record = results["live thread"]
    assert (
        lines[:2]
        == [
            "refused",
            "1 threads of the session were still alive after they were ended: it was not copied",
        ]
        and record["threads_left"] == 1
    ), lines


def platform_copy_partial(top: Path, dest: Path) -> str | None:
    """The platform's copy as harbor makes it: a tar of the tree (links and pipes kept), unpacked
    with the `data` filter; a member the filter refuses stops the unpacking, and what was unpacked
    before it is what goes on (harbor records the artifact as failed and uploads that part). The
    error's name, or None."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    archive = dest.parent / f"{dest.parent.name}.tar.gz"
    with tarfile.open(archive, mode="w:gz") as tar:
        tar.add(top, arcname=".")
    dest.mkdir(parents=True)
    try:
        with tarfile.open(archive, mode="r:*") as tar:
            tar.extractall(dest, filter="data")
    except (tarfile.TarError, OSError) as exc:
        return type(exc).__name__
    return None


def manifest_given(top: Path, state: Path | None) -> object:
    """verify.manifest() on `top` with the sweep's state read from `state`, in a process of its own:
    [notes, refused], or "error: ..."."""
    return verifier_call(
        textwrap.dedent(f"""
        import json, verify
        from pathlib import Path
        verify.SWEEP_STATE = Path({str(state or top.parent / "no-state.json")!r})
        try:
            print(json.dumps(list(verify.manifest(Path({str(top)!r})))))
        except verify.EvaluationError as exc:
            print(json.dumps("error: " + str(exc)))
    """)
    )


def test_whatever_arrives_after_a_sweep_that_did_not_finish_scores_zero(tmp_path):
    """QA 23 N1 (W2): a hook that dies after the refused mark but before the tree is moved out
    leaves the tree in place, as the session left it; its copy stops on the first pipe, absolute
    link or link that climbs out (here named to come ahead of the mark), so the mark may not arrive
    or nothing may. Round 9's verifier called that the copy failing (an error). The sweep's own file,
    copied beside the tree, says it began and not that it finished, so the verifier refuses whatever
    arrived, with a note. After a sweep that said it was done, a missing arrival stays an error (the
    copy or the machine), unless processes of the session were still alive; with no word from the
    sweep at all it stays an error too."""
    out = tmp_path / "out"
    out.mkdir()
    state = out / "sweep.json"
    state.write_text('{"stage": "setup"}'.ljust(4095) + "\n")
    progress = hook_shell("progress")
    if progress:
        subprocess.run(
            [
                "sh",
                "-c",
                f'OUT="{out}"\n' + progress + 'progress \'{"stage": "started"}\'\n',
            ],
            check=True,
            timeout=30,
        )
    else:  # a hook without the file: write what it would say, for the verifier's sake
        state.write_text('{"stage": "started"}'.ljust(4095) + "\n")
    programs = hook_programs()
    arrivals = {}
    for name, bad in (
        ("pipe", "!a/p"),
        ("climbs", "!b/x"),
        ("absolute", "!d/x"),
        ("first", "!p"),
    ):
        top = tmp_path / name / "rebuild"
        top.mkdir(parents=True)
        (top / "carve").write_text("#!/bin/sh\n")
        (top / bad).parent.mkdir(exist_ok=True)
        if name in ("pipe", "first"):
            os.mkfifo(top / bad)
        elif name == "climbs":
            (top / bad).symlink_to(
                "../" * (len(top.parts) + 2) + str(top).lstrip("/") + "/carve"
            )
        else:
            (top / bad).symlink_to("/etc/hosts")
        if (
            "mark" in programs
        ):  # the sweep began, marked the tree refused, and died there
            subprocess.run(
                [sys.executable, "-I", "-", str(top), str(tmp_path / f"{name}-state")],
                check=False,
                input=programs["mark"],
                text=True,
                capture_output=True,
                timeout=60,
            )
        else:
            (top / ".fsmaint").write_text(
                "refused\nthe sweep did not finish: it was not copied\n"
            )
        arrived = tmp_path / name / "arrived" / "rebuild"
        stopped_on = platform_copy_partial(top, arrived)
        arrivals[name] = (
            stopped_on,
            sorted(os.listdir(arrived)),
            manifest_given(arrived, state),
        )
    for name, (stopped_on, listed, verdict) in arrivals.items():
        assert stopped_on is not None, (
            name,
            "the copy should stop on the entry the sweep never took out",
        )
        assert (
            isinstance(verdict, list)
            and verdict[1] is True
            and "did not finish" in verdict[0][0]
        ), (name, listed, verdict)
    assert arrivals["first"][1] == [], (
        "the first member stopped the copy: nothing arrived"
    )
    nothing = tmp_path / "nothing" / "rebuild"
    nothing.mkdir(parents=True)
    for stage, left, expected in (
        ("done", 0, "error: Nothing arrived"),
        ("done", 2, True),
        (None, None, "error: Nothing arrived"),
    ):
        given = None
        if stage is not None:
            given = tmp_path / f"state-{stage}-{left}.json"
            given.write_text(
                json.dumps({"stage": stage, "processes_left": left}).ljust(4095) + "\n"
            )
        verdict = manifest_given(nothing, given)
        assert (
            (verdict[1] is True)
            if expected is True
            else str(verdict).startswith(expected)
        ), (stage, left, verdict)


def test_one_time_limit_covers_the_moving_out_and_the_late_count_is_linear(tmp_path):
    """QA 23 N2 and N5: the moving out had no time limit (a top level of millions of entries took
    minutes), and the count of late entries compared every file with every copy (about 800 s for
    100,000 copies). Now one limit, 480 s from the sweep's start, covers everything from the moving
    out to the moving back: past it, what was not moved out stays where it was, and the file beside
    the tree says the sweep stopped, so whatever arrives is refused. The late count marks copied
    subtrees once, on the way down."""
    top = tmp_path / "late" / "rebuild"
    (top / "sub").mkdir(parents=True)
    (top / "carve").write_text("#!/bin/sh\n")
    os.mkfifo(top / "sub" / "pipe")
    lines = run_hook(top, started=time.time() - 500)
    state = top.parent / ".rebuild-state" / "out" / "sweep.json"
    assert lines[:2] == [
        "refused",
        "it was not moved out within 480 seconds: it was not copied",
    ], lines
    assert {"carve", "sub"} <= set(os.listdir(top)), os.listdir(top)
    assert json.loads(state.read_text())["stage"] == "stopped", state.read_text()[:120]
    assert manifest_given(top, state)[1] is True
    many = tmp_path / "many" / "rebuild"
    many.mkdir(parents=True)
    for index in range(20_000):
        (many / f"f{index:05d}").write_text("x")
    notes = "".join(
        json.dumps(
            {
                "copy": {
                    "path": f"c{index:05d}",
                    "source": "/elsewhere",
                    "target": "/elsewhere",
                    "latest_ctime": 0,
                }
            }
        )
        + "\n"
        for index in range(15_000)
    )
    began = time.monotonic()
    lines = run_measuring(many, notes_text=notes)
    elapsed = time.monotonic() - began
    assert lines[0] == "listed 20000 20000" and elapsed < 12, (lines[:2], elapsed)
    assert (
        hook_programs()["measuring"].count(
            "except (OSError, subprocess.SubprocessError)"
        )
        == 2
    ), "QA 23 N3: a removal that times out is caught, at both of its callers"


def test_the_marks_notes_are_bounded_in_bytes_as_written(tmp_path):
    """QA 23 N6: the mark's 32 KiB were counted in characters, so 1,000 pipes with 4-byte UTF-8 names
    gave a 56,852-byte mark. Now they are counted in bytes as written."""
    top = tmp_path / "rebuild"
    top.mkdir()
    (top / "carve").write_text("#!/bin/sh\n")
    for index in range(1000):
        os.mkfifo(top / (f"{index:03d}" + "\U0001f600" * 60))
    lines = run_hook(top)
    size = (top / ".fsmaint").stat().st_size
    assert lines[0] == "listed 1 10" and size <= 32_768 + 200, (size, len(lines))
    assert re.fullmatch(r"and [\d,]+ more changes: see \.fsmaint\.json", lines[-1]), (
        lines[-1]
    )


# ---------------------------------------------------------------- the recorder

FAKE_CARVE = """#!/usr/bin/env python3
import os, signal, sys
args = [a for a in sys.argv[1:] if not a.startswith("--")]
text = open(args[0]).read() if args and args[0] != "-" else sys.stdin.read()
if "RANDOM" in text: print(os.urandom(4).hex())
elif "HANG" in text:
    import time; time.sleep(5)
elif "PANIC" in text:
    sys.stderr.write("thread 'main' panicked at src/x.rs:1:1\\n"); sys.exit(101)
elif "SEGV" in text: os.kill(os.getpid(), signal.SIGSEGV)
elif "PADDING" in text: print("padded" if "CARVE_PERTURBED_PADDING" in os.environ else "plain")
elif "MISSING" in text: sys.exit(2)
else: print("<p>" + text.strip() + "</p>")
"""


def record(
    tmp_path: Path, cases: list[dict]
) -> tuple[subprocess.CompletedProcess, Path]:
    program = tmp_path / "fake-carve"
    program.write_text(FAKE_CARVE)
    program.chmod(0o755)
    source = tmp_path / "cases.json"
    source.write_text(json.dumps({"cases": cases}))
    driver = textwrap.dedent(f"""
        import sys
        from pathlib import Path
        sys.path.insert(0, {str(RECORDER.parent)!r})
        import runcases
        runcases.WORKSPACE = Path({str(tmp_path / "runs" / "carve-case")!r})
        runcases.HOME = Path({str(tmp_path / "runs" / "carve-home")!r})
        runcases.TEMP = Path({str(tmp_path / "runs" / "carve-tmp")!r})
        import recorder
        sys.argv = ["recorder.py", "record", {str(program)!r}, {str(source)!r}, {str(tmp_path / "expected.json")!r},
                    "--keep", {str(tmp_path / "kept.json")!r}, "--report", {str(tmp_path / "report.json")!r}]
        recorder.main()
    """)
    (tmp_path / "runs").mkdir(exist_ok=True)
    done = subprocess.run(
        [sys.executable, "-B", "-c", driver],
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )
    return done, tmp_path


def doc(i: int, text: str, digest: str | None = None, kind: str = "document") -> dict:
    case = {
        "id": f"P{i:04d}",
        "kind": kind,
        "area": "document",
        "origin": "private",
        "files": {"page.crv": text},
        "argv": ["page.crv"],
        "stdin": None,
        "features": [],
        "djot_exact": False,
        "djot_normalized": False,
    }
    if digest is not None:
        case["answer_sha256"] = digest
    return case


def test_the_recorder_keeps_steady_checked_answers_and_drops_the_rest(tmp_path):
    good = lambda i: hashlib.sha256(f"0\n<p>word{i}</p>\n".encode()).hexdigest()
    done, _ = record(
        tmp_path, [doc(i, f"word{i}", good(i)) for i in range(10)] + [doc(90, "PANIC")]
    )
    assert done.returncode != 0 and "crashed" in done.stdout + done.stderr, (
        "a crash in eleven cases fails the recording"
    )
    cases = [doc(i, f"word{i}", good(i)) for i in range(300)] + [
        doc(1000, "RANDOM"),
        doc(1001, "PANIC"),
        doc(1002, "HANG"),
        doc(1003, "PADDING"),
        doc(1004, "word1004", "0" * 64),
        doc(1005, "MISSING", hashlib.sha256(b"2\n").hexdigest(), kind="cli"),
    ]
    done, out = record(tmp_path, cases)
    assert done.returncode == 0, done.stdout + done.stderr
    report = json.loads((out / "report.json").read_text())
    kept = json.loads((out / "kept.json").read_text())["cases"]
    assert (
        report["unsteady"] == ["P1000"]
        and report["crashed"] == ["P1001"]
        and report["slow"] == ["P1002"]
    )
    assert report["perturbed"] == ["P1003"] and report["differs"] == ["P1004"], (
        "an answer other than the checked one"
    )
    ids = [case["id"] for case in kept]
    assert "P1005" in ids and len(ids) == 301 and len(report["kept_ids_sha256"]) == 64
    assert all("origin" not in case and "answer_sha256" not in case for case in kept), (
        "the final image keeps what grading reads"
    )
    expected = json.loads((out / "expected.json").read_text())
    assert (
        expected["P1005"] == {"exit": 2, "stdout": ""}
        and expected["P0000"]["stdout"] == "<p>word0</p>\n"
    )


def test_selection_drops_shared_answers_answers_in_the_input_and_free_cases():
    report = verifier_call(
        textwrap.dedent("""
        import json
        from verifier import recorder
        case = lambda i, kind, text="x": {"id": f"P{i:04d}", "kind": kind, "files": {"page.crv": text}, "argv": ["page.crv"],
                                          "stdin": None}
        cases, outputs = [], {}
        for i in range(700):   # snippets: 40 render an empty document, the rest a paragraph of their own
            cases.append(case(i, "snippet"))
            outputs[cases[-1]["id"]] = {"exit": 0, "stdout": "\\n"} if i < 40 else {"exit": 0, "stdout": f"<p>line {i}</p>\\n"}
        for i in range(700, 1000):   # documents: 60 share one answer, the rest have their own
            cases.append(case(i, "document"))
            outputs[cases[-1]["id"]] = {"exit": 0, "stdout": "<p>same</p>\\n" if i < 760 else f"<h1>{i}</h1>\\n"}
        cases.append(case(1000, "construct", "```=html\\n<div>a raw block that is long</div>\\n```\\n"))
        outputs["P1000"] = {"exit": 0, "stdout": "<div>a raw block that is long</div>\\n"}
        for i in range(1001, 1021):
            cases.append(case(i, "cli"))
            outputs[cases[-1]["id"]] = {"exit": 2, "stdout": ""}
        kept, dropped = recorder.select(cases, outputs)
        free = recorder.free_cases(kept, outputs)
        print(json.dumps({"kept": len(kept), "dropped": {k: len(v) for k, v in dropped.items()},
                          "quoted": dropped.get("input holds the answer"), "free": sum(map(len, free.values())),
                          "cli": sum(1 for c in kept if c["kind"] == "cli")}))
    """)
    )
    assert report["quoted"] == ["P1000"] and report["cli"] == 20, (
        "the command-line cases are never dropped"
    )
    assert report["dropped"]["answer shared by many cases"] > 0
    assert report["free"] <= 0.05 * report["kept"], report
    assert report["kept"] > 900


def test_the_recording_report_counts_kinds_baselines_and_the_djot_engine(tmp_path):
    run = {"files": {"page.crv": "x"}, "argv": ["page.crv"], "stdin": None}
    kept = [
        dict(
            run,
            id="P1",
            kind="document",
            area="document",
            features=["tables"],
            djot_exact=True,
            djot_normalized=True,
        ),
        dict(
            run,
            id="P2",
            kind="snippet",
            area="layout",
            features=["smart-typography"],
            djot_exact=False,
            djot_normalized=True,
        ),
        dict(
            run,
            id="P3",
            kind="snippet",
            area="inline",
            features=[],
            djot_exact=False,
            djot_normalized=False,
        ),
        dict(
            run,
            id="P4",
            kind="construct",
            area="block",
            features=["comments"],
            djot_exact=False,
            djot_normalized=False,
        ),
        {
            "id": "P9",
            "kind": "cli",
            "files": {},
            "argv": ["missing.crv"],
            "stdin": None,
        },
    ]
    cases = [dict(case, settled="as generated", model="agrees") for case in kept] + [
        dict(run, id="P5", kind="mutant")
    ]
    expected = {
        "P1": {"exit": 0, "stdout": "<table></table>\n"},
        "P2": {"exit": 0, "stdout": "\n"},
        "P3": {"exit": 0, "stdout": "\n"},
        "P4": {"exit": 0, "stdout": "<p>c</p>\n"},
        "P9": {"exit": 2, "stdout": ""},
    }
    seconds = {i: [0.1, 0.2] for i in ("P1", "P2", "P3", "P4", "P9")}
    timing = {
        "keep_seconds": 1.0,
        "keep_cpu": 0.25,
        "seconds": dict(seconds, P5=[0.1, 2]),
        "slow": [],
        "unsteady": ["P5"],
        "crashed": [],
        "differs": [],
        "dropped": {},
    }
    for name, data in (
        ("cases.json", {"cases": cases}),
        ("kept.json", {"cases": kept}),
        ("expected.json", expected),
        ("timing.json", timing),
    ):
        (tmp_path / name).write_text(json.dumps(data))
    (tmp_path / "build.txt").write_text("version carve-rs 0.1.14\nsha256 ab\n")
    subprocess.run(
        [
            sys.executable,
            "-B",
            str(TESTS / "verifier" / "recording.py"),
            *(
                str(tmp_path / name)
                for name in (
                    "cases.json",
                    "kept.json",
                    "expected.json",
                    "timing.json",
                    "out.json",
                )
            ),
            "--build",
            str(tmp_path / "build.txt"),
        ],
        check=True,
        capture_output=True,
        timeout=60,
        cwd=TESTS / "verifier",
    )
    report = json.loads((tmp_path / "out.json").read_text())
    assert report["kinds_kept"] == {
        "cli": 1,
        "construct": 1,
        "document": 1,
        "snippet": 2,
    }
    assert report["areas_kept"] == {
        "block": 1,
        "cli": 1,
        "document": 1,
        "inline": 1,
        "layout": 1,
    }
    assert (
        report["djot_engine"] == {"exact": 0.25, "layout_forgiven": 0.5}
        and report["divergence_share"] == 0.5
    )
    assert (
        report["dropped_unsteady"] == {"mutant": 1}
        and report["build"]["version"] == "carve-rs 0.1.14"
    )
    baselines = report["baselines"]
    assert baselines["print_empty_line_exit_0"] == round(2 / 5, 4) and baselines[
        "print_nothing_exit_2"
    ] == round(1 / 5, 4)
    assert baselines["command_line_table_and_constants"] == round(3 / 5, 4), (
        "the command line and the two empty snippets"
    )
    assert report["spec_model"] == {"agrees": 5}


# ---------------------------------------------------------------- images, solution and what the agent sees


def test_the_verifier_records_in_a_builder_stage_and_keeps_only_the_answers():
    agent = (TASK / "environment" / "Dockerfile").read_text()
    verifier = (TESTS / "Dockerfile").read_text()
    solve = (STEP / "solution" / "solve.sh").read_text()
    base = re.search(
        r"^FROM (ubuntu:24\.04@sha256:[0-9a-f]{64}) AS program$", verifier, re.MULTILINE
    ).group(1)
    assert agent.count(f"FROM {base}") == 1 and verifier.count(f"FROM {base}") == 2, (
        "every stage on the pinned base"
    )
    final = verifier.split(f"\n\nFROM {base}\n", 1)[1]
    assert (
        "RUN python3 -I /original/install.py /original/carve.tar.gz /original/build.txt /opt/carve/carve"
        in verifier
    )
    assert (
        "original" not in final
        and "/opt/carve" not in final
        and "carve.tar.gz" not in final
    )
    assert re.findall(r"^COPY --from=program (\S+) (\S+)$", final, re.MULTILINE) == [
        ("/record/kept.json", "/tests/private/cases.json"),
        ("/record/expected.json", "/tests/private/expected.json"),
        ("/record/probes.json", "/tests/private/probes.json"),
        ("/record/probes_expected.json", "/tests/private/probes_expected.json"),
        ("/record/recording.json", "/tests/private/recording.json"),
    ]
    assert "chmod -R go-rwx /tests" in final, "the answers are root's alone"
    assert (
        "--expect-kept-ids" in verifier
        and "--probes-out /record/probes_expected.json" in verifier
    )
    assert "APT_SNAPSHOT" in verifier and "snapshot.ubuntu.com" in verifier, (
        "the archive can be pinned to a snapshot"
    )
    assert re.findall(r"^COPY .*$", agent, re.MULTILINE) == [
        "COPY spec/ /app/spec/",
        "COPY docs/ /app/docs/",
        "COPY fsmaint-reserve fsmaint-sweep /usr/local/lib/fsmaint/",
    ]
    assert "APT_SNAPSHOT" in agent, "the agent image can be pinned to a snapshot too"
    assert "carve" not in agent.replace("/app/rebuild", "").lower(), (
        "no build of any Carve engine in the agent's image"
    )
    assert (
        'cp -R "$here/carve/carvelib" /app/rebuild/carvelib' in solve
        and 'install -m 0755 "$here/carve/carve" /app/rebuild/carve' in solve
        and "install.py" not in solve
        and "carve.tar.gz" not in solve
    ), (
        "the reference installs the renderer written from the specification, not the original"
    )
    for tool in ("python3", "golang-go", "rustc", "cargo"):
        assert tool in agent and tool in final, tool
    assert "git clone" not in agent + verifier and "npm" not in agent + verifier


def test_the_installer_refuses_any_build_but_the_pinned_one(tmp_path):
    binary = b"\x7fELF carve"
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w:gz") as tar:
        info = tarfile.TarInfo("carve-0.1.14-x86_64-unknown-linux-musl/carve")
        info.size = len(binary)
        tar.addfile(info, io.BytesIO(binary))
    archive = tmp_path / "carve.tar.gz"
    archive.write_bytes(payload.getvalue())
    good = tmp_path / "build.txt"
    good.write_text(
        f"version carve-rs 0.1.14\narchive_sha256 {hashlib.sha256(archive.read_bytes()).hexdigest()}\n"
        f"sha256 {hashlib.sha256(binary).hexdigest()}\n"
    )
    bad = tmp_path / "bad.txt"
    bad.write_text(
        good.read_text().replace(hashlib.sha256(binary).hexdigest(), "0" * 64)
    )
    install = lambda build, dest: subprocess.run(
        [
            sys.executable,
            "-I",
            str(TASK / "common" / "original" / "install.py"),
            str(archive),
            str(build),
            str(dest),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert (
        install(good, tmp_path / "ok" / "carve").returncode == 0
        and (tmp_path / "ok" / "carve").read_bytes() == binary
    )
    assert os.stat(tmp_path / "ok" / "carve").st_mode & 0o777 == 0o755
    assert (
        install(bad, tmp_path / "no" / "carve").returncode != 0
        and not (tmp_path / "no" / "carve").exists()
    )
    assert "--blank" not in (TASK / "common" / "original" / "install.py").read_text()
    package = (SCRIPTS / "package_step.py").read_text()
    assert (
        'content["tests/original/carve.tar.gz"] = original()' in package
        and "solution/blank.json" not in package
        and "solution/LICENSE" not in package
        and 'for place in ("tests/original", "solution")' not in package
    ), "the original goes into the verifier's build context only"


SOLUTION = STEP / "solution" / "carve"


def test_the_reference_is_a_readable_renderer_on_the_standard_library():
    """The reference solution is the renderer itself, in source: a launcher and a package of
    modules, Python 3.12 and its standard library only, no binary, nothing of carve-rs. It holds no
    case or probe ids and, where the private cases are present here, none of their text."""
    files = sorted(
        path
        for path in SOLUTION.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )
    names = [str(path.relative_to(SOLUTION)) for path in files]
    assert "carve" in names and all(
        name == "carve" or (name.startswith("carvelib/") and name.endswith(".py"))
        for name in names
    ), names
    assert not [
        path
        for path in (STEP / "solution").iterdir()
        if path.name not in ("carve", "solve.sh")
    ]
    launcher = (SOLUTION / "carve").read_text()
    assert launcher.startswith("#!/usr/bin/python3 -I\n"), launcher[:40]
    stdlib = set(sys.stdlib_module_names)
    sources = {}
    for path in files:
        text = path.read_text(encoding="utf-8")
        sources[str(path.relative_to(SOLUTION))] = text
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [] if node.level else [node.module or ""]
            else:
                continue
            for module in modules:
                top = module.split(".")[0]
                assert top in stdlib or top == "carvelib", (path.name, module)
    every = "\n".join(sources.values())
    for word in ("carve-rs", "subprocess", "socket", "urllib", "ctypes"):
        assert word not in every, word
    assert not re.search(r"\b[PF]\d{3,5}\b", every), "no case or probe ids"
    private = TESTS / "private" / "cases.json"
    if private.is_file():
        cases = json.loads(private.read_text(encoding="utf-8"))["cases"]
        lines = {
            line.strip()
            for case in cases
            for text in list(case["files"].values()) + [case.get("stdin") or ""]
            for line in text.splitlines()
            if len(line.strip()) >= 40
        }
        found = [line for line in lines if line in every]
        assert not found, found[:3]


def test_hosts_draw_once_and_the_attacker_splice_is_rejected():
    """QA 12b F1: every host draws its text once, so its placeholder form is the kept source with
    the part replaced at the part's prefix (the shape a program with the public corpus rebuilds);
    `attacker_splices` applies that program's rules (R3 here: a lazy placeholder line gives way to
    the body inside its item); and `settle` rejects an answer any such splice reproduces, or one
    that differs from a splice in whitespace only, while keeping a real interaction and storing
    the splices for the recording's own check."""
    out = scripts_call(
        textwrap.dedent("""
        import json, random, hosts, make_cases, corpus_lookup
        from documents import Writer
        rng = random.Random(7)
        w = Writer(rng)
        names, stable = [], []
        for host in hosts.single_hosts(w, rng) + hosts.composite_hosts(w, rng, 2):
            parts = hosts.placeholders(host.arity)
            names.append(host.name)
            stable.append(host.source(parts) == host.source(parts))
        tight = next(h for h in hosts.single_hosts(Writer(random.Random(3)), random.Random(3)) if h.name == "tight-item")
        src, shape = tight.source(["> quoted body\\n"]), tight.source(hosts.placeholders(1))
        same_prefix = src.split("\\n")[1][:2] == "  " and shape.split("\\n")[1] == "  qzjvx"
        shape_html = "<ul>\\n  <li>lead text\\nqzjvx</li>\\n</ul>\\n"
        body_html = "<blockquote>\\n<p>quoted body</p>\\n</blockquote>\\n"
        tries = hosts.attacker_splices(shape_html, [body_html])
        r3 = any("<li>lead text\\n    <blockquote>" in t and "</blockquote>\\n  </li>" in t for t in tries)
        empty = corpus_lookup.Lookup({}, {})
        item = {"kind": "snippet", "index": 0, "variants": [("v0", "s0")], "files": {"a.crv": "base"}, "stdin": None,
                "argv": ["a.crv"], "source": "base", "origin": "x:0", "parts": ["p"]}
        base = {"exit": 0, "stdout": "<p>base</p>\\n"}
        def run(answer):
            chosen, how, reasons = make_cases.settle(item, {(0, -1): base, (0, 0): {"exit": 0, "stdout": answer},
                                                           (0, 100): {"exit": 0, "stdout": shape_html},
                                                           (0, 200): {"exit": 0, "stdout": body_html}}, empty, {})
            return [how, dict(reasons), None if chosen is None else len(chosen.get("splice_guesses", []))]
        spliced = run(tries[-1])
        spaced = run(tries[-1].replace("\\n    <blockquote>", "\\n      <blockquote>"))
        real = run("<ul>\\n  <li>lead text\\n    <blockquote>\\n    <p>quoted body</p>\\n    </blockquote>\\n  </li>\\n</ul>\\n"
                   "<section role=\\"doc-endnotes\\"></section>\\n")
        print(json.dumps([names, stable, same_prefix, r3, len(tries), spliced, spaced, real]))
    """)
    )
    names, stable, same_prefix, r3, tries, spliced, spaced, real = out
    assert len(names) == 18 and all(stable), dict(zip(names, stable))
    assert same_prefix and r3 and tries >= 2
    assert spliced == [
        "no variant kept",
        {"a splice of the host and the parts gives it": 1},
        None,
    ]
    assert spaced == [
        "no variant kept",
        {"the host changed only whitespace or words of a splice": 1},
        None,
    ]
    assert real[0] == "snippet: v0" and real[2] == tries, (
        "a real interaction is kept, with the splices stored for the recording"
    )
    make = (SCRIPTS / "make_cases.py").read_text()
    assert 'item.get("splice_guesses", [])' in make, (
        "the splices' digests travel with the case in lookup_sha256"
    )


def test_a_source_changed_after_the_end_is_copied_and_flagged_whatever_the_end(
    tmp_path,
):
    """The link fixer never refuses a source for when it changed: a source changed after the end of
    the work is copied and flagged, whether the end is the work's limit or only the sweep's start,
    and an honest source finished before the end is copied unflagged; late entries count a copy by
    its source's change time."""

    def delivery(name: str) -> Path:
        outside = tmp_path / f"{name}-outside"
        outside.mkdir()
        (outside / "tool.py").write_text("x = 1\n")
        top = tmp_path / name / "rebuild"
        top.mkdir(parents=True)
        (top / "carve").write_text("#!/bin/sh\nexit 0\n")
        (top / "helpers").symlink_to(outside)
        return top

    past = time.time() - 10  # the work ended before the outside tree was written
    for origin in ("limit", "start"):
        late = delivery(f"late-{origin}")
        run_hook(late, turn_end=past, turn_from=origin)
        record = json.loads((late / ".fsmaint.json").read_text())
        assert (
            (late / "helpers" / "tool.py").is_file()
            and len(record["copies"]) == 1
            and record["refused_copies"] == []
        ), (origin, record["copies"], record["refused_copies"])
        assert (
            f"changed after the end of the work ({origin})"
            in record["copies"][0]["flagged"]
            and record["late_entries"] >= 1
        ), record["copies"]
    flags = verifier_call(
        textwrap.dedent(f"""
        import json, verify
        from pathlib import Path
        print(json.dumps(verify.manifest_record(Path({str(late)!r}))["flags"]))
    """)
    )
    assert any(
        "copies hold files changed after the end of the work; kept" in flag
        for flag in flags
    ), flags
    honest = delivery("honest")
    run_hook(
        honest, turn_end=time.time() + 10**6, turn_from="limit"
    )  # written well before the end
    record = json.loads((honest / ".fsmaint.json").read_text())
    assert (
        len(record["copies"]) == 1
        and "flagged" not in record["copies"][0]
        and record["late_entries"] == 0
    )
    hook = HOOK.read_text()
    assert (
        "SKEW" not in hook
        and '"refused": dict(record, reason=f"{len(late)}' not in hook
    )


def test_a_file_written_in_the_last_second_is_kept(tmp_path):
    """A file the work wrote just before its end stays in the tree unflagged, and one written after
    the end (a process still running when the turn reached its limit) stays too, flagged in the
    record: nothing is moved out for when it was written. The bound's reader takes the work's
    start plus its limit when the sweep began after that, and else the sweep's own start."""
    top = tmp_path / "rebuild"
    top.mkdir()
    (top / "carve").write_text("#!/bin/sh\nexit 0\n")
    written = max((top / "carve").stat().st_mtime, (top / "carve").stat().st_ctime)
    lines = run_hook(top, turn_end=written + 0.3, turn_from="limit")
    record = json.loads((top / ".fsmaint.json").read_text())
    assert lines[0].startswith("listed 1 ") and (top / "carve").is_file(), lines
    assert record["late_entries"] == 0 and record["late_paths"] == [], record
    after = tmp_path / "after" / "rebuild"
    after.mkdir(parents=True)
    (after / "carve").write_text("#!/bin/sh\nexit 0\n")
    (after / "lib.py").write_text("x = 1\n")
    written = min((after / name).stat().st_ctime for name in ("carve", "lib.py"))
    lines = run_hook(after, turn_end=written - 0.3, turn_from="limit")
    record = json.loads((after / ".fsmaint.json").read_text())
    assert lines[0].startswith("listed 2 ") and (after / "lib.py").is_file(), lines
    assert record["late_entries"] == 2 and sorted(record["late_paths"]) == [
        "carve",
        "lib.py",
    ], record
    flags = verifier_call(
        textwrap.dedent(f"""
        import json, verify
        from pathlib import Path
        print(json.dumps(verify.manifest_record(Path({str(after)!r}))["flags"]))
    """)
    )
    assert (
        "2 entries changed after the end of the work (limit); kept: review them"
        in flags
    ), flags
    reader = hook_programs()["bound"]
    state = tmp_path / "state"
    state.mkdir()
    (state / "work-started").write_text("1000.5\n")

    def bound(started: str, limit: str) -> list[str]:
        return subprocess.run(
            [sys.executable, "-I", "-", started, str(state / "work-started"), limit],
            check=False,
            input=reader,
            text=True,
            capture_output=True,
            timeout=30,
        ).stdout.split()

    assert bound("50000.0", "43200") == ["44200.5", "limit"]
    assert bound("2000.0", "43200") == ["2000.0", "start"]
    (state / "work-started").unlink()
    assert bound("50000.0", "43200") == ["50000.0", "start"]


def test_the_agent_cannot_replace_the_artifact_directory():
    docker = (TASK / "environment" / "Dockerfile").read_text()
    assert (
        "chown -R root:root /app" in docker
        and "chmod 1777 /app " in docker
        and "chmod 0777 /app/rebuild" in docker
    )
    assert "useradd --uid 10001 --create-home dev" in docker
    assert "chmod 0700 /usr/local/lib/fsmaint /usr/local/lib/fsmaint/*" in docker
    assert not re.search(r"COPY [^\n]*/usr/local/s?bin", docker), (
        "the hooks live in a root-only directory, not on PATH"
    )
    toml = (TASK / "task.toml").read_text()
    assert (
        'user = "dev"' in toml
        and 'artifacts = ["/app/rebuild", "/var/lib/fsmaint/out"]' in toml
    )
    assert 'environment_mode = "separate"' in toml
    assert toml.count('network_mode = "no-network"') == 4, (
        "no phase has the network: the agent, its environment, the verifier and its environment"
    )
    assert 'network_mode = "public"' not in toml and "open_internet" not in toml


def test_both_images_keep_roots_path_unwritable_and_make_every_artifacts_parent():
    """Root runs tar, su and the hooks' tools through the image's PATH after the work and while it
    grades: in both images an explicit PATH with nothing on it, in it or above it writable by anyone
    but root, checked when the image is built (the last stage, after every install). The verifier
    image makes the parent of every declared artifact."""
    config = tomllib.loads((TASK / "task.toml").read_text())
    for dockerfile in (TASK / "environment" / "Dockerfile", TESTS / "Dockerfile"):
        text = dockerfile.read_text()
        last = text[text.rindex("\nFROM ") :] if text.count("\nFROM ") else text
        assert (
            "ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
            in last
        ), dockerfile
        assert "-perm /022 -o ! -user root" in last and "readlink -f" in last, (
            dockerfile
        )
        gate = last.index("ENV PATH=")
        assert all(
            last.rindex(step) < gate
            for step in ("apt-get install", "COPY ")
            if step in last
        ), "the check comes after everything the last stage installs or copies"
    verifier = (TESTS / "Dockerfile").read_text()
    made = re.search(r"RUN mkdir -p ([^\\\n]+)", verifier[verifier.rindex("\nFROM ") :])
    assert made, "the verifier image makes its directories"
    for artifact in config["artifacts"]:
        parent = str(Path(artifact).parent)
        assert parent in made.group(1).split(), (artifact, made.group(1))
    assert "/logs/verifier" in made.group(1).split()


def test_every_run_fits_inside_the_step_verifier_time():
    per_run = int(
        re.search(r"^CASE_SEC = (\d+)$", RUNNER.read_text(), re.MULTILINE).group(1)
    )
    total = int(
        re.search(
            r"^TOTAL_SEC = (\d+)", (TESTS / "verify.py").read_text(), re.MULTILINE
        ).group(1)
    )
    step_verifier = tomllib.loads((TASK / "task.toml").read_text())["verifier"][
        "timeout_sec"
    ]
    margin = int(
        re.search(
            r"^MARGIN_SEC = (\d+)", (TESTS / "verify.py").read_text(), re.MULTILINE
        ).group(1)
    )
    assert 2200 * (per_run + 0.25) <= total - margin and total < step_verifier, (
        "a renderer that takes the whole stated time on every page still has every page run"
    )
    assert (
        f"Each run finishes within {per_run} seconds"
        in (STEP / "instruction.md").read_text()
    )
    config = tomllib.loads((TASK / "task.toml").read_text())
    declared = (
        config["environment"]["build_timeout_sec"]
        + sum(hook["timeout_sec"] for hook in config["agent"]["setup_begin"])
        + sum(hook["timeout_sec"] for hook in config["agent"]["setup_complete"])
        + config["agent"]["timeout_sec"]
        + sum(hook["timeout_sec"] for hook in config["verifier"]["collect"])
        + step_verifier
    )
    assert declared + 3600 <= 24 * 3600, (
        "one attempt (build, set-up, the work, the collect hook, the verifier, an hour besides) "
        "fits the platform's 24-hour attempt"
    )


def test_nothing_the_agent_sees_names_grading_or_a_budget():
    seen = {
        "Dockerfile": (TASK / "environment" / "Dockerfile").read_text(),
        "instruction.md": (STEP / "instruction.md").read_text(),
        "task.toml": (TASK / "task.toml").read_text(),
    }
    for name, text in seen.items():
        lowered = text.lower()
        for word in (
            "oracle",
            "reference solution",
            "hidden",
            "grade",
            "grading",
            "score",
            "test case",
            "working session",
            "fresh context",
            "candidate",
        ):
            assert word not in lowered, (name, word)
        if name != "task.toml":
            for word in ("verifier", "private", "recorded", "case"):
                assert word not in lowered, (name, word)
    comments = [
        line for line in seen["task.toml"].splitlines() if line.lstrip().startswith("#")
    ]
    said = " ".join(comments).lower()
    for word in (
        "platform",
        "trial",
        "verifier",
        "image",
        "grade",
        "graded",
        "score",
        "reward",
        "evaluat",
        "harbor",
        "oddish",
        "modal",
        "audit",
        "qa ",
        "artifact",
        "result",
        "test",
        "benchmark",
        "agent",
        "hidden",
        "oracle",
        "budget",
        "deadline",
    ):
        assert word not in said, ("task.toml comment", word)
    assert not re.search(r"\bcaps?\b", said), "task.toml comment names a cap"
    assert comments == [], comments  # task.toml carries no comment (round 12)
    instruction = seen["instruction.md"]
    hours = re.findall(r"[^.]*\bhours?\b[^.]*\.", " ".join(instruction.split()))
    agent_limit = tomllib.loads(seen["task.toml"])["agent"]["timeout_sec"]
    assert hours == [" You have up to 12 hours to build and test the renderer."], hours
    assert agent_limit == 12 * 3600, "the stated time is the agent's limit"
    assert "/app/rebuild/carve" in instruction and "Out of scope:" in instruction
    for excluded in (
        "{{ path }}",
        "`fmt`",
        "`lint`",
        "`migrate`",
        "Markdown",
        "the AST as JSON",
        "importers",
        "static mode",
        "`--help`",
        "`--version`",
    ):
        assert excluded in instruction.split("Out of scope:", 1)[1], excluded
    for carrier in (HOOK, SETUP):
        lowered = carrier.read_text().lower()
        for word in (
            "grade",
            "score",
            "reward",
            "verifier",
            "hidden",
            "oracle",
            "the test",
            "deliver",
            "collect",
            "watchdog",
            "platform",
            "harbor",
            "pre-cap",
            "qa ",
            "audit",
            "attempt",
            "budget",
            "deadline",
            "submission",
            "agent",
        ):
            assert word not in lowered, (carrier.name, word)


def test_the_brief_states_only_what_the_verifier_enforces():
    """The brief's one prohibition is the one the verifier refuses: carve-rs, the other Carve
    engines with the runtimes they run on (the four language families of upstream_builds.json's
    runtime markers), and upstream's code. The toolchains are stated as what is installed, gcc
    among them; no duty to keep the code modular or to use only certain toolchains is stated."""
    brief = " ".join((STEP / "instruction.md").read_text().split())
    assert (
        "the other Carve engines (with the JavaScript, PHP, Ruby and WebAssembly runtimes they run on)"
        in brief
        and "they may not be brought in" in brief
    )
    assert (
        "Python 3.12, Go, Rust (`rustc` and `cargo`) and gcc are installed, here and where your "
        "renderer will run, each with its standard library and nothing more"
    ) in brief
    for gone in (
        "modular",
        "separate parts",
        "approved toolchains",
        "code our own team wrote",
        "no third-party",
        "standard library only",
        "since we maintain",
    ):
        assert gone not in brief, gone
    runtimes = json.loads((TESTS / "verifier" / "upstream_builds.json").read_text())[
        "runtimes"
    ]
    families = {
        "bun": "JavaScript",
        "deno": "JavaScript",
        "node": "JavaScript",
        "quickjs": "JavaScript",
        "php": "PHP",
        "ruby": "Ruby",
        "wasm": "WebAssembly",
    }
    assert set(runtimes) == set(families), sorted(runtimes)
    verifier = (TESTS / "Dockerfile").read_text()
    for tool in ("python3", "golang-go", "rustc", "cargo", "gcc"):
        assert tool in verifier, tool


def test_packaging_ships_runtime_files_only_and_flattens_cleanly():
    package = (SCRIPTS / "package_step.py").read_text()
    assert (
        'for directory in ("environment", "tests", "solution"):' in package
        and '"experiment"' in package
    )
    assert (
        'content[f"environment/spec/{name}"]' in package
        and 'content[f"environment/docs/{name}"]' in package
    )
    assert "make_cases.leaks(" in package
    out = scripts_call(
        textwrap.dedent("""
        import json, package_step
        content = {"task.toml": b'schema_version = "1.4"\\nmulti_step_reward_strategy = "final"\\n[task]\\nname = "abundant/swe-m2_x_y"\\n'
                                b'\\n[[steps]]\\nname = "01-implement-renderer"\\n',
                   "instruction.md": b"do it", "environment/Dockerfile": b"FROM x"}
        flat = package_step.flatten(content)
        print(json.dumps({k: v.decode() for k, v in flat.items()}))
    """)
    )
    assert sorted(out) == ["environment/Dockerfile", "instruction.md", "task.toml"]
    assert (
        'name = "abundant/swe-m2_x_y-single"' in out["task.toml"]
        and "[[steps]]" not in out["task.toml"]
    )
    assert "multi_step_reward_strategy" not in out["task.toml"]


def test_the_pins_are_stated_once_and_agree():
    text = (SCRIPTS / "carve_text.py").read_text()
    pins = dict(re.findall(r'^([A-Z0-9_]+) = \(?\s*"([^"]+)"', text, re.MULTILINE))
    assert pins["SPEC_TAG"] == pins["CARVE_RS_TAG"] == "0.1.14"
    assert re.fullmatch(r"[0-9a-f]{40}", pins["SPEC_COMMIT"]) and re.fullmatch(
        r"[0-9a-f]{40}", pins["CARVE_RS_COMMIT"]
    )
    for key in (
        "LINUX_ARCHIVE_SHA256",
        "LINUX_BINARY_SHA256",
        "MAC_ARCHIVE_SHA256",
        "MAC_BINARY_SHA256",
    ):
        assert re.fullmatch(r"[0-9a-f]{64}", pins[key]), key
    readme = (TASK / "README.md").read_text()
    for key in (
        "SPEC_COMMIT",
        "CARVE_RS_COMMIT",
        "LINUX_BINARY_SHA256",
        "LINUX_ARCHIVE_SHA256",
    ):
        assert pins[key] in readme, key


def test_a_fetched_build_of_the_original_or_a_runtime_is_refused(tmp_path):
    top = tmp_path / "rebuild"
    (top / "bin").mkdir(parents=True)
    fetched = b"\x7fELF" + b"q" * ((1 << 20) + 5)
    (top / "bin" / "carve-real").write_bytes(fetched)
    (top / "link").symlink_to(top / "bin" / "carve-real")
    out = verifier_call(
        textwrap.dedent(f"""
        import json, verify
        from pathlib import Path
        top = Path({str(top)!r})
        builds = verify.upstream_builds()
        mine = dict(builds, hashes=set(builds["hashes"]) | {{"{hashlib.sha256(fetched).hexdigest()}"}})
        first = verify.fetched_build(top, mine)
        (top / "bin" / "carve-real").unlink()
        s = builds["strings"]
        # three of carve-rs's own strings, one straddling the 1 MB read boundary
        (top / "many-strings.bin").write_bytes(b"x" * ((1 << 20) - 5) + s[0] + b"y" * 50 + s[1] + b"z" * 50 + s[2])
        second = verify.fetched_build(top, mine)
        (top / "many-strings.bin").write_bytes(b"x" * 1000 + s[0] + b"y" * 50 + s[1])   # two is not enough
        third = verify.fetched_build(top, mine)
        (top / "many-strings.bin").unlink()
        name, group = next(iter(builds["runtimes"].items()))
        (top / "engine").write_bytes(b"z" * 1000 + group[0] + b"z" * 50 + group[1])     # two markers of one runtime
        fourth = verify.fetched_build(top, mine)
        (top / "engine").unlink()
        print(json.dumps([first, second, third, fourth, name, len(builds["hashes"]), len(builds["strings"]),
                          builds["strings_needed"], builds["runtime_needed"], sorted(builds["runtimes"])]))
    """)
    )
    (
        first,
        second,
        third,
        fourth,
        runtime,
        hashes,
        strings,
        needed,
        runtime_needed,
        runtimes,
    ) = out
    assert (
        first
        == "/app/rebuild/bin/carve-real is a build of the original or another engine that upstream publishes"
    )
    assert (
        second
        == "/app/rebuild/many-strings.bin holds the text of a build of the original"
    ), "three strings across a 1 MB chunk boundary"
    assert third is None, "two strings alone is no fetched build"
    assert (
        fourth
        == f"/app/rebuild/engine embeds a {runtime} runtime, which the instruction does not allow"
    )
    builds = json.loads((TESTS / "verifier" / "upstream_builds.json").read_text())
    pins = dict(
        re.findall(
            r'^([A-Z0-9_]+) = \(?\s*"([^"]+)"',
            (SCRIPTS / "carve_text.py").read_text(),
            re.MULTILINE,
        )
    )
    assert (
        pins["LINUX_BINARY_SHA256"] in builds["sha256"]
        and pins["LINUX_ARCHIVE_SHA256"] in builds["sha256"]
    )
    assert hashes >= 1000 and strings >= 10 and needed == 3 and runtime_needed == 2
    assert min(len(t) for t in builds["strings"]) >= 40 and set(runtimes) >= {
        "node",
        "wasm",
        "php",
    }
    instruction = (STEP / "instruction.md").read_text()
    for text in builds["strings"]:
        assert text not in instruction, text
    verify = (TESTS / "verify.py").read_text()
    main = verify[verify.index("def main() -> int:") :]
    assert (
        main.index("seal(REBUILD)")
        < main.index("fetched_build(REBUILD")
        < main.index("fingerprint(PROGRAM")
        < main.index("metrics = run_cases(PROGRAM")
    )
    assert main.index("network_denied(prefix)") < main.index("seal(REBUILD)"), (
        "the network denial is checked before anything of the tree runs"
    )


def fingerprint_probes(tmp_path: Path, kinds: dict[str, int]) -> Path:
    """A private directory with `kinds` probes of each kind (argv: the probe's id) and their
    recorded answers ("original <id>")."""
    private = tmp_path / "private"
    private.mkdir(exist_ok=True)
    probes, answers = [], {}
    for kind, count in kinds.items():
        for index in range(count):
            probe_id = f"{kind[0].upper()}{index:03d}"
            probes.append(
                {
                    "id": probe_id,
                    "kind": f"{kind}:x",
                    "files": {},
                    "argv": [probe_id],
                    "stdin": None,
                }
            )
            answers[probe_id] = {"exit": 0, "stdout": f"original {probe_id}\n"}
    (private / "probes.json").write_text(json.dumps({"probes": probes}))
    (private / "probes_expected.json").write_text(json.dumps(answers))
    return private


def test_a_tree_that_answers_the_probes_as_the_original_does_is_refused(tmp_path):
    """The fingerprint runs before the cases and is scored: a tree that matches the original on
    24 of the 38 documents where it departs from the specification, or on 5 of its 11 commands
    outside the brief, is refused (reward 0, not run); below both, nothing happens. Every probe
    runs whatever the time left, and probes or answers that are missing are an evaluation error."""
    private = fingerprint_probes(tmp_path, {"disagreement": 38, "command": 11})
    match = tmp_path / "match"
    program = tmp_path / "carve"
    program.write_text(
        f'#!/bin/sh\nif grep -qx "$1" {match}; then echo "original $1"; else echo mine; fi\n'
    )
    program.chmod(0o755)
    (tmp_path / "tmp").mkdir()
    report = verifier_call(
        textwrap.dedent(f"""
        import json, verify
        from pathlib import Path
        verify.runcases.WORKSPACE = Path({str(tmp_path / "tmp" / "carve-case")!r})
        verify.runcases.HOME = Path({str(tmp_path / "tmp" / "carve-home")!r})
        verify.runcases.TEMP = Path({str(tmp_path / "tmp" / "carve-tmp")!r})
        verify.PREEXEC = verify.runcases.limit
        verify.TOTAL_SEC, verify.MARGIN_SEC = 0, 10**9   # no time left: the probes still all run
        D = ["D%03d" % i for i in range(38)]
        C = ["C%03d" % i for i in range(11)]
        scenarios = {{"none": [], "d23": D[:23], "d24": D[:24], "c4": C[:4], "c5": C[:5],
                     "both below": D[:23] + C[:4], "original": D + C[:9]}}
        out = {{}}
        for name, matched in scenarios.items():
            Path({str(match)!r}).write_text("".join(m + "\\n" for m in matched))
            result = verify.fingerprint(Path({str(program)!r}), Path({str(private)!r}), [], None)
            out[name] = [result, verify.fingerprint_refusal(result)]
        errors = []
        answers = Path({str(private)!r}) / "probes_expected.json"
        recorded = json.loads(answers.read_text())
        answers.write_text(json.dumps({{k: v for k, v in recorded.items() if k != "C010"}}))
        for _ in range(2):
            try:
                verify.fingerprint(Path({str(program)!r}), Path({str(private)!r}), [], None)
                errors.append(None)
            except verify.EvaluationError as exc:
                errors.append(str(exc))
            answers.unlink(missing_ok=True)
        print(json.dumps([out, errors]))
        """)
    )
    out, errors = report
    assert out["none"] == [
        {
            "total": 49,
            "matches_original": 0,
            "by_kind": {
                "disagreement": {"total": 38, "matches": 0},
                "command": {"total": 11, "matches": 0},
            },
        },
        None,
    ]
    for name in ("d23", "c4", "both below"):
        assert out[name][1] is None, (name, out[name])
    assert out["d24"][1] == (
        "the tree matches carve-rs 0.1.14 on 24 of 49 probes (24 of the 38 documents where it "
        "departs from the specification, 0 of the 11 commands of its own outside the brief): not run"
    )
    assert out["c5"][1].startswith("the tree matches carve-rs 0.1.14 on 5 of 49 probes")
    assert out["original"][0]["matches_original"] == 47 and out["original"][1]
    assert errors == [
        "The fingerprint probes and their recorded answers do not match",
        "The fingerprint probes are unreadable",
    ]
    verify = (TESTS / "verify.py").read_text()
    assert 'FINGERPRINT_REFUSAL = {"disagreement": 24, "command": 5}' in verify
    body = verify[
        verify.index("def fingerprint(") : verify.index("def fingerprint_refusal(")
    ]
    assert "cutoff" not in body and "MARGIN_SEC" not in body, (
        "the probes cannot be skipped on the deadline"
    )


# ---------------------------------------------------------------- round 11 (QA 24)


def test_what_the_session_left_in_logs_artifacts_is_moved_aside_whole(tmp_path):
    """QA 24 S2: /logs/artifacts is writable by the session without bound, and the copy packs it, and
    unpacks it into the verifier's container, before anything else; an upload that fails there ends
    the run in an error. Now the sweep, once the processes are ended, renames it whole into the
    root-only state directory (it is not copied from there) and leaves an empty directory with the
    same owner and mode; the record says how many entries it held, and the verifier flags them."""
    target = tmp_path / "logs" / "artifacts"
    target.mkdir(parents=True)
    target.chmod(0o777)
    for index in range(3000):
        (target / f"a{index:04d}").write_text("x")
    os.mkfifo(target / "pipe")
    (target / "away").symlink_to("/etc/hosts")
    state = tmp_path / "state"
    state.mkdir()
    done = subprocess.run(
        [sys.executable, "-I", "-", str(target), str(state)],
        check=False,
        input=hook_programs()["artifacts"],
        text=True,
        capture_output=True,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr
    report = json.loads((state / "logs-artifacts.json").read_text())
    assert (
        report["entries"] == 3002
        and report["moved_to"]
        and Path(report["moved_to"]).parent == state
    ), report
    assert (
        target.is_dir()
        and os.listdir(target) == []
        and target.stat().st_mode & 0o777 == 0o777
    )
    assert len(os.listdir(report["moved_to"])) == 3002
    hook = HOOK.read_text()
    assert (
        hook.index('> "$STATE/kill.json"')
        < hook.index('"""Move aside what the session left in /logs/artifacts')
        < hook.index('"""Make /app/rebuild safe to copy')
    ), "after the ending, before anything is copied"
    assert "logs_artifacts=logs_artifacts" in hook
    flags = verifier_call(
        textwrap.dedent(f"""
        import json, verify
        from pathlib import Path
        top = Path({str(tmp_path / "rebuild")!r})
        top.mkdir()
        (top / ".fsmaint.json").write_text(json.dumps({{"logs_artifacts": json.loads({json.dumps(report)!r}), "processes_left": 0}}))
        print(json.dumps(verify.manifest_record(top)["flags"]))
    """)
    )
    assert any(
        "3002 entries in /logs/artifacts were set aside" in flag for flag in flags
    ), flags


def test_a_file_with_more_than_a_thousand_hard_links_is_refused(tmp_path):
    """QA 24 S3: the copy's far side may cap the names of a file (ext4: 65,000) and then writes a full
    copy for each name past it, so one large file under some 199,000 names could fill its disk. A
    tree in which a file has more than 1,000 names (cargo makes 2) is now refused, a noted 0, and the
    instruction states the limit beside the others."""
    for count, expected in ((1001, "refused"), (1000, "listed")):
        top = tmp_path / f"links-{count}" / "rebuild"
        top.mkdir(parents=True)
        (top / "carve").write_text("#!/bin/sh\n")
        (top / "big").write_bytes(b"y" * 4096)
        for index in range(count - 1):
            os.link(top / "big", top / f"n{index:04d}")
        lines = run_measuring(top)
        assert lines[0].split()[0] == expected, (count, lines[:3])
        if expected == "refused":
            assert (
                lines[1]
                == "a file in it has more than 1,000 hard links, the most a file in /app/rebuild may have: it was not copied"
            )
            assert manifest_of(top)[1] is True
    assert (
        "with no file that has more than 1,000 hard links"
        in (STEP / "instruction.md").read_text()
    )


# ---------------------------------------------------------------- round 12: no timer; the work's limit; flat bundles


def test_no_timer_ends_the_session_and_the_work_limit_is_one_number():
    """Nothing of the task stops the session before the agent's limit: no timer and no watcher
    (fsmaint-netcheck is gone with its set-up entry); the agent's limit is 43,200 s with no
    comment, the sweep's WORK_LIMIT_SECONDS is the same number, and fsmaint-reserve --begin records
    when the work began, just before it does."""
    for gone in ("fsmaint-timer", "fsmaint-netcheck"):
        assert not (TASK / "environment" / gone).exists(), gone
    toml = (TASK / "task.toml").read_text()
    assert "fsmaint-timer" not in toml and "netcheck" not in toml and "#" not in toml
    assert re.findall(r"\[(agent|steps\.agent)\]\ntimeout_sec = (\d+)", toml) == [
        ("agent", "43200")
    ]
    for carrier in (
        TASK / "environment" / "Dockerfile",
        HOOK,
        SETUP,
        TESTS / "verify.py",
    ):
        text = carrier.read_text().lower()
        assert "timer" not in text and "netcheck" not in text, carrier.name
    assert (
        int(
            re.search(
                r"^WORK_LIMIT_SECONDS=(\d+)", HOOK.read_text(), re.MULTILINE
            ).group(1)
        )
        == 43200
    )
    setup = SETUP.read_text()
    assert (
        'date +%s.%N > "$STATE/work-started"' in setup
        and "setsid" not in setup
        and '[[agent.setup_complete]]\ncommand = "/usr/local/lib/fsmaint/fsmaint-reserve --begin"'
        in toml
    )


def test_a_capped_turn_that_keeps_writing_after_the_limit_keeps_it_flagged(
    tmp_path,
):
    """With no timer, a turn that runs to the agent's limit leaves its processes running until the
    sweep stops them (nothing ends them at the limit). The end of such a work is its start (written
    at set-up) plus 43,200 s: a file written in place after it, and a source a link reaches that
    changed after it, are kept and flagged. Here the limit falls 1.5 s after an honest write, and a
    process of the turn writes and links once it has passed."""
    top = tmp_path / "rebuild"
    top.mkdir()
    program = "#!/bin/sh\necho early\n"
    (top / "carve").write_text(program)
    (top / "notes.txt").write_text("early\n")
    state = top.parent / f".{top.name}-state"  # run_hook's own state directory
    state.mkdir()
    limit_at = time.time() + 1.5
    (state / "work-started").write_text(f"{limit_at - 43200}\n")
    outside = tmp_path / "outside"
    turn = subprocess.Popen(
        [
            "sh",
            "-c",
            (
                f'sleep 2.5; echo late > "{top}/notes.txt"; mkdir -p "{outside}"; '
                f'printf "%s" "written after the limit" > "{outside}/helper.txt"; '
                f'ln -s "{outside}/helper.txt" "{top}/helper.txt"'
            ),
        ]
    )
    assert turn.wait(timeout=30) == 0
    done = subprocess.run(
        [
            sys.executable,
            "-I",
            "-",
            f"{time.time()}",
            str(state / "work-started"),
            "43200",
        ],
        check=False,
        input=hook_programs()["bound"],
        text=True,
        capture_output=True,
        timeout=30,
    )
    end, origin = done.stdout.split()
    assert origin == "limit" and abs(float(end) - limit_at) < 0.01, (
        done.stdout + done.stderr
    )
    lines = run_hook(top, turn_end=float(end), turn_from=origin)
    record = json.loads((top / ".fsmaint.json").read_text())
    assert (
        lines[0].startswith("listed 3 ") and (top / "carve").read_text() == program
    ), lines[:4]
    assert (top / "notes.txt").read_text() == "late\n" and (
        top / "helper.txt"
    ).read_text() == "written after the limit"
    assert (
        record["end_from"] == "limit"
        and record["late_paths"] == ["notes.txt"]
        and record["late_entries"] == 2
        and record["refused_copies"] == []
        and "(limit); copied and flagged" in record["copies"][0]["flagged"]
    ), record
    flags = verifier_call(
        textwrap.dedent(f"""
        import json, verify
        from pathlib import Path
        print(json.dumps(verify.manifest_record(Path({str(top)!r}))["flags"]))
    """)
    )
    assert (
        "the work ran to its time limit; the end bound is its start plus that limit"
        in flags
    ), flags
    assert (
        "2 entries changed after the end of the work (limit); kept: review them"
        in flags
    ), flags


def test_the_flat_bundle_can_keep_the_tasks_name():
    """Round 12: the flat bundle goes up as the next version of the same task, so `--flat
    --keep-name` keeps the name; the layout and task.toml change as with `--flat` alone, and nothing
    else."""
    out = scripts_call(
        textwrap.dedent("""
        import json, package_step
        content = {"task.toml": b'schema_version = "1.4"\\nmulti_step_reward_strategy = "final"\\n[task]\\nname = "abundant/swe-m2_x_y"\\n'
                                b'\\n[[steps]]\\nname = "01-implement-renderer"\\n',
                   "instruction.md": b"do it", "environment/Dockerfile": b"FROM x"}
        print(json.dumps([{k: v.decode() for k, v in package_step.flatten(content, keep_name=True).items()},
                          {k: v.decode() for k, v in package_step.flatten(content).items()}]))
    """)
    )
    kept, renamed = out
    assert (
        sorted(kept) == ["environment/Dockerfile", "instruction.md", "task.toml"]
        and kept["instruction.md"] == "do it"
    )
    assert (
        'name = "abundant/swe-m2_x_y"\n' in kept["task.toml"]
        and "-single" not in kept["task.toml"]
    )
    assert (
        "[[steps]]" not in kept["task.toml"]
        and "multi_step_reward_strategy" not in kept["task.toml"]
    )
    assert kept["task.toml"] == renamed["task.toml"].replace(
        "swe-m2_x_y-single", "swe-m2_x_y"
    )
    invalid = subprocess.run(
        [sys.executable, str(SCRIPTS / "package_step.py"), "--keep-name"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert invalid.returncode == 2
    assert "--keep-name goes with --flat" in invalid.stderr


def test_hard_links_across_the_top_level_and_deeper_keep_every_name_and_no_late_note(
    tmp_path,
):
    """The sweep's own renames (the move out of the top level) move the change time of the inode
    they rename, so a deeper name of a top-level file (cargo's hard links) would read as written
    after the end. Each inode's times are taken before anything of the sweep moves a name of it,
    and every name is judged by them: an honest tree written wholly before the end keeps every name
    and none is flagged as late."""
    top = tmp_path / "rebuild"
    (top / "lib").mkdir(parents=True)
    (top / "dir").mkdir()
    (top / "carve").write_text("#!/bin/sh\necho made before the end\n")
    os.link(
        top / "carve", top / "lib" / "carve-real"
    )  # a top-level file and a deeper name of it
    (top / "dir" / "inner").write_text("inner\n")
    os.link(
        top / "dir" / "inner", top / "inner-top"
    )  # a deeper file and a top-level name of it
    (top / "a").write_text("one file, two names at the top\n")
    os.link(top / "a", top / "b")
    time.sleep(1.2)
    bound = time.time() - 0.1  # the end: after every write
    lines = run_hook(top, turn_end=bound, turn_from="limit")
    record = json.loads((top / ".fsmaint.json").read_text())
    names = sorted(
        str(path.relative_to(top))
        for path in top.rglob("*")
        if path.name not in (".fsmaint", ".fsmaint.json")
    )
    assert names == [
        "a",
        "b",
        "carve",
        "dir",
        "dir/inner",
        "inner-top",
        "lib",
        "lib/carve-real",
    ], names
    size = sum(
        len(text)
        for text in (
            "#!/bin/sh\necho made before the end\n",
            "inner\n",
            "one file, two names at the top\n",
        )
    )
    assert lines[0] == f"listed 8 {size}" and not any(
        "after the end" in line for line in lines
    ), lines
    assert (
        record["late_paths"] == []
        and record["late_entries"] == 0
        and record["end_from"] == "limit"
    ), record["late_entries"]
