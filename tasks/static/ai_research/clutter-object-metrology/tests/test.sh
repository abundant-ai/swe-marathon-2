#!/bin/bash
set -euo pipefail
cd /tests
exec python3 -I -B /tests/verify.py
