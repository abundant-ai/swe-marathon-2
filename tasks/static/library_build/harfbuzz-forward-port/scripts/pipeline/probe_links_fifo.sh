#!/bin/sh
# Probe (b), R2-M4: links and a FIFO in the delivered tree.
#
# Run as the turn of a simulated trial (run_probes.py) after solution/solve.sh, so the tree is the reference's. It
# adds, as an honest session might:
#   - an absolute link into the tree (a shortcut to a header);
#   - an absolute link out of the tree, to a file (the system's python3, as a virtual environment has);
#   - a relative link leaving the tree, to a folder (the shipped specifications, ../docs/specs);
#   - a link to nothing, and a link to a device;
#   - a FIFO a test left behind.
#
# Expected, with the sweep: the in-tree link becomes relative, the two outward links become copies of what they
# lead to, the dangling and device links and the FIFO are removed, every change is noted, the transfer carries the
# whole tree, sweep_check.py finds no fault, and the tree scores 1.0.
# Expected, without the sweep (run_probes.py's raw variant): GNU tar packs the links and the FIFO as they are, and
# the extraction with the "data" filter stops at the first of them it meets, so fewer entries arrive than were
# packed.
set -eu
cd /app/harfbuzz
ln -s /app/harfbuzz/src/hb.h hb-header-shortcut.h
ln -s /usr/bin/python3 python3
ln -s ../docs/specs specs
ln -s /app/harfbuzz/no-such-file dangling-link
ln -s /dev/null null-device
mkfifo test/fifo-left-by-a-test
