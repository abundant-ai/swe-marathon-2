#!/bin/bash
# Run once while the image is built, as the agent's user: the installed programs neither read the
# installed libraries for the user nor load a library the user can change, while they still read
# etc/ and load their own libraries.
set -euo pipefail
lib=/opt/openfoam/platforms/current/lib/libOpenFOAM.so
d=$(mktemp -d)
cd "$d"
mkdir system

! cat "$lib" > /dev/null 2>&1 || { echo "the user can read $lib"; exit 1; }
cat /opt/openfoam/etc/controlDict > /dev/null

cat > user.c <<'C'
#include <stdio.h>
__attribute__((constructor)) static void ran(void) { puts("USER-LIBRARY-RAN"); }
C
cc -shared -fPIC -o libuser.so user.c
cat > system/controlDict <<D
FoamFile { version 2.0; format ascii; class dictionary; object controlDict; }
application none; startFrom startTime; startTime 0; stopAt endTime; endTime 1; deltaT 1;
writeControl timeStep; writeInterval 1;
libs ("$d/libuser.so" fieldFunctionObjects);
D
mkdir 0
out=$(foamListTimes 2>&1 || true)
echo "$out"
! grep -q USER-LIBRARY-RAN <<< "$out" || { echo "a user library was loaded"; exit 1; }

printf '%s\n' 'FoamFile { version 2.0; format ascii; class dictionary; object probe; }' \
    '#includeEtc "caseDicts/setConstraintTypes"' > system/etcProbe
out=$(foamDictionary -expand system/etcProbe 2>&1)
grep -q cyclic <<< "$out" || { echo "etc/ not read: $out"; exit 1; }
printf '%s\n' 'FoamFile { version 2.0; format ascii; class dictionary; object probe; }' \
    "#include \"$lib\"" > system/libProbe
out=$(foamDictionary -expand system/libProbe 2>&1 || true)
! grep -qa ELF <<< "$out" || { echo "the library was read"; exit 1; }

cd / && rm -rf "$d"
echo "hardening checks passed"
