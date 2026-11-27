#!/usr/bin/env bash
set -euo pipefail
mkdir -p /app/model /app/train
cp /opt/models/kev-0.8b/adapter_config.json /opt/models/kev-0.8b/adapter_model.safetensors /opt/models/kev-0.8b/head.pt /app/model/
cat > /app/REPORT.md <<'EOF'
# Baseline

`/app/model` is the released Kev-0.8B checkpoint, copied unchanged. No training was run.
EOF
echo "no training: the released checkpoint is delivered as is" > /app/train/README.md
