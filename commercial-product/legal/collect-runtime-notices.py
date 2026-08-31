from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

PRODUCT_ID = "bossai-video-agent"
REQUIRED_COMPONENTS = ("qwen2.5-7b-instruct", "cosyvoice2-0.5b", "musetalk")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect exact installed runtime license/notice files for BossAI Video Agent.")
    parser.add_argument("--runtimes-root", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    runtimes_root = Path(args.runtimes_root).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()
    if not runtimes_root.is_dir():
        raise RuntimeError(f"runtime root does not exist: {runtimes_root}")
    if out.exists() and any(out.iterdir()) and not args.replace:
        raise RuntimeError(f"notice output is not empty: {out}")
    if out.exists() and args.replace:
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    components: list[dict[str, object]] = []
    for component in REQUIRED_COMPONENTS:
        root = runtimes_root / component
        runtime_manifest_path = root / "runtime.json"
        licenses_root = root / "licenses"
        if not runtime_manifest_path.is_file():
            raise RuntimeError(f"installed runtime manifest missing: {runtime_manifest_path}")
        runtime_manifest = read_json(runtime_manifest_path)
        if runtime_manifest.get("schema") != "bossai.video-agent-installed-runtime.v1":
            raise RuntimeError(f"invalid runtime manifest schema: {runtime_manifest_path}")
        if runtime_manifest.get("component") != component:
            raise RuntimeError(f"runtime manifest component mismatch: {runtime_manifest_path}")
        if not licenses_root.is_dir():
            raise RuntimeError(f"runtime license directory missing: {licenses_root}")
        license_files = sorted(path for path in licenses_root.rglob("*") if path.is_file())
        if not license_files:
            raise RuntimeError(f"no runtime license/notice files found: {licenses_root}")

        destination = out / component
        destination.mkdir(parents=True, exist_ok=False)
        files = []
        for source in license_files:
            relative = source.relative_to(licenses_root)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            files.append({
                "path": target.relative_to(out).as_posix(),
                "sha256": sha256(target),
                "bytes": target.stat().st_size,
            })
        components.append({
            "id": component,
            "source": runtime_manifest.get("source") or {},
            "licenseFiles": files,
        })

    summary = [
        "# BossAI Video Agent Third-Party Runtime Notices",
        "",
        "This bundle is generated from the exact installed customer runtime manifests and their copied upstream license/notice files.",
        "BossAI trademarks and product branding do not replace or modify upstream licenses.",
        "",
    ]
    for item in components:
        summary.extend([f"## {item['id']}", ""])
        for file_info in item["licenseFiles"]:
            summary.append(f"- `{file_info['path']}`")
        summary.append("")
    (out / "THIRD_PARTY_RUNTIME_NOTICES.md").write_text("\n".join(summary), encoding="utf-8")

    manifest = {
        "schema": "bossai.video-agent-runtime-notices.v1",
        "productId": PRODUCT_ID,
        "requiredComponents": list(REQUIRED_COMPONENTS),
        "complete": True,
        "components": components,
        "summary": "THIRD_PARTY_RUNTIME_NOTICES.md",
    }
    (out / "runtime-notices-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "components": len(components), "out": str(out)}, ensure_ascii=False, indent=2))
    print("RESULT: exact installed-runtime notice bundle collected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
