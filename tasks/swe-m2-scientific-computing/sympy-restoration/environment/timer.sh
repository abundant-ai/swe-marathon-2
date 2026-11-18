#!/bin/sh
# Prints the wall-clock budget that remains, in seconds, counted over all working sessions.
TOTAL_SEC=172800
# Time used by earlier sessions; scripts/package_session.py sets it for sessions after the first.
USED_BEFORE_SEC=0
start_file=/app/.work-start
if [ ! -f "$start_file" ]; then
    now=$(date +%s)
    start=$(stat -c %Y /proc/1 2>/dev/null || echo "$now")
    # the start time of PID 1 is the container start; fall back to "now" if it looks wrong
    age=$((now - start))
    if [ "$age" -lt 0 ] || [ "$age" -gt 172800 ]; then start=$now; fi
    echo "$start" > "$start_file"
fi
now=$(date +%s)
start=$(cat "$start_file")
left=$((TOTAL_SEC - USED_BEFORE_SEC - now + start))
if [ "$left" -lt 0 ]; then left=0; fi
printf '%s seconds remaining of %s\n' "$left" "$TOTAL_SEC"
