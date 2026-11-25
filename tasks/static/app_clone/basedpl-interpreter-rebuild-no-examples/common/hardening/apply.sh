#!/bin/sh
# Hardens a BasedPL source tree at the pinned commit before it is built: applies
# basedpl-hardening.patch, which sits beside this script, writes the all-zero build marker, and
# places the pinned Cargo.lock. `git apply` changes all nine files or none, and the checks after it
# fail unless every file carries the change and nothing the patch removes is left.
#
# What the patch does, file by file:
#   src/host.rs     reads a file only where the file actually opened lies under the working
#                   directory and outside /proc, /sys and /dev; `•fetch` starts no program
#                   (upstream runs curl) and opens no connection
#   src/lib.rs      the same read for the command line's program file
#   src/data.rs     `•nput` writes no file (standard output is unchanged)
#   src/files.rs    `•metadata`, `•readdir`, `•copy`, `•rename`, `•remove`, `•mkdir` refuse
#   jit/src/lib.rs  no kernel is compiled to machine code (Cranelift is never called)
#   cli/src/cli.rs  no `--kernel` (Jupyter sockets) and no `--costs` (timing); usage text to match
#   cli/src/worker.rs  only code, call and bindings requests: no reference checks, timings or files
#   cli/src/editor.rs  the REPL reads and writes no history file
#   cli/src/main.rs the build marker (cli/src/build_marker.txt), kept in the binary, never printed
# usage: apply.sh <basedpl source tree at the pinned commit>
set -eu
here=$(cd "$(dirname "$0")" && pwd)
cd "$1"
# Never the patch of an enclosing repository's paths: no repository above this tree is used.
GIT_CEILING_DIRECTORIES=$(dirname "$(pwd)") git apply "$here/basedpl-hardening.patch"
printf 'BPL-BUILD-MARKER-00000000000000000000000000000000' > cli/src/build_marker.txt
cp "$here/Cargo.lock" Cargo.lock
for file in src/host.rs src/lib.rs src/data.rs src/files.rs jit/src/lib.rs cli/src/cli.rs cli/src/worker.rs cli/src/editor.rs cli/src/main.rs; do
    grep -q "Hardened build" "$file" || { echo "hardening patch missing from $file" >&2; exit 1; }
done
if grep -q 'Command::new("curl")' src/host.rs \
    || grep -q 'std::fs::read(path)' src/host.rs \
    || grep -q 'OpenOptions' src/data.rs \
    || grep -qE 'crate::kernel::run|flag == "--costs"|--costs PATH|--kernel -f' cli/src/cli.rs \
    || grep -q '^mod kernel;' cli/src/main.rs \
    || grep -qE 'request\.get\("(case|timing|steps|profile|costs|check|reference|page|route)"\)' cli/src/worker.rs \
    || grep -q 'XDG_CONFIG_HOME' cli/src/editor.rs \
    || grep -q 'self.compile()?' jit/src/lib.rs \
    || ! grep -q 'black_box(BUILD_MARKER)' cli/src/main.rs \
    || [ "$(grep -c 'refuse("•' src/files.rs)" -ne 6 ]; then
    echo "hardening patch incomplete" >&2
    exit 1
fi
echo "basedpl sources hardened"
