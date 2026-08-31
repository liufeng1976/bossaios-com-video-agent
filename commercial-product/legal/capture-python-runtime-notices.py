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
    args = parser.parse_args()

    out = Path(args.out).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    python_out = out / "python"
    if python_out.exists():
        shutil.rmtree(python_out)
    python_out.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, object]] = []
    missing_text: list[str] = []
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
        "distributions": records,
    }
    report_path = out / "python-dependency-notices.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "passed",
        "component": args.component,
        "distributionCount": len(records),
        "missingEmbeddedLicenseTextCount": len(missing_text),
        "report": str(report_path),
    }, ensure_ascii=False, indent=2))
    print("RESULT: Python runtime notice snapshot captured from the exact active environment.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
