#!/bin/sh
# make_longline BASE_TREE OUT_TREE
#
# A delivered tree whose library prints one huge line in every case program (R2-M5). On its first font load
# (hb_blob_create_from_file_or_fail(), which every case program calls), the library reads its batch's first case id
# from standard input (pread at offset 0, the input file root opened), writes that id, a tab and a result that fills
# the line to exactly 16 MiB (the verifier's per-batch read cap) with one character outside the BMP at its end, and
# exits. BASE_TREE is the reference tree. Round 1's verifier kept each such line as a Python string of 4 bytes a
# character, 64 MiB a batch, and ran out of memory after about 128 of 261 batches.
# Expected: every batch fails. 260 are read and fail on their first case, whose result is over 4,096 characters
# ("1 result over 4096 characters; its case fails"), and on the others, which were never printed; batch 30 (hbapi51,
# which prints its font-free cases before its first font load) goes over the 16 MiB cap and fails whole. metrics.json
# results_too_long 260 and a peak_rss_mib of about 200 (one batch's text while it is read, never more); reward.txt
# 0.0, written about as soon as for the reference (102 s on Docker Desktop's emulated amd64).
# Copied without test/ (the product build never reads it). Runs inside the pipeline image only.
set -eu
BASE=$1
OUT=$2
test ! -e "$OUT"
mkdir -p "$OUT"
(cd "$BASE" && tar -cf - --exclude=./test .) | (cd "$OUT" && tar -xf -)
python3 - "$OUT/src/hb-blob.cc" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
s = path.read_text()
anchor = '#include "hb-blob.hh"\n'
if s.count(anchor) != 1:
    raise SystemExit(f"{path}: no single {anchor.strip()}")
s = s.replace(anchor, anchor + "\n#include <stdlib.h>\n#include <string.h>\n#include <unistd.h>\n", 1)
m = re.search(r"\nhb_blob_create_from_file_or_fail \(const char \*file_name\)\n\{\n", s)
if not m:
    raise SystemExit(f"hb_blob_create_from_file_or_fail not found in {path}")
probe = r"""  {
    /* Long-line probe (scripts/pipeline/make_longline.sh): one line of exactly 16 MiB for the batch's first case,
       ending in a character outside the BMP, then the process ends before the program prints any more. */
    char _hb_probe_id[64];
    ssize_t _hb_probe_n = pread (0, _hb_probe_id, sizeof (_hb_probe_id), 0);
    if (_hb_probe_n > 0)
    {
      size_t _hb_probe_len = 0;
      while (_hb_probe_len < (size_t) _hb_probe_n && _hb_probe_id[_hb_probe_len] != '\t')
        _hb_probe_len++;
      const size_t _hb_probe_total = 16u << 20;
      char *_hb_probe_line = (char *) malloc (_hb_probe_total);
      if (_hb_probe_line)
      {
        memcpy (_hb_probe_line, _hb_probe_id, _hb_probe_len);
        _hb_probe_line[_hb_probe_len] = '\t';
        memset (_hb_probe_line + _hb_probe_len + 1, 'x', _hb_probe_total - _hb_probe_len - 1 - 4 - 1);
        memcpy (_hb_probe_line + _hb_probe_total - 5, "\xF0\x9F\x98\x80", 4);
        _hb_probe_line[_hb_probe_total - 1] = '\n';
        size_t _hb_probe_off = 0;
        while (_hb_probe_off < _hb_probe_total)
        {
          ssize_t _hb_probe_w = write (1, _hb_probe_line + _hb_probe_off, _hb_probe_total - _hb_probe_off);
          if (_hb_probe_w <= 0)
            break;
          _hb_probe_off += (size_t) _hb_probe_w;
        }
      }
    }
    _exit (0);
  }
"""
s = s[: m.end()] + probe + s[m.end() :]
path.write_text(s)
PY
echo "long-line tree: $(grep -c _hb_probe_line "$OUT/src/hb-blob.cc") probe lines"
