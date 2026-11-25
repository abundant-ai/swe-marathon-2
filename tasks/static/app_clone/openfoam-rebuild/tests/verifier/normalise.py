"""Removes from printed output what changes between runs (banner, date, time, host, process
id, paths, run times and memory use, stray NUL bytes from parallel runs) and the C++ function names,
source lines and stack traces in errors."""

from __future__ import annotations

import os
import re

_BANNER_TOP = re.compile(r"^/\*-{20,}")
_BANNER_END = re.compile(r"^\\\*-{20,}\*/\s*$")
_DROP = re.compile(r"^(Date|Time|PID)\s*:")
_CLOCK = re.compile(r"^\s*ExecutionTime\s*=.*ClockTime\s*=.*$")
_FROM = re.compile(r"^\s+From (?:.*\(.*\)|\S+)\s*(?:const)?\s*$")
_IN_FILE = re.compile(r"^\s+in file \S+ at line \d+\.\s*$")
_FRAME = re.compile(r"^\s*\[\d+\]\s+#\d+\s|^#\d+\s+")
_ELAPSED = re.compile(
    r"\bin (=\s*)?[-+.\deE]+ s(?:econds)?\b"
)  # "Mesh refined in = 0.14 s.", "Mapping completed in 0.01 seconds"
_TIME_MEM = re.compile(
    r"\b[\d.]+ s, \d+ kB\b"
)  # "VTK mesh topology: 0.01 s, 313228 kB"
_MEMORY = re.compile(r"\b\d+ kB\b")  # "Initial memory 319096 kB"
_STACK = "[stack trace]"  # OpenFOAM's crash trace: frames of the C++ build, to the second "====" line
# Where the program is installed: OpenFOAM prints its own location, e.g. 'Reading
# "/opt/openfoam/etc/thermoData/thermoData"'. A submission lives in /app/rebuild, so the location
# is replaced, up to the top-level folder of the installation (etc, doc, bin, ...), by <install>.
RECORDED_INSTALL = "/opt/openfoam"
SUBMISSION_INSTALL = (
    "/app/rebuild",
    RECORDED_INSTALL,
)  # either is fine in a submission's output
_TOP = r"(?=/(?:etc|doc|bin|platforms|src|applications|tutorials|wmake|META-INFO)\b)"


def _install(roots: tuple[str, ...]):
    alt = "|".join(re.escape(r) for r in roots)
    return re.compile(rf"(?:{alt})(?:/[^/\s\"']+)*?" + _TOP + rf"|(?:{alt})\b")


def normalise(
    text: str,
    *,
    case_dir: str | None = None,
    home: str | None = None,
    host: str | None = None,
    install: tuple[str, ...] = (),
) -> list[str]:
    """Output lines with run-specific content removed or replaced by <case>, <root> (the folder
    holding the case), <home>, <host>, <install>."""
    install_re = _install(install) if install else None
    lines = text.replace("\r\n", "\n").replace("\x00", "").split("\n")
    out = []
    in_banner = False
    in_stack = 0  # "=====" lines of the stack trace seen so far
    for line in lines:
        if line.strip() == _STACK:
            in_stack = 1
            out.append(_STACK)
            continue
        if in_stack:
            if line.startswith("====="):
                in_stack += 1
                if in_stack > 2:
                    in_stack = 0
            continue
        if _BANNER_TOP.match(line):
            in_banner = True
            continue
        if in_banner:
            if _BANNER_END.match(line):
                in_banner = False
            continue
        if (
            _DROP.match(line)
            or _CLOCK.match(line)
            or _IN_FILE.match(line)
            or _FRAME.match(line)
        ):
            continue
        if _FROM.match(line):
            continue
        line = _ELAPSED.sub("in <time> s", line)
        line = _TIME_MEM.sub("<time> s, <memory> kB", line)
        line = _MEMORY.sub("<memory> kB", line)
        if home:  # first: the home folder may lie inside the folder holding the case
            line = line.replace(home.rstrip("/"), "<home>")
        if case_dir:
            line = line.replace(case_dir.rstrip("/"), "<case>")
            # some programs print the folder holding the case and the case name separately
            line = line.replace(os.path.dirname(case_dir.rstrip("/")), "<root>")
        if host:
            line = re.sub(rf"\b{re.escape(host)}\b", "<host>", line)
        if install_re:
            line = install_re.sub("<install>", line)
        out.append(line.rstrip())
    while out and out[-1] == "":
        out.pop()
    return out


_DATES = [
    re.compile(
        r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b"
    ),  # 2026-11-19T18:22:33
    re.compile(
        r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w* +\w{3} +\d{1,2} +\d{2}:\d{2}:\d{2} +\d{4}\b"
    ),  # Wed Nov 19 22:53:01 2026
    re.compile(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w* +\d{1,2},? +\d{4}\b"
    ),  # Nov 19 2026
    re.compile(r"\b\d{2}:\d{2}:\d{2}\b"),  # 22:53:01
]


def strip_dates(line: str) -> str:
    """Replaces dates and clock times (written into some output files' headers) by <date>."""
    for d in _DATES:
        line = d.sub("<date>", line)
    return line
