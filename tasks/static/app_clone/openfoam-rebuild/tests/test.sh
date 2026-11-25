#!/usr/bin/env bash
set -euo pipefail
cd /tests
exec python3 -I /tests/verify.py
