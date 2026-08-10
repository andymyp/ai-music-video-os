"""FFmpegMediaEngine — deterministic FFmpeg/FFprobe implementation.

Commands are built as structured argument arrays and executed without a shell
(TDD-001 §92: no ``shell=True``, no unsafe interpolation), so filenames and
filter expressions can never inject a shell command. The default runner uses
``asyncio.create_subprocess_exec`` and terminates the process on cancellation so
long-running renders are safely interrupted (TDD-001 §88). Tests inject a fake
runner to avoid depending on a system FFmpeg; the integration suite exercises
the real binary.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Awaitable, Callable

from api.core.errors import MediaProcessingError
from api.media.models import (
    MASTER_PROFILE,
    SHORT_PROFILE,
    MediaExpectations,
    MediaProbe,
    MediaValidationResult,
    RenderProfile,
    RenderRequest,
    ValidationCheck,
)

#: async runner signature: (cmd: list[str], *, timeout) -> (stdout, stderr)
ProcessRunner = Callable[..., Awaitable[tuple[bytes, bytes]]]


def _fmt(value: float) -> str:
    """Shortest deterministic float representation (e.g. ``184.2``)."""
    return f"{value:g}"


def _escape_filter(value: str) -> str:
    """Escape a value for use inside an FFmpeg filter graph (no shell involved)."""
    return (
        value.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace(",", "\\,")
        .replace("'", "\\'")
        .replace("%", "%%")
    )


def build_render_args(request: RenderRequest, profile: RenderProfile) -> list[str]:
    """Structured FFmpeg arguments for *request* under *profile* (no shell)."""
    args: list[str] = ["-y"]
    # Static image backgrounds/overlays must loop to outlast the audio.
    args += ["-loop", "1", "-i", str(request.background)]
    if request.segment is not None:
        # Trim only the audio input to the selected segment (TDD-001 §129).
        args += ["-ss", _fmt(request.segment.start_seconds)]
        args += ["-t", _fmt(request.segment.duration_seconds)]
    args += ["-i", str(request.audio)]
    for overlay in request.overlays:
        args += ["-loop", "1", "-i", str(overlay.path)]

    args += ["-filter_complex", _build_filter_graph(request, profile)]
    args += ["-map", "[vout]", "-map", "1:a"]
    args += ["-r", str(profile.fps)]
    args += ["-c:v", profile.video_codec]
    if profile.preset:
        args += ["-preset", profile.preset]
    if profile.crf is not None:
        args += ["-crf", str(profile.crf)]
    if profile.video_bitrate:
        args += ["-b:v", profile.video_bitrate]
    args += ["-pix_fmt", profile.pixel_format]
    args += ["-c:a", profile.audio_codec]
    if profile.audio_bitrate:
        args += ["-b:a", profile.audio_bitrate]
    args += ["-shortest", str(request.output_path)]
    return args


def _build_filter_graph(request: RenderRequest, profile: RenderProfile) -> str:
    """Deterministic filter_complex: scale/pad background, overlay layers, branding.

    Background fills the profile resolution (scale + pad to center-crop); each
    overlay is optionally scaled/alpha-mixed and positioned; branding text is
    drawn last. The final stream is labelled ``[vout]``.
    """
    w, h = profile.width, profile.height
    parts = [
        f"[0:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1[base]"
    ]
    current = "base"
    for index, overlay in enumerate(request.overlays):
        src_index = 2 + index
        label = f"ovsrc{index}"
        # Always pass a filter so the relabel is valid (never bare [in][label]).
        if overlay.opacity is not None:
            chain = f"[{src_index}:v]format=rgba,colorchannelmixer=aa={overlay.opacity:.2f}"
        else:
            chain = f"[{src_index}:v]null"
        parts.append(f"{chain}[{label}]")
        src = label
        if overlay.width or overlay.height:
            scaled = f"ovs{index}"
            parts.append(
                f"[{label}]scale={overlay.width or -1}:{overlay.height or -1}[{scaled}]"
            )
            src = scaled
        final = index == len(request.overlays) - 1 and request.branding_font is not None
        out = "vout" if final else f"o{index}"
        parts.append(f"[{current}][{src}]overlay={overlay.x}:{overlay.y}[{out}]")
        current = out
    if request.branding_font is not None:
        text = _escape_filter(request.branding_text or "")
        fontfile = _escape_filter(str(request.branding_font))
        parts.append(
            f"[{current}]drawtext=text='{text}':fontfile='{fontfile}'"
            f":x={request.branding_x}:y={request.branding_y}"
            f":fontsize={request.branding_size}:fontcolor=white[vout]"
        )
    elif current != "vout":
        parts.append(f"[{current}]null[vout]")
    return ";".join(parts)


async def _run_process(cmd: list[str], *, timeout: float | None = None) -> tuple[bytes, bytes]:
    """Run *cmd* as a subprocess (no shell); terminate safely on cancellation."""
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
    except asyncio.CancelledError:
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), 5)
        except (asyncio.TimeoutError, OSError):
            process.kill()
        raise
    except asyncio.TimeoutError:
        process.terminate()
        await process.wait()
        raise MediaProcessingError(
            f"command timed out: {' '.join(cmd[:4])}... (timeout={timeout}s)"
        ) from None
    if process.returncode != 0:
        detail = stderr.decode("utf-8", errors="replace")[-2000:]
        raise MediaProcessingError(f"command failed (exit {process.returncode}): {detail}")
    return stdout, stderr


def _fps_from_stream(stream: dict[str, Any]) -> float | None:
    for key in ("avg_frame_rate", "r_frame_rate"):
        raw = stream.get(key)
        if not raw:
            continue
        try:
            num, den = raw.split("/")
            value = float(num) / float(den)
        except (ValueError, ZeroDivisionError):
            continue
        if value > 0:
            return round(value, 3)
    return None


def probe_to_model(info: dict[str, Any]) -> MediaProbe:
    """Normalize an ffprobe ``-show_format -show_streams`` JSON object."""
    container = info.get("format") or {}
    streams = info.get("streams") or []
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    return MediaProbe(
        duration_seconds=float(container["duration"]) if container.get("duration") is not None else None,
        sample_rate=int(audio["sample_rate"]) if audio and audio.get("sample_rate") else None,
        channels=int(audio["channels"]) if audio and audio.get("channels") else None,
        audio_codec=audio.get("codec_name") if audio else None,
        audio_bit_rate=int(audio["bit_rate"]) if audio and audio.get("bit_rate") else None,
        video_codec=video.get("codec_name") if video else None,
        width=int(video["width"]) if video and video.get("width") else None,
        height=int(video["height"]) if video and video.get("height") else None,
        fps=_fps_from_stream(video) if video else None,
        container_format=container.get("format_name"),
        has_audio=audio is not None,
        has_video=video is not None,
    )


def _check(name: str, passed: bool, *, expected: str | None = None, actual: str | None = None) -> ValidationCheck:
    return ValidationCheck(name=name, passed=passed, expected=expected, actual=actual)


def run_validation_checks(
    probe: MediaProbe,
    expectations: MediaExpectations,
    *,
    exists: bool,
) -> MediaValidationResult:
    """Evaluate *probe* against *expectations* (PRD-001 §18 media checks)."""
    checks: list[ValidationCheck] = [_check("exists", exists)]
    if not exists:
        return MediaValidationResult(valid=False, checks=checks)

    def exact(value: float | int | None, expected: float | int | str | None, *, tolerance: float = 0.0) -> bool:
        if expected is None:
            return True
        return value is not None and abs(value - expected) <= tolerance

    def at_least(value: float | int | None, expected: float | int | None, *, tolerance: float = 0.0) -> bool:
        if expected is None:
            return True
        return value is not None and value >= expected - tolerance

    def at_most(value: float | int | None, expected: float | int | None, *, tolerance: float = 0.0) -> bool:
        if expected is None:
            return True
        return value is not None and value <= expected + tolerance

    checks.append(_check("audio_present", (not expectations.require_audio) or probe.has_audio))
    checks.append(_check("video_present", (not expectations.require_video) or probe.has_video))
    checks.append(
        _check(
            "duration_min",
            at_least(probe.duration_seconds, expectations.min_duration, tolerance=1.0),
            expected=f">={expectations.min_duration}",
            actual=_fmt(probe.duration_seconds) if probe.duration_seconds is not None else None,
        )
    )
    checks.append(
        _check(
            "duration_max",
            at_most(probe.duration_seconds, expectations.max_duration, tolerance=1.0),
            expected=f"<={expectations.max_duration}",
            actual=_fmt(probe.duration_seconds) if probe.duration_seconds is not None else None,
        )
    )
    checks.append(
        _check(
            "resolution",
            exact(probe.width, expectations.width) and exact(probe.height, expectations.height),
            expected=f"{expectations.width}x{expectations.height}",
            actual=f"{probe.width}x{probe.height}" if probe.width and probe.height else None,
        )
    )
    checks.append(
        _check(
            "fps",
            exact(probe.fps, expectations.fps, tolerance=0.5),
            expected=str(expectations.fps),
            actual=_fmt(probe.fps) if probe.fps is not None else None,
        )
    )
    checks.append(
        _check(
            "sample_rate_min",
            at_least(probe.sample_rate, expectations.min_sample_rate, tolerance=100),
            expected=f">={expectations.min_sample_rate}",
            actual=str(probe.sample_rate) if probe.sample_rate is not None else None,
        )
    )
    checks.append(
        _check(
            "channels_min",
            at_least(probe.channels, expectations.min_channels),
            expected=f">={expectations.min_channels}",
            actual=str(probe.channels) if probe.channels is not None else None,
        )
    )
    checks.append(
        _check(
            "audio_codec",
            expectations.audio_codec is None or probe.audio_codec == expectations.audio_codec,
            expected=expectations.audio_codec,
            actual=probe.audio_codec,
        )
    )
    checks.append(
        _check(
            "video_codec",
            expectations.video_codec is None or probe.video_codec == expectations.video_codec,
            expected=expectations.video_codec,
            actual=probe.video_codec,
        )
    )
    return MediaValidationResult(valid=all(check.passed for check in checks), checks=checks)


class FFmpegMediaEngine:
    """Deterministic media engine backed by FFmpeg/FFprobe (TDD-001 §125).

    ``runner`` is injectable for unit tests; the default is :func:`_run_process`.
    """

    def __init__(
        self,
        *,
        ffmpeg_bin: str = "ffmpeg",
        ffprobe_bin: str = "ffprobe",
        runner: ProcessRunner | None = None,
    ) -> None:
        self._ffmpeg = ffmpeg_bin
        self._ffprobe = ffprobe_bin
        self._runner = runner or _run_process

    # --- render ------------------------------------------------------------

    async def render_master(
        self,
        request: RenderRequest,
        profile: RenderProfile = MASTER_PROFILE,
    ) -> Path:
        return await self._render(request, profile)

    async def render_short(
        self,
        request: RenderRequest,
        profile: RenderProfile = SHORT_PROFILE,
    ) -> Path:
        return await self._render(request, profile)

    async def _render(self, request: RenderRequest, profile: RenderProfile) -> Path:
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        args = [self._ffmpeg, "-loglevel", "error", *build_render_args(request, profile)]
        await self._runner(args)
        return request.output_path

    # --- probe / validate --------------------------------------------------

    async def analyze_audio(self, path: Path) -> MediaProbe:
        return probe_to_model(await self._probe(path))

    async def validate_media(
        self,
        path: Path,
        *,
        expectations: MediaExpectations | None = None,
    ) -> MediaValidationResult:
        expectations = expectations or MediaExpectations()
        if not Path(path).is_file():
            return run_validation_checks(MediaProbe(), expectations, exists=False)
        try:
            probe = probe_to_model(await self._probe(path))
        except MediaProcessingError as exc:
            result = run_validation_checks(MediaProbe(), expectations, exists=True)
            return MediaValidationResult(
                valid=False,
                checks=[_check("readable", False, actual=str(exc))],
            )
        return run_validation_checks(probe, expectations, exists=True)

    async def _probe(self, path: Path) -> dict[str, Any]:
        args = [
            self._ffprobe,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
        stdout, _ = await self._runner(args)
        return json.loads(stdout.decode("utf-8"))

    # --- extract -----------------------------------------------------------

    async def extract_audio(self, source: Path, output_path: Path, *, codec: str = "pcm_s16le") -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        args = [
            self._ffmpeg,
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-vn",
            "-acodec",
            codec,
            str(output_path),
        ]
        await self._runner(args)
        return output_path

    async def extract_segment(
        self,
        source: Path,
        output_path: Path,
        start: float,
        duration: float | None = None,
        *,
        codec: str = "copy",
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        args = [self._ffmpeg, "-loglevel", "error", "-y", "-ss", _fmt(start), "-i", str(source)]
        if duration is not None:
            args += ["-t", _fmt(duration)]
        args += ["-c", codec, str(output_path)]
        await self._runner(args)
        return output_path
