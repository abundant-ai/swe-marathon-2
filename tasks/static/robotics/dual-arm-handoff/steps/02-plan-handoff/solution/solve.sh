#!/bin/sh
set -eu
solution_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
install -d /app/dual_arm
cp "$solution_dir"/dual_arm/*.py /app/dual_arm/
