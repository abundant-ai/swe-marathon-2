#!/usr/bin/env bash
set -euo pipefail
# the premise first: the sealed server answers, and gives a workspace, as the agent's own user sees it
curl -fsS -m 10 http://127.0.0.1:8080/api/health >/dev/null
curl -fsS -m 30 -X POST http://127.0.0.1:8080/api/workspaces >/dev/null
exec python3 "$(dirname "$0")/oracle.py"
