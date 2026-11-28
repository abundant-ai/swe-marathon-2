#!/bin/sh
# make_stubs BASE_TREE OUT_DIR [NOTES]
#
# The stub zoo: trees that must all score exactly 0. Each is a copy of our shipped 14.3.0 tree with one edit:
#   comments   comment and whitespace edits only
#   refactor   a behaviour-neutral refactor (a helper that nothing calls)
#   nobuild    a tree that does not compile
#   empty      hb_shape_full() returns an empty buffer
#   abort      the library aborts on its first shaping call
#   noop-api   the four functions the 15.1.0 and 15.2.0 notes add, declared exactly as the notes give them (NOTES,
#              default /env/docs/notes.md, the instruction's notes as a file) in the headers they name, with
#              bodies that return NULL, 0 or false and write nothing; the API probes compile and run against it
#   noop-api-zero  the same declarations, with bodies that also write 0 through a non-NULL glyphs_count and
#              buf_consumed (what the notes' negative clauses describe: "possibly zero", "0 when nothing is
#              consumed"); both no-op stubs must score 0.000 (QA R2-09 N1)
# Runs inside the pipeline image only.
set -eu
BASE=$1
OUT=$2
NOTES=${3:-/env/docs/notes.md}
mkdir -p "$OUT"
# Each stub is a copy of the base without test/, which the product build never reads (tests are disabled); the
# shared machine's disk is tight. (Hard links do not survive Docker Desktop's file sharing.)
for s in comments refactor nobuild empty abort noop-api noop-api-zero; do
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
# noop-api and noop-api-zero: the declarations, copied from the notes' C blocks into the named headers (inside
# HB_BEGIN_DECLS, so they keep C linkage), and bodies that do nothing (noop-api) or only write 0 through the
# out-parameters (noop-api-zero), at the end of the sources that hold their neighbours
for s in noop-api noop-api-zero; do
python3 - "$OUT/$s" "$NOTES" "$s" <<'PY'
import re, sys, textwrap
from pathlib import Path
tree, notes, stub = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
blocks = [textwrap.dedent(b) for b in re.findall(r"^ *```c\n(.*?)^ *```$", notes.read_text(), re.M | re.S)]
HEADERS = {
    "hb_buffer_deserialize_glyphs2": "hb-buffer.h",
    "hb_buffer_deserialize_unicode2": "hb-buffer.h",
    "hb_font_create_without_funcs_or_fail": "hb-font.h",
    "hb_ot_layout_get_extender_glyphs": "hb-ot-layout.h",
}
ZERO = stub == "noop-api-zero"
CONSUMED = "  if (buf_consumed)\n    *buf_consumed = 0;\n" if ZERO else ""
COUNT = "  if (glyphs_count)\n    *glyphs_count = 0;\n" if ZERO else ""
BODIES = {
    "hb-buffer-serialize.cc": f"""
hb_bool_t
hb_buffer_deserialize_glyphs2 (hb_buffer_t *, const char *, int, unsigned int *buf_consumed, hb_font_t *,
			       hb_buffer_serialize_format_t)
{{
{CONSUMED}  (void) buf_consumed;
  return false;
}}

hb_bool_t
hb_buffer_deserialize_unicode2 (hb_buffer_t *, const char *, int, unsigned int *buf_consumed,
				hb_buffer_serialize_format_t)
{{
{CONSUMED}  (void) buf_consumed;
  return false;
}}
""",
    "hb-font.cc": """
hb_font_t *
hb_font_create_without_funcs_or_fail (hb_face_t *)
{
  return nullptr;
}
""",
    "hb-ot-layout.cc": f"""
unsigned
hb_ot_layout_get_extender_glyphs (hb_face_t *, hb_script_t, hb_language_t, unsigned, unsigned *glyphs_count,
				  hb_codepoint_t *)
{{
{COUNT}  (void) glyphs_count;
  return 0;
}}
""",
}
found = set()
for block in blocks:
    names = sorted(set(re.findall(r"^(hb_\w+) \(", block, re.M)) & set(HEADERS))
    if not names or len({HEADERS[n] for n in names}) != 1:
        raise SystemExit(f"noop-api: a C block of {notes} names no single header's functions: {names}")
    found |= set(names)
    h = tree / "src" / HEADERS[names[0]]
    s = h.read_text()
    at = s.rindex("\nHB_END_DECLS\n")
    h.write_text(s[:at] + "\n" + block.rstrip("\n") + "\n" + s[at:])
if found != set(HEADERS):
    raise SystemExit(f"{stub}: {notes} does not declare {sorted(set(HEADERS) - found)}")
for name, body in BODIES.items():
    p = tree / "src" / name
    p.write_text(p.read_text() + body)
PY
done
grep -c "unused_helper" "$OUT/refactor/src/hb-shape.cc"
grep -c "glyphs_count = 0" "$OUT/noop-api-zero/src/hb-ot-layout.cc"
echo "stubs: $(ls "$OUT" | tr '\n' ' ')"
