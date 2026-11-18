"""Development checks: cases are reproducible, comment-free and split by program; the recorder keeps
only cases that finish the same way twice; the images and the reference solution build one hardened compiler."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
STEP = TASK / "steps" / "01-rebuild-compiler"
RUNNER = STEP / "tests" / "verifier" / "runcases.py"
HARDENING = TASK / "common" / "hardening"

RUN_PROGRAM = "import std;\n// prints the sum\nfn main() {\n    var total = 0;\n    for i in 0..{n} {\n        total += i * 2;\n    }\n    print(total);\n}\n"
ERROR_PROGRAM = "// error: expected a value of type i32, got const u8[:]\n// the literal is text\nfn main() {\n    let x: i32 = \"a\";\n    print(x);\n}\n"


def checkout(tmp_path: Path) -> Path:
    root = tmp_path / "goose"
    for directory in ("test/codegen", "test/typing", "test/errors_tc", "test/expected", "test/gfx", "samples", "docs"):
        (root / directory).mkdir(parents=True, exist_ok=True)
    for index in range(40):
        directory = "codegen" if index % 2 else "typing"
        (root / "test" / directory / f"prog{index}.goose").write_text(RUN_PROGRAM.replace("{n}", str(index + 3)))
        (root / "test" / "expected" / f"prog{index}.out").write_text("0\n")
        (root / "test" / "errors_tc" / f"bad{index}.goose").write_text(ERROR_PROGRAM.replace('"a"', f'"a{index}"'))
    (root / "test" / "gfx" / "draw.goose").write_text("import gfx;\nfn main() {}\n")
    (root / "test" / "codegen" / "skip.goose").write_text("// no-jit\nfn main() {}\n")
    (root / "samples" / "hello.goose").write_text("fn main() {\n    print(\"hello\");\n}\n")
    (root / "docs" / "reference.md").write_text("Text.\n\n```goose\nfn main() {\n    print(1 + 2);\n}\n```\n\n<!-- fragment -->\n```goose\nlet y = 3;\n```\n")
    return root


def generate(tmp_path: Path, seed: int) -> tuple[list[dict], list[dict]]:
    root = checkout(tmp_path) if not (tmp_path / "goose").exists() else tmp_path / "goose"
    private, visible = tmp_path / f"p{seed}.json", tmp_path / f"v{seed}.json"
    done = subprocess.run([sys.executable, "-B", str(TASK / "scripts" / "make_cases.py"), str(root), "--count", "120", "--seed", str(seed),
                           "--visible", "20", "--out-private", str(private), "--out-visible", str(visible)],
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(private.read_text())["cases"], json.loads(visible.read_text())["cases"]


def test_cases_are_reproducible_comment_free_and_never_reuse_a_shown_program(tmp_path):
    private, visible = generate(tmp_path, 5)
    again, _ = generate(tmp_path, 5)
    assert private == again and generate(tmp_path, 6)[0] != private
    assert len(private) == 100 and len(visible) == 20
    assert all(case["id"].startswith("P") for case in private) and all(case["id"].startswith("E") for case in visible)
    texts = [text for case in private + visible for text in case["files"].values()] + [c["stdin"] or "" for c in private + visible]
    assert texts and not any("//" in text for text in texts), "comments must be stripped: the error tests name their errors in them"
    assert not any("import gfx" in text for text in texts) and not any("no-jit" in text for text in texts)
    shown = {"fn main() {\n    print(\"hello\");\n}\n", "fn main() {\n    print(1 + 2);\n}\n"}
    assert not any(text in shown for case in private for text in case["files"].values())
    kinds = {case["argv"][0] for case in private if case["argv"]}
    assert {"run", "check", "format"} <= kinds


def test_recorder_keeps_only_cases_that_finish_the_same_way_twice(tmp_path):
    program = tmp_path / "fake-goose"
    program.write_text("#!/usr/bin/env python3\nimport os, sys, time\n"
                       "if 'help' in sys.argv: print(os.urandom(4).hex())\n"
                       "elif 'version' in sys.argv: time.sleep(5)\n"
                       "else: print(' '.join(sys.argv[1:]), sorted(os.listdir('.')))\n"
                       "sys.exit(2 if 'check' in sys.argv else 0)\n")
    program.chmod(0o755)
    cases = [{"id": f"P{i}", "files": {"main.goose": "fn main() {}\n"}, "argv": argv, "stdin": None}
             for i, argv in enumerate([["run", "main.goose"], ["check", "main.goose"], ["help"], ["version"], ["format"]])]
    source, outputs, kept = tmp_path / "cases.json", tmp_path / "outputs.json", tmp_path / "kept.json"
    source.write_text(json.dumps({"cases": cases}))
    done = subprocess.run([sys.executable, "-B", str(RUNNER), "record", str(program), str(source), str(outputs), "--keep", str(kept)],
                          capture_output=True, text=True, timeout=120)
    assert done.returncode != 0 and "only 3 of 5" in done.stdout + done.stderr  # two of five dropped is below the 85% floor
    cases = cases[:2] + [cases[4]] * 8
    for index, case in enumerate(cases):
        cases[index] = dict(case, id=f"P{index}")
    cases.append({"id": "P99", "files": {}, "argv": ["help"], "stdin": None})
    source.write_text(json.dumps({"cases": cases}))
    done = subprocess.run([sys.executable, "-B", str(RUNNER), "record", str(program), str(source), str(outputs), "--keep", str(kept)],
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stdout + done.stderr
    assert [c["id"] for c in json.loads(kept.read_text())["cases"]] == [f"P{i}" for i in range(10)]
    check = subprocess.run([sys.executable, "-B", str(RUNNER), "check", str(program), str(kept), str(outputs)],
                           capture_output=True, text=True, timeout=120)
    assert check.stdout.strip().splitlines()[-1] == "10 of 10 cases pass"


def test_images_and_solution_build_one_compiler_and_ship_no_private_cases():
    agent = (TASK / "environment" / "Dockerfile").read_text()
    verifier = (STEP / "tests" / "Dockerfile").read_text()
    solve = (STEP / "solution" / "solve.sh").read_text()
    builder = agent.split("\n\nFROM ubuntu:24.04\n", 1)[0]
    assert verifier.startswith(builder), "both images must build the compiler the same way"
    for flag in ("-DGOOSE_VERSION=745901f", "-DGOOSE_STDLIB_PATH=/usr/local/share/goose/stdlib"):
        assert flag in builder and flag in solve
    final_agent = agent.split("\n\nFROM ubuntu:24.04\n", 1)[1]
    final_verifier = verifier.split("\n\nFROM ubuntu:24.04\n", 1)[1]
    assert "private" not in agent and "chown root:goose /opt/goose/goose && chmod 2711 /opt/goose/goose" in final_agent
    assert "/opt/goose" not in final_verifier, "the verifier image holds no copy of the compiler"
    assert "COPY --from=program /record/kept.json /tests/private/cases.json" in final_verifier
    assert "stdlib" not in solve.split("install -m 0755", 1)[1], "the solution ships no stdlib beside its binary"
    assert "git clone" not in agent + verifier


def test_nothing_the_agent_sees_names_a_reference_answer_or_a_budget():
    seen = {"Dockerfile": (TASK / "environment" / "Dockerfile").read_text(), "instruction.md": (STEP / "instruction.md").read_text(),
            "run_examples.py": RUNNER.read_text(), "task.toml": (TASK / "task.toml").read_text()}
    for name, text in seen.items():
        lowered = text.lower()
        for word in ("oracle", "reference solution", "hidden", "grade", "grading", "working session", "fresh context", "hours"):
            assert word not in lowered, (name, word)
    assert "#" not in seen["task.toml"]
    assert sorted(path.name for path in (TASK / "environment").iterdir()) == [".dockerignore", "Dockerfile"]


def test_every_run_fits_inside_the_step_verifier_time():
    per_run = int(re.search(r"^CASE_SEC = (\d+)$", RUNNER.read_text(), re.M).group(1))
    total = int(re.search(r"^TOTAL_SEC = (\d+)", (STEP / "tests" / "verify.py").read_text(), re.M).group(1))
    step_verifier = int(re.search(r"\[steps\.verifier\]\s*timeout_sec = (\d+)", (TASK / "task.toml").read_text()).group(1))
    assert 1500 * per_run <= total < step_verifier
    assert f"Each run finishes within {per_run} seconds" in (STEP / "instruction.md").read_text()


def test_only_documentation_and_samples_reach_the_agent():
    spec = importlib.util.spec_from_file_location("goose_rebuild_package_step", TASK / "scripts" / "package_step.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in ("README.md", "LICENSE", "docs/reference.md", "docs/design/packages.md", "samples/hello.goose", "samples/README.md"):
        assert module.shipped_docs(name), name
    for name in ("docs/testing.md", "test/errors_tc/a.goose", "test/expected/a.out", "samples/data/alice.txt", "tree-sitter/grammar.js",
                 "src/main.cpp", "docs/site/index.html", "vscode/package.json"):
        assert not module.shipped_docs(name), name


def test_all_three_builds_apply_the_hardening_before_cmake_and_prove_it_after():
    agent = (TASK / "environment" / "Dockerfile").read_text()
    builder, final_agent = agent.split("\n\nFROM ubuntu:24.04\n", 1)
    solve = (STEP / "solution" / "solve.sh").read_text()
    assert builder.index("sh /hardening/apply.sh /src") < builder.index("cmake -S") < builder.index("bash /hardening/smoke.sh")
    assert solve.index('sh "$here/hardening/apply.sh" "$src"') < solve.index("cmake -S") < solve.index("hardening/smoke.sh") \
        < solve.index("install -m 0755")
    assert "hardening" not in final_agent
    assert "hardening" not in (STEP / "tests" / "Dockerfile").read_text().split("\n\nFROM ubuntu:24.04\n", 1)[1]
    assert "extern" in (STEP / "instruction.md").read_text().split("Out of scope:", 1)[1]
    spec = importlib.util.spec_from_file_location("goose_rebuild_package_step", TASK / "scripts" / "package_step.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert set(module.DROPPED) == {"stdlib/os.goose", "stdlib/ffi.goose"}
    assert sorted(path.name for path in HARDENING.iterdir()) == ["apply.sh", "goose-hardening.patch", "smoke.sh"]


def test_the_hardening_patch_applies_and_its_refusals_are_the_ones_the_build_proves(tmp_path):
    patch = (HARDENING / "goose-hardening.patch").read_text()
    added = "\n".join(line[1:] for line in patch.splitlines() if line.startswith("+") and not line.startswith("+++"))
    removed = "\n".join(line[1:] for line in patch.splitlines() if line.startswith("-") and not line.startswith("---"))
    smoke = (HARDENING / "smoke.sh").read_text()
    assert sorted(re.findall(r"^diff --git a/(\S+)", patch, re.M)) == ["src/jit.h", "src/main.cpp", "src/packages.h", "src/parser.h"]
    for gone in ('getenv("GOOSE_TCCLIB")', 'getenv("GOOSE_STDLIB")', 'arg == "-D"', 'arg == "--include"', 'arg == "--stdlib"',
                 'arg == "--unsafe-no-rf-check"', 'cands.push_back("stdlib/")'):
        assert gone in removed and gone not in added, gone
    for message in ("extern fn is only allowed in the standard library", "sidecar files are not supported"):
        assert message in added and message in smoke
    for option in ("-D", "--include", "--stdlib", "--unsafe-no-rf-check"):
        assert f'"unknown option: {option}' in smoke, option
    for refused in ("GOOSE_TCCLIB", "GOOSE_STDLIB", "cannot find the module os", "cannot find the module ffi", "main.build"):
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
    assert all("Hardened build" in (tree / name).read_text() for name in ("src/jit.h", "src/main.cpp", "src/packages.h", "src/parser.h"))
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
