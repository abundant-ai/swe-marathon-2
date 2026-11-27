#!/bin/bash
set -euo pipefail
cd /app/work
python3 /solution/oracle.py
./python smoke.py
