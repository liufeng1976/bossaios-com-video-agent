"""Verify the BossAI first-party asset bundle.

The product may ship BossAI-owned or redistribution-licensed voices, avatars,
media and music. This makes that impossible to do accidentally: every listed
asset must name a rights holder, a licence and an acquisition record, must exist,
and must match its pinned SHA-256.

An empty bundle passes — shipping nothing is the correct default. What must never
pass is an asset present without provenance.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSET_ROOT = HERE / "first-party-assets"
MANIFEST = ASSET_ROOT / "manifest.json"

SCHEMA = "bossai.video-agent-first-party-assets.v1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ASSET_ID = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")

KIND_DIRECTORIES = {
    "voice": "voices",
    "avatar": "avatars",
    "media": "media",
    "bgm": "bgm",
}
# A licence to *use* an asset is not a licence to redistribute it in a product.
ALLOWED_SOURCE_TYPES = {"bossai-owned", "licensed-for-redistribution"}
REQUIRED_FIELDS = ("id", "kind", "file", "displayName", "sha256", "rightsHolder", "license", "acquisitionRecord", "sourceType")


def main() -> int:
    failures: list[str] = []

    if not MANIFEST.is_file():
        print(json.dumps({"status": "failed", "failures": [f"missing manifest: {MANIFEST}"]}, ensure_ascii=False, indent=2))
        return 2

    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        print(json.dumps({"status": "failed", "failures": [f"manifest is not valid JSON: {exc}"]}, ensure_ascii=False, indent=2))
        return 2

    if manifest.get("schema") != SCHEMA:
        failures.append(f"invalid manifest schema: {manifest.get('schema')!r}")

    assets = manifest.get("assets")
    if not isinstance(assets, list):
        print(json.dumps({"status": "failed", "failures": ["manifest assets must be a list"]}, ensure_ascii=False, indent=2))
        return 2

    # Any listed asset means a human signed off on the bundle.
    if assets and not str(manifest.get("reviewedBy") or "").strip():
        failures.append("first-party assets are listed but reviewedBy is empty")
    if assets and not str(manifest.get("reviewedAt") or "").strip():
        failures.append("first-party assets are listed but reviewedAt is empty")

    seen_ids: set[str] = set()
    verified: list[dict[str, object]] = []

    for index, asset in enumerate(assets):
        label = f"asset[{index}]"
        if not isinstance(asset, dict):
            failures.append(f"{label} is not an object")
            continue

        for field in REQUIRED_FIELDS:
            if not str(asset.get(field) or "").strip():
                failures.append(f"{label} is missing required field: {field}")

        asset_id = str(asset.get("id") or "")
        if asset_id and not ASSET_ID.fullmatch(asset_id):
            failures.append(f"{label} id is not a safe slug: {asset_id!r}")
        if asset_id in seen_ids:
            failures.append(f"{label} duplicates id: {asset_id!r}")
        seen_ids.add(asset_id)

        kind = str(asset.get("kind") or "")
        if kind not in KIND_DIRECTORIES:
            failures.append(f"{label} has an unknown kind: {kind!r}")

        source_type = str(asset.get("sourceType") or "")
        if source_type and source_type not in ALLOWED_SOURCE_TYPES:
            failures.append(f"{label} sourceType is not an approved redistribution basis: {source_type!r}")

        digest = str(asset.get("sha256") or "").lower()
        if digest and not HEX64.fullmatch(digest):
            failures.append(f"{label} sha256 is not a 64-char lowercase digest")

        relative = str(asset.get("file") or "")
        if not relative:
            continue

        path = (ASSET_ROOT / relative).resolve()
        try:
            path.relative_to(ASSET_ROOT.resolve())
        except ValueError:
            failures.append(f"{label} file escapes the asset directory: {relative!r}")
            continue

        expected_dir = KIND_DIRECTORIES.get(kind)
        if expected_dir and not relative.replace("\\", "/").startswith(f"{expected_dir}/"):
            failures.append(f"{label} file must live under {expected_dir}/: {relative!r}")

        if not path.is_file():
            failures.append(f"{label} file is missing: {relative}")
            continue

        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest and actual != digest:
            failures.append(f"{label} SHA-256 mismatch: expected {digest}, got {actual}")

        verified.append({"id": asset_id, "kind": kind, "sizeBytes": path.stat().st_size, "sha256": actual})

    # Anything sitting in the asset directories but absent from the manifest is
    # exactly the accident this check exists to catch.
    declared = {str((asset or {}).get("file") or "").replace("\\", "/") for asset in assets if isinstance(asset, dict)}
    for directory in KIND_DIRECTORIES.values():
        folder = ASSET_ROOT / directory
        if not folder.is_dir():
            continue
        for item in folder.rglob("*"):
            if not item.is_file() or item.name.lower() in {".gitkeep", "readme.md"}:
                continue
            relative = item.relative_to(ASSET_ROOT).as_posix()
            if relative not in declared:
                failures.append(f"undeclared asset present without provenance: {relative}")

    result = {
        "schema": "bossai.video-agent-first-party-asset-evidence.v1",
        "passed": not failures,
        "assetCount": len(assets),
        "verified": verified,
        "bundledMediaShipped": bool(assets),
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures:
        return 2
    if not assets:
        print("RESULT: no first-party assets are bundled; the product ships no media of its own.")
    else:
        print(f"RESULT: {len(assets)} first-party asset(s) verified with complete provenance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
