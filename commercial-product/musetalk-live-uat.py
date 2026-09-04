from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import musetalk_adapter

PRODUCT_ID = "bossai-video-agent"
PRODUCT_VERSION = "0.1.0"
SCHEMA = "bossai.video-agent-musetalk-commercial-uat.v1"
ALLOWED_BASES = {"customer-authorized", "bossai-owned"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def persisted_runtime_root() -> Path | None:
    explicit = str(os.environ.get("BOSSAI_VIDEO_RUNTIME_ROOT") or "").strip().strip('"')
    if explicit:
        return Path(explicit).expanduser().resolve()
    local = str(os.environ.get("LOCALAPPDATA") or "").strip()
    if not local:
        return None
    config_path = Path(local) / "BossAI" / "VideoAgent" / "runtime-storage.json"
    if not config_path.is_file():
        return None
    try:
        value = str(read_json(config_path).get("runtimeRoot") or "").strip()
    except Exception:
        return None
    return Path(value).expanduser().resolve() if value else None


def configure_musetalk_env() -> tuple[Path | None, dict]:
    runtime_root = persisted_runtime_root()
    if runtime_root is None:
        return None, {}
    component_root = runtime_root / "musetalk"
    manifest_path = component_root / "runtime.json"
    if not manifest_path.is_file():
        return component_root, {}
    manifest = read_json(manifest_path)
    env = manifest.get("env") or {}
    for key in ("BOSSAI_MUSETALK_ROOT", "BOSSAI_MUSETALK_PYTHON", "BOSSAI_FFMPEG_BIN", "TORCH_HOME"):
        value = str(env.get(key) or "").strip()
        if value:
            os.environ[key] = value
    return component_root, manifest


def ffprobe_output(output: Path) -> dict:
    ffmpeg = str(os.environ.get("BOSSAI_FFMPEG_BIN") or "").strip().strip('"')
    ffmpeg_path = Path(ffmpeg).expanduser().resolve() if ffmpeg else None
    ffprobe = (ffmpeg_path.parent / "ffprobe.exe") if ffmpeg_path and ffmpeg_path.is_file() else None
    if ffprobe is None or not ffprobe.is_file():
        return {"available": False, "valid": False, "durationSeconds": None, "videoStreamCount": 0}
    process = subprocess.run(
        [
            str(ffprobe),
            "-v", "error",
            "-show_entries", "format=duration:stream=codec_type",
            "-of", "json",
            str(output),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if process.returncode != 0:
        return {"available": True, "valid": False, "durationSeconds": None, "videoStreamCount": 0}
    try:
        payload = json.loads(process.stdout or "{}")
        duration = float(((payload.get("format") or {}).get("duration") or 0.0))
        streams = payload.get("streams") or []
        video_count = sum(1 for item in streams if str(item.get("codec_type") or "") == "video")
    except Exception:
        return {"available": True, "valid": False, "durationSeconds": None, "videoStreamCount": 0}
    return {
        "available": True,
        "valid": duration > 0 and video_count > 0,
        "durationSeconds": round(duration, 3),
        "videoStreamCount": video_count,
    }


def write_report(report: dict, out: str) -> None:
    if not out:
        return
    path = Path(out).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fail-closed end-to-end MuseTalk commercial render UAT using only customer-authorized or BossAI-owned media. "
            "Input paths are never persisted in the evidence report."
        )
    )
    parser.add_argument("--video", required=True, help="Authorized avatar/video file")
    parser.add_argument("--audio", required=True, help="Authorized/generated audio file")
    parser.add_argument("--authorization-basis", required=True, choices=sorted(ALLOWED_BASES))
    parser.add_argument(
        "--rights-affirmed",
        action="store_true",
        help="Required explicit assertion that BossAI/customer has sufficient rights for this UAT media.",
    )
    parser.add_argument("--product-version", default=PRODUCT_VERSION)
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--out", default="")
    parser.add_argument("--timeout-seconds", type=float, default=1800.0)
    args = parser.parse_args()

    video = Path(args.video).expanduser().resolve()
    audio = Path(args.audio).expanduser().resolve()
    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "BossAI" / "VideoAgent" / "uat" / "musetalk"
    )

    report = {
        "schema": SCHEMA,
        "productId": PRODUCT_ID,
        "productVersion": args.product_version,
        "generatedAt": now_iso(),
        "passed": False,
        "ready": False,
        "renderAttempted": False,
        "authorizedMediaUsed": False,
        "authorizationBasis": args.authorization_basis,
        "privacy": {
            "inputPathsPersisted": False,
            "customerContentPersistedInEvidence": False,
            "accessTokensPersisted": False,
            "providerKeysPersisted": False,
        },
        "runtime": {},
        "inputs": {},
        "output": {},
        "reasonCode": "",
        "reason": "",
    }

    if not args.rights_affirmed:
        report["reasonCode"] = "MEDIA_RIGHTS_NOT_AFFIRMED"
        report["reason"] = "Explicit --rights-affirmed is required before any commercial MuseTalk UAT render is attempted."
        write_report(report, args.out)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print("RESULT: MuseTalk commercial render UAT FAILED CLOSED (media rights not affirmed).")
        return 2
    report["authorizedMediaUsed"] = True

    if not video.is_file() or not audio.is_file():
        report["reasonCode"] = "AUTHORIZED_MEDIA_MISSING"
        report["reason"] = "Authorized video and audio files must both exist before render UAT."
        write_report(report, args.out)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print("RESULT: MuseTalk commercial render UAT FAILED CLOSED (authorized media missing).")
        return 2

    component_root, runtime_manifest = configure_musetalk_env()
    setup = musetalk_adapter.inspect_setup()
    runtime_source = runtime_manifest.get("source") or {}
    runtime_manifest_path = (component_root / "runtime.json") if component_root else None
    report["runtime"] = {
        "componentRootPresent": bool(component_root and component_root.is_dir()),
        "manifestPresent": bool(runtime_manifest),
        "manifestSha256": sha256(runtime_manifest_path) if runtime_manifest_path and runtime_manifest_path.is_file() else "",
        "sourceRevision": str(runtime_source.get("revision") or ""),
        "modelRevision": str(runtime_source.get("modelRevision") or ""),
        "setupReady": bool(setup.get("ready")),
        "engine": str(setup.get("engine") or ""),
        "version": str(setup.get("version") or ""),
        "usesOfficialTestData": bool(setup.get("usesOfficialTestData")),
    }
    report["ready"] = bool(setup.get("ready")) and not bool(setup.get("usesOfficialTestData"))
    if not report["ready"]:
        report["reasonCode"] = "MUSETALK_RUNTIME_NOT_READY"
        report["reason"] = "Installed MuseTalk runtime is not ready or would rely on official test data."
        write_report(report, args.out)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print("RESULT: MuseTalk commercial render UAT FAILED CLOSED (runtime not ready).")
        return 2

    report["inputs"] = {
        "video": {"bytes": video.stat().st_size, "sha256": sha256(video)},
        "audio": {"bytes": audio.stat().st_size, "sha256": sha256(audio)},
    }

    try:
        report["renderAttempted"] = True
        result = musetalk_adapter.render(
            video_path=video,
            audio_path=audio,
            output_dir=output_dir,
            output_filename="bossai-musetalk-commercial-uat.mp4",
            timeout_seconds=args.timeout_seconds,
        )
        output = Path(str(result.get("outputPath") or "")).expanduser().resolve()
        if not output.is_file() or output.stat().st_size < 1024:
            raise RuntimeError("MuseTalk render did not produce a non-empty MP4 output.")
        probe = ffprobe_output(output)
        report["output"] = {
            "bytes": output.stat().st_size,
            "sha256": sha256(output),
            "ffprobe": probe,
            "elapsedSeconds": result.get("elapsedSeconds"),
            "returnCode": result.get("returnCode"),
        }
        report["passed"] = bool(probe.get("valid"))
        if report["passed"]:
            report["reasonCode"] = "PASS"
            report["reason"] = "Authorized-media MuseTalk end-to-end render produced a valid MP4 video."
        else:
            report["reasonCode"] = "OUTPUT_MEDIA_VALIDATION_FAILED"
            report["reason"] = "MuseTalk produced an output file but ffprobe did not validate a non-empty video stream."
    except Exception:
        report["reasonCode"] = "MUSETALK_RENDER_FAILED"
        report["reason"] = (
            "MuseTalk render failed. Detailed subprocess diagnostics are intentionally excluded from the machine evidence "
            "so authorized customer-media paths/content are not persisted."
        )

    write_report(report, args.out)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["passed"]:
        print("RESULT: MuseTalk commercial render UAT PASSED.")
        return 0
    print("RESULT: MuseTalk commercial render UAT FAILED CLOSED.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
