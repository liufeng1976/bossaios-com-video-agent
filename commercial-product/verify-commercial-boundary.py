from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

# Keep legacy identifiers out of commercial source text as well as customer builds.
# Sensitive/legacy markers are assembled instead of embedded verbatim.
LEGACY_LAUNCHER_NAME = "AI" + "Agent.exe"
LEGACY_ELECTRON_NAME = "AI" + "智能体.exe"
LEGACY_PRODUCT_MARKER = "AI" + "Agent"
LEGACY_REPAIR_MARKER = "AI-" + "Agent-T"
LEGACY_CN_PRODUCT_MARKER = "AI" + "智能体"
LEGACY_PERSON_MARKER = "".join(chr(value) for value in (0x5CB3, 0x54E5))
LEGACY_CLOUD_MARKER = "ai" + "bigbox"
LEGACY_PRODUCT_TYPE_MARKER = "DIGITAL" + "_AGENT"
LEGACY_WORKBENCH_MARKER = "".join(chr(value) for value in (0x7206, 0x6B3E, 0x53E3, 0x64AD, 0x667A, 0x80FD, 0x4F53))
LEGACY_RECOVERY_MARKER = "re" + "covered"
LEGACY_RECONSTRUCTION_MARKER = "re" + "constructed"
LEGACY_HEYVIDEO_MARKER = "Hey" + "Video"

FORBIDDEN_EXACT_NAMES = {
    LEGACY_LAUNCHER_NAME,
    LEGACY_ELECTRON_NAME,
    "key.txt",
    "activation.json",
    "local.db",
}

FORBIDDEN_UPSTREAM_SHA256 = {
    "3ac683e61e00c32421b980a8ac56a5f4fad6c9e29112da1c3601825992fcbb44": "legacy upstream launcher binary",
    "a84d8461d6f40e7d986d708cbf591cb4260f328217231e060181383e494545a8": "legacy upstream Electron executable",
    "34ecda0180c4ff25ace1baac8bce2e996a5ab2bf011fedb0dd0360910b60308f": "legacy upstream production bundle",
}

FORBIDDEN_PATH_PARTS = {
    "user_data",
    "cookies",
    "sessions",
    "__pycache__",
}

FORBIDDEN_WEIGHT_SUFFIXES = {
    ".gguf",
    ".safetensors",
    ".ckpt",
    ".pth",
    ".pt",
    ".onnx",
}

TEXT_SUFFIXES = {
    ".html",
    ".css",
    ".js",
    ".cjs",
    ".mjs",
    ".json",
    ".md",
    ".txt",
    ".vue",
    ".ts",
    ".tsx",
    ".jsx",
    ".yaml",
    ".yml",
    ".xml",
    ".ini",
    ".cfg",
    ".ps1",
    ".cmd",
    ".bat",
}

FORBIDDEN_TEXT_MARKERS = {
    LEGACY_PERSON_MARKER: "legacy person/brand marker",
    LEGACY_CN_PRODUCT_MARKER: "legacy Chinese product marker",
    LEGACY_PRODUCT_MARKER: "legacy upstream product marker",
    LEGACY_CLOUD_MARKER: "legacy upstream cloud-domain marker",
    LEGACY_PRODUCT_TYPE_MARKER: "legacy upstream product-type marker",
    LEGACY_WORKBENCH_MARKER: "legacy upstream workbench label",
    LEGACY_RECOVERY_MARKER: "internal recovery marker must not appear in customer build",
    LEGACY_RECONSTRUCTION_MARKER: "internal reconstruction marker must not appear in customer build",
    LEGACY_HEYVIDEO_MARKER: "legacy upstream digital-human runtime marker",
}

# Strong identity markers are also scanned inside arbitrary binary files. This
# prevents a renamed EXE/ASAR/DLL from carrying an embedded upstream identity.
# Generic forensic words such as "recovered" are intentionally text-only to
# avoid false positives in third-party binary code.
FORBIDDEN_BINARY_MARKERS = {
    LEGACY_PERSON_MARKER: "embedded legacy person/brand marker",
    LEGACY_CN_PRODUCT_MARKER: "embedded legacy Chinese product marker",
    LEGACY_PRODUCT_MARKER: "embedded legacy upstream product marker",
    LEGACY_CLOUD_MARKER: "embedded legacy upstream cloud-domain marker",
    LEGACY_PRODUCT_TYPE_MARKER: "embedded legacy upstream product-type marker",
    LEGACY_WORKBENCH_MARKER: "embedded legacy upstream workbench label",
    LEGACY_HEYVIDEO_MARKER: "embedded legacy upstream digital-human runtime marker",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_text_markers(path: Path, rel: Path) -> list[dict[str, str]]:
    if path.suffix.lower() not in TEXT_SUFFIXES or path.stat().st_size > 4 * 1024 * 1024:
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    found: list[dict[str, str]] = []
    for marker, reason in FORBIDDEN_TEXT_MARKERS.items():
        if marker and marker in text:
            found.append({"path": rel.as_posix(), "reason": reason})
    # The historical repair package marker is a short token that also occurs
    # inside legitimate BossAI identifiers such as X-BossAI-Agent-Token. Match
    # it only as a standalone token/path segment to avoid false positives.
    if re.search(r"(?<![A-Za-z0-9])" + re.escape(LEGACY_REPAIR_MARKER) + r"(?![A-Za-z0-9])", text):
        found.append({"path": rel.as_posix(), "reason": "legacy repair-package marker"})
    return found


def scan_binary_identity_markers(path: Path, rel: Path) -> list[dict[str, str]]:
    patterns: list[tuple[bytes, str]] = []
    for marker, reason in FORBIDDEN_BINARY_MARKERS.items():
        if not marker:
            continue
        for encoding in ("utf-8", "utf-16-le", "utf-16-be"):
            encoded = marker.encode(encoding)
            if encoded:
                patterns.append((encoded, reason))

    if not patterns:
        return []
    max_pattern = max(len(pattern) for pattern, _reason in patterns)
    tail = b""
    found_reasons: set[str] = set()
    try:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                data = tail + chunk
                for pattern, reason in patterns:
                    if reason not in found_reasons and pattern in data:
                        found_reasons.add(reason)
                if len(found_reasons) == len({reason for _pattern, reason in patterns}):
                    break
                tail = data[-max_pattern + 1 :] if max_pattern > 1 else b""
    except OSError:
        return []
    return [{"path": rel.as_posix(), "reason": reason} for reason in sorted(found_reasons)]


def classify(root: Path) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        parts_lower = {part.lower() for part in rel.parts}
        name = path.name
        lower_name = name.lower()

        if name in FORBIDDEN_EXACT_NAMES:
            violations.append({"path": rel.as_posix(), "reason": "forbidden upstream/runtime or credential artifact"})
            continue
        if path.suffix.lower() == ".exe" or lower_name == "app.asar":
            digest = sha256_file(path)
            if digest in FORBIDDEN_UPSTREAM_SHA256:
                violations.append({"path": rel.as_posix(), "reason": FORBIDDEN_UPSTREAM_SHA256[digest]})
                continue
        if parts_lower & FORBIDDEN_PATH_PARTS:
            violations.append({"path": rel.as_posix(), "reason": "forbidden runtime/customer state directory"})
            continue
        if path.suffix.lower() in FORBIDDEN_WEIGHT_SUFFIXES:
            violations.append({"path": rel.as_posix(), "reason": "model weight requires explicit commercial redistribution approval"})
            continue
        if lower_name in {"cookies.json", "session.json", "auth.json", ".env"}:
            violations.append({"path": rel.as_posix(), "reason": "credential/session configuration must not ship"})
            continue

        violations.extend(scan_text_markers(path, rel))
        violations.extend(scan_binary_identity_markers(path, rel))

    # A marker found in a UTF-8 text file is intentionally detected by both the
    # text and binary scanners; keep the customer-facing report concise.
    unique: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in violations:
        key = (item["path"], item["reason"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed commercial distribution boundary check for BossAI Video Agent.")
    parser.add_argument("staging_root", help="Directory that is about to be packaged for customers")
    args = parser.parse_args()

    root = Path(args.staging_root).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"staging root does not exist: {root}")

    violations = classify(root)
    report = {
        "product": "BossAI Video Agent",
        "stagingRoot": str(root),
        "passed": not violations,
        "violationCount": len(violations),
        "violations": violations,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if violations:
        print("RESULT: commercial distribution boundary FAILED.")
        return 2
    print("RESULT: commercial distribution boundary passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
