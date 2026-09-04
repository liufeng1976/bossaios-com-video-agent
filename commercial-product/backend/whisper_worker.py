"""BossAI local transcription worker.

Runs inside the isolated faster-whisper virtual environment created by
install-whisper.ps1. It transcribes a media file the customer already has on
this machine and prints one JSON line describing the result.

This worker never fetches remote media: it only accepts a local path. HF_HUB
offline mode is forced so the model can never be pulled at inference time.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys


def _cuda_usable() -> bool:
    """Report whether CUDA can actually run inference, not merely load a model.

    CTranslate2 builds the model on a CUDA device happily and only needs the
    cuDNN ops library once inference starts. When cuDNN is missing the process
    aborts inside native code, which no Python ``except`` can catch — so the
    only reliable option is to refuse CUDA up front rather than fall back after
    the fact.
    """
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() <= 0:
            return False
    except Exception:  # noqa: BLE001 - absent or unusable CUDA build
        return False

    import ctypes

    for candidate in ("cudnn_ops64_9.dll", "libcudnn_ops.so.9", "libcudnn_ops.so"):
        try:
            ctypes.CDLL(candidate)
            return True
        except OSError:
            continue
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="BossAI local Whisper transcription worker")
    parser.add_argument("--model", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--language", default="")
    args = parser.parse_args()

    # Never allow an inference-time model download.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    model_dir = pathlib.Path(args.model).expanduser().resolve()
    source = pathlib.Path(args.input).expanduser().resolve()
    if not model_dir.is_dir():
        print(json.dumps({"error": "model directory is missing"}), file=sys.stderr)
        return 2
    if not source.is_file():
        print(json.dumps({"error": "input media is missing"}), file=sys.stderr)
        return 2

    from faster_whisper import WhisperModel

    requested = args.device if args.device in {"auto", "cpu", "cuda"} else "auto"
    language = args.language.strip() or None

    def run(device: str, compute_type: str):
        """Load and transcribe on one device, forcing every error to surface here.

        transcribe() returns a generator, so a GPU that constructs fine but
        cannot run (for example CUDA present without cuDNN) only fails while the
        segments are consumed. Materialising them inside this call is what makes
        the CPU fallback below actually reachable.
        """
        model = WhisperModel(str(model_dir), device=device, compute_type=compute_type)
        segments, info = model.transcribe(str(source), language=language, vad_filter=True, beam_size=5)
        return list(segments), info

    attempts = []
    if requested in {"auto", "cuda"} and _cuda_usable():
        attempts.append(("cuda", "float16"))
    attempts.append(("cpu", "int8"))

    device = ""
    raw_segments = None
    info = None
    last_error: Exception | None = None
    for candidate_device, compute_type in attempts:
        try:
            raw_segments, info = run(candidate_device, compute_type)
            device = candidate_device
            break
        except Exception as exc:  # noqa: BLE001 - any GPU failure must fall back to CPU
            last_error = exc
    if raw_segments is None:
        print(json.dumps({"error": f"transcription failed: {last_error}"}), file=sys.stderr)
        return 3

    items = []
    for segment in raw_segments:
        text = (segment.text or "").strip()
        if not text:
            continue
        items.append(
            {
                "start": round(float(segment.start), 3),
                "end": round(float(segment.end), 3),
                "text": text,
            }
        )

    print(
        json.dumps(
            {
                "schema": "bossai.video-agent-transcription.v1",
                "language": getattr(info, "language", "") or "",
                "languageProbability": round(float(getattr(info, "language_probability", 0.0) or 0.0), 4),
                "durationSeconds": round(float(getattr(info, "duration", 0.0) or 0.0), 3),
                "device": device,
                "segments": items,
                "text": "".join(item["text"] for item in items).strip(),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
