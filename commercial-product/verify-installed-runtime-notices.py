from __future__ import annotations

import argparse
import hashlib
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def verify_file_set(entries: list[tuple[Path, str, str]], component: str, item: dict[str, object], failures: list[str]) -> None:
    verified = 0
    total_bytes = 0
    for path, expected_hash, label in entries:
        if not path.is_file():
            failures.append(f"{component}: required runtime artifact missing: {label}")
            continue
        actual = sha256(path)
        if actual != expected_hash.lower():
            failures.append(f"{component}: runtime artifact SHA-256 mismatch: {label}")
            continue
        verified += 1
        total_bytes += path.stat().st_size
    item["runtimeArtifactCountExpected"] = len(entries)
    item["runtimeArtifactCountVerified"] = verified
    item["runtimeArtifactBytesVerified"] = total_bytes
    item["runtimeArtifactsComplete"] = verified == len(entries) and bool(entries)


def verify_env_paths(runtime_manifest: dict, component: str, runtime_root: Path, item: dict[str, object], failures: list[str]) -> None:
    env = runtime_manifest.get("env") or {}
    required: dict[str, str] = {}
    if component == "qwen2.5-7b-instruct":
        required = {"BOSSAI_QWEN_MODEL": "file", "BOSSAI_QWEN_SERVER": "file"}
    elif component == "cosyvoice2-0.5b":
        required = {"BOSSAI_COSYVOICE_ROOT": "dir", "BOSSAI_COSYVOICE_MODEL_DIR": "dir", "BOSSAI_COSYVOICE_PYTHON": "file"}
    elif component == "musetalk":
        required = {"BOSSAI_MUSETALK_ROOT": "dir", "BOSSAI_MUSETALK_PYTHON": "file", "TORCH_HOME": "dir", "BOSSAI_FFMPEG_BIN": "file"}
    resolved: dict[str, str] = {}
    declared: dict[str, str] = {}
    ok = True
    component_key = component.lower()
    for key, kind in required.items():
        raw = str(env.get(key) or "").strip()
        declared[key] = raw
        path = Path(raw).expanduser() if raw else Path()
        exists = bool(raw) and (path.is_file() if kind == "file" else path.is_dir())
        if raw and not exists and key != "BOSSAI_FFMPEG_BIN":
            parts = list(path.parts)
            match_index = next((index for index, part in enumerate(parts) if part.lower() == component_key), None)
            if match_index is not None:
                relocated = runtime_root.joinpath(*parts[match_index + 1 :])
                relocated_exists = relocated.is_file() if kind == "file" else relocated.is_dir()
                if relocated_exists:
                    path = relocated
                    exists = True
        resolved[key] = str(path) if raw else ""
        if not exists:
            failures.append(f"{component}: runtime environment path missing/unusable: {key}")
            ok = False
    item["runtimeEnvironmentPathsValid"] = ok
    item["runtimeEnvironmentDeclared"] = declared
    item["runtimeEnvironment"] = resolved


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
        if runtime_manifest.get("schema") not in {"bossai.video-agent-installed-runtime.v1", "bossai.video-agent-installed-runtime.v2"} or runtime_manifest.get("component") != component:
            failures.append(f"{component}: runtime manifest identity mismatch")
        lock_component = lock_components.get(component) or {}
        expected = expected_revision(lock_component, component)
        actual_source = runtime_manifest.get("source") or {}
        matches = all(str(actual_source.get(key) or "") == value and bool(value) for key, value in expected.items())
        item["sourceLockMatches"] = matches
        if not matches:
            failures.append(f"{component}: installed source/model revision does not match source lock")

        verify_env_paths(runtime_manifest, component, runtime_root, item, failures)
        runtime_entries: list[tuple[Path, str, str]] = []
        if component == "qwen2.5-7b-instruct":
            for file_entry in lock_component.get("files") or []:
                if not isinstance(file_entry, dict):
                    continue
                name = str(file_entry.get("name") or "")
                digest = str(file_entry.get("sha256") or "")
                if name and digest:
                    runtime_entries.append((runtime_root / "model" / name, digest, name))
            llama_server = runtime_root / "llama.cpp" / "llama-server.exe"
            if not llama_server.is_file():
                failures.append("qwen2.5-7b-instruct: pinned llama.cpp server executable missing")
                item["inferenceExecutablePresent"] = False
            else:
                item["inferenceExecutablePresent"] = True
        elif component == "cosyvoice2-0.5b":
            model_root = runtime_root / "model" / "CosyVoice2-0.5B"
            for name, digest in (lock_component.get("verifiedHashes") or {}).items():
                runtime_entries.append((model_root / str(name), str(digest), str(name)))
        elif component == "musetalk":
            source_root = runtime_root / "MuseTalk"
            for name, digest in (lock_component.get("verifiedHashes") or {}).items():
                runtime_entries.append((source_root / Path(str(name)), str(digest), str(name)))
            for artifact_name, artifact in (lock_component.get("implicitRuntimeArtifacts") or {}).items():
                if not isinstance(artifact, dict):
                    continue
                destination = str(artifact.get("destination") or "")
                digest = str(artifact.get("sha256") or "")
                if destination and digest:
                    runtime_entries.append((runtime_root / Path(destination), digest, f"implicit:{artifact_name}"))
        verify_file_set(runtime_entries, component, item, failures)

        if not primary_path.is_file():
            failures.append(f"{component}: primary upstream license missing: {primary_license}")

        if component == "musetalk":
            model_license_report_path = licenses_root / "model-license-evidence.json"
            item["modelLicenseEvidenceRequired"] = True
            item["modelLicenseEvidencePresent"] = model_license_report_path.is_file()
            model_license_ok = False
            if not model_license_report_path.is_file():
                failures.append("musetalk: model/dependency license evidence missing")
            else:
                try:
                    model_report = read_json(model_license_report_path)
                    expected_items = {str(entry.get("id") or ""): entry for entry in lock_component.get("modelLicenseEvidence") or [] if isinstance(entry, dict)}
                    actual_items = {str(entry.get("id") or ""): entry for entry in model_report.get("items") or [] if isinstance(entry, dict)}
                    model_license_ok = bool(
                        model_report.get("schema") == "bossai.video-agent-model-license-evidence.v1"
                        and model_report.get("component") == "musetalk"
                        and model_report.get("complete") is True
                        and expected_items
                        and set(actual_items) == set(expected_items)
                    )
                    if model_license_ok:
                        for evidence_id, expected_item in expected_items.items():
                            actual_item = actual_items[evidence_id]
                            for key in ("repository", "revision", "declaredLicense", "sha256"):
                                if str(actual_item.get(key) or "") != str(expected_item.get(key) or ""):
                                    model_license_ok = False
                                    break
                            if str(actual_item.get("sourceUrl") or "") != str(expected_item.get("url") or ""):
                                model_license_ok = False
                            evidence_path = runtime_root / str(actual_item.get("path") or "")
                            if not evidence_path.is_file() or sha256(evidence_path) != str(expected_item.get("sha256") or "").lower():
                                model_license_ok = False
                            if not model_license_ok:
                                break
                    item["modelLicenseEvidenceCount"] = len(actual_items)
                    item["modelLicenseEvidenceComplete"] = model_license_ok
                    if not model_license_ok:
                        failures.append("musetalk: model/dependency license evidence does not match source lock")
                except Exception as exc:
                    failures.append(f"musetalk: model/dependency license evidence unreadable: {exc}")
            ffmpeg_license = licenses_root / "FFmpeg-GPL-3.0-LICENSE.txt"
            ffmpeg_lock = lock_component.get("ffmpegRuntime") or {}
            ffmpeg_license_ok = bool(
                ffmpeg_license.is_file()
                and sha256(ffmpeg_license) == str(ffmpeg_lock.get("licenseFileSha256") or "").lower()
            )
            item["ffmpegLicenseEvidencePresent"] = ffmpeg_license.is_file()
            item["ffmpegLicenseEvidenceMatches"] = ffmpeg_license_ok
            if not ffmpeg_license_ok:
                failures.append("musetalk: pinned external FFmpeg GPL license evidence missing or mismatched")
        else:
            item["modelLicenseEvidenceRequired"] = False

        python_notice_required = component != "qwen2.5-7b-instruct"
        item["pythonDependencySnapshotRequired"] = python_notice_required
        if not python_notice_required:
            item["pythonDependencyLicenseTextComplete"] = True
        elif not snapshot_path.is_file():
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
