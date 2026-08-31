from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
os.environ.pop("BOSSAI_VIDEO_COMMERCIAL_PREVIEW", None)

with tempfile.TemporaryDirectory(prefix="bossai-video-feature-gate-") as temp_root:
    os.environ["BOSSAI_VIDEO_DATA_ROOT"] = str(Path(temp_root) / "data")
    import server
    from fastapi import HTTPException

    original_snapshot = server._entitlement_snapshot
    try:
        def expect_denied(snapshot: dict, feature: str) -> None:
            server._entitlement_snapshot = lambda: snapshot
            try:
                server.require_execution(feature)
            except HTTPException as exc:
                if exc.status_code != 403:
                    raise AssertionError(f"expected 403, got {exc.status_code}: {exc.detail}")
            else:
                raise AssertionError(f"feature unexpectedly allowed: {feature}")

        expect_denied(
            {"verified": False, "paidExecutionAllowed": False, "features": [], "reason": "not entitled"},
            server.FEATURE_REWRITE,
        )
        expect_denied(
            {"verified": True, "paidExecutionAllowed": True, "features": [server.FEATURE_TTS]},
            server.FEATURE_REWRITE,
        )

        for feature in (server.FEATURE_REWRITE, server.FEATURE_TTS, server.FEATURE_DIGITAL_HUMAN):
            server._entitlement_snapshot = lambda feature=feature: {
                "verified": True,
                "paidExecutionAllowed": True,
                "features": [feature],
            }
            server.require_execution(feature)

        server._entitlement_snapshot = lambda: {
            "verified": True,
            "paidExecutionAllowed": True,
            "features": [server.FEATURE_REWRITE],
        }
        expect_denied(server._entitlement_snapshot(), server.FEATURE_TTS)
    finally:
        server._entitlement_snapshot = original_snapshot

print("RESULT: BossAI Video Agent feature entitlement gate passed.")
print("Production execution requires verified entitlement plus the explicit requested feature code.")
