#!/bin/bash
set -euo pipefail
cd /app/work
python3 -B /solution/oracle.py
./python smoke.py
