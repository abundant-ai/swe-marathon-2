#!/bin/bash
# Run once while the image is built, as the agent's user: the installed programs neither read the
# installed libraries for the user nor load a library the user can change, while they still read
# etc/ and load their own libraries. Prints each step; fails at the end if any check failed.
set -uo pipefail
lib=/opt/openfoam/platforms/current/lib/libOpenFOAM.so
d=$(mktemp -d)
cd "$d"
mkdir system 0
failed=0
fail() { echo "CHECK FAILED: $*"; failed=1; }
run() {  # run <command...>: prints the exit code and output; output in $out
    out=$("$@" 2>&1)
    local rc=$?
    echo "\$ $* -> exit $rc"
    printf '%s\n' "$out" | head -40 | sed 's/^/    /'
    return 0
}

id
cat "$lib" > /dev/null 2>&1 && fail "the user can read $lib"
cat /opt/openfoam/etc/controlDict > /dev/null || fail "etc/controlDict not readable"

cat > user.c <<'C'
#include <stdio.h>
__attribute__((constructor)) static void ran(void) { puts("USER-LIBRARY-RAN"); }
C
cc -shared -fPIC -o libuser.so user.c || fail "cannot build the test library"
cat > system/controlDict <<D
FoamFile { version 2.0; format ascii; class dictionary; object controlDict; }
application none; startFrom startTime; startTime 0; stopAt endTime; endTime 1; deltaT 1;
writeControl timeStep; writeInterval 1;
libs ("$d/libuser.so" fieldFunctionObjects);
D

run foamListTimes -help
grep -q "Usage:" <<< "$out" || fail "foamListTimes does not start"
run foamListTimes
grep -q USER-LIBRARY-RAN <<< "$out" && fail "a user library was loaded"

printf '%s\n' 'FoamFile { version 2.0; format ascii; class dictionary; object probe; }' \
    '#includeEtc "caseDicts/setConstraintTypes"' > system/etcProbe
run foamDictionary -expand system/etcProbe
grep -q cyclic <<< "$out" || fail "etc/ not read through #includeEtc"
printf '%s\n' 'FoamFile { version 2.0; format ascii; class dictionary; object probe; }' \
    "#include \"$lib\"" > system/libProbe
run foamDictionary -expand system/libProbe
grep -qa ELF <<< "$out" && fail "the library was read through #include"

cd / && rm -rf "$d"
[ "$failed" = 0 ] || exit 1
echo "hardening checks passed"
