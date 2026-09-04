from __future__ import annotations

import argparse
import json
import pathlib
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="BossAI CosyVoice2 local inference worker")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    repo = pathlib.Path(args.repo).expanduser().resolve()
    model_dir = pathlib.Path(args.model).expanduser().resolve()
    reference = pathlib.Path(args.reference).expanduser().resolve()
    output = pathlib.Path(args.output).expanduser().resolve()

    sys.path.insert(0, str(repo))
    matcha = repo / "third_party" / "Matcha-TTS"
    if matcha.is_dir():
        sys.path.insert(0, str(matcha))

    import torch
    import torchaudio
    from cosyvoice.cli.cosyvoice import CosyVoice2

    engine = CosyVoice2(str(model_dir), load_jit=False, load_trt=False, fp16=torch.cuda.is_available())
    chunks = []
    sample_rate = int(getattr(engine, "sample_rate", 24000) or 24000)
    # CosyVoice2's public zero-shot API loads and resamples the reference
    # audio itself. Passing a preloaded tensor works with neither the current
    # 2.0 runtime nor the documented API, so retain the verified file path.
    for item in engine.inference_zero_shot(
        args.text,
        "",
        str(reference),
        stream=False,
        text_frontend=False,
    ):
        speech = item.get("tts_speech") if isinstance(item, dict) else None
        if speech is not None:
            chunks.append(speech.detach().cpu())
    if not chunks:
        raise RuntimeError("CosyVoice2 returned no audio")

    waveform = torch.cat(chunks, dim=1 if chunks[0].ndim > 1 else 0)
    if waveform.ndim == 1:
        waveform = waveform.unsqueeze(0)
    output.parent.mkdir(parents=True, exist_ok=True)
    torchaudio.save(str(output), waveform, sample_rate)
    result = {
        "engine": "cosyvoice2-0.5b",
        "sampleRate": sample_rate,
        "sizeBytes": output.stat().st_size,
        "cuda": bool(torch.cuda.is_available()),
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
