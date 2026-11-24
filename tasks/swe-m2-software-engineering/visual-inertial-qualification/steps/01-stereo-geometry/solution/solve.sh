#!/bin/sh
set -eu
solution=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
install -d /app/visqual
cp "$solution"/visqual/*.py /app/visqual/
