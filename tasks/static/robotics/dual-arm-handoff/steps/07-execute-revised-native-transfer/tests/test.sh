#!/bin/sh
set -eu
exec python3 -IB /tests/verify.py --stage 7
