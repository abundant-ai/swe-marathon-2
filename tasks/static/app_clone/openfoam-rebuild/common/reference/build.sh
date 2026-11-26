#!/bin/bash
# Builds the hardened OpenFOAM from a staged source tree and installs only what its programs need
# at run time: programs, libraries, and the run-time data under etc/ and bin/tools.
# Nothing else (sources, objects, lnInclude trees, build logs) leaves the build stage.
# usage: build.sh <source tree> <install prefix> <jobs>
set -euo pipefail
src=$1; prefix=$2; jobs=$3

cd "$src"
# The hardened build: hardening.patch beside this script, applied once (a source tree shipped
# without it has it applied already).
hardening="$(dirname "$(readlink -f "$0")")/hardening.patch"
if [ -f "$hardening" ]; then
    patch -p1 -R -s -f --dry-run < "$hardening" > /dev/null 2>&1 || patch -p1 -s < "$hardening"
fi
[ -f src/OSspecific/POSIX/hardened.C ] || { echo "source not hardened" >&2; exit 1; }
# Third-party libraries: Ubuntu's own, as in the official openfoam2606 package.
sed -i 's/^SCOTCH_VERSION=.*/SCOTCH_VERSION=scotch-system/' etc/config.sh/scotch
sed -i 's/^METIS_VERSION=.*/METIS_VERSION=metis-system/' etc/config.sh/metis
sed -i 's/^KAHIP_VERSION=.*/KAHIP_VERSION=kahip-none/' etc/config.sh/kahip
sed -i 's/^fftw_version=.*/fftw_version=fftw-system/' etc/config.sh/FFTW
sed -i 's/^boost_version=.*/boost_version=boost-system/; s/^cgal_version=.*/cgal_version=cgal-system/' etc/config.sh/CGAL

# etc/bashrc is not written for set -eu (its last test may be false)
set +eu; source etc/bashrc; set -eu
echo "building $WM_OPTIONS with $jobs jobs"
[ "$WM_PROJECT_DIR" = "$src" ] || { echo "OpenFOAM environment not set (WM_PROJECT_DIR=$WM_PROJECT_DIR)" >&2; exit 1; }
export WM_NCOMPPROCS=$jobs
./Allwmake -j "$jobs" -s -q -l || true   # failures are caught by the program check below
echo "Allwmake finished; errors in log: $(grep -c -E 'Error [0-9]' "log.$WM_OPTIONS" || true)"
# Allwmake ends 0 even when some targets fail; require the programs the tutorials use.
for p in blockMesh snappyHexMesh checkMesh decomposePar reconstructPar simpleFoam pimpleFoam \
         icoFoam interFoam rhoPimpleFoam buoyantSimpleFoam foamDictionary postProcess; do
    [ -x "$FOAM_APPBIN/$p" ] || { echo "missing program: $p" >&2; exit 1; }
done

mkdir -p "$prefix/platforms/$WM_OPTIONS" "$prefix/bin"
cp -a "$FOAM_APPBIN" "$prefix/platforms/$WM_OPTIONS/bin"
cp -a "$FOAM_LIBBIN" "$prefix/platforms/$WM_OPTIONS/lib"
cp -a etc "$prefix/etc"
cp -a bin/tools "$prefix/bin/tools"
for s in foamRunTutorials foamCleanTutorials foamEtcFile foamCleanPath foamCleanPolyMesh foamCloneCase; do
    [ -e "bin/$s" ] && cp -a "bin/$s" "$prefix/bin/"
done
echo "$WM_OPTIONS" > "$prefix/WM_OPTIONS"
echo "programs: $(ls "$prefix/platforms/$WM_OPTIONS/bin" | wc -l)  libraries: $(find "$prefix/platforms/$WM_OPTIONS/lib" -name '*.so' | wc -l)"
