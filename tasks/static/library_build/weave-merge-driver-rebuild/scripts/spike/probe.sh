#!/bin/bash
# Run as dev: every route to the installed build's bytes must fail; running it must work.
B=/usr/local/bin/weave-driver
say() { printf '%-34s %s\n' "$1" "$2"; }
say "id" "$(id)"
say "mode" "$(stat -c '%A %U:%G' $B)"
say "run --version" "$($B --version 2>&1)"
cat $B > /tmp/copy 2>/dev/null && say "read the file" "READ OK ($(stat -c %s /tmp/copy) bytes)" || say "read the file" "refused"
cp $B /tmp/copy2 2>/dev/null && say "cp" "COPIED" || say "cp" "refused"
out=$(strace -f -o /tmp/st.txt $B --version 2>&1); say "strace" "rc=$? out=${out:0:60}"
grep -c . /tmp/st.txt 2>/dev/null | xargs -I{} printf '%-34s %s\n' "strace lines" "{}"
out=$(gdb -batch -ex run -ex 'info proc mappings' --args $B --version 2>&1 | tail -3 | tr '\n' ' '); say "gdb" "${out:0:150}"
cat > /tmp/pre.c <<'C'
#include <stdio.h>
__attribute__((constructor)) static void hit(void) { FILE *f = fopen("/tmp/preload-ran", "w"); if (f) fclose(f); }
C
gcc -shared -fPIC -o /tmp/pre.so /tmp/pre.c 2>/dev/null
LD_PRELOAD=/tmp/pre.so $B --version > /dev/null 2>&1
[ -e /tmp/preload-ran ] && say "LD_PRELOAD constructor" "RAN" || say "LD_PRELOAD constructor" "ignored"
mkfifo /tmp/fifo; printf 'x\n' > /tmp/o.py; printf 'y\n' > /tmp/t.py
$B /tmp/fifo /tmp/o.py /tmp/t.py -o /tmp/out.py -l 7 -p a.py & pid=$!
sleep 1
dd if=/proc/$pid/mem bs=1 count=16 skip=4194304 of=/dev/null 2>/dev/null && say "/proc/pid/mem" "READ OK" || say "/proc/pid/mem" "refused"
cat /proc/$pid/exe > /tmp/exe 2>/dev/null && say "/proc/pid/exe" "READ OK" || say "/proc/pid/exe" "refused"
say "/proc/pid/status Dumpable" "$(grep -i -m1 -E '^(Uid|Gid)' /proc/$pid/status | tr '\t' ' ')"
gdb -batch -p $pid -ex 'info proc' > /tmp/attach.txt 2>&1; say "gdb attach" "$(grep -i -m1 -E 'not permitted|ptrace|Attaching' /tmp/attach.txt)"
ulimit -c unlimited; kill -SEGV $pid; wait $pid 2>/dev/null; sleep 1
ls /tmp/core* > /dev/null 2>&1 && say "core dump" "WRITTEN" || say "core dump" "none"
