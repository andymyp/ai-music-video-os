#!/usr/bin/env bash
# Start the Temporal worker. Requires a running Temporal dev server.
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run amv-worker
