from __future__ import annotations

import os
import pathlib
import shutil
import sys
import tempfile
import uuid

sys.dont_write_bytecode = True


def main() -> int:
    temp_root = pathlib.Path(tempfile.mkdtemp(prefix="bossai-final-video-smoke-"))
    try:
        data_root = temp_root / "data"
        os.environ["BOSSAI_VIDEO_DATA_ROOT"] = str(data_root)

        backend = pathlib.Path(__file__).resolve().parent
        if str(backend) not in sys.path:
            sys.path.insert(0, str(backend))

        import server

        job_id = uuid.uuid4().hex
        digital_human_root = data_root / "digital-human"
        digital_human_root.mkdir(parents=True, exist_ok=True)
        source = digital_human_root / f"{job_id}.mp4"
        source.write_bytes(b"bossai-commercial-video-smoke" * 256)
        server._set_job(
            server._DH_JOBS,
            job_id,
            id=job_id,
            status="done",
            outputPath=str(source.resolve()),
            fileUrl=f"/api/commercial/digital-human/jobs/{job_id}/file",
        )

        finalized = server.finalize_video(
            server.FinalVideoBody(
                sourceUrl=f"/api/commercial/digital-human/jobs/{job_id}/file",
                projectName="BossAI 商业成片：Smoke?",
            )
        )
        final_data = finalized.get("data") or {}
        final_video_id = str(final_data.get("finalVideoId") or "")
        final_url = str(final_data.get("fileUrl") or "")
        download_name = str(final_data.get("downloadName") or "")
        if finalized.get("success") is not True or not server.FINAL_VIDEO_ID_RE.fullmatch(final_video_id):
            raise AssertionError(f"final video identity invalid: {finalized!r}")
        if final_url != f"/api/commercial/video/final/{final_video_id}/file":
            raise AssertionError(f"final video URL invalid: {finalized!r}")
        if not download_name.endswith(".mp4") or ":" in download_name or "?" in download_name:
            raise AssertionError(f"download name was not sanitized: {download_name!r}")

        final_path = server._final_video_path(final_video_id)
        if final_path.read_bytes() != source.read_bytes():
            raise AssertionError("final video artifact does not preserve the generated commercial output")

        publish_status = server.commercial_publish_status()
        publish_data = publish_status.get("data") or {}
        if publish_data.get("automatedPublishAllowed") is not False:
            raise AssertionError(f"automated publish unexpectedly enabled: {publish_status!r}")
        if publish_data.get("manualExportAllowed") is not True or publish_data.get("approvalRequired") is not True:
            raise AssertionError(f"publish gate policy incomplete: {publish_status!r}")

        prepared = server.prepare_commercial_publish(
            server.PublishPrepareBody(finalVideoUrl=final_url, platform="douyin")
        )
        prepared_data = prepared.get("data") or {}
        if prepared_data.get("status") != "blocked" or prepared_data.get("automatedPublishAllowed") is not False:
            raise AssertionError(f"publish preparation did not fail closed: {prepared!r}")

        print(
            "RESULT: BossAI commercial final-video/export contract passed; "
            "external publishing remains fail-closed."
        )
        print(f"finalVideoId={final_video_id}")
        print(f"downloadName={download_name}")
        print(f"sizeBytes={final_path.stat().st_size}")
        return 0
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
