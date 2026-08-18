#!/usr/bin/env bash
# Phase 25 performance benchmark (MASTER §40, TDD-001 §145).
# Runs one mock-provider production through the real FFmpeg media engines and
# prints the performance budget (RAM/CPU/disk, FFmpeg renders, AI latency,
# workflow duration) to stdout.
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run python scripts/benchmark_performance.py "$@"
