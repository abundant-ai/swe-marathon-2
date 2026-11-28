#!/bin/sh
# make_hang BASE_TREE OUT_TREE
#
# A delivered tree whose library never returns from shaping: hb_shape_full() ignores SIGTERM and spins forever on
# its first call. BASE_TREE is the reference tree. Expected (fix round 2): the build and every case program build as
# for the reference; each batch whose program shapes is stopped at its limit (at most 15 s, keeping 2 s for every
# batch still to run; TERM ignored, so `timeout` kills it shortly after) and keeps the lines it printed before its
# first shaping call; every batch runs within the 1,800 s deadline, so the batches that never shape score as for the
# reference and the reward is their credit (QA R2-11 N3 predicts about 0.074), written well before the deadline.
# (Round 1, with 120 s batches, dropped every batch after the 14th: 0.018.)
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
