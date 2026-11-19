"""Record what the original `bpl` prints for each private case, when the verifier image is built.

usage: python3 recorder.py record <program> <cases.json> <expected.json> [--keep <kept.json>] [--report <report.json>]

Each case is first settled (`settle`): of the rewrites the generator made of it, the first that
ends the way the case's own inputs do and prints something else, and nothing trivial where the base
does not, is chosen (the base where none does). The settled case is run three times with four
worker threads (MAIN_ENV, so the builder's core count changes nothing) and a fourth time perturbed
(`perturbed`: another binary path, padding in the environment, a smaller stack, one CPU and a single
worker thread), and kept if all four print the same and end normally (`crashed`), print nothing that
depends on the machine (`MACHINE`, on either output stream), the three used at most KEEP_CPU seconds
of CPU and KEEP_SEC of wall time each, and, for a display case, its display setting changes what it
prints (`unset`). Last, by rule and by id, `select` leaves out the cases whose answers take no
interpreter to give (`no_interpreter`) and those that print the last bits of the maths library
(`last_bits`).
`--keep` writes the cases kept, without their "record" entries, and `--report` how each run went
and why cases were left out.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import resource
import shutil
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

try:  # run as a script beside runcases.py, or imported from the verifier package
    from runcases import ENCODING, LIMITS, clear_workspace, limit
    from runcases import run_case as run_once
except ImportError:
    from .runcases import ENCODING, LIMITS, clear_workspace, limit
    from .runcases import run_case as run_once

KEEP_SEC = 1.0    # wall time of each of the two runs, at most: generous, since a busy builder is slow
KEEP_CPU = 0.25   # CPU time of each, at most, which a busy builder hardly changes: an eighth of the run limit
# A run of the original that ends in one of these on standard error, or with an exit status other
# than 0, 1 and 2 (the interpreter's own), or by a signal, is no answer an implementation can give.
CRASH_MARKERS = (b"panicked at", b"memory guard:", b"stack overflow", b"fatal runtime error", b"Segmentation", b"core dumped")
# Answers that depend on the machine that records them (the memory limit is half its memory).
MACHINE = (b"memory limit of", b" MiB")
PAIR_SHARE = 0.015   # cases kept with any one (stdout, exit code), the command line aside, at most
FLOOR_SHARE = 0.05   # cases a dispatcher with no interpreter passes (free_cases), at most
QUOTE_LEN = 12       # an answer at least this long that the case's own input holds is free
PERTURBED_ENV = {"BPL_PERTURBED_PADDING": "p" * 4096, "RAYON_NUM_THREADS": "1"}
MAIN_ENV = {"RAYON_NUM_THREADS": "4"}  # the main runs' worker threads: the verifier's and the agent's CPU count
MAIN_RUNS = 3
# What the original computes with its own approximations and solvers, whose last bits the docs do
# not promise (within 4 ULP; "need not agree bit for bit"): circular functions and their inverses,
# exp and power, gamma and binomials, matrix division, decompositions, numeric inverses. A case whose
# own code uses one and whose answer shows a float to 15 or more significant digits, an exponent of
# -12 or lower, or a 32- or 16-bit float, prints those bits, which no clean-room build can derive.
LAST_BIT_CODE = ("○", "*", "⊛", "!", "⌹", "⌻", "⨸", "•decompose", "•special", "∧")
NUMERIC_INVERSE = re.compile(r"(?<![A-Za-z])⁻")  # ⁻ after a function, not a system function's own inverse (•csv⁻)
DYADIC_ROOT = re.compile(r"[\dωα)\]∞]\s*√")  # a root other than the square root: an approximation too
FLOAT_RE = re.compile(r"(?<![\w.])[¯-]?(\d+)(?:\.(\d+))?(?:[eEₑ]([¯+-]?\d+))?([ₛₕ])?")
RESIDUE_DIGITS = 10  # a float with an exponent of -12 or lower shows last bits only with this many digits or more
TRIVIAL = {"0", "⍬", "$f", "0ₓ", "0.0", '""', "''"}  # tokens of an answer that tells nothing


def run_case(program: list[str], case: dict, **options) -> dict:
    """runcases.run_case, again (twice at most) where the run was stopped by the disk or file
    limit. Those count only the run's own files, which the original never writes, so a stop there
    is the builder's doing (a workspace on a filesystem that cannot be counted); never kept as an
    answer either way."""
    for _ in range(2):
        got = run_once(program, case, **options)
        if got.get("error") not in ("disk limit", "file limit"):
            return got
    return run_once(program, case, **options)


def crashed(got: dict) -> bool:
    """A finished run of the original that is no answer: killed by a signal, an exit status other
    than 0, 1 or 2, or a panic, abort or allocation failure reported on standard error."""
    if got["exit"] is None:
        return False
    return got["exit"] not in (0, 1, 2) or any(marker in got.get("stderr", b"") for marker in CRASH_MARKERS)


def inputs(case: dict, option: dict) -> dict:
    """The case with one option's inputs (argv, files, stdin) in place of its own."""
    return dict(case, **{key: option[key] for key in ("argv", "files", "stdin") if key in option})


def settle(program: str, case: dict, plan: dict) -> tuple[dict, str]:
    """The case as it is recorded, from its "record" entry (`plan`), and how it was settled.

    The case's own inputs are the base. Each of `plan["variants"]` (other argv, files or stdin) is
    tried in order: the first that ends as the base does (the same exit code, printing something
    where the base does) and prints something else is kept; failing that, the first that ends the
    same and prints the same; failing that, the base.
    """
    options = plan.get("variants", [])
    if not options:
        return case, "as generated"
    base = run_case([program], case, keep_stderr=True, env=MAIN_ENV)
    fallback = None
    for index, option in enumerate(options):
        candidate = inputs(case, option)
        got = run_case([program], candidate, keep_stderr=True, env=MAIN_ENV)
        if got["exit"] is None or crashed(got) or got["exit"] != base["exit"] or (base["stdout"] and not got["stdout"]):
            continue
        if trivial(got["stdout"]) and not trivial(base["stdout"]):  # a rewrite that left nothing to check
            continue
        if got["stdout"] != base["stdout"]:
            return candidate, f"variant {index}"
        fallback = fallback if fallback is not None else (index, candidate)
    if fallback is not None:
        return fallback[1], f"variant {fallback[0]}, output as the base's"
    return case, "base"


def trivial(stdout: bytes | str) -> bool:
    """Whether an answer tells nothing: empty, or only zeros, empty vectors and falses."""
    text = stdout.decode(*ENCODING) if isinstance(stdout, bytes) else stdout
    return all(token in TRIVIAL for token in re.split(r"[\s\[\]◇]+", text) if token)


def group(case: dict) -> str:
    """What a case asks, as a dispatcher could tell without reading its program: its kind."""
    return case.get("kind", "?")


def own_code(case: dict) -> str:
    """The text of a case that is its own: its files (upstream's libraries under lib/ aside), its
    arguments and its standard input."""
    files = [text for path, text in sorted(case["files"].items()) if not path.startswith("lib/")]
    requests = []
    if case["argv"][:1] == ["--worker"]:  # a request's code as the worker reads it, escapes undone
        for line in (case.get("stdin") or "").splitlines():
            try:
                requests.append(json.dumps(json.loads(line), ensure_ascii=False))
            except ValueError:
                continue
    return "\n".join(files + case["argv"] + [case.get("stdin") or ""] + requests)


def shows_bits(text: str) -> bool:
    """Whether text shows a float to 15 or more significant digits, as a residue (an exponent of
    -12 or lower with RESIDUE_DIGITS or more digits; 1ₑ¯17 is an exact literal, 2.220446049ₑ¯16 is
    not), or as a 32- or 16-bit float."""
    for whole, fraction, exponent, small in FLOAT_RE.findall(text):
        if not fraction and not exponent:
            continue  # an integer is exact
        digits = len((whole + fraction).lstrip("0"))
        if small or digits >= 15:
            return True
        if exponent and int(exponent.replace("¯", "-")) <= -12 and digits >= RESIDUE_DIGITS:
            return True
    return False


def last_bits(case: dict, answer: str) -> bool:
    """Whether the answer shows the last bits of a result the original computes with its own
    approximations or solvers (LAST_BIT_CODE, NUMERIC_INVERSE): a float `shows_bits`, from a case
    whose own code uses one. In a worker session, whose replies carry every float in full, it is
    the reply to a request that uses one (one reply per request, in order; a request's reply holds
    its value even with echo off, so an assignment shows the bits where they arise)."""
    uses = lambda text: (any(name in text for name in LAST_BIT_CODE) or bool(NUMERIC_INVERSE.search(text))  # noqa: E731
                         or bool(DYADIC_ROOT.search(text)))
    if not uses(own_code(case)):
        return False
    if case["argv"][:1] != ["--worker"]:
        return shows_bits(answer)
    try:
        requests = [json.loads(line) for line in (case.get("stdin") or "").splitlines() if line.strip()]
    except ValueError:
        return shows_bits(answer)
    replies = answer.splitlines()
    if len(replies) != len(requests):  # not one reply per request: judge the session whole
        return shows_bits(answer)
    return any(uses(json.dumps(request, ensure_ascii=False)) and shows_bits(reply) for request, reply in zip(requests, replies))


def statements(text: str) -> list[str]:
    """A program's statements as a dispatcher would split them: by line and by ◇, blank and
    comment-only lines left out."""
    found = []
    for line in text.splitlines():
        for part in line.split("◇"):
            part = part.split("⍝", 1)[0].strip()
            if part:
                found.append(part)
    return found


LITERAL_RE = re.compile(r'^(?:"[^"\\]*"|ι\d+|[¯\d. ]+)$')
INTEGERS = r"¯?\d+(?: ¯?\d+)*"
# The generator's own lead forms (make_cases.LEADS), as a dispatcher with no interpreter could still
# evaluate them: the number N, and how the original shows the value.
LEAD_FORMS = (
    (re.compile(r"^\+/ι(\d+)$"), lambda m: str(int(m[1]) * (int(m[1]) - 1) // 2)),
    (re.compile(r"^(\d+)×ι(\d+)$"), lambda m: " ".join(str(int(m[1]) * i) for i in range(int(m[2])))),
    (re.compile(r"^⌽ι(\d+)$"), lambda m: " ".join(str(i) for i in reversed(range(int(m[1]))))),
    (re.compile(r'^⌽"([^"]*)"$'), lambda m: '"' + m[1][::-1] + '"'),
    (re.compile(r'^≢"([^"]*)"$'), lambda m: f"{len(m[1])}ₓ"),
    (re.compile(rf"^⌈/({INTEGERS})$"), lambda m: str(max(int(v.replace("¯", "-")) for v in m[1].split())).replace("-", "¯")),
    (re.compile(rf"^\+/({INTEGERS})$"), lambda m: str(sum(int(v.replace("¯", "-")) for v in m[1].split())).replace("-", "¯")),
    (re.compile(r"^(\d+)\+(\d+)×(\d+)$"), lambda m: str(int(m[1]) + int(m[2]) * int(m[3]))),
)


def literal_value(text: str, evaluate: bool = False) -> str | None:
    """How the original shows a literal a dispatcher can echo: a string (quoted), ιN (0 to N-1)
    or a strand of plain numbers; with `evaluate`, also the value of one of the generator's lead
    forms (LEAD_FORMS); None for anything else."""
    text = text.strip()
    if evaluate:
        for form, value in LEAD_FORMS:
            match = form.match(text)
            if match:
                return value(match)
    if not LITERAL_RE.match(text) or not text:
        return None
    if text.startswith("ι"):
        return " ".join(str(index) for index in range(int(text[1:])))
    if text.startswith('"'):
        return text
    numbers = text.split()
    return " ".join(numbers) if numbers and all(re.fullmatch(r"¯?\d+", number) for number in numbers) else None


def program_of(case: dict) -> str | None:
    """The program a dispatcher reads: the `-e` code, the file named first, or standard input for
    `-` or no arguments; None for the worker and the other command-line cases."""
    argv = case["argv"]
    if argv[:1] == ["-e"] and len(argv) > 1:
        return argv[1]
    if argv and argv[0] in case["files"]:
        return case["files"][argv[0]]
    if argv[:1] == ["-"] or not argv:
        return case.get("stdin")
    return None


STRAND_RE = re.compile(r'"[^"\\]*"|(?<![\w.¯])¯?\d+(?:\.\d+)?(?: ¯?\d+(?:\.\d+)?)*')


def last_literal(case: dict) -> tuple[str, int] | None:
    """The answer of a dispatcher that echoes the last number strand or string literal anywhere in
    the program (a value assigned and then named, say); None where there is none."""
    program = program_of(case)
    found = STRAND_RE.findall("\n".join(statements(program))) if program else []
    return (found[-1] + "\n", 0) if found else None


def error_instances(cases: list[dict], outputs: dict) -> list[tuple[str, str, set[str], tuple[str, int]]]:
    """The guarded error cases whose handler prints the message (`$e.message`) or the kind and the
    message: their id, handler, the glyph features of the code inside the guard (system names,
    glyphs, glyph bigrams) and their answer."""
    found = []
    for case in cases:
        text = case["files"].get("main.bpl") if case.get("kind") == "error" else None
        match = re.search(r"\{∞::(.*?)(?: ◇ |\n)", text, re.S) if text else None
        if not match or match[1].strip() not in ("$e.message", '$e.kind,": ",$e.message'):
            continue
        body = text[match.end():]
        names = set(re.findall(r"•\w+", body))
        glyphs = [ch for ch in re.sub(r"•\w+", " ", body) if not (ch.isalnum() or ch in " \n\"'_.") or ch in "ιρωαₓⱼᵣₑ"]
        found.append((case["id"], match[1].strip(), names | set(glyphs) | {a + b for a, b in zip(glyphs, glyphs[1:])},
                      (outputs[case["id"]]["stdout"], outputs[case["id"]]["exit"])))
    return found


def error_lookup(cases: list[dict], outputs: dict) -> list[str]:
    """The guarded error cases a lookup trained on the other cases' own answers (leave one out: a
    generous bound, since no submission sees them) gets right: the message of the case whose code
    shares the most glyph features (Jaccard; ties to the more common message), shown the way the
    case's handler shows it."""
    instances = error_instances(cases, outputs)
    message = lambda answer: answer[0].strip().strip('"').split(": ", 1)[-1]  # noqa: E731
    kind = lambda answer: answer[0].strip().strip('"').split(": ", 1)[0] if ": " in answer[0] else "DOMAIN"  # noqa: E731
    common = Counter(message(answer) for *_, answer in instances)
    hits = []
    for ident, handler, feats, answer in instances:
        best, score = None, -1.0
        for other_id, _, other_feats, other_answer in instances:
            if other_id == ident:
                continue
            overlap = len(feats & other_feats) / (len(feats | other_feats) or 1)
            if overlap > score or (overlap == score and common[message(other_answer)] > common[message(best)]):
                best, score = other_answer, overlap
        if best is None:
            continue
        guess = f'"{message(best)}"\n' if handler == "$e.message" else f'"{kind(best)}: {message(best)}"\n'
        if (guess, 0) == answer:
            hits.append(ident)
    return hits


def shape(case: dict) -> tuple:
    """What a submission sees of a case before reading its program: the arguments with programs and
    paths replaced by placeholders, whether standard input is given, and how many files."""
    argv = tuple("CODE" if index and case["argv"][index - 1] == "-e" else "FILE" if value in case["files"] else value
                 for index, value in enumerate(case["argv"]))
    return argv, case.get("stdin") is not None, len(case["files"])


def echoed(case: dict, evaluate: bool = False) -> tuple[str, int] | None:
    """The answer of a dispatcher that echoes a program's leading `⎕←` literals (with `evaluate`,
    the generator's lead forms too) and exits 1 at the first other statement (0 where there is
    none); for `-e` with a single literal, that literal. None where the case's program does not
    start with one."""
    argv = case["argv"]
    if argv[:1] == ["-e"] and len(argv) > 1:
        shown = literal_value(argv[1], evaluate)
        return (shown + "\n", 0) if shown is not None else None
    program = case["files"].get(argv[0]) if argv and argv[0] in case["files"] else \
        (case.get("stdin") if argv[:1] == ["-"] else None)
    if program is None:
        return None
    printed = []
    for statement in statements(program):
        shown = literal_value(statement[2:], evaluate) if statement.startswith("⎕←") else None
        if shown is None:
            return ("".join(line + "\n" for line in printed), 1) if printed else None
        printed.append(shown)
    return "".join(line + "\n" for line in printed), 0


def no_interpreter(cases: list[dict], outputs: dict) -> dict[str, list[str]]:
    """The cases that the strongest dispatcher with no interpreter in it answers (QA waves 1 and 2
    and the round-2 re-check: a stub, trivial heuristics, echoes, a lookup), by strategy; a case
    may fall to more than one. The strategies: every command-line case (a table of the original's
    answers); a program that starts with `⎕←` literals, echoed and then exit 1 at the first other
    statement (`echoed`), and the same with the generator's lead forms evaluated (`LEAD_FORMS`);
    an echo of the program's last number strand or string literal (`last_literal`); a lookup of
    error messages trained on the other cases' own answers (`error_lookup`); and for the rest, the
    most common answer among the cases of the same visible shape (`shape`) where two or more share
    it. `free_union` is what a dispatcher using all of them passes."""
    answer = lambda case: (outputs[case["id"]]["stdout"], outputs[case["id"]]["exit"])  # noqa: E731
    free: dict[str, list[str]] = defaultdict(list)
    rest: dict[tuple, list[dict]] = defaultdict(list)
    for case in cases:
        if group(case) == "cli":
            free["command-line table"].append(case["id"])
            continue
        if echoed(case) == answer(case):
            free["echoed literals"].append(case["id"])
        elif echoed(case, evaluate=True) == answer(case):
            free["lead forms evaluated"].append(case["id"])
        if last_literal(case) == answer(case):
            free["last literal echoed"].append(case["id"])
        if echoed(case) is None and echoed(case, evaluate=True) is None:
            rest[shape(case)].append(case)
    free["error lookup"] = error_lookup(cases, outputs)
    for key, members in rest.items():
        common, shared = max(Counter(map(answer, members)).items(), key=lambda item: (item[1], repr(item[0])))
        if shared > 1:
            free[f"constant for {' '.join(key[0]) or 'no arguments'}"] += [case["id"] for case in members if answer(case) == common]
    return {how: ids for how, ids in free.items() if ids}


def free_union(free: dict[str, list[str]]) -> set[str]:
    """The cases any strategy of `no_interpreter` passes, each once."""
    return {ident for ids in free.values() for ident in ids}


def free_cases(cases: list[dict], outputs: dict) -> dict[str, list[str]]:
    """The cases a program with no interpreter in it answers, by how (`no_interpreter`)."""
    return no_interpreter(cases, outputs)


def quoted(case: dict, answer: str) -> bool:
    """Whether the case's own input holds its whole answer (at least QUOTE_LEN characters of it):
    a submission could print it without interpreting anything."""
    text = answer.strip()
    if len(text) < QUOTE_LEN:
        return False
    held = "\n".join(list(case["files"].values()) + [case.get("stdin") or ""] + case["argv"])
    return text in held


def select(cases: list[dict], outputs: dict) -> tuple[list[dict], dict[str, list[str]]]:
    """The recorded cases less, in this order and each time by id: those whose input holds their
    answer (`quoted`); beyond PAIR_SHARE of the cases, those with an answer that many others share
    (the command line aside); and while more than FLOOR_SHARE of them can be answered without an
    interpreter (`free_cases`), one of those in the largest group. Also the ids left out, by reason."""
    dropped: dict[str, list[str]] = defaultdict(list)
    kept = []
    for case in cases:
        if quoted(case, outputs[case["id"]]["stdout"]):
            dropped["input holds the answer"].append(case["id"])
        elif last_bits(case, outputs[case["id"]]["stdout"]):
            dropped["prints the maths library's last bits"].append(case["id"])
        else:
            kept.append(case)
    # The command-line cases are never dropped, so they take their share of an answer first.
    limit_, cases = max(1, int(PAIR_SHARE * len(kept))), kept
    seen = Counter((outputs[case["id"]]["stdout"], outputs[case["id"]]["exit"]) for case in cases if group(case) == "cli")
    kept = []
    for case in cases:
        answer = (outputs[case["id"]]["stdout"], outputs[case["id"]]["exit"])
        if group(case) != "cli":
            seen[answer] += 1
            if seen[answer] > limit_:
                dropped["answer shared by many cases"].append(case["id"])
                continue
        kept.append(case)
    while True:
        free = free_cases(kept, outputs)
        groups = [name for name in free if name != "command-line table" and free[name]]
        if len(free_union(free)) <= FLOOR_SHARE * len(kept) or not groups:
            break
        victim = max(free[max(groups, key=lambda name: (len(free[name]), name))])
        dropped["passed with no interpreter"].append(victim)
        kept = [case for case in kept if case["id"] != victim]
    return kept, dict(dropped)


def perturbed_limits() -> None:
    """`limit`, then a stack 256 KB smaller (another stack placement) and one CPU."""
    limit()
    try:
        resource.setrlimit(resource.RLIMIT_STACK, (LIMITS[resource.RLIMIT_STACK] - (256 << 10),) * 2)
    except (ValueError, OSError):
        pass
    try:
        os.sched_setaffinity(0, {sorted(os.sched_getaffinity(0))[0]})
    except (AttributeError, OSError, IndexError):
        pass


def relocated(program: str) -> str:
    """A copy of the program under a longer path of its own."""
    place = Path(tempfile.mkdtemp(prefix="bpl-perturbed-location-")) / "bin"
    place.mkdir()
    shutil.copy2(program, place / Path(program).name)
    return str(place / Path(program).name)


def host() -> dict:
    """What of the machine could change an answer: CPU and its vector extensions, kernel, CPUs
    usable and physical memory."""
    info = {"machine": platform.machine(), "cpus": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None}
    try:
        cpu = Path("/proc/cpuinfo").read_text(errors="replace")
        info["cpu"] = next((line.split(":", 1)[1].strip() for line in cpu.splitlines() if line.startswith("model name")), "")
        flags = next((line.split(":", 1)[1].split() for line in cpu.splitlines() if line.startswith("flags")), [])
        info["fma"], info["avx2"], info["avx512f"] = "fma" in flags, "avx2" in flags, "avx512f" in flags
        info["kernel"] = Path("/proc/version").read_text(errors="replace").strip()
        info["memory_kb"] = next((int(line.split()[1]) for line in Path("/proc/meminfo").read_text().splitlines()
                                  if line.startswith("MemTotal")), None)
    except (OSError, ValueError, IndexError):
        pass
    return info


def unchanged_by_setting(program: str, settled: dict, plan: dict, first: dict) -> bool:
    """For a case whose plan names its display setting (`unset`: the file, the text to take out of
    it and what to put in its place), whether the program prints the same without it: such a case
    grades nothing of the setting."""
    unset = plan.get("unset")
    if not unset or len(unset) != 3:
        return False
    path, old, new = unset
    text = settled["files"].get(path)
    if text is None or old not in text:
        return False
    plain = dict(settled, files=dict(settled["files"], **{path: text.replace(old, new, 1)}))
    got = run_case([program], plain, keep_stderr=True, env=MAIN_ENV)
    return (got["exit"], got["stdout"]) == (first["exit"], first["stdout"])


def record(program: str, cases: list[dict]) -> tuple[list[dict], dict, dict]:
    """The cases kept (settled, without their "record" entries), what the program printed for them,
    and a report: how long and how much CPU every run took, how each case was settled, and why the
    others were left out."""
    finished, outputs = [], {}
    started = time.monotonic()
    report = {"keep_seconds": KEEP_SEC, "keep_cpu": KEEP_CPU, "main_runs": MAIN_RUNS, "main_env": MAIN_ENV, "seconds": {},
              "cpu": {}, "slow": [], "unsteady": [], "crashed": [], "machine": [], "output_limit": [], "memory_limit": [],
              "disk_limit": [], "perturbed": [], "setting_changes_nothing": [], "settled": {}, "dropped": {}, "host": host()}
    elsewhere = relocated(program)
    for case in cases:
        plan = case.get("record", {})
        case = {key: value for key, value in case.items() if key != "record"}
        settled, how = settle(program, case, plan)
        report["settled"][case["id"]] = how
        runs = [run_case([program], settled, keep_stderr=True, env=MAIN_ENV) for _ in range(MAIN_RUNS)]
        first = runs[0]
        report["seconds"][case["id"]] = [run["seconds"] for run in runs]
        report["cpu"][case["id"]] = [run["cpu"] for run in runs]
        errors = {run.get("error") for run in runs} - {None}
        if errors:
            report["slow" if "timeout" in errors else "output_limit" if "output limit" in errors else
                   "memory_limit" if "memory limit" in errors else
                   "disk_limit" if errors & {"disk limit", "file limit"} else "unsteady"].append(case["id"])
        elif any((run["exit"], run["stdout"]) != (first["exit"], first["stdout"]) for run in runs):
            report["unsteady"].append(case["id"])
        elif any(crashed(run) for run in runs):
            report["crashed"].append(case["id"])
        elif any(marker in first["stdout"] or marker in first.get("stderr", b"") for marker in MACHINE):
            report["machine"].append(case["id"])
        elif max(run["seconds"] for run in runs) > KEEP_SEC or max(run["cpu"] for run in runs) > KEEP_CPU:
            report["slow"].append(case["id"])
        else:
            perturbed = run_case([elsewhere], settled, keep_stderr=True, env=PERTURBED_ENV, preexec=perturbed_limits)
            if (perturbed["exit"], perturbed["stdout"]) != (first["exit"], first["stdout"]):
                report["perturbed"].append(case["id"])
                continue
            if unchanged_by_setting(program, settled, plan, first):
                report["setting_changes_nothing"].append(case["id"])
                continue
            finished.append(settled)
            outputs[case["id"]] = {"exit": first["exit"], "stdout": first["stdout"].decode(*ENCODING)}
    shutil.rmtree(Path(elsewhere).parent.parent, ignore_errors=True)
    kept, dropped = select(finished, outputs)
    for reason, ids in dropped.items():
        report["dropped"].setdefault(reason, []).extend(ids)
    report["wall_seconds"] = round(time.monotonic() - started, 1)
    return kept, {case["id"]: outputs[case["id"]] for case in kept}, report


def main() -> None:
    """Record what a program prints for every case and keep the cases worth grading."""
    if len(sys.argv) < 5 or sys.argv[1] != "record":
        raise SystemExit(__doc__)
    program, cases_path, expected_path = sys.argv[2:5]
    option = lambda name: sys.argv[sys.argv.index(name) + 1] if name in sys.argv else None  # noqa: E731
    cases = json.loads(Path(cases_path).read_text(encoding="utf-8"))["cases"]
    kept, outputs, report = record(program, cases)
    clear_workspace()
    if len(report["unsteady"]) > 0.05 * len(cases) or len(report["crashed"]) > 0.02 * len(cases) \
            or len(report["perturbed"]) > 0.05 * len(cases) or len(kept) < 0.6 * len(cases):
        raise SystemExit(f"kept {len(kept)} of {len(cases)} cases: {len(report['unsteady'])} did not finish the same "
                         f"way twice, {len(report['crashed'])} crashed, {len(report['perturbed'])} changed when "
                         f"perturbed, {len(report['slow'])} were slow")
    free = free_union(free_cases(kept, outputs))
    if len(free) > FLOOR_SHARE * len(kept):  # select() drops them; only the command line's own cases can stay
        raise SystemExit(f"{len(free)} of {len(kept)} kept cases pass with no interpreter, more than {FLOOR_SHARE:.0%}")
    report["kept_ids_sha256"] = hashlib.sha256("\n".join(case["id"] for case in kept).encode()).hexdigest()
    Path(expected_path).write_text(json.dumps(outputs, sort_keys=True))
    if option("--keep"):
        Path(option("--keep")).write_text(json.dumps({"cases": kept}, sort_keys=True, ensure_ascii=False))
    if option("--report"):
        Path(option("--report")).write_text(json.dumps(report, sort_keys=True))
    print(f"recorded {len(kept)} of {len(cases)} cases in {report['wall_seconds']} s ({len(report['slow'])} slow, "
          f"{len(report['unsteady'])} unsteady, {len(report['crashed'])} crashed, {len(report['machine'])} machine, "
          f"{len(report['perturbed'])} perturbed, {len(report['setting_changes_nothing'])} unchanged by their setting, "
          + ", ".join(f"{len(ids)} {why}" for why, ids in report["dropped"].items()) + ")")


if __name__ == "__main__":
    main()
