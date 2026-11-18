#!/usr/bin/env bash
# Proves at build time that a goose binary is the hardened one (apply.sh): ordinary programs and
# the standard library's own extern fns still work, and every way for a program to put code of
# its own into the compiler's process is refused. The standard library is the installed one.
# usage: smoke.sh <goose binary>
set -euo pipefail
goose="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
cd "$work"

fail() {
    echo "hardening smoke test failed: $*" >&2
    exit 1
}

# expect CODE TEXT COMMAND...: the command exits with CODE and prints TEXT on stdout or stderr.
expect() {
    local code=$1 text=$2 out status=0
    shift 2
    out="$(timeout 120 "$@" 2>&1)" || status=$?
    [ "$status" -eq "$code" ] || fail "'$*' exited $status, expected $code: $out"
    [[ "$out" == *"$text"* ]] || fail "'$*' did not print '$text': $out"
}

# The standard library's extern fns (std's popcount, math's sqrt) bind and run: the program
# checks their values itself (a failed assert aborts with a nonzero exit), so only its exit
# status and one plain word are compared here, never the way numbers print.
cat > ok.goose <<'EOF'
import std;
import math;

fn main() {
    assert(popcount(255) == 8);
    assert(sqrt(16.0) == 4.0);
    print("hardened");
}
EOF
expect 0 "hardened" "$goose" run ok.goose
# TinyCC's files come from beside the compiler whatever GOOSE_TCCLIB says.
expect 0 "hardened" env GOOSE_TCCLIB="$work/nowhere" "$goose" run ok.goose
# Every module whose files declare extern fns (slice_pool through slice_pool_internal) still checks.
for module in std math binary slice_pool; do
    printf 'import %s;\n\nfn main() {}\n' "$module" > "uses_$module.goose"
    expect 0 "" "$goose" check "uses_$module.goose"
done

# A user's extern fn or extern block, here bound to the runtime's raw memory read.
cat > peek.goose <<'EOF'
extern fn peek(p: u64, n: i64, out: u8[>..]&) -> bool = "gs_ffi_bytes";

fn main() {
    print("unreachable");
}
EOF
cat > block.goose <<'EOF'
extern "c" {
    fn puts(s: u64) -> i32;
}

fn main() {}
EOF
expect 1 "extern fn is only allowed in the standard library" "$goose" run peek.goose
expect 1 "extern fn is only allowed in the standard library" "$goose" check --diagnostics json peek.goose
expect 1 "extern fn is only allowed in the standard library" "$goose" check block.goose

# No os or ffi module.
printf 'import os;\n\nfn main() {}\n' > uses_os.goose
printf 'import ffi;\n\nfn main() {}\n' > uses_ffi.goose
expect 1 "cannot find the module os" "$goose" check uses_os.goose
expect 1 "cannot find the module ffi" "$goose" check uses_ffi.goose

# A standard library of the user's: GOOSE_STDLIB, a stdlib/ in the working directory, --stdlib.
mkdir -p fake stdlib
printf 'extern fn peek(p: u64, n: i64, out: u8[>..]&) -> bool = "gs_ffi_bytes";\n' > fake/evil.goose
cp fake/evil.goose stdlib/evil.goose
printf 'import evil;\n\nfn main() {}\n' > shadow.goose
expect 1 "cannot find the module evil" env GOOSE_STDLIB="$work/fake" "$goose" check shadow.goose
expect 1 "cannot find the module evil" "$goose" check shadow.goose
expect 1 "unknown option: --stdlib" "$goose" check --stdlib "$work/fake" shadow.goose

# C of the user's in the program: -D, --include, a sidecar; and the unsound option.
printf 'int extra;\n' > extra.h
expect 1 "unknown option: -D" "$goose" run -D GS_DEBUG=1 ok.goose
expect 1 "unknown option: -DGS_DEBUG=1" "$goose" run -DGS_DEBUG=1 ok.goose
expect 1 "unknown option: --include" "$goose" run --include extra.h ok.goose
expect 1 "unknown option: --unsafe-no-rf-check" "$goose" run --unsafe-no-rf-check ok.goose
mkdir side
cp ok.goose side/main.goose
printf 'c_sources = ["evil.c"];\n' > side/main.build
expect 1 "sidecar files are not supported" "$goose" run side/main.goose

echo "goose hardening verified: $goose"
