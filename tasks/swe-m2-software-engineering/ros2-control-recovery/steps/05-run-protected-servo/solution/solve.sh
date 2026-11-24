#!/bin/sh
set -eu
solution_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
install -d /app/control_recovery
cp "$solution_dir"/control_recovery/*.py /app/control_recovery/
