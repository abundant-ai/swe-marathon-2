#!/bin/bash
set -euo pipefail
solution_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec /opt/application/bin/python "${solution_dir}/oracle.py" "$@"
