from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import re
import shutil
import sys
from pathlib import Path

NOTICE_NAME = re.compile(r"^(license|licence|copying|notice|copyright|authors?)([._-].*)?$", re.IGNORECASE)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return cleaned or "unknown"


def canonical_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value.strip()).lower()


def load_supplements(manifest_path: Path | None) -> dict[tuple[str, str], dict[str, object]]:
    if manifest_path is None:
        return {}
    manifest_path = manifest_path.expanduser().resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if payload.get("schema") != "bossai.video-agent-python-license-supplements.v1":
        raise RuntimeError(f"unsupported supplemental license manifest: {manifest_path}")
    base = manifest_path.parent.resolve()
    result: dict[tuple[str, str], dict[str, object]] = {}
    for entry in payload.get("entries") or []:
        name = str(entry.get("name") or "").strip()
        version = str(entry.get("version") or "").strip()
        relative = Path(str(entry.get("path") or ""))
        expected = str(entry.get("sha256") or "").strip().lower()
        if not name or not version or not relative.parts or not expected:
            raise RuntimeError(f"invalid supplemental license entry in {manifest_path}: {entry!r}")
        source = (base / relative).resolve()
        try:
            source.relative_to(base)
        except ValueError as exc:
            raise RuntimeError(f"supplemental license escapes manifest directory: {relative}") from exc
        if not source.is_file():
            raise RuntimeError(f"supplemental license file is missing: {source}")
        actual = sha256(source)
        if actual != expected:
            raise RuntimeError(f"supplemental license SHA-256 mismatch for {name}=={version}: {actual}")
        key = (canonical_name(name), version)
        if key in result:
            raise RuntimeError(f"duplicate supplemental license entry for {name}=={version}")
        result[key] = {
            **entry,
            "sourcePath": source,
        }
    return result


def license_metadata(dist: metadata.Distribution) -> dict[str, object]:
    meta = dist.metadata
    classifiers = [str(item) for item in (meta.get_all("Classifier") or []) if "License" in str(item)]
    project_urls = [str(item) for item in (meta.get_all("Project-URL") or [])]
    return {
        "license": str(meta.get("License") or "").strip(),
        "licenseExpression": str(meta.get("License-Expression") or "").strip(),
        "licenseClassifiers": classifiers,
        "homePage": str(meta.get("Home-page") or "").strip(),
        "projectUrls": project_urls,
    }


def candidate_notice_files(dist: metadata.Distribution) -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()
    for file_entry in dist.files or []:
        relative = Path(str(file_entry).replace("\\", "/"))
        parts = relative.parts
        if not parts:
            continue
        name = relative.name
        parent_names = {part.lower() for part in parts[:-1]}
        is_license_dir = any(part in {"licenses", "license"} for part in parent_names)
        if not is_license_dir and not NOTICE_NAME.match(name):
            continue
        try:
            source = Path(dist.locate_file(file_entry)).resolve()
        except Exception:
            continue
        if not source.is_file():
            continue
        key = str(source).lower()
        if key in seen:
            continue
        seen.add(key)
        found.append(source)
    return sorted(found, key=lambda value: str(value).lower())


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture license/notice evidence from the exact active Python environment.")
    parser.add_argument("--component", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--supplemental-license-manifest", default="")
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()

    out = Path(args.out).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    python_out = out / "python"
    if python_out.exists():
        shutil.rmtree(python_out)
    python_out.mkdir(parents=True, exist_ok=True)

    supplements = load_supplements(Path(args.supplemental_license_manifest) if args.supplemental_license_manifest else None)
    records: list[dict[str, object]] = []
    missing_text: list[str] = []
    supplements_used: list[str] = []
    for dist in sorted(metadata.distributions(), key=lambda item: (str(item.metadata.get("Name") or "").lower(), item.version)):
        name = str(dist.metadata.get("Name") or "unknown").strip() or "unknown"
        version = str(dist.version or "").strip()
        destination = python_out / safe_name(name)
        destination.mkdir(parents=True, exist_ok=True)
        copied = []
        for index, source in enumerate(candidate_notice_files(dist), start=1):
            target_name = source.name
            target = destination / target_name
            if target.exists():
                target = destination / f"{index:02d}-{target_name}"
            shutil.copy2(source, target)
            copied.append({
                "path": target.relative_to(out).as_posix(),
                "sha256": sha256(target),
                "bytes": target.stat().st_size,
            })
        supplemental_used = False
        if not copied:
            supplement = supplements.get((canonical_name(name), version))
            if supplement:
                source = Path(supplement["sourcePath"])
                target = destination / f"SUPPLEMENTAL-{source.name}"
                shutil.copy2(source, target)
                copied.append({
                    "path": target.relative_to(out).as_posix(),
                    "sha256": sha256(target),
                    "bytes": target.stat().st_size,
                    "sourceType": "pinned-upstream-supplement",
                    "sourceUrl": str(supplement.get("sourceUrl") or ""),
                    "sourceSha256": str(supplement.get("sha256") or ""),
                    "declaredLicense": str(supplement.get("license") or ""),
                })
                supplemental_used = True
                supplements_used.append(f"{name}=={version}")
        license_info = license_metadata(dist)
        has_license_metadata = any([
            license_info["license"],
            license_info["licenseExpression"],
            license_info["licenseClassifiers"],
        ])
        if not copied:
            missing_text.append(f"{name}=={version}")
        records.append({
            "name": name,
            "version": version,
            **license_info,
            "licenseFiles": copied,
            "licenseMetadataPresent": bool(has_license_metadata),
            "licenseTextPresent": bool(copied),
            "supplementalLicenseUsed": supplemental_used,
        })

    report = {
        "schema": "bossai.video-agent-python-runtime-notices.v1",
        "component": args.component,
        "python": {
            "executable": sys.executable,
            "version": sys.version.split()[0],
        },
        "distributionCount": len(records),
        "completeLicenseTextCoverage": not missing_text,
        "distributionsMissingEmbeddedLicenseText": missing_text,
        "supplementalLicenseManifest": str(Path(args.supplemental_license_manifest).expanduser().resolve()) if args.supplemental_license_manifest else None,
        "supplementalLicensesUsed": supplements_used,
        "distributions": records,
    }
    report_path = out / "python-dependency-notices.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    complete = not missing_text
    print(json.dumps({
        "status": "passed" if complete else "incomplete",
        "component": args.component,
        "distributionCount": len(records),
        "missingEmbeddedLicenseTextCount": len(missing_text),
        "report": str(report_path),
    }, ensure_ascii=False, indent=2))
    if complete:
        print("RESULT: Python runtime notice snapshot captured with complete license-text coverage.")
    else:
        print("RESULT: Python runtime notice snapshot is incomplete; missing license text remains.")
    return 0 if complete or not args.require_complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
