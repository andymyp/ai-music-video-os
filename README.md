# AI Music Video OS

Local-first, provider-agnostic, agent-driven **instrumental music video
production**. With one action (Genre or Trending + branding), the system
produces a complete content package:

- `master-16x9.mp4` — 1920×1080 long-form instrumental music video
- `short-9x16.mp4` — 1080×1920 short-form video
- `metadata.json` — titles / descriptions / hashtags for both outputs
- `production.json` — production manifest
- `qc-report.json` — quality-control report

All artifacts are stored locally.

> **Status:** Phase 00 (Project Foundation) in progress.
> See [docs/MASTER_EXECUTION.md](docs/MASTER_EXECUTION.md) for the execution plan.

## Documents (source of truth)

| Document                     | Purpose                                                      |
| ---------------------------- | ------------------------------------------------------------ |
| [docs/MAD.md](docs/MAD.md)   | Master Architecture Document (MAD-001) — what the system is. |
| [docs/PRD.md](docs/PRD.md)   | Product Requirements Document (PRD-001) — what the product must do. |
| [docs/TDD.md](docs/TDD.md)   | Technical Design Document (TDD-001) — how the system is designed. |
| [docs/MASTER_EXECUTION.md](docs/MASTER_EXECUTION.md) | Implementation plan and phase status. |

## Repository layout

```text
apps/
├── web/                      Next.js frontend
└── api/                      FastAPI backend + Temporal worker
packages/                     shared TS packages (contracts, types, config)
assets/                       reusable assets (radios, fonts, templates, overlays)
docs/                         architecture, requirements, execution plan
prompts/                      versioned AI prompts
infrastructure/               temporal + ffmpeg dev-environment notes
data/                         runtime data (database, productions, assets, cache, logs, temp)
scripts/                      developer / validation scripts
tests/                        integration / workflow / e2e suites
```

## Prerequisites

- Python 3.14 and [uv](https://docs.astral.sh/uv/)
- Node.js 20+ and [pnpm](https://pnpm.io/)
- FFmpeg and FFprobe on `PATH`
- Temporal CLI (`winget install --id Temporal.TemporalCLI`)
- Git

Verify with `scripts/check-env.sh`.

## Setup

```bash
# Python environment
uv sync                      # creates .venv and installs the backend

# Node environment
pnpm install                 # installs the web app and workspace packages

# optional local config
cp .env.example .env
```

## Running the stack

```bash
scripts/dev-temporal.sh      # Temporal dev server (port 7233, UI :8233)
scripts/dev-api.sh           # FastAPI backend (http://127.0.0.1:8000)
scripts/dev-web.sh           # Next.js frontend (http://localhost:3000)
scripts/dev-worker.sh        # Temporal worker
```

Backend health checks:

```text
GET http://127.0.0.1:8000/api/health          # liveness
GET http://127.0.0.1:8000/api/health/ready    # readiness (database)
GET http://127.0.0.1:8000/docs                # OpenAPI UI
```

## Validation

```bash
scripts/validate-phase-00.sh                  # Python imports, pytest, frontend build
scripts/run-temporal-smoke.sh                 # smoke workflow (needs server + worker)
```

## Testing

```bash
uv run pytest apps/api/tests -q               # backend unit tests
```

Testing layers (unit / integration / workflow / e2e) are defined in MAD-001
§57 and expanded as phases progress.

## Configuration

Configuration precedence (MAD-001 §93): defaults < `.env` < environment
variables < overrides. See `.env.example` for every supported key.
