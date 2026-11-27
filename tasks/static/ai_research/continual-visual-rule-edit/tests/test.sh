#!/bin/bash
set -euo pipefail
cd /tests
install -d -m 700 /logs/verifier
rm -f -- /logs/verifier/{reward.txt,reward.txt.new,metrics.json,metrics.json.new,submitted.py,artifact.npz,infrastructure.json}
exec python3 -I -B /tests/verify.py
