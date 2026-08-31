from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

PRODUCT_ID = "bossai-video-agent"
ENTITLEMENT_SCHEMA = "bossai.commercial-entitlement.v1"


class BossAIOSBridgeError(RuntimeError):
    def __init__(self, code: str, message: str, *, status: int = 503):
        super().__init__(message)
        self.code = code
        self.status = status


def _base_url() -> str:
    raw = os.environ.get("BOSSAI_OS_BASE_URL", "").strip().rstrip("/")
    if not raw:
        return ""
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise BossAIOSBridgeError(
            "BOSSAI_OS_ENDPOINT_INVALID",
            "BossAI OS bridge must use a loopback HTTP endpoint on the same customer device.",
            status=500,
        )
    return raw


def configured() -> bool:
    try:
        return bool(_base_url())
    except BossAIOSBridgeError:
        return False


def _headers(*, product_headers: dict[str, str] | None = None) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    desktop_token = os.environ.get("BOSSAI_OS_DESKTOP_TOKEN", "").strip()
    if desktop_token:
        headers["x-bossai-desktop-token"] = desktop_token
    if product_headers:
        headers.update(product_headers)
    return headers


def _request(method: str, path: str, *, body: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    base = _base_url()
    if not base:
        raise BossAIOSBridgeError("BOSSAI_OS_NOT_CONFIGURED", "BossAI OS is not connected on this installation.")

    payload = None
    merged_headers = _headers(product_headers=headers)
    if body is not None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        merged_headers["Content-Type"] = "application/json"

    request = urllib.request.Request(base + path, data=payload, method=method.upper(), headers=merged_headers)
    try:
        with urllib.request.urlopen(request, timeout=8.0) as response:
            raw = response.read().decode("utf-8", errors="replace")
            parsed = json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {}
        detail = parsed.get("message") or parsed.get("detail") or str(exc.reason or "BossAI OS request failed")
        if isinstance(detail, list):
            detail = "; ".join(str(item.get("message") or item.get("msg") or item) for item in detail)
        raise BossAIOSBridgeError(
            str(parsed.get("code") or f"BOSSAI_OS_HTTP_{exc.code}"),
            str(detail),
            status=int(exc.code),
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise BossAIOSBridgeError("BOSSAI_OS_UNAVAILABLE", f"BossAI OS is unavailable: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise BossAIOSBridgeError("BOSSAI_OS_RESPONSE_INVALID", "BossAI OS returned invalid JSON.") from exc

    if parsed.get("success") is False:
        raise BossAIOSBridgeError(
            str(parsed.get("code") or "BOSSAI_OS_REQUEST_REJECTED"),
            str(parsed.get("message") or parsed.get("detail") or "BossAI OS rejected the request."),
            status=400,
        )
    return parsed.get("data", parsed)


def account_session() -> dict[str, Any]:
    if not configured():
        return {
            "schemaVersion": "bossai.account-session.v1",
            "accountRequired": True,
            "serviceConfigured": False,
            "authenticated": False,
            "sessionStatus": "not_configured",
            "account": None,
            "commercial": None,
            "nextAction": "connect_bossai_os",
        }
    value = _request("GET", "/api/account/session")
    if not isinstance(value, dict) or value.get("schemaVersion") != "bossai.account-session.v1":
        raise BossAIOSBridgeError("BOSSAI_ACCOUNT_SESSION_INVALID", "BossAI OS returned an invalid account-session contract.")
    return value


def create_challenge(payload: dict[str, Any]) -> Any:
    return _request("POST", "/api/account/challenges", body=payload)


def authenticate(payload: dict[str, Any]) -> dict[str, Any]:
    value = _request("POST", "/api/account/session", body=payload)
    if not isinstance(value, dict) or value.get("schemaVersion") != "bossai.account-session.v1":
        raise BossAIOSBridgeError("BOSSAI_ACCOUNT_SESSION_INVALID", "BossAI OS returned an invalid authenticated account session.")
    return value


def logout() -> dict[str, Any]:
    value = _request("POST", "/api/account/logout", body={})
    if not isinstance(value, dict):
        raise BossAIOSBridgeError("BOSSAI_ACCOUNT_LOGOUT_INVALID", "BossAI OS returned an invalid logout response.")
    return value


def entitlement(*, installation_id: str, product_version: str) -> dict[str, Any]:
    value = _request(
        "GET",
        "/api/customer-experience/commercial-entitlement",
        headers={
            "x-bossai-product-id": PRODUCT_ID,
            "x-bossai-installation-id": str(installation_id),
            "x-bossai-product-version": str(product_version),
        },
    )
    if not isinstance(value, dict) or value.get("schemaVersion") != ENTITLEMENT_SCHEMA:
        raise BossAIOSBridgeError("BOSSAI_ENTITLEMENT_INVALID", "BossAI OS returned an invalid commercial entitlement contract.")
    product = value.get("product") or {}
    if product.get("id") != PRODUCT_ID or product.get("version") != product_version:
        raise BossAIOSBridgeError("BOSSAI_ENTITLEMENT_PRODUCT_MISMATCH", "Commercial entitlement belongs to another product or version.", status=403)
    authority = value.get("headquartersCommerce") or {}
    if authority.get("authority") != "bossai-headquarters-commerce":
        raise BossAIOSBridgeError("BOSSAI_ENTITLEMENT_AUTHORITY_INVALID", "Commercial entitlement authority is invalid.", status=403)
    return value
