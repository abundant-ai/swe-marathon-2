#!/bin/bash
set -euo pipefail
cd /tests
install -d -m 700 /logs/verifier
test -O /logs
chmod go-w /logs
# The dedicated verifier owns these mounts. Only a worker's disposable HOME is writable.
chmod 700 /app/work
for shared in /tmp /var/tmp /dev/shm /dev/mqueue /run/lock; do
    if [ -d "$shared" ]; then
        chmod o-w "$shared"
    fi
done
exec python3 -IB /tests/verify.py
