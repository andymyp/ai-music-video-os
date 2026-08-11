# MASTER EXECUTION DOCUMENT

# AI Instrumental Music Video Production OS

**Document ID:** MASTER-EXECUTION-001
**Version:** 1.0.0
**Status:** Implementation Master Plan
**Date:** 2026-08-10

**Source of Truth:**

* MAD-001 — Master Architecture Document
* PRD-001 — Product Requirements Document
* TDD-001 — Technical Design Document

---

# 1. Purpose

This document is the authoritative execution plan for implementing the AI Instrumental Music Video Production OS.

It converts the approved architecture and technical design into a sequence of implementation phases.

The implementation MUST follow this document sequentially unless an Architecture Decision Record explicitly authorizes a change.

---

# 2. Authority Hierarchy

When a conflict exists between implementation decisions, use the following priority:

```text
MAD
 ↓
PRD
 ↓
TDD
 ↓
MASTER_EXECUTION
 ↓
Implementation
```

A lower-level document MUST NOT override a higher-level document.

If implementation reveals that MAD, PRD, or TDD must change:

```text
Problem
   ↓
ADR
   ↓
Architecture Review
   ↓
MAD Update
   ↓
PRD Update
   ↓
TDD Update
   ↓
MASTER_EXECUTION Update
   ↓
Implementation
```

Do not silently change architecture.

---

# 3. Product Objective

The system allows a user to create an instrumental music video production through a single workflow.

The user:

```text
New
 ↓
Select Genre OR Trending
 ↓
Enter Branding Text
 ↓
Generate
```

The system then autonomously:

```text
Creative Planning
 ↓
Music Generation
 ↓
Visual Generation
 ↓
Audio Analysis
 ↓
Visualizer Generation
 ↓
16:9 Master Rendering
 ↓
9:16 Short Selection
 ↓
9:16 Short Rendering
 ↓
Metadata Generation
 ↓
Quality Control
 ↓
Local Storage
```

Each successful production produces:

```text
master-16x9.mp4
short-9x16.mp4
metadata.json
production.json
qc-report.json
```

---

# 4. Non-Negotiable Architecture

The implementation MUST preserve:

```text
Local-first
Provider-agnostic
AI-agent-driven creative decisions
Deterministic media processing
Temporal durable workflow
SQLite metadata persistence
Filesystem media storage
Resumable execution
Technical QC
Creative QC
16:9 master
9:16 short
Automatic metadata
```

---

# 5. Technology Baseline

## Frontend

```text
Next.js
React
TypeScript
Tailwind CSS
```

## Backend

```text
Python
FastAPI
Pydantic
```

## Workflow

```text
Temporal
```

## Database

```text
SQLite
SQLAlchemy
Alembic
```

## Media

```text
FFmpeg
FFprobe
Python media utilities
```

## AI

Provider-agnostic capability interfaces.

Required capability categories:

```text
LLM
Music
Image
Vision
Embedding
Trend
```

---

# 6. Implementation Philosophy

The implementation follows:

```text
Architecture First
      ↓
Contracts First
      ↓
Infrastructure
      ↓
Deterministic Services
      ↓
Provider Abstraction
      ↓
Workflow
      ↓
Agents
      ↓
API
      ↓
Frontend
      ↓
Quality Control
      ↓
End-to-End Validation
```

Do not start with UI before the underlying contracts and workflow architecture are established.

---

# 7. Execution Rules

Every implementation phase MUST:

1. Read this document.
2. Read the relevant MAD section.
3. Read the relevant PRD requirements.
4. Read the relevant TDD section.
5. Implement only the assigned scope.
6. Add tests.
7. Validate integration.
8. Update implementation status.
9. Report deviations.
10. Do not silently modify architecture.

---

# 8. Phase Completion Rule

A phase is complete only when:

```text
Code
+
Tests
+
Validation
+
Documentation
+
No unresolved blocking errors
```

A phase MUST NOT be marked complete merely because the code compiles.

---

# 9. Phase Dependency Graph

```text
Phase 00  Project Foundation
    ↓
Phase 01  Domain Model
    ↓
Phase 02  Database
    ↓
Phase 03  Filesystem Storage
    ↓
Phase 04  Provider Contracts
    ↓
Phase 05  Mock Providers
    ↓
Phase 06  Media Engine
    ↓
Phase 07  Audio Analysis
    ↓
Phase 08  Agent Runtime
    ↓
Phase 09  Workflow Runtime
    ↓
Phase 10  Production Workflow
    ↓
Phase 11  Trend Engine
    ↓
Phase 12  Music Pipeline
    ↓
Phase 13  Visual Pipeline
    ↓
Phase 14  Visualizer Pipeline
    ↓
Phase 15  Master Rendering
    ↓
Phase 16  Short Generation
    ↓
Phase 17  Metadata
    ↓
Phase 18  Quality Control
    ↓
Phase 19  API
    ↓
Phase 20  Frontend
    ↓
Phase 21  Recovery / Cancellation
    ↓
Phase 22  Observability
    ↓
Phase 23  Security
    ↓
Phase 24  End-to-End Integration
    ↓
Phase 25  Performance Validation
    ↓
Phase 26  Final Acceptance
```

---

# 10. Phase 00 — Project Foundation

## Objective

Create the base repository and development environment.

## Tasks

Create:

```text
apps/
packages/
infrastructure/
data/
tests/
docs/
```

Establish:

```text
Python environment
Node environment
FFmpeg
FFprobe
Temporal development environment
SQLite
```

Create initial application entry points:

```text
FastAPI application
Next.js application
Temporal worker
```

## Required Result

The following must start successfully:

```text
Frontend
Backend
Temporal Worker
Database
```

## Validation

```text
✓ Python environment works
✓ Node environment works
✓ FFmpeg available
✓ FFprobe available
✓ Backend starts
✓ Frontend starts
✓ Worker starts
```

---

# 11. Phase 01 — Domain Model

## Objective

Implement domain models defined by TDD.

Implement:

```text
Production
ProductionConfig
CreativeConcept
MusicStrategy
VisualStrategy
TrendResult
Asset
MetadataPackage
QualityDecision
ShortSegment
AudioAnalysis
VisualizerData
```

Implement enums:

```text
ProductionMode
ProductionStatus
AssetType
```

## Required Tests

Test:

* Valid production
* Invalid production
* Genre mode
* Trending mode
* Branding
* Status transitions
* Configuration validation

---

# 12. Phase 02 — Database

## Objective

Implement SQLite persistence.

Tables:

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

Implement:

```text
SQLAlchemy models
Repositories
Alembic migrations
```

## Required Repository Interfaces

```text
ProductionRepository
AssetRepository
WorkflowRepository
ProviderRunRepository
```

## Validation

Test:

```text
create
read
update
delete where permitted
relationships
transactions
migration
```

---

# 13. Phase 03 — Filesystem Storage

## Objective

Implement production artifact storage.

Structure:

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

Implement:

```text
StorageService
ArtifactService
HashService
```

## Requirements

Must support:

```text
write
read
exists
delete
hash
size
metadata
```

---

# 14. Phase 04 — Provider Contracts

## Objective

Create provider abstraction interfaces.

Implement:

```text
LLMProvider
MusicProvider
ImageProvider
VisionProvider
EmbeddingProvider
TrendProvider
```

The domain layer MUST NOT import provider SDKs.

---

# 15. Phase 05 — Mock Providers

## Objective

Create deterministic providers for development and testing.

Implement:

```text
MockLLMProvider
MockMusicProvider
MockImageProvider
MockVisionProvider
MockEmbeddingProvider
MockTrendProvider
```

Mock providers MUST:

* Be deterministic.
* Produce valid outputs.
* Require no external credentials.
* Support complete E2E workflow execution.

---

# 16. Phase 06 — Media Engine

## Objective

Create deterministic media-processing abstraction.

Implement:

```text
MediaEngine
FFmpegMediaEngine
```

Capabilities:

```text
render_master
render_short
analyze_audio
validate_media
extract_audio
extract_segment
```

The media engine must use structured FFmpeg arguments.

Do not use unsafe shell interpolation.

---

# 17. Phase 07 — Audio Analysis

## Objective

Implement audio analysis.

Produce:

```text
duration
BPM
loudness
energy_curve
spectral_curve
beats
sections
```

Output:

```text
AudioAnalysis
```

## Validation

Test against known audio fixtures.

---

# 18. Phase 08 — Agent Runtime

## Objective

Implement agent infrastructure.

Agents:

```text
OrchestratorAgent
TrendResearchAgent
MusicStrategyAgent
MusicGenerationAgent
VisualStrategyAgent
VisualGenerationAgent
ShortSelectionAgent
MetadataAgent
QualityControlAgent
```

Agents must use:

```text
typed inputs
typed outputs
registered tools
capability interfaces
```

Agents MUST NOT have unrestricted filesystem, shell, database, or secret access.

---

# 19. Phase 09 — Workflow Runtime

## Objective

Integrate Temporal.

Implement:

```text
ProductionWorkflow
Activities
Worker
Workflow configuration
Retry policies
```

The workflow must remain deterministic.

External calls occur inside activities.

---

# 20. Phase 10 — Production Workflow

Implement the base workflow:

```text
ValidateInput
 ↓
ResolveCreativeDirection
 ↓
GenerateMusicStrategy
 ↓
GenerateMusic
 ↓
ValidateMusic
 ↓
GenerateVisualStrategy
 ↓
GenerateBackground
 ↓
ResolveRadio
 ↓
AnalyzeAudio
 ↓
GenerateVisualizer
 ↓
RenderMaster
 ↓
ValidateMaster
 ↓
SelectShortSegment
 ↓
RenderShort
 ↓
ValidateShort
 ↓
GenerateMetadata
 ↓
RunQC
 ↓
GenerateManifest
 ↓
CompleteProduction
```

At this stage the workflow must work using mock providers.

---

# 21. Phase 11 — Trend Engine

## Objective

Implement Trending mode.

Architecture:

```text
TrendProvider
      ↓
Trend Aggregator
      ↓
Trend Ranking
      ↓
TrendResearchAgent
      ↓
CreativeConcept
```

Trend signals must consider:

```text
recency
volume
growth
cross-platform presence
content relevance
```

Trend data must be time-aware.

Stale results must not be presented as current trends.

---

# 22. Phase 12 — Music Pipeline

## Objective

Implement instrumental music generation.

Flow:

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
Music Validation
      ↓
Master Audio
```

The product requires:

```text
Instrumental
No Vocal
```

Music must be validated before proceeding.

---

# 23. Phase 13 — Visual Pipeline

## Objective

Generate the visual environment.

Flow:

```text
CreativeConcept
      ↓
VisualStrategyAgent
      ↓
VisualStrategy
      ↓
ImageProvider
      ↓
Background
```

The background must correspond to the selected:

```text
genre
mood
theme
creative direction
```

---

# 24. Phase 14 — Visualizer Pipeline

## Objective

Generate an audio-reactive visualizer.

Flow:

```text
Master Audio
      ↓
Audio Analysis
      ↓
Visualizer Data
      ↓
Visualizer Renderer
      ↓
Visualizer Layer
```

The visualizer must be synchronized with the actual audio.

It must be positioned inside the radio display area.

---

# 25. Phase 15 — Master Rendering

## Objective

Produce the 16:9 master.

Required inputs:

```text
Background
Radio
Visualizer
Branding
Master Audio
Render Profile
```

Output:

```text
master-16x9.mp4
```

Target:

```text
1920x1080
30 FPS
H.264
AAC
```

The exact encoding profile must be defined by the rendering configuration.

---

# 26. Phase 16 — Short Generation

## Objective

Generate the 9:16 short from the master production.

Selection:

```text
AudioAnalysis
      ↓
ShortSelectionAgent
      ↓
ShortSegment
```

Rendering:

```text
ShortSegment
+
Shared Visual Assets
+
Branding
      ↓
Vertical Renderer
      ↓
short-9x16.mp4
```

Target:

```text
1080x1920
```

The short must not regenerate independent music.

---

# 27. Phase 17 — Metadata

## Objective

Generate metadata automatically.

Generate:

```text
Title
Description
Hashtags
```

Metadata must be generated from actual production information.

Separate metadata may be generated for:

```text
Master
Short
```

Output:

```text
metadata.json
```

---

# 28. Phase 18 — Quality Control

## Objective

Implement technical and creative QC.

Technical QC:

```text
resolution
FPS
duration
codec
audio stream
video stream
file integrity
```

Creative QC:

```text
visual coherence
visualizer placement
branding presence
content consistency
metadata relevance
```

Output:

```text
qc-report.json
```

---

# 29. Phase 19 — API

## Objective

Expose application functionality to frontend.

Required endpoints:

```text
POST /api/productions
GET /api/productions
GET /api/productions/{id}
POST /api/productions/{id}/retry
POST /api/productions/{id}/cancel
GET /api/productions/{id}/progress
GET /api/productions/{id}/artifacts
```

The API must not execute the entire production synchronously.

Production execution occurs through Temporal.

---

# 30. Phase 20 — Frontend

## Objective

Implement the user-facing production interface.

Primary flow:

```text
Dashboard
    ↓
New
    ↓
New Production Modal
    ↓
Genre / Trending
    ↓
Branding Text
    ↓
Generate
    ↓
Production Progress
    ↓
Production Result
```

---

# 31. New Production Modal

Required UI:

```text
Mode
 ├── Genre
 └── Trending

Genre
Branding Text

Generate
```

When:

```text
Trending
```

is selected, the application determines the currently relevant genre/theme automatically.

---

# 32. Production Progress UI

Display:

```text
Current stage
Progress
Production status
Errors
```

Possible stages:

```text
Planning
Music
Visual
Audio Analysis
Master Rendering
Short Rendering
Metadata
Quality Control
Completed
```

---

# 33. Production Result UI

Display:

```text
Master Video
Short Video
Metadata
QC Result
```

The user must be able to access the generated local artifacts.

---

# 34. Phase 21 — Recovery and Cancellation

## Objective

Ensure durable execution.

Implement:

```text
workflow resume
activity retry
production recovery
cancellation
FFmpeg termination
```

Test:

```text
application crash
workflow retry
provider failure
media failure
cancellation
restart
```

---

# 35. Phase 22 — Observability

Implement structured logging.

Every important operation should include:

```text
production_id
workflow_id
stage
component
event
severity
duration
error
```

Track:

```text
production duration
stage duration
provider latency
provider failures
render duration
QC failures
```

---

# 36. Phase 23 — Security

Implement:

```text
credential isolation
filesystem path validation
safe FFmpeg execution
agent tool restrictions
secret handling
API validation
```

Never expose:

```text
API keys
provider credentials
arbitrary filesystem paths
```

to the frontend or AI agents.

---

# 37. Phase 24 — End-to-End Integration

## Objective

Execute the entire workflow using mock providers.

Test:

```text
Genre Production
```

and:

```text
Trending Production
```

Expected result:

```text
master-16x9.mp4
short-9x16.mp4
metadata.json
production.json
qc-report.json
```

---

# 38. E2E Genre Scenario

Input:

```json
{
  "mode": "genre",
  "genre": "lofi",
  "branding_text": "MY CHANNEL"
}
```

Expected flow:

```text
Genre
 ↓
Creative Concept
 ↓
Music
 ↓
Background
 ↓
Radio
 ↓
Visualizer
 ↓
Master
 ↓
Short
 ↓
Metadata
 ↓
QC
 ↓
Completed
```

---

# 39. E2E Trending Scenario

Input:

```json
{
  "mode": "trending",
  "branding_text": "MY CHANNEL"
}
```

Expected flow:

```text
Trend Discovery
 ↓
Trend Ranking
 ↓
Genre / Theme Decision
 ↓
Creative Concept
 ↓
Music
 ↓
Background
 ↓
Radio
 ↓
Visualizer
 ↓
Master
 ↓
Short
 ↓
Metadata
 ↓
QC
 ↓
Completed
```

---

# 40. Phase 25 — Performance Validation

Target hardware:

```text
AMD Ryzen 5 7430U
16 GB RAM
Windows 11 Pro
```

Performance validation must focus on:

```text
RAM usage
CPU utilization
Disk usage
FFmpeg performance
AI request latency
workflow duration
```

The initial system should default to:

```text
one heavy rendering task at a time
```

until benchmarks justify higher concurrency.

---

# 41. Resource Safety

The application must avoid:

```text
loading large video files entirely into RAM
unbounded concurrent rendering
unbounded provider requests
unbounded agent retries
```

Use:

```text
streaming
temporary files
bounded concurrency
bounded retries
```

---

# 42. Phase 26 — Final Acceptance

The system is accepted only when all required capabilities pass.

## Functional

```text
✓ Create production
✓ Genre mode
✓ Trending mode
✓ Branding
✓ Instrumental music
✓ Background generation
✓ Radio composition
✓ Audio visualizer
✓ 16:9 master
✓ 9:16 short
✓ Metadata
✓ QC
✓ Local storage
```

## Reliability

```text
✓ Retry
✓ Resume
✓ Cancellation
✓ Recovery
✓ Provider failure handling
```

## Technical

```text
✓ SQLite
✓ Filesystem storage
✓ Temporal
✓ FFmpeg
✓ Provider abstraction
✓ Agent runtime
✓ API
✓ Frontend
```

---

# 43. Production State Machine

Valid state progression:

```text
CREATED
   ↓
PLANNING
   ↓
CONCEPT_READY
   ↓
GENERATING_MUSIC
   ↓
MUSIC_READY
   ↓
GENERATING_VISUAL
   ↓
VISUAL_READY
   ↓
ANALYZING_AUDIO
   ↓
RENDERING_MASTER
   ↓
MASTER_READY
   ↓
SELECTING_SHORT
   ↓
RENDERING_SHORT
   ↓
SHORT_READY
   ↓
GENERATING_METADATA
   ↓
QUALITY_CHECK
   ↓
COMPLETED
```

Any unrecoverable failure:

```text
FAILED
```

Cancellation:

```text
CANCELLED
```

---

# 44. Artifact Lifecycle

Every artifact follows:

```text
REQUESTED
   ↓
GENERATING
   ↓
VALIDATING
   ↓
READY
```

Failure:

```text
FAILED
```

---

# 45. Provider Lifecycle

Provider execution:

```text
REQUESTED
   ↓
RUNNING
   ↓
SUCCESS
```

or:

```text
RUNNING
   ↓
RETRYABLE_FAILURE
   ↓
RETRY
```

or:

```text
RUNNING
   ↓
PERMANENT_FAILURE
```

---

# 46. Agent Execution Lifecycle

```text
INPUT
 ↓
PLAN
 ↓
TOOL / CAPABILITY EXECUTION
 ↓
RESULT
 ↓
VALIDATION
 ↓
OUTPUT
```

Invalid output must not be passed silently to the next stage.

---

# 47. Regeneration Rules

Regeneration is permitted only when:

```text
provider failure
invalid output
quality failure
creative validation failure
```

Regeneration must be bounded.

Example:

```text
Maximum Attempts = N
```

The exact value is configuration-driven.

---

# 48. Prompt Execution Rules

Every AI prompt must:

* Have a version.
* Have a defined input schema.
* Have a defined output schema.
* Use structured output where applicable.
* Be validated before downstream use.

---

# 49. Agent Execution Rules

Agents must:

```text
Reason
Decide
Call approved capabilities
Validate results
Return structured output
```

Agents must not:

```text
Directly execute FFmpeg
Directly access secrets
Directly manipulate arbitrary files
Directly access the database
```

---

# 50. Deterministic Service Rules

Deterministic services handle:

```text
Media
Audio analysis
Rendering
Validation
Hashing
Storage
State persistence
```

AI agents handle:

```text
Creative planning
Trend interpretation
Music direction
Visual direction
Short selection
Metadata
Creative QC
```

---

# 51. Local-First Rules

The application must keep:

```text
Production metadata
Production state
Generated media
Metadata
QC
Manifest
```

locally.

External providers are dependencies for capabilities, not the system of record.

---

# 52. Provider-Agnostic Rules

Never write:

```python
if provider == "specific_provider":
```

inside business logic when capability abstraction is sufficient.

Use:

```python
provider_registry.resolve(
    capability=Capability.MUSIC
)
```

instead.

---

# 53. Storage Rules

SQLite stores:

```text
state
metadata
relationships
references
configuration
```

Filesystem stores:

```text
audio
images
videos
large artifacts
```

Never store large video binaries directly inside SQLite.

---

# 54. Workflow Rules

Temporal is the source of truth for active workflow execution.

Do not create a second independent workflow engine.

---

# 55. API Rules

API responsibilities:

```text
validate requests
create production
query production state
expose progress
expose artifacts
request retry
request cancellation
```

API does not directly perform long-running AI or rendering work.

---

# 56. Frontend Rules

Frontend is responsible for:

```text
user input
production creation
progress visualization
result visualization
artifact access
error presentation
```

Frontend does not contain:

```text
provider credentials
AI orchestration
workflow logic
FFmpeg execution
```

---

# 57. Testing Matrix

| Component      | Unit | Integration | E2E |
| -------------- | ---: | ----------: | --: |
| Domain         |    ✓ |             |     |
| Database       |    ✓ |           ✓ |     |
| Storage        |    ✓ |           ✓ |     |
| Providers      |    ✓ |           ✓ |     |
| Media Engine   |    ✓ |           ✓ |   ✓ |
| Audio Analysis |    ✓ |           ✓ |   ✓ |
| Agents         |    ✓ |           ✓ |   ✓ |
| Workflow       |      |           ✓ |   ✓ |
| API            |    ✓ |           ✓ |   ✓ |
| Frontend       |    ✓ |           ✓ |   ✓ |
| QC             |    ✓ |           ✓ |   ✓ |

---

# 58. Required Test Scenarios

At minimum:

```text
1. Create genre production
2. Create trending production
3. Branding enabled
4. Branding empty
5. Music provider success
6. Music provider failure
7. Image provider failure
8. Trend provider failure
9. Invalid AI output
10. Master render failure
11. Short render failure
12. QC failure
13. Workflow retry
14. Workflow resume
15. Cancellation
16. Application restart
17. Duplicate request
18. Insufficient disk space
19. Invalid input
20. Complete successful production
```

---

# 59. Definition of Production Success

A production is successful only when:

```text
master-16x9.mp4
exists
AND
is valid
AND

short-9x16.mp4
exists
AND
is valid
AND

metadata.json
exists
AND

production.json
exists
AND

qc-report.json
exists
AND

mandatory QC passed
```

Then:

```text
Production.status = COMPLETED
```

---

# 60. Definition of Production Failure

Production is failed when:

```text
A required stage cannot complete
AND
Retry policy is exhausted
AND
No valid fallback exists
```

Previously generated valid artifacts must not be deleted.

---

# 61. Definition of Production Cancellation

Cancellation means:

```text
The user intentionally stopped execution.
```

Cancellation must not be classified as a technical failure.

---

# 62. Definition of Production Recovery

Recovery means:

```text
The application or worker restarts
and
the production continues from the durable workflow state.
```

---

# 63. Implementation Status Tracking

Maintain the following table in the project:

| Phase | Name                    | Status      |
| ----- | ----------------------- | ----------- |
| 00    | Project Foundation      | COMPLETED   |
| 01    | Domain Model            | COMPLETED   |
| 02    | Database                | COMPLETED   |
| 03    | Filesystem Storage      | COMPLETED   |
| 04    | Provider Contracts      | COMPLETED   |
| 05    | Mock Providers          | COMPLETED   |
| 06    | Media Engine            | COMPLETED   |
| 07    | Audio Analysis          | COMPLETED   |
| 08    | Agent Runtime           | COMPLETED   |
| 09    | Workflow Runtime        | COMPLETED   |
| 10    | Production Workflow     | COMPLETED   |
| 11    | Trend Engine            | COMPLETED   |
| 12    | Music Pipeline          | COMPLETED   |
| 13    | Visual Pipeline         | COMPLETED   |
| 14    | Visualizer Pipeline     | COMPLETED   |
| 15    | Master Rendering        | COMPLETED   |
| 16    | Short Generation        | COMPLETED   |
| 17    | Metadata                | COMPLETED   |
| 18    | Quality Control         | COMPLETED   |
| 19    | API                     | COMPLETED   |
| 20    | Frontend                | COMPLETED   |
| 21    | Recovery / Cancellation | COMPLETED   |
| 22    | Observability           | COMPLETED    |
| 23    | Security                | NOT_STARTED |
| 24    | End-to-End Integration  | NOT_STARTED |
| 25    | Performance Validation  | NOT_STARTED |
| 26    | Final Acceptance        | NOT_STARTED |

Allowed statuses:

```text
NOT_STARTED
IN_PROGRESS
BLOCKED
COMPLETED
```

---

# 64. Phase Execution Protocol

For each phase:

```text
STEP 1
Read MASTER_EXECUTION.md

STEP 2
Read corresponding MAD requirements

STEP 3
Read corresponding PRD requirements

STEP 4
Read corresponding TDD requirements

STEP 5
Inspect existing implementation

STEP 6
Implement only this phase

STEP 7
Run tests

STEP 8
Run integration validation

STEP 9
Fix failures

STEP 10
Update phase status

STEP 11
Record deviations

STEP 12
Only then proceed
```

---

# 65. AI Coding Agent Rules

Any AI coding agent implementing this project MUST:

```text
Read MASTER_EXECUTION.md first.
```

Then inspect:

```text
MAD
PRD
TDD
```

before making architectural changes.

The agent must never:

```text
rewrite architecture without authorization
skip phases
delete working functionality without justification
replace Temporal with another workflow engine
replace SQLite without authorization
couple business logic to a provider
move media into database storage
give agents unrestricted system access
```

---

# 66. Coding Agent Scope Rule

When instructed:

```text
Implement Phase X
```

the coding agent must:

1. Read all relevant documents.
2. Inspect existing implementation.
3. Determine what already exists.
4. Implement missing functionality.
5. Avoid duplicating existing functionality.
6. Run relevant tests.
7. Fix regressions.
8. Report completion.
9. Stop at the requested phase.

It must not automatically implement future phases unless explicitly instructed.

---

# 67. No Scope Creep Rule

The following are NOT part of the current execution scope unless explicitly added through PRD/MAD changes:

```text
Cloud media storage
Automatic social media posting
Multi-user SaaS
Team collaboration
Mobile application
Real-time collaboration
Public API platform
Marketplace
Subscription billing
Advanced analytics platform
```

The system remains focused on local AI-assisted instrumental music video production.

---

# 68. Current MVP User Journey

The complete MVP journey is:

```text
USER
 │
 ▼
Click "New"
 │
 ▼
New Production Modal
 │
 ├── Genre
 │      └── Select Genre
 │
 └── Trending
        └── AI determines current trend
 │
 ▼
Enter Branding Text
 │
 ▼
Click "Generate"
 │
 ▼
Production Created
 │
 ▼
AI Planning
 │
 ▼
Instrumental Music Generated
 │
 ▼
Background Generated
 │
 ▼
Radio + Visualizer Prepared
 │
 ▼
Audio Analysis
 │
 ▼
16:9 Master Rendered
 │
 ▼
Best Short Segment Selected
 │
 ▼
9:16 Short Rendered
 │
 ▼
Metadata Generated
 │
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

# 69. Final Output Contract

Every successful production MUST produce:

```text
data/
└── productions/
    └── <production-id>/
        ├── render/
        │   ├── master-16x9.mp4
        │   └── short-9x16.mp4
        │
        ├── metadata/
        │   └── metadata.json
        │
        ├── manifest/
        │   └── production.json
        │
        └── qc/
            └── qc-report.json
```

Additional intermediate artifacts may exist.

---

# 70. Final Architecture

```text
┌─────────────────────────────────────────────┐
│                    USER                     │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│                 NEXT.JS UI                  │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│                  FASTAPI                    │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│              APPLICATION LAYER              │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│             TEMPORAL WORKFLOW               │
└──────────────────────┬──────────────────────┘
                       │
          ┌────────────┼─────────────┐
          │            │             │
          ▼            ▼             ▼
     AI AGENTS     PROVIDERS    MEDIA ENGINE
          │            │             │
          │            │             │
          └────────────┼─────────────┘
                       │
                       ▼
             ┌──────────────────┐
             │ SQLite + Storage │
             └──────────────────┘
                       │
                       ▼
              LOCAL ARTIFACTS
```

---

# 71. Final Execution Principle

The system must be implemented from the inside outward:

```text
FOUNDATION
   ↓
DOMAIN
   ↓
PERSISTENCE
   ↓
CAPABILITIES
   ↓
MEDIA
   ↓
AGENTS
   ↓
WORKFLOW
   ↓
PRODUCTION
   ↓
API
   ↓
UI
   ↓
QC
   ↓
RELIABILITY
   ↓
ACCEPTANCE
```

Do not reverse this order without an approved architectural reason.

---

# 72. Final Master Rule

The implementation agent must always remember:

```text
MAD defines WHAT the system is.
PRD defines WHAT the product must do.
TDD defines HOW the system is technically designed.
MASTER_EXECUTION defines IN WHAT ORDER it must be implemented.
```

Therefore:

```text
Do not invent requirements.
Do not change architecture silently.
Do not skip foundational phases.
Do not couple the product to one AI provider.
Do not put deterministic media processing inside AI agents.
Do not bypass Temporal for long-running production execution.
Do not store large media files inside SQLite.
Do not expose secrets to agents or frontend.
Do not mark a phase complete without validation.
```

---

# 73. Final Implementation Target

At the end of this execution plan, the application must provide a complete local-first AI production pipeline:

```text
USER
  ↓
NEW
  ↓
GENRE / TRENDING
  ↓
BRANDING
  ↓
GENERATE
  ↓
AI CREATIVE PLANNING
  ↓
AI INSTRUMENTAL MUSIC
  ↓
AI VISUAL DIRECTION
  ↓
AI BACKGROUND
  ↓
RADIO
  ↓
AUDIO ANALYSIS
  ↓
AUDIO VISUALIZER
  ↓
16:9 MASTER
  ↓
SHORT SEGMENT SELECTION
  ↓
9:16 SHORT
  ↓
TITLE
  ↓
DESCRIPTION
  ↓
HASHTAGS
  ↓
TECHNICAL QC
  ↓
CREATIVE QC
  ↓
LOCAL STORAGE
  ↓
COMPLETED
```

The final system is considered technically complete only when this entire pipeline can execute successfully, recover from failures, and produce the required artifacts using the approved architecture.

**END OF MASTER_EXECUTION-001**
