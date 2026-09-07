from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
os.environ.pop("BOSSAI_VIDEO_COMMERCIAL_PREVIEW", None)
os.environ.pop("BOSSAI_VIDEO_LOCAL_FREE_DAILY_UNITS", None)

UNITS = 30

with tempfile.TemporaryDirectory(prefix="bossai-video-local-quota-") as temp_root:
    root = Path(temp_root) / "data"
    os.environ["BOSSAI_VIDEO_DATA_ROOT"] = str(root)
    import local_quota
    import server
    from fastapi import HTTPException

    server._accept_eula("zh-CN")
    original_configured = server.bossai_os_bridge.configured
    server.bossai_os_bridge.configured = lambda: False
    try:
        # --- Shipping default: metering off -------------------------------
        # The allowance stays off until an operator sets it, so the default
        # build behaves exactly as it did before this feature existed.
        assert local_quota.enabled() is False
        off = local_quota.snapshot(root)
        assert off["enabled"] is False, off
        assert off["enforcement"] == "disabled", off
        assert local_quota.has_capacity(root, "digital-human") is True
        assert local_quota.consume(root, "digital-human")["usedUnits"] == 0
        assert not (root / "local-free-quota.json").exists(), "metering off must not write a counter"

        unmetered = server._entitlement_snapshot()
        assert unmetered["localFreeMode"] is True, unmetered
        assert unmetered["quotaAuthority"] == "none-local-free", unmetered
        assert unmetered["quotaPeriod"] == "local-unmetered", unmetered
        assert "daily local units remain" not in unmetered["reason"], unmetered["reason"]
        for operation in ("rewrite", "tts", "digital-human"):
            server.require_execution(f"video.{operation}", operation)

        # --- Turned on ----------------------------------------------------
        os.environ["BOSSAI_VIDEO_LOCAL_FREE_DAILY_UNITS"] = str(UNITS)
        assert local_quota.enabled() is True

        fresh = local_quota.snapshot(root)
        assert fresh["dailyUnits"] == UNITS, fresh
        assert fresh["remainingUnits"] == UNITS, fresh
        assert fresh["authority"] == "local-free-daily", fresh
        assert fresh["authority"] != "bossai-headquarters-commerce", "local counter must never claim the commercial authority"
        assert fresh["enforcement"] == "local-advisory", fresh

        # Accessory calls name no operation, so they cost nothing and can never
        # be the reason a customer is refused.
        assert local_quota.units_for("") == 0
        assert local_quota.units_for("title") == 0
        assert local_quota.has_capacity(root, "") is True

        # Charging is per finished deliverable, at the published cost.
        assert local_quota.consume(root, "rewrite")["usedUnits"] == 1
        assert local_quota.consume(root, "tts")["usedUnits"] == 3
        after = local_quota.consume(root, "digital-human")
        assert after["usedUnits"] == 8, after
        assert after["operations"] == {"rewrite": 1, "tts": 1, "digital-human": 1}, after

        snapshot = server._entitlement_snapshot()
        assert snapshot["quotaAuthority"] == local_quota.AUTHORITY, snapshot
        assert snapshot["quotaPeriod"] == local_quota.PERIOD, snapshot
        assert snapshot["quotaRemaining"] == UNITS - 8, snapshot
        # Exhausting the day's allowance must not read as "unlicensed".
        assert snapshot["executionAllowed"] is True, snapshot

        while local_quota.snapshot(root)["remainingUnits"] >= local_quota.units_for("digital-human"):
            local_quota.consume(root, "digital-human")
        try:
            server.require_execution(server.FEATURE_DIGITAL_HUMAN, "digital-human")
        except HTTPException as exc:
            assert exc.status_code == 429, exc.status_code
            assert "resets at" in str(exc.detail), exc.detail
        else:
            raise AssertionError("exhausted local allowance unexpectedly permitted a render")

        while local_quota.snapshot(root)["remainingUnits"] > 0:
            local_quota.consume(root, "rewrite")
        assert local_quota.snapshot(root)["remainingUnits"] == 0
        server.require_execution(server.FEATURE_REWRITE)  # accessory: must not raise

        # Paid tiers are metered by the commercial authority; their work must
        # never touch this counter.
        before = local_quota.snapshot(root)["usedUnits"]
        server._charge_local_quota({"localFreeMode": False}, "digital-human")
        assert local_quota.snapshot(root)["usedUnits"] == before, "paid-tier usage leaked into the local counter"

        # The day rolls over on the local calendar date, not on elapsed time.
        state_path = root / "local-free-quota.json"
        stored = json.loads(state_path.read_text(encoding="utf-8"))
        stored["date"] = "2000-01-01"
        state_path.write_text(json.dumps(stored), encoding="utf-8")
        assert local_quota.snapshot(root)["remainingUnits"] == UNITS

        # A corrupt counter must not cost the customer their personal use. This
        # is deliberately fail-open: the counter shapes the free tier, it is not
        # what protects commercial use, and that distinction is the whole reason
        # the entitlement check is separate and fail-closed.
        state_path.write_text("{ not json", encoding="utf-8")
        assert local_quota.snapshot(root)["remainingUnits"] == UNITS

        # --- Turned back off ----------------------------------------------
        os.environ.pop("BOSSAI_VIDEO_LOCAL_FREE_DAILY_UNITS", None)
        assert local_quota.enabled() is False
        assert local_quota.has_capacity(root, "digital-human") is True
        server.require_execution(server.FEATURE_DIGITAL_HUMAN, "digital-human")
    finally:
        server.bossai_os_bridge.configured = original_configured
        os.environ.pop("BOSSAI_VIDEO_LOCAL_FREE_DAILY_UNITS", None)

print("RESULT: BossAI Video Agent local Free Personal daily allowance passed.")
print(
    f"Metering is off unless {local_quota.ALLOWANCE_ENV} is set. When on, deliverables are charged on success at "
    "published costs, accessory calls are free, exhaustion returns 429 rather than reading as unlicensed, the counter "
    "resets on the local date, and paid-tier usage never touches it."
)
