#!/bin/sh
set -eu
exec python3 -I /tests/verify.py --stage 5
