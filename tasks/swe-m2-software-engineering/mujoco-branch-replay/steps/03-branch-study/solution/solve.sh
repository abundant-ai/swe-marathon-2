#!/bin/sh
set -eu
solution_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
install -d /app/simbranch
cp "$solution_dir"/simbranch/*.py /app/simbranch/
