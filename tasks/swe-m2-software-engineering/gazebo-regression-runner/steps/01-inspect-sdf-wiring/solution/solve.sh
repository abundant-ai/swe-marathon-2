#!/bin/sh
set -eu
solution="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
mkdir -p /app/sim_regression
cp "$solution"/sim_regression/*.py /app/sim_regression/
