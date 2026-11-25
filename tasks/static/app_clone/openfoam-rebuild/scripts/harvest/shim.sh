#!/bin/bash
# Wraps one OpenFOAM program (or mpirun) while a tutorial runs: saves the folder before the
# run, the command, and what the run wrote, printed and returned, then behaves like the program.
# usage: shim.sh <program> <args...>
# env: HARVEST_ROOT (tutorial folder), HARVEST_OUT (records), HARVEST_STEPS (solver step cap),
#      HARVEST_INSIDE (set during a recorded run, so nested calls are not recorded)
prog=$1; shift
real=$(PATH=$HARVEST_REAL_PATH command -v "$prog")
[ -n "$real" ] || { echo "harvest shim: no real $prog" >&2; exit 127; }
if [ -n "${HARVEST_INSIDE:-}" ] || [ -z "${HARVEST_ROOT:-}" ]; then
    exec -a "$prog" "$real" "$@"
fi

# For mpirun, the program is the first OpenFOAM program among the arguments.
app=$prog
if [ "$prog" = mpirun ] || [ "$prog" = mpiexec ]; then
    app=
    for a in "$@"; do [ -x "$HARVEST_APPBIN/$a" ] && { app=$a; break; }; done
fi
# Case folder: -case <dir>, else the current folder.
case_dir=$PWD; prev=
for a in "$@"; do [ "$prev" = -case ] && case_dir=$(cd "$a" 2>/dev/null && pwd); prev=$a; done

# Solvers: write every N steps and stop at the first write.
if [ "${HARVEST_STEPS:-0}" -gt 0 ] && [[ "$app" == *Foam ]] && [[ "$app" != *ToFoam ]] \
   && [ -f "$case_dir/system/controlDict" ]; then
    for kv in "writeControl timeStep" "writeInterval $HARVEST_STEPS" "stopAt nextWrite"; do
        HARVEST_INSIDE=1 "$HARVEST_APPBIN/foamDictionary" -case "$case_dir" -entry "${kv%% *}" \
            -set "${kv#* }" system/controlDict >/dev/null 2>&1
    done
fi

n=$(( $(cat "$HARVEST_OUT/.count" 2>/dev/null || echo 0) + 1 )); echo $n > "$HARVEST_OUT/.count"
rec=$HARVEST_OUT/$(printf %03d $n)-${app:-$prog}
mkdir -p "$rec/input"
tar -C "$HARVEST_ROOT" --exclude='./log.*' --exclude='*/log.*' -cf - . | tar -C "$rec/input" -xf -
python3 - "$rec/cmd.json" "$prog" "${app:-}" "$(realpath --relative-to="$HARVEST_ROOT" "$PWD")" "$HARVEST_ROOT" "$(hostname)" "$@" <<'EOF'
import json, sys
out, prog, app, cwd, root, host, *args = sys.argv[1:]
json.dump({"program": prog, "app": app, "args": args, "cwd": cwd, "root": root, "host": host},
          open(out, "w"), indent=1)
EOF

start=$(date +%s.%N)
( export HARVEST_INSIDE=1; exec -a "$prog" "$real" "$@" ) > >(tee "$rec/stdout") 2> >(tee "$rec/stderr" >&2)
rc=$?
end=$(date +%s.%N)
wait
echo $rc > "$rec/exit"
echo "$end - $start" | bc > "$rec/seconds"
# Keep only files the run created or changed.
python3 "$HARVEST_TOOLS/snapdiff.py" "$rec/input" "$HARVEST_ROOT" "$rec/output"
exit $rc
