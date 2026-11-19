"""Development checks: the rewrites keep what a renderer reads and change what it prints; nothing
the agent can read becomes a case; the generators make documents for any seed; the verifier counts
what a submission does as that submission's failed cases and reads the delivery the collect hook
marked; the hook lets an honest delivery through the platform's copy; the recorder keeps only steady
answers that need a renderer; and the agent's image holds the specification and the documentation,
nothing else.

Script and verifier code runs in processes of its own: another task's checks have modules named
`make_cases`, `seeds` and `verifier` too. Nothing here needs the upstream checkouts, the original's
binary, Node or experiment/.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import textwrap
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
STEP = TASK / "steps" / "01-implement-renderer"
SCRIPTS = TASK / "scripts"
TESTS = STEP / "tests"
RUNNER = TESTS / "verifier" / "runcases.py"
RECORDER = TESTS / "verifier" / "recorder.py"
HOOK = TASK / "environment" / "prepare-delivery"


def scripts_call(code: str) -> object:
    """The JSON a snippet prints with the task's scripts importable, in a process of its own."""
    done = subprocess.run([sys.executable, "-B", "-c", f"import sys; sys.path.insert(0, {str(SCRIPTS)!r})\n" + code],
                          capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


def verifier_call(code: str) -> object:
    """The JSON a snippet prints with the verifier importable, in a process of its own."""
    done = subprocess.run([sys.executable, "-B", "-c", f"import sys; sys.path.insert(0, {str(TESTS)!r})\n" + code],
                          capture_output=True, text=True, timeout=600)
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
    out = scripts_call(textwrap.dedent(f'''
        import json, random, rewrite
        source = {SAMPLE!r}
        variants = rewrite.renamings(source, random.Random(4), 3)
        print(json.dumps([variants, sorted(rewrite.protected_words(source))]))
    '''))
    variants, protected = out
    assert len(variants) == 3 and len(set(variants)) == 3
    for variant in variants:
        assert variant != SAMPLE
        assert [len(line) for line in variant.splitlines()] == [len(line) for line in SAMPLE.splitlines()], "same lengths"
        for kept in ("::: warning", "```python", "key=value", "&amp;", "(tm)", "- [x]", "a.  ", "iv.  ", "https://",
                     "mailto:", "'s ", "{#", "10:30"):
            assert kept in variant, kept
        heading = re.search(r"^# (\w+) (\w+)$", variant, re.M).groups()
        assert f"</#{heading[0]}-{heading[1]}>" in variant and f"[{heading[0]} {heading[1]}][]" in variant, \
            "a cross-reference and a heading reference still name their heading"
        assert variant.count("[^note]") == 0 and len(set(re.findall(r"\[\^(\w+)\]", variant))) == 1, "one label, renamed alike"
        abbreviation = re.search(r"^\*\[(\w+)\]:", variant, re.M).group(1)
        assert abbreviation.isupper() and len(abbreviation) == 3 and variant.count(abbreviation) >= 2, "the abbreviation and its use"
    assert {"warning", "python", "key", "value", "amp", "tm", "x", "a", "iv", "https", "mailto"} <= set(protected)


def test_structure_ignores_words_and_numbers_and_keeps_tags():
    out = scripts_call(textwrap.dedent('''
        import json, rewrite
        a = '<section id="Getting-Started">\\n  <h1>Getting Started</h1>\\n  <p>See <a href="#x1">it</a> 12.</p>\\n</section>\\n'
        b = '<section id="Tall-Window">\\n  <h1>Tall Window</h1>\\n  <p>Run <a href="#q7">ox</a> 345.</p>\\n</section>\\n'
        c = '<section id="Tall-Window">\\n  <h2>Tall Window</h2>\\n  <p>Run <a href="#q7">ox</a> 345.</p>\\n</section>\\n'
        print(json.dumps([rewrite.structure(a) == rewrite.structure(b), rewrite.structure(a) == rewrite.structure(c)]))
    '''))
    assert out == [True, False]


def test_mutations_are_local_edits_for_any_seed():
    out = scripts_call(textwrap.dedent('''
        import json, random, rewrite
        rng = random.Random(9)
        found = []
        for seed in range(200):
            mutant, edits = rewrite.mutate("- one\\n  - two\\n\\n> quote\\n", rng, ["# H\\n", "| a |\\n"])
            found.append([mutant.endswith("\\n"), all(edit in rewrite.MUTATORS for edit in edits), 1 <= len(edits) <= 3])
        print(json.dumps(found))
    '''))
    assert all(all(row) for row in out)


def test_leak_index_catches_copies_and_near_copies():
    pages = {
        "docs/guide.md": "# Guide\n\n```carve\n::: note\nShort body.\n:::\n```\n\nWrite `/slanted words/` for italic.\n\n"
                         "```\n- one\n- two\n```\n\n    -{.c} x         Djot:  <p>...</p>\n",
        "spec/07.ebnf": "(* kind is text in that region: {/a/b/} -> <em>a/b</em>, and `*b*` too *)\n",
        "spec/cases.json": json.dumps({"cases": [{"source": "[t]()", "html": "<p><a href=\"\">t</a></p>"}]}),
    }
    out = scripts_call(textwrap.dedent(f'''
        import json, carve_text as ct, make_cases
        skeletons, blob = ct.leak_index({pages!r})
        probe = lambda s: make_cases.leaks(s, skeletons, blob)
        print(json.dumps([probe("::: tip\\nOther words.\\n:::\\n"), probe("- six\\n- ten\\n"), probe("{{/q/r/}}"),
                          probe("[w]()"), probe("-{{.z}} y"), probe("Write /slanted words/ often."),
                          probe("# A heading\\n\\nA paragraph with *bold* text that the docs never show.\\n"),
                          ct.holds_include("text {{{{ part.crv }}}} more"), ct.holds_include("{{ not one }}")]))
    '''))
    assert out[:6] == [True, True, True, True, True, False], "a shown example or a renamed copy of one is a leak"
    assert out[6] is False and out[7] is True and out[8] is False


def test_documents_and_constructs_for_any_seed():
    out = scripts_call(textwrap.dedent('''
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
    '''))
    kinds, areas, bad, _ = out
    assert len(kinds) >= 10 and areas == ["attributes", "block", "divergence", "inline", "layout", "resolution"] and bad == []


def test_the_djot_rewrite_is_the_obvious_one():
    out = scripts_call(textwrap.dedent('''
        import json, features as f
        print(json.dumps([f.to_djot("/i/ *b* _u_ ~s~ =h= H{,2,}O x{^2^} `/c/`\\n"), f.to_djot(". one\\n. two\\n"),
                          f.to_djot("|= A |= B |\\n| 1 | 2 |\\n"), f.to_djot(":: term\\n: meaning\\n"), f.to_djot("x %% note\\n"),
                          f.to_djot("```\\n/kept/\\n```\\n"), f.normalized("<p>a</p>\\n  <p>b  c</p>\\n")]))
    '''))
    inline, ordered, table, definition, comment, fence, normal = out
    assert inline == "_i_ *b* {+u+} {-s-} {=h=} H~2~O x^2^ `/c/`\n"
    assert ordered == "1. one\n1. two\n" and table == "| A | B |\n|---|---|\n| 1 | 2 |\n"
    assert definition == ": term\n\n  meaning\n" and comment == "x {% note %}\n" and fence == "```\n/kept/\n```\n"
    assert normal == "<p>a</p><p>b c</p>"


def test_features_and_areas_read_the_source():
    out = scripts_call(textwrap.dedent('''
        import json, features as f
        print(json.dumps([f.area("- a\\n+\\n> q\\n"), f.area("- a\\n  - b\\n"), f.area("> q\\nlazy\\n"), f.area("# H\\n\\nSee </#H>.\\n"),
                          f.area("{.c}\\n# H\\n"), f.area("- a\\n- b\\n"), f.area("just *text*\\n"),
                          f.features("::: note\\nx\\n:::\\n"), f.features("- [/] going\\n")]))
    '''))
    assert out[:7] == ["layout", "layout", "layout", "resolution", "attributes", "block", "inline"]
    assert "typed-containers" in out[7] and "colon-fences" in out[7] and "task-states" in out[8]


def test_settle_prefers_a_rename_that_changes_the_answer_and_keeps_its_structure():
    out = scripts_call(textwrap.dedent('''
        import json, make_cases
        item = lambda kind, variants: {"kind": kind, "index": 0, "variants": variants, "files": {"a.crv": "base"}, "stdin": None,
                                       "argv": ["a.crv"], "source": "base"}
        def run(outputs, kind="snippet", variants=("v0", "v1", "v2")):
            chosen, how = make_cases.settle(item(kind, list(variants)), outputs)
            return [chosen["source"] if chosen else None, how]
        base = {"exit": 0, "stdout": "<p>base</p>\\n"}
        same = {"exit": 0, "stdout": "<p>base</p>\\n"}
        other = {"exit": 0, "stdout": "<p>word</p>\\n"}
        shape = {"exit": 0, "stdout": "<h1>word</h1>\\n"}
        print(json.dumps([
            run({(0, -1): base, (0, 0): same, (0, 1): shape, (0, 2): other}),
            run({(0, -1): base, (0, 0): shape, (0, 1): same, (0, 2): same}),
            run({(0, -1): base, (0, 0): same, (0, 1): same, (0, 2): same}),
            run({(0, -1): base}, kind="document", variants=()),
            run({(0, -1): {"exit": None, "error": "timeout"}}),
            make_cases.js_trim("\\ufeff\\u00a0 x \\u2028\\n"), make_cases.answer_sha256(0, "<p>x</p>\\n")]))
    '''))
    assert out[0] == ["v2", "renamed, same structure"] and out[1] == ["v0", "renamed, structure changed"]
    assert out[2] == [None, "no renaming changes the answer"] and out[3] == ["base", "as generated"]
    assert out[4][0] is None and out[5] == "x"
    digest = verifier_call('import json\nfrom verifier import recorder\nprint(json.dumps(recorder.digest(0, b"<p>x</p>\\n")))')
    assert out[6] == digest, "the build's recording compares the digest the generator stored"


def test_command_line_cases_are_one_per_behaviour():
    out = scripts_call(textwrap.dedent('''
        import json, make_cases
        cases = make_cases.cli_cases()
        print(json.dumps([[c["origin"] for c in cases], [json.dumps([c["argv"], c["files"], c["stdin"]], sort_keys=True) for c in cases]]))
    '''))
    origins, inputs = out
    assert len(origins) == len(set(origins)) == len(set(inputs)) >= 20
    for behaviour in ("missing-file", "directory", "two-files", "unknown-long-option", "double-dash", "stdin-dash",
                      "invalid-utf8", "byte-order-mark", "crlf", "empty-file", "file-then-safe"):
        assert f"cli:{behaviour}" in origins, behaviour


# ---------------------------------------------------------------- the verifier

def run_verifier(tmp_path: Path, script: str, cases: list[dict], expected: dict, case_sec: float = 2,
                 output_limit: int | None = None) -> dict:
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
        verify.runcases.WORKSPACE = Path({str(tmp_path / 'tmp' / 'carve-case')!r})
        verify.runcases.HOME = Path({str(tmp_path / 'tmp' / 'carve-home')!r})
        verify.runcases.TEMP = Path({str(tmp_path / 'tmp' / 'carve-tmp')!r})
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
    cases = [{"id": f"P{i}", "files": {"page.crv": "# T\n"}, "argv": argv, "stdin": None} for i, argv in enumerate(argvs)]
    for case, kind in zip(cases, kinds or []):
        case["kind"] = kind
        case["area"] = {"document": "document", "snippet": "layout"}.get(kind, "inline")
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


def test_metrics_count_each_kind_and_area(tmp_path):
    cases, expected = plain_cases([["a"], ["b"], ["slow"], ["c"]], kinds=["document", "document", "snippet", "construct"])
    metrics = run_verifier(tmp_path, 'case "$1" in slow) exec sleep 5;; b) echo no; exit 0;; esac\necho ok\n', cases, expected,
                           case_sec=1.0)
    assert metrics["by_kind"] == {"document": {"total": 2, "run": 2, "passed": 1, "failed": 1},
                                  "snippet": {"total": 1, "run": 1, "passed": 0, "failed": 1},
                                  "construct": {"total": 1, "run": 1, "passed": 1, "failed": 0}}
    assert metrics["by_area"] == {"document": {"total": 2, "passed": 1}, "layout": {"total": 1, "passed": 0},
                                  "inline": {"total": 1, "passed": 1}}
    assert metrics["cases_failed"] == 2 and metrics["timeouts"] == 1
    assert 1.0 <= metrics["seconds_max"] < 3 and metrics["seconds_max"] <= metrics["seconds_total"]


def test_case_files_standard_input_and_arguments_reach_the_program(tmp_path):
    latin = b"caf\xe9\n".decode("utf-8", "surrogateescape")
    cases = [{"id": "P1", "files": {"docs/page.crv": latin}, "argv": ["--safe", "docs/page.crv"], "stdin": "piped\n"}]
    script = 'printf "%s|" "$@"; od -An -c docs/page.crv | tr -s " "; cat; [ -z "$(ls -A "$HOME")$(ls -A "$TMPDIR")" ] && echo clean\n'
    done = subprocess.run(["sh", "-c", "printf 'caf\\351\\n' | od -An -c | tr -s ' '"], capture_output=True, text=True)
    expected = {"P1": {"exit": 0, "stdout": "--safe|docs/page.crv|" + done.stdout + "piped\nclean\n"}}
    assert run_verifier(tmp_path, script, cases, expected)["cases_passed"] == 1, "bytes that are not UTF-8 reach the file"


def test_every_run_gets_the_same_limits(tmp_path):
    report = verifier_call(textwrap.dedent(f"""
        import json, sys
        from pathlib import Path
        from verifier import runcases
        runcases.WORKSPACE = Path({str(tmp_path / 'carve-case')!r})
        runcases.HOME, runcases.TEMP = Path({str(tmp_path / 'carve-home')!r}), Path({str(tmp_path / 'carve-tmp')!r})
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
    for name, mode in (("carve", 0o4755), ("lib/helper", 0o2775), ("lib/data", 0o4666), ("lib", 0o1777)):
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
    assert modes == {".": 0o755, "carve": 0o755, "lib": 0o755, "lib/helper": 0o755, "lib/data": 0o644, "link": modes["link"]}
    assert (top / "link").is_symlink()


def test_nothing_a_submission_writes_reaches_a_later_case(tmp_path):
    """Each run has a new workspace, HOME and TMPDIR, and what the sandbox user left anywhere it
    can write (here `shared`, standing for /tmp and the other world-writable directories) is gone
    before the next case. kill_user is left out: here the sandbox user is the one running pytest."""
    shared = tmp_path / "shared"
    shared.mkdir()
    program = tmp_path / "carve"
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
        verify.runcases.WORKSPACE = Path({str(tmp_path / 'carve-case')!r})
        verify.runcases.HOME = Path({str(tmp_path / 'carve-home')!r})
        verify.runcases.TEMP = Path({str(tmp_path / 'carve-tmp')!r})
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


def test_hashing_a_submission_is_bounded_and_never_raises(tmp_path):
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    (tmp_path / "linked").symlink_to(fifo)
    data = b"x" * ((1 << 20) + 77)
    (tmp_path / "carve").write_bytes(data)
    out = verifier_call(textwrap.dedent(f"""
        import json, verify
        from pathlib import Path
        top = Path({str(tmp_path)!r})
        verify.MAX_PROGRAM = 1 << 22
        big = top / "big"
        with open(big, "wb") as handle:
            handle.truncate((1 << 22) + 1)
        print(json.dumps([verify.identity(top / "linked"), verify.identity(top / "fifo"), verify.identity(top / "carve"),
                          verify.identity(big), verify.identity(top / "missing")]))
    """))
    linked, fifo_result, good, big, missing = out
    assert linked == {"error": "not a regular file"} and fifo_result == {"error": "not a regular file"}
    assert good == {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    assert big["error"] == "too large to hash" and missing == {"error": "FileNotFoundError"}


def test_cleanup_cost_does_not_grow_with_what_a_run_leaves(tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir()
    program = tmp_path / "carve"
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
        verify.runcases.WORKSPACE = Path({str(tmp_path / 'carve-case')!r})
        verify.runcases.HOME = Path({str(tmp_path / 'carve-home')!r})
        verify.runcases.TEMP = Path({str(tmp_path / 'carve-tmp')!r})
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
    with open(big / "carve", "wb") as handle:
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
    instruction = (STEP / "instruction.md").read_text()
    assert "under 2 GB and 200,000 files and directories" in instruction
    assert "adds at most 1 GB and 100,000 files and directories" in instruction
    hook = HOOK.read_text()
    assert "LIMIT_ENTRIES=200000" in hook and "LIMIT_BYTES=2000000000" in hook
    verify = (TESTS / "verify.py").read_text()
    assert "MAX_ENTRIES = 200_002" in verify and "MAX_BYTES = 2 << 30" in verify


def test_no_reward_exists_until_the_real_end_and_the_reward_comes_first(tmp_path):
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
        rc.disk_free = lambda path=None: (-1, -1, -1)
        unknown = rc.over_limit(1, None, before)
        print(json.dumps([sorted(found), disk, files, unknown]))
    """))
    found, disk, files, unknown = out
    assert reserved.read_text() == "0.731000" and json.loads(metrics.read_text()) == {"reward": 0.731}
    assert not any("logs" in path for path in found) and str(tree / "tmp") in found
    assert disk == "disk limit" and files == "file limit" and unknown is None
    verify = (TESTS / "verify.py").read_text()
    main = verify[verify.index("def main() -> int:"):]
    order = ['(output / ".reward.tmp").write_text("--------")', "delivery(SUBMISSION)", "sandbox()", "seal(SUBMISSION)",
             "metrics = grade(PROGRAM", "final_cleanup(owner[0], min(deadline", 'write_in_place(output / ".reward.tmp"',
             'os.replace(output / ".reward.tmp", output / "reward.txt")', 'write_in_place(output / "metrics.json"']
    assert [main.index(step) for step in order] == sorted(main.index(step) for step in order)
    assert '(output / "reward.txt").write_text' not in verify, "no valid reward before the real end"
    assert "if os.geteuid() != 0 or uid == os.geteuid()" in verify, "never kill -1 as the verifier's own uid"


# ---------------------------------------------------------------- delivery

def hook_programs() -> list[str]:
    return re.findall(r"<<'EOF'\n(.*?)\nEOF", HOOK.read_text(), re.S)


def run_hook(top: Path, entries: int = 200000, size: int = 2000000000) -> list[str]:
    """The collect hook's link fixing and measuring on `top`, as this user (the hook runs the first
    as the agent's user, the second as root, handing it what the first printed and the session
    record), after a session record of its own; the mark's lines."""
    session, fixing, measuring = hook_programs()
    state = top.parent / f".{top.name}-state"
    state.mkdir()
    done = subprocess.run([sys.executable, "-I", "-", str(state / "session.json")], input=session.replace(
        '("github.com", 443), ("pypi.org", 443), ("proxy.golang.org", 443), ("registry.npmjs.org", 443)', '("127.0.0.1", 9),'),
        text=True, capture_output=True, timeout=60)
    assert done.returncode == 0, done.stdout + done.stderr
    notes = top.parent / f".{top.name}-notes"
    with open(notes, "w") as handle:
        done = subprocess.run([sys.executable, "-I", "-", str(top), str(entries), str(size)], input=fixing, text=True,
                              stdout=handle, stderr=subprocess.STDOUT, timeout=300)
    assert done.returncode == 0, notes.read_text()
    done = subprocess.run([sys.executable, "-I", "-", str(top), str(entries), str(size), str(notes), str(state), "1", "0"],
                          input=measuring, text=True, capture_output=True, timeout=300)
    assert done.returncode == 0, done.stdout + done.stderr
    assert not notes.exists(), "the notes file is consumed"
    return (top / ".delivered").read_text().splitlines()


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
    (venv / "bin" / "python3").symlink_to(outside / "python3.12")      # absolute, outside: a venv's interpreter
    (venv / "bin" / "python").symlink_to("python3")                    # relative, inside
    (venv / "lib64").symlink_to("lib")
    (venv / "pyvenv.cfg").write_text(f"home = {outside}\n")
    target = top / "src" / "target" / "release"
    (target / "deps").mkdir(parents=True)
    (target / "deps" / "carve-0123abcd").write_bytes(b"\x7fELF binary")
    os.link(target / "deps" / "carve-0123abcd", target / "carve")       # cargo's hard link
    (top / "carve").symlink_to(target / "carve")                        # absolute, inside
    (top / "helpers").symlink_to(tmp_path / "home-tool")                # absolute directory outside
    (top / "dangling").symlink_to(tmp_path / "gone")
    os.mkfifo(top / "pipe")
    lines = run_hook(top)
    assert lines[0].startswith("delivered ") and any("dangling" in line for line in lines[1:]), lines
    assert any("pipe" in line for line in lines[1:]) and any("a copy of" in line for line in lines[1:]), lines
    assert os.readlink(top / "carve") == "src/target/release/carve" and (top / "helpers" / "lib.py").is_file()
    assert (venv / "bin" / "python3").is_file() and not (venv / "bin" / "python3").is_symlink()
    copied = tmp_path / "arrived" / "rebuild"
    platform_copy(top, copied)
    arrived = verifier_call(textwrap.dedent(f"""
        import json, verify
        from pathlib import Path
        top = Path({str(copied)!r})
        print(json.dumps([list(verify.arrived(top)), verify.delivery(top)]))
    """))
    _, counted, size = lines[0].split()
    assert arrived[0] == [int(counted), int(size)] and arrived[1][1] is False, (lines, arrived)
    assert (copied / "carve").read_bytes() == b"\x7fELF binary"
    record = json.loads((copied / ".delivery.json").read_text())
    assert record["delivered"] == lines[0] and record["listing_complete"] is True and record["kill_rounds"] == 1
    assert record["egress"] == {"127.0.0.1:9": record["egress"]["127.0.0.1:9"]} and record["egress_open"] is False
    listed = {item["path"]: item for item in record["entries"]}
    assert len(listed) == int(counted) and listed["carve"]["type"] == "link"
    assert listed["src/target/release/deps/carve-0123abcd"]["sha256"] == hashlib.sha256(b"\x7fELF binary").hexdigest()
    assert all("ctime" in item and "mtime" in item for item in record["entries"])


def test_the_delivery_mark_decides_between_an_error_a_zero_and_grading(tmp_path):
    def delivered(name: str, mark: str | None, files: dict[str, str]) -> Path:
        top = tmp_path / name / "rebuild"
        top.mkdir(parents=True)
        for path, text in files.items():
            (top / path).parent.mkdir(parents=True, exist_ok=True)
            (top / path).write_text(text)
        if mark is not None:
            (top / ".delivered").write_text(mark)
        return top
    tops = {
        "empty": delivered("empty", None, {}),
        "unmarked": delivered("unmarked", None, {"carve": "x"}),
        "refused": delivered("refused", "refused\nit holds more than 2,000,000,000 bytes: it was not copied\n", {}),
        "short": delivered("short", "delivered 3 30\n", {"carve": "x"}),
        "whole": delivered("whole", "delivered 2 4\nremoved pipe: not a file, a directory or a link\n", {"a/carve": "xyzw"}),
        "garbled": delivered("garbled", "delivered many\n", {"carve": "x"}),
    }
    out = verifier_call(textwrap.dedent(f"""
        import json, verify
        from pathlib import Path
        results = {{}}
        for name, top in {json.dumps({k: str(v) for k, v in tops.items()})}.items():
            try:
                results[name] = list(verify.delivery(Path(top)))
            except verify.EvaluationError as exc:
                results[name] = "error: " + str(exc)
        print(json.dumps(results))
    """))
    assert out["empty"].startswith("error: Nothing arrived") and out["unmarked"].startswith("error:")
    assert out["refused"][1] is True and "it was not copied" in out["refused"][0][0]
    assert out["short"].startswith("error: The copy arrived cut short") and out["garbled"].startswith("error:")
    assert out["whole"] == [["collect hook: removed pipe: not a file, a directory or a link"], False]
    small = tmp_path / "over" / "rebuild"
    small.mkdir(parents=True)
    for index in range(12):
        (small / f"f{index}").write_text("x" * 100)
    assert run_hook(small, entries=10)[0] == "refused" and sorted(os.listdir(small)) == [".delivered", ".delivery.json"]
    toml = (TASK / "task.toml").read_text()
    assert '[[verifier.collect]]\ncommand = "/usr/local/sbin/prepare-delivery"\nuser = "root"' in toml
    for phase in ("setup_begin", "setup_complete"):
        assert f'[[agent.{phase}]]\ncommand = "/usr/local/sbin/reserve-delivery-room"' in toml, phase


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


def record(tmp_path: Path, cases: list[dict]) -> tuple[subprocess.CompletedProcess, Path]:
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
        runcases.WORKSPACE = Path({str(tmp_path / 'runs' / 'carve-case')!r})
        runcases.HOME = Path({str(tmp_path / 'runs' / 'carve-home')!r})
        runcases.TEMP = Path({str(tmp_path / 'runs' / 'carve-tmp')!r})
        import recorder
        sys.argv = ["recorder.py", "record", {str(program)!r}, {str(source)!r}, {str(tmp_path / 'expected.json')!r},
                    "--keep", {str(tmp_path / 'kept.json')!r}, "--report", {str(tmp_path / 'report.json')!r}]
        recorder.main()
    """)
    (tmp_path / "runs").mkdir(exist_ok=True)
    done = subprocess.run([sys.executable, "-B", "-c", driver], capture_output=True, text=True, timeout=300)
    return done, tmp_path


def doc(i: int, text: str, digest: str | None = None, kind: str = "document") -> dict:
    case = {"id": f"P{i:04d}", "kind": kind, "area": "document", "origin": "private", "files": {"page.crv": text},
            "argv": ["page.crv"], "stdin": None, "features": [], "djot_exact": False, "djot_normalized": False}
    if digest is not None:
        case["answer_sha256"] = digest
    return case


def test_the_recorder_keeps_steady_checked_answers_and_drops_the_rest(tmp_path):
    good = lambda i: hashlib.sha256(f"0\n<p>word{i}</p>\n".encode()).hexdigest()  # noqa: E731
    done, _ = record(tmp_path, [doc(i, f"word{i}", good(i)) for i in range(10)] + [doc(90, "PANIC")])
    assert done.returncode != 0 and "crashed" in done.stdout + done.stderr, "a crash in eleven cases fails the recording"
    cases = [doc(i, f"word{i}", good(i)) for i in range(300)] + [
        doc(1000, "RANDOM"), doc(1001, "PANIC"), doc(1002, "HANG"), doc(1003, "PADDING"), doc(1004, "word1004", "0" * 64),
        doc(1005, "MISSING", hashlib.sha256(b"2\n").hexdigest(), kind="cli")]
    done, out = record(tmp_path, cases)
    assert done.returncode == 0, done.stdout + done.stderr
    report = json.loads((out / "report.json").read_text())
    kept = json.loads((out / "kept.json").read_text())["cases"]
    assert report["unsteady"] == ["P1000"] and report["crashed"] == ["P1001"] and report["slow"] == ["P1002"]
    assert report["perturbed"] == ["P1003"] and report["differs"] == ["P1004"], "an answer other than the checked one"
    ids = [case["id"] for case in kept]
    assert "P1005" in ids and len(ids) == 301 and len(report["kept_ids_sha256"]) == 64
    assert all("origin" not in case and "answer_sha256" not in case for case in kept), "the final image keeps what grading reads"
    expected = json.loads((out / "expected.json").read_text())
    assert expected["P1005"] == {"exit": 2, "stdout": ""} and expected["P0000"]["stdout"] == "<p>word0</p>\n"


def test_selection_drops_shared_answers_answers_in_the_input_and_free_cases():
    report = verifier_call(textwrap.dedent("""
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
    """))
    assert report["quoted"] == ["P1000"] and report["cli"] == 20, "the command-line cases are never dropped"
    assert report["dropped"]["answer shared by many cases"] > 0
    assert report["free"] <= 0.05 * report["kept"], report
    assert report["kept"] > 900


def test_the_recording_report_counts_kinds_baselines_and_the_djot_engine(tmp_path):
    run = {"files": {"page.crv": "x"}, "argv": ["page.crv"], "stdin": None}
    kept = [dict(run, id="P1", kind="document", area="document", features=["tables"], djot_exact=True, djot_normalized=True),
            dict(run, id="P2", kind="snippet", area="layout", features=["smart-typography"], djot_exact=False, djot_normalized=True),
            dict(run, id="P3", kind="snippet", area="inline", features=[], djot_exact=False, djot_normalized=False),
            dict(run, id="P4", kind="construct", area="block", features=["comments"], djot_exact=False, djot_normalized=False),
            {"id": "P9", "kind": "cli", "files": {}, "argv": ["missing.crv"], "stdin": None}]
    cases = [dict(case, settled="as generated", model="agrees") for case in kept] + [dict(run, id="P5", kind="mutant")]
    expected = {"P1": {"exit": 0, "stdout": "<table></table>\n"}, "P2": {"exit": 0, "stdout": "\n"},
                "P3": {"exit": 0, "stdout": "\n"}, "P4": {"exit": 0, "stdout": "<p>c</p>\n"}, "P9": {"exit": 2, "stdout": ""}}
    seconds = {i: [0.1, 0.2] for i in ("P1", "P2", "P3", "P4", "P9")}
    timing = {"keep_seconds": 1.0, "keep_cpu": 0.25, "seconds": dict(seconds, P5=[0.1, 2]), "slow": [], "unsteady": ["P5"],
              "crashed": [], "differs": [], "dropped": {}}
    for name, data in (("cases.json", {"cases": cases}), ("kept.json", {"cases": kept}), ("expected.json", expected),
                       ("timing.json", timing)):
        (tmp_path / name).write_text(json.dumps(data))
    (tmp_path / "build.txt").write_text("version carve-rs 0.1.14\nsha256 ab\n")
    subprocess.run([sys.executable, "-B", str(TESTS / "verifier" / "recording.py"),
                    *(str(tmp_path / name) for name in ("cases.json", "kept.json", "expected.json", "timing.json", "out.json")),
                    "--build", str(tmp_path / "build.txt")], check=True, capture_output=True, timeout=60, cwd=TESTS / "verifier")
    report = json.loads((tmp_path / "out.json").read_text())
    assert report["kinds_kept"] == {"cli": 1, "construct": 1, "document": 1, "snippet": 2}
    assert report["areas_kept"] == {"block": 1, "cli": 1, "document": 1, "inline": 1, "layout": 1}
    assert report["djot_engine"] == {"exact": 0.25, "layout_forgiven": 0.5} and report["divergence_share"] == 0.5
    assert report["dropped_unsteady"] == {"mutant": 1} and report["build"]["version"] == "carve-rs 0.1.14"
    baselines = report["baselines"]
    assert baselines["print_empty_line_exit_0"] == round(2 / 5, 4) and baselines["print_nothing_exit_2"] == round(1 / 5, 4)
    assert baselines["command_line_table_and_constants"] == round(3 / 5, 4), "the command line and the two empty snippets"
    assert report["spec_model"] == {"agrees": 5}


# ---------------------------------------------------------------- images, solution and what the agent sees

def test_the_verifier_records_in_a_builder_stage_and_keeps_only_the_answers():
    agent = (TASK / "environment" / "Dockerfile").read_text()
    verifier = (TESTS / "Dockerfile").read_text()
    solve = (STEP / "solution" / "solve.sh").read_text()
    base = re.search(r"^FROM (ubuntu:24\.04@sha256:[0-9a-f]{64}) AS program$", verifier, re.M).group(1)
    assert agent.count(f"FROM {base}") == 1 and verifier.count(f"FROM {base}") == 2, "every stage on the pinned base"
    final = verifier.split(f"\n\nFROM {base}\n", 1)[1]
    assert "RUN python3 -I /original/install.py /original/carve.tar.gz /original/build.txt /opt/carve/carve" in verifier
    assert "original" not in final and "/opt/carve" not in final and "carve.tar.gz" not in final
    assert re.findall(r"^COPY --from=program (\S+) (\S+)$", final, re.M) == [
        ("/record/kept.json", "/tests/private/cases.json"), ("/record/expected.json", "/tests/private/expected.json"),
        ("/record/recording.json", "/tests/private/recording.json")]
    assert "chmod -R go-rwx /tests" in final, "the answers are root's alone"
    assert re.findall(r"^COPY .*$", agent, re.M) == ["COPY spec/ /app/spec/", "COPY docs/ /app/docs/",
                                                    "COPY reserve-delivery-room prepare-delivery /usr/local/sbin/"]
    assert "carve" not in agent.replace("/app/rebuild", "").lower(), "no build of any Carve engine in the agent's image"
    assert 'install.py" "$here/carve.tar.gz" "$here/build.txt" /app/rebuild/carve' in solve
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
    good.write_text(f"version carve-rs 0.1.14\narchive_sha256 {hashlib.sha256(archive.read_bytes()).hexdigest()}\n"
                    f"sha256 {hashlib.sha256(binary).hexdigest()}\n")
    bad = tmp_path / "bad.txt"
    bad.write_text(good.read_text().replace(hashlib.sha256(binary).hexdigest(), "0" * 64))
    install = lambda build, dest: subprocess.run([sys.executable, "-I", str(TASK / "common" / "original" / "install.py"),  # noqa: E731
                                                  str(archive), str(build), str(dest)], capture_output=True, text=True, timeout=60)
    assert install(good, tmp_path / "ok" / "carve").returncode == 0 and (tmp_path / "ok" / "carve").read_bytes() == binary
    assert os.stat(tmp_path / "ok" / "carve").st_mode & 0o777 == 0o755
    assert install(bad, tmp_path / "no" / "carve").returncode != 0 and not (tmp_path / "no" / "carve").exists()
    blank = tmp_path / "blank.json"
    blank.write_text(json.dumps({"strings": ["ELF"]}))
    done = subprocess.run([sys.executable, "-I", str(TASK / "common" / "original" / "install.py"), str(archive), str(good),
                           str(tmp_path / "blanked" / "carve"), "--blank", str(blank)], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0 and (tmp_path / "blanked" / "carve").read_bytes() == b"\x7fxxx carve", "blanked in place, same length"
    solve = (STEP / "solution" / "solve.sh").read_text()
    verifier = (TESTS / "Dockerfile").read_text()
    assert '/app/rebuild/carve --blank "$here/blank.json"' in solve and "--blank" not in verifier, "only the solution blanks"
    package = (SCRIPTS / "package_step.py").read_text()
    assert 'content[f"{STEP}/solution/blank.json"]' in package and '["strings"]' in package


def test_the_agent_cannot_replace_the_artifact_directory():
    docker = (TASK / "environment" / "Dockerfile").read_text()
    assert "chown -R root:root /app" in docker and "chmod 1777 /app " in docker and "chmod 0777 /app/rebuild" in docker
    assert "useradd --uid 10001 --create-home dev" in docker
    assert "chmod 0700 /usr/local/sbin/reserve-delivery-room /usr/local/sbin/prepare-delivery" in docker
    toml = (TASK / "task.toml").read_text()
    assert 'user = "dev"' in toml and 'artifacts = ["/app/rebuild"]' in toml and 'environment_mode = "separate"' in toml
    assert toml.count('network_mode = "no-network"') == 3


def test_every_run_fits_inside_the_step_verifier_time():
    per_run = int(re.search(r"^CASE_SEC = (\d+)$", RUNNER.read_text(), re.M).group(1))
    total = int(re.search(r"^TOTAL_SEC = (\d+)", (TESTS / "verify.py").read_text(), re.M).group(1))
    step_verifier = int(re.search(r"\[steps\.verifier\]\s*timeout_sec = (\d+)", (TASK / "task.toml").read_text()).group(1))
    margin = int(re.search(r"^MARGIN_SEC = (\d+)", (TESTS / "verify.py").read_text(), re.M).group(1))
    assert 2200 * (per_run + 0.25) <= total - margin and total < step_verifier, \
        "a renderer that takes the whole stated time on every page still has every page run"
    assert f"Each run finishes within {per_run} seconds" in (STEP / "instruction.md").read_text()
    assert int(re.search(r"\[agent\]\ntimeout_sec = (\d+)", (TASK / "task.toml").read_text()).group(1)) + step_verifier <= 41000


def test_nothing_the_agent_sees_names_grading_or_a_budget():
    seen = {"Dockerfile": (TASK / "environment" / "Dockerfile").read_text(), "instruction.md": (STEP / "instruction.md").read_text(),
            "task.toml": (TASK / "task.toml").read_text()}
    for name, text in seen.items():
        lowered = text.lower()
        for word in ("oracle", "reference solution", "hidden", "grade", "grading", "score", "test case", "working session",
                     "fresh context", "hours", "candidate"):
            assert word not in lowered, (name, word)
        if name != "task.toml":
            for word in ("verifier", "private", "recorded", "case"):
                assert word not in lowered, (name, word)
    assert "#" not in seen["task.toml"]
    instruction = seen["instruction.md"]
    assert "/app/rebuild/carve" in instruction and "Out of scope:" in instruction
    for excluded in ("{{ path }}", "`fmt`", "`lint`", "`migrate`", "Markdown", "the AST as JSON", "importers", "static mode",
                     "`--help`", "`--version`"):
        assert excluded in instruction.split("Out of scope:", 1)[1], excluded
    hook = HOOK.read_text().lower()
    for word in ("grade", "score", "reward", "verifier", "hidden", "test"):
        assert word not in hook, word


def test_packaging_ships_runtime_files_only_and_flattens_cleanly():
    package = (SCRIPTS / "package_step.py").read_text()
    assert 'for directory in ("environment", STEP):' in package and '"experiment"' in package
    assert 'content[f"environment/spec/{name}"]' in package and 'content[f"environment/docs/{name}"]' in package
    assert "make_cases.leaks(" in package
    out = scripts_call(textwrap.dedent('''
        import json, package_step
        content = {"task.toml": b'schema_version = "1.4"\\nmulti_step_reward_strategy = "final"\\n[task]\\nname = "abundant/swe-m2_x_y"\\n'
                                b'\\n[[steps]]\\nname = "01-implement-renderer"\\n',
                   "steps/01-implement-renderer/instruction.md": b"do it", "environment/Dockerfile": b"FROM x"}
        flat = package_step.flatten(content)
        print(json.dumps({k: v.decode() for k, v in flat.items()}))
    '''))
    assert sorted(out) == ["environment/Dockerfile", "instruction.md", "task.toml"]
    assert 'name = "abundant/swe-m2_x_y-single"' in out["task.toml"] and "[[steps]]" not in out["task.toml"]
    assert "multi_step_reward_strategy" not in out["task.toml"]


def test_the_pins_are_stated_once_and_agree():
    text = (SCRIPTS / "carve_text.py").read_text()
    pins = dict(re.findall(r'^([A-Z0-9_]+) = "([^"]+)"', text, re.M))
    assert pins["SPEC_TAG"] == pins["CARVE_RS_TAG"] == "0.1.14"
    assert re.fullmatch(r"[0-9a-f]{40}", pins["SPEC_COMMIT"]) and re.fullmatch(r"[0-9a-f]{40}", pins["CARVE_RS_COMMIT"])
    for key in ("LINUX_ARCHIVE_SHA256", "LINUX_BINARY_SHA256", "MAC_ARCHIVE_SHA256", "MAC_BINARY_SHA256"):
        assert re.fullmatch(r"[0-9a-f]{64}", pins[key]), key
    readme = (TASK / "README.md").read_text()
    for key in ("SPEC_COMMIT", "CARVE_RS_COMMIT", "LINUX_BINARY_SHA256", "LINUX_ARCHIVE_SHA256"):
        assert pins[key] in readme, key


def test_a_fetched_build_of_the_original_is_refused(tmp_path):
    top = tmp_path / "rebuild"
    (top / "bin").mkdir(parents=True)
    fetched = b"\x7fELF" + b"q" * ((1 << 20) + 5)
    (top / "bin" / "carve-real").write_bytes(fetched)
    (top / "one-string.py").write_text("# Dropped code-block language is a phrase we never print\n")
    (top / "link").symlink_to(top / "bin" / "carve-real")
    two = tmp_path / "two.bin"
    two.write_bytes(b"x" * ((1 << 20) - 10) + b"Dropped code-block language " + b"y" * 100 + b"round-trip carrier attribute ")
    out = verifier_call(textwrap.dedent(f"""
        import json, verify
        from pathlib import Path
        top = Path({str(top)!r})
        hashes, strings, needed = verify.upstream_builds()
        mine = {{"{hashlib.sha256(fetched).hexdigest()}"}}
        first = verify.fetched_build(top, mine, strings, needed)
        (top / "bin" / "carve-real").unlink()
        (top / "two-strings.bin").write_bytes(Path({str(two)!r}).read_bytes())
        second = verify.fetched_build(top, mine, strings, needed)
        (top / "two-strings.bin").unlink()
        third = verify.fetched_build(top, mine, strings, needed)
        print(json.dumps([first, second, third, len(hashes), len(strings), needed]))
    """))
    first, second, third, hashes, strings, needed = out
    assert first == "/app/rebuild/bin/carve-real is a build of the original that upstream publishes"
    assert second == "/app/rebuild/two-strings.bin holds the text of a build of the original that upstream publishes", \
        "two strings across a 1 MB chunk boundary"
    assert third is None, "one string alone is no fetched build"
    builds = json.loads((TESTS / "verifier" / "upstream_builds.json").read_text())
    pins = dict(re.findall(r'^([A-Z0-9_]+) = "([^"]+)"', (SCRIPTS / "carve_text.py").read_text(), re.M))
    assert pins["LINUX_BINARY_SHA256"] in builds["sha256"] and pins["LINUX_ARCHIVE_SHA256"] in builds["sha256"]
    assert hashes >= 200 and strings >= 10 and needed == 2
    instruction = (STEP / "instruction.md").read_text()
    for text in builds["strings"]:
        assert text not in instruction, text
    verify = (TESTS / "verify.py").read_text()
    main = verify[verify.index("def main() -> int:"):]
    assert main.index("seal(SUBMISSION)") < main.index("fetched_build(SUBMISSION") < main.index("metrics = grade(PROGRAM")
