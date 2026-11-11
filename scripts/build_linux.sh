#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
./scripts/prepare_runtime.sh
exec dx build --desktop -p xopilot --release "$@"
