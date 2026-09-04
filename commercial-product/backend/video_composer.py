"""BossAI final-video composition.

Builds the customer deliverable from an already generated BossAI digital-human
clip by burning in subtitles and a banner title and mixing background music with
the locally installed FFmpeg.

Design constraints that this module deliberately honours:

* No media is bundled with the product. Background music and fonts are read from
  the customer's own local BossAI asset directory or from fonts the customer has
  already installed on the machine, so the product ships no third-party media
  whose redistribution rights are not established.
* Subtitle and title text are passed to FFmpeg through ``textfile=`` and the
  font through ``fontfile=`` inside a per-job working directory. FFmpeg runs with
  that directory as its working directory, so no Windows drive letter or
  punctuation ever has to be escaped into a filter graph.
* Timing is derived from the rendered voiceover duration; the product has no
  speech-recognition runtime, so segment timing is distributed across the
  measured duration proportionally to segment length.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

AUDIO_SUFFIXES = frozenset({".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"})
FONT_SUFFIXES = frozenset({".ttf", ".otf", ".ttc"})
IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp"})
VIDEO_SUFFIXES = frozenset({".mp4", ".mov", ".webm", ".mkv"})
MEDIA_SUFFIXES = IMAGE_SUFFIXES | VIDEO_SUFFIXES
MAX_BGM_BYTES = 64 * 1024 * 1024
MAX_MEDIA_BYTES = 512 * 1024 * 1024

# Inset placement, expressed against the overlay filter's main/overlay sizes.
_PIP_CORNERS = {
    "top-left": ("{m}", "{m}"),
    "top-right": ("main_w-overlay_w-{m}", "{m}"),
    "bottom-left": ("{m}", "main_h-overlay_h-{m}"),
    "bottom-right": ("main_w-overlay_w-{m}", "main_h-overlay_h-{m}"),
    "center": ("(main_w-overlay_w)/2", "(main_h-overlay_h)/2"),
}

SENTENCE_END = "。！？!?；;\n\r"
SOFT_BREAK = "，,、：:—- "
MIN_SEGMENT_SECONDS = 0.7
DEFAULT_LINE_CHARS = 18
MAX_SUBTITLE_LINES = 2

# Vertical placement as a fraction of frame height, keyed by the UI position.
_POSITION_Y = {
    "top": "h*0.07",
    "center": "(h-text_h)/2",
    "bottom": "h-text_h-h*0.08",
}


class CompositionError(RuntimeError):
    """Raised when the local FFmpeg runtime cannot produce the final video."""


@dataclass(frozen=True)
class Segment:
    """One on-screen subtitle line group with its display window."""

    text: str
    start: float
    end: float


@dataclass(frozen=True)
class SubtitleStyle:
    enabled: bool = True
    font_file: str = ""
    position: str = "bottom"
    font_size: int = 60
    color: str = "#ffffff"
    stroke_color: str = "#000000"
    stroke_width: float = 1.5
    line_chars: int = DEFAULT_LINE_CHARS


@dataclass(frozen=True)
class TitleStyle:
    enabled: bool = False
    text: str = ""
    font_file: str = ""
    position: str = "top"
    font_size: int = 60
    color: str = "#ffffff"
    stroke_color: str = "#000000"
    stroke_width: float = 1.25


@dataclass(frozen=True)
class AudioMix:
    bgm_path: Path | None = None
    bgm_volume: int = 13
    voice_volume: int = 100


@dataclass(frozen=True)
class PictureInPicture:
    """A customer-supplied image or clip inset over the main video.

    ``scale_percent`` and ``margin_percent`` are both measured against the
    output frame width, not against the supplied asset, so the same settings
    produce the same on-screen result for any source resolution.
    """

    media_path: Path | None = None
    corner: str = "top-right"
    scale_percent: int = 28
    margin_percent: int = 4
    opacity: int = 100
    start: float = 0.0
    end: float = 0.0  # 0 means "until the end of the video"

    @property
    def enabled(self) -> bool:
        return self.media_path is not None and self.media_path.is_file()


@dataclass(frozen=True)
class CoverStyle:
    """Text burned onto an exported cover image."""

    text: str = ""
    font_file: str = ""
    position: str = "center"
    font_size: int = 96
    color: str = "#ffffff"
    stroke_color: str = "#000000"
    stroke_width: float = 3.0
    line_chars: int = 9


def _no_window_kwargs() -> dict[str, Any]:
    """Keep FFmpeg from flashing a console window inside the packaged app."""
    if os.name != "nt":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {"startupinfo": startupinfo, "creationflags": subprocess.CREATE_NO_WINDOW}


def ffmpeg_executable() -> str:
    explicit = os.environ.get("BOSSAI_FFMPEG_BIN", "").strip().strip('"')
    if explicit:
        candidate = Path(explicit)
        if candidate.is_dir():
            candidate = candidate / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        if candidate.is_file():
            return str(candidate.resolve())
    found = shutil.which("ffmpeg.exe") or shutil.which("ffmpeg")
    return str(Path(found).resolve()) if found else ""


def ffprobe_executable() -> str:
    """Locate ffprobe next to the resolved ffmpeg before falling back to PATH."""
    ffmpeg = ffmpeg_executable()
    if ffmpeg:
        sibling = Path(ffmpeg).with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
        if sibling.is_file():
            return str(sibling.resolve())
    found = shutil.which("ffprobe.exe") or shutil.which("ffprobe")
    return str(Path(found).resolve()) if found else ""


def has_drawtext_filter() -> bool:
    """Report whether the local FFmpeg was built with the drawtext filter."""
    ffmpeg = ffmpeg_executable()
    if not ffmpeg:
        return False
    try:
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-filters"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            **_no_window_kwargs(),
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return " drawtext " in (result.stdout or "")


def inspect_setup() -> dict[str, Any]:
    """Describe whether final-video composition can run on this machine."""
    ffmpeg = ffmpeg_executable()
    ffprobe = ffprobe_executable()
    missing: list[str] = []
    if not ffmpeg:
        missing.append("ffmpeg-runtime")
    if not ffprobe:
        missing.append("ffprobe-runtime")
    drawtext = bool(ffmpeg) and has_drawtext_filter()
    if ffmpeg and not drawtext:
        missing.append("ffmpeg-drawtext-filter")
    return {
        "ready": not missing,
        "missing": missing,
        "ffmpegAvailable": bool(ffmpeg),
        "ffprobeAvailable": bool(ffprobe),
        "drawtextAvailable": drawtext,
    }


def probe_duration(path: Path) -> float:
    """Return the media duration in seconds, or 0.0 when it cannot be read."""
    ffprobe = ffprobe_executable()
    if not ffprobe:
        return 0.0
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            **_no_window_kwargs(),
        )
    except (OSError, subprocess.SubprocessError):
        return 0.0
    try:
        return max(0.0, float((result.stdout or "").strip()))
    except ValueError:
        return 0.0


def probe_video_size(path: Path) -> tuple[int, int]:
    """Return the video frame size in pixels, or (0, 0) when it cannot be read."""
    ffprobe = ffprobe_executable()
    if not ffprobe:
        return 0, 0
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            **_no_window_kwargs(),
        )
    except (OSError, subprocess.SubprocessError):
        return 0, 0
    values = [line.strip() for line in (result.stdout or "").splitlines() if line.strip().isdigit()]
    if len(values) < 2:
        return 0, 0
    return int(values[0]), int(values[1])


def _display_width(text: str) -> int:
    """Count CJK/full-width characters as two columns when wrapping lines."""
    return sum(2 if unicodedata.east_asian_width(char) in "WF" else 1 for char in text)


def _wrap(text: str, line_chars: int) -> str:
    """Wrap one segment into display lines using a column budget."""
    budget = max(8, line_chars) * 2
    if _display_width(text) <= budget:
        return text

    # Latin-style text wraps on word boundaries; CJK wraps on character columns.
    if " " in text.strip() and _display_width(text) == len(text):
        lines: list[str] = []
        current = ""
        for word in text.split():
            candidate = f"{current} {word}".strip()
            if _display_width(candidate) > budget and current:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        return "\n".join(lines)

    lines = []
    current = ""
    width = 0
    for char in text:
        char_width = 2 if unicodedata.east_asian_width(char) in "WF" else 1
        if width + char_width > budget and current:
            lines.append(current)
            current = char
            width = char_width
        else:
            current += char
            width += char_width
    if current:
        lines.append(current)
    # Every line is kept: an over-long caption is better than one that silently
    # drops the end of what the presenter actually says.
    return "\n".join(lines)


def split_script(script_text: str, line_chars: int = DEFAULT_LINE_CHARS) -> list[str]:
    """Split a talking script into subtitle-sized chunks."""
    normalized = re.sub(r"[ \t]+", " ", str(script_text or "")).strip()
    if not normalized:
        return []

    sentences: list[str] = []
    buffer = ""
    for char in normalized:
        buffer += char
        if char in SENTENCE_END:
            candidate = buffer.strip()
            if candidate:
                sentences.append(candidate)
            buffer = ""
    if buffer.strip():
        sentences.append(buffer.strip())

    budget = max(8, line_chars) * 2 * MAX_SUBTITLE_LINES
    chunks: list[str] = []
    for sentence in sentences:
        if _display_width(sentence) <= budget:
            chunks.append(sentence)
            continue
        # Long sentences are broken again at soft punctuation so a single caption
        # never overflows the frame.
        piece = ""
        for char in sentence:
            piece += char
            if char in SOFT_BREAK and _display_width(piece) >= budget * 0.6:
                chunks.append(piece.strip())
                piece = ""
        if piece.strip():
            chunks.append(piece.strip())
    return [chunk for chunk in chunks if chunk]


def build_segments(script_text: str, duration: float, line_chars: int = DEFAULT_LINE_CHARS) -> list[Segment]:
    """Distribute the script across the measured duration proportionally."""
    chunks = split_script(script_text, line_chars)
    if not chunks or duration <= 0:
        return []

    weights = [max(1, len(chunk)) for chunk in chunks]
    total_weight = sum(weights)
    segments: list[Segment] = []
    cursor = 0.0
    for index, (chunk, weight) in enumerate(zip(chunks, weights)):
        share = duration * weight / total_weight
        start = cursor
        end = duration if index == len(chunks) - 1 else min(duration, start + share)
        if end - start < MIN_SEGMENT_SECONDS and index != len(chunks) - 1:
            end = min(duration, start + MIN_SEGMENT_SECONDS)
        if end <= start:
            continue
        segments.append(Segment(text=_wrap(chunk, line_chars), start=round(start, 3), end=round(end, 3)))
        cursor = end
        if cursor >= duration:
            break
    return segments


def _hex_color(value: str, fallback: str) -> str:
    text = str(value or "").strip()
    match = re.fullmatch(r"#?([0-9a-fA-F]{6})", text)
    if not match:
        match = re.fullmatch(r"#?([0-9a-fA-F]{6})", fallback)
    return f"0x{match.group(1).lower()}" if match else "0xffffff"


def _position_expr(position: str, fallback: str) -> str:
    key = str(position or "").strip().lower()
    return _POSITION_Y.get(key) or _POSITION_Y[fallback]


def list_bgm(bgm_dir: Path) -> list[dict[str, Any]]:
    """List the customer's own background-music files."""
    if not bgm_dir.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(bgm_dir.iterdir(), key=lambda item: item.name.lower()):
        if path.is_file() and path.suffix.lower() in AUDIO_SUFFIXES:
            items.append(
                {
                    "fileName": path.name,
                    "displayName": path.stem,
                    "sizeBytes": path.stat().st_size,
                    "source": "customer-provided",
                }
            )
    return items


def _font_directories() -> list[Path]:
    directories: list[Path] = []
    if os.name == "nt":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        directories.append(Path(windir) / "Fonts")
        local = os.environ.get("LOCALAPPDATA")
        if local:
            directories.append(Path(local) / "Microsoft" / "Windows" / "Fonts")
    else:
        directories.extend([Path("/usr/share/fonts"), Path.home() / ".fonts"])
    return [item for item in directories if item.is_dir()]


def list_subtitle_fonts(extra_dir: Path | None = None) -> list[dict[str, Any]]:
    """List fonts already installed on the customer machine.

    The product never redistributes font files; it only references fonts the
    customer already has, plus any font they place in their own BossAI asset
    directory.
    """
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    directories = list(_font_directories())
    if extra_dir and extra_dir.is_dir():
        directories.insert(0, extra_dir)
    for directory in directories:
        try:
            entries = sorted(directory.iterdir(), key=lambda item: item.name.lower())
        except OSError:
            continue
        for path in entries:
            if not path.is_file() or path.suffix.lower() not in FONT_SUFFIXES:
                continue
            key = path.name.lower()
            if key in seen:
                continue
            seen.add(key)
            items.append({"fileName": path.name, "displayName": path.stem, "path": str(path)})
    return items


def resolve_font(file_name: str, extra_dir: Path | None = None) -> Path | None:
    """Resolve a font choice to a real file, ignoring any path component."""
    name = Path(str(file_name or "").strip()).name
    if not name:
        return None
    for font in list_subtitle_fonts(extra_dir):
        if font["fileName"].lower() == name.lower():
            return Path(font["path"])
    return None


def default_font(extra_dir: Path | None = None) -> Path | None:
    """Pick a readable default that covers Chinese and Latin text."""
    preferred = ("msyh.ttc", "msyh.ttf", "msyhbd.ttc", "simhei.ttf", "deng.ttf", "simsun.ttc", "arial.ttf")
    fonts = list_subtitle_fonts(extra_dir)
    lookup = {font["fileName"].lower(): Path(font["path"]) for font in fonts}
    for name in preferred:
        if name in lookup:
            return lookup[name]
    return Path(fonts[0]["path"]) if fonts else None


def _drawtext(
    *,
    text_file: str,
    font_file: str,
    font_size: int,
    color: str,
    stroke_color: str,
    stroke_width: float,
    y_expr: str,
    enable: str = "",
) -> str:
    """Build one drawtext filter.

    Text comes from a file and the font from a file, so no caption content or
    Windows path ever needs filter-graph escaping.
    """
    parts = [
        f"textfile={text_file}",
        f"fontfile={font_file}",
        f"fontsize={max(12, int(font_size))}",
        f"fontcolor={color}",
        f"borderw={max(0, round(float(stroke_width)))}",
        f"bordercolor={stroke_color}",
        "line_spacing=8",
        "x=(w-text_w)/2",
        f"y={y_expr}",
    ]
    if enable:
        parts.append(f"enable='{enable}'")
    return "drawtext=" + ":".join(parts)


def _build_filters(
    work_dir: Path,
    segments: Sequence[Segment],
    subtitle: SubtitleStyle,
    subtitle_font: Path | None,
    title: TitleStyle,
    title_font: Path | None,
) -> list[str]:
    filters: list[str] = []

    if subtitle.enabled and segments and subtitle_font is not None:
        font_name = "subtitle-font" + subtitle_font.suffix.lower()
        shutil.copyfile(subtitle_font, work_dir / font_name)
        color = _hex_color(subtitle.color, "#ffffff")
        stroke = _hex_color(subtitle.stroke_color, "#000000")
        y_expr = _position_expr(subtitle.position, "bottom")
        for index, segment in enumerate(segments):
            text_name = f"subtitle-{index:04d}.txt"
            (work_dir / text_name).write_text(segment.text, encoding="utf-8")
            filters.append(
                _drawtext(
                    text_file=text_name,
                    font_file=font_name,
                    font_size=subtitle.font_size,
                    color=color,
                    stroke_color=stroke,
                    stroke_width=subtitle.stroke_width,
                    y_expr=y_expr,
                    enable=f"between(t,{segment.start:.3f},{segment.end:.3f})",
                )
            )

    if title.enabled and title.text.strip() and title_font is not None:
        font_name = "title-font" + title_font.suffix.lower()
        if not (work_dir / font_name).exists():
            shutil.copyfile(title_font, work_dir / font_name)
        (work_dir / "title.txt").write_text(title.text.strip(), encoding="utf-8")
        filters.append(
            _drawtext(
                text_file="title.txt",
                font_file=font_name,
                font_size=title.font_size,
                color=_hex_color(title.color, "#ffffff"),
                stroke_color=_hex_color(title.stroke_color, "#000000"),
                stroke_width=title.stroke_width,
                y_expr=_position_expr(title.position, "top"),
            )
        )

    return filters


def _volume(percent: int) -> float:
    return max(0, min(400, int(percent))) / 100.0


def compose(
    *,
    source_video: Path,
    output_path: Path,
    work_dir: Path,
    script_text: str = "",
    subtitle: SubtitleStyle | None = None,
    title: TitleStyle | None = None,
    audio: AudioMix | None = None,
    pip: PictureInPicture | None = None,
    asset_font_dir: Path | None = None,
    on_progress: Callable[[int, str], None] | None = None,
) -> dict[str, Any]:
    """Render the final customer video.

    Returns a summary describing what was actually burned in, so the UI never
    claims an edit that FFmpeg did not perform.
    """
    subtitle = subtitle or SubtitleStyle(enabled=False)
    title = title or TitleStyle(enabled=False)
    audio = audio or AudioMix()
    pip = pip or PictureInPicture()

    ffmpeg = ffmpeg_executable()
    if not ffmpeg:
        raise CompositionError(
            "FFmpeg is not available on this machine. Install the FFmpeg runtime from Settings before rendering."
        )

    duration = probe_duration(source_video)
    frame_width, _frame_height = probe_video_size(source_video)
    segments: list[Segment] = []
    if subtitle.enabled:
        segments = build_segments(script_text, duration, subtitle.line_chars)

    subtitle_font = resolve_font(subtitle.font_file, asset_font_dir) or default_font(asset_font_dir)
    title_font = resolve_font(title.font_file, asset_font_dir) or subtitle_font

    if subtitle.enabled and segments and subtitle_font is None:
        raise CompositionError("No usable font was found for subtitles. Install a system font or choose one in Settings.")
    if title.enabled and title.text.strip() and title_font is None:
        raise CompositionError("No usable font was found for the banner title.")

    work_dir.mkdir(parents=True, exist_ok=True)
    filters = _build_filters(work_dir, segments, subtitle, subtitle_font, title, title_font)

    bgm_path = audio.bgm_path if audio.bgm_path and audio.bgm_path.is_file() else None
    voice_gain = _volume(audio.voice_volume)
    bgm_gain = _volume(audio.bgm_volume)

    command: list[str] = [ffmpeg, "-hide_banner", "-nostdin", "-y", "-i", str(source_video)]
    next_input = 1

    pip_index = -1
    pip_width_px = 0
    if pip is not None and pip.enabled:
        # The inset is sized against the *output* frame, never against the
        # customer's own asset, so the same percentage looks the same on screen
        # whether they supplied a 100px icon or a 4K logo.
        if frame_width <= 0:
            raise CompositionError(
                "The source video resolution could not be read, so the picture-in-picture size cannot be determined."
            )
        base_width = frame_width - (frame_width % 2)
        scale = max(5, min(100, int(pip.scale_percent)))
        pip_width_px = max(2, min(base_width, round(base_width * scale / 100)))
        pip_width_px -= pip_width_px % 2
        # A still image is looped into a stream; a clip repeats so a short inset
        # still covers the whole video. `-shortest` bounds the result either way.
        if pip.media_path.suffix.lower() in IMAGE_SUFFIXES:
            command += ["-loop", "1", "-i", str(pip.media_path)]
        else:
            command += ["-stream_loop", "-1", "-i", str(pip.media_path)]
        pip_index = next_input
        next_input += 1

    bgm_index = -1
    if bgm_path is not None:
        # Loop the music so a short track still covers the whole clip.
        command += ["-stream_loop", "-1", "-i", str(bgm_path)]
        bgm_index = next_input
        next_input += 1

    video_chain = ",".join(filters)
    graph_parts: list[str] = []

    if pip_index >= 0:
        # The inset goes under the text so subtitles are never obscured by it.
        margin = max(0, min(40, int(pip.margin_percent)))
        opacity = max(1, min(100, int(pip.opacity))) / 100.0
        x_expr, y_expr = _PIP_CORNERS.get(pip.corner, _PIP_CORNERS["top-right"])
        margin_expr = f"main_w*{margin / 100:.4f}"
        overlay_args = [
            f"x={x_expr.format(m=margin_expr)}",
            f"y={y_expr.format(m=margin_expr)}",
        ]
        if pip.start > 0 or pip.end > 0:
            end = pip.end if pip.end > 0 else max(duration, pip.start + 1)
            overlay_args.append(f"enable='between(t,{pip.start:.3f},{end:.3f})'")
        graph_parts.append("[0:v]scale=trunc(iw/2)*2:trunc(ih/2)*2[base]")
        graph_parts.append(
            f"[{pip_index}:v]scale={pip_width_px}:-2,format=rgba,"
            f"colorchannelmixer=aa={opacity:.3f}[pip]"
        )
        graph_parts.append("[base][pip]overlay=" + ":".join(overlay_args) + "[ov]")
        graph_parts.append(f"[ov]{video_chain}[vout]" if video_chain else "[ov]null[vout]")
    elif video_chain or bgm_index >= 0:
        graph_parts.append(f"[0:v]{video_chain}[vout]" if video_chain else "[0:v]null[vout]")

    if bgm_index >= 0:
        graph_parts.append(
            f"[0:a]volume={voice_gain:.3f}[voice];"
            f"[{bgm_index}:a]volume={bgm_gain:.3f}[music];"
            "[voice][music]amix=inputs=2:duration=first:dropout_transition=0[aout]"
        )

    if graph_parts:
        command += ["-filter_complex", ";".join(graph_parts), "-map", "[vout]"]
        command += ["-map", "[aout]" if bgm_index >= 0 else "0:a?"]
        if bgm_index >= 0 or pip_index >= 0:
            command += ["-shortest"]
        if bgm_index < 0 and voice_gain != 1.0:
            command += ["-af", f"volume={voice_gain:.3f}"]
    elif voice_gain != 1.0:
        command += ["-af", f"volume={voice_gain:.3f}"]

    command += [
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        "-progress",
        "pipe:1",
        "-nostats",
        str(output_path),
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    _run_with_progress(command, work_dir, duration, on_progress)

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise CompositionError("FFmpeg finished without producing a final video file.")

    return {
        "durationSeconds": round(duration, 3),
        "subtitleSegments": len(segments),
        "subtitleBurned": bool(subtitle.enabled and segments),
        "titleBurned": bool(title.enabled and title.text.strip() and title_font is not None),
        "bgmMixed": bgm_path is not None,
        "pipOverlaid": bool(pip.enabled),
        "pipWidthPx": pip_width_px,
        "reEncoded": True,
    }


def _run_with_progress(
    command: Sequence[str],
    work_dir: Path,
    duration: float,
    on_progress: Callable[[int, str], None] | None,
) -> None:
    """Run FFmpeg, translating its progress stream into percentages.

    FFmpeg keeps writing codec and mapping details to stderr even with
    ``-nostats``. Sending stderr to a file rather than a second pipe avoids the
    deadlock where a full stderr buffer stops FFmpeg while this loop is still
    waiting on stdout.
    """
    log_path = work_dir / "ffmpeg.log"
    try:
        with log_path.open("w", encoding="utf-8", errors="replace") as log:
            process = subprocess.Popen(
                list(command),
                cwd=str(work_dir),
                stdout=subprocess.PIPE,
                stderr=log,
                text=True,
                encoding="utf-8",
                errors="replace",
                **_no_window_kwargs(),
            )
            assert process.stdout is not None
            for line in process.stdout:
                if not on_progress or duration <= 0:
                    continue
                key, _, value = line.strip().partition("=")
                if key == "out_time_us" and value.strip().lstrip("-").isdigit():
                    seconds = int(value) / 1_000_000
                    percent = int(max(0.0, min(99.0, seconds / duration * 100)))
                    on_progress(percent, "Rendering final video")
            process.wait()
    except OSError as exc:
        raise CompositionError(f"Unable to start the local FFmpeg runtime: {exc}") from exc

    if process.returncode != 0:
        stderr = log_path.read_text(encoding="utf-8", errors="replace") if log_path.is_file() else ""
        raise CompositionError(_ffmpeg_error(stderr))


def _ffmpeg_error(stderr: str) -> str:
    """Surface the most useful FFmpeg error line instead of the whole log."""
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    for line in reversed(lines):
        lowered = line.lower()
        if any(token in lowered for token in ("error", "invalid", "no such file", "unable", "failed")):
            return f"FFmpeg failed: {line}"
    return "FFmpeg failed: " + (lines[-1] if lines else "unknown error")


def create_cover(
    *,
    source_video: Path,
    output_path: Path,
    work_dir: Path,
    timestamp: float = 0.0,
    style: CoverStyle | None = None,
    asset_font_dir: Path | None = None,
) -> dict[str, Any]:
    """Grab one frame from the finished video and burn the cover title onto it.

    The cover comes from the customer's own rendered video, so no stock imagery
    and no background-removal model is involved.
    """
    style = style or CoverStyle()
    ffmpeg = ffmpeg_executable()
    if not ffmpeg:
        raise CompositionError(
            "FFmpeg is not available on this machine. Install the FFmpeg runtime from Settings before creating a cover."
        )
    if not source_video.is_file():
        raise CompositionError("The source video for the cover is missing.")

    duration = probe_duration(source_video)
    seek = max(0.0, min(float(timestamp), max(0.0, duration - 0.05)))

    work_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    filters: list[str] = []
    text = style.text.strip()
    font = resolve_font(style.font_file, asset_font_dir) or default_font(asset_font_dir)
    if text:
        if font is None:
            raise CompositionError("No usable font was found for the cover title.")
        font_name = "cover-font" + font.suffix.lower()
        shutil.copyfile(font, work_dir / font_name)
        (work_dir / "cover.txt").write_text(_wrap(text, style.line_chars), encoding="utf-8")
        filters.append(
            _drawtext(
                text_file="cover.txt",
                font_file=font_name,
                font_size=style.font_size,
                color=_hex_color(style.color, "#ffffff"),
                stroke_color=_hex_color(style.stroke_color, "#000000"),
                stroke_width=style.stroke_width,
                y_expr=_position_expr(style.position, "center"),
            )
        )

    command = [ffmpeg, "-hide_banner", "-nostdin", "-y", "-ss", f"{seek:.3f}", "-i", str(source_video)]
    if filters:
        command += ["-vf", ",".join(filters)]
    command += ["-frames:v", "1", "-update", "1", str(output_path)]

    _run_with_progress(command, work_dir, 0.0, None)

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise CompositionError("FFmpeg finished without producing a cover image.")
    return {
        "timestampSeconds": round(seek, 3),
        "titleBurned": bool(text),
        "sizeBytes": output_path.stat().st_size,
    }


def main() -> int:
    """Report local composition readiness; used by the runtime smoke tests."""
    setup = inspect_setup()
    print(f"ffmpeg={setup['ffmpegAvailable']} ffprobe={setup['ffprobeAvailable']} drawtext={setup['drawtextAvailable']}")
    if not setup["ready"]:
        print("MISSING: " + ", ".join(setup["missing"]))
        return 1
    print("RESULT: BossAI final-video composition runtime is ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
