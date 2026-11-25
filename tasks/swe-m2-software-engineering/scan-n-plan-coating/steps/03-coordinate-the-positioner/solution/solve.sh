#!/bin/sh
set -eu
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
app_dir=${COATING_APP_DIR:-/app}
install -d "$app_dir/coating_app"
install -m 0755 "$source_dir/coating" "$app_dir/coating"
install -m 0644 "$source_dir"/*.py "$app_dir/coating_app/"
