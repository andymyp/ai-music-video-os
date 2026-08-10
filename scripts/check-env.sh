#!/usr/bin/env bash
# Verify the Phase 00 toolchain. Run from the repo root (Git Bash on Windows).
set -euo pipefail

echo "== Tooling =="
for tool in python uv node pnpm ffmpeg ffprobe git; do
  if command -v "$tool" >/dev/null 2>&1; then
    echo "  [ok] $tool -> $("$tool" --version 2>&1 | head -1)"
  else
    echo "  [MISSING] $tool"
  fi
done

echo "== Temporal CLI =="
if command -v temporal >/dev/null 2>&1; then
  echo "  [ok] temporal -> $(temporal --version 2>&1 | head -1)"
else
  echo "  [MISSING] temporal (needed for 'temporal server start-dev')"
  echo "            install: winget install --id Temporal.TemporalCLI"
fi
