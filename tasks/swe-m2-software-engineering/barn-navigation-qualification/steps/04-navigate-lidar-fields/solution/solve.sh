#!/bin/sh
set -eu
solution_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
install -d /app/barn_qualification
cp "$solution_dir"/barn_qualification/*.py /app/barn_qualification/
