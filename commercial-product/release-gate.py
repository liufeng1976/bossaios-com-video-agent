from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_boundary():
    path = HERE / "verify-commercial-boundary.py"
    spec = importlib.util.spec_from_file_location("bossai_video_boundary", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load commercial boundary verifier: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed BossAI Video Agent commercial release gate.")
    parser.add_argument("--staging-root", default="", help="Optional unpacked/staging customer tree to scan")
    args = parser.parse_args()

    manifest = load_json(HERE / "product-manifest.json")
    inventory = load_json(HERE / "runtime-license-inventory.json")
    notices = load_json(HERE / "customer-third-party-notices.json")
    desktop_package = load_json(HERE / "desktop" / "package.json")
    customer_metadata = load_json(HERE / "customer-product-metadata.json")
    configured_icon = str((((desktop_package.get("build") or {}).get("win") or {}).get("icon") or "")).strip()
    desktop_icon = (HERE / "desktop" / configured_icon).resolve() if configured_icon else None
    ui_icon = HERE / "ui" / "public" / "bossai-video-mark.svg"
    brand_evidence_value = str(manifest.get("commercialBrandAssetEvidence") or "").strip()
    brand_evidence = (HERE / brand_evidence_value).resolve() if brand_evidence_value else None

    checks: list[dict[str, object]] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        checks.append({"id": check_id, "passed": bool(passed), "detail": detail})

    add("brand-exclusive", manifest.get("customerFacingBrand") == "BossAI" and manifest.get("legacyBrandScanPassed") is True,
        "Customer-facing identity must be BossAI-only and legacy-brand scan must pass.")
    add("independent-desktop", manifest.get("commercialDesktopShellPacked") is True and manifest.get("commercialDesktopBackendPackaged") is True,
        "Independent BossAI Electron shell and BossAI Video Engine must be packaged.")
    add("customer-metadata-identity",
        customer_metadata.get("productId") == "bossai-video-agent"
        and customer_metadata.get("productName") == "BossAI Video Agent"
        and customer_metadata.get("company") == "BossAI"
        and customer_metadata.get("desktopAppId") == "com.bossai.videoagent",
        "Customer metadata must expose BossAI-only product identity.")
    extra_resources = ((desktop_package.get("build") or {}).get("extraResources") or [])
    packaged_metadata_sources = {str(item.get("from") or "") for item in extra_resources if isinstance(item, dict)}
    forbidden_internal_metadata = {
        "../product-manifest.json",
        "../brand-policy.json",
        "../bossai-entitlement-contract.json",
        "../feature-entitlement-contract.json",
    }
    add("customer-metadata-sanitized",
        "../customer-product-metadata.json" in packaged_metadata_sources
        and not (packaged_metadata_sources & forbidden_internal_metadata),
        "Customer package must carry only sanitized customer product metadata, not internal governance manifests/contracts.")
    add("packaged-runtime-smoke", manifest.get("commercialDesktopPackagedRuntimeSmokePassed") is True,
        "Packaged desktop must start its bundled engine and close it cleanly.")
    packaged_violations = manifest.get("commercialDesktopPackagedBoundaryViolations")
    add("distribution-boundary", isinstance(packaged_violations, int) and packaged_violations == 0,
        "Packaged customer tree must have zero legacy/proprietary/credential boundary violations.")
    runtime_strategy = str(manifest.get("runtimeProvisioningStrategy") or "").strip()
    runtime_evidence_value = str(manifest.get("runtimeProvisioningEvidence") or "").strip()
    runtime_evidence = (HERE / runtime_evidence_value).resolve() if runtime_evidence_value else None
    if runtime_strategy == "customer-side-pinned-official-download":
        runtime_ready = bool(
            manifest.get("officialSourceRuntimeInstallersPrepared") is True
            and manifest.get("runtimeSourceLockPrepared") is True
            and manifest.get("runtimeProvisioningContractValidated") is True
            and manifest.get("baseInstallerBundlesModelWeights") is False
            and runtime_evidence is not None
            and runtime_evidence.is_file()
        )
        runtime_detail = "Base installer uses fail-closed customer-side pinned official downloads; it must not bundle model weights or legacy runtimes."
    else:
        runtime_ready = manifest.get("commercialRuntimePacksReady") is True
        runtime_detail = "Prebundled customer Qwen/CosyVoice2/MuseTalk runtime packs must be composed from traceable licensed sources."
    add("runtime-provisioning", runtime_ready, runtime_detail)
    runtime_notices_evidence_value = str(manifest.get("runtimeNoticesEvidence") or "").strip()
    runtime_notices_evidence = (HERE / runtime_notices_evidence_value).resolve() if runtime_notices_evidence_value else None
    runtime_notices_ready = False
    if manifest.get("commercialNoticesComplete") is True and runtime_notices_evidence is not None and runtime_notices_evidence.is_file():
        try:
            runtime_notices_report = load_json(runtime_notices_evidence)
            runtime_notices_ready = bool(
                runtime_notices_report.get("schema") == "bossai.video-agent-installed-runtime-notice-verification.v1"
                and runtime_notices_report.get("productId") == manifest.get("productId")
                and runtime_notices_report.get("passed") is True
                and not (runtime_notices_report.get("failures") or [])
            )
        except Exception:
            runtime_notices_ready = False
    add("license-notices", runtime_notices_ready,
        "Full license texts and required copyright/attribution notices for the exact installed runtime must be backed by a passing machine evidence file.")
    entitlement_evidence_value = str(manifest.get("bossaiLiveEntitlementEvidence") or "").strip()
    entitlement_evidence = (HERE / entitlement_evidence_value).resolve() if entitlement_evidence_value else None
    entitlement_ready = False
    if manifest.get("bossaiLiveEntitlementUatPassed") is True and entitlement_evidence is not None and entitlement_evidence.is_file():
        try:
            entitlement_report = load_json(entitlement_evidence)
            entitlement_state = entitlement_report.get("commercialEntitlement") or {}
            entitlement_ready = bool(
                entitlement_report.get("schema") == "bossai.video-agent-live-entitlement-evidence.v1"
                and entitlement_report.get("productId") == manifest.get("productId")
                and entitlement_report.get("passed") is True
                and entitlement_state.get("verified") is True
                and entitlement_state.get("schemaVersion") == "bossai.commercial-entitlement.v1"
                and entitlement_state.get("licenseActive") is True
                and entitlement_state.get("paidExecutionAllowed") is True
            )
        except Exception:
            entitlement_ready = False
    add("bossai-entitlement-live-uat", entitlement_ready,
        "A real customer BossAI account/device must have passing machine evidence for bossai.commercial-entitlement.v1 verification.")

    musetalk_evidence_value = str(manifest.get("musetalkCommercialRenderEvidence") or "").strip()
    musetalk_evidence = (HERE / musetalk_evidence_value).resolve() if musetalk_evidence_value else None
    musetalk_ready = False
    if manifest.get("musetalkCommercialRenderUatPassed") is True and musetalk_evidence is not None and musetalk_evidence.is_file():
        try:
            musetalk_report = load_json(musetalk_evidence)
            musetalk_ready = bool(
                musetalk_report.get("schema") == "bossai.video-agent-musetalk-commercial-uat.v1"
                and musetalk_report.get("productId") == manifest.get("productId")
                and musetalk_report.get("passed") is True
                and musetalk_report.get("ready") is True
                and musetalk_report.get("renderAttempted") is True
                and musetalk_report.get("authorizedMediaUsed") is True
            )
        except Exception:
            musetalk_ready = False
    add("musetalk-live-uat", musetalk_ready,
        "Commercial MuseTalk render must have passing machine evidence from an end-to-end render using authorized customer/BossAI-owned media.")

    signing_evidence_value = str(manifest.get("windowsCodeSigningEvidence") or "").strip()
    signing_evidence = (HERE / signing_evidence_value).resolve() if signing_evidence_value else None
    signing_ready = False
    if manifest.get("windowsCodeSigningValidated") is True and signing_evidence is not None and signing_evidence.is_file():
        try:
            signing_report = load_json(signing_evidence)
            signing_ready = bool(
                signing_report.get("schema") == "bossai.video-agent-windows-signing-evidence.v1"
                and signing_report.get("productId") == manifest.get("productId")
                and signing_report.get("passed") is True
                and (signing_report.get("application") or {}).get("valid") is True
                and (signing_report.get("installer") or {}).get("valid") is True
            )
        except Exception:
            signing_ready = False
    add("windows-code-signing", signing_ready,
        "Customer executable and NSIS installer must have passing Authenticode machine evidence from the exact release artifacts.")
    brand_assets_ready = bool(
        manifest.get("commercialBrandAssetsReady") is True
        and configured_icon == "build/icon.svg"
        and desktop_icon is not None and desktop_icon.is_file()
        and ui_icon.is_file()
        and brand_evidence is not None and brand_evidence.is_file()
    )
    add("brand-assets", brand_assets_ready,
        "Customer executable/installer must use BossAI-owned icons and visual brand assets, with machine evidence, instead of defaults.")
    legal_release_root = HERE / "legal" / "release"
    legal_manifest_path = legal_release_root / "legal-release-manifest.json"
    legal_files = (
        "CUSTOMER_TERMS.md",
        "PRIVACY_NOTICE.md",
        "VOICE_AVATAR_AUTHORIZATION.md",
        "SUPPORT_AND_INSTALLATION.md",
    )
    legal_ready = False
    if manifest.get("customerLegalDocumentsReady") is True and legal_manifest_path.is_file():
        try:
            legal_manifest = load_json(legal_manifest_path)
            legal_ready = bool(
                legal_manifest.get("schema") == "bossai.video-agent-legal-release.v1"
                and legal_manifest.get("productId") == manifest.get("productId")
                and legal_manifest.get("approved") is True
                and all((legal_release_root / name).is_file() for name in legal_files)
            )
        except Exception:
            legal_ready = False
    add("customer-legal", legal_ready,
        "Customer terms, privacy notice, voice/avatar authorization notice, support contact and approved legal-release manifest must be included.")

    publishing_enabled = bool(manifest.get("publishingEnabled"))
    add("publishing-uat", (not publishing_enabled) or manifest.get("realPublishingUatPassed") is True,
        "If publishing is enabled for customers, real-account UAT is mandatory before release.")

    default_stack = inventory.get("commercialDefaultStack") or {}
    components = {item.get("id"): item for item in inventory.get("components") or []}
    runtime_roles = manifest.get("commercialRuntimeRoles") or []
    stack_ids = [default_stack.get(str(role)) for role in runtime_roles]
    unsafe_stack = []
    for component_id in stack_ids:
        item = components.get(component_id) or {}
        status = str(item.get("commercialStatus") or "")
        if not component_id or status.startswith("blocked") or status in {"unknown", "requires-eula-review"}:
            unsafe_stack.append(component_id or "missing")
    add("default-stack-license-status", not unsafe_stack,
        "Default customer stack must not include a blocked/unknown-rights component: " + (", ".join(unsafe_stack) if unsafe_stack else "OK"))

    notice_ids = {item.get("id") for item in notices.get("components") or []}
    missing_notice_metadata = [component_id for component_id in stack_ids if component_id and component_id not in notice_ids]
    add("notice-metadata", not missing_notice_metadata,
        "Notice metadata must cover every default runtime component: " + (", ".join(missing_notice_metadata) if missing_notice_metadata else "OK"))

    staging_violations: list[dict[str, str]] = []
    if args.staging_root:
        staging_root = Path(args.staging_root).expanduser().resolve()
        if not staging_root.is_dir():
            add("staging-root", False, f"staging root does not exist: {staging_root}")
        else:
            staging_violations = load_boundary().classify(staging_root)
            add("staging-boundary", not staging_violations,
                f"customer staging boundary violations: {len(staging_violations)}")
            metadata_candidates = [staging_root / "metadata", staging_root / "resources" / "metadata"]
            metadata_root = next((candidate for candidate in metadata_candidates if candidate.is_dir()), metadata_candidates[0])
            internal_metadata_residue = [
                name for name in (
                    "product-manifest.json",
                    "brand-policy.json",
                    "bossai-entitlement-contract.json",
                    "feature-entitlement-contract.json",
                )
                if (metadata_root / name).exists()
            ]
            add("staging-customer-metadata",
                (metadata_root / "product.json").is_file() and not internal_metadata_residue,
                "Customer staging must contain sanitized metadata/product.json (root staging or Electron resources layout) only; internal metadata residue: "
                + (", ".join(internal_metadata_residue) if internal_metadata_residue else "none"))

    failed = [item for item in checks if not item["passed"]]
    report = {
        "schema": "bossai.video-agent-release-gate.v1",
        "productId": manifest.get("productId"),
        "version": manifest.get("version"),
        "passed": not failed,
        "distributionReadyDeclared": manifest.get("distributionReady") is True,
        "checks": checks,
        "failedChecks": [item["id"] for item in failed],
        "stagingViolations": staging_violations,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failed:
        print("RESULT: BossAI Video Agent commercial release gate FAILED CLOSED.")
        return 2
    if manifest.get("distributionReady") is not True:
        print("RESULT: release evidence passes but product-manifest distributionReady is still false.")
        return 3
    print("RESULT: BossAI Video Agent commercial release gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
