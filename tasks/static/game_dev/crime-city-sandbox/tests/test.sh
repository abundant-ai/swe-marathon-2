#!/usr/bin/env bash
# Thin adapter: the verifier image holds the grader, the kit, the telemetry library and
# the private instances under /tests. Draft until WS7 packages the images.
set -euo pipefail
cd /tests
exec python3 -I -B /tests/verify.py
