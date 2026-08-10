# PRODUCT REQUIREMENTS DOCUMENT

# AI Instrumental Music Video Production OS

**Document ID:** PRD-001
**Version:** 1.0.0
**Status:** Approved
**Date:** 2026-08-10
**Parent Architecture:** MAD-001 v1.0.0

---

# 1. Document Purpose

This Product Requirements Document (PRD) defines the functional and non-functional product requirements for the **AI Instrumental Music Video Production OS**.

This document is derived directly from **MAD-001 v1.0.0**.

The PRD defines:

* Product goals
* User experience
* Product scope
* Functional requirements
* Production workflow
* AI agent responsibilities
* Output requirements
* Quality requirements
* Error and recovery behavior
* Configuration requirements
* MVP acceptance criteria

This document must not introduce architectural decisions that conflict with MAD-001.

---

# 2. Product Vision

The product enables a user to generate a complete instrumental music content package through a minimal interaction.

The user should only need to:

1. Create a new production.
2. Select a genre or trending mode.
3. Optionally provide branding text.
4. Click Generate.

The system then autonomously:

1. Determines the creative direction.
2. Generates instrumental music.
3. Generates the visual background.
4. Creates the audio visualizer.
5. Produces a 16:9 long-form video.
6. Selects an appropriate short segment.
7. Produces a 9:16 short-form video.
8. Generates metadata.
9. Performs quality control.
10. Saves the final artifacts locally.

---

# 3. Product Goals

## 3.1 Primary Goals

The system must:

* Automate instrumental music video production.
* Require minimal user interaction.
* Produce both long-form and short-form content from one production.
* Use AI agents for creative decisions.
* Use deterministic media processing for technical operations.
* Store final outputs locally.
* Support genre-based production.
* Support trend-based production.
* Support user branding.
* Generate metadata automatically.
* Support resumable production workflows.
* Support provider replacement and failover.

---

# 4. Non-Goals

The MVP does not include:

* Automatic social media publishing.
* YouTube publishing.
* TikTok publishing.
* Instagram publishing.
* Facebook publishing.
* Monetization management.
* Analytics dashboards for published content.
* Multi-user collaboration.
* Cloud storage.
* SaaS billing.
* Team permissions.
* Full manual video editing.
* Manual timeline editing.

These capabilities may be introduced in future versions but are not requirements for PRD-001.

---

# 5. Target User

The primary user is a content creator who wants to produce instrumental music content without manually performing the creative and technical production process.

The user does not need to:

* Select individual music instruments.
* Manually create the visualizer.
* Edit the video timeline.
* Manually create the short clip.
* Write metadata.
* Perform technical rendering.
* Manually assemble the final video.

The system handles these responsibilities automatically.

---

# 6. Core User Journey

The complete user journey is:

```text
Open Application
      ↓
Click "New"
      ↓
Production Modal
      ↓
Select Genre / Trending
      ↓
Enter Branding Text
      ↓
Click "Generate"
      ↓
Production Starts
      ↓
AI Planning
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
Short Segment Selection
      ↓
9:16 Short Rendering
      ↓
Metadata Generation
      ↓
Quality Control
      ↓
Production Completed
      ↓
Local Storage
```

---

# 7. Production Creation

## PRD-001-FR-001 — New Production

The user must be able to create a new production by clicking the **New** button.

### Acceptance Criteria

* A production creation modal is displayed.
* The modal allows the user to select the production mode.
* The modal allows branding text input.
* The user can start generation from the modal.

---

# 8. Production Modes

The system must provide two production modes:

```text
Genre
Trending
```

---

## PRD-001-FR-002 — Genre Mode

When the user selects **Genre**, the system must allow the user to select a music genre.

Example genres:

* Lo-fi
* Jazz
* Ambient
* Chill
* Classical
* Synthwave
* Piano
* Acoustic
* Cinematic

The exact available genre list must remain configurable.

### Acceptance Criteria

* Genre mode can be selected.
* A genre can be selected.
* The selected genre is stored with the production.
* The genre becomes the initial creative input for the production.

---

# 9. Trending Mode

## PRD-001-FR-003 — Trending Mode

When the user selects **Trending**, the user does not manually select the genre.

The system must determine the appropriate trending genre or creative direction automatically.

The system must use current trend signals available before the production begins.

---

## PRD-001-FR-004 — Trend Discovery

The system must collect relevant trend signals before determining the production concept.

Trend signals may include:

* Search trends
* Video trends
* Music trends
* Social signals
* Community signals
* Cross-platform signals

The exact providers are defined separately through the provider architecture.

---

## PRD-001-FR-005 — Trend Evaluation

The system must evaluate trend signals using:

* Growth
* Volume
* Cross-platform presence
* Recency
* Content fit

The trend engine must produce a structured trend result.

Example:

```json
{
  "genre": "lofi",
  "score": 89.4,
  "confidence": 0.91
}
```

---

## PRD-001-FR-006 — Trend Creative Decision

The system must not simply select the most popular genre.

The AI must interpret the trend signals and determine an appropriate creative opportunity.

The result may include:

```text
Genre
Mood
Theme
Music direction
Visual direction
Target audience
```

---

# 10. Branding

## PRD-001-FR-007 — Branding Input

The user must be able to enter optional branding text.

Example:

```text
MY MUSIC CHANNEL
```

The branding text is associated with the production.

---

## PRD-001-FR-008 — Branding on Master Video

The branding must be rendered into the 16:9 master video.

---

## PRD-001-FR-009 — Branding on Short Video

The branding must also be rendered into the 9:16 short video.

---

## PRD-001-FR-010 — Branding Consistency

The same production branding configuration must be used for both outputs.

The branding configuration must not change during an active production.

---

# 11. Generate Action

## PRD-001-FR-011 — Start Production

When the user clicks **Generate**, the application must:

1. Validate the production configuration.
2. Create the production record.
3. Persist the production input.
4. Start the production workflow.
5. Display production progress.

The frontend must not block while the production is running.

---

# 12. Production Progress

The application must display the current production stage.

Example:

```text
Generating Music
████████░░░░░░░░ 50%
```

Possible stages:

```text
Planning
Trend Research
Generating Music
Generating Visual
Analyzing Audio
Rendering Master
Selecting Short
Rendering Short
Generating Metadata
Quality Check
Completed
```

---

# 13. Production State

The production must expose a state.

Supported states include:

```text
CREATED
PLANNING
CONCEPT_READY
GENERATING_MUSIC
MUSIC_READY
GENERATING_VISUAL
VISUAL_READY
ANALYZING_AUDIO
RENDERING_MASTER
MASTER_READY
SELECTING_SHORT
RENDERING_SHORT
SHORT_READY
GENERATING_METADATA
QUALITY_CHECK
COMPLETED
FAILED
```

The UI must represent these states clearly.

---

# 14. AI Creative Planning

Before generating media, the system must establish the creative direction.

The creative plan must consider:

* Selected genre or trend
* Mood
* Theme
* Music characteristics
* Visual characteristics
* Target content format

---

# 15. Instrumental Music Requirement

## PRD-001-FR-012 — Instrumental-Only Content

All generated music must be instrumental.

The production must explicitly prohibit:

```text
Vocals
Lyrics
Singing
Spoken vocal content
```

The system must validate generated audio where practical.

---

# 16. Music Strategy

## PRD-001-FR-013 — Music Strategy Generation

The AI must generate a structured music strategy.

The strategy may contain:

```text
Genre
Mood
BPM range
Key
Instruments
Musical style
Structure
Duration target
```

Example:

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
  "vocal_policy": "none"
}
```

---

# 17. Music Generation

## PRD-001-FR-014 — Generate Music

The system must generate or obtain an instrumental music track according to the music strategy.

The music provider must be selected through the provider abstraction layer.

The product must not depend on a single music provider.

---

# 18. Music Validation

After music generation, the system must validate:

* File existence
* File readability
* Duration
* Audio format
* Sample rate
* Channel configuration
* Audio integrity
* Instrumental requirement where technically detectable

Invalid audio must not proceed to rendering.

---

# 19. Audio Normalization

The system must normalize generated audio before final rendering.

Normalization may include:

* Sample rate normalization
* Channel normalization
* Loudness normalization
* Silence detection
* Format normalization

The normalized output becomes the master audio source.

---

# 20. Visual Strategy

## PRD-001-FR-015 — Visual Strategy Generation

The AI must generate a visual strategy based on:

* Genre
* Mood
* Theme
* Music direction
* Branding context

The visual strategy must define:

* Environment
* Lighting
* Style
* Color direction
* Radio style
* Composition

---

# 21. Background Image

## PRD-001-FR-016 — Generate Background

The system must generate or obtain a background image matching the visual strategy.

The background must:

* Support 16:9 composition.
* Have sufficient resolution.
* Avoid unwanted text.
* Avoid unwanted logos.
* Provide suitable space for the radio.
* Support a coherent visual composition.

---

# 22. Radio

## PRD-001-FR-017 — Radio Asset

Every final video must contain a radio visual element.

The radio may be:

* Selected from an existing asset library.
* Generated when an appropriate asset does not exist.

The radio style must match the visual strategy.

---

# 23. Audio Visualizer

## PRD-001-FR-018 — Visualizer Generation

The system must generate an audio visualizer synchronized with the actual master audio.

The visualizer must be positioned within the radio's central display area.

The visualizer may use:

* Frequency bars
* Waveforms
* Spectrum visualization
* Other configured deterministic visualizer styles

---

# 24. Visualizer Synchronization

The visualizer must be generated from actual audio analysis.

It must not be a randomly animated visual unrelated to the audio.

The system must use deterministic audio processing to derive visualizer values.

---

# 25. Master Video

## PRD-001-FR-019 — 16:9 Master

Every successful production must generate exactly one 16:9 master video.

Target:

```text
1920 × 1080
30 FPS
H.264
AAC
```

The final configuration remains configurable through rendering profiles.

---

# 26. Master Video Composition

The master must contain:

```text
Background
+
Radio
+
Audio Visualizer
+
Branding
+
Instrumental Audio
```

The elements must maintain visual consistency throughout the video.

---

# 27. Long-Form Content

The master video is the long-form output.

The initial target duration is approximately:

```text
60 minutes
```

The exact duration must remain configurable.

The music duration and rendering configuration must be compatible with the configured target duration.

---

# 28. Short Video

## PRD-001-FR-020 — Generate Short

Every successful production must generate exactly one 9:16 short-form video.

Target:

```text
1080 × 1920
```

Initial duration target:

```text
30–60 seconds
```

The exact duration must remain configurable.

---

# 29. Short Segment Selection

## PRD-001-FR-021 — Select Short Segment

The system must automatically select a suitable segment from the production's audio.

Selection may consider:

* Energy
* Musical changes
* Melodic interest
* Transitions
* Standalone quality
* Intro/outro suitability

The user is not required to manually select the segment.

---

# 30. Short Composition

The short must use a dedicated vertical composition.

It must not simply crop the 16:9 master.

The composition must maintain:

* Background
* Radio
* Visualizer
* Branding
* Visual identity

---

# 31. Metadata Generation

## PRD-001-FR-022 — Generate Metadata

The system must automatically generate metadata.

Required metadata:

```text
Title
Description
Hashtags
```

Metadata must be generated for:

1. The 16:9 master.
2. The 9:16 short.

---

# 32. Master Metadata

Master metadata should be optimized for long-form content.

The title must:

* Describe the content.
* Reflect the genre or theme.
* Be natural.
* Avoid keyword stuffing.

The description must accurately describe the music and visual concept.

Hashtags must be relevant to the actual content.

---

# 33. Short Metadata

Short metadata should be optimized independently from master metadata.

The short may have:

* Different title
* Different description
* Different hashtags

The metadata must remain factually consistent with the production.

---

# 34. Quality Control

## PRD-001-FR-023 — Technical QC

Before completion, the system must verify:

* Master file exists.
* Short file exists.
* Files are readable.
* Video streams exist.
* Audio streams exist.
* Duration is valid.
* Resolution is valid.
* FPS is valid.
* Branding is present.
* Files are not corrupted.

---

# 35. Creative QC

## PRD-001-FR-024 — Creative QC

The system should evaluate:

* Visual coherence.
* Music/visual consistency.
* Metadata quality.
* Potential vocal presence.
* Creative duplication.

Creative QC must not replace deterministic technical validation.

---

# 36. Quality Gates

A production must pass the relevant quality gate before proceeding.

Example:

```text
Music Generated
      ↓
Music Validation
      ↓
Visual Generated
      ↓
Visual Validation
      ↓
Master Render
      ↓
Master Validation
      ↓
Short Render
      ↓
Short Validation
      ↓
Metadata Validation
      ↓
Final QC
```

---

# 37. Failure Handling

If a stage fails, the system must preserve previously completed stages.

Example:

```text
Music
  ↓
Visual
  ↓
Master Render
  ↓
FAILED
```

Retrying must not regenerate the music or visual unnecessarily.

---

# 38. Retry

The user must be able to retry a failed production stage when the failure is recoverable.

The system must distinguish between:

### Retryable

* Temporary provider failure
* Network timeout
* Rate limit
* Temporary infrastructure failure

### Non-Retryable

* Invalid configuration
* Invalid credentials
* Unsupported input
* Permanent provider error

---

# 39. Resume

A production must be resumable.

If the application closes during production, previously completed stages must remain available.

When resumed, the workflow should continue from the last valid stage.

---

# 40. Local Storage

## PRD-001-FR-025 — Save Final Output

When production is completed, all final artifacts must be stored locally.

Required files:

```text
master-16x9.mp4
short-9x16.mp4
metadata.json
production.json
qc-report.json
```

---

# 41. Production Manifest

The system must save a production manifest describing:

* Production ID
* Input configuration
* Creative decisions
* Assets
* Providers
* Renders
* Metadata
* QC
* Timestamps
* Production version

The manifest must support production traceability.

---

# 42. Asset Management

Generated assets must be associated with the production.

Asset types include:

```text
Audio
Image
Radio
Visualizer Data
Video
Metadata
QC Report
```

Each asset should have:

* Unique ID
* Path
* Hash
* MIME type
* Size
* Creation time
* Provider
* Status

---

# 43. Deduplication

The system must attempt to prevent unnecessary duplicate generation.

Deduplication may use:

```text
SHA-256
Perceptual Hash
Embedding Similarity
Audio Fingerprinting
```

The system should reuse an existing valid asset when the same generation request is detected.

---

# 44. Provider Independence

The product must not expose provider-specific concepts to the core production workflow.

The product should operate using capabilities such as:

```text
LLM
Music Generation
Image Generation
Trend Research
Embedding
Vision
```

Providers are implementation details.

---

# 45. Provider Failover

If the selected provider fails and another compatible provider is configured, the system should attempt provider failover.

Example:

```text
Provider A
   ↓
Failure
   ↓
Provider B
   ↓
Success
```

The production must remain provider-agnostic.

---

# 46. Cost-Aware Operation

The application must support multiple provider modes.

Required modes:

```text
Mock
Free
Balanced
Quality
Custom
```

### Mock

No external AI APIs are required.

### Free

Prioritizes free or local providers.

### Balanced

Balances quality, cost, latency, and availability.

### Quality

Prioritizes output quality.

### Custom

Allows user-defined provider routing.

---

# 47. Local-First Requirement

The following must remain local:

* Production metadata
* Workflow state references
* Generated media
* Assets
* Logs
* QC reports
* Configuration
* Production manifests

External providers are used only for capabilities that require them.

---

# 48. Offline Behavior

When network access is unavailable:

The application must still allow:

* Opening the application.
* Viewing previous productions.
* Viewing local metadata.
* Previewing local videos.
* Performing deterministic local media processing.

AI-dependent tasks must enter a waiting state rather than permanently failing the production.

---

# 49. User Interface Requirements

The MVP must provide:

### Dashboard

Displays:

* Recent productions
* Production status
* Completion state
* Output availability

### New Production Modal

Contains:

```text
Production Mode
Genre
Branding Text
Generate
```

### Production Detail

Displays:

* Production status
* Current stage
* Progress
* Generated outputs
* Metadata
* QC result

---

# 50. Production Detail View

When production completes, the user must be able to see:

```text
16:9 Master
[ Preview ] [ Open / Export ]

9:16 Short
[ Preview ] [ Open / Export ]

Metadata
Title
Description
Hashtags

Quality
Passed
```

The UI must reference the locally stored artifacts.

---

# 51. No Manual Editing Requirement

The MVP does not require a timeline editor.

The user's responsibility ends after configuring the production and clicking Generate.

The system is responsible for producing the complete package.

---

# 52. Metadata Structure

The final metadata must use the following structure:

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

# 53. Production Output Contract

Every successful production must produce:

```text
Production
│
├── 16:9 Long Video
├── 9:16 Short Video
└── Metadata
    ├── Master Metadata
    └── Short Metadata
```

A production cannot be marked `COMPLETED` if any required output is missing.

---

# 54. Performance Requirements

The application must remain responsive while a production is running.

Long-running operations must execute outside the frontend request lifecycle.

The UI must receive progress information asynchronously.

---

# 55. Resource Constraints

The product must be optimized for the target development hardware:

```text
AMD Ryzen 5 7430U
16 GB RAM
Integrated Radeon Graphics
Windows 11 Pro
```

The system should initially limit active rendering to one production at a time.

The application must avoid unnecessary RAM consumption.

---

# 56. Disk Requirements

Before starting a production, the system should verify that sufficient disk space exists.

The system must account for:

* Generated audio
* Background images
* Intermediate files
* Video encoding
* Final videos
* Temporary files

If insufficient space is detected, production should not start.

---

# 57. Configuration

The following must be configurable:

```text
Music provider
Image provider
LLM provider
Trend provider
Long-form duration
Short-form duration
Master resolution
Short resolution
FPS
Visualizer style
Branding position
Branding opacity
Rendering profile
Provider mode
```

Production-specific settings must be captured in the production manifest.

---

# 58. Content Consistency

The system must maintain a consistent creative identity between:

```text
Music
Background
Radio
Visualizer
Branding
Master
Short
Metadata
```

The short must feel like a derivative of the same production rather than an unrelated video.

---

# 59. Content Duplication Prevention

The system should consider historical productions when creating new content.

It should attempt to avoid:

* Identical music concepts
* Identical visual concepts
* Repeated backgrounds
* Repeated metadata
* Excessively similar creative combinations

Semantic memory may be used for this purpose.

---

# 60. AI Agent Product Requirements

The system must contain the following logical agents:

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

Each agent must have a clearly defined responsibility.

---

# 61. Orchestrator Agent Requirements

The Orchestrator Agent must:

* Coordinate creative decisions.
* Invoke appropriate agents.
* Respect production state.
* Use registered capabilities.
* Handle creative workflow decisions.

The Orchestrator Agent must not directly:

* Execute shell commands.
* Execute FFmpeg.
* Access provider SDKs.
* Modify database records directly.
* Access secrets.

---

# 62. Trend Research Agent Requirements

The Trend Research Agent must:

1. Receive available trend data.
2. Analyze trend signals.
3. Identify relevant genres or themes.
4. Produce structured recommendations.
5. Provide confidence and reasoning.

---

# 63. Music Strategy Agent Requirements

The Music Strategy Agent must:

1. Receive genre/trend context.
2. Define music characteristics.
3. Explicitly enforce instrumental-only requirements.
4. Produce structured music strategy output.

---

# 64. Music Generation Agent Requirements

The Music Generation Agent must:

1. Receive a validated music strategy.
2. Select an available music generation capability.
3. Generate or obtain music.
4. Return the generated asset.
5. Allow provider failover when configured.

---

# 65. Visual Strategy Agent Requirements

The Visual Strategy Agent must:

1. Receive music and trend context.
2. Define the visual environment.
3. Define radio style.
4. Define composition.
5. Ensure the radio can contain the visualizer.
6. Produce structured visual strategy output.

---

# 66. Visual Generation Agent Requirements

The Visual Generation Agent must:

1. Search for a suitable existing asset when applicable.
2. Generate a new background when necessary.
3. Validate the result.
4. Return a usable visual asset.

---

# 67. Short Selection Agent Requirements

The Short Selection Agent must:

1. Analyze the production audio characteristics.
2. Identify a suitable segment.
3. Return start time and duration.
4. Provide a selection reason.
5. Ensure the segment can stand independently.

---

# 68. Metadata Agent Requirements

The Metadata Agent must:

1. Receive production context.
2. Generate master metadata.
3. Generate short metadata.
4. Validate metadata structure.
5. Avoid misleading claims.
6. Avoid keyword stuffing.

---

# 69. Quality Control Agent Requirements

The Quality Control Agent must:

1. Receive technical QC results.
2. Inspect creative quality.
3. Identify issues.
4. Produce a structured QC report.
5. Approve or reject the production.

---

# 70. AI Output Validation

All structured AI outputs must be validated before being consumed by downstream services.

Required flow:

```text
AI Output
    ↓
Schema Validation
    ↓
Application Model
    ↓
Workflow
```

Invalid AI output must not silently enter the production pipeline.

---

# 71. Production History

The application must retain production history locally.

Users should be able to see:

```text
Production ID
Date
Genre
Mode
Status
Master
Short
```

Historical productions may be used by deduplication and semantic memory.

---

# 72. Search and Discovery

The MVP should provide enough production history functionality to locate previous productions.

Advanced media search is not required for MVP.

---

# 73. Quality of Final Video

The final master must:

* Play successfully.
* Contain valid audio.
* Contain valid video.
* Maintain correct aspect ratio.
* Contain the radio.
* Contain the visualizer.
* Contain branding when provided.
* Match the selected creative direction.

The short must satisfy equivalent requirements in its 9:16 format.

---

# 74. User Notifications

The UI must provide clear production state feedback.

Examples:

```text
Production started
Generating instrumental music
Generating visual background
Rendering master video
Generating short video
Generating metadata
Quality check completed
Production completed
```

For failures:

```text
Production failed
Reason: Music provider unavailable
Action: Retry
```

---

# 75. Error Transparency

The UI must not display generic errors when a useful actionable error is available.

Bad:

```text
Something went wrong.
```

Preferred:

```text
Music generation failed because the selected provider
returned a rate-limit error.

The production can be retried or another configured
provider can be used.
```

---

# 76. Production Cancellation

The system should support cancellation of an active production.

Cancellation must:

* Stop future workflow stages.
* Safely terminate applicable processing.
* Preserve already generated valid artifacts.
* Mark the production appropriately.

Cancellation must not corrupt existing files.

---

# 77. Production Retry

A failed production must expose a retry action when applicable.

Retry behavior should reuse valid existing artifacts.

Example:

```text
Music READY
Visual READY
Master FAILED

Retry
   ↓
Render Master
```

The system must not unnecessarily restart from the beginning.

---

# 78. Production Reproducibility

A completed production must contain enough information to understand how it was generated.

The manifest should identify:

* Input
* Configuration
* Prompt versions
* Providers
* Models
* Assets
* Render profile
* Output hashes
* QC results

---

# 79. MVP Acceptance Criteria

The MVP is accepted when the following complete flow works:

```text
1. User opens application.
2. User clicks New.
3. User selects Genre.
4. User selects a genre.
5. User enters optional branding.
6. User clicks Generate.
7. Production starts.
8. Music strategy is created.
9. Instrumental music is generated.
10. Music is validated.
11. Visual strategy is created.
12. Background is generated or selected.
13. Radio is selected or generated.
14. Audio is analyzed.
15. Visualizer is generated.
16. 16:9 master is rendered.
17. Short segment is selected.
18. 9:16 short is rendered.
19. Metadata is generated.
20. Technical QC runs.
21. Creative QC runs.
22. Production passes.
23. Final artifacts are stored locally.
24. User can access both videos and metadata.
```

---

# 80. Trending Mode Acceptance Criteria

Trending mode is accepted when:

```text
1. User selects Trending.
2. User clicks Generate.
3. System retrieves available trend signals.
4. Trend engine evaluates signals.
5. AI interprets the trend.
6. A genre/theme is selected.
7. Music strategy is generated.
8. Visual strategy is generated.
9. The standard production pipeline continues.
10. Final outputs are produced.
```

The user must not be required to manually choose the trending genre.

---

# 81. Failure Recovery Acceptance Criteria

The system is accepted when:

```text
1. A production reaches a completed intermediate stage.
2. A later stage fails.
3. The user retries.
4. Previously completed stages are reused.
5. Only the failed stage and necessary downstream stages execute again.
```

---

# 82. Local Storage Acceptance Criteria

After successful production:

```text
production/
├── master-16x9.mp4
├── short-9x16.mp4
├── metadata.json
├── production.json
└── qc-report.json
```

must exist and be valid.

---

# 83. Provider Independence Acceptance Criteria

The application must be able to replace a provider without modifying the production workflow logic.

Example:

```text
Music Provider A
        ↓
replace
        ↓
Music Provider B
```

The Music Generation Agent and Production Workflow must remain unchanged.

---

# 84. Mock Mode Acceptance Criteria

The complete production workflow must be executable without external AI APIs.

Mock mode must generate deterministic test artifacts.

This allows:

* Development
* Automated testing
* CI
* Debugging
* Workflow validation

without consuming external API quotas.

---

# 85. Security Acceptance Criteria

The product must ensure:

```text
✓ API keys are not committed
✓ Agents cannot access secrets directly
✓ Arbitrary shell execution is blocked
✓ Filesystem paths are validated
✓ Generated filenames are sanitized
✓ Provider credentials are protected
```

---

# 86. Performance Acceptance Criteria

On the target machine:

```text
AMD Ryzen 5 7430U
16 GB RAM
Windows 11 Pro
```

the application must:

* Remain responsive during production.
* Avoid excessive RAM usage.
* Process one active production render initially.
* Clean temporary files.
* Avoid unnecessary duplication of large media files.

Exact timing targets must be established through implementation benchmarking rather than assumed at the PRD level.

---

# 87. Product Success Metrics

Initial product metrics should include:

### Production Completion Rate

Percentage of productions that complete successfully.

### Stage Failure Rate

Percentage of failures by production stage.

### Average Production Duration

Time from Generate to Completed.

### Retry Rate

Percentage of productions requiring retry.

### Provider Failure Rate

Failure rate by provider.

### Duplicate Generation Rate

Percentage of unnecessary duplicate asset generation.

### QC Failure Rate

Percentage of productions failing quality control.

---

# 88. Product Success Definition

The product is considered successful when a user can consistently go from:

```text
New
 ↓
Genre / Trending
 ↓
Branding
 ↓
Generate
```

to:

```text
16:9 Master
+
9:16 Short
+
Metadata
```

without manually editing the content.

---

# 89. Requirements Traceability

The PRD must remain traceable to MAD-001.

| Product Requirement Area | MAD-001 Reference   |
| ------------------------ | ------------------- |
| Local-first              | Sections 3, 47      |
| Provider abstraction     | Sections 3, 35–38   |
| AI agents                | Sections 33–36      |
| Trend discovery          | Sections 15–16      |
| Instrumental music       | Sections 17–19      |
| Visual generation        | Sections 20–22      |
| Audio visualizer         | Sections 23–24      |
| 16:9 master              | Sections 24–26      |
| 9:16 short               | Sections 25–27      |
| Metadata                 | Sections 29–30      |
| QC                       | Sections 31–32      |
| Retry / recovery         | Sections 13, 37, 51 |
| SQLite                   | Sections 10, 50     |
| Filesystem storage       | Sections 11, 40     |
| Temporal                 | Sections 9, 45      |
| Cost-aware providers     | Sections 38–39      |
| Deduplication            | Section 41          |
| Performance              | Sections 43–44      |
| Security                 | Sections 47–48      |
| Testing                  | Sections 57–58      |
| Future extensibility     | Sections 83–85      |

---

# 90. Requirements Priority

Requirements use the following priority levels:

```text
P0 — Mandatory for MVP
P1 — Required after core MVP
P2 — Future enhancement
```

### P0

* New production
* Genre mode
* Trending mode
* Branding
* AI planning
* Instrumental music generation
* Visual generation
* Audio analysis
* Visualizer
* 16:9 master
* 9:16 short
* Short selection
* Metadata
* Technical QC
* Local storage
* Retry
* Resume
* Mock providers
* Provider abstraction

### P1

* Advanced deduplication
* Advanced semantic memory
* Multiple simultaneous productions
* Advanced provider routing
* Advanced performance optimization

### P2

* Publishing agents
* Platform integrations
* Analytics agents
* A/B testing
* Automated content feedback loop

---

# 91. MVP Product Boundary

The MVP ends here:

```text
                 ┌───────────────┐
                 │     USER      │
                 └───────┬───────┘
                         │
                         ▼
              Genre / Trending
                         │
                         ▼
                     Generate
                         │
                         ▼
                 AI Production
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
       16:9 MP4       9:16 MP4      Metadata
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                  Local Storage
```

Automatic publishing is explicitly outside this boundary.

---

# 92. Final Product Contract

The product accepts:

```text
Production Mode
Genre or Trending
Optional Branding Text
```

The product produces:

```text
One 16:9 long-form instrumental music video
One 9:16 short-form instrumental music video
Master metadata
Short metadata
Production manifest
QC report
```

All final artifacts are stored locally.

---

# 93. Product Architecture Constraint

This PRD does not authorize implementation choices that contradict MAD-001.

In particular:

```text
AI agents must remain provider-agnostic.
Media rendering must remain deterministic.
Long-running production must remain workflow-driven.
Final media must remain locally stored.
Production must remain resumable.
```

Any change to these principles requires an ADR and an update to the architecture baseline.

---

# 94. Final MVP Definition

The AI Instrumental Music Video Production OS MVP is a successful implementation when:

> A user can select a genre or allow the system to identify a current trending genre, optionally enter branding text, click Generate once, and receive a complete instrumental music content package consisting of a 16:9 long-form video, a 9:16 short-form video, and automatically generated metadata, with all artifacts stored locally and the entire production process handled by resumable AI-agent-driven workflows.

---

# 95. Document Status

**PRD-001 v1.0.0**

Status:

**APPROVED**

Parent document:

**MAD-001 v1.0.0**

All subsequent technical specifications must derive their requirements from this PRD and must remain consistent with MAD-001.

**END OF PRD-001**
