#!/usr/bin/env bash
# Start the local Temporal dev server (downloads the server on first run).
# See infrastructure/temporal/README.md for alternatives.
set -euo pipefail
exec temporal server start-dev
