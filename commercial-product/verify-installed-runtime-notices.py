from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
REQUIRED = {
    "qwen2.5-7b-instruct": "Qwen-LICENSE.txt",
    "cosyvoice2-0.5b": "CosyVoice-LICENSE.txt",
    "musetalk": "MuseTalk-LICENSE.txt",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def default_root() -> Path:
    local = os.environ.get("LOCALAPPDATA", "").strip()
    if not local:
        raise RuntimeError("LOCALAPPDATA is unavailable; pass --runtimes-root explicitly")
    return Path(local) / "BossAI" / "VideoAgent" / "runtimes"


def expected_revision(lock_component: dict, component: str) -> dict[str, str]:
    if component == "qwen2.5-7b-instruct":
        return {"revision": str(lock_component.get("revision") or "")}
    return {
        "revision": str(lock_component.get("sourceRevision") or ""),
        "modelRevision": str(lock_component.get("modelRevision") or ""),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed exact installed-runtime LICENSE/NOTICE verifier for BossAI Video Agent.")
    parser.add_argument("--runtimes-root", default="")
    args = parser.parse_args()

    root = Path(args.runtimes_root).expanduser().resolve() if args.runtimes_root else default_root().resolve()
    source_lock = read_json(HERE / "runtime-installers" / "runtime-source-lock.json")
    lock_components = source_lock.get("components") or {}

    components: list[dict[str, object]] = []
    failures: list[str] = []
    for component, primary_license in REQUIRED.items():
        runtime_root = root / component
        runtime_manifest_path = runtime_root / "runtime.json"
        licenses_root = runtime_root / "licenses"
        snapshot_path = licenses_root / "python-dependency-notices.json"
        primary_path = licenses_root / primary_license
        item: dict[str, object] = {
            "id": component,
            "runtimeRoot": str(runtime_root),
            "runtimeManifestPresent": runtime_manifest_path.is_file(),
            "primaryLicensePresent": primary_path.is_file(),
            "pythonDependencySnapshotPresent": snapshot_path.is_file(),
            "sourceLockMatches": False,
            "pythonDependencyLicenseTextComplete": False,
        }

        if not runtime_manifest_path.is_file():
            failures.append(f"{component}: runtime.json missing")
            components.append(item)
            continue
        try:
            runtime_manifest = read_json(runtime_manifest_path)
        except Exception as exc:
            failures.append(f"{component}: runtime.json unreadable: {exc}")
            components.append(item)
            continue
        if runtime_manifest.get("schema") != "bossai.video-agent-installed-runtime.v1" or runtime_manifest.get("component") != component:
            failures.append(f"{component}: runtime manifest identity mismatch")
        lock_component = lock_components.get(component) or {}
        expected = expected_revision(lock_component, component)
        actual_source = runtime_manifest.get("source") or {}
        matches = all(str(actual_source.get(key) or "") == value and bool(value) for key, value in expected.items())
        item["sourceLockMatches"] = matches
        if not matches:
            failures.append(f"{component}: installed source/model revision does not match source lock")

        if not primary_path.is_file():
            failures.append(f"{component}: primary upstream license missing: {primary_license}")

        if not snapshot_path.is_file():
            failures.append(f"{component}: python dependency notice snapshot missing")
        else:
            try:
                snapshot = read_json(snapshot_path)
                snapshot_ok = bool(
                    snapshot.get("schema") == "bossai.video-agent-python-runtime-notices.v1"
                    and snapshot.get("component") == component
                    and int(snapshot.get("distributionCount") or 0) > 0
                    and snapshot.get("completeLicenseTextCoverage") is True
                    and not (snapshot.get("distributionsMissingEmbeddedLicenseText") or [])
                )
                item["pythonDependencyLicenseTextComplete"] = snapshot_ok
                item["pythonDistributionCount"] = int(snapshot.get("distributionCount") or 0)
                item["missingEmbeddedLicenseTextCount"] = len(snapshot.get("distributionsMissingEmbeddedLicenseText") or [])
                if not snapshot_ok:
                    failures.append(f"{component}: Python dependency full license-text coverage is incomplete")
            except Exception as exc:
                failures.append(f"{component}: Python dependency notice snapshot unreadable: {exc}")

        item["licenseFileCount"] = len([path for path in licenses_root.rglob("*") if path.is_file()]) if licenses_root.is_dir() else 0
        components.append(item)

    report = {
        "schema": "bossai.video-agent-installed-runtime-notice-verification.v1",
        "productId": "bossai-video-agent",
        "runtimesRoot": str(root),
        "passed": not failures,
        "requiredComponents": list(REQUIRED),
        "components": components,
        "failures": failures,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failures:
        print("RESULT: installed BossAI runtime notice verification FAILED CLOSED.")
        return 2
    print("RESULT: installed BossAI runtime LICENSE/NOTICE coverage verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
