#!/bin/sh
# make_flood BASE_TREE OUT_TREE
#
# A delivered tree whose library floods its standard output: every hb_shape_full() call first writes 4 GiB of
# lines. BASE_TREE is the reference tree. Expected: each batch whose program shapes is cut off at the case
# programs' 64 MiB file-size limit; root reads no more than 16 MiB + 1 byte of it and fails that whole batch
# ("output over 16 MiB or unreadable; its cases fail"); every batch that never shapes scores as for the reference;
# the verifier's memory and disk stay small (each batch's files are removed once read), and reward.txt is written
# about as soon as for the reference.
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
s = s.replace(anchor, anchor + "\n#include <string.h>\n#include <unistd.h>\n", 1)
m = re.search(r"\nhb_shape_full \([^)]*\)\n\{\n", s)
if not m:
    raise SystemExit(f"hb_shape_full not found in {path}")
flood = """  {
    /* Flooding-library probe (scripts/pipeline/make_flood.sh): 4 GiB of lines on standard output first. */
    static char _hb_probe_chunk[1 << 20];
    memset (_hb_probe_chunk, 'x', sizeof (_hb_probe_chunk));
    _hb_probe_chunk[sizeof (_hb_probe_chunk) - 1] = '\\n';
    for (unsigned int _hb_probe_i = 0; _hb_probe_i < 4096; _hb_probe_i++)
      if (write (1, _hb_probe_chunk, sizeof (_hb_probe_chunk)) < 0)
        break;
  }
"""
s = s[: m.end()] + flood + s[m.end() :]
path.write_text(s)
PY
echo "flood tree: $(grep -c _hb_probe_chunk "$OUT/src/hb-shape.cc") probe lines"
