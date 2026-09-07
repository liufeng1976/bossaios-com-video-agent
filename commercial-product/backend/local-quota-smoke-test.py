from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
os.environ.pop("BOSSAI_VIDEO_COMMERCIAL_PREVIEW", None)
os.environ.pop("BOSSAI_VIDEO_LOCAL_FREE_DAILY_UNITS", None)

with tempfile.TemporaryDirectory(prefix="bossai-video-local-quota-") as temp_root:
    root = Path(temp_root) / "data"
    os.environ["BOSSAI_VIDEO_DATA_ROOT"] = str(root)
    import local_quota
    import server
    from fastapi import HTTPException

    server._accept_eula("zh-CN")

    # A fresh install starts with the whole day's allowance and nothing spent.
    fresh = local_quota.snapshot(root)
    assert fresh["dailyUnits"] == local_quota.DEFAULT_DAILY_UNITS, fresh
    assert fresh["remainingUnits"] == local_quota.DEFAULT_DAILY_UNITS, fresh
    assert fresh["usedUnits"] == 0, fresh
    assert fresh["authority"] == "local-free-daily", fresh
    assert fresh["authority"] != "bossai-headquarters-commerce", "local counter must never claim the commercial authority"
    assert fresh["enforcement"] == "local-advisory", fresh

    # Accessory calls name no operation, so they cost nothing and can never be
    # the reason a customer is refused.
    assert local_quota.units_for("") == 0
    assert local_quota.units_for("title") == 0
    assert local_quota.has_capacity(root, "") is True

    # Charging is per finished deliverable, at the published cost.
    after_rewrite = local_quota.consume(root, "rewrite")
    assert after_rewrite["usedUnits"] == 1, after_rewrite
    after_tts = local_quota.consume(root, "tts")
    assert after_tts["usedUnits"] == 3, after_tts
    after_dh = local_quota.consume(root, "digital-human")
    assert after_dh["usedUnits"] == 8, after_dh
    assert after_dh["operations"] == {"rewrite": 1, "tts": 1, "digital-human": 1}, after_dh
    assert after_dh["remainingUnits"] == local_quota.DEFAULT_DAILY_UNITS - 8, after_dh

    # The snapshot the product reports must agree with the counter.
    original_configured = server.bossai_os_bridge.configured
    try:
        server.bossai_os_bridge.configured = lambda: False
        snapshot = server._entitlement_snapshot()
        assert snapshot["localFreeMode"] is True, snapshot
        assert snapshot["quotaAuthority"] == local_quota.AUTHORITY, snapshot
        assert snapshot["quotaPeriod"] == local_quota.PERIOD, snapshot
        assert snapshot["quotaRemaining"] == after_dh["remainingUnits"], snapshot
        assert snapshot["localFreeQuota"]["usedUnits"] == 8, snapshot
        # Exhausting the day's allowance must not read as "unlicensed".
        assert snapshot["executionAllowed"] is True, snapshot

        # Spend the rest of the day, then confirm the gate refuses with 429 and
        # not with the 403 that means "you are not entitled to this at all".
        while local_quota.snapshot(root)["remainingUnits"] >= local_quota.units_for("digital-human"):
            local_quota.consume(root, "digital-human")
        try:
            server.require_execution(server.FEATURE_DIGITAL_HUMAN, "digital-human")
        except HTTPException as exc:
            assert exc.status_code == 429, exc.status_code
            assert "resets at" in str(exc.detail), exc.detail
        else:
            raise AssertionError("exhausted local allowance unexpectedly permitted a render")

        # A cheaper deliverable is still allowed while units remain for it, and
        # accessory calls stay free even at zero.
        remaining = local_quota.snapshot(root)["remainingUnits"]
        if remaining >= local_quota.units_for("rewrite"):
            server.require_execution(server.FEATURE_REWRITE, "rewrite")
        while local_quota.snapshot(root)["remainingUnits"] > 0:
            local_quota.consume(root, "rewrite")
        assert local_quota.snapshot(root)["remainingUnits"] == 0
        server.require_execution(server.FEATURE_REWRITE)  # accessory: must not raise

        # Paid tiers are metered by the commercial authority; their work must
        # never touch this counter.
        before = local_quota.snapshot(root)["usedUnits"]
        server._charge_local_quota({"localFreeMode": False}, "digital-human")
        assert local_quota.snapshot(root)["usedUnits"] == before, "paid-tier usage leaked into the local counter"
    finally:
        server.bossai_os_bridge.configured = original_configured

    # The day rolls over on the local calendar date, not on elapsed time.
    state_path = root / "local-free-quota.json"
    stored = json.loads(state_path.read_text(encoding="utf-8"))
    stored["date"] = "2000-01-01"
    state_path.write_text(json.dumps(stored), encoding="utf-8")
    rolled = local_quota.snapshot(root)
    assert rolled["usedUnits"] == 0, rolled
    assert rolled["remainingUnits"] == local_quota.DEFAULT_DAILY_UNITS, rolled

    # A corrupt counter must not cost the customer their personal use. This is
    # deliberately fail-open: the counter shapes the free tier, it is not what
    # protects commercial use, and that distinction is the whole reason the
    # entitlement check is separate and fail-closed.
    state_path.write_text("{ not json", encoding="utf-8")
    recovered = local_quota.snapshot(root)
    assert recovered["remainingUnits"] == local_quota.DEFAULT_DAILY_UNITS, recovered

    # The allowance is operator-configurable without a rebuild.
    os.environ["BOSSAI_VIDEO_LOCAL_FREE_DAILY_UNITS"] = "6"
    try:
        assert local_quota.snapshot(root)["dailyUnits"] == 6
        local_quota.consume(root, "tts")
        assert local_quota.snapshot(root)["remainingUnits"] == 4
    finally:
        os.environ.pop("BOSSAI_VIDEO_LOCAL_FREE_DAILY_UNITS", None)

print("RESULT: BossAI Video Agent local Free Personal daily allowance passed.")
print(
    "Deliverables are charged on success at published costs, accessory calls are free, exhaustion returns 429 rather "
    "than reading as unlicensed, the counter resets on the local date, and paid-tier usage never touches it."
)
