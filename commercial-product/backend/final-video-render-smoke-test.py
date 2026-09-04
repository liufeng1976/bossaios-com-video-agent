"""Smoke test for BossAI final-video composition.

Renders a synthetic clip through the real local FFmpeg runtime and asserts that
subtitles, a banner title and background music were actually burned in. The test
reports SKIPPED (exit 0) when the machine has no usable FFmpeg, so it can run on
build agents without a media runtime without turning into a false failure.
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
SCRIPT_TEXT = "大家好，我是本店老板。今天介绍一款好用的产品！它省时间，也省钱。"


def _build_inputs(ffmpeg: str, root: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    source = root / "source.mp4"
    bgm = root / "bgm.m4a"
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
        [
            ffmpeg, "-y", "-v", "error",
            "-f", "lavfi", "-i", "sine=frequency=800:duration=2",
            "-c:a", "aac", str(bgm),
        ],
        check=True,
    )
    return source, bgm


def main() -> int:
    temp_root = pathlib.Path(tempfile.mkdtemp(prefix="bossai-render-smoke-"))
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
        source, bgm = _build_inputs(ffmpeg, temp_root)

        # Register the synthetic clip as a completed digital-human job so the
        # render endpoint accepts it through its normal provenance check.
        job_id = uuid.uuid4().hex
        digital_human_root = server._dir("digital-human")
        registered = digital_human_root / f"{job_id}.mp4"
        shutil.copyfile(source, registered)
        server._set_job(
            server._DH_JOBS,
            job_id,
            id=job_id,
            status="done",
            outputPath=str(registered.resolve()),
            fileUrl=f"/api/commercial/digital-human/jobs/{job_id}/file",
        )

        server._ensure_asset_dirs()
        shutil.copyfile(bgm, server._bgm_dir() / "smoke-bgm.m4a")
        listed = [item["fileName"] for item in server.commercial_video_assets()["data"]["bgm"]]
        if "smoke-bgm.m4a" not in listed:
            raise AssertionError(f"customer background music was not listed: {listed!r}")

        started = server.render_final_video(
            server.VideoRenderBody(
                sourceUrl=f"/api/commercial/digital-human/jobs/{job_id}/file",
                projectName="BossAI 渲染冒烟：Smoke?",
                scriptText=SCRIPT_TEXT,
                subtitleEnabled=True,
                subtitlePosition="bottom",
                subtitleFontSize=40,
                bgmEnabled=True,
                bgmFile="smoke-bgm.m4a",
                bgmVolume=15,
                voiceMixVolume=100,
                videoTitleEnabled=True,
                videoTitleText="限时活动",
                videoTitlePosition="top",
                videoTitleFontSize=48,
            )
        )
        render_job_id = str((started.get("data") or {}).get("jobId") or "")
        if not server.JOB_ID_RE.fullmatch(render_job_id):
            raise AssertionError(f"render job identity invalid: {started!r}")

        deadline = time.time() + 300
        job: dict = {}
        while time.time() < deadline:
            job = server.final_video_job(render_job_id)["data"]
            if job.get("status") in {"done", "failed"}:
                break
            time.sleep(0.5)

        if job.get("status") != "done":
            raise AssertionError(f"render did not complete: {job!r}")
        if not job.get("subtitleBurned"):
            raise AssertionError(f"subtitles were not burned in: {job!r}")
        if not job.get("titleBurned"):
            raise AssertionError(f"banner title was not burned in: {job!r}")
        if not job.get("bgmMixed"):
            raise AssertionError(f"background music was not mixed: {job!r}")
        if int(job.get("subtitleSegments") or 0) < 2:
            raise AssertionError(f"script was not segmented into captions: {job!r}")

        download_name = str(job.get("downloadName") or "")
        if not download_name.endswith(".mp4") or ":" in download_name or "?" in download_name:
            raise AssertionError(f"download name was not sanitized: {download_name!r}")

        final_path = server._final_video_path(str(job.get("finalVideoId")))
        if not final_path.is_file() or final_path.stat().st_size == 0:
            raise AssertionError("composed final video is missing")
        if final_path.read_bytes() == registered.read_bytes():
            raise AssertionError("final video is a byte copy; composition did not re-encode")

        rendered_seconds = video_composer.probe_duration(final_path)
        if abs(rendered_seconds - CLIP_SECONDS) > 1.0:
            raise AssertionError(f"composed duration drifted: {rendered_seconds}")

        # The per-job scratch directory must not survive a completed render.
        if (server._dir("render-work") / str(job.get("finalVideoId"))).exists():
            raise AssertionError("render working directory was not cleaned up")

        print("RESULT: BossAI final-video composition smoke passed (subtitles, banner title, BGM mix).")
        print(f"segments={job.get('subtitleSegments')} durationSeconds={rendered_seconds}")
        print(f"sizeBytes={final_path.stat().st_size} downloadName={download_name}")
        return 0
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
