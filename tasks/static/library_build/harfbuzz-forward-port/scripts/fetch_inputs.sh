#!/usr/bin/env bash
# Fetch every pinned input named in notes/SPIKE.md into the durable cache and record name, URL, size and
# SHA-256 in MANIFEST.tsv. Development tooling: never shipped, never copied into an image.
#
# Usage: scripts/fetch_inputs.sh [CACHE_DIR]
set -euo pipefail

CACHE=${1:-$HOME/Documents/github/Abundant/lib-tasks-cache/harfbuzz-forward-port}
DL="$CACHE/dl"
MANIFEST="$CACHE/MANIFEST.tsv"
mkdir -p "$DL/harfbuzz" "$DL/fonts" "$DL/python" "$DL/unicode" "$DL/docs/opentype" "$DL/docs/script-development" \
  "$DL/docs/apple" "$DL/docs/unicode" "$DL/git"
[ -f "$MANIFEST" ] || printf 'group\tpath\turl\tbytes\tsha256\tfetched_utc\n' > "$MANIFEST"

NOTO_SHA=d14cc173a70dc57962ed2d4ad278fc9df83bf9f3   # notofonts/notofonts.github.io main, 2026-11-27
CJK_SHA=f8d157532fbfaeda587e826d4cd5b21a49186f7c    # notofonts/noto-cjk main, 2026-11-27

record() { # group relpath url
  local f="$DL/$2"
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$(stat -f %z "$f")" "$(shasum -a 256 "$f" | cut -d' ' -f1)" \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$MANIFEST"
}

fetch() { # group relpath url...  (tries each URL in turn; keeps the first that answers 200)
  local group=$1 rel=$2; shift 2
  local out="$DL/$rel"
  if grep -qF "$(printf '\t%s\t' "$rel")" "$MANIFEST" 2>/dev/null && [ -s "$out" ]; then echo "have $rel"; return 0; fi
  mkdir -p "$(dirname "$out")"
  local url
  for url in "$@"; do
    if curl -fsSL --retry 3 --retry-delay 5 --connect-timeout 30 --max-time 900 -o "$out.part" "$url"; then
      mv "$out.part" "$out"; record "$group" "$rel" "$url"; echo "got $rel"; return 0
    fi
  done
  rm -f "$out.part"; echo "MISSING $rel" >&2; return 1
}

# A1-A2. HarfBuzz release tarballs.
for v in 14.3.0 15.0.0 15.1.0 15.2.0; do
  fetch harfbuzz "harfbuzz/harfbuzz-$v.tar.xz" "https://github.com/harfbuzz/harfbuzz/releases/download/$v/harfbuzz-$v.tar.xz"
done

# B. Fonts (OFL), pinned commits.
NOTO="https://raw.githubusercontent.com/notofonts/notofonts.github.io/$NOTO_SHA/fonts"
for fam in NotoSansKhmer NotoSerifKhmer NotoSansMyanmar NotoSansDevanagari NotoSansBengali NotoSansBalinese \
           NotoSansJavanese NotoSansTaiTham NotoSansHebrew NotoSansSyriac NotoNaskhArabic NotoSansArabic; do
  fetch fonts "fonts/$fam-Regular.ttf" "$NOTO/$fam/hinted/ttf/$fam-Regular.ttf" \
    "$NOTO/$fam/full/ttf/$fam-Regular.ttf" "$NOTO/$fam/unhinted/ttf/$fam-Regular.ttf" || true
done
for fam in NotoSans NotoSerif; do
  fetch fonts "fonts/$fam-VF.ttf" "$NOTO/$fam/unhinted/variable-ttf/$fam%5Bwdth%2Cwght%5D.ttf" \
    "$NOTO/$fam/googlefonts/variable-ttf/$fam%5Bwdth%2Cwght%5D.ttf" "$NOTO/$fam/full/variable-ttf/$fam%5Bwdth%2Cwght%5D.ttf" || true
done
fetch fonts "fonts/NotoSansKR-Regular.otf" \
  "https://raw.githubusercontent.com/notofonts/noto-cjk/$CJK_SHA/Sans/SubsetOTF/KR/NotoSansKR-Regular.otf" \
  "https://raw.githubusercontent.com/notofonts/noto-cjk/$CJK_SHA/Sans/OTF/Korean/NotoSansKR-Regular.otf" || true
fetch fonts "fonts/LICENSE-notofonts" "https://raw.githubusercontent.com/notofonts/notofonts.github.io/$NOTO_SHA/LICENSE" || true
fetch fonts "fonts/LICENSE-noto-cjk-Sans" "https://raw.githubusercontent.com/notofonts/noto-cjk/$CJK_SHA/Sans/LICENSE" || true

# C. Python wheels (pure Python; installed inside containers only).
fetch python "python/fonttools-4.69.1-py3-none-any.whl" \
  "https://files.pythonhosted.org/packages/py3/f/fonttools/fonttools-4.69.1-py3-none-any.whl"
fetch python "python/packtab-1.9.0-py3-none-any.whl" \
  "https://files.pythonhosted.org/packages/py3/p/packtab/packtab-1.9.0-py3-none-any.whl"
fetch python "python/meson-1.12.1-py3-none-any.whl" \
  "https://files.pythonhosted.org/packages/py3/m/meson/meson-1.12.1-py3-none-any.whl"

# E1-E5. Unicode data and language-tag sources.
fetch unicode "unicode/UCD-18.0.0.zip" "https://www.unicode.org/Public/18.0.0/ucd/UCD.zip"
fetch unicode "unicode/DerivedCoreProperties-17.0.0.txt" "https://www.unicode.org/Public/17.0.0/ucd/DerivedCoreProperties.txt"
fetch unicode "unicode/ucd.nounihan.grouped-18.0.0.zip" "https://www.unicode.org/Public/18.0.0/ucdxml/ucd.nounihan.grouped.zip"
fetch unicode "unicode/emoji-data-18.0.txt" "https://www.unicode.org/Public/18.0.0/ucd/emoji/emoji-data.txt"
fetch unicode "unicode/emoji-test-18.0.txt" "https://www.unicode.org/Public/18.0.0/emoji/emoji-test.txt" \
  "https://www.unicode.org/Public/emoji/18.0/emoji-test.txt"
fetch unicode "unicode/language-subtag-registry" "https://www.iana.org/assignments/language-subtag-registry/language-subtag-registry"
fetch unicode "unicode/languagetags.html" "https://learn.microsoft.com/en-us/typography/opentype/spec/languagetags"
fetch unicode "unicode/unicode-license.txt" "https://www.unicode.org/license.txt"

# E7-E10. Specification pages.
OT=https://learn.microsoft.com/en-us/typography/opentype/spec
for p in otff chapter2 gsub gpos gdef base jstf cmap glyf head hhea vhea hmtx vmtx os2 stat fvar avar gvar hvar \
         mvar otvarcommonformats colr cpal cbdt cblc kern featuretags scripttags features_ae features_fj features_ko \
         features_pt features_uz; do
  fetch docs "docs/opentype/$p.html" "$OT/$p" || true
done
for p in khmer myanmar devanagari bengali use hangul hebrew arabic; do
  fetch docs "docs/script-development/$p.html" "https://learn.microsoft.com/en-us/typography/script-development/$p" || true
done
AP=https://developer.apple.com/fonts/TrueType-Reference-Manual
for t in morx mort kerx kern trak ankr feat; do
  fetch docs "docs/apple/Chap6$t.html" "$AP/RM06/Chap6$t.html" || true
done
fetch docs "docs/apple/AppendixF.html" "$AP/RM09/AppendixF.html" || true
fetch docs "docs/unicode/tr29.html" "https://www.unicode.org/reports/tr29/" || true

# A3, E11. Upstream history (blobless; blobs arrive on demand) and the USE override files at cdbe72ca.
if [ ! -d "$DL/git/harfbuzz/.git" ]; then
  git clone -q --filter=blob:none --no-checkout https://github.com/harfbuzz/harfbuzz.git "$DL/git/harfbuzz"
fi
git -C "$DL/git/harfbuzz" fetch -q --tags origin
for f in IndicSyllabicCategory-Additional.txt IndicPositionalCategory-Additional.txt; do
  if [ ! -s "$DL/unicode/ms-use-cdbe72ca-$f" ]; then
    git -C "$DL/git/harfbuzz" show "cdbe72ca8:src/ms-use/$f" > "$DL/unicode/ms-use-cdbe72ca-$f"
    record unicode "unicode/ms-use-cdbe72ca-$f" "git:harfbuzz@cdbe72ca8:src/ms-use/$f"
  fi
done
echo "done: $(du -sh "$CACHE" | cut -f1) in $CACHE"
