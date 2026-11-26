#!/bin/bash
# Records a list of tutorials in parallel, packs the files into a shared store, then keeps the
# runs OpenFOAM repeats exactly and drops the checks a do-nothing program passes (one that
# prints nothing and exits 0, and one that prints nothing and exits 1).
# usage: harvest_many.sh <list file> <records dir> <verifier dir> [slots=4] [steps=5] [limit s=600]
set -u
list=$1; out=$2; verifier=$3; slots=${4:-4}; steps=${5:-5}; limit=${6:-600}
here=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$out"; out=$(cd "$out" && pwd)
grep -v '^\s*$' "$list" | xargs -P "$slots" -I{} bash -c '
    t=$1; o=$2/$(echo "$t" | tr / _)
    bash "$3/harvest.sh" "$t" "$o" "$4" "$5"
    python3 "$3/pack.py" "$2/store" "$o"
    echo "recorded $t: $(ls "$o" | grep -c -E "^[0-9]{3}-") runs, status $(cat "$o/allrun.status")"
    true' _ {} "$out" "$here" "$steps" "$limit"
python3 -B "$here/replay.py" stability "$verifier" "$out"/*/ > "$out/stability.txt" 2>&1
for code in 0 1; do
    dummy=$(mktemp -d)
    for p in "$FOAM_APPBIN"/*; do printf '#!/bin/sh\nexit %s\n' "$code" > "$dummy/$(basename "$p")"; chmod +x "$dummy/$(basename "$p")"; done
    PATH=$dummy:$PATH python3 -B "$here/replay.py" dummy "$verifier" "$out"/*/ > "$out/dummy$code.txt" 2>&1
done
python3 -B "$here/replay.py" check "$verifier" "$out"/*/ > "$out/check.txt" 2>&1
echo "$(tail -1 "$out/stability.txt"); gold: $(tail -1 "$out/check.txt"); store: $(du -sh "$out/store" | cut -f1)"
