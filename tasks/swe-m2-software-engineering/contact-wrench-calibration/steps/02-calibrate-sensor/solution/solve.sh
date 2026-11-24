#!/bin/sh
set -eu
solution=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
install -d /app/wrenchlab
cp "$solution"/wrenchlab/*.py /app/wrenchlab/
