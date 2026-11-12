#!/usr/bin/env bash
set -euo pipefail
cd /tests
exec /opt/runtime/bin/python -I /tests/verify.py
