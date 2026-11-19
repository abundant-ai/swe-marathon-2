#!/bin/sh
# Prints the wall-clock time that remains of the 12 hours, in seconds, counted from the
# start of the machine's first process (no state file, so concurrent calls cannot race).
TOTAL_SEC=43200
elapsed=$(ps -o etimes= -p 1 2>/dev/null | tr -d ' ')
case "$elapsed" in
    ''|*[!0-9]*) elapsed=0 ;;
esac
left=$((TOTAL_SEC - elapsed))
if [ "$left" -lt 0 ]; then left=0; fi
printf '%s seconds remaining of %s\n' "$left" "$TOTAL_SEC"
