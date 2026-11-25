"""Find the kept cases whose answer one documented function of the language gives, applied once to the case's own
literals or to its input, as the original shows it. A program can print such an answer by applying a function it
sees to a literal it sees, without running the case's code, so runcases.distinct_outputs leaves these cases out.

usage: python3 derivations.py <program> <kept cases.json> <expected.json> <functions.json> <out.json>

A case is looked at when it otherwise counts (runcases.counts) and its answer is one line (`looked_at`). Its literals
(`case_literals`) are the number strands and the string and character literals of its own code, statement by
statement: its files but library ones (under lib/), the code after -e, a program on standard input. Its input
(`input_literals`) is what it gives a program to read: each line of standard input that is data (the program is
elsewhere) and each argument after the program, each as a string literal and as the number strands it holds; and,
where there is more than one line, all of them as one list of strings and all their numbers as one strand.

Its derivations (`derivations`), for each function of the documentation's table (functions.json: the glyph of every
glyph page of the documentation that calls it a function; all of them but NOT_APPLIED):
- each literal and each part of the input as it is;
- the function applied to one of them, monadically, and as a reduction;
- the function applied dyadically to the two literals the code writes on either side of it (`A f B`);
- the function applied dyadically to a literal of the code and a part of the input, in either order.

The original shows each derivation through its worker (`<program> --worker`, one request each, in a new empty
directory); a case is derived when its answer is what one of them shows. A worker that ends, stalls for REQUEST_SEC
or holds more than RSS_LIMIT bytes is ended, the request it had reached is passed over, and a new worker goes on
after it. The script stops the build (exit status 1) when the worker does not show CHECK's answer right, or passes
over more than SKIPPED_SHARE of the requests: the cases it would write could not be trusted then. It writes
{"derived": [ids], "looked_at": n, "derivations": n, "passed_over": n, "functions": n}.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Iterator
from pathlib import Path

try:  # run as a script beside runcases.py, or imported from the verifier package
    from recorder import program_of, statements
    from runcases import ENV, counts, limit
except ImportError:
    from .recorder import program_of, statements
    from .runcases import ENV, counts, limit

# Functions of the table that are not applied: ¿ gives a random result, and ⍎ runs the text it is given as code.
NOT_APPLIED = ("¿", "⍎")
CHUNK = 1000             # requests one worker gets at most
REQUEST_SEC = 10         # a worker that answers nothing for this long is ended
RSS_LIMIT = 512 << 20    # bytes of memory a worker may hold; past it, it is ended
LINE_LIMIT = 1 << 20     # bytes of one reply kept at most; a longer one shows no one-line answer
SKIPPED_SHARE = 0.01     # requests that may be passed over, at most
CHECK = ("⌽1 2 3", "3 2 1")  # a derivation, and what the original shows for it
NUMBER = r"¯?(?:\d+(?:\.\d*)?|\.\d+)(?:[eEₑ]¯?\d+)?(?:j¯?\d+(?:\.\d+)?)?[ₓᵣₛₕ]?"
LITERAL = rf'"(?:[^"]|"")*"|\'(?:[^\']|\'\')\'|(?<![\w.¯]){NUMBER}(?: +{NUMBER})*(?![\w.])'
LITERALS = re.compile(LITERAL)


def looked_at(case: dict, answer: dict) -> bool:
    """Whether a case's answer is looked for among its derivations: it counts otherwise (runcases.counts)
    and is one line, ended by a newline."""
    stdout = answer["stdout"]
    return counts(case, answer) and stdout.endswith("\n") and "\n" not in stdout[:-1]


def string(text: str) -> str:
    """BPL's string literal for a text: in double quotes, each double quote in it doubled."""
    return '"' + text.replace('"', '""') + '"'


def case_literals(case: dict) -> list[str]:
    """The literals of a case's own code, each once, in the order the code holds them.

    Called by derivations. The number strands and the string and character literals of each statement
    (recorder.statements: comments left out) of its files but library ones (under lib/), of the code
    after -e and of a program on standard input.

    Args:
        case: A kept case: "argv", "files" and "stdin".

    Returns:
        The literals as BPL text. Reads and changes nothing.
    """
    program = program_of(case)
    texts = [text for path, text in sorted(case["files"].items()) if not path.startswith("lib/")]
    if case["argv"][:1] == ["-e"] and len(case["argv"]) > 1:
        texts.append(case["argv"][1])
    if program is not None and program not in texts:
        texts.append(program)
    return list(dict.fromkeys(literal for text in texts for statement in statements(text)
                              for literal in LITERALS.findall(statement)))


def input_literals(case: dict) -> list[str]:
    """What a case gives a program to read, as BPL literals, each once.

    Called by derivations. Each line of standard input that is data (the case's program is elsewhere) and
    each argument after the program, as a string literal and as the number strands it holds; where there
    is more than one, all of them as one list of strings and all their numbers as one strand.

    Args:
        case: A kept case: "argv", "files" and "stdin".

    Returns:
        The parts of the input as BPL text. Reads and changes nothing.
    """
    program, argv = program_of(case), case["argv"]
    lines = case["stdin"].splitlines() if case.get("stdin") and program != case.get("stdin") else []
    lines += argv[2:] if argv[:1] == ["-e"] else argv[1:] if argv and (argv[0] in case["files"] or argv[0] == "-") else []
    found = [part for line in lines for part in (string(line), *LITERALS.findall(line))]
    if len(lines) > 1:
        found.append(" ".join(string(line) for line in lines))
        numbers = [number for line in lines for strand in LITERALS.findall(line) if not strand.startswith(('"', "'"))
                   for number in strand.split()]
        if numbers:
            found.append(" ".join(numbers))
    return list(dict.fromkeys(found))


def derivations(case: dict, functions: list[str]) -> set[str]:
    """What one function of the table makes of a case's literals and input, as BPL code.

    Called by derived_cases. Each literal and part of the input as it is; each function applied to one of
    them monadically (`fL`) and as a reduction (`f/L`); each function applied dyadically to the two
    literals the code writes on either side of it (`(A)fB` where a statement holds `A f B`); and each
    function applied dyadically to a literal of the code and a part of the input, in either order.

    Args:
        case: A kept case.
        functions: The documentation's table, NOT_APPLIED already left out.

    Returns:
        The derivations' code. Reads and changes nothing.
    """
    own, given = case_literals(case), input_literals(case)
    found = set(own) | set(given)
    for function in functions:
        for literal in (*own, *given):
            found.update((f"{function}{literal}", f"{function}/{literal}"))
        for literal in own:
            for part in given:
                found.update((f"({literal}){function}{part}", f"({part}){function}{literal}"))
    written = re.compile(rf"(?=({LITERAL})\s*({'|'.join(map(re.escape, functions))})\s*({LITERAL}))")
    program, texts = program_of(case), [text for path, text in sorted(case["files"].items()) if not path.startswith("lib/")]
    texts += [case["argv"][1]] if case["argv"][:1] == ["-e"] and len(case["argv"]) > 1 else []
    texts += [program] if program is not None and program not in texts else []
    for text in texts:
        for statement in statements(text):
            found.update(f"({match[1]}){match[2]}{match[3]}" for match in written.finditer(statement))
    return found


def resident(pid: int) -> int:
    """The bytes of memory a process holds now: from /proc where the system has it, else from ps; 0
    where neither answers (a process just gone)."""
    try:
        return int(Path(f"/proc/{pid}/statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE")
    except (OSError, ValueError, IndexError):
        pass
    try:
        done = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True, timeout=10)
        return int(done.stdout.strip() or 0) * 1024
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0


def replies(proc: subprocess.Popen) -> Iterator[bytes]:
    """The worker's reply lines, one at a time as they come, until it ends; each cut to LINE_LIMIT bytes (a
    longer one is no JSON then). Each read marks the worker as heard from (`proc.heard`), for the watch
    that ends a worker that stalls."""
    line = b""
    while True:
        part = proc.stdout.readline(LINE_LIMIT)
        if not part:
            return
        proc.heard = time.monotonic()
        if len(line) < LINE_LIMIT:
            line += part
        if part.endswith(b"\n"):
            yield line[:LINE_LIMIT]
            line = b""


def show(program: str, codes: list[str], workdir: str, wanted: set[str] | None = None) -> tuple[dict[str, str], int]:
    """What the original shows for each code, through its worker, CHUNK requests per worker.

    Called by derived_cases and main. The worker runs in `workdir` with the case runs' environment and
    limits (runcases.ENV, runcases.limit), HOME and TMPDIR there too. A worker that ends early, answers
    nothing for REQUEST_SEC or holds more than RSS_LIMIT bytes is ended; the request after its last reply
    is passed over, and a new worker goes on after it.

    Args:
        program: The original's path.
        codes: BPL code, one request each.
        workdir: A new empty directory.
        wanted: Where given, only these displays are kept (the answers looked for), to bound memory.

    Returns:
        The display shown, by code, for each code that ran without an error and showed one (when wanted);
        and the number of requests passed over.
    """
    shown, passed_over, at = {}, 0, 0
    env = dict(ENV, HOME=workdir, TMPDIR=workdir, RAYON_NUM_THREADS="1")
    while at < len(codes):
        chunk = codes[at:at + CHUNK]
        proc = subprocess.Popen([program, "--worker"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                cwd=workdir, env=env, preexec_fn=limit)
        proc.heard = time.monotonic()
        requests = "".join(json.dumps({"id": index, "code": code}, ensure_ascii=False) + "\n" for index, code in enumerate(chunk))

        def write(proc: subprocess.Popen = proc, data: bytes = requests.encode("utf-8")) -> None:
            try:
                proc.stdin.write(data)
                proc.stdin.close()
            except OSError:  # the worker ended before reading every request
                pass

        def watch(proc: subprocess.Popen = proc) -> None:
            while proc.poll() is None:
                if resident(proc.pid) > RSS_LIMIT or time.monotonic() - proc.heard > REQUEST_SEC:
                    proc.kill()
                    return
                time.sleep(0.05)

        threading.Thread(target=write, daemon=True).start()
        threading.Thread(target=watch, daemon=True).start()
        last = -1
        for line in replies(proc):
            try:
                reply = json.loads(line.decode("utf-8", "surrogateescape"))
            except ValueError:
                continue
            if not isinstance(reply, dict) or type(reply.get("id")) is not int or not 0 <= reply["id"] < len(chunk):
                continue
            last = max(last, reply["id"])
            result = reply.get("result")
            if not isinstance(result, dict) or result.get("error") is not None:
                continue
            for item in result.get("output") or []:
                data = item.get("data") if isinstance(item, dict) and item.get("kind") == "display" else None
                text = data.get("text/plain") if isinstance(data, dict) else None
                if isinstance(text, str) and (wanted is None or text in wanted):
                    shown[chunk[reply["id"]]] = text
        proc.wait()
        if last + 1 < len(chunk):  # the worker ended at the request after its last reply: pass it over
            passed_over += 1
            at += last + 2
        else:
            at += len(chunk)
    return shown, passed_over


def derived_cases(program: str, cases: list[dict], expected: dict, functions: list[str], workdir: str) -> tuple[list[str], dict]:
    """The cases looked at whose answer one of their derivations shows, and figures on the search.

    Called by main.

    Args:
        program: The original's path.
        cases: The kept cases.
        expected: Their recorded answers by id.
        functions: The documentation's table, NOT_APPLIED already left out.
        workdir: A new empty directory the worker runs in.

    Returns:
        The derived cases' ids, sorted; and {"looked_at": cases looked at, "derivations": requests made,
        "passed_over": requests passed over}.
    """
    by_case = {case["id"]: derivations(case, functions) for case in cases if looked_at(case, expected[case["id"]])}
    answers = {expected[ident]["stdout"][:-1] for ident in by_case}
    codes = sorted({code for found in by_case.values() for code in found})
    shown, passed_over = show(program, codes, workdir, answers)
    derived = sorted(ident for ident, found in by_case.items() if any(shown.get(code) == expected[ident]["stdout"][:-1] for code in found))
    return derived, {"looked_at": len(by_case), "derivations": len(codes), "passed_over": passed_over}


def main() -> None:
    """Write the derived cases, or stop the build where the original's worker cannot be trusted."""
    if len(sys.argv) != 6:
        raise SystemExit(__doc__)
    program, cases_path, expected_path, table_path, out_path = sys.argv[1:6]
    cases = json.loads(Path(cases_path).read_text(encoding="utf-8"))["cases"]
    expected = json.loads(Path(expected_path).read_text(encoding="utf-8"))
    functions = [function for function in json.loads(Path(table_path).read_text(encoding="utf-8"))["functions"]
                 if function not in NOT_APPLIED]
    with tempfile.TemporaryDirectory() as workdir:
        checked, _ = show(program, [CHECK[0]], workdir)
        if checked.get(CHECK[0]) != CHECK[1]:
            raise SystemExit(f"derivations.py: the worker showed {checked.get(CHECK[0])!r} for {CHECK[0]}, not {CHECK[1]!r}")
        derived, figures = derived_cases(program, cases, expected, functions, workdir)
    if figures["passed_over"] > SKIPPED_SHARE * figures["derivations"]:
        raise SystemExit(f"derivations.py: {figures['passed_over']} of {figures['derivations']} derivations were passed over")
    Path(out_path).write_text(json.dumps(dict(figures, derived=derived, functions=len(functions)), sort_keys=True) + "\n")
    print(f"derivations.py: {len(derived)} of {figures['looked_at']} cases derived, from {figures['derivations']} derivations "
          f"({figures['passed_over']} passed over)")


if __name__ == "__main__":
    main()
