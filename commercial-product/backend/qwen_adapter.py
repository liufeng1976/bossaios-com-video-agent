from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

ENGINE_ID = "qwen2.5-7b-instruct"


def _path_env(name: str) -> Path | None:
    raw = os.environ.get(name, "").strip().strip('"')
    if not raw:
        return None
    try:
        return Path(raw).expanduser().resolve()
    except OSError:
        return Path(raw).expanduser().absolute()


def _model_path() -> Path | None:
    return _path_env("BOSSAI_QWEN_MODEL")


def _python_path() -> Path | None:
    return _path_env("BOSSAI_QWEN_PYTHON")


def _worker_path() -> Path:
    explicit = _path_env("BOSSAI_QWEN_WORKER")
    if explicit:
        return explicit
    return Path(__file__).resolve().with_name("qwen_worker.py")


def inspect_setup() -> dict[str, Any]:
    model = _model_path()
    python_exe = _python_path()
    worker = _worker_path()
    missing: list[str] = []
    if model is None or not model.is_file():
        missing.append("model")
    if python_exe is None or not python_exe.is_file():
        missing.append("python-runtime")
    if not worker.is_file():
        missing.append("worker")
    return {
        "schema": "bossai.video-agent-qwen-runtime.v1",
        "engine": ENGINE_ID,
        "ready": not missing,
        "missing": missing,
        "externalWorker": True,
    }


def rewrite(source_text: str, options: dict[str, Any] | None = None) -> str:
    setup = inspect_setup()
    if not setup["ready"]:
        raise RuntimeError("Qwen runtime is not ready: " + ", ".join(setup["missing"]))

    source = str(source_text or "").strip()
    if not source:
        raise ValueError("source text is required")

    options = dict(options or {})
    model = _model_path()
    python_exe = _python_path()
    worker = _worker_path()
    assert model and python_exe

    payload = {
        "sourceText": source,
        "targetChars": max(80, min(1600, int(options.get("targetChars") or 300))),
        "platform": str(options.get("platform") or "douyin"),
        "videoType": str(options.get("videoType") or "voiceover"),
        "toneStyle": str(options.get("toneStyle") or ""),
        "industryPersona": str(options.get("industryPersona") or ""),
        "productBusiness": str(options.get("productBusiness") or ""),
        "sellingPoints": str(options.get("sellingPoints") or ""),
        "extraRequirements": str(options.get("extraRequirements") or ""),
        "modelPath": str(model),
    }
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.setdefault("PYTHONNOUSERSITE", "1")
    try:
        timeout = max(30.0, float(os.environ.get("BOSSAI_QWEN_TIMEOUT_SECONDS", "600")))
    except (TypeError, ValueError):
        timeout = 600.0

    process = subprocess.run(
        [str(python_exe), str(worker)],
        input=json.dumps(payload, ensure_ascii=False),
        cwd=worker.parent,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeError("Qwen inference failed: " + (process.stderr or process.stdout)[-3000:])

    result: dict[str, Any] | None = None
    for line in reversed((process.stdout or "").splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            result = value
            break
    text = str((result or {}).get("text") or "").strip()
    if not text:
        raise RuntimeError("Qwen worker returned no text")
    return text
