#!/bin/bash
# Runs one tutorial (Allrun, else blockMesh and the case's solver) with every OpenFOAM
# program and mpirun wrapped by shim.sh, which records each run.
# usage: harvest.sh <tutorial path under $FOAM_TUTORIALS, or absolute case folder> <records dir> [steps=5] [limit s=600]
set -u
tut=$1; out=$2; steps=${3:-5}; limit=${4:-600}
here=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d)
root=$work/$(basename "$tut")
case $tut in /*) src=$tut ;; *) src=$FOAM_TUTORIALS/$tut ;; esac   # a tutorial, or our own case folder
cp -a "$src" "$root"
mkdir -p "$out"; out=$(cd "$out" && pwd)

shims=$work/.shims; mkdir -p "$shims"
for p in "$FOAM_APPBIN"/* "$(command -v mpirun)"; do
    printf '#!/bin/bash\nexec bash %q %q "$@"\n' "$here/shim.sh" "$(basename "$p")" > "$shims/$(basename "$p")"
    chmod +x "$shims/$(basename "$p")"
done

export HARVEST_ROOT=$root HARVEST_OUT=$out HARVEST_STEPS=$steps HARVEST_TOOLS=$here \
       HARVEST_APPBIN=$FOAM_APPBIN HARVEST_REAL_PATH=$PATH HARVEST_SHIMS=$shims
export PATH=$shims:$PATH
unset BASH_ENV   # re-sourcing etc/bashrc would put the real programs before the shims
cd "$root"
if   [ -x Allrun ];          then script=./Allrun
elif [ -x Allrun-parallel ]; then script=./Allrun-parallel
elif [ -x Allrun-serial ];   then script=./Allrun-serial
else script="bash -c '. \$WM_PROJECT_DIR/bin/tools/RunFunctions; runApplication blockMesh; runApplication \$(getApplication)'"
fi
start=$(date +%s)
timeout -s KILL "$limit" bash -c "$script" > "$out/allrun.out" 2>&1
echo "$? $(( $(date +%s) - start ))" > "$out/allrun.status"
cd /; rm -rf "$work"
