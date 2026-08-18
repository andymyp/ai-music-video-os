#!/usr/bin/env bash
# Start the FastAPI backend.
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run amv-api
