#!/bin/sh
# make_hang BASE_TREE OUT_TREE
#
# A delivered tree whose library never returns from shaping: hb_shape_full() ignores SIGTERM and spins forever on
# its first call. BASE_TREE is the reference tree. Expected: the build and every case program build as for the
# reference; each batch whose program shapes is stopped at its 120 s limit (TERM ignored, so `timeout` kills it 5 s
# later), and keeps the lines it printed before its first shaping call; once the deadline (1,800 s) has passed, the
# remaining batches are not run ("... batches (... cases) not run: the time was up"); their cases fail; reward.txt
# is written at about 1,800-1,850 s. Batches that never shape score as for the reference.
# Copied without test/ (the product build never reads it). Runs inside the pipeline image only.
set -eu
BASE=$1
OUT=$2
test ! -e "$OUT"
mkdir -p "$OUT"
(cd "$BASE" && tar -cf - --exclude=./test .) | (cd "$OUT" && tar -xf -)
python3 - "$OUT/src/hb-shape.cc" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
s = path.read_text()
anchor = '#include "hb-machinery.hh"\n'
if s.count(anchor) != 1:
    raise SystemExit(f"{path}: no single {anchor.strip()}")
s = s.replace(anchor, anchor + "\n#include <signal.h>\n", 1)
m = re.search(r"\nhb_shape_full \([^)]*\)\n\{\n", s)
if not m:
    raise SystemExit(f"hb_shape_full not found in {path}")
hang = """  {
    /* Hanging-library probe (scripts/pipeline/make_hang.sh): never return, and ignore the polite stop. */
    signal (SIGTERM, SIG_IGN);
    volatile unsigned long _hb_probe_spin = 0;
    for (;;)
      _hb_probe_spin = _hb_probe_spin + 1;
  }
"""
s = s[: m.end()] + hang + s[m.end() :]
path.write_text(s)
PY
echo "hang tree: $(grep -c _hb_probe_spin "$OUT/src/hb-shape.cc") probe lines"
