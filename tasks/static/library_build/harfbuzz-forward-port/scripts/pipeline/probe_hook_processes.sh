#!/bin/sh
# Probe (d): round 1's collect-hook test (fix1-final plan, step 160), as the turn of a simulated trial
# (run_probes.py) after solution/solve.sh. It leaves processes of dev behind: a stopped one, a setsid one, a
# forking loop (a new `sleep 5` every 50 ms) and a nohup one; round 1 counted 22 of them after a second.
#
# Run with --no-egress: the net check sees no opening and ends nothing, so the sweep alone has to stop them (the
# forking loop too), list them and kill them.
#
# Expected: the sweep lists at least 22 processes of dev, kills every one (processes_left 0), takes the end of the
# work from the session, finds no late change, and the oracle's tree scores 1.0 with no fault.
set -eu
sleep 1000 > /dev/null 2>&1 < /dev/null &
stopped=$!
kill -STOP "$stopped"
setsid sleep 1000 > /dev/null 2>&1 < /dev/null &
(while :; do sleep 5 & sleep 0.05; done) > /dev/null 2>&1 < /dev/null &
nohup sleep 1000 > /dev/null 2>&1 < /dev/null &
sleep 1
pgrep -u dev | wc -l > /home/dev/processes-before.txt
