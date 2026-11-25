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

# Nothing writes C, the program's or the runtime's own: no goose build, no -o, --standalone,
# --header, --emit-runtime or --gen-runtime-header.
expect 1 "unknown option: --emit-runtime" "$goose" --emit-runtime runtime.c
expect 1 "unknown option: --gen-runtime-header" "$goose" --gen-runtime-header
expect 1 "unknown option: -o" "$goose" -o program.c ok.goose
expect 1 "unknown option: --standalone" "$goose" --standalone ok.goose
expect 1 "unknown option: --header" "$goose" --header program.h ok.goose
expect 1 "goose build is not available" "$goose" build ok.goose
written="$(find "$work" -name '*.c' -o -name program.h)"
[ -z "$written" ] || fail "C was written: $written"
# Nor does any help or completion script offer them.
for topic in "" check run c internals version; do
    out="$("$goose" help $topic 2>&1)" || true
    case "$out" in
        *"-D NAME"*|*"--stdlib"*|*"--include"*|*"-o out"*|*"--standalone"*|*"--emit-runtime"*|*"--unsafe-no-rf-check"*|*"--gen-runtime-header"*)
            fail "goose help $topic still offers a removed option: $out" ;;
    esac
done
out="$("$goose" completion zsh 2>&1)" || true
case "$out" in
    *"--stdlib"*|*"--standalone"*|*"--emit-runtime"*) fail "the zsh completion still offers a removed option" ;;
esac

# embed_file reads only files under the directory of the file that embeds it: one beside it
# still works, while an absolute path, a ".." and a symbolic link that lead out of it (to the
# compiler's own /proc/self files) are refused. No shaders either, whose files the shader
# compiler would read in the compiler's process.
mkdir -p embed/sub
printf 'inside\n' > embed/data.txt
ln -s /proc/self/maps embed/maps.txt
embed_case() {
    printf 'import std;\n\nlet TABLE: const u8[:] = embed_file("%s");\n\nfn main() {\n    print(TABLE.len);\n}\n' "$1" > embed/sub/main.goose
    cp embed/sub/main.goose embed/main.goose
}
embed_case data.txt
expect 0 "7" "$goose" run embed/main.goose
embed_case /proc/self/maps
expect 1 "is outside the directory of the file that embeds it" "$goose" run embed/main.goose
embed_case ../data.txt
expect 1 "is outside the directory of the file that embeds it" "$goose" run embed/sub/main.goose
embed_case maps.txt
expect 1 "is outside the directory of the file that embeds it" "$goose" check embed/main.goose
# Nothing under /proc, /sys or /dev is a program, a module or a file to format, by name or link:
# the compiler's own environment and memory map never become source text in a message.
secret=smoke-environ-7d1e9c
ln -s /proc/self/environ envmod.goose
ln -s /proc/self/maps maps.goose
printf 'import envmod;\n\nfn main() {}\n' > uses_env.goose
for command in "run /proc/self/environ" "check envmod.goose" "check uses_env.goose" "run maps.goose" \
               "format --check /proc/self/environ" "check /dev/null"; do
    status=0
    out="$(env GOOSE_SMOKE_SECRET=$secret timeout 120 "$goose" $command 2>&1)" || status=$?
    [ "$status" -ne 0 ] || fail "goose $command succeeded"
    case "$out" in *"$secret"*|*"[stack]"*) fail "goose $command printed the compiler's process files: $out" ;; esac
done
printf 'fn main() {\n    let s = embed_shader("frag", "void main() {}");\n}\n' > shader.goose
expect 1 "embed_shader is not available in this build of goose" "$goose" check shader.goose

echo "goose hardening verified: $goose"
