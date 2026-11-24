#!/bin/sh
set -eu
solution_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
install -d /app/workcell
cp "$solution_dir"/workcell/*.py /app/workcell/
