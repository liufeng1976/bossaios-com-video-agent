"""BossAI local transcription adapter.

Drives the pinned faster-whisper runtime in its own interpreter so the ASR
dependency set never mixes with the engine's.

Scope note: this adapter transcribes media the customer already holds locally.
It deliberately exposes no way to fetch a remote URL — pulling a script out of
a third-party platform is out of scope for this product.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

ENGINE_ID = "faster-whisper-large-v3"


def _path_env(name: str) -> Path | None:
    raw = os.environ.get(name, "").strip().strip('"')
    if not raw:
        return None
    try:
        return Path(raw).expanduser().resolve()
    except OSError:
        return Path(raw).expanduser().absolute()


def inspect_setup(worker_path: Path | None = None) -> dict[str, Any]:
    """Report whether local transcription can actually run.

    ``worker_path`` is checked because the worker is a loose script executed by
    a separately installed interpreter, not a module imported into this
    process. In a frozen build it only exists if the packaging step bundled it,
    so omitting that check would let the product report "ready" and then fail
    at transcription time — after the customer had already downloaded the model.
    """
    model = _path_env("BOSSAI_WHISPER_MODEL")
    python_exe = _path_env("BOSSAI_WHISPER_PYTHON")
    missing: list[str] = []
    if model is None or not (model / "model.bin").is_file():
        missing.append("model-runtime")
    if python_exe is None or not python_exe.is_file():
        missing.append("python-runtime")
    if worker_path is not None and not Path(worker_path).is_file():
        missing.append("transcription-worker")
    return {
        "schema": "bossai.video-agent-whisper-runtime.v1",
        "engine": ENGINE_ID,
        "ready": not missing,
        "missing": missing,
        "device": os.environ.get("BOSSAI_WHISPER_DEVICE", "auto"),
    }


def transcribe(*, media_path: Path, worker_path: Path, language: str = "") -> dict[str, Any]:
    """Transcribe a local media file into timed segments."""
    setup = inspect_setup(worker_path)
    if not setup["ready"]:
        raise RuntimeError("Local transcription runtime is not ready: " + ", ".join(setup["missing"]))

    source = Path(media_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"media file is missing: {source}")

    model = _path_env("BOSSAI_WHISPER_MODEL")
    python_exe = _path_env("BOSSAI_WHISPER_PYTHON")
    assert model and python_exe

    env = os.environ.copy()
    # The worker runs on a separately installed interpreter; never leak this
    # process's package roots into it.
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.setdefault("PYTHONNOUSERSITE", "1")
    env["HF_HUB_OFFLINE"] = "1"

    # -I keeps the worker's own directory off sys.path. In the packaged product
    # that directory is the PyInstaller extraction directory, which holds the
    # engine's Python 3.12 extension modules; without this the interpreter here
    # imports those and dies with "Module use of python312.dll conflicts with
    # this version of Python". -I also implies -E, which discards the PYTHON*
    # variables set above, so the UTF-8 requirement is restated as -X utf8 --
    # otherwise the worker writes its JSON as GBK and Chinese text arrives
    # corrupted.
    command = [
        str(python_exe),
        "-I",
        "-X",
        "utf8",
        str(worker_path),
        "--model",
        str(model),
        "--input",
        str(source),
        "--device",
        os.environ.get("BOSSAI_WHISPER_DEVICE", "auto"),
    ]
    if language.strip():
        command += ["--language", language.strip()]

    try:
        timeout = max(60.0, float(os.environ.get("BOSSAI_WHISPER_TIMEOUT_SECONDS", "1800")))
    except (TypeError, ValueError):
        timeout = 1800.0

    process = subprocess.run(
        command,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeError("Local transcription failed: " + (process.stderr or process.stdout)[-3000:])

    for line in reversed((process.stdout or "").splitlines()):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("schema"):
            return payload
    raise RuntimeError("Local transcription returned no usable result.")
