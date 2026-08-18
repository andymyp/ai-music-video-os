# TECHNICAL DESIGN DOCUMENT

# AI Instrumental Music Video Production OS

**Document ID:** TDD-001
**Version:** 1.0.0
**Status:** Approved
**Date:** 2026-08-10
**Parent Documents:** MAD-001 v1.0.0, PRD-001 v1.0.0

---

# 1. Document Purpose

This Technical Design Document defines the technical implementation design for the AI Instrumental Music Video Production OS.

The document translates the requirements defined in:

* MAD-001 — Master Architecture Document
* PRD-001 — Product Requirements Document

into concrete technical designs.

This document defines:

* Application architecture
* Runtime architecture
* Module boundaries
* Data flow
* Workflow execution
* Agent implementation
* Provider abstraction
* Media processing
* Storage
* Database
* API boundaries
* Frontend architecture
* Configuration
* Error handling
* Retry behavior
* Testing
* Security
* Performance

This document must not introduce requirements outside the scope of MAD-001 and PRD-001.

---

# 2. Design Principles

The implementation must follow these principles.

## 2.1 Local-First

Application state and generated artifacts are stored locally.

External services are used only when required for AI capabilities or external trend information.

---

## 2.2 Provider-Agnostic

Business logic must never depend directly on a specific AI provider.

Providers are accessed through capability interfaces.

```text
Application
     ↓
Capability Interface
     ↓
Provider Adapter
     ↓
External Provider
```

---

## 2.3 Agent-Orchestrated

AI agents make creative decisions and coordinate AI capabilities.

Deterministic services perform technical operations.

```text
Agent
   ↓
Decision
   ↓
Service
   ↓
Deterministic Result
```

---

## 2.4 Deterministic Media Processing

FFmpeg and related media processing components must perform deterministic operations.

AI must not be responsible for:

* Video encoding
* Audio normalization
* Timeline manipulation
* Visualizer rendering
* File concatenation
* Format conversion

---

## 2.5 Resumable Workflow

Every long-running production must be represented as a durable workflow.

A workflow failure must not invalidate already completed stages.

---

## 2.6 Explicit State

Every important production transition must be represented by persistent state.

---

## 2.7 Artifact-Based Processing

Each stage consumes and produces explicit artifacts.

```text
Input Artifact
      ↓
Processing
      ↓
Output Artifact
```

---

# 3. System Architecture

The system consists of the following logical layers:

```text
┌─────────────────────────────────────────────┐
│                  Frontend                   │
│              Desktop Web UI                │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│                Application API              │
│             Production Management           │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│             Workflow Runtime                │
│              Temporal Worker                │
└──────────────────────┬──────────────────────┘
                       │
          ┌────────────┼─────────────┐
          ▼            ▼             ▼
      AI Agents    AI Providers   Media Engine
          │            │             │
          └────────────┼─────────────┘
                       ▼
┌─────────────────────────────────────────────┐
│          Local Persistence Layer             │
│       SQLite + Filesystem + Cache            │
└─────────────────────────────────────────────┘
```

---

# 4. Runtime Components

The application consists of these runtime components:

```text
ai-music-video-os
│
├── frontend
├── api
├── orchestrator
├── workflow-worker
├── agent-runtime
├── provider-runtime
├── media-engine
├── storage
├── database
└── observability
```

These are logical components.

The MVP may deploy them within a single local application process or a small number of processes while preserving the logical boundaries.

---

# 5. Recommended Runtime Stack

## Frontend

```text
Next.js
React
TypeScript
Tailwind CSS
```

---

## Backend

```text
Python
FastAPI
Pydantic
```

Python is selected because the product requires:

* AI integration
* Media processing
* Audio analysis
* Image processing
* AI SDK ecosystem
* Workflow integration

---

## Workflow

```text
Temporal
```

Temporal is responsible for:

* Durable workflows
* Retry
* Resume
* Activity execution
* Workflow state

---

## Database

```text
SQLite
```

SQLite is the primary local relational database.

---

## ORM / Database Layer

```text
SQLAlchemy
Alembic
```

---

## Media

```text
FFmpeg
FFprobe
Python media utilities
```

---

## AI Runtime

AI providers are accessed through internal capability interfaces.

The system must not embed provider-specific calls inside business logic.

---

# 6. Repository Structure

Recommended repository structure:

```text
music-video-os/
│
├── apps/
│   ├── web/
│   └── api/
│
├── packages/
│   ├── domain/
│   ├── application/
│   ├── agents/
│   ├── providers/
│   ├── workflows/
│   ├── media/
│   ├── storage/
│   ├── database/
│   ├── observability/
│   └── shared/
│
├── infrastructure/
│   ├── temporal/
│   ├── ffmpeg/
│   └── scripts/
│
├── data/
│   ├── database/
│   ├── productions/
│   ├── assets/
│   ├── cache/
│   └── logs/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── workflow/
│   └── e2e/
│
├── docs/
│
├── pyproject.toml
├── package.json
└── README.md
```

The exact physical repository structure may change during implementation, but logical boundaries must remain intact.

---

# 7. Domain Model

The primary domain object is:

```text
Production
```

A Production represents one complete content-generation request.

---

# 8. Production Entity

Conceptual model:

```python
Production
├── id
├── mode
├── genre
├── branding_text
├── status
├── target_duration
├── created_at
├── updated_at
├── completed_at
└── version
```

---

# 9. Production Modes

```python
class ProductionMode(str, Enum):
    GENRE = "genre"
    TRENDING = "trending"
```

---

# 10. Production Status

```python
class ProductionStatus(str, Enum):
    CREATED = "created"
    PLANNING = "planning"
    CONCEPT_READY = "concept_ready"
    GENERATING_MUSIC = "generating_music"
    MUSIC_READY = "music_ready"
    GENERATING_VISUAL = "generating_visual"
    VISUAL_READY = "visual_ready"
    ANALYZING_AUDIO = "analyzing_audio"
    RENDERING_MASTER = "rendering_master"
    MASTER_READY = "master_ready"
    SELECTING_SHORT = "selecting_short"
    RENDERING_SHORT = "rendering_short"
    SHORT_READY = "short_ready"
    GENERATING_METADATA = "generating_metadata"
    QUALITY_CHECK = "quality_check"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

---

# 11. Production Configuration

```python
ProductionConfig
├── mode
├── genre
├── branding
├── long_form_duration
├── short_form_duration
├── master_resolution
├── short_resolution
├── fps
├── visualizer_style
├── branding_position
├── branding_opacity
└── provider_profile
```

The configuration is immutable once production execution begins.

---

# 12. Creative Concept

The workflow produces a structured creative concept.

```python
CreativeConcept
├── genre
├── mood
├── theme
├── audience
├── music_direction
└── visual_direction
```

---

# 13. Music Strategy

```python
MusicStrategy
├── genre
├── mood
├── bpm_range
├── key
├── instruments
├── structure
├── duration
└── vocal_policy
```

The vocal policy must always be:

```text
none
```

for this product.

---

# 14. Visual Strategy

```python
VisualStrategy
├── environment
├── lighting
├── style
├── color_direction
├── radio_style
├── composition
└── visualizer_style
```

---

# 15. Trend Result

```python
TrendResult
├── source
├── topic
├── genre
├── score
├── confidence
├── recency
└── evidence
```

Multiple TrendResult objects may be evaluated before a final trend decision.

---

# 16. Asset Entity

```python
Asset
├── id
├── production_id
├── type
├── path
├── mime_type
├── size
├── sha256
├── provider
├── status
├── created_at
└── metadata
```

---

# 17. Asset Types

```python
AssetType
├── AUDIO_SOURCE
├── AUDIO_MASTER
├── BACKGROUND
├── RADIO
├── VISUALIZER_DATA
├── MASTER_VIDEO
├── SHORT_VIDEO
├── METADATA
├── QC_REPORT
└── MANIFEST
```

---

# 18. Database Design

SQLite tables:

```text
productions
production_configs
creative_concepts
music_strategies
visual_strategies
trend_results
assets
workflow_runs
provider_runs
metadata
qc_reports
events
```

---

# 19. Production Table

```sql
productions
------------
id
mode
genre
branding_text
status
created_at
updated_at
completed_at
version
```

---

# 20. Asset Table

```sql
assets
------
id
production_id
type
path
mime_type
size
sha256
provider
status
created_at
metadata_json
```

---

# 21. Provider Run Table

```sql
provider_runs
-------------
id
production_id
capability
provider
model
status
started_at
completed_at
error_code
metadata_json
```

This allows provider usage to be traced without coupling the domain layer to the provider implementation.

---

# 22. Workflow Architecture

The production workflow is:

```text
ProductionWorkflow
│
├── ValidateInput
├── ResolveCreativeDirection
├── GenerateMusicStrategy
├── GenerateMusic
├── ValidateMusic
├── GenerateVisualStrategy
├── GenerateBackground
├── ResolveRadio
├── AnalyzeAudio
├── GenerateVisualizer
├── RenderMaster
├── ValidateMaster
├── SelectShortSegment
├── RenderShort
├── ValidateShort
├── GenerateMetadata
├── RunQC
├── GenerateManifest
└── CompleteProduction
```

---

# 23. Workflow Execution

The Temporal workflow coordinates activities.

Conceptually:

```python
@workflow.defn
class ProductionWorkflow:

    @workflow.run
    async def run(self, production_id):
        ...
```

The workflow must remain deterministic.

External calls must occur inside activities.

---

# 24. Workflow Activity Rule

Activities may perform:

* Provider calls
* Database operations
* Filesystem operations
* FFmpeg execution
* Audio analysis
* Image processing

The workflow itself must coordinate these activities.

---

# 25. Input Validation Activity

The first activity validates:

* Production mode
* Genre when required
* Branding
* Configuration
* Provider availability
* Disk space

Invalid requests terminate before expensive generation.

---

# 26. Creative Direction

### Genre Mode

```text
User Genre
    ↓
Creative Planner
    ↓
Creative Concept
```

### Trending Mode

```text
Trend Providers
      ↓
Trend Research Agent
      ↓
Trend Result
      ↓
Creative Planner
      ↓
Creative Concept
```

---

# 27. Trend Architecture

Trend discovery uses:

```text
TrendProvider Interface
```

Example:

```python
class TrendProvider(Protocol):

    async def discover(
        self,
        query: TrendQuery
    ) -> list[TrendSignal]:
        ...
```

The provider implementation remains replaceable.

---

# 28. Trend Aggregation

The system may combine multiple trend sources.

```text
Provider A ─┐
Provider B ─┼──> Trend Aggregator
Provider C ─┘
                   ↓
              Trend Ranking
                   ↓
              AI Analysis
```

---

# 29. Trend Scoring

Trend scoring must consider:

```text
recency
volume
growth
cross-platform presence
content relevance
```

A normalized score is produced.

The scoring implementation is deterministic where possible.

---

# 30. Music Provider Interface

```python
class MusicProvider(Protocol):

    async def generate(
        self,
        request: MusicGenerationRequest
    ) -> GeneratedAudio:
        ...
```

Provider adapters implement this interface.

---

# 31. Image Provider Interface

```python
class ImageProvider(Protocol):

    async def generate(
        self,
        request: ImageGenerationRequest
    ) -> GeneratedImage:
        ...
```

---

# 32. LLM Provider Interface

```python
class LLMProvider(Protocol):

    async def generate_structured(
        self,
        request: StructuredGenerationRequest
    ) -> StructuredResult:
        ...
```

Structured outputs must be validated using Pydantic schemas.

---

# 33. Vision Provider Interface

Where visual AI analysis is required:

```python
class VisionProvider(Protocol):

    async def analyze(
        self,
        request: VisionRequest
    ) -> VisionResult:
        ...
```

---

# 34. Embedding Provider Interface

For semantic deduplication:

```python
class EmbeddingProvider(Protocol):

    async def embed(
        self,
        text: str
    ) -> list[float]:
        ...
```

---

# 35. Provider Registry

Providers are registered through a registry.

```text
ProviderRegistry
│
├── LLM
├── Music
├── Image
├── Vision
├── Embedding
└── Trend
```

The registry resolves a capability according to configuration.

---

# 36. Provider Selection

Selection may consider:

```text
Provider Profile
      ↓
Capability
      ↓
Availability
      ↓
Cost
      ↓
Quota
      ↓
Priority
      ↓
Provider
```

---

# 37. Provider Failover

Example:

```text
MusicProvider A
      ↓
Rate Limited
      ↓
Provider Registry
      ↓
MusicProvider B
      ↓
Success
```

Only compatible providers may be used as fallback.

---

# 38. AI Agent Architecture

The agent layer contains:

```text
AgentRuntime
│
├── OrchestratorAgent
├── TrendResearchAgent
├── MusicStrategyAgent
├── MusicGenerationAgent
├── VisualStrategyAgent
├── VisualGenerationAgent
├── ShortSelectionAgent
├── MetadataAgent
└── QualityControlAgent
```

---

# 39. Agent Contract

Agents must communicate through typed inputs and outputs.

Example:

```python
class Agent[Input, Output]:

    async def execute(
        self,
        input: Input
    ) -> Output:
        ...
```

---

# 40. Orchestrator Agent

The Orchestrator is responsible for creative coordination.

It may determine:

* Which agent should run.
* Which capability should be used.
* Whether a result requires regeneration.
* Which creative direction should be selected.

It must not execute low-level system operations.

---

# 41. Agent Tool Boundary

Agents may use registered tools.

Example:

```text
Agent
  ↓
Tool Registry
  ↓
Capability Service
```

Agents must not directly access:

```text
OS shell
Filesystem
Secrets
Database
Provider SDK
```

---

# 42. Music Generation Flow

```text
CreativeConcept
       ↓
MusicStrategyAgent
       ↓
MusicStrategy
       ↓
MusicGenerationAgent
       ↓
MusicProvider
       ↓
Audio Asset
       ↓
MusicValidator
       ↓
Master Audio
```

---

# 43. Music Validation

Validation uses:

```text
FFprobe
Audio analysis
Duration validation
Format validation
Silence detection
Optional vocal detection
```

---

# 44. Vocal Detection

The system should use an available audio/AI analysis capability to detect potential vocal content.

The result is advisory unless a deterministic validation method is available.

If vocal presence violates the configured requirement, the music may be rejected and regenerated.

---

# 45. Audio Analysis

Audio analysis generates structured data:

```text
AudioAnalysis
├── duration
├── bpm
├── loudness
├── energy_curve
├── spectral_curve
├── beats
├── sections
└── timestamps
```

---

# 46. Visualizer Data

Visualizer generation consumes audio analysis.

```text
Master Audio
      ↓
Audio Analysis
      ↓
Frequency / Waveform Data
      ↓
Visualizer Data
      ↓
Renderer
```

Visualizer data must be generated from the actual audio used by the master video.

---

# 47. Background Generation

```text
VisualStrategy
      ↓
ImageProvider
      ↓
Background Image
      ↓
Image Validation
      ↓
Background Asset
```

---

# 48. Radio Resolution

Radio selection follows:

```text
VisualStrategy
      ↓
Asset Search
      ↓
Existing Suitable Radio?
      │
   ┌──┴──┐
  YES    NO
   │      │
   ▼      ▼
Reuse   Generate
   │      │
   └──┬───┘
      ▼
Radio Asset
```

---

# 49. Master Composition

The master video renderer receives:

```text
Background
Radio
Visualizer Data
Branding
Master Audio
Render Profile
```

---

# 50. Master Rendering

The deterministic media engine creates:

```text
1920x1080
30 FPS
H.264
AAC
```

using FFmpeg or an equivalent configured rendering engine.

---

# 51. Master Rendering Pipeline

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
Composition Graph
     ↓
FFmpeg
     ↓
master-16x9.mp4
```

---

# 52. Visualizer Rendering

The visualizer must be composited into the radio's central display area.

The renderer must use predefined layout parameters:

```text
radio_position
radio_scale
visualizer_region
visualizer_style
branding_position
```

---

# 53. Branding Rendering

Branding configuration:

```text
text
position
font
size
opacity
margin
```

The same branding configuration must be applied to both master and short outputs unless explicitly configured otherwise.

---

# 54. Short Selection

The short selection stage consumes:

```text
AudioAnalysis
```

and produces:

```python
ShortSegment
├── start
├── duration
├── score
└── reason
```

---

# 55. Short Selection Strategy

Potential scoring dimensions:

```text
energy
musical interest
transition quality
melodic interest
section completeness
```

The highest-quality valid segment is selected.

---

# 56. Short Rendering

The short renderer uses:

```text
Background
Radio
Visualizer
Branding
Audio Segment
Short Render Profile
```

Output:

```text
1080x1920
```

---

# 57. Metadata Generation

Metadata Agent input:

```text
CreativeConcept
MusicStrategy
VisualStrategy
Production Context
ShortSegment
```

Output:

```python
MetadataPackage
├── master
│   ├── title
│   ├── description
│   └── hashtags
└── short
    ├── title
    ├── description
    └── hashtags
```

---

# 58. Metadata Validation

Validation must ensure:

* Required fields exist.
* Hashtags are structured correctly.
* No unsupported claims are introduced.
* Metadata corresponds to the actual production.
* No excessive keyword stuffing.

---

# 59. Quality Control Pipeline

```text
Master
  ↓
Technical QC
  ↓
Creative QC

Short
  ↓
Technical QC
  ↓
Creative QC

Metadata
  ↓
Metadata QC

All Results
  ↓
Final QC
```

---

# 60. Technical QC

Technical QC uses deterministic tools.

Primary tools:

```text
FFprobe
FFmpeg validation
Filesystem checks
Hash validation
```

Checks include:

```text
resolution
FPS
duration
codec
audio stream
video stream
file integrity
```

---

# 61. Creative QC

Creative QC may use AI for:

* Visual coherence
* Visualizer placement
* Branding presence
* Content consistency
* Metadata relevance

AI QC results must be represented as structured results.

---

# 62. Storage Architecture

The filesystem is the primary media storage system.

Recommended structure:

```text
data/
└── productions/
    └── <production-id>/
        ├── input/
        ├── planning/
        ├── audio/
        ├── visual/
        ├── render/
        ├── metadata/
        ├── qc/
        └── manifest/
```

---

# 63. Artifact Naming

Artifacts must use deterministic names.

Example:

```text
audio-master.wav
background.png
radio.png
visualizer.json
master-16x9.mp4
short-9x16.mp4
metadata.json
qc-report.json
production.json
```

---

# 64. Temporary Storage

Temporary files must be stored under:

```text
data/cache/
```

or production-specific temporary directories.

Temporary files must be removed after successful processing unless explicitly required for recovery.

---

# 65. Artifact Hashing

Every final artifact must have a SHA-256 hash.

Example:

```text
master-16x9.mp4
sha256:
<hash>
```

This supports:

* Integrity
* Deduplication
* Reproducibility

---

# 66. Deduplication

The deduplication service may use:

```text
Exact Hash
     ↓
Perceptual Hash
     ↓
Semantic Similarity
```

The system should avoid regenerating identical assets when a valid equivalent exists.

---

# 67. Database / Filesystem Separation

SQLite stores:

```text
metadata
state
relationships
configuration
references
```

Filesystem stores:

```text
large media artifacts
```

The database must not store large video or audio binaries.

---

# 68. API Architecture

The API provides frontend-facing application operations.

Example routes:

```text
POST   /api/productions
GET    /api/productions
GET    /api/productions/{id}
POST   /api/productions/{id}/retry
POST   /api/productions/{id}/cancel
GET    /api/productions/{id}/progress
GET    /api/productions/{id}/artifacts
```

---

# 69. Create Production API

```http
POST /api/productions
```

Request:

```json
{
  "mode": "genre",
  "genre": "lofi",
  "branding_text": "MY CHANNEL"
}
```

Response:

```json
{
  "id": "production-id",
  "status": "created"
}
```

The API must validate input before starting the workflow.

---

# 70. Trending API

Trending mode may be represented as:

```json
{
  "mode": "trending",
  "branding_text": "MY CHANNEL"
}
```

The server/workflow performs trend discovery.

The client does not need to know which trend provider is used.

---

# 71. Progress API

```http
GET /api/productions/{id}/progress
```

Response:

```json
{
  "production_id": "123",
  "status": "rendering_master",
  "progress": 0.63,
  "stage": "Rendering Master"
}
```

---

# 72. Artifact API

```http
GET /api/productions/{id}/artifacts
```

Response:

```json
{
  "master": "...",
  "short": "...",
  "metadata": "..."
}
```

The API should provide safe local artifact access rather than exposing arbitrary filesystem paths.

---

# 73. Frontend Architecture

Frontend structure:

```text
app/
├── dashboard/
├── productions/
├── components/
├── hooks/
├── services/
├── stores/
└── types/
```

---

# 74. New Production Modal

Components:

```text
NewProductionModal
├── ModeSelector
├── GenreSelector
├── BrandingInput
└── GenerateButton
```

When Trending is selected:

```text
GenreSelector
```

is disabled/hidden.

---

# 75. Production Detail UI

```text
ProductionDetail
├── Status
├── Progress
├── MasterPreview
├── ShortPreview
├── MetadataPanel
├── QCPanel
└── Actions
```

---

# 76. Progress Communication

The frontend may use:

```text
Server-Sent Events
```

or polling.

The exact mechanism must not alter the underlying workflow architecture.

The production state remains authoritative in the backend.

---

# 77. Configuration Architecture

Configuration hierarchy:

```text
Default Configuration
        ↓
User Configuration
        ↓
Production Configuration
        ↓
Runtime Configuration
```

Production configuration is persisted as part of the production.

---

# 78. Provider Configuration

Provider configuration must contain:

```text
provider_id
capability
model
priority
enabled
cost_mode
credentials_reference
```

Secrets must not be stored in plaintext production records.

---

# 79. Secrets

Secrets must be stored in:

* Environment variables
* OS credential store
* Secure local secret storage

Agents must never receive raw API keys.

---

# 80. Logging

Structured logs must include:

```text
timestamp
production_id
workflow_id
stage
component
event
severity
duration
error
```

Logs must not contain API keys.

---

# 81. Observability

The system should expose:

```text
Production duration
Stage duration
Provider latency
Provider failures
Workflow failures
Rendering duration
QC failures
```

---

# 82. Error Model

Errors should use typed categories:

```text
ValidationError
ProviderError
RateLimitError
TimeoutError
MediaProcessingError
StorageError
WorkflowError
QualityError
ConfigurationError
```

---

# 83. Retry Policy

Provider calls should use exponential backoff where appropriate.

Example:

```text
Attempt 1
   ↓
1s
   ↓
Attempt 2
   ↓
2s
   ↓
Attempt 3
   ↓
4s
```

Exact retry configuration must remain provider-aware.

---

# 84. Workflow Retry

Temporal handles workflow activity retries.

The application must not implement an independent competing retry engine.

---

# 85. Idempotency

Activities that create artifacts must be designed to avoid duplicate output.

A production stage should use:

```text
production_id
stage
attempt
artifact_id
```

to identify execution.

---

# 86. Cancellation

Cancellation must propagate from:

```text
Frontend
   ↓
API
   ↓
Temporal
   ↓
Activity
   ↓
Media Process
```

Long-running FFmpeg processes must be safely terminated when cancellation is requested.

---

# 87. Resource Management

Only one heavy media rendering task should run concurrently by default on the target laptop.

Concurrency may be increased later after benchmarking.

---

# 88. Memory Management

The implementation must avoid loading entire large media files into RAM.

Prefer:

```text
streaming
file paths
temporary files
FFmpeg pipelines
```

over:

```text
full file bytes in memory
```

---

# 89. Disk Management

The media engine must:

* Monitor available disk space.
* Use temporary directories.
* Remove unnecessary intermediates.
* Preserve required recovery artifacts.

---

# 90. Security Architecture

Security boundaries:

```text
Frontend
   ↓
API
   ↓
Application Services
   ↓
Workflow
   ↓
Activities
   ↓
Providers / Media Engine
```

No frontend component may directly access provider credentials.

---

# 91. Filesystem Security

All production paths must be derived from validated production IDs.

Arbitrary paths supplied by the user must not be accepted.

---

# 92. Shell Execution Security

FFmpeg execution must use structured argument arrays.

Avoid:

```text
shell=True
```

or equivalent unsafe shell interpolation.

---

# 93. Agent Security

Agents must not have unrestricted system access.

The agent runtime exposes only explicitly registered tools.

---

# 94. Testing Strategy

Testing layers:

```text
Unit Tests
Integration Tests
Workflow Tests
Provider Contract Tests
Media Tests
End-to-End Tests
```

---

# 95. Unit Tests

Unit tests cover:

* Domain models
* Validation
* Scoring
* Metadata validation
* Configuration
* Deduplication
* Short selection

---

# 96. Provider Contract Tests

Each provider adapter must implement the same capability contract.

Example:

```text
MusicProviderContract
ImageProviderContract
LLMProviderContract
TrendProviderContract
```

---

# 97. Media Tests

Media tests verify:

```text
audio duration
video resolution
FPS
codec
audio presence
video presence
visualizer synchronization
branding presence
```

---

# 98. Workflow Tests

Workflow tests must verify:

```text
happy path
provider failure
retry
resume
cancellation
partial completion
duplicate execution
```

Temporal's test environment should be used where appropriate.

---

# 99. End-to-End Test

The complete E2E test:

```text
Create Production
      ↓
Generate
      ↓
Workflow
      ↓
Music
      ↓
Visual
      ↓
Master
      ↓
Short
      ↓
Metadata
      ↓
QC
      ↓
Local Artifacts
```

The test must use mock providers to avoid external costs.

---

# 100. Mock Provider Architecture

Mock providers must implement the same interfaces as production providers.

Example:

```text
MusicProvider
├── MockMusicProvider
├── ProviderA
└── ProviderB
```

Mock providers should return deterministic outputs.

---

# 101. Development Mode

Development mode must support:

```text
Mock LLM
Mock Music
Mock Image
Mock Trend
Mock Vision
Mock Embedding
```

This allows the entire workflow to be tested without external API access.

---

# 102. Production Mode

Production mode uses configured real providers.

Example:

```text
Provider Registry
      ↓
Capability
      ↓
Selected Provider
      ↓
External API
```

---

# 103. Configuration Profiles

Recommended profiles:

```text
development
free
balanced
quality
custom
```

Profiles select provider priorities rather than embedding providers inside business logic.

---

# 104. Free Provider Strategy

The application should support providers offering:

* Free tiers
* Large quotas
* Local inference
* Open models

However, availability and quota limits are external provider concerns.

The application must not assume any provider is permanently unlimited.

---

# 105. Local AI Strategy

Where practical, local models may be registered as providers.

Examples of capabilities:

```text
Local LLM
Local Embedding
Local Vision
Local Audio Analysis
```

This reduces API cost and external dependency.

---

# 106. External AI Strategy

External providers are preferred when:

* Quality is significantly higher.
* Local inference is too expensive computationally.
* A capability is unavailable locally.
* Trend information requires current external data.
* Generation speed is insufficient locally.

---

# 107. Cost Control

Every provider execution should record:

```text
provider
model
capability
duration
estimated usage
status
```

This allows later cost analysis.

---

# 108. Trend Data Caching

Trend results may be cached for a short configurable period.

The cache must include:

```text
provider
query
timestamp
result
expiration
```

The system must not treat stale trend information as current.

---

# 109. Asset Cache

Reusable assets may be cached.

Examples:

```text
radio assets
fonts
visualizer templates
static resources
```

Generated production-specific content must remain associated with the production.

---

# 110. Versioning

The following must be versioned:

```text
Production schema
Prompt templates
Agent definitions
Rendering profiles
Provider adapters
Configuration
```

The production manifest records the versions used.

---

# 111. Prompt Versioning

AI prompts must be stored as versioned application resources.

Example:

```text
prompts/
├── trend/
│   └── v1.txt
├── music-strategy/
│   └── v1.txt
├── visual-strategy/
│   └── v1.txt
└── metadata/
    └── v1.txt
```

The exact file organization may vary.

---

# 112. Rendering Profiles

Rendering profiles define:

```text
resolution
FPS
video codec
audio codec
bitrate
pixel format
visualizer layout
branding layout
```

Example:

```text
master_1080p
short_1080x1920
```

---

# 113. Rendering Determinism

Given identical:

```text
input assets
audio
visualizer data
branding
render profile
```

the renderer should produce equivalent output.

Binary-level identical output is not required unless explicitly configured.

---

# 114. Production Manifest

Example:

```json
{
  "production_id": "prod_123",
  "mode": "genre",
  "genre": "lofi",
  "branding_text": "MY CHANNEL",
  "creative_concept": {},
  "music_strategy": {},
  "visual_strategy": {},
  "providers": {},
  "assets": {},
  "outputs": {
    "master": {},
    "short": {}
  },
  "metadata": {},
  "qc": {}
}
```

---

# 115. Completion Transaction

A production is marked `COMPLETED` only after:

```text
Master exists
AND
Short exists
AND
Metadata exists
AND
QC passed
AND
Manifest written
```

The completion state must be persisted atomically.

---

# 116. Recovery Model

If the application crashes:

```text
Application Restart
       ↓
Load Production
       ↓
Read Workflow State
       ↓
Identify Last Valid Stage
       ↓
Resume
```

Temporal remains the authoritative workflow execution mechanism.

---

# 117. Startup Recovery

On startup, the application must:

1. Connect to local database.
2. Initialize storage.
3. Connect to Temporal.
4. Resume worker operation.
5. Discover existing productions.
6. Display their persisted state.

---

# 118. Shutdown

The application must attempt graceful shutdown of:

* API
* Workflow worker
* Media processes
* Provider connections

Active workflows must remain recoverable.

---

# 119. Data Retention

Production artifacts should remain until explicitly removed by the user or by configured cleanup policy.

Automatic cleanup must never delete a completed production unexpectedly.

---

# 120. Backup

Backup is not required for MVP but the storage architecture must allow the production directory and SQLite database to be backed up together.

---

# 121. API / Domain Separation

API models must not directly become domain models.

```text
HTTP Request
    ↓
API Schema
    ↓
Application Command
    ↓
Domain Model
```

This prevents API contracts from leaking into internal architecture.

---

# 122. Application Services

Core application services:

```text
ProductionService
TrendService
MusicService
VisualService
AudioService
RenderingService
MetadataService
QCService
ArtifactService
ProviderService
```

Services coordinate domain logic but do not bypass workflow boundaries for long-running operations.

---

# 123. Repository Interfaces

Persistence uses interfaces such as:

```python
ProductionRepository
AssetRepository
WorkflowRepository
ProviderRunRepository
```

Concrete implementation:

```text
SQLiteRepository
```

---

# 124. Media Engine Interface

```python
class MediaEngine(Protocol):

    async def render_master(...):
        ...

    async def render_short(...):
        ...

    async def analyze_audio(...):
        ...

    async def validate_media(...):
        ...
```

---

# 125. Media Engine Implementation

The default implementation uses:

```text
FFmpeg
FFprobe
Python utilities
```

The application interacts with the media engine through its interface.

---

# 126. Audio Visualizer Engine

Visualizer rendering must be deterministic.

Conceptual interface:

```python
class VisualizerEngine:

    def generate_data(
        self,
        audio_analysis
    ) -> VisualizerData:
        ...

    def render(
        self,
        visualizer_data,
        layout
    ) -> VisualizerLayer:
        ...
```

---

# 127. Short Video Architecture

The short is not generated independently from the master concept.

It shares:

```text
CreativeConcept
Music
Background
Radio
Branding
Visualizer
```

but uses:

```text
ShortSegment
ShortRenderProfile
VerticalComposition
```

---

# 128. Vertical Composition

The vertical composition must calculate:

```text
source dimensions
radio position
radio scale
visualizer region
branding position
safe margins
```

The implementation must prevent important elements from being cropped.

---

# 129. Audio Segment Extraction

The selected short segment should be extracted directly from the master audio rather than regenerating music.

This ensures:

```text
Master Audio
      ↓
Short Audio
```

and guarantees consistency.

---

# 130. Metadata Consistency

Metadata generation must consume actual production data.

It must not invent:

* Artists
* Songs
* Instruments that are not present
* Claims about trends
* External achievements

unless those facts are actually available.

---

# 131. Quality Gate Decision

QC returns:

```python
QualityDecision
├── passed
├── issues
├── warnings
└── score
```

A production cannot complete when mandatory QC failures exist.

Warnings may be allowed according to configurable policy.

---

# 132. Error Propagation

Errors propagate:

```text
Activity
   ↓
Workflow
   ↓
Production State
   ↓
API
   ↓
Frontend
```

Errors must retain structured codes.

---

# 133. Provider Rate Limits

Provider rate-limit errors must be classified separately.

The provider adapter should expose:

```text
retryable = true
retry_after
provider_code
```

when available.

---

# 134. Network Failures

Temporary network failures must be retryable.

Persistent failures must transition the production to an actionable failed state.

---

# 135. Invalid AI Output

Invalid structured AI output must:

1. Be rejected.
2. Be logged.
3. Optionally trigger a controlled regeneration.
4. Never silently pass downstream.

---

# 136. AI Regeneration

Regeneration must be limited.

A stage should have a configured maximum number of creative regeneration attempts.

If the limit is reached:

```text
Stage → FAILED
```

---

# 137. Duplicate Production Requests

The system should support idempotency for production creation.

A repeated request with the same idempotency key should not create duplicate productions.

---

# 138. Production ID

Production IDs must be globally unique within the local application.

Recommended format:

```text
prod_<ULID>
```

---

# 139. Asset ID

Asset IDs should use the same uniqueness strategy:

```text
asset_<ULID>
```

---

# 140. Time Handling

All persisted timestamps should use UTC internally.

The UI may convert timestamps to local time.

---

# 141. Deterministic Configuration

A production must snapshot:

```text
provider profile
render profile
agent versions
prompt versions
creative configuration
```

so future configuration changes do not alter historical production interpretation.

---

# 142. Compatibility

The system must support:

```text
Windows 11
```

as the primary development/runtime platform for MVP.

Media binaries must be validated against the target operating system.

---

# 143. External Dependency Failure

If an external provider is unavailable:

```text
Provider unavailable
      ↓
Retry
      ↓
Failover
      ↓
If unavailable
      ↓
Workflow paused/failed
```

Previously generated assets must remain valid.

---

# 144. Offline Production History

The application must continue to provide access to:

* Production history
* Metadata
* Local video files
* QC reports

without external AI providers.

---

# 145. Performance Budget

The initial implementation should prioritize:

```text
Low RAM usage
Single active render
Streaming media processing
Minimal asset duplication
Efficient FFmpeg operations
```

Exact performance budgets must be established through benchmarks.

---

# 146. Implementation Sequence

Implementation should follow this dependency order:

```text
1. Project Foundation
2. Domain Models
3. SQLite Persistence
4. Filesystem Storage
5. Provider Interfaces
6. Mock Providers
7. Media Engine
8. Workflow Runtime
9. Agent Runtime
10. Production Workflow
11. API
12. Frontend
13. QC
14. Recovery
15. E2E Tests
```

---

# 147. Definition of Done

A component is considered complete when:

```text
Implementation
+
Unit Tests
+
Integration Tests where applicable
+
Error Handling
+
Logging
+
Documentation
```

are complete.

---

# 148. MVP Technical Definition of Done

The MVP technical implementation is complete when:

```text
✓ Application starts locally
✓ SQLite initializes
✓ Filesystem storage initializes
✓ Temporal worker starts
✓ Mock providers work
✓ Production can be created
✓ Genre mode works
✓ Trending mode works
✓ Music pipeline works
✓ Visual pipeline works
✓ Audio analysis works
✓ Visualizer works
✓ Master rendering works
✓ Short selection works
✓ Short rendering works
✓ Metadata generation works
✓ QC works
✓ Retry works
✓ Resume works
✓ Cancellation works
✓ Final artifacts are stored locally
✓ E2E test passes
```

---

# 149. Architecture Compliance

The implementation must comply with MAD-001 and PRD-001.

The following are mandatory:

```text
Local-first
Provider-agnostic
AI-agent-driven creative decisions
Deterministic media processing
Temporal-based durable workflow
SQLite metadata persistence
Filesystem media storage
Resumable execution
16:9 master output
9:16 short output
Automatic metadata
Technical + creative QC
```

---

# 150. Architectural Change Rule

If implementation requires a change to any architectural principle defined by MAD-001, the change must not be silently implemented.

The process is:

```text
Problem
  ↓
ADR
  ↓
Architecture Review
  ↓
MAD Update
  ↓
PRD/TDD Update
  ↓
Implementation
```

---

# 151. Final Technical Contract

The system accepts:

```text
ProductionRequest
├── mode
├── genre (optional when trending)
└── branding_text (optional)
```

The workflow produces:

```text
ProductionResult
├── master-16x9.mp4
├── short-9x16.mp4
├── metadata.json
├── production.json
└── qc-report.json
```

All outputs are locally persisted.

---

# 152. Final System Flow

```text
                    USER
                      │
                      ▼
              New Production
                      │
                      ▼
             Genre / Trending
                      │
                      ▼
                Branding
                      │
                      ▼
                  Generate
                      │
                      ▼
              ┌───────────────┐
              │ API / Service │
              └───────┬───────┘
                      │
                      ▼
             Temporal Workflow
                      │
          ┌───────────┴───────────┐
          │                       │
          ▼                       ▼
     AI Agents              AI Providers
          │                       │
          └───────────┬───────────┘
                      │
                      ▼
                Media Engine
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
       16:9 MP4    9:16 MP4    Metadata
          │           │           │
          └───────────┼───────────┘
                      ▼
                     QC
                      │
                      ▼
               Local Storage
                      │
                      ▼
                  COMPLETED
```

---

# 153. Final Technical Statement

The AI Instrumental Music Video Production OS is implemented as a **local-first, provider-agnostic, agent-driven media production system**.

AI agents are responsible for creative reasoning and decisions.

Deterministic services are responsible for:

* Audio processing
* Audio analysis
* Visualizer generation
* Video composition
* Video encoding
* Validation
* Storage

Temporal provides durable orchestration and recovery.

SQLite stores application state and metadata.

The filesystem stores large media artifacts.

The resulting system allows a single production request to deterministically progress from:

```text
Genre / Trending
        ↓
Creative Direction
        ↓
Instrumental Music
        ↓
Visual Background
        ↓
Audio Visualizer
        ↓
16:9 Master
        ↓
Short Segment
        ↓
9:16 Short
        ↓
Metadata
        ↓
Quality Control
        ↓
Local Storage
```

without requiring manual media editing.

**END OF TDD-001**
