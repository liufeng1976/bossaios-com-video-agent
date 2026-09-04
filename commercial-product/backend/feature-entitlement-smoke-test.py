from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
os.environ.pop("BOSSAI_VIDEO_COMMERCIAL_PREVIEW", None)

with tempfile.TemporaryDirectory(prefix="bossai-video-freemium-gate-") as temp_root:
    os.environ["BOSSAI_VIDEO_DATA_ROOT"] = str(Path(temp_root) / "data")
    import server
    from fastapi import HTTPException

    assert server._normalize_plan_tier({"planCode": "video-free"}, {}) == server.TIER_FREE_PERSONAL
    assert server._normalize_plan_tier({"planCode": "video-pro"}, {}) == server.TIER_PERSONAL_PRO
    assert server._normalize_plan_tier({"planCode": "video-business"}, {}) == server.TIER_BUSINESS
    assert server._normalize_plan_tier({}, {"plan": "enterprise"}) == server.TIER_BUSINESS
    assert server._normalize_plan_tier({"planCode": "mystery"}, {}) == "unknown"

    acceptance = server._accept_eula("zh-CN")
    assert acceptance["accepted"] is True
    assert server._eula_acceptance()["productVersion"] == server.PRODUCT_VERSION

    original_configured = server.bossai_os_bridge.configured
    try:
        server.bossai_os_bridge.configured = lambda: False
        local_free = server._entitlement_snapshot()
        assert local_free["status"] == "local_free"
        assert local_free["tier"] == server.TIER_FREE_PERSONAL
        assert local_free["verified"] is True
        assert local_free["executionAllowed"] is True
        assert local_free["gatewayExecutionAllowed"] is False
        assert local_free["businessUseAllowed"] is False
        assert local_free["localFreeMode"] is True
        assert set(local_free["features"]) == set(server.CORE_FEATURES)
    finally:
        server.bossai_os_bridge.configured = original_configured

    original_snapshot = server._entitlement_snapshot
    try:
        server._entitlement_snapshot = lambda: {
            "verified": True,
            "executionAllowed": True,
            "features": sorted(server.CORE_FEATURES),
        }
        for feature in server.CORE_FEATURES:
            server.require_execution(feature)

        server._entitlement_snapshot = lambda: {
            "verified": True,
            "executionAllowed": False,
            "features": sorted(server.CORE_FEATURES),
            "reason": "quota exhausted",
        }
        try:
            server.require_execution(server.FEATURE_REWRITE)
        except HTTPException as exc:
            assert exc.status_code == 403
        else:
            raise AssertionError("quota-restricted execution unexpectedly passed")

        server._entitlement_snapshot = lambda: {
            "verified": True,
            "executionAllowed": True,
            "features": [server.FEATURE_REWRITE],
        }
        try:
            server.require_execution(server.FEATURE_TTS)
        except HTTPException as exc:
            assert exc.status_code == 403
        else:
            raise AssertionError("feature-level entitlement unexpectedly bypassed")
    finally:
        server._entitlement_snapshot = original_snapshot

print("RESULT: BossAI Video Agent local Free Personal + Personal Pro / Business entitlement gate passed.")
print("Local Free Personal works without BossAI sign-in after license acceptance; Gateway and commercial use remain external BossAI authority state and fail closed without verified authorization.")
