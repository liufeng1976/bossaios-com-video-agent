from __future__ import annotations

import atexit
import json
import os
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ENGINE_ID = "qwen2.5-7b-instruct"
_SERVER_LOCK = threading.Lock()
_SERVER_PROCESS: subprocess.Popen[str] | None = None
_SERVER_PORT: int | None = None
_SERVER_MODEL: Path | None = None


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


def _server_path() -> Path | None:
    return _path_env("BOSSAI_QWEN_SERVER")


def _gpu_layers() -> int:
    raw = os.environ.get("BOSSAI_QWEN_GPU_LAYERS", "10").strip()
    try:
        return max(0, min(999, int(raw)))
    except ValueError:
        return 10


def inspect_setup() -> dict[str, Any]:
    model = _model_path()
    server = _server_path()
    missing: list[str] = []
    if model is None or not model.is_file():
        missing.append("model")
    if server is None or not server.is_file():
        missing.append("llama-server")
    return {
        "schema": "bossai.video-agent-qwen-runtime.v2",
        "engine": ENGINE_ID,
        "ready": not missing,
        "missing": missing,
        "runtime": "llama.cpp-vulkan",
        "gpuLayers": _gpu_layers(),
        "externalWorker": False,
    }


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _json_request(url: str, payload: dict[str, Any] | None = None, timeout: float = 5.0) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="GET" if payload is None else "POST")
    request.add_header("Content-Type", "application/json; charset=utf-8")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("llama-server returned a non-object response")
    return value


def _wait_server(port: int, process: subprocess.Popen[str], timeout: float = 90.0) -> None:
    deadline = time.time() + timeout
    last_error = ""
    while time.time() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate(timeout=3)
            detail = (stderr or stdout or "").strip()[-3000:]
            raise RuntimeError(f"llama-server exited during startup: {detail}")
        try:
            value = _json_request(f"http://127.0.0.1:{port}/health", timeout=1.5)
            if str(value.get("status") or "").lower() in {"ok", "ready"}:
                return
        except Exception as exc:  # startup polling only
            last_error = str(exc)
        time.sleep(0.4)
    raise RuntimeError(f"llama-server did not become ready: {last_error}")


def _stop_server() -> None:
    global _SERVER_PROCESS, _SERVER_PORT, _SERVER_MODEL
    with _SERVER_LOCK:
        process = _SERVER_PROCESS
        _SERVER_PROCESS = None
        _SERVER_PORT = None
        _SERVER_MODEL = None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


atexit.register(_stop_server)


def _ensure_server() -> int:
    global _SERVER_PROCESS, _SERVER_PORT, _SERVER_MODEL
    setup = inspect_setup()
    if not setup["ready"]:
        raise RuntimeError("Qwen runtime is not ready: " + ", ".join(setup["missing"]))
    model = _model_path()
    server = _server_path()
    assert model and server

    with _SERVER_LOCK:
        if (
            _SERVER_PROCESS is not None
            and _SERVER_PROCESS.poll() is None
            and _SERVER_PORT is not None
            and _SERVER_MODEL == model
        ):
            return _SERVER_PORT

        old = _SERVER_PROCESS
        if old is not None and old.poll() is None:
            old.terminate()
            try:
                old.wait(timeout=5)
            except subprocess.TimeoutExpired:
                old.kill()
                old.wait(timeout=3)

        port = _free_port()
        gpu_layers = _gpu_layers()
        n_ctx = max(2048, min(16384, int(os.environ.get("BOSSAI_QWEN_N_CTX", "4096"))))
        command = [
            str(server),
            "-m",
            str(model),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "-c",
            str(n_ctx),
            "-ngl",
            str(gpu_layers),
            "--no-webui",
        ]
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        process = subprocess.Popen(
            command,
            cwd=str(server.parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
        )
        _wait_server(port, process)
        _SERVER_PROCESS = process
        _SERVER_PORT = port
        _SERVER_MODEL = model
        return port


def _messages(source: str, options: dict[str, Any]) -> list[dict[str, str]]:
    target_chars = max(80, min(1600, int(options.get("targetChars") or 300)))
    platform = str(options.get("platform") or "douyin")
    persona = str(options.get("industryPersona") or "").strip()
    product = str(options.get("productBusiness") or "").strip()
    selling = str(options.get("sellingPoints") or "").strip()
    tone = str(options.get("toneStyle") or "").strip()
    extra = str(options.get("extraRequirements") or "").strip()
    return [
        {
            "role": "system",
            "content": (
                "你是 BossAI Video Agent 的中文短视频文案编辑。"
                "只根据客户提供的真实资料改写，不编造价格、资质、效果、销量、评价或承诺。"
                "输出只保留最终口播文案，不解释过程，不输出 Markdown 标题。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"目标平台：{platform}\n"
                f"目标长度：约 {target_chars} 个中文字符\n"
                f"行业/人设：{persona or '未提供'}\n"
                f"产品/服务：{product or '未提供'}\n"
                f"核心卖点：{selling or '未提供'}\n"
                f"表达风格：{tone or '自然、清晰、可信'}\n"
                f"其他要求：{extra or '无'}\n\n"
                f"原始资料：\n{source}"
            ),
        },
    ]


def rewrite(source_text: str, options: dict[str, Any] | None = None) -> str:
    source = str(source_text or "").strip()
    if not source:
        raise ValueError("source text is required")
    options = dict(options or {})
    target_chars = max(80, min(1600, int(options.get("targetChars") or 300)))
    port = _ensure_server()
    payload = {
        "model": ENGINE_ID,
        "messages": _messages(source, options),
        "temperature": float(os.environ.get("BOSSAI_QWEN_TEMPERATURE", "0.65")),
        "top_p": 0.9,
        "max_tokens": max(256, min(4096, target_chars * 2)),
        "stream": False,
    }
    timeout = max(30.0, float(os.environ.get("BOSSAI_QWEN_TIMEOUT_SECONDS", "240")))
    try:
        result = _json_request(f"http://127.0.0.1:{port}/v1/chat/completions", payload, timeout=timeout)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[-3000:]
        raise RuntimeError(f"Qwen llama-server request failed ({exc.code}): {detail}") from exc
    choices = result.get("choices") or []
    if not choices:
        raise RuntimeError("Qwen llama-server returned no completion")
    text = str((choices[0].get("message") or {}).get("content") or "").strip()
    if not text:
        raise RuntimeError("Qwen llama-server returned an empty completion")
    return text
