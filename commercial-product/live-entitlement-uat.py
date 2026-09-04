from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import bossai_os_bridge

PRODUCT_ID = "bossai-video-agent"
PRODUCT_VERSION = "0.1.0"
SCHEMA = "bossai.video-agent-live-entitlement-evidence.v1"
EXPECTED_ENTITLEMENT_SCHEMA = "bossai.commercial-entitlement.v1"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_report(report: dict, out: str) -> None:
    if not out:
        return
    path = Path(out).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only live BossAI OS / Headquarters entitlement UAT for BossAI Video Agent."
    )
    parser.add_argument("--installation-id", default="bossai-video-agent-live-uat")
    parser.add_argument("--product-version", default=PRODUCT_VERSION)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    report = {
        "schema": SCHEMA,
        "productId": PRODUCT_ID,
        "productVersion": args.product_version,
        "generatedAt": now_iso(),
        "passed": False,
        "accountSession": {
            "reachable": False,
            "authenticated": False,
            "serviceConfigured": False,
        },
        "commercialEntitlement": {
            "verified": False,
            "schemaVersion": "",
            "authority": "",
            "licenseActive": False,
            "paidExecutionAllowed": False,
            "businessUseAllowed": False,
        },
        "reasonCode": "",
        "reason": "",
        "privacy": {
            "containsPassword": False,
            "containsVerificationCode": False,
            "containsAccessToken": False,
            "containsRefreshToken": False,
            "containsProviderKeys": False,
            "containsCustomerContent": False,
        },
    }

    try:
        session = bossai_os_bridge.account_session()
        report["accountSession"] = {
            "reachable": True,
            "authenticated": bool(session.get("authenticated")),
            "serviceConfigured": bool(session.get("serviceConfigured", session.get("accountRequired", False))),
            "sessionStatus": str(session.get("sessionStatus") or ""),
        }
        if not bool(session.get("authenticated")):
            report["reasonCode"] = "BOSSAI_ACCOUNT_NOT_AUTHENTICATED"
            report["reason"] = "BossAI account service is reachable but no authenticated customer session is available."
            write_report(report, args.out)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            print("RESULT: live BossAI commercial entitlement UAT FAILED CLOSED (no authenticated customer session).")
            return 2

        raw = bossai_os_bridge.entitlement(
            installation_id=args.installation_id,
            product_version=args.product_version,
        )
        entitlement = raw.get("entitlement") or {}
        authority = raw.get("headquartersCommerce") or {}
        license_active = bool(entitlement.get("licenseActive"))
        paid_execution_allowed = bool(entitlement.get("canCreatePaidAiTasks"))
        business_use_allowed = bool(entitlement.get("canUseLocalBusinessProduct"))
        verified = bool(
            raw.get("schemaVersion") == EXPECTED_ENTITLEMENT_SCHEMA
            and bossai_os_bridge.ENTITLEMENT_SCHEMA == EXPECTED_ENTITLEMENT_SCHEMA
            and authority.get("authority") == "bossai-headquarters-commerce"
            and license_active
            and paid_execution_allowed
            and business_use_allowed
        )
        report["commercialEntitlement"] = {
            "verified": verified,
            "schemaVersion": str(raw.get("schemaVersion") or ""),
            "authority": str(authority.get("authority") or ""),
            "licenseActive": license_active,
            "paidExecutionAllowed": paid_execution_allowed,
            "businessUseAllowed": business_use_allowed,
        }
        report["passed"] = verified
        if not verified:
            report["reasonCode"] = "BOSSAI_BUSINESS_ENTITLEMENT_NOT_ACTIVE"
            report["reason"] = "A live entitlement response was received but it does not authorize Business paid execution."
        else:
            report["reasonCode"] = "PASS"
            report["reason"] = "Live BossAI Headquarters Business entitlement is verified for this product/version."
    except bossai_os_bridge.BossAIOSBridgeError as exc:
        report["reasonCode"] = exc.code
        report["reason"] = str(exc)

    write_report(report, args.out)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["passed"]:
        print("RESULT: live BossAI commercial entitlement UAT PASSED.")
        return 0
    print("RESULT: live BossAI commercial entitlement UAT FAILED CLOSED.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
