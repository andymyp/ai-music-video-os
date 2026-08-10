# FFmpeg / FFprobe

FFmpeg and FFprobe are the deterministic media-processing engine (MAD-001
ADR-007, §19, §24). They must be available on `PATH`:

```bash
ffmpeg --version
ffprobe --version
```

Installation (Windows): download an essentials build from
https://www.gyan.dev/ffmpeg/builds/ and add the `bin` directory to `PATH`, or
install via `winget install Gyan.FFmpeg`.

## Usage rules

- The media engine (Phase 06) invokes FFmpeg with **structured argument
  arrays** — never `shell=True` or interpolated shell strings (TDD-001 §92).
- All encoding parameters are driven by externalized render profiles
  (MAD-001 §56), not hard-coded in application code.
- Long-running renders must run in a single render worker by default
  (MAD-001 §43) and be safely terminable on cancellation (TDD-001 §86).
