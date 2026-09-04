"""Smoke test for the BossAI publish bundle.

The bundle is the compliant substitute for automated publishing, so the two
things worth pinning down are that it assembles the real artifacts and that it
never quietly becomes a publishing mechanism: no credentials, no upload, and
the automated-publish flag stays false.
"""

from __future__ import annotations

import ast
import inspect
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import textwrap
import uuid

sys.dont_write_bytecode = True


def main() -> int:
    temp_root = pathlib.Path(tempfile.mkdtemp(prefix="bossai-bundle-smoke-"))
    try:
        os.environ["BOSSAI_VIDEO_DATA_ROOT"] = str(temp_root / "data")

        backend = pathlib.Path(__file__).resolve().parent
        if str(backend) not in sys.path:
            sys.path.insert(0, str(backend))

        import server
        import video_composer

        setup = video_composer.inspect_setup()
        if not setup.get("ready"):
            print("SKIPPED: local FFmpeg runtime unavailable: " + ", ".join(setup.get("missing") or []))
            return 0

        ffmpeg = video_composer.ffmpeg_executable()
        source = temp_root / "source.mp4"
        subprocess.run(
            [ffmpeg, "-y", "-v", "error",
             "-f", "lavfi", "-i", "testsrc=size=540x960:rate=25:duration=3",
             "-f", "lavfi", "-i", "sine=frequency=300:duration=3",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source)],
            check=True,
        )

        job_id = uuid.uuid4().hex
        registered = server._dir("digital-human") / f"{job_id}.mp4"
        shutil.copyfile(source, registered)
        server._set_job(server._DH_JOBS, job_id, id=job_id, status="done",
                        outputPath=str(registered.resolve()),
                        fileUrl=f"/api/commercial/digital-human/jobs/{job_id}/file")

        final = server.finalize_video(server.FinalVideoBody(
            sourceUrl=f"/api/commercial/digital-human/jobs/{job_id}/file",
            projectName="门店口播：Smoke?",
        ))["data"]
        cover = server.create_video_cover(server.CoverBody(
            sourceUrl=final["fileUrl"], projectName="门店口播", coverTitle="十年老店", fontSize=60,
        ))["data"]

        bundle = server.create_publish_bundle(server.PublishBundleBody(
            finalVideoUrl=final["fileUrl"],
            coverUrl=cover["fileUrl"],
            projectName="门店口播：Smoke?",
            platform="douyin",
            title="如何挑选靠谱社区餐厅？",
            topics="#家常菜 #社区餐厅",
        ))["data"]

        directory = pathlib.Path(bundle["directory"])
        names = {item.name for item in directory.iterdir()}

        video_name = next((f["name"] for f in bundle["files"] if f["kind"] == "video"), "")
        cover_name = next((f["name"] for f in bundle["files"] if f["kind"] == "cover"), "")
        if not video_name or video_name not in names:
            raise AssertionError(f"bundle is missing the video: {names!r}")
        if not cover_name or cover_name not in names:
            raise AssertionError(f"bundle is missing the cover: {names!r}")
        for required in ("publish.txt", "publish.json"):
            if required not in names:
                raise AssertionError(f"bundle is missing {required}: {names!r}")

        # Names must be filesystem-safe even from a messy project title.
        for name in names:
            if any(ch in name for ch in ':?*<>|"'):
                raise AssertionError(f"bundle file name was not sanitized: {name!r}")

        if (directory / video_name).stat().st_size != server._final_video_path(final["finalVideoId"]).stat().st_size:
            raise AssertionError("bundled video does not match the produced final video")

        copy = (directory / "publish.txt").read_text(encoding="utf-8")
        for fragment in ("如何挑选靠谱社区餐厅？", "#家常菜", "抖音"):
            if fragment not in copy:
                raise AssertionError(f"publish copy is missing {fragment!r}")

        metadata = json.loads((directory / "publish.json").read_text(encoding="utf-8"))
        if metadata.get("automatedPublishAllowed") is not False:
            raise AssertionError(f"bundle must not claim automated publishing: {metadata!r}")
        if not str(metadata.get("uploadPage", "")).startswith("https://"):
            raise AssertionError(f"upload page must be an official https page: {metadata!r}")

        # The bundle must remain a handoff, never a publishing client. Comments
        # and the docstring are stripped first, so prose describing what the
        # function does *not* do cannot trip this check.
        tree = ast.parse(textwrap.dedent(inspect.getsource(server.create_publish_bundle)))
        function = tree.body[0]
        if (
            function.body
            and isinstance(function.body[0], ast.Expr)
            and isinstance(function.body[0].value, ast.Constant)
            and isinstance(function.body[0].value.value, str)
        ):
            function.body = function.body[1:]
        code = ast.unparse(function).lower()
        for forbidden in ("cookie", "password", "login", "session", "token", "urlopen", "requests."):
            if forbidden in code:
                raise AssertionError(f"publish bundle must not handle credentials: found {forbidden!r}")

        # Path traversal on the read-back endpoint.
        for bad in ("../../server", "not-an-id", "0" * 31):
            try:
                server.publish_bundle(bad)
            except Exception as exc:
                if getattr(exc, "status_code", None) not in {400, 403, 404}:
                    raise AssertionError(f"unexpected error for {bad!r}: {exc!r}") from exc
            else:
                raise AssertionError(f"invalid bundle id accepted: {bad!r}")

        # Publishing itself must still be fail-closed.
        status = server.commercial_publish_status()["data"]
        if status.get("automatedPublishAllowed") is not False:
            raise AssertionError(f"automated publishing unexpectedly enabled: {status!r}")

        print("RESULT: BossAI publish bundle smoke passed (video, cover, copy, fail-closed).")
        print(f"files={sorted(names)}")
        print(f"uploadPage={metadata['uploadPage']}")
        return 0
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
