#!/bin/bash
# Core-dump check as the agent user, bounded: every wait has a timeout, the FIFO's write end is
# opened to release a reader blocked in open(), and the signals are ones Rust does not catch.
set -u
mkdir -p /tmp/coretest && cd /tmp/coretest || exit 1
echo "user: $(id -un) groups: $(id -Gn)"
echo "suid_dumpable: $(cat /proc/sys/fs/suid_dumpable 2>/dev/null || echo unreadable)"
echo "core_pattern: $(cat /proc/sys/kernel/core_pattern 2>/dev/null || echo unreadable)"
ulimit -c unlimited; echo "core limit: $(ulimit -c)"
printf 'x = 1\n' > b.py; printf 'x = 2\n' > t.py
for sig in ABRT QUIT; do
  rm -f fifo core core.*; mkfifo fifo
  /usr/local/bin/weave-driver fifo b.py t.py -o out.py -l 7 -p a.py &
  pid=$!
  sleep 1
  owner=$(stat -c '%U:%G' /proc/$pid/environ 2>/dev/null || echo gone)
  kill -$sig $pid 2>/dev/null
  timeout 5 bash -c 'exec 3> fifo; echo "x = 3" >&3' 2>/dev/null
  timeout 10 tail --pid=$pid -f /dev/null 2>/dev/null
  kill -KILL $pid 2>/dev/null
  wait $pid 2>/dev/null; rc=$?
  cores=$(ls core core.* 2>/dev/null | tr '\n' ' ')
  echo "SIG$sig: /proc/pid/environ owned by $owner; exit $rc; core files: ${cores:-none}"
done
echo "probe done"
