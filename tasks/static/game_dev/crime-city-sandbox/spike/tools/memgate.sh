#!/bin/bash
# Usage: memgate.sh [min_free_pct]  -> prints free %, exits 1 if below the floor (default 30).
min=${1:-30}
pct=$(memory_pressure 2>/dev/null | awk -F': ' '/System-wide memory free percentage/{gsub("%","",$2); print $2}')
if [ -z "$pct" ]; then echo "memgate: cannot read memory_pressure" >&2; exit 2; fi
echo "memgate: free ${pct}% (floor ${min}%)"
if [ "$pct" -lt "$min" ]; then echo "memgate: BELOW FLOOR, not starting" >&2; exit 1; fi
exit 0
