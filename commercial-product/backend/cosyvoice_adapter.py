from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any

ENGINE_ID = "cosyvoice2-0.5b"


def _path_env(name: str) -> Path | None:
    raw = os.environ.get(name, "").strip().strip('"')
    if not raw:
        return None
    try:
        return Path(raw).expanduser().resolve()
    except OSError:
        return Path(raw).expanduser().absolute()


def inspect_setup() -> dict[str, Any]:
    repo = _path_env("BOSSAI_COSYVOICE_ROOT")
    model = _path_env("BOSSAI_COSYVOICE_MODEL_DIR")
    python_exe = _path_env("BOSSAI_COSYVOICE_PYTHON")
    missing: list[str] = []
    if repo is None or not (repo / "cosyvoice" / "cli" / "cosyvoice.py").is_file():
        missing.append("repo")
    if model is None or not model.is_dir():
        missing.append("model")
    if python_exe is None or not python_exe.is_file():
        missing.append("python-runtime")
    return {
        "schema": "bossai.video-agent-cosyvoice-runtime.v1",
        "engine": ENGINE_ID,
        "ready": not missing,
        "missing": missing,
    }


def render(*, text: str, reference_audio: Path, output_dir: Path, worker_path: Path) -> dict[str, Any]:
    setup = inspect_setup()
    if not setup["ready"]:
        raise RuntimeError("CosyVoice2 runtime is not ready: " + ", ".join(setup["missing"]))

    source = Path(reference_audio).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"authorized reference voice is missing: {source}")
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{uuid.uuid4().hex}.wav"

    repo = _path_env("BOSSAI_COSYVOICE_ROOT")
    model = _path_env("BOSSAI_COSYVOICE_MODEL_DIR")
    python_exe = _path_env("BOSSAI_COSYVOICE_PYTHON")
    assert repo and model and python_exe

    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.setdefault("PYTHONNOUSERSITE", "1")
    command = [
        str(python_exe),
        str(worker_path),
        "--repo",
        str(repo),
        "--model",
        str(model),
        "--text",
        str(text),
        "--reference",
        str(source),
        "--output",
        str(output),
    ]
    try:
        timeout = max(30.0, float(os.environ.get("BOSSAI_COSYVOICE_TIMEOUT_SECONDS", "900")))
    except (TypeError, ValueError):
        timeout = 900.0
    process = subprocess.run(
        command,
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if process.returncode != 0:
        output.unlink(missing_ok=True)
        raise RuntimeError("CosyVoice2 inference failed: " + (process.stderr or process.stdout)[-3000:])
    if not output.is_file() or output.stat().st_size < 1024:
        output.unlink(missing_ok=True)
        raise RuntimeError("CosyVoice2 did not produce a valid WAV file")

    worker_result: dict[str, Any] = {}
    for line in reversed((process.stdout or "").splitlines()):
        try:
            worker_result = json.loads(line)
            break
        except json.JSONDecodeError:
            continue
    return {
        "schema": "bossai.video-agent-tts-output.v1",
        "engine": ENGINE_ID,
        "outputPath": str(output),
        "sizeBytes": output.stat().st_size,
        "sampleRate": worker_result.get("sampleRate"),
        "cuda": worker_result.get("cuda"),
    }
