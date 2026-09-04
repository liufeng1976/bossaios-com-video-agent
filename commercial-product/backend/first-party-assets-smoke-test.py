"""Smoke test for the BossAI first-party asset bundle.

The mechanism exists so BossAI can ship its own voices, avatars, media and music
without ever shipping media whose redistribution rights are unestablished. That
guarantee is only worth something if the checks actually bite, so this drives the
verifier through each way an asset could slip in.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

BACKEND = pathlib.Path(__file__).resolve().parent
PRODUCT = BACKEND.parent
VERIFIER = PRODUCT / "verify-first-party-assets.py"
ASSET_ROOT = PRODUCT / "first-party-assets"
MANIFEST = ASSET_ROOT / "manifest.json"


def run_verifier() -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(VERIFIER)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def main() -> int:
    original = MANIFEST.read_text(encoding="utf-8")
    strays: list[pathlib.Path] = []
    try:
        # The shipped default must be an empty, passing bundle.
        code, out = run_verifier()
        if code != 0:
            raise AssertionError(f"default bundle should pass: {out}")
        shipped = json.loads(original)
        if shipped.get("assets"):
            raise AssertionError("the repository must not ship first-party media by default")

        base = json.loads(original)

        def write(assets, reviewed=True):
            data = dict(base)
            data["assets"] = assets
            data["reviewedBy"] = "legal" if reviewed else ""
            data["reviewedAt"] = "2026-09-05" if reviewed else ""
            MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        payload = b"bossai-owned-track" * 64
        track = ASSET_ROOT / "bgm" / "smoke-track.mp3"
        strays.append(track)
        track.write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()

        def entry(**overrides):
            item = {
                "id": "bossai-smoke-track",
                "kind": "bgm",
                "file": "bgm/smoke-track.mp3",
                "displayName": "BossAI Smoke Track",
                "sha256": digest,
                "rightsHolder": "BossAI",
                "license": "BossAI-owned; full commercial redistribution rights",
                "acquisitionRecord": "SMOKE-TEST-ONLY",
                "sourceType": "bossai-owned",
            }
            item.update(overrides)
            return item

        # A complete entry is accepted.
        write([entry()])
        code, out = run_verifier()
        if code != 0:
            raise AssertionError(f"a fully documented asset should pass: {out}")

        # Each way provenance can be incomplete must fail.
        cases = {
            "missing rights holder": entry(rightsHolder=""),
            "missing licence": entry(license=""),
            "missing acquisition record": entry(acquisitionRecord=""),
            "hash mismatch": entry(sha256="0" * 64),
            "use-only licence": entry(sourceType="purchased-usage-rights"),
            "path escape": entry(file="../../../LICENSE"),
            "wrong folder for kind": entry(file="voices/smoke-track.mp3"),
        }
        for label, bad in cases.items():
            write([bad])
            code, out = run_verifier()
            if code == 0:
                raise AssertionError(f"verifier accepted an asset with {label}: {out}")

        # A signed-off bundle is required once anything is listed.
        write([entry()], reviewed=False)
        code, out = run_verifier()
        if code == 0:
            raise AssertionError("verifier accepted bundled media with no reviewer recorded")

        # A file dropped in without any manifest entry must be caught.
        write([])
        code, out = run_verifier()
        if code == 0:
            raise AssertionError("verifier missed an undeclared asset file")
        if "undeclared asset" not in out:
            raise AssertionError(f"undeclared asset was not named in the failure: {out}")

        track.unlink()
        strays.remove(track)

        # The backend must ignore an asset whose provenance is incomplete.
        MANIFEST.write_text(original, encoding="utf-8")
        temp_root = pathlib.Path(tempfile.mkdtemp(prefix="bossai-fp-smoke-"))
        try:
            os.environ["BOSSAI_VIDEO_DATA_ROOT"] = str(temp_root / "data")
            if str(BACKEND) not in sys.path:
                sys.path.insert(0, str(BACKEND))
            import server

            listing = server.commercial_first_party_assets()["data"]
            for kind in ("voices", "avatars", "media", "bgm"):
                if listing[kind]:
                    raise AssertionError(f"default build must bundle no {kind}: {listing[kind]!r}")

            half = ASSET_ROOT / "bgm" / "half.mp3"
            strays.append(half)
            half.write_bytes(payload)
            write([entry(id="half-documented", file="bgm/half.mp3", rightsHolder="")])
            if server._first_party_assets("bgm"):
                raise AssertionError("backend surfaced an asset with incomplete provenance")
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

        print("RESULT: BossAI first-party asset bundle passed (empty by default, provenance enforced).")
        print(f"blocked cases: {len(cases) + 2}")
        return 0
    finally:
        MANIFEST.write_text(original, encoding="utf-8")
        for stray in strays:
            if stray.exists():
                stray.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
