from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRODUCT_ID = "bossai-video-agent"
PRODUCT_VERSION = "0.1.0"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_file(source: Path, target: Path) -> None:
    if not source.is_file():
        raise RuntimeError(f"required commercial source file is missing: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def load_boundary_verifier():
    path = HERE / "verify-commercial-boundary.py"
    spec = importlib.util.spec_from_file_location("bossai_video_distribution_boundary", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load commercial distribution boundary verifier: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def staged_files(root: Path) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if path.name == "staging-manifest.json":
            continue
        items.append(
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return items


def assemble(ui_dist: Path, out: Path, *, replace: bool, engine_exe: Path | None = None) -> dict[str, object]:
    ui_dist = ui_dist.expanduser().resolve()
    out = out.expanduser().resolve()
    if not (ui_dist / "index.html").is_file():
        raise RuntimeError(f"BossAI commercial UI dist is missing index.html: {ui_dist}")
    if out.exists():
        if not replace:
            raise RuntimeError(f"staging directory already exists: {out}; pass --replace to rebuild it")
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=False)

    desktop = HERE / "desktop"
    backend = HERE / "backend"

    for name in ("main.cjs", "preload.cjs", "package.json"):
        copy_file(desktop / name, out / "desktop" / name)

    if engine_exe is not None:
        copy_file(engine_exe.expanduser().resolve(), out / "backend" / "BossAI Video Engine.exe")
    else:
        for name in (
            "server.py",
            "bossai_os_bridge.py",
            "qwen_adapter.py",
            "cosyvoice_adapter.py",
            "cosyvoice_worker.py",
            "musetalk_adapter.py",
            "requirements.txt",
        ):
            copy_file(backend / name, out / "backend" / name)

    shutil.copytree(ui_dist, out / "ui" / "dist", dirs_exist_ok=False)

    copy_file(HERE / "customer-product-metadata.json", out / "metadata" / "product.json")
    copy_file(HERE / "customer-third-party-notices.json", out / "legal" / "third-party-notices.json")
    copy_file(HERE.parent / "EULA.md", out / "legal" / "EULA.md")
    copy_file(HERE.parent / "LICENSE", out / "legal" / "HISTORICAL-MIT-LICENSE.txt")
    copy_file(HERE.parent / "COMMERCIAL_LICENSE.md", out / "legal" / "COMMERCIAL-LICENSE.md")
    copy_file(HERE.parent / "TERMS.md", out / "legal" / "TERMS.md")
    copy_file(HERE.parent / "PRIVACY.md", out / "legal" / "PRIVACY.md")
    copy_file(HERE.parent / "INSTALL.md", out / "legal" / "INSTALL.md")

    legal_release = HERE / "legal" / "release"
    if legal_release.is_dir():
        shutil.copytree(legal_release, out / "legal" / "release", dirs_exist_ok=False)
    runtime_notices = HERE / "legal" / "runtime-notices"
    if runtime_notices.is_dir():
        shutil.copytree(runtime_notices, out / "legal" / "runtime-notices", dirs_exist_ok=False)

    runtime_installers = HERE / "runtime-installers"
    for name in (
        "install-python310.ps1",
        "install-qwen.ps1",
        "install-cosyvoice2.ps1",
        "install-musetalk.ps1",
        "musetalk-constraints.txt",
        "musetalk-windows-requirements.txt",
        "cosyvoice-windows-requirements.txt",
        "runtime-source-lock.json",
    ):
        copy_file(runtime_installers / name, out / "runtime-installers" / name)

    boundary = load_boundary_verifier()
    violations = boundary.classify(out)
    if violations:
        raise RuntimeError("commercial staging violates distribution boundary: " + json.dumps(violations, ensure_ascii=False))

    files = staged_files(out)
    manifest = {
        "schema": "bossai.video-agent-commercial-staging.v1",
        "productId": PRODUCT_ID,
        "productVersion": PRODUCT_VERSION,
        "customerFacingBrand": "BossAI",
        "legacyBrandMatches": 0,
        "legacyUpstreamBinaryIncluded": False,
        "modelWeightsIncluded": False,
        "customerRuntimeStateIncluded": False,
        "credentialsIncluded": False,
        "customerProductMetadataIncluded": True,
        "communitySourceLicenseIncluded": True,
        "commercialLicenseSummaryIncluded": True,
        "internalGovernanceMetadataIncluded": False,
        "legalReleaseIncluded": (out / "legal" / "release" / "legal-release-manifest.json").is_file(),
        "runtimeNoticesIncluded": (out / "legal" / "runtime-notices" / "runtime-notices-manifest.json").is_file(),
        "distributionBoundaryPassed": True,
        "backendEngineIncluded": bool(engine_exe),
        "backendSourceIncluded": engine_exe is None,
        "installerReady": False,
        "reasonInstallerNotReady": "The BossAI control engine can be bundled independently, but Qwen/CosyVoice2/MuseTalk runtime packs and the final exact license/NOTICE bundle still require customer-distribution composition and UAT.",
        "files": files,
    }
    (out / "staging-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble a fail-closed BossAI Video Agent customer staging tree.")
    parser.add_argument("--ui-dist", required=True, help="Built BossAI commercial UI dist directory")
    parser.add_argument("--out", required=True, help="Destination staging directory")
    parser.add_argument("--replace", action="store_true", help="Replace an existing staging directory")
    parser.add_argument("--engine-exe", default="", help="Optional compiled BossAI Video Engine.exe to include in customer staging")
    args = parser.parse_args()

    engine_exe = Path(args.engine_exe) if str(args.engine_exe).strip() else None
    result = assemble(Path(args.ui_dist), Path(args.out), replace=args.replace, engine_exe=engine_exe)
    print(json.dumps({
        "status": "passed",
        "productId": result["productId"],
        "fileCount": len(result["files"]),
        "distributionBoundaryPassed": result["distributionBoundaryPassed"],
        "legacyBrandMatches": result["legacyBrandMatches"],
        "backendEngineIncluded": result["backendEngineIncluded"],
        "backendSourceIncluded": result["backendSourceIncluded"],
        "installerReady": result["installerReady"],
    }, ensure_ascii=False, indent=2))
    print("RESULT: BossAI Video Agent staging assembled without legacy customer-facing identity.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
