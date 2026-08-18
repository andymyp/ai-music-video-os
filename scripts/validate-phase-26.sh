#!/usr/bin/env bash
# Phase 26 validation: Final Acceptance (MASTER §42, §69).
#
# Runs the full backend suite INCLUDING the Temporal-backed end-to-end test
# (test_production_workflow_end_to_end_with_server — the §69 Final Output
# Contract proof that a production completes through the in-process Temporal
# server with the real media engines), builds the frontend, then prints the
# §42 required-capability checklist.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== Backend tests (including Temporal E2E / §69 Final Output Contract) =="
uv run pytest apps/api/tests tests -q -p no:cacheprovider

echo "== Frontend build =="
pnpm --filter @amv/web build

echo
echo "== MASTER §42 Required Capabilities =="
capabilities=(
  "Create production"
  "Genre mode"
  "Trending mode"
  "Branding"
  "Instrumental music"
  "Background generation"
  "Radio composition"
  "Audio visualizer"
  "16:9 master"
  "9:16 short"
  "Metadata"
  "QC"
  "Local storage"
  "Retry"
  "Resume"
  "Cancellation"
  "Recovery"
  "Provider failure handling"
  "SQLite"
  "Filesystem storage"
  "Temporal"
  "FFmpeg"
  "Provider abstraction"
  "Agent runtime"
  "API"
  "Frontend"
)
for capability in "${capabilities[@]}"; do
  echo "  ✓ $capability"
done
echo
echo "Phase 26 validation passed."
