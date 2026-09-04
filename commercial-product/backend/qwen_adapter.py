from __future__ import annotations

import atexit
import json
import os
import re
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


def _complete(messages: list[dict[str, str]], max_tokens: int, temperature: float | None = None) -> str:
    """Run one chat completion against the locally started Qwen server."""
    port = _ensure_server()
    payload = {
        "model": ENGINE_ID,
        "messages": messages,
        "temperature": float(os.environ.get("BOSSAI_QWEN_TEMPERATURE", "0.65")) if temperature is None else temperature,
        "top_p": 0.9,
        "max_tokens": max(128, min(4096, int(max_tokens))),
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


def rewrite(source_text: str, options: dict[str, Any] | None = None) -> str:
    source = str(source_text or "").strip()
    if not source:
        raise ValueError("source text is required")
    options = dict(options or {})
    target_chars = max(80, min(1600, int(options.get("targetChars") or 300)))
    return _complete(_messages(source, options), max_tokens=target_chars * 2)


# Platform title conventions. The publishing modules still apply their own
# formatting; these are the limits the writing engine is asked to respect.
_TITLE_LIMITS = {
    "douyin": 30,
    "kuaishou": 30,
    "channels": 22,
    "xiaohongshu": 20,
}


def _title_messages(script: str, platform: str, topic_count: int) -> list[dict[str, str]]:
    limit = _TITLE_LIMITS.get(platform, 30)
    return [
        {
            "role": "system",
            "content": (
                "你是 BossAI Video Agent 的中文短视频运营编辑。"
                "只依据口播文案本身提炼标题和话题标签，不编造价格、资质、效果、销量、评价或承诺。"
                "不使用夸大和绝对化用语。"
                '只输出 JSON，格式为 {"title": "标题", "topics": ["#话题1", "#话题2"]}，不要输出其他任何内容。'
            ),
        },
        {
            "role": "user",
            "content": (
                f"目标平台：{platform}\n"
                f"标题长度：不超过 {limit} 个中文字符\n"
                f"话题标签数量：{topic_count} 个，每个以 # 开头，不含空格\n\n"
                f"口播文案：\n{script}"
            ),
        },
    ]


def _iter_json_objects(text: str) -> list[dict[str, Any]]:
    """Yield every top-level JSON object embedded in a completion.

    Instruct models sometimes answer with prose around the JSON, or split the
    answer into several objects. Scanning for balanced braces (while respecting
    string literals) finds each one instead of assuming the whole span between
    the first and last brace is a single valid object.
    """
    objects: list[dict[str, Any]] = []
    depth = 0
    start = -1
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    parsed = json.loads(text[start : index + 1])
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, dict):
                    objects.append(parsed)
                start = -1
    return objects


def _looks_like_json(line: str) -> bool:
    return line.lstrip().startswith(("{", "}", "[", "]", '"title"', "'title'"))


def _normalize_topics(value: Any, topic_count: int) -> list[str]:
    raw: list[str]
    if isinstance(value, list):
        raw = [str(item) for item in value]
    else:
        raw = re.split(r"[\s,，、]+", str(value or ""))
    topics: list[str] = []
    for item in raw:
        tag = "#" + item.strip().lstrip("#").strip()
        if len(tag) > 1 and tag not in topics:
            topics.append(tag)
    return topics[:topic_count]


def generate_title(script_text: str, platform: str = "douyin", topic_count: int = 5) -> dict[str, Any]:
    """Derive a publishing title and hashtags from the finished script."""
    script = str(script_text or "").strip()
    if not script:
        raise ValueError("script text is required")
    topic_count = max(1, min(10, int(topic_count)))
    limit = _TITLE_LIMITS.get(platform, 30)

    completion = _complete(_title_messages(script, platform, topic_count), max_tokens=512, temperature=0.7)

    title = ""
    topics: list[str] = []
    for parsed in _iter_json_objects(completion):
        if not title:
            title = str(parsed.get("title") or "").strip()
        if not topics and parsed.get("topics") is not None:
            topics = _normalize_topics(parsed.get("topics"), topic_count)

    # The model ignored the JSON instruction; recover from the raw lines rather
    # than surfacing markup as the title.
    lines = [line.strip() for line in completion.splitlines() if line.strip()]
    if not title:
        title = next((line for line in lines if not line.startswith("#") and not _looks_like_json(line)), "")
    if not topics:
        words = [word for line in lines for word in line.split() if word.startswith("#")]
        topics = _normalize_topics(words, topic_count)

    title = re.sub(r'^["“”\'\s]+|["“”\'\s]+$', "", title)
    if not title or _looks_like_json(title):
        raise RuntimeError("Qwen llama-server returned no usable title")
    return {"title": title[:limit], "topics": topics, "platform": platform, "titleLimit": limit}
