"""Smoke test for BossAI cover generation and picture-in-picture overlay.

Runs the real local FFmpeg over synthetic media and asserts the composer
actually overlaid the inset and produced a cover image. Reports SKIPPED
(exit 0) when the machine has no usable FFmpeg.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

sys.dont_write_bytecode = True

CLIP_SECONDS = 4
SCRIPT_TEXT = "大家好，我是本店老板。今天介绍一款好用的产品。"


def _build_inputs(ffmpeg: str, root: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    source = root / "source.mp4"
    logo = root / "logo.png"
    subprocess.run(
        [
            ffmpeg, "-y", "-v", "error",
            "-f", "lavfi", "-i", f"testsrc=size=540x960:rate=25:duration={CLIP_SECONDS}",
            "-f", "lavfi", "-i", f"sine=frequency=300:duration={CLIP_SECONDS}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source),
        ],
        check=True,
    )
    subprocess.run(
        [ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=orange:size=240x240:duration=1",
         "-frames:v", "1", str(logo)],
        check=True,
    )
    return source, logo


def main() -> int:
    temp_root = pathlib.Path(tempfile.mkdtemp(prefix="bossai-cover-pip-smoke-"))
    try:
        os.environ["BOSSAI_VIDEO_DATA_ROOT"] = str(temp_root / "data")

        backend = pathlib.Path(__file__).resolve().parent
        if str(backend) not in sys.path:
            sys.path.insert(0, str(backend))

        import server
        import video_composer

        setup = video_composer.inspect_setup()
        if not setup.get("ready"):
            print("SKIPPED: local FFmpeg composition runtime unavailable: " + ", ".join(setup.get("missing") or []))
            return 0

        ffmpeg = video_composer.ffmpeg_executable()
        source, logo = _build_inputs(ffmpeg, temp_root)

        # --- media library -------------------------------------------------
        media_id = uuid.uuid4().hex
        server._media_dir().mkdir(parents=True, exist_ok=True)
        shutil.copyfile(logo, server._media_dir() / f"{media_id}.png")
        listed = server.list_media(page=1, pageSize=100)["data"]["items"]
        entry = next((item for item in listed if item["id"] == media_id), None)
        if entry is None or entry["kind"] != "image":
            raise AssertionError(f"media item was not listed as an image: {listed!r}")

        server.rename_media(media_id, server.RenameBody(displayName="门店招牌"))
        listed = server.list_media(page=1, pageSize=100)["data"]["items"]
        if not any(item["displayName"] == "门店招牌" for item in listed):
            raise AssertionError("media rename did not persist")

        # --- render with picture-in-picture --------------------------------
        job_id = uuid.uuid4().hex
        registered = server._dir("digital-human") / f"{job_id}.mp4"
        shutil.copyfile(source, registered)
        server._set_job(
            server._DH_JOBS, job_id, id=job_id, status="done",
            outputPath=str(registered.resolve()),
            fileUrl=f"/api/commercial/digital-human/jobs/{job_id}/file",
        )

        started = server.render_final_video(
            server.VideoRenderBody(
                sourceUrl=f"/api/commercial/digital-human/jobs/{job_id}/file",
                projectName="BossAI 画中画冒烟",
                scriptText=SCRIPT_TEXT,
                subtitleEnabled=True,
                subtitleFontSize=36,
                pipEnabled=True,
                pipMediaId=media_id,
                pipCorner="top-right",
                pipScalePercent=30,
                pipOpacity=90,
            )
        )
        render_job_id = str((started.get("data") or {}).get("jobId") or "")
        deadline = time.time() + 300
        job: dict = {}
        while time.time() < deadline:
            job = server.final_video_job(render_job_id)["data"]
            if job.get("status") in {"done", "failed"}:
                break
            time.sleep(0.5)

        if job.get("status") != "done":
            raise AssertionError(f"picture-in-picture render did not complete: {job!r}")
        if not job.get("pipOverlaid"):
            raise AssertionError(f"picture-in-picture was not overlaid: {job!r}")
        if not job.get("subtitleBurned"):
            raise AssertionError(f"subtitles were dropped when PiP was enabled: {job!r}")

        final_url = str(job.get("fileUrl") or "")
        final_path = server._final_video_path(str(job.get("finalVideoId")))
        rendered_seconds = video_composer.probe_duration(final_path)
        if abs(rendered_seconds - CLIP_SECONDS) > 1.0:
            raise AssertionError(f"PiP render duration drifted: {rendered_seconds}")

        # --- cover ----------------------------------------------------------
        cover = server.create_video_cover(
            server.CoverBody(
                sourceUrl=final_url,
                projectName="BossAI 封面冒烟：Smoke?",
                timestampSeconds=1.5,
                coverTitle="十年老店 只做现炒",
                fontSize=64,
            )
        )["data"]
        if not server.COVER_ID_RE.fullmatch(str(cover.get("coverId") or "")):
            raise AssertionError(f"cover identity invalid: {cover!r}")
        if not cover.get("titleBurned"):
            raise AssertionError(f"cover title was not burned in: {cover!r}")
        download_name = str(cover.get("downloadName") or "")
        if not download_name.endswith("-cover.png") or ":" in download_name or "?" in download_name:
            raise AssertionError(f"cover download name was not sanitized: {download_name!r}")

        cover_path = server._cover_path(str(cover["coverId"]))
        if cover_path.stat().st_size < 1024:
            raise AssertionError("cover image is suspiciously small")

        # A cover must come from the customer's own video, never an arbitrary path.
        try:
            server.create_video_cover(
                server.CoverBody(sourceUrl="/api/commercial/digital-human/jobs/" + job_id + "/file")
            )
        except Exception as exc:
            if getattr(exc, "status_code", None) not in {400, 404}:
                raise AssertionError(f"unexpected error for non-final source: {exc!r}") from exc
        else:
            raise AssertionError("cover accepted a source outside the final-video boundary")

        server.delete_media(media_id)
        if any(item["id"] == media_id for item in server.list_media(page=1, pageSize=100)["data"]["items"]):
            raise AssertionError("media item was not deleted")

        print("RESULT: BossAI cover + picture-in-picture smoke passed.")
        print(f"pipOverlaid={job.get('pipOverlaid')} subtitleSegments={job.get('subtitleSegments')}")
        print(f"coverBytes={cover_path.stat().st_size} downloadName={download_name}")
        return 0
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
