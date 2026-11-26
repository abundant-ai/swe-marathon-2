#!/usr/bin/env bash
# Oracle: bring /app/harfbuzz to upstream 15.2.0 by applying the patch packaging generates from the pinned
# 14.3.0 and 15.2.0 release tarballs (both pruned the same way as the agent's tree).
set -euo pipefail
cd /app/harfbuzz
patch -p1 --no-backup-if-mismatch < /solution/private/harfbuzz-14.3.0-to-15.2.0.patch
