#!/usr/bin/env bash
# Execute the Phase 00 smoke workflow (requires dev server + worker running).
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run python -m api.worker.smoke_client
