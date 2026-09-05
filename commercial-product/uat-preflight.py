"""Report whether the GA UAT tracks can even be attempted yet.

This is a readiness check, not evidence. It renders nothing, authenticates
nothing, writes no evidence file and sets no gate flag. Its only job is to let
an operator find out what is blocking a UAT *before* they go and collect
rights-cleared media or arrange a real Business account.

Exit 0 when every checked track is ready to attempt; exit 1 otherwise.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _load_uat_module():
    """Reuse the UAT's own runtime-resolution logic instead of copying it.

    The filename contains hyphens, so it cannot be imported by name.
    """
    spec = importlib.util.spec_from_file_location("_musetalk_live_uat", HERE / "musetalk-live-uat.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load musetalk-live-uat.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_musetalk() -> dict:
    track: dict = {"track": "musetalk-authorized-media-render", "ready": False, "blockers": [], "details": {}}

    try:
        uat = _load_uat_module()
    except Exception as exc:
        track["blockers"].append(f"MuseTalk UAT runner is not importable: {type(exc).__name__}")
        return track

    runtime_root = uat.persisted_runtime_root()
    track["details"]["runtimeRootResolved"] = bool(runtime_root)
    if runtime_root is None:
        track["blockers"].append(
            "Runtime root is not resolvable. Set BOSSAI_VIDEO_RUNTIME_ROOT, or install a runtime from "
            "Settings so runtime-storage.json records the location."
        )
        return track

    component_root, manifest = uat.configure_musetalk_env()
    track["details"]["componentRootPresent"] = bool(component_root and component_root.is_dir())
    track["details"]["manifestPresent"] = bool(manifest)
    if not manifest:
        track["blockers"].append("MuseTalk is not installed under the resolved runtime root (no runtime.json).")
        return track

    source = manifest.get("source") or {}
    track["details"]["sourceRevision"] = str(source.get("revision") or "")
    track["details"]["modelRevision"] = str(source.get("modelRevision") or "")

    try:
        import musetalk_adapter

        setup = musetalk_adapter.inspect_setup()
    except Exception as exc:
        track["blockers"].append(f"MuseTalk adapter could not inspect the installation: {type(exc).__name__}")
        return track

    track["details"]["setupReady"] = bool(setup.get("ready"))
    track["details"]["usesOfficialTestData"] = bool(setup.get("usesOfficialTestData"))
    if not setup.get("ready"):
        track["blockers"].append("MuseTalk runtime reports setupReady=false; re-run the installer and its verifier.")
    if setup.get("usesOfficialTestData"):
        track["blockers"].append(
            "MuseTalk installation would fall back to upstream demo assets. The UAT refuses those by design; "
            "the installation must be repaired before a commercial render is meaningful."
        )

    # Without ffprobe the render can succeed and the UAT still cannot return PASS,
    # because the verdict depends on probing the output stream.
    ffmpeg = str(os.environ.get("BOSSAI_FFMPEG_BIN") or "").strip().strip('"')
    ffprobe = (Path(ffmpeg).expanduser().resolve().parent / "ffprobe.exe") if ffmpeg else None
    has_ffprobe = bool(ffprobe and ffprobe.is_file())
    track["details"]["ffprobeAvailable"] = has_ffprobe
    if not has_ffprobe:
        track["blockers"].append(
            "ffprobe was not found next to BOSSAI_FFMPEG_BIN. The render would run but the UAT could never "
            "validate the output, so it would fail closed."
        )

    track["ready"] = not track["blockers"]
    return track


def check_entitlement() -> dict:
    track: dict = {"track": "live-business-entitlement", "ready": False, "blockers": [], "details": {}}
    try:
        import bossai_os_bridge
    except Exception as exc:
        track["blockers"].append(f"BossAI OS bridge is not importable: {type(exc).__name__}")
        return track

    configured = bool(bossai_os_bridge.configured())
    track["details"]["serviceConfigured"] = configured
    if not configured:
        track["blockers"].append("BossAI account service is not configured for this machine.")

    try:
        session = bossai_os_bridge.account_session()
        track["details"]["reachable"] = True
        authenticated = bool(session.get("authenticated"))
        track["details"]["authenticated"] = authenticated
        if not authenticated:
            track["blockers"].append(
                "No authenticated customer session. A real customer account with an active Business "
                "entitlement must be signed in on this machine."
            )
    except Exception as exc:
        track["details"]["reachable"] = False
        track["blockers"].append(f"BossAI account service is not reachable: {type(exc).__name__}")

    track["ready"] = not track["blockers"]
    return track


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--track",
        choices=("all", "musetalk", "entitlement"),
        default="all",
        help="Which UAT track to check readiness for.",
    )
    args = parser.parse_args()

    tracks = []
    if args.track in ("all", "musetalk"):
        tracks.append(check_musetalk())
    if args.track in ("all", "entitlement"):
        tracks.append(check_entitlement())

    report = {
        "schema": "bossai.video-agent-uat-preflight.v1",
        "isEvidence": False,
        "tracks": tracks,
        "allReady": all(item["ready"] for item in tracks),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print()
    for item in tracks:
        if item["ready"]:
            print(f"READY   {item['track']}")
        else:
            print(f"BLOCKED {item['track']}")
            for blocker in item["blockers"]:
                print(f"        - {blocker}")
    print()
    print("This preflight is not UAT evidence and does not change any release gate.")
    return 0 if report["allReady"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
