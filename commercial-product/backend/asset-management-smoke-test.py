"""Smoke test for BossAI local asset management.

Covers the voice and avatar library contract: list, audition/preview, rename and
delete, plus the invariant that unknown-rights default voices are never created
by the product itself.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import sys
import tempfile
import uuid

sys.dont_write_bytecode = True


def _write_voice(server, display_name: str) -> str:
    voice_id = uuid.uuid4().hex
    server._voice_wav_path(voice_id).write_bytes(b"RIFFbossai-voice-smoke" * 128)
    server._voice_meta_path(voice_id).write_text(
        json.dumps({"id": voice_id, "displayName": display_name}, ensure_ascii=False), encoding="utf-8"
    )
    return voice_id


def _write_avatar(server, display_name: str) -> str:
    avatar_id = uuid.uuid4().hex
    (server._dir("avatars") / f"{avatar_id}.mp4").write_bytes(b"bossai-avatar-smoke" * 256)
    server._avatar_meta_path(avatar_id).write_text(
        json.dumps({"id": avatar_id, "displayName": display_name}, ensure_ascii=False), encoding="utf-8"
    )
    return avatar_id


def main() -> int:
    temp_root = pathlib.Path(tempfile.mkdtemp(prefix="bossai-assets-smoke-"))
    try:
        os.environ["BOSSAI_VIDEO_DATA_ROOT"] = str(temp_root / "data")

        backend = pathlib.Path(__file__).resolve().parent
        if str(backend) not in sys.path:
            sys.path.insert(0, str(backend))

        import server

        # --- voices -------------------------------------------------------
        voice_id = _write_voice(server, "授权音色 A")
        listed = server.list_voices(page=1, pageSize=100)["data"]["items"]
        if not any(item["id"] == voice_id and item["displayName"] == "授权音色 A" for item in listed):
            raise AssertionError(f"voice was not listed: {listed!r}")

        renamed = server.rename_voice(voice_id, server.RenameBody(displayName="品牌主理人音色"))
        if renamed["data"]["displayName"] != "品牌主理人音色":
            raise AssertionError(f"voice rename failed: {renamed!r}")
        listed = server.list_voices(page=1, pageSize=100)["data"]["items"]
        if not any(item["displayName"] == "品牌主理人音色" for item in listed):
            raise AssertionError("voice rename did not persist")

        audition = server.voice_file(voice_id)
        if not pathlib.Path(audition.path).is_file():
            raise AssertionError("voice audition file is not served")

        server.delete_voice(voice_id)
        if any(item["id"] == voice_id for item in server.list_voices(page=1, pageSize=100)["data"]["items"]):
            raise AssertionError("voice was not deleted")
        if server._voice_meta_path(voice_id).exists():
            raise AssertionError("voice metadata survived deletion")

        # --- avatars ------------------------------------------------------
        avatar_id = _write_avatar(server, "授权人物 A")
        listed = server.list_avatars(page=1, pageSize=100)["data"]["items"]
        entry = next((item for item in listed if item["id"] == avatar_id), None)
        if entry is None or entry["displayName"] != "授权人物 A":
            raise AssertionError(f"avatar was not listed: {listed!r}")
        if entry["fileUrl"] != f"/api/commercial/avatars/{avatar_id}/file":
            raise AssertionError(f"avatar file URL invalid: {entry!r}")

        renamed = server.rename_avatar(avatar_id, server.RenameBody(displayName="公司代言人"))
        if renamed["data"]["displayName"] != "公司代言人":
            raise AssertionError(f"avatar rename failed: {renamed!r}")

        preview = server.avatar_file(avatar_id)
        if not pathlib.Path(preview.path).is_file():
            raise AssertionError("avatar preview file is not served")

        server.delete_avatar(avatar_id)
        if any(item["id"] == avatar_id for item in server.list_avatars(page=1, pageSize=100)["data"]["items"]):
            raise AssertionError("avatar was not deleted")
        if server._avatar_meta_path(avatar_id).exists():
            raise AssertionError("avatar metadata survived deletion")

        # --- invariants ---------------------------------------------------
        if server.list_voices(page=1, pageSize=100)["data"]["items"] or server.list_avatars(page=1, pageSize=100)["data"]["items"]:
            raise AssertionError("product created default voice or avatar assets on its own")

        for bad in ("not-an-id", "../../server", "0" * 31):
            for call in (server.rename_voice, server.delete_voice):
                try:
                    call(bad) if call is server.delete_voice else call(bad, server.RenameBody(displayName="x"))
                except Exception as exc:  # HTTPException from FastAPI
                    if getattr(exc, "status_code", None) not in {400, 404}:
                        raise AssertionError(f"unexpected error for {bad!r}: {exc!r}") from exc
                else:
                    raise AssertionError(f"invalid identifier {bad!r} was accepted")

        print("RESULT: BossAI local asset management contract passed (list, audition, rename, delete).")
        print("No default voices or avatars are created by the product.")
        return 0
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
