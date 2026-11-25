#!/bin/bash
# Assembles /app/docs: the published OpenFOAM v2606 documentation (see index.md).
# usage: build_docs.sh <out dir>    (needs curl, pdftotext, and python with beautifulsoup4 and
#        markdownify; PYTHON names that python)
set -euo pipefail
out=$1
here=$(cd "$(dirname "$0")" && pwd)
py=${PYTHON:-python3}
mkdir -p "$out/guides" "$out/repository/doc"
cp "$here/index.md" "$out/README.md"

for g in UserGuide TutorialGuide ProgrammersGuide; do
  curl -sfL -A "Wget/1.21" -o "$out/guides/$g.pdf" "https://dl.openfoam.com/source/v2606/$g.pdf"
  pdftotext -layout "$out/guides/$g.pdf" "$out/guides/$g.txt"
done

for f in README.md LICENSE.md CONTRIBUTORS.md CITATION.cff doc/Build.md doc/BuildIssues.md \
         doc/Requirements.md doc/openfoam.1.in; do
  curl -sfL -o "$out/repository/$f" "https://gitlab.com/openfoam/core/openfoam/-/raw/OpenFOAM-v2606/$f"
done

"$py" -I "$here/fetch_release_notes.py" "$out/release-notes-v2606.md"
"$py" -I "$here/fetch_site.py" "$out/website"
