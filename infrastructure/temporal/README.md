# Temporal development environment

Temporal is the durable workflow engine (MAD-001 ADR-004, §9). The local
development server is provided by the Temporal CLI:

```bash
# one-time install (Windows)
winget install --id Temporal.TemporalCLI

# start the local dev server (downloads the server binary on first run)
scripts/dev-temporal.sh        # or: temporal server start-dev
```

The server listens on `127.0.0.1:7233` by default and exposes its Web UI on
`http://localhost:8233`.

## Worker

```bash
scripts/dev-worker.sh          # or: uv run amv-worker
```

The worker connects to `TEMPORAL_ADDRESS` (default `localhost:7233`) and polls
`TEMPORAL_TASK_QUEUE` (default `production`).

## Smoke test

With both the dev server and worker running:

```bash
scripts/run-temporal-smoke.sh  # prints SMOKE_RESULT=foundation-ok:phase-00
```

## Alternative: Docker

The full Temporal development cluster can be run with the
`temporalio/auto-setup` image. The CLI's `server start-dev` mode is preferred
for local development because it starts and manages the server in one process.
