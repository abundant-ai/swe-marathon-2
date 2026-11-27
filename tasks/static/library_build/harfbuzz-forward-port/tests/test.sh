#!/usr/bin/env bash
set -euo pipefail
umask 022
cd /tests
exec python3 -I -B /tests/verify.py
