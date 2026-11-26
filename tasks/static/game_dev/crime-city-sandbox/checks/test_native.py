"""The telemetry library's engine-free C parts, and the strings of the built library.

The SHA-256/HMAC and JSON-number code is compiled into a small driver with the host C
compiler and compared with Python's hashlib, hmac and float parsing. The built library's
printable strings must have no evaluation wording and only one exported symbol.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import random
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import pytest

TASK = Path(__file__).resolve().parent.parent
NATIVE = TASK / "common/probe/native"
BUILT = (
    TASK
    / "common/probe/build"
    / ("darwin-arm64" if sys.platform == "darwin" else "linux-x86_64")
)
LIBRARY = BUILT / (
    "libtelemetry.dylib" if sys.platform == "darwin" else "libtelemetry.so"
)

DRIVER = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "sha256.h"
#include "jw.h"
/* stdin: lines "h <keyhex> <msghex>" -> HMAC hex; "s <msghex>" -> SHA-256 hex;
   "f <double>" -> the JSON number written for it. */
static int unhex(const char *s, unsigned char *out) {
	int n = 0;
	while (s[0] && s[1] && s[0] != '\n') { unsigned v; sscanf(s, "%2x", &v); out[n++] = (unsigned char)v; s += 2; }
	return n;
}
int main(void) {
	static char line[1 << 20];
	static unsigned char a[1 << 19], b[1 << 19];
	while (fgets(line, sizeof line, stdin)) {
		unsigned char out[32];
		if (line[0] == 'h') {
			char *sp = strchr(line + 2, ' '); *sp = 0;
			int kn = unhex(line + 2, a), mn = unhex(sp + 1, b);
			hmac_sha256(a, (size_t)kn, b, (size_t)mn, out);
		} else if (line[0] == 's') {
			int mn = unhex(line + 2, b);
			sha256_ctx c; sha256_init(&c); sha256_update(&c, b, (size_t)mn); sha256_final(&c, out);
		} else if (line[0] == 'f') {
			jbuf j; jb_init(&j, 1 << 10); jb_f64(&j, strtod(line + 2, NULL));
			printf("%.*s\n", (int)j.n, j.p); jb_free(&j); continue;
		} else continue;
		for (int i = 0; i < 32; i++) printf("%02x", out[i]);
		printf("\n");
	}
	return 0;
}
"""


@pytest.fixture(scope="module")
def driver(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the C driver once for the module."""
    cc = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
    if cc is None:
        pytest.skip("no C compiler")
    d = tmp_path_factory.mktemp("native")
    (d / "driver.c").write_text(DRIVER)
    exe = d / "driver"
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-O2",
            "-I",
            str(NATIVE),
            "-o",
            str(exe),
            str(d / "driver.c"),
            str(NATIVE / "sha256.c"),
            str(NATIVE / "jw.c"),
            "-lm",
        ],
        check=True,
    )
    return exe


def run_driver(exe: Path, lines: list[str]) -> list[str]:
    """Feed lines to the driver; return its output lines."""
    out = subprocess.run(
        [str(exe)],
        input="\n".join(lines) + "\n",
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.splitlines()


def test_sha256_and_hmac_match_python(driver: Path) -> None:
    """The C digests equal hashlib's and hmac's for many lengths, including block edges."""
    rng = random.Random(5)
    msgs = [os.urandom(n) for n in (0, 1, 55, 56, 63, 64, 65, 119, 120, 1000, 70000)]
    msgs += [rng.randbytes(rng.randint(0, 5000)) for _ in range(20)]
    keys = [os.urandom(32) for _ in msgs]
    lines = [f"s {m.hex()}" for m in msgs] + [
        f"h {k.hex()} {m.hex()}" for k, m in zip(keys, msgs)
    ]
    got = run_driver(driver, lines)
    want = [hashlib.sha256(m).hexdigest() for m in msgs]
    want += [hmac.new(k, m, hashlib.sha256).hexdigest() for k, m in zip(keys, msgs)]
    assert got == want


def test_json_numbers_round_trip_exactly(driver: Path) -> None:
    """Every double comes back exactly from the JSON text, always as a float."""
    rng = random.Random(9)
    values = [0.0, -0.0, 1.0, 3.0, 0.1, 1e-7, 2.068e-07, 123456789.0, 1e300, -2.5e-300]
    values += [rng.uniform(-1e4, 1e4) for _ in range(200)]
    values += [
        struct.unpack("f", struct.pack("f", rng.uniform(-100, 100)))[0]
        for _ in range(200)
    ]
    got = run_driver(driver, [f"f {v!r}" for v in values])
    for v, text in zip(values, got):
        assert float(text) == v, (v, text)
        assert any(c in text for c in ".eE"), text
    assert run_driver(driver, ["f nan", "f inf"]) == ["null", "null"]


@pytest.mark.skipif(
    not LIBRARY.is_file(), reason="library not built (common/probe/native/build.sh)"
)
def test_built_library_strings_are_neutral() -> None:
    """No evaluation wording among the library's printable strings."""
    sys.path.insert(0, str(TASK / "scripts"))
    from check_agent_text import PATTERN

    data = LIBRARY.read_bytes()
    strings = []
    run = bytearray()
    for byte in data:
        if 32 <= byte < 127:
            run.append(byte)
            continue
        if len(run) >= 4:
            strings.append(run.decode())
        run = bytearray()
    hits = [s for s in strings if PATTERN.search(s)]
    assert strings and hits == []


@pytest.mark.skipif(
    not LIBRARY.is_file() or not shutil.which("nm"), reason="library not built or no nm"
)
def test_built_library_exports_only_its_entry_symbol() -> None:
    """The entry symbol is the only defined global symbol."""
    out = subprocess.run(
        ["nm", "-g", "--defined-only", str(LIBRARY)],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    names = sorted(
        {
            ln.split()[-1].lstrip("_")
            for ln in out.splitlines()
            if ln.strip() and not ln.endswith(":")
        }
    )
    assert names == ["qa_telemetry_init"]
