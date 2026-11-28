#!/bin/sh
# make_stall BASE_TREE OUT_TREE
#
# A delivered tree whose build and library try to stall the verifier's sweeps, as the `builder` user the verifier runs
# them as (R2-M6, R2-07 N1). At `meson setup` (a run_command), at `ninja` (a custom target) and on the first font load
# of every case program (hb_blob_create_from_file_or_fail()), it leaves behind, each in a session of its own:
#   - a stopper: threads that, once the step's `timeout` has ended (that is, while root sweeps), send SIGSTOP to every
#     process they may signal (kill(-1)), over and over, and SIGCONT to the survivor;
#   - a survivor that changes its pid all the time (it forks, and the parent exits), to dodge per-process kills.
# The first three case programs start their stopper at once and then wait, so the case program and its `timeout` are
# stopped and the batch runs into root's own limit. BASE_TREE is the shipped 14.3.0 tree, whose true score is 0.
# Round 1's verifier swept with a child that took builder's uids; the stoppers stopped it, root's wait never returned,
# and the reward came at the 2,100 s alarm or not at all.
# Expected: reward.txt 0.0, written after about as long as for the reference plus three stalled batches (155 s on
# Docker Desktop's emulated amd64), and never later than about 1,800 s; metrics.json notes processes of builder left
# running and killed after setup, the build and every batch, and the first three batches "stopped at its time limit
# (15s)"; no note says processes "could not be stopped", and "survivors" is null.
# Copied without test/ (the product build never reads it). Runs inside the pipeline image only.
set -eu
BASE=$1
OUT=$2
test ! -e "$OUT"
mkdir -p "$OUT"
(cd "$BASE" && tar -cf - --exclude=./test .) | (cd "$OUT" && tar -xf -)
mkdir "$OUT/stall"

cat > "$OUT/stall/stall-core.h" <<'C'
/* Stall probe (scripts/pipeline/make_stall.sh): processes of the tree's user that try to stop the verifier's
   sweeping child. Compiles as C and as C++ (the library includes it); every function is static inline. */
#ifndef HB_STALL_CORE_H
#define HB_STALL_CORE_H
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

typedef struct
{
  volatile pid_t survivor;
} hb_stall_shared_t;

static hb_stall_shared_t *hb_stall_shared;

/* The nearest ancestor whose name is `name`, else the parent. */
static inline pid_t
hb_stall_ancestor (const char *name)
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
    if (!strcmp (open_paren + 1, name))
      return pid;
    int ppid = 0;
    if (sscanf (close_paren + 2, "%*c %d", &ppid) != 1)
      break;
    pid = (pid_t) ppid;
  }
  return parent;
}

static inline void *
hb_stall_spin (void *arg)
{
  (void) arg;
  for (;;)
  {
    kill (-1, SIGSTOP); /* every process this one may signal, but its own */
    pid_t survivor = hb_stall_shared->survivor;
    if (survivor > 0)
      kill (survivor, SIGCONT);
  }
  return NULL;
}

static inline void
hb_stall_detach (void)
{
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
}

/* A survivor and a stopper, out of the caller's way; the stopper starts once `wait_for` has ended (at once for 0). */
static inline void
hb_stall_start (pid_t wait_for)
{
  void *page = mmap (NULL, sizeof (hb_stall_shared_t), PROT_READ | PROT_WRITE, MAP_SHARED | MAP_ANONYMOUS, -1, 0);
  if (page == MAP_FAILED)
    return;
  hb_stall_shared = (hb_stall_shared_t *) page;
  hb_stall_shared->survivor = 0;
  pid_t p = fork ();
  if (p == 0)
  {
    if (fork () != 0)
      _exit (0);
    hb_stall_detach ();
    for (;;)
    {
      pid_t q = fork ();
      if (q > 0)
        _exit (0);
      if (q == 0)
        hb_stall_shared->survivor = getpid ();
      usleep (500);
    }
  }
  if (p > 0)
    waitpid (p, NULL, 0);
  p = fork ();
  if (p == 0)
  {
    if (fork () != 0)
      _exit (0);
    hb_stall_detach ();
    while (wait_for > 0 && (kill (wait_for, 0) == 0 || errno == EPERM))
      usleep (200);
    pthread_t thread;
    for (int i = 0; i < 2; i++)
      pthread_create (&thread, NULL, hb_stall_spin, NULL);
    hb_stall_spin (NULL);
  }
  if (p > 0)
    waitpid (p, NULL, 0);
}

/* How many case programs have loaded a font so far, this one included. */
static inline int
hb_stall_turn (void)
{
  const char *dir = getenv ("TMPDIR");
  char path[512];
  snprintf (path, sizeof (path), "%s/.hb-stall-count", dir && *dir ? dir : "/tmp");
  int fd = open (path, O_WRONLY | O_CREAT | O_APPEND, 0600);
  if (fd < 0)
    return 1000;
  ssize_t written = write (fd, "x", 1);
  (void) written;
  struct stat st;
  int turn = fstat (fd, &st) == 0 ? (int) st.st_size : 1000;
  close (fd);
  return turn;
}
#endif
C

cat > "$OUT/stall/stall.c" <<'C'
/* Stall probe: `stall [STAMP]` leaves a stopper and a survivor that start once the step's `timeout` (the nearest
   ancestor of that name) has ended; with STAMP, it also writes that file (a build target's output). */
#include "stall-core.h"

int
main (int argc, char **argv)
{
  hb_stall_start (hb_stall_ancestor ("timeout"));
  if (argc > 1)
  {
    FILE *stamp = fopen (argv[1], "w");
    if (stamp)
      fclose (stamp);
  }
  return 0;
}
C

cat >> "$OUT/meson.build" <<'MESON'

# Stall probe (scripts/pipeline/make_stall.sh): processes that try to stop the verifier's sweeping child.
stall_exe = meson.current_build_dir() / 'hb-stall'
run_command('cc', '-O2', '-pthread', '-o', stall_exe, meson.current_source_dir() / 'stall' / 'stall.c', check: true)
stall = find_program(stall_exe)
run_command(stall, check: false)
custom_target('stall-build',
  output: 'stall-build.stamp',
  command: [stall, '@OUTPUT@'],
  build_by_default: true,
)
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
s = s.replace(anchor, anchor + '\n#include "../stall/stall-core.h"\n', 1)
m = re.search(r"\nhb_blob_create_from_file_or_fail \(const char \*file_name\)\n\{\n", s)
if not m:
    raise SystemExit(f"hb_blob_create_from_file_or_fail not found in {path}")
probe = """  {
    /* Stall probe (scripts/pipeline/make_stall.sh): on the first font load of each case program, a stopper and a
       survivor. The first three case programs start the stopper at once and wait for it to stop them; the others
       leave one that starts once their `timeout` has ended. */
    static int _hb_probe_stalled;
    if (!_hb_probe_stalled)
    {
      _hb_probe_stalled = 1;
      if (hb_stall_turn () <= 3)
      {
        hb_stall_start (0);
        for (;;)
          pause ();
      }
      hb_stall_start (hb_stall_ancestor ("timeout"));
    }
  }
"""
s = s[: m.end()] + probe + s[m.end() :]
path.write_text(s)
PY
echo "stall tree: $(grep -c hb_stall_start "$OUT/src/hb-blob.cc") library hook, $(wc -l < "$OUT/stall/stall-core.h") lines of stopper"
