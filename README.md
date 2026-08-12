# AI Music Video OS

Local-first, provider-agnostic, agent-driven **instrumental music video
production**. With one action — a Genre or Trending request plus optional
branding — the system orchestrates an agent pipeline to produce a complete,
publish-ready content package, stored entirely on your machine.

Every successful production outputs:

| Artifact | Purpose |
| --- | --- |
| `master-16x9.mp4` | 1920×1080 long-form instrumental music video |
| `short-9x16.mp4` | 1080×1920 short-form video |
| `metadata.json` | titles / descriptions / hashtags for both outputs |
| `production.json` | production manifest (full artifact catalogue) |
| `qc-report.json` | automated quality-control report |

**Status:** All 26 implementation phases complete (see
[docs/MASTER_EXECUTION.md](docs/MASTER_EXECUTION.md)).

## Documents (source of truth)

| Document | Purpose |
| --- | --- |
| [docs/MAD.md](docs/MAD.md) | Master Architecture Document (MAD-001) — what the system is. |
| [docs/PRD.md](docs/PRD.md) | Product Requirements Document (PRD-001) — what the product must do. |
| [docs/TDD.md](docs/TDD.md) | Technical Design Document (TDD-001) — how the system is designed. |
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

| Tool | Version | Install |
| --- | --- | --- |
| Python | 3.14+ | [python.org](https://www.python.org/) |
| [uv](https://docs.astral.sh/uv/) | latest | `pip install uv` or [installer](https://docs.astral.sh/uv/getting-started/installation/) |
| Node.js | 20+ | [nodejs.org](https://nodejs.org/) |
| [pnpm](https://pnpm.io/) | 10+ | `npm install -g pnpm` or [corepack](https://nodejs.org/api/corepack.html) |
| FFmpeg / FFprobe | latest | on `PATH` ([ffmpeg.org](https://ffmpeg.org/download.html)) |
| Temporal CLI | latest | `winget install --id Temporal.TemporalCLI` (Windows) / `brew install temporal` (macOS) / [docs](https://docs.temporal.io/cli) |
| Git | any | [git-scm.com](https://git-scm.com/) |

Run `pnpm check` any time to verify the toolchain on your platform.

## Getting started

### 1. Install dependencies

```bash
pnpm install
```

One command sets up the whole workspace:

- installs **Node** dependencies for the web app and shared packages,
- auto-runs `prepare`, which copies `.env.example` → `.env` (only if `.env`
  does not exist) and installs the **Python** backend via `uv sync`.

Run `pnpm prepare` on its own any time you need to re-bootstrap or refresh the
Python environment. It never overwrites an existing `.env`.

### 2. Configure

Edit `.env` to taste — environment profile, provider mode, ports, rendering
defaults, provider credentials. See [Configuration](#configuration) below.
Commands must be run from the repository root so the app finds `.env`.

### 3. Run the full stack

```bash
pnpm dev
```

Starts all four processes with prefixed, colorized output:

| Process | Address |
| --- | --- |
| Temporal dev server | gRPC `localhost:7233`, UI `http://localhost:8233` |
| FastAPI backend | `http://127.0.0.1:8000` |
| Temporal worker | — |
| Next.js frontend | `http://localhost:3000` |

Or start pieces individually:

```bash
pnpm dev:temporal   # Temporal dev server only
pnpm dev:api        # FastAPI backend only
pnpm dev:worker     # Temporal worker only
pnpm dev:web        # Next.js frontend only
pnpm dev:apps       # api + worker + web (assumes Temporal already running)
```

Backend endpoints while it runs:

```text
GET  http://127.0.0.1:8000/api/health          # liveness
GET  http://127.0.0.1:8000/api/health/ready    # readiness (database)
GET  http://127.0.0.1:8000/docs                # OpenAPI UI
```

### 4. Create a production

```bash
# Genre mode (instrumental lofi music video)
curl -s -X POST http://127.0.0.1:8000/api/productions \
  -H "Content-Type: application/json" \
  -d '{"mode": "genre", "genre": "lofi"}'

# Trending mode (the system researches a genre first)
curl -s -X POST http://127.0.0.1:8000/api/productions \
  -H "Content-Type: application/json" \
  -d '{"mode": "trending"}'
```

Poll `GET /api/productions/{id}` until the status is `completed`, then read the
final artifacts from `GET /api/productions/{id}/artifacts` or the local `data/`
directory. The frontend at `http://localhost:3000` provides a UI for the same
flow.

## Scripts reference

| Script | What it does |
| --- | --- |
| `pnpm prepare` | bootstrap: copy `.env.example` → `.env`, `uv sync` |
| `pnpm dev` | run the full stack (Temporal + API + worker + web) |
| `pnpm dev:api` / `dev:worker` / `dev:web` / `dev:temporal` | run one process |
| `pnpm dev:apps` | run API + worker + web (Temporal already up) |
| `pnpm build` | production build of the web app |
| `pnpm start` | serve the production web build |
| `pnpm test` | full backend suite (incl. Temporal end-to-end) |
| `pnpm test:fast` | backend suite without the end-to-end test |
| `pnpm check` | verify the toolchain (cross-platform) |
| `pnpm smoke` | smoke workflow (requires running server + worker) |

Unix-only equivalents of the `dev:*` scripts remain in [`scripts/`](scripts/).

## Testing

```bash
pnpm test        # everything
pnpm test:fast   # everything except the Temporal end-to-end test
```

Testing layers — unit / integration / workflow / e2e — are defined in
MAD-001 §57. The end-to-end test drives the whole pipeline through an
in-process Temporal server with the real media engines and asserts the
[MASTER §69](docs/MASTER_EXECUTION.md) final-output contract.

## Validation

```bash
pnpm check                          # toolchain health
scripts/validate-phase-26.sh        # full backend suite + frontend build + §42 checklist
pnpm smoke                          # smoke workflow (needs server + worker)
```

## Configuration

Configuration precedence (MAD-001 §93): **defaults < `.env` < environment
variables < overrides**. `.env.example` documents every supported key. Key
groups:

- **Environment / provider mode** — `APP_ENV`, `PROVIDER_MODE` (`mock` by
  default; `free`, `balanced`, `quality`, `custom` for real providers)
- **Servers** — `API_HOST`, `API_PORT`, `TEMPORAL_ADDRESS`, `TEMPORAL_TASK_QUEUE`
- **Storage** — `APP_DATA_DIR`, `DATABASE_URL`, `TEMP_DIR`
- **Rendering** — output dimensions, FPS, short-form duration
- **Resource limits** — `MAX_CONCURRENT_PRODUCTIONS`, `MAX_RENDER_WORKERS`
- **Provider credentials** — `OPENAI_API_KEY`, `GEMINI_API_KEY`, etc. Only
  needed once real providers are configured; leave unset for mock mode. Never
  commit real credentials — `.env` is git-ignored.
