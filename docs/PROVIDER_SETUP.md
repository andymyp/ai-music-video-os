# AI Music Video OS — Provider Setup Guide (User Edition)

**Version:** 0.1.0 (Phase 05)  
**Status:** Mock providers only — real providers coming in Phase 17+  
**For:** Users who want to run the app and configure AI providers  

---

## Quick Start: Run with Mock Providers (No Setup Required)

The app works **out of the box** with zero configuration. Mock providers generate valid audio/video files locally — no API keys, no accounts, no internet required.

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Start Temporal (required for production pipeline)
docker run --rm -p 7233:7233 temporalio/auto-setup:1.3

# 3. Start the API
cd apps/api && uv run amv-api

# 4. Start the worker (separate terminal)
uv run amv-worker

# 5. Create a production
curl -X POST http://localhost:8000/api/productions \
  -H "Content-Type: application/json" \
  -d '{"mode": "full", "genre": "synthwave", "branding_text": "My Video"}'
```

**Done.** You'll get a complete music video produced locally using deterministic mock providers.

---

## Understanding Provider Modes

The app has **5 provider modes** that control cost vs quality. Currently only `mock` works — real providers are not yet implemented.

| Mode | Cost | Quality | Best For | Status |
|------|------|---------|----------|--------|
| **mock** | $0 | Basic | Development, testing, CI/CD | ✅ Working |
| **free** | $0 | Good | Hobbyists, local models | 🔜 Phase 17+ |
| **balanced** | $10–50/mo | Very Good | Production use, best value | 🔜 Phase 17+ |
| **quality** | $100+/mo | Best | Commercial, premium output | 🔜 Phase 17+ |
| **custom** | Variable | You decide | Advanced users, mixed chains | 🔜 Phase 17+ |

**Current recommendation:** Use `mock` mode. It's the only working mode and produces complete videos for testing the pipeline.

---

## Configuration: Edit `.env`

Copy `.env.example` to `.env` and adjust these key settings:

```bash
# === REQUIRED: Choose your provider mode ===
PROVIDER_MODE=mock          # Options: mock | free | balanced | quality | custom

# === OPTIONAL: Environment profile ===
APP_ENV=development         # Options: development | test | mock | production

# === OPTIONAL: Resource limits (adjust for your hardware) ===
MAX_CONCURRENT_PRODUCTIONS=1   # How many videos at once (1 for 16GB RAM)
MAX_RENDER_WORKERS=1           # Render processes (1 for 16GB RAM)

# === OPTIONAL: Video output settings ===
MASTER_VIDEO_WIDTH=1920
MASTER_VIDEO_HEIGHT=1080
MASTER_VIDEO_FPS=30
SHORT_VIDEO_WIDTH=1080
SHORT_VIDEO_HEIGHT=1920
SHORT_VIDEO_DURATION_SECONDS=45
```

### When Real Providers Arrive (Phase 17+)

You'll add API keys to `.env` — **never commit this file**:

```bash
# === REAL PROVIDER KEYS (Phase 17+) ===
# Get keys from each provider's dashboard, then add here:
OPENAI_API_KEY=sk-...           # For GPT-4o, DALL-E 3, embeddings
GEMINI_API_KEY=...              # For Gemini Pro, Flash
GROQ_API_KEY=...                # For free/fast LLM (Llama, Mixtral)
CEREBRAS_API_KEY=...            # For ultra-fast LLM inference
OPENROUTER_API_KEY=...          # For 100+ models via one key
# SUNO_API_KEY=...              # For music generation
# UDIO_API_KEY=...              # For music generation
# FLUX_API_KEY=...              # For image generation
# TAVILY_API_KEY=...            # For trend research
```

---

## Recommended Provider Setup by Mode

### 🟢 Mock Mode (Current — Use This)

| Capability | Provider | Model | Why |
|------------|----------|-------|-----|
| LLM | Mock | `mock-llm` | Structured JSON output, deterministic |
| Music | Mock | `mock-music` | Instrumental WAV, sine tones |
| Image | Mock | `mock-image` | PNG textures, 5 aspect ratios |
| Vision | Mock | `mock-vision` | Image analysis (unused in pipeline) |
| Embedding | Mock | `mock-embedding` | 8-dim vectors (unused in pipeline) |
| Trend | Mock | `mock-trend` | Deterministic trend signals |

**No setup needed.** Just run the app.

---

### 🆓 Free Mode (Planned — Phase 17+)

| Capability | Recommended Provider | Model | Est. Cost |
|------------|---------------------|-------|-----------|
| LLM | **Groq** | `llama-3.1-70b-versatile` | Free tier |
| LLM | **Cerebras** | `llama-3.1-70b` | Free tier |
| LLM | **OpenRouter** | `meta-llama/llama-3.1-70b-instruct:free` | Free tier |
| Music | **Suno** | `chirp-v3` (free credits) | Free tier |
| Image | **Local SDXL** | `sdxl-base-1.0` (via ComfyUI) | $0 (your GPU) |
| Image | **Flux Schnell** | `flux-schnell` (local) | $0 (your GPU) |
| Trend | **Tavily** | Free tier (1000 req/mo) | Free tier |

**Setup:** Add `GROQ_API_KEY` or `OPENROUTER_API_KEY` to `.env`, set `PROVIDER_MODE=free`.

---

### ⚖️ Balanced Mode (Planned — Phase 17+) — **Recommended for Production**

| Capability | Recommended Provider | Model | Est. Monthly Cost |
|------------|---------------------|-------|-------------------|
| LLM | **OpenAI** | `gpt-4o-mini` | ~$5–15 |
| LLM | **Google** | `gemini-1.5-flash` | ~$2–10 |
| Music | **Suno** | `chirp-v3` | ~$10–30 |
| Music | **Udio** | `udio-130` | ~$10–30 |
| Image | **OpenAI** | `dall-e-3` | ~$10–40 |
| Image | **Flux** | `flux-pro` (via Replicate/Fal) | ~$10–30 |
| Trend | **Tavily** | Pro tier | ~$20–50 |

**Setup:** Add `OPENAI_API_KEY` + `GEMINI_API_KEY` to `.env`, set `PROVIDER_MODE=balanced`.

**Why this combo:** GPT-4o-mini + Gemini Flash gives you redundancy (failover) at low cost. Suno/Udio for music, DALL-E 3 or Flux for images.

---

### 🏆 Quality Mode (Planned — Phase 17+)

| Capability | Recommended Provider | Model | Est. Monthly Cost |
|------------|---------------------|-------|-------------------|
| LLM | **OpenAI** | `gpt-4o` | ~$50–200 |
| LLM | **Google** | `gemini-1.5-pro` | ~$30–150 |
| Music | **Suno** | `chirp-v3` (max quality) | ~$30–100 |
| Music | **Udio** | `udio-130` (max quality) | ~$30–100 |
| Image | **Flux** | `flux-pro` / `flux-1.1-pro` | ~$50–200 |
| Image | **Midjourney** | `v6.1` (via API wrapper) | ~$30–100 |
| Trend | **Tavily** | Enterprise | ~$100+ |

**Setup:** Add all premium keys, set `PROVIDER_MODE=quality`.

---

### 🔧 Custom Mode (Planned — Phase 17+)

Mix and match any providers. Example custom chain:

```bash
# .env
PROVIDER_MODE=custom
# LLM: Local Llama for privacy + OpenAI for complex reasoning
# Music: Udio for quality + Suno for variety
# Image: Local Flux for speed + Midjourney for final renders
```

You'll configure exact provider priorities in code (advanced).

---

## Provider Comparison Cheat Sheet

### LLM Providers (Creative Direction, Strategy, Metadata, QC)

| Provider | Best Model | Strengths | Weakness | Cost/1M tokens |
|----------|------------|-----------|----------|----------------|
| **OpenAI** | `gpt-4o-mini` | Best structured output, reliable | Cost adds up | $0.15/$0.60 |
| **OpenAI** | `gpt-4o` | Smartest, best reasoning | Expensive | $2.50/$10 |
| **Google** | `gemini-1.5-flash` | Fast, huge context, cheap | Less consistent JSON | $0.075/$0.30 |
| **Google** | `gemini-1.5-pro` | Best long-context | Slower | $1.25/$5 |
| **Groq** | `llama-3.1-70b` | Insane speed, free tier | Rate limited | Free |
| **Cerebras** | `llama-3.1-70b` | Fastest inference | Limited access | Free |
| **OpenRouter** | Multiple | One key, 100+ models | Extra hop latency | Varies |

**Recommendation:** `gpt-4o-mini` + `gemini-1.5-flash` (balanced) or `gpt-4o` + `gemini-1.5-pro` (quality)

---

### Music Providers (Instrumental Generation)

| Provider | Model | Strengths | Weakness | Cost |
|----------|-------|-----------|----------|------|
| **Suno** | `chirp-v3` | Best quality, vocals optional | No pure instrumental guarantee | ~$0.02/sec |
| **Udio** | `udio-130` | Great quality, tag control | Newer, less tested | ~$0.02/sec |
| **Local** | `MusicGen` / `AudioLDM` | Free, private | Lower quality, needs GPU | $0 |

**Critical:** The app **requires instrumental-only** output. Both Suno and Udio support this via tags/prompts.

**Recommendation:** Suno for reliability, Udio for variety. Use both with failover.

---

### Image Providers (Background Generation)

| Provider | Model | Strengths | Weakness | Cost |
|----------|-------|-----------|----------|------|
| **Flux** | `flux-pro` / `1.1-pro` | Best quality, prompt adherence | Cost | ~$0.04/img |
| **Flux** | `flux-schnell` | Fast, free (local) | Lower quality | Free (local) |
| **OpenAI** | `dall-e-3` | Reliable, consistent | Expensive, less control | $0.04–0.08/img |
| **Midjourney** | `v6.1` | Best artistic quality | No official API | ~$0.03/img (wrapper) |
| **SDXL** | `sdxl-base-1.0` | Free local, customizable | Needs GPU, setup work | Free (local) |

**Aspect ratios supported:** 16:9, 9:16, 1:1, 4:3, 3:4 (all providers)

**Recommendation:** Flux Pro for quality, Flux Schnell for speed/cost, DALL-E 3 for simplicity.

---

### Trend Providers (Creative Direction Research)

| Provider | Strengths | Cost |
|----------|-----------|------|
| **Tavily** | Real-time web search, structured results | $20–100/mo |
| **SerpAPI** | Google/Youtube/Spotify search | $50–200/mo |
| **Custom** | Your own data sources | Dev time |

**Recommendation:** Tavily — best API for trend discovery, reasonable price.

---

## Hardware Requirements by Mode

| Mode | GPU | RAM | Storage | Notes |
|------|-----|-----|---------|-------|
| **mock** | None | 8 GB+ | 5 GB | CPU only, fully local |
| **free** | 8 GB VRAM+ | 16 GB+ | 20 GB | For local SDXL/Flux/MusicGen |
| **balanced** | None (cloud) | 8 GB+ | 10 GB | All cloud APIs |
| **quality** | None (cloud) | 8 GB+ | 10 GB | All cloud APIs |
| **custom** | Optional | 16 GB+ | 50 GB+ | Mix of local + cloud |

**Minimum for local models (free mode):** RTX 3060 12GB / RTX 4060 8GB / M2 Mac 16GB unified

---

## Step-by-Step: Switching Modes (When Real Providers Exist)

### 1. Get API Keys

| Provider | Sign Up | Key Location |
|----------|---------|--------------|
| OpenAI | platform.openai.com | API Keys page |
| Google AI | aistudio.google.com | Get API Key |
| Groq | console.groq.com | API Keys |
| Cerebras | cloud.cerebras.ai | API Keys |
| OpenRouter | openrouter.ai | Keys |
| Suno | suno.com | API (waitlist) |
| Udio | udio.com | API (waitlist) |
| Fal.ai | fal.ai | API Keys (for Flux) |
| Replicate | replicate.com | API Token (for Flux) |
| Tavily | tavily.com | API Keys |

### 2. Add to `.env`

```bash
# Example balanced setup
PROVIDER_MODE=balanced
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...
SUNO_API_KEY=...
TWO_API_KEY=...  # for Flux via Fal/Replicate
TAVILY_API_KEY=...
```

### 3. Restart Services

```bash
# Stop worker (Ctrl+C), then restart
uv run amv-worker

# API auto-reloads in development mode
```

### 4. Verify

```bash
curl http://localhost:8000/api/health
# Should show: "provider_mode": "balanced"
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `PROVIDER_MODE=free` but still uses mock | Real providers not implemented yet (Phase 17+) |
| "Invalid secret reference" error | Ensure `.env` has `OPENAI_API_KEY=sk-...` not the key in config |
| Production fails at music generation | Check Suno/Udio API key, credits, and instrumental-only support |
| Out of memory on render | Reduce `MAX_CONCURRENT_PRODUCTIONS=1`, `MAX_RENDER_WORKERS=1` |
| Temporal connection failed | Ensure `docker run -p 7233:7233 temporalio/auto-setup:1.3` is running |
| Video quality looks bad | Increase `MASTER_VIDEO_WIDTH/HEIGHT`, check image provider quality |

---

## Current Limitations (Phase 05)

1. **Only `mock` mode works** — real provider adapters coming in Phase 17+
2. **No provider switching UI** — configure via `.env` only
3. **No cost tracking** — planned for Phase 17+
4. **No per-stage provider selection** — one provider per capability per production
5. **Trend/Vision/Embedding unused in pipeline** — only LLM, Music, Image are active

---

## Roadmap: When Real Providers Arrive

| Phase | Feature |
|-------|---------|
| **17** | OpenAI, Gemini, Groq LLM adapters |
| **17** | Suno, Udio music adapters |
| **17** | Flux, DALL-E 3, SDXL image adapters |
| **17** | Tavily trend adapter |
| **18** | Provider health monitoring UI |
| **18** | Cost tracking & budgets |
| **19** | Failover chains (auto-switch on error) |
| **20** | Custom provider plugin system |

---

## FAQ

**Q: Can I use this today without any API keys?**  
A: Yes! `PROVIDER_MODE=mock` works completely offline.

**Q: When will real providers work?**  
A: Phase 17+ (check `docs/MASTER_EXECUTION.md` for timeline).

**Q: Which mode should I use for my first real video?**  
A: Start with `mock` to verify the pipeline works, then `balanced` when real providers launch.

**Q: Can I run local models (Ollama, LM Studio) instead of cloud APIs?**  
A: Not yet. Local model adapters planned for Phase 17+ (free mode).

**Q: How much will it cost per video in balanced mode?**  
A: Rough estimate: $0.50–$2.00 per video (LLM ~$0.10, Music ~$0.30, Image ~$0.10, Trend ~$0.05).

**Q: Can I use different providers for different steps?**  
A: Not yet. One provider per capability per production. Custom chains coming later.

**Q: Is my API key safe?**  
A: Keys live only in `.env` (never committed) and process memory. The app validates they're env-var references, never literal values in config.

---

## File Reference

| File | Purpose |
|------|---------|
| `.env.example` | Template — copy to `.env` |
| `.env` | Your actual config (gitignored) |
| `apps/api/src/api/config/settings.py` | All config options with defaults |
| `apps/api/src/api/config/profiles.py` | Valid `APP_ENV` and `PROVIDER_MODE` values |

---

*Document version: 0.1.0 | For users running the app | Update when real providers launch (Phase 17+)*