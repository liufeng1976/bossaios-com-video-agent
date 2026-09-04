from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_python(script: Path, *args: str) -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(HERE),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return proc.returncode == 0, proc.stdout.strip()


def runtime_root() -> Path | None:
    local = os.environ.get("LOCALAPPDATA", "").strip()
    if not local:
        return None
    config = Path(local) / "BossAI" / "VideoAgent" / "runtime-storage.json"
    if not config.is_file():
        return None
    try:
        value = str(read_json(config).get("runtimeRoot") or "").strip()
    except Exception:
        return None
    return Path(value).expanduser().resolve() if value else None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="BossAI Video Agent Internal Pilot gate. This is intentionally not the GA/commercial release gate."
    )
    parser.add_argument(
        "--installer",
        default=str(HERE / "desktop" / "dist" / "BossAI-Video-Agent-0.1.0-Setup.exe"),
    )
    parser.add_argument(
        "--application",
        default=str(HERE / "desktop" / "dist" / "win-unpacked" / "BossAI Video Agent.exe"),
    )
    parser.add_argument(
        "--engine",
        default=str(HERE / "desktop" / "dist" / "win-unpacked" / "resources" / "backend" / "BossAI Video Engine.exe"),
    )
    parser.add_argument("--staging-root", default=str(HERE / "desktop" / "dist" / "win-unpacked"))
    args = parser.parse_args()

    manifest = read_json(HERE / "product-manifest.json")
    installer = Path(args.installer).expanduser().resolve()
    application = Path(args.application).expanduser().resolve()
    engine = Path(args.engine).expanduser().resolve()
    staging = Path(args.staging_root).expanduser().resolve()
    root = runtime_root()

    checks: list[dict[str, object]] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        checks.append({"id": check_id, "passed": bool(passed), "detail": detail})

    add(
        "pilot-scope",
        manifest.get("distributionReady") is False and manifest.get("publishingEnabled") is False,
        "Pilot must remain non-GA and real publishing must stay disabled.",
    )
    add(
        "free-personal-product-policy",
        "free-personal" in (manifest.get("freemiumTiers") or [])
        and manifest.get("featureEntitlementGateIntegrated") is True,
        "Free Personal must exist and the feature entitlement gate must be integrated.",
    )
    add(
        "installer-present",
        installer.is_file(),
        f"Exact Pilot installer must exist: {installer}",
    )
    if installer.is_file():
        actual = sha256(installer)
        expected = str(manifest.get("commercialInstallerSha256") or "").lower()
        add("installer-sha256", actual == expected and bool(expected), f"installer SHA-256 actual={actual} expected={expected}")
    else:
        add("installer-sha256", False, "Installer is missing.")

    artifact_specs = (
        ("application", application, str(manifest.get("commercialApplicationSha256") or "").lower()),
        ("engine", engine, str(manifest.get("commercialEngineSha256") or "").lower()),
    )
    for name, path, expected in artifact_specs:
        if path.is_file():
            actual = sha256(path)
            add(f"{name}-sha256", actual == expected and bool(expected), f"{name} SHA-256 actual={actual} expected={expected}")
        else:
            add(f"{name}-sha256", False, f"{name} artifact missing: {path}")

    provisioning_ok, provisioning_output = run_python(HERE / "verify-runtime-provisioning.py")
    add("runtime-provisioning", provisioning_ok, provisioning_output[-1000:] if provisioning_output else "no output")

    entitlement_ok, entitlement_output = run_python(HERE / "backend" / "feature-entitlement-smoke-test.py")
    add("free-commercial-fail-closed", entitlement_ok, entitlement_output[-1000:] if entitlement_output else "no output")

    if root and root.is_dir():
        notices_ok, notices_output = run_python(HERE / "verify-installed-runtime-notices.py", "--runtimes-root", str(root))
        add("installed-runtimes", notices_ok, notices_output[-1200:] if notices_output else "no output")
    else:
        add("installed-runtimes", False, "Persisted BossAI runtime-storage.json does not resolve to an installed runtime root.")

    if staging.is_dir():
        boundary_ok, boundary_output = run_python(HERE / "verify-commercial-boundary.py", str(staging))
        add("packaged-boundary", boundary_ok, boundary_output[-1000:] if boundary_output else "no output")
    else:
        add("packaged-boundary", False, f"Unpacked customer staging is missing: {staging}")

    add(
        "packaged-runtime-smoke-evidence",
        manifest.get("commercialDesktopPackagedRuntimeSmokePassed") is True
        and manifest.get("commercialInstallerRuntimeSmokePassed") is True,
        "Both packaged desktop smoke and real installer smoke must already be recorded as passing.",
    )
    add(
        "runtime-license-evidence",
        manifest.get("installedRuntimeNoticeVerificationPassed") is True
        and manifest.get("commercialNoticesComplete") is True,
        "Exact installed runtime license/NOTICE evidence must be complete.",
    )
    add(
        "unsigned-pilot-only",
        manifest.get("windowsCodeSigningValidated") is False,
        "Unsigned build is permitted only for Internal Pilot; this condition MUST become false before GA/commercial release.",
    )
    add(
        "business-remains-unverified",
        manifest.get("bossaiLiveEntitlementUatPassed") is False,
        "Pilot may test Free Personal while Business use remains unavailable until live entitlement UAT passes.",
    )
    add(
        "musetalk-commercial-claim-disabled",
        manifest.get("musetalkCommercialRenderUatPassed") is False,
        "MuseTalk runtime may be exercised internally, but commercial render readiness must not be claimed before authorized-media live UAT.",
    )
    add(
        "customer-legal-not-ga",
        manifest.get("customerLegalDocumentsReady") is False,
        "Internal Pilot must not be represented as customer-ready GA while legal approval is incomplete.",
    )

    failed = [item for item in checks if not item["passed"]]
    report = {
        "schema": "bossai.video-agent-internal-pilot-gate.v1",
        "productId": manifest.get("productId"),
        "version": manifest.get("version"),
        "channel": "internal-pilot",
        "passed": not failed,
        "installer": {
            "path": str(installer),
            "sha256": sha256(installer) if installer.is_file() else "",
            "authenticodeRequired": False,
            "warning": "Unsigned Windows build. Internal Pilot only; SmartScreen/security warnings may appear.",
        },
        "runtimeRoot": str(root) if root else "",
        "checks": checks,
        "failedChecks": [item["id"] for item in failed],
        "gaBlockersIntentionallyExcluded": [
            "bossai-entitlement-live-uat",
            "musetalk-live-uat",
            "windows-code-signing",
            "customer-legal",
        ],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failed:
        print("RESULT: BossAI Video Agent Internal Pilot gate FAILED CLOSED.")
        return 2
    print("RESULT: BossAI Video Agent is INTERNAL PILOT READY. This is not a GA/commercial-release approval.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
