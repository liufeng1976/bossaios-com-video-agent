"""Smoke test for BossAI local transcription.

Two things matter here and both run without the 3 GB ASR model installed:

1. The scope boundary — the product transcribes local media the customer
   already holds and exposes no way to fetch a remote/platform URL.
2. Graceful degradation — when the ASR runtime is absent, subtitle timing
   falls back to proportional estimation instead of failing the render.

The live model path runs only when the runtime is installed.
"""

from __future__ import annotations

import inspect
import os
import pathlib
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True


def main() -> int:
    temp_root = pathlib.Path(tempfile.mkdtemp(prefix="bossai-asr-smoke-"))
    try:
        os.environ["BOSSAI_VIDEO_DATA_ROOT"] = str(temp_root / "data")

        backend = pathlib.Path(__file__).resolve().parent
        if str(backend) not in sys.path:
            sys.path.insert(0, str(backend))

        import server
        import video_composer
        import whisper_adapter

        # --- scope boundary --------------------------------------------------
        # Neither layer may reach the network: transcription is strictly local.
        adapter_source = inspect.getsource(whisper_adapter)
        worker_source = (backend / "whisper_worker.py").read_text(encoding="utf-8")
        for name, text in (("whisper_adapter", adapter_source), ("whisper_worker", worker_source)):
            for forbidden in ("urlopen", "requests.", "httpx", "http://", "https://"):
                if forbidden in text:
                    raise AssertionError(f"{name} must not perform network access: found {forbidden!r}")

        signature = inspect.signature(whisper_adapter.transcribe)
        if "media_path" not in signature.parameters:
            raise AssertionError("transcribe() must take a local media path")
        if any(name in signature.parameters for name in ("url", "link", "share_text")):
            raise AssertionError(f"transcribe() must not accept a remote source: {signature}")

        # The endpoint accepts an uploaded file, never a caller-supplied location.
        upload_params = inspect.signature(server.upload_transcription_media).parameters
        if "file" not in upload_params:
            raise AssertionError("the transcription endpoint must take an uploaded file")
        if any(name in upload_params for name in ("url", "link", "shareText", "sourceUrl")):
            raise AssertionError(f"the transcription endpoint must not accept a remote source: {tuple(upload_params)}")

        # --- runtime reporting -----------------------------------------------
        setup = whisper_adapter.inspect_setup()
        if setup.get("engine") != "faster-whisper-large-v3":
            raise AssertionError(f"unexpected ASR engine: {setup!r}")
        center = server._runtime_install_center()
        whisper_entry = center["components"].get("whisper")
        if whisper_entry is None:
            raise AssertionError("whisper is missing from the runtime install center")
        if whisper_entry.get("requires") != ["python310"]:
            raise AssertionError(f"whisper install prerequisites are wrong: {whisper_entry!r}")

        # --- graceful degradation --------------------------------------------
        # With no ASR runtime the render must still produce estimated timings.
        measured = server._measured_subtitle_segments(temp_root / "missing.mp4")
        if measured:
            raise AssertionError("segments were returned without an installed ASR runtime")

        estimated = video_composer.build_segments("第一句话。第二句话。第三句话。", 9.0)
        if len(estimated) < 2:
            raise AssertionError(f"fallback estimation produced too few segments: {estimated!r}")

        if not setup.get("ready"):
            print("RESULT: BossAI transcription scope and fallback contract passed.")
            print("SKIPPED live transcription: ASR runtime not installed.")
            return 0

        # --- live path ---------------------------------------------------------
        ffmpeg = video_composer.ffmpeg_executable()
        if not ffmpeg:
            print("RESULT: BossAI transcription scope and fallback contract passed.")
            print("SKIPPED live transcription: FFmpeg unavailable for fixture creation.")
            return 0

        import subprocess

        sample = temp_root / "speech.wav"
        subprocess.run(
            [ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
             "-ar", "16000", str(sample)],
            check=True,
        )
        result = whisper_adapter.transcribe(media_path=sample, worker_path=backend / "whisper_worker.py")
        if result.get("schema") != "bossai.video-agent-transcription.v1":
            raise AssertionError(f"unexpected transcription schema: {result!r}")
        print("RESULT: BossAI transcription scope, fallback and live contract passed.")
        print(f"device={result.get('device')} durationSeconds={result.get('durationSeconds')}")
        return 0
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
