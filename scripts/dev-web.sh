#!/usr/bin/env bash
# Start the Next.js frontend (dev server).
set -euo pipefail
cd "$(dirname "$0")/.."
exec pnpm --filter @amv/web dev
