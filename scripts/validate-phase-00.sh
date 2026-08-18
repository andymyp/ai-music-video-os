#!/usr/bin/env bash
# Phase 00 validation: Python imports, backend tests, frontend build.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== Python environment =="
uv run python -c "import fastapi, pydantic, sqlalchemy, temporalio; print('core imports ok')"

echo "== Backend tests =="
uv run pytest apps/api/tests -q

echo "== Frontend build =="
pnpm --filter @amv/web build
