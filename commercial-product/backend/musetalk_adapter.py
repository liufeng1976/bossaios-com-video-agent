from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

ADAPTER_SCHEMA = "bossai.video-agent-musetalk-adapter.v1"
ENGINE_ID = "musetalk-v1.5"

# MuseTalk 1.5 model layout follows the official repository quickstart.
_REQUIRED_RELATIVE_FILES = (
    "scripts/inference.py",
    "models/musetalkV15/unet.pth",
    "models/musetalkV15/musetalk.json",
    "models/syncnet/latentsync_syncnet.pt",
    "models/dwpose/dw-ll_ucoco_384.pth",
    "models/face-parse-bisent/79999_iter.pth",
    "models/face-parse-bisent/resnet18-5c106cde.pth",
    "models/sd-vae/config.json",
    "models/sd-vae/diffusion_pytorch_model.bin",
    "models/whisper/config.json",
    "models/whisper/pytorch_model.bin",
    "models/whisper/preprocessor_config.json",
)


def _as_path(value: str | os.PathLike[str] | None) -> Path | None:
    raw = str(value or "").strip().strip('"')
    if not raw:
        return None
    try:
        return Path(raw).expanduser().resolve()
    except OSError:
        return Path(raw).expanduser().absolute()


def configured_root() -> Path | None:
    return _as_path(os.environ.get("BOSSAI_MUSETALK_ROOT"))


def configured_python(root: Path | None = None) -> Path | None:
    explicit = _as_path(os.environ.get("BOSSAI_MUSETALK_PYTHON"))
    if explicit and explicit.is_file():
        return explicit
    root = root or configured_root()
    if not root:
        return None
    candidates = (
        root / ".venv" / "Scripts" / "python.exe",
        root / "venv" / "Scripts" / "python.exe",
        root / "python.exe",
    )
    return next((candidate.resolve() for candidate in candidates if candidate.is_file()), None)


def configured_ffmpeg_bin() -> Path | None:
    explicit = _as_path(os.environ.get("BOSSAI_FFMPEG_BIN"))
    if explicit:
        if explicit.is_file():
            return explicit.parent
        if explicit.is_dir() and (explicit / "ffmpeg.exe").is_file():
            return explicit
    discovered = shutil.which("ffmpeg")
    return Path(discovered).resolve().parent if discovered else None


def inspect_setup() -> dict[str, Any]:
    root = configured_root()
    python_exe = configured_python(root)
    ffmpeg_bin = configured_ffmpeg_bin()
    missing: list[str] = []

    if root is None or not root.is_dir():
        missing.append("BOSSAI_MUSETALK_ROOT")
    else:
        for relative in _REQUIRED_RELATIVE_FILES:
            if not (root / relative).is_file():
                missing.append(relative)

    if python_exe is None:
        missing.append("MuseTalk Python environment (BOSSAI_MUSETALK_PYTHON or .venv\\Scripts\\python.exe)")
    if ffmpeg_bin is None:
        missing.append("FFmpeg (BOSSAI_FFMPEG_BIN or PATH)")

    return {
        "schema": ADAPTER_SCHEMA,
        "engine": ENGINE_ID,
        "ready": not missing,
        "root": str(root) if root else None,
        "python": str(python_exe) if python_exe else None,
        "ffmpegBin": str(ffmpeg_bin) if ffmpeg_bin else None,
        "missing": missing,
        "version": "v15",
        "usesOfficialTestData": False,
        "requiresCustomerAuthorizedAvatar": True,
        "requiresCustomerAuthorizedAudio": True,
    }


def _yaml_string(value: str | os.PathLike[str]) -> str:
    # JSON double-quoted strings are valid YAML scalar syntax and safely escape Windows paths.
    return json.dumps(str(value), ensure_ascii=False)


def _write_inference_config(path: Path, *, video_path: Path, audio_path: Path, result_name: str) -> None:
    content = (
        "bossai_task:\n"
        f"  video_path: {_yaml_string(video_path)}\n"
        f"  audio_path: {_yaml_string(audio_path)}\n"
        f"  result_name: {_yaml_string(result_name)}\n"
        "  bbox_shift: 0\n"
    )
    path.write_text(content, encoding="utf-8")


def render(
    *,
    video_path: str | os.PathLike[str],
    audio_path: str | os.PathLike[str],
    output_dir: str | os.PathLike[str],
    output_filename: str | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    setup = inspect_setup()
    if not setup["ready"]:
        raise RuntimeError("MuseTalk runtime is not ready: " + "; ".join(setup["missing"]))

    root = Path(str(setup["root"]))
    python_exe = Path(str(setup["python"]))
    ffmpeg_bin = Path(str(setup["ffmpegBin"]))
    source_video = Path(video_path).expanduser().resolve()
    source_audio = Path(audio_path).expanduser().resolve()
    target_root = Path(output_dir).expanduser().resolve()

    if not source_video.is_file():
        raise FileNotFoundError(f"authorized avatar/video is missing: {source_video}")
    if not source_audio.is_file():
        raise FileNotFoundError(f"authorized/generated audio is missing: {source_audio}")

    target_root.mkdir(parents=True, exist_ok=True)
    filename = Path(output_filename or f"bossai-musetalk-{uuid.uuid4().hex}.mp4").name
    if not filename.lower().endswith(".mp4"):
        filename += ".mp4"

    result_dir = target_root / f"task-{uuid.uuid4().hex}"
    result_dir.mkdir(parents=True, exist_ok=False)
    config_path = result_dir / "inference.yaml"
    _write_inference_config(
        config_path,
        video_path=source_video,
        audio_path=source_audio,
        result_name=filename,
    )

    expected_output = result_dir / "v15" / filename
    command = [
        str(python_exe),
        "-m",
        "scripts.inference",
        "--inference_config",
        str(config_path),
        "--result_dir",
        str(result_dir),
        "--unet_model_path",
        str(root / "models" / "musetalkV15" / "unet.pth"),
        "--unet_config",
        str(root / "models" / "musetalkV15" / "musetalk.json"),
        "--whisper_dir",
        str(root / "models" / "whisper"),
        "--version",
        "v15",
        "--ffmpeg_path",
        str(ffmpeg_bin),
        "--use_float16",
    ]

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PATH"] = str(ffmpeg_bin) + os.pathsep + env.get("PATH", "")

    started = time.perf_counter()
    timeout = timeout_seconds
    if timeout is None:
        try:
            timeout = float(os.environ.get("BOSSAI_MUSETALK_TIMEOUT_SECONDS", "1800"))
        except (TypeError, ValueError):
            timeout = 1800.0

    process = subprocess.run(
        command,
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=max(30.0, float(timeout)),
        check=False,
    )
    elapsed = round(time.perf_counter() - started, 3)

    if process.returncode != 0:
        raise RuntimeError(
            "MuseTalk inference failed "
            f"(rc={process.returncode}): {(process.stderr or process.stdout)[-4000:]}"
        )
    if not expected_output.is_file() or expected_output.stat().st_size < 1024:
        raise RuntimeError(
            "MuseTalk exited without the expected output file. "
            f"Expected: {expected_output}; stdout tail: {process.stdout[-3000:]}"
        )

    final_output = target_root / filename
    if final_output.exists():
        final_output.unlink()
    expected_output.replace(final_output)
    shutil.rmtree(result_dir, ignore_errors=True)

    return {
        "schema": ADAPTER_SCHEMA,
        "engine": ENGINE_ID,
        "outputPath": str(final_output),
        "sizeBytes": final_output.stat().st_size,
        "elapsedSeconds": elapsed,
        "returnCode": process.returncode,
        "usesOfficialTestData": False,
    }


if __name__ == "__main__":
    print(json.dumps(inspect_setup(), ensure_ascii=False, indent=2))
