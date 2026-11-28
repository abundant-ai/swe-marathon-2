#!/usr/bin/env bash
set -euo pipefail
umask 022
# Root resolves no command through the PATH it was started with (QA, Dogwood pass 07 F1).
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
cd /tests
exec /usr/bin/python3 -I -B /tests/verify.py
