#!/bin/sh
# regen_unicode OUT_TREE
# S7: a 14.3.0 tree whose Unicode tables a maintainer regenerated from the shipped Unicode 18 files with 14.3.0's own
# generators, after adding the three new script values the notes name (taken from 15.2.0's script list, the one
# piece not derivable from the data). Runs inside the pipeline image only; the result is built with hb_build.
set -eu
OUT=$1
mkdir -p "$OUT"
tar -xJf /dl/harfbuzz/harfbuzz-14.3.0.tar.xz -C "$OUT" --strip-components=1
mkdir -p /tmp/ucd /tmp/t152
cd /tmp/ucd
python3 -c "import zipfile; zipfile.ZipFile('/dl/unicode/UCD-18.0.0.zip').extractall('/tmp/ucd')"
S="$OUT/src"
for f in UnicodeData.txt Scripts.txt Blocks.txt ArabicShaping.txt IndicSyllabicCategory.txt IndicPositionalCategory.txt; do
  cp "/tmp/ucd/$f" "$S/$f"
done
cp /dl/unicode/DerivedCoreProperties-17.0.0.txt "$S/DerivedCoreProperties.txt"
cp /dl/unicode/emoji-data-18.0.txt "$S/emoji-data.txt"
cp /dl/unicode/emoji-test-18.0.txt "$S/emoji-test.txt"
cp /dl/unicode/ucd.nounihan.grouped-18.0.0.zip "$S/ucd.nounihan.grouped.zip"
cp /dl/unicode/language-subtag-registry "$S/language-subtag-registry"
cp /dl/unicode/languagetags.html "$S/languagetags"
cp /dl/unicode/ms-use-cdbe72ca-IndicSyllabicCategory-Additional.txt "$S/ms-use/IndicSyllabicCategory-Additional.txt"
cp /dl/unicode/ms-use-cdbe72ca-IndicPositionalCategory-Additional.txt "$S/ms-use/IndicPositionalCategory-Additional.txt"
tar -xJf /dl/harfbuzz/harfbuzz-15.2.0.tar.xz -C /tmp/t152 --strip-components=1 harfbuzz-15.2.0/src/hb-script-list.h
cp /tmp/t152/src/hb-script-list.h "$S/hb-script-list.h"
cd "$S"
P=/opt/py/bin/python
$P ./gen-arabic-joining-list.py ArabicShaping.txt Scripts.txt > hb-ot-shaper-arabic-joining-list.hh
$P ./gen-arabic-table.py ArabicShaping.txt UnicodeData.txt Blocks.txt > hb-ot-shaper-arabic-table.hh
$P ./gen-emoji-table.py emoji-data.txt emoji-test.txt > hb-unicode-emoji-table.hh
$P ./gen-indic-table.py IndicSyllabicCategory.txt IndicPositionalCategory.txt Blocks.txt > hb-ot-shaper-indic-table.cc
$P ./gen-tag-table.py languagetags language-subtag-registry > hb-ot-tag-table.hh
$P ./gen-ucd-table.py ucd.nounihan.grouped.zip hb-script-list.h > hb-ucd-table.hh
$P ./gen-use-table.py IndicSyllabicCategory.txt IndicPositionalCategory.txt ArabicShaping.txt DerivedCoreProperties.txt \
  UnicodeData.txt Blocks.txt Scripts.txt ms-use/IndicSyllabicCategory-Additional.txt \
  ms-use/IndicPositionalCategory-Additional.txt > hb-ot-shaper-use-table.hh
$P ./gen-vowel-constraints.py ms-use/IndicShapingInvalidCluster.txt Scripts.txt > hb-ot-shaper-vowel-constraints.cc
echo "regenerated: $(ls -1 hb-ot-shaper-*table* hb-ucd-table.hh hb-unicode-emoji-table.hh hb-ot-tag-table.hh | wc -l) tables"
