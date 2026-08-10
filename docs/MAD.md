# MASTER ARCHITECTURE DOCUMENT

# AI Instrumental Music Video Production OS

**Document ID:** MAD-001
**Version:** 1.0.0
**Status:** Approved Architecture Baseline
**Date:** 2026-08-10
**Architecture Style:** Local-First, AI-Agentic, Workflow-Oriented, Provider-Agnostic
**Target Platform:** Windows 11 Pro
**Primary Development Hardware:** AMD Ryzen 5 7430U, 16 GB RAM

---

# 1. Executive Summary

The AI Instrumental Music Video Production OS is a local-first application that automates the production of instrumental music video content through specialized AI agents and deterministic media-processing pipelines.

The application requires minimal user input:

* Production mode: `Genre` or `Trending`
* Genre, when Genre mode is selected
* Branding text / watermark

After the user clicks **Generate**, the system automatically executes the entire production pipeline.

A single production generates:

1. One 16:9 long-form instrumental music video
2. One 9:16 short-form video
3. Metadata for both outputs:

   * title
   * description
   * hashtags

All final artifacts are stored in local storage.

The architecture is designed to be:

* Local-first
* Provider-agnostic
* Resumable
* Retryable
* Cost-aware
* Deterministic for media processing
* AI-driven for creative decisions
* Extensible
* Testable
* Suitable for free-tier and paid AI providers
* Suitable for future desktop packaging

---

# 2. Product Vision

The system enables users to create a complete instrumental music content package with a single production action.

The intended user experience is:

```text
User
 │
 ├── Select Genre / Trending
 ├── Enter Branding
 │
 ▼
Generate
 │
 ▼
AI automatically:
 │
 ├── Researches trends
 ├── Creates music strategy
 ├── Generates instrumental music
 ├── Creates visual strategy
 ├── Generates visual background
 ├── Analyzes audio
 ├── Generates audio visualizer data
 ├── Renders 16:9 master
 ├── Selects short segment
 ├── Renders 9:16 short
 ├── Generates metadata
 └── Performs quality control
 │
 ▼
Production Completed
 │
 ├── 16:9 Video
 ├── 9:16 Video
 └── Metadata
 │
 ▼
Local Storage
```

The system must minimize manual intervention while maintaining deterministic and inspectable production stages.

---

# 3. Core Architectural Principles

## 3.1 Local-First Architecture

The application database, production state, generated assets, cache, logs, and final media files are stored locally.

External services are used only when required for:

* LLM inference
* Music generation
* Image generation
* Trend research
* External APIs

The application must remain functional for local operations when network access is unavailable.

---

## 3.2 Provider-Agnostic Architecture

No agent may depend directly on a vendor-specific SDK.

Incorrect:

```text
Agent → OpenAI SDK
```

Correct:

```text
Agent
  ↓
Capability
  ↓
Provider Router
  ↓
Provider Adapter
  ↓
External Provider
```

Example:

```text
MusicGenerationAgent
  ↓
MusicGenerationCapability
  ↓
MusicProviderRouter
  ↓
Suno / Udio / MusicGen / Other Provider
```

This allows providers and models to be replaced without rewriting the agent layer.

---

## 3.3 AI for Decisions, Deterministic Code for Processing

AI should be used for tasks requiring reasoning or creative judgment:

* trend interpretation
* creative planning
* music strategy
* visual strategy
* metadata generation
* content evaluation

Deterministic software should be used for:

* audio analysis
* FFT
* visualizer generation
* video composition
* encoding
* scaling
* cropping
* watermarking
* file management
* hashing
* validation
* technical quality control

---

## 3.4 Resumable Workflows

Production may take several minutes or hours.

Every long-running stage must support:

* retries
* timeouts
* recovery
* resumption
* inspection
* partial completion

A failure in one stage must not require the entire production to restart.

Example:

```text
Generate Music
      ↓
Generate Visual
      ↓
Render Master
      ↓
FAILED
      ↓
Retry Render Master
```

The music and visual assets must not be regenerated unnecessarily.

---

## 3.5 Idempotency

Activities must be idempotent whenever practical.

For example:

```text
GenerateBackground(
    production_id,
    visual_prompt_hash
)
```

If the same artifact already exists and is valid:

```text
RETURN EXISTING_ARTIFACT
```

rather than generating it again.

---

## 3.6 Cost Awareness

Provider selection must consider:

```text
Quality
Cost
Latency
Availability
Rate Limit
Task Complexity
```

Simple tasks should use inexpensive or free providers.

Complex reasoning tasks may use premium providers.

---

## 3.7 No Unnecessary AI

AI must not be used where deterministic algorithms are superior.

For example:

```text
Audio
  ↓
FFT
  ↓
Frequency Analysis
  ↓
Visualizer
```

rather than:

```text
Audio
  ↓
AI
  ↓
Visualizer
```

---

# 4. System Scope

## 4.1 In Scope

### Production

* Production creation
* Genre mode
* Trending mode
* Branding configuration
* AI music strategy
* Instrumental music generation
* AI visual strategy
* Background generation
* Radio asset management
* Audio visualizer
* 16:9 rendering
* 9:16 rendering
* Short segment selection
* Metadata generation
* Quality control
* Local storage

### AI

* Trend research
* Trend scoring
* Creative planning
* Music concept generation
* Visual concept generation
* Metadata generation
* AI-assisted quality control

### Infrastructure

* Workflow orchestration
* Provider abstraction
* Local database
* Local asset storage
* Vector memory
* Logging
* Retry
* Recovery
* Cost tracking

---

# 5. Out of Scope for the Initial Release

The following are not part of the initial MVP:

* Automatic social media publishing
* YouTube account management
* TikTok account management
* Facebook publishing
* Instagram publishing
* Monetization analytics
* Multi-user collaboration
* Cloud asset storage
* SaaS billing
* Team permissions
* Advanced timeline editor
* Full manual video editing suite

The architecture must remain extensible enough to support these capabilities later.

---

# 6. High-Level Architecture

```text
┌──────────────────────────────────────────────────────────────┐
│                           USER                               │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                     NEXT.JS APPLICATION                      │
│                                                              │
│ Dashboard │ Productions │ Preview │ Settings │ Providers     │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                          FASTAPI                              │
│                                                              │
│ REST API │ Production API │ Asset API │ Config API            │
└────────────────┬─────────────────────────────┬───────────────┘
                 │                             │
                 ▼                             ▼
┌──────────────────────────────┐  ┌────────────────────────────┐
│           TEMPORAL           │  │       LOCAL DATABASE       │
│                              │  │                            │
│ Production Workflows         │  │ SQLite                     │
│ Activities                   │  │ SQLAlchemy                 │
│ Retry / Recovery             │  │                            │
└──────────────┬───────────────┘  └────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│                    AGENT ORCHESTRATION                       │
│                                                              │
│ Trend │ Music │ Visual │ Short │ Metadata │ QC              │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                      CAPABILITY LAYER                        │
│                                                              │
│ LLM │ Music │ Image │ Trend │ Embedding │ Vision             │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                       PROVIDER ROUTER                        │
│                                                              │
│ OpenAI │ Gemini │ Groq │ Cerebras │ OpenRouter                │
│ Suno │ Udio │ MusicGen │ Flux │ SDXL                         │
└──────────────────────────────────────────────────────────────┘

                         LOCAL MEDIA
                              │
              ┌───────────────┼────────────────┐
              ▼               ▼                ▼
           FFmpeg          Librosa          Filesystem
              │               │                │
              └───────────────┼────────────────┘
                              ▼
                       FINAL ARTIFACTS
```

---

# 7. Technology Stack

## 7.1 Frontend

```text
Next.js 16
React 19
TypeScript
Tailwind CSS
shadcn/ui
Zustand
TanStack Query
```

Responsibilities:

* User interface
* Production creation
* Production progress
* Asset preview
* Metadata display
* Settings
* Provider configuration

The frontend must not contain core production logic.

---

# 8. Backend

```text
Python 3.14
FastAPI
Pydantic v2
SQLAlchemy 2
Alembic
httpx
asyncio
```

Responsibilities:

* REST API
* Application services
* Workflow triggering
* Configuration management
* Asset management
* Provider management
* Database access

---

# 9. Workflow Engine

The primary workflow engine is:

```text
Temporal
```

The primary workflow is:

```text
ProductionWorkflow
```

Activities include:

```text
ResearchTrendActivity
CreateMusicStrategyActivity
GenerateMusicActivity
CreateVisualStrategyActivity
GenerateBackgroundActivity
AnalyzeAudioActivity
CreateVisualizerActivity
RenderMasterActivity
SelectShortSegmentActivity
RenderShortActivity
GenerateMetadataActivity
QualityCheckActivity
FinalizeProductionActivity
```

Temporal owns workflow state, retries, timeouts, and recovery.

---

# 10. Database Architecture

Primary database:

```text
SQLite
```

ORM:

```text
SQLAlchemy 2
```

Migration:

```text
Alembic
```

SQLite stores:

* production metadata
* workflow state references
* asset metadata
* provider information
* configuration
* trend snapshots
* quality reports
* cost information

Large binary files must not be stored inside SQLite.

---

# 11. Storage Architecture

Recommended application data directory:

```text
ai-music-video-os/
├── database/
│   └── app.db
│
├── productions/
│   └── <production_id>/
│       ├── production.json
│       │
│       ├── research/
│       │   ├── trends.json
│       │   └── trend-report.json
│       │
│       ├── music/
│       │   ├── strategy.json
│       │   ├── source/
│       │   ├── normalized/
│       │   └── master.wav
│       │
│       ├── visual/
│       │   ├── strategy.json
│       │   ├── background/
│       │   ├── radio/
│       │   └── visualizer/
│       │
│       ├── render/
│       │   ├── master-16x9.mp4
│       │   └── short-9x16.mp4
│       │
│       ├── metadata/
│       │   └── metadata.json
│       │
│       └── qc/
│           └── report.json
│
├── assets/
│   ├── radios/
│   ├── fonts/
│   ├── templates/
│   └── overlays/
│
├── cache/
├── logs/
└── temp/
```

---

# 12. Production Entity

A `Production` is the root business entity.

Example:

```json
{
  "id": "prod_01JXYZ",
  "mode": "genre",
  "genre": "lofi",
  "branding_text": "MY MUSIC CHANNEL",
  "status": "completed",
  "created_at": "2026-08-10T08:00:00Z"
}
```

Once generation begins, the creative input must be treated as immutable for that production version.

---

# 13. Production State Machine

```text
CREATED
   │
   ▼
PLANNING
   │
   ▼
CONCEPT_READY
   │
   ▼
GENERATING_MUSIC
   │
   ▼
MUSIC_READY
   │
   ▼
GENERATING_VISUAL
   │
   ▼
VISUAL_READY
   │
   ▼
ANALYZING_AUDIO
   │
   ▼
RENDERING_MASTER
   │
   ▼
MASTER_READY
   │
   ▼
SELECTING_SHORT
   │
   ▼
RENDERING_SHORT
   │
   ▼
SHORT_READY
   │
   ▼
GENERATING_METADATA
   │
   ▼
QUALITY_CHECK
   │
   ▼
COMPLETED
```

Any stage may transition to:

```text
FAILED
```

A failed production must support retry and resume.

---

# 14. User Flow

## 14.1 Create Production

The user selects:

```text
New
```

The application displays:

```text
Production Mode

( ) Genre
( ) Trending

Genre:
[ Lo-Fi ▼ ]

Branding:
[ MY MUSIC CHANNEL ]

[ Generate ]
```

When Trending mode is selected, the Genre field is hidden or disabled.

---

# 15. Trending Architecture

Trending mode must not simply select a popular genre.

It must identify a current content opportunity.

Pipeline:

```text
Trend Discovery
      ↓
Trend Collection
      ↓
Trend Normalization
      ↓
Trend Scoring
      ↓
AI Trend Interpretation
      ↓
Music Concept
      ↓
Visual Concept
```

Potential signal sources include:

* YouTube
* Google Trends
* TikTok signals
* Spotify signals
* Reddit
* other publicly available trend signals

Each source must be implemented through a provider adapter.

Availability, API access, rate limits, and licensing requirements must be verified before implementation.

---

# 16. Trend Scoring Engine

The initial scoring model is:

```text
TrendScore =
    0.30 × Growth
  + 0.25 × Volume
  + 0.20 × CrossPlatform
  + 0.15 × Recency
  + 0.10 × ContentFit
```

Weights must be configurable.

Example output:

```json
{
  "genre": "lofi",
  "score": 89.4,
  "confidence": 0.91,
  "signals": [],
  "reasoning": ""
}
```

The scoring engine provides structured evidence.

The AI agent interprets the evidence and produces the final creative recommendation.

---

# 17. Music Strategy Agent

Input:

```text
genre
trend data
target format
creative history
```

Output:

```json
{
  "genre": "lofi",
  "mood": "late night cozy",
  "bpm_range": [70, 85],
  "key": "A minor",
  "instruments": [
    "Rhodes piano",
    "soft drums",
    "warm bass"
  ],
  "structure": "continuous instrumental mix",
  "vocal_policy": "none",
  "duration_target_minutes": 60
}
```

Hard requirements:

```text
VOCALS = FORBIDDEN
LYRICS = FORBIDDEN
SINGING = FORBIDDEN
```

The system is explicitly designed for instrumental content.

---

# 18. Music Generation Architecture

```text
Music Strategy
      │
      ▼
MusicGenerationCapability
      │
      ▼
MusicProviderRouter
      │
      ├── Provider A
      ├── Provider B
      └── Provider C
```

Potential providers include:

* Suno
* Udio
* MusicGen
* other compliant music-generation providers

Before production use, every provider must be evaluated for:

* commercial usage rights
* API availability
* output licensing
* duration limitations
* rate limits
* pricing
* reliability

---

# 19. Music Normalization

Generated audio must be normalized before rendering.

Pipeline:

```text
Generated Audio
      ↓
Format Validation
      ↓
Sample Rate Normalization
      ↓
Channel Normalization
      ↓
Loudness Normalization
      ↓
Silence Detection
      ↓
Audio Master
```

Primary tools:

```text
FFmpeg
FFprobe
librosa
NumPy
```

---

# 20. Visual Strategy Agent

Input:

```text
genre
mood
music concept
branding
```

Output:

```json
{
  "theme": "rainy late-night bedroom",
  "palette": [],
  "environment": "cozy bedroom",
  "lighting": "warm lamp + blue night",
  "era": "modern",
  "style": "cinematic illustration",
  "radio_style": "vintage"
}
```

The visual strategy must reserve a suitable central area for the radio.

---

# 21. Background Generation

The preferred visual architecture uses a static background image.

Requirements:

```text
16:9 composition
High resolution
No text
No logos
No unwanted watermark
Suitable central composition
Consistent lighting
Loop-friendly composition
```

The radio is preferably a separate reusable asset.

---

# 22. Radio Asset System

Radio assets are reusable.

```text
assets/radios/
├── vintage-radio.png
├── wooden-radio.png
├── cyberpunk-radio.png
└── classic-radio.png
```

Selection flow:

```text
Visual Strategy
      ↓
Radio Style
      ↓
Asset Registry
      ↓
Existing Asset?
   /       \
 YES       NO
  │         │
Use      Generate
```

This reduces generation cost and improves visual consistency.

---

# 23. Audio Visualizer

The audio visualizer is deterministic.

Pipeline:

```text
Master Audio
      ↓
FFT
      ↓
Frequency Bands
      ↓
Normalized Values
      ↓
Visualizer Data
      ↓
Video Renderer
```

Suggested frequency groups:

```text
Bass
Low-Mid
Mid
High-Mid
High
```

Example configuration:

```json
{
  "style": "bars",
  "sensitivity": 0.8,
  "smoothing": 0.7,
  "position": "radio-center"
}
```

The visualizer must be synchronized with the actual audio.

---

# 24. 16:9 Master Video

Target resolution:

```text
1920 × 1080
```

Pipeline:

```text
Background
+
Radio
+
Visualizer
+
Branding
+
Audio
      ↓
FFmpeg
      ↓
16:9 Master Video
```

Initial recommended defaults:

```text
Aspect Ratio: 16:9
Resolution: 1920×1080
FPS: 30
Video Codec: H.264
Audio Codec: AAC
```

All encoding parameters must remain configurable.

---

# 25. Short Video Strategy

The short video is derived from the same production but uses a dedicated vertical composition.

It must not simply crop the 16:9 master.

Pipeline:

```text
Master Audio
      ↓
Short Selection Agent
      ↓
Best Segment
      ↓
Vertical Composition
      ↓
9:16 Renderer
```

Target:

```text
1080 × 1920
```

Initial target duration:

```text
30–60 seconds
```

Platform-specific duration rules must remain configurable.

---

# 26. Short Selection Agent

The agent may consider:

```text
Audio energy
Melodic changes
Musical peaks
Transitions
Intro/outro suitability
Standalone listening quality
```

Example output:

```json
{
  "start": 184.2,
  "duration": 45,
  "reason": "Strong melodic section with high energy"
}
```

The final segment must be validated before rendering.

---

# 27. Vertical Composition

The short uses a dedicated layout:

```text
┌──────────────────┐
│                  │
│    Background    │
│                  │
│     ┌──────┐     │
│     │ RADIO│     │
│     │ WAVE │     │
│     └──────┘     │
│                  │
│     BRANDING     │
│                  │
└──────────────────┘
```

The vertical composition must preserve the same visual identity as the master video.

---

# 28. Branding System

User input:

```text
branding_text
```

Example:

```text
MY MUSIC CHANNEL
```

Branding configuration:

```json
{
  "text": "MY MUSIC CHANNEL",
  "position": "bottom-right",
  "opacity": 0.65,
  "font_size": 28
}
```

Branding must be rendered into:

* 16:9 master
* 9:16 short

Branding configuration is immutable for a production run.

---

# 29. Metadata Agent

Metadata generation uses:

```text
Genre
Mood
Music Concept
Visual Concept
Trend Context
Target Audience
Production Format
```

Output:

```json
{
  "master": {
    "title": "",
    "description": "",
    "hashtags": []
  },
  "short": {
    "title": "",
    "description": "",
    "hashtags": []
  }
}
```

Metadata is generated separately for the master and short because their optimization requirements differ.

---

# 30. Metadata Quality Rules

## Title

Must be:

* descriptive
* natural
* searchable
* relevant
* non-misleading
* free from keyword stuffing

## Description

Must:

* accurately describe the content
* identify the instrumental nature
* reflect the actual mood/theme
* avoid fabricated claims

## Hashtags

Must be:

* relevant
* limited
* non-spammy
* related to the actual content

---

# 31. Quality Control Architecture

Quality control consists of deterministic checks and AI-assisted checks.

## 31.1 Deterministic Checks

```text
File exists
File readable
Duration valid
Resolution valid
FPS valid
Codec valid
Audio stream exists
Video stream exists
No zero-byte files
No corrupted frames
Branding exists
```

## 31.2 AI-Assisted Checks

```text
Visual coherence
Music/visual theme consistency
Metadata quality
Possible vocal presence
Creative duplication
```

Deterministic checks must always run before AI-assisted checks.

---

# 32. QC Failure Handling

Example:

```text
RenderMaster
      ↓
QC
      ↓
FAILED
      ↓
Reason:
"Branding missing"
      ↓
Retry RenderMaster
```

The system must retry only the affected stage whenever possible.

---

# 33. Agent Architecture

Primary agents:

```text
Orchestrator Agent
Trend Research Agent
Music Strategy Agent
Music Generation Agent
Visual Strategy Agent
Visual Generation Agent
Short Selection Agent
Metadata Agent
Quality Control Agent
```

Agents must not perform low-level media processing.

---

# 34. Agent Responsibilities

## Orchestrator Agent

Responsible for high-level production decisions and coordination.

It must not:

* execute FFmpeg directly
* write arbitrary files
* access the database directly
* call vendor SDKs directly

---

## Trend Research Agent

Interprets structured trend signals and identifies promising creative opportunities.

---

## Music Strategy Agent

Creates the structured music blueprint.

---

## Music Generation Agent

Uses `MusicGenerationCapability` to generate or request instrumental music.

---

## Visual Strategy Agent

Creates the structured visual blueprint.

---

## Visual Generation Agent

Uses `ImageGenerationCapability` to produce visual assets.

---

## Short Selection Agent

Identifies the strongest segment for short-form content.

---

## Metadata Agent

Generates platform-ready metadata.

---

## Quality Control Agent

Evaluates creative and technical quality.

---

# 35. Capability Architecture

Capabilities form the abstraction layer between agents and providers.

Core capabilities:

```text
LLMCapability
MusicGenerationCapability
ImageGenerationCapability
TrendResearchCapability
EmbeddingCapability
VisionCapability
```

Agents depend on capabilities, never concrete providers.

---

# 36. Provider Architecture

```text
ProviderRegistry
      │
      ├── LLM Providers
      │   ├── OpenAI
      │   ├── Gemini
      │   ├── Groq
      │   ├── Cerebras
      │   └── OpenRouter
      │
      ├── Music Providers
      │   ├── Suno
      │   ├── Udio
      │   └── MusicGen
      │
      └── Image Providers
          ├── Gemini
          ├── Flux
          └── SDXL
```

Provider implementations must not contain business logic.

---

# 37. Provider Routing

Provider selection is policy-driven.

Example:

```json
{
  "task": "metadata_generation",
  "preferred": [
    "gemini",
    "groq",
    "cerebras"
  ],
  "fallback": [
    "openai"
  ]
}
```

Complex reasoning may use:

```json
{
  "task": "trend_analysis",
  "preferred": [
    "openai",
    "gemini"
  ]
}
```

The exact model/provider configuration must remain externalized and configurable.

---

# 38. Recommended AI Provider Strategy

## LLM

Primary candidates:

* Gemini
* OpenAI

Low-cost/free-tier candidates:

* Gemini free tier
* Groq
* Cerebras
* OpenRouter models
* local Ollama models

## Music

Candidates:

* Suno
* Udio
* MusicGen
* other commercially compliant providers

## Image

Candidates:

* Gemini
* Flux
* SDXL

All providers must be evaluated for current availability, commercial licensing, pricing, rate limits, and API access before being selected for production.

---

# 39. Local AI

Optional local AI runtime:

```text
Ollama
```

Use cases:

* offline fallback
* simple classification
* metadata generation
* development
* testing

The local hardware is not considered sufficient for large-scale local music and image generation.

---

# 40. Vector Memory

Use:

```text
LanceDB
```

Potential collections:

```text
production_embeddings
music_concepts
visual_concepts
trend_history
metadata_history
```

Use cases:

* semantic duplicate detection
* creative similarity
* historical context
* style consistency
* content memory

---

# 41. Deduplication

The system should use multiple layers.

## Binary Deduplication

```text
SHA-256
```

## Visual Deduplication

```text
Perceptual Hash
```

## Semantic Deduplication

```text
Embedding Similarity
```

## Audio Deduplication

Audio fingerprinting may be used to detect reused or highly similar music.

---

# 42. Caching Architecture

Cache high-cost or deterministic results:

```text
Trend Results
LLM Strategy Results
Generated Images
Music Generation Metadata
Audio Analysis
Embeddings
FFprobe Results
```

Cache keys should be deterministic.

Recommended:

```text
hash(
    provider,
    model,
    prompt,
    input,
    configuration
)
```

---

# 43. Resource Management

Target development hardware:

```text
AMD Ryzen 5 7430U
16 GB RAM
Integrated Radeon Graphics
Windows 11 Pro
```

The application must:

* limit parallel FFmpeg processes
* limit workflow concurrency
* use temporary files
* avoid loading large media files into RAM
* stream media where possible
* clean up temporary artifacts

Initial default:

```text
Maximum active production renders: 1
```

This can be increased after performance profiling.

---

# 44. Temporary Storage

Temporary files are stored under:

```text
temp/
```

Temporary artifacts must have a lifecycle.

After successful production:

Retain:

* final assets
* required intermediate assets
* metadata
* manifests
* QC reports

Delete where possible:

* temporary encoding files
* download fragments
* unused intermediate renders
* failed transient artifacts

Cleanup must be configurable and safe.

---

# 45. API Architecture

The application exposes a REST API.

Example endpoints:

```text
POST   /api/productions
GET    /api/productions
GET    /api/productions/:id
POST   /api/productions/:id/cancel
POST   /api/productions/:id/retry
GET    /api/productions/:id/progress

GET    /api/assets/:id
GET    /api/assets/:id/download

GET    /api/providers
GET    /api/settings
PUT    /api/settings
```

The API must never synchronously execute long-running production tasks.

Instead:

```text
Validate
  ↓
Persist
  ↓
Start Workflow
  ↓
Return
```

---

# 46. Real-Time Progress

The frontend requires production progress updates.

Preferred initial implementation:

```text
Server-Sent Events (SSE)
```

Example event:

```json
{
  "production_id": "prod_001",
  "stage": "rendering_master",
  "progress": 0.64,
  "message": "Rendering master video"
}
```

WebSockets may be introduced later if required.

---

# 47. Security

The local architecture must still enforce security boundaries.

Requirements:

* API keys must never be committed to source control
* secrets must not be stored as plaintext application data
* filesystem paths must be validated
* filenames must be sanitized
* arbitrary shell commands must not be accepted
* FFmpeg arguments must be generated from validated parameters
* agents must not access secrets directly
* agents must use registered tools only

---

# 48. Secret Management

Development:

```text
.env
```

Production desktop builds should use an OS-supported secure credential mechanism where practical.

Potential environment variables:

```text
OPENAI_API_KEY
GEMINI_API_KEY
GROQ_API_KEY
CEREBRAS_API_KEY
OPENROUTER_API_KEY
...
```

Secrets must never be hard-coded.

---

# 49. Logging

Logging must be structured.

Each production-related log should include, where applicable:

```text
timestamp
level
production_id
workflow_id
activity
provider
model
duration
status
error
```

Example:

```json
{
  "level": "INFO",
  "production_id": "prod_001",
  "activity": "GenerateMusic",
  "provider": "music_provider",
  "duration_ms": 124000,
  "status": "success"
}
```

---

# 50. Observability

The system should track:

```text
production_duration
stage_duration
provider_latency
provider_failure_rate
generation_cost
retry_count
render_duration
storage_usage
```

For the local MVP, these metrics may be stored in SQLite.

---

# 51. Error Taxonomy

Errors should be categorized:

```text
ProviderError
RateLimitError
AuthenticationError
TimeoutError
ValidationError
MediaProcessingError
StorageError
WorkflowError
QualityCheckError
ConfigurationError
```

Retry behavior depends on the error category.

---

# 52. Retry Policy

Retryable:

```text
Temporary network failure
Timeout
Temporary provider failure
Rate limit
Transient infrastructure failure
```

Not automatically retryable:

```text
Invalid API key
Invalid user configuration
Unsupported format
Invalid input
Permanent provider error
```

Exponential backoff must be used for retryable provider failures.

---

# 53. Cost Tracking

Every external AI request should record:

```text
provider
model
input units
output units
estimated cost
currency
timestamp
production_id
```

Where provider pricing information is available.

The UI should eventually display:

```text
Estimated Production Cost: $0.00
```

or:

```text
Estimated Production Cost: $0.42
```

---

# 54. Production Manifest

Every production must have a manifest.

Example:

```json
{
  "production_id": "prod_001",
  "version": 1,
  "input": {},
  "concept": {},
  "assets": {},
  "renders": {},
  "metadata": {},
  "qc": {},
  "providers": {},
  "created_at": "",
  "completed_at": ""
}
```

The manifest provides traceability and reproducibility.

---

# 55. Versioning

Creative and technical configurations must be versioned.

Examples:

```text
production_version = 1
music_strategy_version = 1
visual_strategy_version = 1
metadata_version = 1
render_profile_version = 1
```

Existing production outputs must not silently change when configuration defaults are updated.

---

# 56. Rendering Profiles

Rendering configuration must be externalized.

Initial profiles:

```text
youtube_master
youtube_short
preview
thumbnail
```

Example:

```json
{
  "name": "youtube_master",
  "width": 1920,
  "height": 1080,
  "fps": 30,
  "video_codec": "libx264",
  "audio_codec": "aac"
}
```

---

# 57. Testing Strategy

## 57.1 Unit Tests

Test:

* trend scoring
* provider routing
* metadata validation
* state transitions
* storage
* hashing
* visualizer calculations
* configuration validation

## 57.2 Integration Tests

Test:

* FastAPI + SQLite
* Temporal workflows
* provider adapters
* FFmpeg
* asset lifecycle

## 57.3 End-to-End Tests

Test the complete flow:

```text
New
 ↓
Generate
 ↓
Production
 ↓
Render
 ↓
Metadata
 ↓
QC
 ↓
Completed
```

---

# 58. Mock Providers

Development must not require paid external APIs.

Implement:

```text
MockLLMProvider
MockMusicProvider
MockImageProvider
MockTrendProvider
```

Mock providers must generate deterministic artifacts.

Examples:

```text
mock-music.wav
mock-background.png
mock-metadata.json
```

This enables complete workflow testing without API cost.

---

# 59. Development Modes

## Mock Mode

No external AI providers.

```text
All providers mocked
```

## Free Mode

Only free-tier or local providers.

## Balanced Mode

Free and low-cost providers.

## Quality Mode

Premium providers.

## Custom Mode

User-defined provider routing.

---

# 60. Recommended Repository Structure

```text
ai-music-video-os/
│
├── apps/
│   ├── web/
│   │   ├── app/
│   │   ├── components/
│   │   ├── features/
│   │   ├── hooks/
│   │   ├── stores/
│   │   └── lib/
│   │
│   └── api/
│       ├── src/
│       │   ├── api/
│       │   ├── agents/
│       │   ├── capabilities/
│       │   ├── providers/
│       │   ├── workflows/
│       │   ├── activities/
│       │   ├── media/
│       │   ├── database/
│       │   ├── storage/
│       │   ├── config/
│       │   └── core/
│       │
│       └── tests/
│
├── packages/
│   ├── contracts/
│   ├── types/
│   └── config/
│
├── assets/
├── docs/
├── prompts/
├── scripts/
├── tests/
│
├── .env.example
├── pyproject.toml
├── package.json
├── pnpm-workspace.yaml
└── README.md
```

---

# 61. Core Backend Modules

```text
core/
├── errors.py
├── events.py
├── ids.py
├── hashing.py
└── clock.py
```

```text
agents/
├── orchestrator/
├── trend/
├── music/
├── visual/
├── short/
├── metadata/
└── qc/
```

```text
capabilities/
├── llm/
├── music/
├── image/
├── trend/
├── embedding/
└── vision/
```

```text
providers/
├── openai/
├── gemini/
├── groq/
├── cerebras/
├── openrouter/
├── suno/
├── udio/
├── musicgen/
├── flux/
└── sdxl/
```

---

# 62. Dependency Direction

Dependencies must point inward toward abstractions.

```text
API
 ↓
Application Services
 ↓
Agents / Workflows
 ↓
Capabilities
 ↓
Provider Interfaces
 ↓
Provider Implementations
```

Providers must never depend on business logic.

Agents must never depend on vendor SDK details.

---

# 63. Core Domain Model

Core entities:

```text
Production
ProductionRun
ProductionStage
Asset
AudioTrack
VisualAsset
Render
Metadata
TrendSnapshot
Provider
AgentRun
QualityReport
```

---

# 64. Production Relationships

```text
Production
 │
 ├── ProductionRun
 │
 ├── Assets
 │    ├── Audio
 │    ├── Image
 │    └── Video
 │
 ├── Metadata
 │
 ├── TrendSnapshot
 │
 └── QualityReport
```

---

# 65. Asset Lifecycle

```text
REQUESTED
    ↓
GENERATING
    ↓
DOWNLOADING
    ↓
VALIDATING
    ↓
READY
```

Failure state:

```text
FAILED
```

Every asset should contain:

```text
id
type
path
hash
size
mime_type
created_at
provider
status
```

---

# 66. AI Prompt Architecture

Prompts must not be scattered throughout source code.

Recommended structure:

```text
prompts/
├── trend/
├── music/
├── visual/
├── metadata/
└── qc/
```

Prompts must be versioned.

Examples:

```text
music_strategy_v1
visual_strategy_v1
metadata_v1
```

---

# 67. Structured AI Output

Every AI agent that communicates with application logic must return structured data.

Required flow:

```text
LLM
 ↓
JSON Schema
 ↓
Pydantic Validation
 ↓
Domain Object
```

Invalid responses must trigger controlled repair/retry behavior.

---

# 68. Agent Guardrails

Agents must never:

* execute arbitrary shell commands
* write arbitrary files
* access secrets
* modify the database directly
* modify provider configuration without authorization
* delete productions without explicit application-level authorization

Agents may only use registered tools.

---

# 69. Tool Architecture

Agents may access tools such as:

```text
TrendSearchTool
ProviderTool
AssetSearchTool
AudioAnalysisTool
RenderTool
MetadataTool
QCInspectionTool
```

Each tool must have a strict input/output schema.

---

# 70. Workflow vs. Agent Responsibilities

Workflow determines:

```text
WHEN
WHAT ORDER
RETRY
TIMEOUT
STATE
```

Agent determines:

```text
WHAT SHOULD WE CREATE?
WHAT SHOULD WE CHOOSE?
WHAT IS BETTER?
```

Example:

```text
Temporal:
Generate Music
 → Wait
 → Validate
 → Render
```

Agent:

```text
Choose the most appropriate music concept.
```

---

# 71. Concurrency

Initial MVP:

```text
1 active production render
```

The architecture must support multiple productions later.

Concurrency should be constrained by:

* CPU
* RAM
* disk
* provider rate limits
* API quotas

---

# 72. Local Resource Manager

A future component:

```text
LocalResourceManager
```

may manage:

```text
CPU usage
RAM usage
FFmpeg workers
Disk availability
Provider concurrency
```

This is especially important for the target 16 GB RAM system.

---

# 73. Disk Safety

Before starting a production:

```text
Check available disk space
```

If insufficient:

```text
BLOCK PRODUCTION
```

Required disk space should account for:

* source audio
* generated audio
* temporary files
* video encoding
* final video
* intermediate artifacts

---

# 74. Performance Strategy

The application must never load an entire long-form video into RAM unnecessarily.

Use:

```text
FFmpeg streaming
Chunked processing
Temporary files
Incremental analysis
```

Audio analysis should support chunk-based processing.

---

# 75. Offline Behavior

When offline, the application should still support:

* opening the dashboard
* viewing existing productions
* viewing metadata
* previewing local videos
* deterministic media processing
* deterministic QC

AI-dependent stages should transition into:

```text
WAITING_FOR_NETWORK
```

rather than failing the entire production.

---

# 76. Provider Failure Strategy

Example:

```text
Gemini
  ↓
Rate Limited
  ↓
Provider Router
  ↓
Groq
  ↓
Success
```

If all eligible providers fail:

```text
WAITING_FOR_PROVIDER
```

The production should remain recoverable.

---

# 77. Music Provider Failover

Example:

```text
Music Provider A
      ↓
Failure
      ↓
Music Provider B
      ↓
Success
      ↓
Audio Normalization
```

Provider-specific output differences must be normalized before entering the next stage.

---

# 78. Visual Provider Failover

Example:

```text
Image Provider A
      ↓
Failure
      ↓
Image Provider B
      ↓
Success
```

The generated image must still satisfy:

* required aspect ratio
* required resolution
* central radio composition
* no unwanted text
* visual strategy constraints

---

# 79. Quality Gates

Each major stage has a quality gate.

```text
Music Generated
      ↓
Music Gate
      ↓
Visual Generated
      ↓
Visual Gate
      ↓
Master Rendered
      ↓
Master Gate
      ↓
Short Rendered
      ↓
Short Gate
      ↓
Metadata Generated
      ↓
Final QC
```

---

# 80. Production Completion Criteria

A production is `COMPLETED` only when:

```text
✓ Music is valid
✓ Visual assets are valid
✓ 16:9 master is valid
✓ 9:16 short is valid
✓ Metadata is valid
✓ Branding is present
✓ QC passed
✓ Production manifest exists
```

---

# 81. Final Output Contract

The final production directory must provide:

```text
production/
├── master-16x9.mp4
├── short-9x16.mp4
├── metadata.json
├── production.json
└── qc-report.json
```

---

# 82. Metadata Contract

```json
{
  "master": {
    "title": "",
    "description": "",
    "hashtags": []
  },
  "short": {
    "title": "",
    "description": "",
    "hashtags": []
  }
}
```

---

# 83. Future Extensibility

The architecture should support future agents such as:

```text
Thumbnail Agent
Caption Agent
Publishing Agent
YouTube Agent
TikTok Agent
Instagram Agent
Facebook Agent
Analytics Agent
A/B Testing Agent
Content Calendar Agent
Channel Strategy Agent
```

These must be added without requiring changes to the core media rendering pipeline.

---

# 84. Future Publishing Architecture

Future architecture:

```text
Production
      ↓
Publishing Agent
      ↓
Platform Adapters
      ├── YouTube
      ├── TikTok
      ├── Instagram
      └── Facebook
```

Publishing must remain separate from the core production workflow.

---

# 85. Future Analytics Architecture

Future:

```text
Published Content
      ↓
Analytics Providers
      ↓
Performance Data
      ↓
Analytics Agent
      ↓
Creative Feedback
      ↓
Next Production Strategy
```

This enables a closed-loop content production system.

---

# 86. Future Closed-Loop Architecture

```text
TREND
  ↓
CREATE
  ↓
PUBLISH
  ↓
ANALYZE
  ↓
LEARN
  ↓
IMPROVE
  ↓
CREATE AGAIN
```

The MVP ends at:

```text
CREATE → LOCAL STORAGE
```

---

# 87. Architecture Decision Records

The initial architecture establishes the following decisions.

### ADR-001 — Local-First Architecture

The application stores application state and media artifacts locally.

### ADR-002 — Python Backend

Python is selected for AI, media, audio, and ML ecosystem compatibility.

### ADR-003 — Next.js Frontend

Next.js is selected for the primary application UI.

### ADR-004 — Temporal Workflow Engine

Temporal is selected for durable, resumable, long-running production workflows.

### ADR-005 — SQLite Database

SQLite is selected for the local-first metadata database.

### ADR-006 — Filesystem Asset Storage

Binary media artifacts are stored on the local filesystem rather than inside SQLite.

### ADR-007 — FFmpeg Rendering Engine

FFmpeg is the deterministic media processing engine.

### ADR-008 — Provider Abstraction

All external AI providers are accessed through capability and provider interfaces.

### ADR-009 — AI/Deterministic Separation

AI handles creative decisions; deterministic software handles media processing.

### ADR-010 — LanceDB

LanceDB is selected for local semantic memory and embedding-based retrieval.

---

# 88. MVP Definition

The MVP is complete when a user can:

```text
1. Open the application
2. Click New
3. Select Genre
4. Enter branding
5. Click Generate
6. Generate instrumental music
7. Generate visual background
8. Generate audio visualizer
9. Render 16:9 master
10. Select a short segment
11. Render 9:16 short
12. Generate metadata
13. Run QC
14. Store final artifacts locally
```

Trending mode must additionally support:

```text
Discover Trends
      ↓
Select Trending Genre/Concept
      ↓
Continue Production
```

---

# 89. Non-Functional Requirements

## Reliability

Productions must be resumable.

## Performance

The UI must remain responsive during production.

## Cost

Development must support mock and free-tier provider configurations.

## Portability

The application must support Windows 11.

## Maintainability

AI providers and models must be replaceable without rewriting business logic.

## Observability

Every production stage must be inspectable.

## Reproducibility

The production manifest must describe how an output was created.

---

# 90. Windows Compatibility

Primary target:

```text
Windows 11 Pro 64-bit
```

Required development/runtime components:

```text
Python
Node.js
pnpm
FFmpeg
Temporal
Git
```

FFmpeg should either be bundled, provisioned during installation, or detected by the application.

Filesystem operations must use cross-platform abstractions.

No application logic may depend on hard-coded Windows paths.

---

# 91. Package Management

Python:

```text
uv
```

Node.js:

```text
pnpm
```

Dependency lockfiles must be committed to source control.

Python dependencies must be locked.

---

# 92. Environment Profiles

Supported profiles:

```text
development
test
mock
production
```

Development:

```text
Real APIs optional
```

Test:

```text
Mock providers
```

Production:

```text
Real providers
```

---

# 93. Configuration Architecture

Configuration precedence:

```text
Default Configuration
        ↓
Configuration File
        ↓
Environment Variables
        ↓
User Settings
        ↓
Production Overrides
```

Production-specific configuration must be captured in the production manifest.

---

# 94. Important Configuration

```text
APP_DATA_DIR
DATABASE_URL
TEMP_DIR

DEFAULT_LLM_PROVIDER
DEFAULT_MUSIC_PROVIDER
DEFAULT_IMAGE_PROVIDER

MAX_CONCURRENT_PRODUCTIONS
MAX_RENDER_WORKERS

MASTER_VIDEO_WIDTH
MASTER_VIDEO_HEIGHT
MASTER_VIDEO_FPS

SHORT_VIDEO_WIDTH
SHORT_VIDEO_HEIGHT
SHORT_VIDEO_DURATION
```

---

# 95. Architectural Golden Rules

### Rule 1

Agents never call vendor SDKs directly.

### Rule 2

Agents never execute FFmpeg directly.

### Rule 3

Agents never manipulate production state directly.

### Rule 4

Temporal owns workflow execution state.

### Rule 5

SQLite owns application metadata.

### Rule 6

Filesystem storage owns binary artifacts.

### Rule 7

FFmpeg owns deterministic media processing.

### Rule 8

AI owns creative decisions.

### Rule 9

Every external provider must have an adapter.

### Rule 10

Every long-running operation must be resumable.

---

# 96. Recommended Implementation Order

Implementation must follow an architecture-first approach.

Recommended sequence:

```text
Phase 1
Repository + Development Environment

Phase 2
Domain Model

Phase 3
SQLite + Storage

Phase 4
FastAPI

Phase 5
Next.js UI

Phase 6
Temporal

Phase 7
Provider Abstraction

Phase 8
Mock Providers

Phase 9
Music Pipeline

Phase 10
Visual Pipeline

Phase 11
Audio Analysis + Visualizer

Phase 12
16:9 Renderer

Phase 13
9:16 Renderer

Phase 14
Metadata

Phase 15
Quality Control

Phase 16
Trend Engine

Phase 17
Real AI Providers

Phase 18
End-to-End Production

Phase 19
Performance Optimization

Phase 20
Desktop Packaging
```

Mock providers must be implemented before real AI providers so the complete workflow can be tested without external API costs.

---

# 97. Definition of Architectural Success

The architecture is successful when:

```text
✓ A user can create a production from one modal
✓ Production runs without blocking the UI
✓ Workflow can resume after failure
✓ Individual stages can be retried
✓ Providers can be replaced
✓ Music providers can be replaced
✓ Image providers can be replaced
✓ Trend providers can be replaced
✓ Rendering runs locally
✓ Assets are stored locally
✓ Production can be reproduced
✓ Duplicate generation can be prevented
✓ Mock/free modes are available
✓ 16:9 and 9:16 outputs are generated automatically
✓ Metadata is generated automatically
✓ Quality control is automated
```

---

# 98. Final Architecture

```text
                         USER
                           │
                           ▼
                    NEXT.JS 16 UI
                           │
                           ▼
                       FASTAPI
                           │
            ┌──────────────┴──────────────┐
            │                             │
            ▼                             ▼
       SQLite Database              Temporal
                                          │
                                          ▼
                                Production Workflow
                                          │
              ┌───────────────────────────┼──────────────────────────┐
              │                           │                          │
              ▼                           ▼                          ▼
        Trend Agent                 Music Agent                Visual Agent
              │                           │                          │
              ▼                           ▼                          ▼
       Trend Capability           Music Capability           Image Capability
              │                           │                          │
              ▼                           ▼                          ▼
       Trend Providers            Music Providers             Image Providers
                                          │
                                          ▼
                                   Audio Normalization
                                          │
                                          ▼
                                   Audio Analysis
                                          │
                                          ▼
                                     Visualizer
                                          │
                           ┌──────────────┴──────────────┐
                           ▼                             ▼
                    16:9 Renderer                 Short Selector
                           │                             │
                           │                             ▼
                           │                      9:16 Renderer
                           │                             │
                           └──────────────┬──────────────┘
                                          ▼
                                   Metadata Agent
                                          │
                                          ▼
                                      QC Agent
                                          │
                                          ▼
                                  Final Production
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    ▼                     ▼                     ▼
                16:9 MP4              9:16 MP4            metadata.json
                    │                     │                     │
                    └─────────────────────┼─────────────────────┘
                                          ▼
                                    LOCAL STORAGE
```

---

# 99. Architecture Baseline

**MAD-001 v1.0.0** is the approved architectural baseline for the AI Instrumental Music Video Production OS.

All subsequent technical documentation and implementation must conform to the architecture defined in this document.

The following documents must derive their requirements from this MAD:

```text
01. Product Requirements Document (PRD)
02. Architecture Principles
03. Technology Stack Specification
04. System Architecture Specification
05. Agent Architecture Specification
06. Workflow Specification
07. Trend / Discovery Engine Specification
08. Music Generation Specification
09. Visual Generation Specification
10. Audio Analysis & Visualizer Specification
11. Rendering Pipeline Specification
12. Storage Architecture Specification
13. Database Design Specification
14. Provider Architecture Specification
15. AI Model Management Specification
16. Metadata Specification
17. Quality Control Specification
18. Security & Privacy Specification
19. Logging & Monitoring Specification
20. Performance Optimization Specification
21. Testing Strategy
22. Deployment & Packaging Specification
23. Architecture Decision Records
24. Implementation Plan
```

Any deviation from this architecture must be documented through an Architecture Decision Record (ADR).

Architecture changes must never be introduced silently.

**END OF MAD-001**
