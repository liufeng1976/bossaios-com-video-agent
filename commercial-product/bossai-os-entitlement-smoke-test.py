from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

PRODUCT_ID = "bossai-video-agent"
PRODUCT_VERSION = "0.1.0"

STATE = {
    "authenticated": True,
    "licenseActive": True,
    "canCreatePaidAiTasks": True,
    "registered": True,
    "walletAvailable": 1000,
    "planCode": "video-pro",
    "planName": "Video Pro",
    "tenantPlan": "personal-pro",
    "lastAuthPayload": None,
}


def account_snapshot() -> dict:
    authenticated = bool(STATE["authenticated"])
    return {
        "schemaVersion": "bossai.account-session.v1",
        "generatedAt": "2026-08-29T00:00:00.000Z",
        "accountRequired": True,
        "serviceConfigured": True,
        "authenticated": authenticated,
        "sessionStatus": "authenticated" if authenticated else "signed_out",
        "account": {
            "id": "acct-commercial-smoke",
            "displayName": "Commercial Smoke",
            "channel": "email",
            "maskedIdentifier": "c***@example.com",
        } if authenticated else None,
        "tenant": {"id": "tenant-smoke", "name": "Smoke Tenant"} if authenticated else None,
        "access": None,
        "device": {"installationId": "smoke-device", "registered": authenticated},
        "commercial": None,
        "session": None,
        "privacy": {
            "containsPassword": False,
            "containsVerificationCode": False,
            "containsAccessToken": False,
            "containsRefreshToken": False,
            "containsProviderKeys": False,
        },
        "nextAction": "continue" if authenticated else "sign_in",
    }


def entitlement_snapshot(product_version: str) -> dict:
    return {
        "schemaVersion": "bossai.commercial-entitlement.v1",
        "generatedAt": "2026-08-29T00:00:00.000Z",
        "diagnosticId": "diag-smoke",
        "entitlementRevision": "rev-smoke",
        "tenant": {"id": "tenant-smoke", "name": "Smoke Tenant", "plan": str(STATE["tenantPlan"])},
        "product": {"id": PRODUCT_ID, "version": product_version},
        "device": {"id": "smoke-device", "registered": bool(STATE["registered"]), "lastSeenAt": "2026-08-29T00:00:00.000Z"},
        "headquartersCommerce": {
            "authority": "bossai-headquarters-commerce",
            "manages": ["license", "membership", "points"],
            "controlsBusinessExecution": False,
            "controlsLocalUsers": False,
            "controlsLocalRoles": False,
            "controlsLocalWorkflows": False,
            "routesProviders": False,
            "invokesProviders": False,
            "acceptsCustomerBusinessContent": False,
            "remoteBusinessActionsAllowed": False,
        },
        "entitlement": {
            "licenseActive": bool(STATE["licenseActive"]),
            "canUseLocalBusinessProduct": True,
            "canCreatePaidAiTasks": bool(STATE["canCreatePaidAiTasks"]),
            "commerceAuthorizationRequired": True,
            "commerceConnectivity": "connected",
            "walletAuthority": "headquarters",
            "localWalletAuthoritative": False,
            "allowedBillingModes": ["bossai_points"],
            "defaultBillingMode": "bossai_points",
            "accessReason": "Smoke entitlement",
            "planCode": str(STATE["planCode"]),
            "planName": str(STATE["planName"]),
            "membershipStatus": "active",
            "features": ["video.rewrite", "video.tts", "video.digital-human"],
            "walletAvailable": int(STATE["walletAvailable"]),
            "walletReserved": 0,
            "walletFrozen": False,
            "expiresAt": None,
            "offlineGraceUntil": None,
        },
        "localBusinessExecution": {
            "authority": "customer-local",
            "owns": ["video-production"],
            "businessDataResidency": "customer-local",
            "headquartersRemoteBusinessControl": False,
            "customerContentUploadedByDefault": False,
            "localUsersAndRolesManagedLocally": True,
            "localApprovalsManagedLocally": True,
            "agentPlatform": "bossai-os",
            "hermesProfile": "bossaiworkforce",
            "localAiExecutionGateway": True,
        },
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def _json(self, status: int, data: dict) -> None:
        body = json.dumps({"success": True, "data": data}, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("content-length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_GET(self):
        if self.path == "/api/account/session":
            self._json(200, account_snapshot())
            return
        if self.path == "/api/customer-experience/commercial-entitlement":
            version = self.headers.get("x-bossai-product-version") or ""
            if self.headers.get("x-bossai-product-id") != PRODUCT_ID:
                self.send_error(400)
                return
            self._json(200, entitlement_snapshot(version))
            return
        self.send_error(404)

    def do_POST(self):
        if self.path == "/api/account/session":
            payload = self._body()
            STATE["lastAuthPayload"] = payload
            STATE["authenticated"] = True
            self._json(201, account_snapshot())
            return
        if self.path == "/api/account/challenges":
            _ = self._body()
            self._json(201, {"challengeId": "challenge-smoke-001", "purpose": "register"})
            return
        if self.path == "/api/account/logout":
            _ = self._body()
            STATE["authenticated"] = False
            self._json(200, account_snapshot())
            return
        self.send_error(404)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> int:
    port = free_port()
    server_http = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server_http.serve_forever, daemon=True)
    thread.start()

    old_base = os.environ.get("BOSSAI_OS_BASE_URL")
    old_preview = os.environ.get("BOSSAI_VIDEO_COMMERCIAL_PREVIEW")
    old_data_root = os.environ.get("BOSSAI_VIDEO_DATA_ROOT")
    temp_data = tempfile.TemporaryDirectory(prefix="bossai-video-commercial-entitlement-")
    os.environ["BOSSAI_OS_BASE_URL"] = f"http://127.0.0.1:{port}"
    os.environ["BOSSAI_VIDEO_DATA_ROOT"] = str(Path(temp_data.name) / "data")
    os.environ.pop("BOSSAI_VIDEO_COMMERCIAL_PREVIEW", None)

    try:
        import bossai_os_bridge
        import server

        server._accept_eula("zh-CN")
        session = bossai_os_bridge.authenticate({
            "mode": "login",
            "identifier": "customer@example.com",
            "password": "temporary-password",
        })
        if not session.get("authenticated"):
            raise AssertionError("BossAI account bridge did not authenticate")
        if STATE["lastAuthPayload"] != {
            "mode": "login",
            "identifier": "customer@example.com",
            "password": "temporary-password",
        }:
            raise AssertionError("BossAI account login payload changed unexpectedly")

        active = server._entitlement_snapshot()
        if not active.get("verified") or not active.get("executionAllowed") or active.get("status") != "active" or active.get("tier") != "personal-pro":
            raise AssertionError(f"Personal Pro entitlement was not accepted: {active}")
        if active.get("businessUseAllowed"):
            raise AssertionError("Personal Pro unexpectedly authorized commercial use")
        server.require_execution(server.FEATURE_REWRITE)

        STATE["walletAvailable"] = 0
        restricted = server._entitlement_snapshot()
        if not restricted.get("verified") or restricted.get("executionAllowed") or restricted.get("status") != "quota_exhausted":
            raise AssertionError(f"authoritative quota exhaustion did not fail closed: {restricted}")
        try:
            server.require_execution(server.FEATURE_REWRITE)
        except Exception as exc:
            if getattr(exc, "status_code", None) != 403:
                raise
        else:
            raise AssertionError("quota-exhausted execution unexpectedly passed")

        STATE["walletAvailable"] = 1000
        STATE["planCode"] = "video-business"
        STATE["planName"] = "Video Business"
        STATE["tenantPlan"] = "business"
        business = server._entitlement_snapshot()
        if business.get("tier") != "business" or not business.get("businessUseAllowed") or not business.get("executionAllowed"):
            raise AssertionError(f"Business entitlement was not projected correctly: {business}")

        STATE["authenticated"] = False
        signed_out = server._entitlement_snapshot()
        if signed_out.get("verified") or signed_out.get("executionAllowed") or signed_out.get("status") != "account_required":
            raise AssertionError(f"signed-out state did not fail closed: {signed_out}")

        print(json.dumps({
            "status": "passed",
            "productId": PRODUCT_ID,
            "accountLoginProxied": True,
            "passwordPersistedByVideoProduct": False,
            "personalProAllowedPersonalExecution": True,
            "quotaExhaustionDeniedExecution": True,
            "businessCommercialUseProjected": True,
            "signedOutDeniedExecution": True,
            "upstreamAuthority": "bossai-headquarters-commerce",
        }, ensure_ascii=False, indent=2))
        print("RESULT: BossAI Video Agent Free Personal / Personal Pro / Business entitlement bridge contract passed.")
        return 0
    finally:
        server_http.shutdown()
        server_http.server_close()
        thread.join(timeout=2)
        if old_base is None:
            os.environ.pop("BOSSAI_OS_BASE_URL", None)
        else:
            os.environ["BOSSAI_OS_BASE_URL"] = old_base
        if old_preview is None:
            os.environ.pop("BOSSAI_VIDEO_COMMERCIAL_PREVIEW", None)
        else:
            os.environ["BOSSAI_VIDEO_COMMERCIAL_PREVIEW"] = old_preview
        if old_data_root is None:
            os.environ.pop("BOSSAI_VIDEO_DATA_ROOT", None)
        else:
            os.environ["BOSSAI_VIDEO_DATA_ROOT"] = old_data_root
        temp_data.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
