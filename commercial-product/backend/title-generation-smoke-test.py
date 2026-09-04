"""Smoke test for BossAI title and hashtag generation.

The parser cases run everywhere and are the real regression guard: instruct
models answer with prose around the JSON, or split the answer into two objects,
and a naive parser then surfaces raw markup as the customer-facing title.

The live model call runs only when the Qwen runtime is installed and
BOSSAI_TITLE_SMOKE_LIVE=1 is set, so this stays fast by default.
"""

from __future__ import annotations

import os
import pathlib
import sys

sys.dont_write_bytecode = True

SCRIPT = "大家好，我是本店老板。我们家做了十年家常菜，主打新鲜现炒。今天想跟大家聊聊怎么挑一家靠谱的社区餐厅。"

# (name, completion text, expected title, expected topic count)
PARSER_CASES = [
    ("clean-json", '{"title": "挑餐厅指南", "topics": ["#家常菜", "#社区餐厅"]}', "挑餐厅指南", 2),
    ("prose-wrapped", '好的：\n{"title": "挑餐厅指南", "topics": ["#家常菜"]}\n希望有帮助。', "挑餐厅指南", 1),
    ("split-objects", '{"title": "挑餐厅指南"}\n{"topics": ["#家常菜", "#现炒"]}', "挑餐厅指南", 2),
    ("plain-text", "挑餐厅指南\n#家常菜 #社区餐厅", "挑餐厅指南", 2),
    ("duplicate-topics", '{"title": "挑餐厅指南", "topics": ["#家常菜", "家常菜", "#现炒"]}', "挑餐厅指南", 2),
]


def _parse(adapter, completion: str, topic_count: int = 5) -> tuple[str, list[str]]:
    """Mirror the extraction order used by generate_title."""
    title = ""
    topics: list[str] = []
    for parsed in adapter._iter_json_objects(completion):
        if not title:
            title = str(parsed.get("title") or "").strip()
        if not topics and parsed.get("topics") is not None:
            topics = adapter._normalize_topics(parsed.get("topics"), topic_count)
    lines = [line.strip() for line in completion.splitlines() if line.strip()]
    if not title:
        title = next((line for line in lines if not line.startswith("#") and not adapter._looks_like_json(line)), "")
    if not topics:
        words = [word for line in lines for word in line.split() if word.startswith("#")]
        topics = adapter._normalize_topics(words, topic_count)
    return title, topics


def main() -> int:
    backend = pathlib.Path(__file__).resolve().parent
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))

    import qwen_adapter

    for name, completion, expected_title, expected_topics in PARSER_CASES:
        title, topics = _parse(qwen_adapter, completion)
        if title != expected_title:
            raise AssertionError(f"{name}: title {title!r} != {expected_title!r}")
        if len(topics) != expected_topics:
            raise AssertionError(f"{name}: expected {expected_topics} topics, got {topics!r}")
        if any(not topic.startswith("#") or " " in topic for topic in topics):
            raise AssertionError(f"{name}: malformed hashtags {topics!r}")
        if qwen_adapter._looks_like_json(title):
            raise AssertionError(f"{name}: raw markup leaked into the title {title!r}")

    # Titles must never be longer than the platform allows.
    for platform, limit in qwen_adapter._TITLE_LIMITS.items():
        messages = qwen_adapter._title_messages(SCRIPT, platform, 5)
        if f"不超过 {limit} 个中文字符" not in messages[1]["content"]:
            raise AssertionError(f"{platform}: prompt does not carry its title limit")

    print(f"RESULT: BossAI title parser passed {len(PARSER_CASES)} completion shapes.")

    if os.environ.get("BOSSAI_TITLE_SMOKE_LIVE", "").strip() != "1":
        print("SKIPPED live model call (set BOSSAI_TITLE_SMOKE_LIVE=1 with the Qwen runtime installed).")
        return 0

    setup = qwen_adapter.inspect_setup()
    if not setup.get("ready"):
        print("SKIPPED live model call: Qwen runtime unavailable: " + ", ".join(setup.get("missing") or []))
        return 0

    for platform, limit in qwen_adapter._TITLE_LIMITS.items():
        result = qwen_adapter.generate_title(SCRIPT, platform)
        title = str(result.get("title") or "")
        if not title or len(title) > limit:
            raise AssertionError(f"{platform}: live title invalid: {result!r}")
        if qwen_adapter._looks_like_json(title):
            raise AssertionError(f"{platform}: live title contains raw markup: {result!r}")
        print(f"live {platform}: {title} | {' '.join(result.get('topics') or [])}")

    print("RESULT: BossAI live title generation passed for every platform.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
