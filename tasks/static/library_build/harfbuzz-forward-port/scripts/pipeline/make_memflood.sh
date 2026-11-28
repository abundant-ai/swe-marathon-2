#!/bin/sh
# make_memflood BASE_TREE OUT_TREE
#
# A delivered tree that fills the container's memory with many small processes (R2-21 N3), as the `builder` user the
# verifier runs it as. At `meson setup`, a run_command forks children that each touch 16 MiB (less than the
# verifier's own Python) and wait, until a fork fails, a child is killed (the kernel's out-of-memory killer at work)
# or 4,000 have been made; it then waits 2 s and returns, leaving the children behind. Under a hard memory limit
# (Docker's --memory; 8 GiB on the platform) the kernel kills a process each time the limit is reached. With the
# verifier at oom_score_adj -1000 (or 0 where root may not lower it) and every builder process at +1000, it kills
# builder's processes, the largest first: meson. Round 1's verifier gave builder no score, so once meson was gone the
# largest process left was the verifier itself, and no reward was written. BASE_TREE is the reference tree.
# Expected (docker run --memory=4g --memory-swap=4g): setup ends "exit 137" or "exit -9" (the kernel killed meson, or
# the step's own timeout), so no case program is built; reward.txt 0.0 is written well inside a minute (23 s on Docker
# Desktop's emulated amd64); metrics.json notes the children left running and killed after setup (272 there) and a
# peak_rss_mib of tens of MiB. On a platform that kills the whole sandbox instead of one process (Modal in its AUTO
# memory mode) no limit inside the container helps: that residual needs a cgroup.
# Copied without test/ (the product build never reads it). Runs inside the pipeline image only.
set -eu
BASE=$1
OUT=$2
test ! -e "$OUT"
mkdir -p "$OUT"
(cd "$BASE" && tar -cf - --exclude=./test .) | (cd "$OUT" && tar -xf -)
mkdir "$OUT/memflood"

cat > "$OUT/memflood/flood.c" <<'C'
/* Memory-flood probe (scripts/pipeline/make_memflood.sh). */
#include <fcntl.h>
#include <signal.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

int
main (void)
{
  const size_t size = 16u << 20;
  for (int made = 0; made < 4000; made++)
  {
    pid_t p = fork ();
    if (p < 0)
      break;
    if (p == 0)
    {
      /* Let go of meson's pipes, so that run_command returns while the children wait. */
      int null = open ("/dev/null", O_RDWR);
      if (null >= 0)
      {
        dup2 (null, 0);
        dup2 (null, 1);
        dup2 (null, 2);
      }
      char *block = (char *) malloc (size);
      if (block)
        for (size_t i = 0; i < size; i += 4096)
          block[i] = 1;
      for (;;)
        pause ();
    }
    int status;
    pid_t gone = waitpid (-1, &status, WNOHANG);
    if (gone > 0 && WIFSIGNALED (status) && WTERMSIG (status) == SIGKILL)
      break;
  }
  sleep (2);
  return 0;
}
C

cat >> "$OUT/meson.build" <<'MESON'

# Memory-flood probe (scripts/pipeline/make_memflood.sh): small processes until the memory runs out.
flood_exe = meson.current_build_dir() / 'hb-memflood'
run_command('cc', '-O2', '-o', flood_exe, meson.current_source_dir() / 'memflood' / 'flood.c', check: true)
run_command(find_program(flood_exe), check: false)
MESON
echo "memory-flood tree: $(grep -c hb-memflood "$OUT/meson.build") meson lines"
