#!/usr/bin/env bash
cd /tests || exit 1
exec /usr/local/bin/python3 -I /tests/verify.py
