#!/bin/sh
set -eu
solution_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
install -d /app/control_recovery/native
cp "$solution_dir"/control_recovery/*.py /app/control_recovery/
cp -R "$solution_dir/native/fenced_drive" "$solution_dir/native/coupled_handover" /app/control_recovery/native/
