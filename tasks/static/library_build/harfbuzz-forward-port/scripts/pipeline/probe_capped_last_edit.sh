#!/bin/sh
# Probe (e), R2-08 finding 1 fix 3: an honest capped run's last edit must not be zeroed.
#
# Run as the turn of a simulated trial (run_probes.py) after solution/solve.sh, with --limit-in 9: the start of the
# work is recorded 34,560 s minus 9 s before the hooks' set-up, so the work's time limit falls about 9 s into the
# trial, as the cap does in a run that reaches it. Before the limit the turn makes its last edit of a file the build
# needs (a comment appended to src/hb-ot-layout.cc); after the limit it keeps working, as the agent does until the
# hook stops it: it overwrites that file with a line that breaks the build and makes a new file.
#
# Expected: the end of the work is the limit; the file changed after it is put back as the last copy from before
# it (the edit with the comment, not removed and not the late version), the new file is removed, and the tree
# scores 1.0 with no fault.
set -eu
cd /app/harfbuzz
printf '\n// the last edit before the limit\n' >> src/hb-ot-layout.cc
sleep 12
printf '#error an edit after the limit\n' > src/hb-ot-layout.cc
echo "made after the limit" > made-after-the-limit.txt
