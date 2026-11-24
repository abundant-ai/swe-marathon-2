#!/bin/sh
set -eu
solution="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
mkdir -p /app/barn_qualification
cp "$solution"/barn_qualification/*.py /app/barn_qualification/
