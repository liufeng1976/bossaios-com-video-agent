"""Daily courtesy quota for the unauthenticated local Free Personal tier.

This is a product-shaping limit, not a security boundary. The counter is a plain
JSON file inside the customer's own data directory, so anyone who wants to reset
it can, and nothing here pretends otherwise: there is no signing, no hidden
mirror of the count, and no attempt to detect tampering. The limit exists to
give personal use a visible shape and an obvious upgrade path.

Paid tiers never reach this module. Their quota is issued by the BossAI
commercial authority, and mixing a locally-held number into that would make the
authoritative quota unauditable.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

SCHEMA = "bossai.video-agent-local-free-quota.v1"
AUTHORITY = "local-free-daily"
PERIOD = "local-daily"

DEFAULT_DAILY_UNITS = 30

# Cost per finished deliverable. Accessory calls that merely decorate work the
# customer already paid for -- a title or a cover line for a script they just
# rewrote -- are deliberately absent and therefore cost nothing.
OPERATION_UNITS: dict[str, int] = {
    "rewrite": 1,
    "tts": 2,
    "digital-human": 5,
}

_LOCK = threading.Lock()


def daily_units() -> int:
    raw = str(os.environ.get("BOSSAI_VIDEO_LOCAL_FREE_DAILY_UNITS") or "").strip()
    if not raw:
        return DEFAULT_DAILY_UNITS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_DAILY_UNITS
    return max(0, value)


def units_for(operation: str) -> int:
    return OPERATION_UNITS.get(str(operation or "").strip(), 0)


def _state_path(data_root: Path) -> Path:
    return Path(data_root) / "local-free-quota.json"


def _today() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d")


def _next_reset() -> str:
    now = datetime.now().astimezone()
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight.isoformat()


def _blank(date: str) -> dict[str, Any]:
    return {"schema": SCHEMA, "date": date, "usedUnits": 0, "operations": {}}


def _load(data_root: Path) -> dict[str, Any]:
    """Read today's counter, resetting when the day rolls over.

    An unreadable or malformed file is treated as a fresh day rather than as a
    reason to refuse work. Failing closed here would take a customer's personal
    use away because of a corrupt file, and this counter is not the thing that
    protects commercial use -- that is the entitlement check, which is
    fail-closed and lives elsewhere.
    """
    today = _today()
    path = _state_path(data_root)
    if not path.is_file():
        return _blank(today)
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return _blank(today)
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        return _blank(today)
    if str(data.get("date") or "") != today:
        return _blank(today)
    operations = data.get("operations")
    return {
        "schema": SCHEMA,
        "date": today,
        "usedUnits": max(0, int(data.get("usedUnits") or 0)),
        "operations": {str(k): max(0, int(v or 0)) for k, v in operations.items()} if isinstance(operations, dict) else {},
    }


def _save(data_root: Path, state: dict[str, Any]) -> None:
    path = _state_path(data_root)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def snapshot(data_root: Path) -> dict[str, Any]:
    with _LOCK:
        state = _load(Path(data_root))
    allowance = daily_units()
    used = int(state["usedUnits"])
    return {
        "schema": SCHEMA,
        "authority": AUTHORITY,
        "period": PERIOD,
        "date": state["date"],
        "dailyUnits": allowance,
        "usedUnits": used,
        "remainingUnits": max(0, allowance - used),
        "resetAt": _next_reset(),
        "operationUnits": dict(OPERATION_UNITS),
        "operations": dict(state["operations"]),
        "enforcement": "local-advisory",
    }


def has_capacity(data_root: Path, operation: str) -> bool:
    cost = units_for(operation)
    if cost <= 0:
        return True
    return snapshot(data_root)["remainingUnits"] >= cost


def consume(data_root: Path, operation: str) -> dict[str, Any]:
    """Charge one finished deliverable against today's allowance."""
    cost = units_for(operation)
    if cost <= 0:
        return snapshot(data_root)
    root = Path(data_root)
    with _LOCK:
        state = _load(root)
        state["usedUnits"] = int(state["usedUnits"]) + cost
        state["operations"][operation] = int(state["operations"].get(operation) or 0) + 1
        try:
            _save(root, state)
        except OSError:
            # A counter we cannot persist must not block the work the customer
            # has already had rendered for them.
            pass
    return snapshot(root)
