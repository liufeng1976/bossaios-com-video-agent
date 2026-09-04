from __future__ import annotations

import argparse
import json
from pathlib import Path

SCHEMA = "bossai.video-agent-legal-config.v1"
PRODUCT_ID = "bossai-video-agent"
REQUIRED_TEXT = (
    "approvedBy",
    "approvedAt",
    "legalEntityName",
    "registeredAddress",
    "supportEmail",
    "privacyContact",
    "governingLaw",
    "disputeVenue",
    "refundPolicy",
    "supportHours",
    "dataRetentionSummary",
    "termsEffectiveDate",
)
REQUIRED_LISTS = ("salesTerritories", "cloudProcessingRegions")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed customer legal release preflight for BossAI Video Agent.")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    path = Path(args.config).expanduser().resolve()
    failures: list[str] = []
    if not path.is_file():
        failures.append(f"legal config missing: {path}")
        data: dict = {}
    else:
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            failures.append(f"legal config unreadable: {exc}")
            data = {}

    if data.get("schema") != SCHEMA:
        failures.append("schema must be bossai.video-agent-legal-config.v1")
    if data.get("productId") != PRODUCT_ID:
        failures.append("productId must be bossai-video-agent")

    missing = [key for key in REQUIRED_TEXT if not str(data.get(key) or "").strip()]
    missing += [key for key in REQUIRED_LISTS if not data.get(key)]
    for key in missing:
        failures.append(f"required legal decision missing: {key}")

    if data.get("approved") is not True:
        failures.append("approved must be true only after authorized human/legal review")

    report = {
        "schema": "bossai.video-agent-legal-release-preflight.v1",
        "productId": PRODUCT_ID,
        "config": str(path),
        "passed": not failures,
        "approved": data.get("approved") is True,
        "missingRequiredDecisions": missing,
        "requiredTextFields": list(REQUIRED_TEXT),
        "requiredListFields": list(REQUIRED_LISTS),
        "failures": failures,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failures:
        print("RESULT: customer legal release preflight FAILED CLOSED.")
        return 2
    print("RESULT: customer legal release preflight passed; approved bundle may be generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
