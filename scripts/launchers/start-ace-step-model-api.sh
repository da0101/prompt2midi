#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

echo "Starting ACE-Step model API at http://${ACESTEP_API_HOST:-127.0.0.1}:${ACESTEP_API_PORT:-8001}"
exec bash scripts/start-ace-step-api.sh
