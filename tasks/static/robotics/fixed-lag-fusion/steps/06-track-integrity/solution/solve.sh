#!/bin/sh
set -eu
solution=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
install -d /app/lagfusion
cp "$solution"/lagfusion/*.py /app/lagfusion/
