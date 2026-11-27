#!/bin/sh
# make_stubs BASE_TREE OUT_DIR
#
# The stub zoo: trees that must all score exactly 0. Each is a copy of our shipped 14.3.0 tree with one edit:
#   comments   comment and whitespace edits only
#   refactor   a behaviour-neutral refactor (a helper that nothing calls)
#   nobuild    a tree that does not compile
#   empty      hb_shape_full() returns an empty buffer
#   abort      the library aborts on its first shaping call
# Runs inside the pipeline image only.
set -eu
BASE=$1
OUT=$2
mkdir -p "$OUT"
# Each stub is a copy of the base without test/, which the product build never reads (tests are disabled); the
# shared machine's disk is tight. (Hard links do not survive Docker Desktop's file sharing.)
for s in comments refactor nobuild empty abort; do
  test ! -e "$OUT/$s"
  mkdir -p "$OUT/$s"
  (cd "$BASE" && tar -cf - --exclude=./test .) | (cd "$OUT/$s" && tar -xf -)
done
# comments: a comment line after every #include in src/hb-buffer.cc and trailing blanks in hb-shape.cc
sed -i 's|^\(#include .*\)$|\1\n/* product build */|' "$OUT/comments/src/hb-buffer.cc"
printf '\n\n' >> "$OUT/comments/src/hb-shape.cc"
# refactor: a static inline helper that nothing calls, in hb-shape.cc
cat >> "$OUT/refactor/src/hb-shape.cc" <<'C'

static inline unsigned int
_hb_product_unused_helper (unsigned int x)
{
  unsigned int doubled = x + x;
  return doubled;
}
C
# nobuild
printf '\n#error "product build: incomplete change"\n' >> "$OUT/nobuild/src/hb-common.cc"
# empty: clear the buffer and report success before shaping
python3 - "$OUT" <<'PY'
import re, sys
from pathlib import Path
out = Path(sys.argv[1])
for name, body in (("empty", "  hb_buffer_clear_contents (buffer);\n  return true;\n"), ("abort", "  abort ();\n")):
    p = out / name / "src" / "hb-shape.cc"
    s = p.read_text()
    m = re.search(r"\nhb_shape_full \([^)]*\)\n\{\n", s)
    if not m:
        raise SystemExit(f"hb_shape_full not found in {p}")
    s = s[: m.end()] + body + s[m.end() :]
    if name == "abort" and "#include <stdlib.h>" not in s:
        s = "#include <stdlib.h>\n" + s
    p.write_text(s)
PY
grep -c "unused_helper" "$OUT/refactor/src/hb-shape.cc"
echo "stubs: $(ls "$OUT" | tr '\n' ' ')"
