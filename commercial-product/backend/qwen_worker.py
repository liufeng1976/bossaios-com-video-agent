from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


def required_path(value: str, label: str) -> Path:
    path = Path(str(value or "").strip().strip('"')).expanduser().resolve()
    if not path.is_file():
        raise RuntimeError(f"{label} is missing: {path}")
    return path


def read_request() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        raise RuntimeError("Qwen worker request is empty")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise RuntimeError("Qwen worker request must be an object")
    return value


def build_messages(request: dict[str, Any]) -> list[dict[str, str]]:
    source = str(request.get("sourceText") or "").strip()
    if not source:
        raise RuntimeError("sourceText is required")

    target_chars = max(80, min(1600, int(request.get("targetChars") or 300)))
    platform = str(request.get("platform") or "douyin")
    persona = str(request.get("industryPersona") or "").strip()
    product = str(request.get("productBusiness") or "").strip()
    selling = str(request.get("sellingPoints") or "").strip()
    tone = str(request.get("toneStyle") or "").strip()
    extra = str(request.get("extraRequirements") or "").strip()

    system_prompt = (
        "你是 BossAI Video Agent 的中文短视频文案编辑。"
        "只根据客户提供的真实资料改写，不编造价格、资质、效果、销量、评价或承诺。"
        "输出只保留最终口播文案，不解释过程，不输出 Markdown 标题。"
    )
    user_prompt = (
        f"目标平台：{platform}\n"
        f"目标长度：约 {target_chars} 个中文字符\n"
        f"行业/人设：{persona or '未提供'}\n"
        f"产品/服务：{product or '未提供'}\n"
        f"核心卖点：{selling or '未提供'}\n"
        f"表达风格：{tone or '自然、清晰、可信'}\n"
        f"其他要求：{extra or '无'}\n\n"
        f"原始资料：\n{source}"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def main() -> int:
    request = read_request()
    model_path = required_path(str(request.get("modelPath") or ""), "Qwen model")

    from llama_cpp import Llama

    target_chars = max(80, min(1600, int(request.get("targetChars") or 300)))
    llm = Llama(
        model_path=str(model_path),
        n_ctx=max(2048, int(os.environ.get("BOSSAI_QWEN_N_CTX", "4096"))),
        n_gpu_layers=int(os.environ.get("BOSSAI_QWEN_GPU_LAYERS", "-1")),
        verbose=False,
    )
    result = llm.create_chat_completion(
        messages=build_messages(request),
        temperature=float(os.environ.get("BOSSAI_QWEN_TEMPERATURE", "0.65")),
        top_p=0.9,
        max_tokens=max(256, target_chars * 2),
    )
    choices = result.get("choices") or []
    if not choices:
        raise RuntimeError("Qwen returned no completion")
    text = str((choices[0].get("message") or {}).get("content") or "").strip()
    if not text:
        raise RuntimeError("Qwen returned an empty completion")

    print(json.dumps({
        "schema": "bossai.video-agent-qwen-worker-result.v1",
        "text": text,
        "engine": "qwen2.5-7b-instruct",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
