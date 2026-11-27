#!/bin/sh
# make_robust REFERENCE_TREE OUT_TREE
#
# A delivered tree with the clutter a session can leave behind: a named pipe, a 600 MB sparse file, 100,000 empty
# files, a link out of the tree and a dangling link. The verifier must grade it as it grades the tree without them.
# Copied without test/ (the product build never reads it). Runs inside the pipeline image only.
set -eu
REF=$1
OUT=$2
test ! -e "$OUT"
mkdir -p "$OUT"
(cd "$REF" && tar -cf - --exclude=./test .) | (cd "$OUT" && tar -xf -)
cd "$OUT"
mkfifo stray.fifo || echo "make_robust: no named pipe on this file system; make it from the host"
truncate -s 600M big.bin
mkdir many
i=0
while [ "$i" -lt 100000 ]; do
  : > "many/f$i"
  i=$((i + 1))
done
ln -s /etc/passwd outside-link
ln -s /nonexistent dangling-link
echo "robust tree: $(ls many | wc -l) extra files"
