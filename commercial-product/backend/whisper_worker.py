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

    device = args.device if args.device in {"auto", "cpu", "cuda"} else "auto"
    # int8 on CPU keeps a large-v3 transcription tractable on a laptop; float16
    # is used when a CUDA device is actually available.
    last_error: Exception | None = None
    model = None
    for candidate_device, compute_type in (
        (device, "float16" if device in {"auto", "cuda"} else "int8"),
        ("cpu", "int8"),
    ):
        try:
            model = WhisperModel(str(model_dir), device=candidate_device, compute_type=compute_type)
            device = candidate_device
            break
        except Exception as exc:  # noqa: BLE001 - fall back to CPU on any GPU failure
            last_error = exc
    if model is None:
        print(json.dumps({"error": f"model load failed: {last_error}"}), file=sys.stderr)
        return 3

    language = args.language.strip() or None
    segments, info = model.transcribe(
        str(source),
        language=language,
        vad_filter=True,
        beam_size=5,
    )

    items = []
    for segment in segments:
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
