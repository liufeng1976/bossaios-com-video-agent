"""Smoke test for BossAI final-video composition.

Renders a synthetic clip through the real local FFmpeg runtime and asserts that
subtitles, a banner title and background music were actually burned in. The test
reports SKIPPED (exit 0) when the machine has no usable FFmpeg, so it can run on
build agents without a media runtime without turning into a false failure.
"""

from __future__ import annotations

import json
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


def _await_render(server, render_job_id: str) -> dict:
    """Poll a queued render to completion and return its finished job record."""
    if not server.JOB_ID_RE.fullmatch(render_job_id):
        raise AssertionError(f"render job identity invalid: {render_job_id!r}")
    deadline = time.time() + 300
    job: dict = {}
    while time.time() < deadline:
        job = server.final_video_job(render_job_id)["data"]
        if job.get("status") in {"done", "failed"}:
            break
        time.sleep(0.5)
    if job.get("status") != "done":
        raise AssertionError(f"render did not complete: {job!r}")
    return job


def _register_pip_media(ffmpeg: str, server, size: str = "2000x2000") -> str:
    """Place a media-library item the way the upload endpoint would store one."""
    media_id = uuid.uuid4().hex
    server._media_dir().mkdir(parents=True, exist_ok=True)
    target = server._media_dir() / f"{media_id}.png"
    subprocess.run(
        [ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=red:s={size}", "-frames:v", "1", str(target)],
        check=True,
    )
    server._media_meta_path(media_id).write_text(
        json.dumps(
            {"id": media_id, "displayName": "冒烟贴片", "sizeBytes": target.stat().st_size, "suffix": ".png"},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    # Called directly rather than through FastAPI, so the Query defaults must be
    # supplied explicitly.
    listed = {item["id"]: item for item in server.list_media(page=1, pageSize=100)["data"]["items"]}
    if media_id not in listed:
        raise AssertionError(f"customer media was not listed: {sorted(listed)!r}")
    if listed[media_id].get("kind") != "image":
        raise AssertionError(f"media kind was misreported: {listed[media_id]!r}")
    return media_id


def _assert_pip_renders_through_the_endpoint(
    server,
    ffmpeg: str,
    source_url: str,
    frame_width: int,
) -> dict:
    """The render endpoint must burn the inset in and size it against the frame.

    The asset is deliberately 2000px wide against a much narrower video, so a
    regression that sizes the inset from the asset shows up as a wildly wrong
    ``pipWidthPx`` rather than as a silently ugly video.
    """
    media_id = _register_pip_media(ffmpeg, server)
    started = server.render_final_video(
        server.VideoRenderBody(
            sourceUrl=source_url,
            projectName="BossAI 贴片冒烟",
            scriptText=SCRIPT_TEXT,
            subtitleEnabled=False,
            pipEnabled=True,
            pipMediaId=media_id,
            pipCorner="bottom-right",
            pipScalePercent=25,
            pipMarginPercent=5,
            pipOpacity=80,
        )
    )
    job = _await_render(server, str((started.get("data") or {}).get("jobId") or ""))
    if not job.get("pipOverlaid"):
        raise AssertionError(f"picture-in-picture was not overlaid by the render endpoint: {job!r}")
    expected = round(frame_width * 0.25)
    if abs(int(job.get("pipWidthPx") or 0) - expected) > 2:
        raise AssertionError(
            f"endpoint inset width {job.get('pipWidthPx')!r} is not 25% of the {frame_width}px frame"
        )
    final_path = server._final_video_path(str(job.get("finalVideoId")))
    if not final_path.is_file() or final_path.stat().st_size == 0:
        raise AssertionError("composed picture-in-picture video is missing")
    return job


def _assert_cover_renders(server, source_url: str) -> dict:
    """The cover must be a real frame of the customer's own finished video."""
    data = server.create_video_cover(
        server.CoverBody(
            sourceUrl=source_url,
            projectName="BossAI 封面冒烟：Smoke?",
            timestampSeconds=1.5,
            coverTitle="限时活动",
        )
    )["data"]

    if not data.get("titleBurned"):
        raise AssertionError(f"cover title was not burned in: {data!r}")
    if abs(float(data.get("timestampSeconds") or 0) - 1.5) > 0.05:
        raise AssertionError(f"cover frame timestamp drifted: {data!r}")

    cover_path = server._cover_path(str(data.get("coverId")))
    if not cover_path.is_file() or cover_path.stat().st_size == 0:
        raise AssertionError("cover image was not produced")
    if cover_path.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError("cover image is not a PNG")

    download_name = str(data.get("downloadName") or "")
    if not download_name.endswith("-cover.png") or ":" in download_name or "?" in download_name:
        raise AssertionError(f"cover download name was not sanitized: {download_name!r}")
    if (server._dir("render-work") / f"cover-{data.get('coverId')}").exists():
        raise AssertionError("cover working directory was not cleaned up")
    return data


def _assert_pip_scales_to_the_frame(
    ffmpeg: str,
    video_composer,
    source: pathlib.Path,
    root: pathlib.Path,
) -> int:
    """The inset must be sized against the output frame, not the source asset.

    The same ``scale_percent`` is rendered twice from wildly different assets: a
    2000px logo and a 100px icon. Both must land on the same on-screen width, or
    the inset silently swallows the frame for high-resolution customer artwork.
    """
    assets = []
    for name, size in (("pip-large.png", "2000x2000"), ("pip-small.png", "100x100")):
        asset = root / name
        subprocess.run(
            [ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=red:s={size}", "-frames:v", "1", str(asset)],
            check=True,
        )
        assets.append(asset)

    frame_width = video_composer.probe_video_size(source)[0]
    if frame_width <= 0:
        raise AssertionError("source frame width could not be probed")

    widths = []
    for index, asset in enumerate(assets):
        summary = video_composer.compose(
            source_video=source,
            output_path=root / f"pip-{index}.mp4",
            work_dir=root / f"pip-work-{index}",
            script_text="",
            pip=video_composer.PictureInPicture(media_path=asset, scale_percent=25),
        )
        if not summary.get("pipOverlaid"):
            raise AssertionError(f"picture-in-picture was not overlaid: {summary!r}")
        widths.append(int(summary.get("pipWidthPx") or 0))

    if widths[0] <= 0 or widths[1] <= 0:
        raise AssertionError(f"composer did not report an inset width: {widths!r}")
    if widths[0] != widths[1]:
        raise AssertionError(
            f"inset size followed the source asset instead of the frame: {widths[0]}px vs {widths[1]}px"
        )
    expected = round(frame_width * 0.25)
    if abs(widths[0] - expected) > 2:
        raise AssertionError(f"inset width {widths[0]}px is not 25% of the {frame_width}px frame")
    return widths[0]


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
        job = _await_render(server, str((started.get("data") or {}).get("jobId") or ""))
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

        frame_width = video_composer.probe_video_size(source)[0]
        pip_widths = _assert_pip_scales_to_the_frame(ffmpeg, video_composer, source, temp_root)
        pip_job = _assert_pip_renders_through_the_endpoint(
            server,
            ffmpeg,
            f"/api/commercial/digital-human/jobs/{job_id}/file",
            frame_width,
        )
        cover = _assert_cover_renders(server, str(job.get("fileUrl") or ""))

        print(
            "RESULT: BossAI final-video composition smoke passed "
            "(subtitles, banner title, BGM mix, picture-in-picture, cover)."
        )
        print(f"segments={job.get('subtitleSegments')} durationSeconds={rendered_seconds}")
        print(f"sizeBytes={final_path.stat().st_size} downloadName={download_name}")
        print(f"pipWidthPx={pip_widths} composer / {pip_job.get('pipWidthPx')} endpoint on a {frame_width}px frame")
        print(f"coverId={cover.get('coverId')} coverBytes={cover.get('sizeBytes')} at t={cover.get('timestampSeconds')}s")
        return 0
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
