from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ValidationError

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import bossai_os_bridge
import cosyvoice_adapter
import musetalk_adapter
import qwen_adapter

PRODUCT_ID = "bossai-video-agent"
PRODUCT_VERSION = "0.1.0"
PRODUCT_NAME = "BossAI Video Agent"
ENTITLEMENT_SCHEMA = "bossai.commercial-entitlement.v1"
FEATURE_REWRITE = "video.rewrite"
FEATURE_TTS = "video.tts"
FEATURE_DIGITAL_HUMAN = "video.digital-human"

VOICE_ID_RE = re.compile(r"^[0-9a-f]{32}$", re.I)
AVATAR_ID_RE = re.compile(r"^[0-9a-f]{32}$", re.I)
TTS_ID_RE = re.compile(r"^[0-9a-f]{32}$", re.I)
JOB_ID_RE = re.compile(r"^[0-9a-f]{32}$", re.I)
FINAL_VIDEO_ID_RE = re.compile(r"^[0-9a-f]{32}$", re.I)
ALLOWED_AVATAR_SUFFIXES = {".mp4", ".mov", ".webm", ".mkv"}
MAX_VOICE_BYTES = 128 * 1024 * 1024
MAX_AVATAR_BYTES = 2 * 1024 * 1024 * 1024

app = FastAPI(title=PRODUCT_NAME, version=PRODUCT_VERSION, docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=False,
)

_TTS_JOBS: dict[str, dict[str, Any]] = {}
_DH_JOBS: dict[str, dict[str, Any]] = {}
_RUNTIME_JOBS: dict[str, dict[str, Any]] = {}
_AGENT_EXECUTIONS: dict[str, dict[str, Any]] = {}
_JOB_LOCK = threading.Lock()
_RUNTIME_JOB_LOCK = threading.Lock()
_RUNTIME_INSTALL_LOCK = threading.Lock()
_AGENT_EXECUTION_LOCK = threading.Lock()


class RewriteBody(BaseModel):
    sourceText: str = Field(..., min_length=1, max_length=20000)
    targetChars: int = Field(default=300, ge=80, le=1600)
    platform: str = Field(default="douyin", max_length=64)
    videoType: str = Field(default="voiceover", max_length=64)
    toneStyle: str = Field(default="", max_length=500)
    industryPersona: str = Field(default="", max_length=1000)
    productBusiness: str = Field(default="", max_length=1000)
    sellingPoints: str = Field(default="", max_length=2000)
    extraRequirements: str = Field(default="", max_length=2000)


class TtsBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    voiceId: str = Field(..., min_length=32, max_length=32)
    language: str = Field(default="zh", max_length=32)


class DigitalHumanBody(BaseModel):
    avatarId: str = Field(..., min_length=32, max_length=32)
    audioUrl: str = Field(..., min_length=1, max_length=4096)
    outputFileName: str | None = Field(default=None, max_length=255)


class FinalVideoBody(BaseModel):
    sourceUrl: str = Field(..., min_length=1, max_length=4096)
    projectName: str | None = Field(default=None, max_length=120)


class PublishPrepareBody(BaseModel):
    finalVideoUrl: str = Field(..., min_length=1, max_length=4096)
    platform: Literal["douyin", "channels", "xiaohongshu", "kuaishou"]


class AccountChallengeBody(BaseModel):
    channel: Literal["email", "phone"]
    identifier: str = Field(..., min_length=6, max_length=320)
    locale: str | None = Field(default=None, max_length=20)


class AccountSessionBody(BaseModel):
    mode: Literal["login", "register"]
    identifier: str = Field(..., min_length=6, max_length=320)
    password: str = Field(..., min_length=8, max_length=200)
    displayName: str | None = Field(default=None, min_length=1, max_length=120)
    challengeId: str | None = Field(default=None, min_length=8, max_length=160)
    verificationCode: str | None = Field(default=None, min_length=4, max_length=12)


class RuntimeInstallBody(BaseModel):
    acceptLicense: bool = False
    profile: Literal["gpu", "cpu"] = "gpu"


class AgentPairBody(BaseModel):
    rotate: bool = False
    clientName: str = Field(default="BossAI OS", min_length=1, max_length=120)


class AgentInvokeBody(BaseModel):
    toolId: str = Field(..., min_length=3, max_length=160)
    input: dict[str, Any] = Field(default_factory=dict)
    requestId: str | None = Field(default=None, min_length=8, max_length=160)


def data_root() -> Path:
    explicit = os.environ.get("BOSSAI_VIDEO_DATA_ROOT", "").strip().strip('"')
    if explicit:
        root = Path(explicit).expanduser().resolve()
    elif os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        root = Path(os.environ["LOCALAPPDATA"]) / "BossAI" / "VideoAgent"
    else:
        root = Path.home() / ".bossai" / "video-agent"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _dir(name: str) -> Path:
    path = data_root() / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def _preview_enabled() -> bool:
    return os.environ.get("BOSSAI_VIDEO_COMMERCIAL_PREVIEW", "").strip() == "1"


def _entitlement_snapshot() -> dict[str, Any]:
    preview = _preview_enabled()
    base = {
        "schema": "bossai.video-agent-entitlement-status.v1",
        "productId": PRODUCT_ID,
        "productVersion": PRODUCT_VERSION,
        "verified": False,
        "licenseActive": False,
        "paidExecutionAllowed": False,
        "internalPreviewAllowed": preview,
        "authority": "bossai-headquarters-commerce",
        "upstreamSchema": ENTITLEMENT_SCHEMA,
        "account": None,
        "planCode": "",
        "planName": "",
        "membershipStatus": "",
        "walletAvailable": 0,
        "walletReserved": 0,
        "walletFrozen": False,
        "features": [],
    }
    if preview:
        return {
            **base,
            "status": "preview",
            "reason": "Internal commercial preview is explicitly enabled; no paid customer entitlement is implied.",
        }
    if not bossai_os_bridge.configured():
        return {
            **base,
            "status": "unconfigured",
            "reason": "BossAI OS is not connected on this installation.",
        }
    try:
        session = bossai_os_bridge.account_session()
    except bossai_os_bridge.BossAIOSBridgeError as exc:
        return {**base, "status": "unavailable", "reason": str(exc)}
    account = session.get("account") if isinstance(session, dict) else None
    base["account"] = account
    if not bool(session.get("authenticated")):
        return {
            **base,
            "status": "account_required",
            "reason": "Sign in with a BossAI account to verify the commercial entitlement.",
        }
    try:
        raw = bossai_os_bridge.entitlement(installation_id=_installation_id(), product_version=PRODUCT_VERSION)
    except bossai_os_bridge.BossAIOSBridgeError as exc:
        return {**base, "status": "unavailable", "reason": str(exc)}

    entitlement = raw.get("entitlement") or {}
    device = raw.get("device") or {}
    license_active = bool(entitlement.get("licenseActive"))
    product_allowed = bool(entitlement.get("canUseLocalBusinessProduct"))
    paid_ai_allowed = bool(entitlement.get("canCreatePaidAiTasks"))
    device_registered = bool(device.get("registered"))
    paid_execution = license_active and product_allowed and paid_ai_allowed and device_registered
    return {
        **base,
        "status": "active" if paid_execution else "restricted",
        "verified": True,
        "licenseActive": license_active,
        "paidExecutionAllowed": paid_execution,
        "reason": str(entitlement.get("accessReason") or ("Commercial entitlement is active." if paid_execution else "Commercial entitlement does not permit paid AI execution.")),
        "planCode": str(entitlement.get("planCode") or ""),
        "planName": str(entitlement.get("planName") or ""),
        "membershipStatus": str(entitlement.get("membershipStatus") or ""),
        "walletAvailable": int(entitlement.get("walletAvailable") or 0),
        "walletReserved": int(entitlement.get("walletReserved") or 0),
        "walletFrozen": bool(entitlement.get("walletFrozen")),
        "features": [str(value) for value in (entitlement.get("features") or [])],
        "deviceRegistered": device_registered,
        "entitlementRevision": str(raw.get("entitlementRevision") or ""),
        "generatedAt": str(raw.get("generatedAt") or ""),
    }


def require_execution(feature: str) -> None:
    if _preview_enabled():
        return
    snapshot = _entitlement_snapshot()
    if not bool(snapshot.get("verified")) or not bool(snapshot.get("paidExecutionAllowed")):
        raise HTTPException(403, str(snapshot.get("reason") or "BossAI commercial execution is not entitled on this installation."))
    features = {str(value).strip() for value in (snapshot.get("features") or []) if str(value).strip()}
    if feature not in features:
        raise HTTPException(403, f"Current BossAI plan does not include feature: {feature}")


def _installation_id() -> str:
    path = data_root() / "installation.json"
    if path.is_file():
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            installation_id = str(value.get("installationId") or "")
            if installation_id:
                return installation_id
        except (OSError, json.JSONDecodeError):
            pass
    installation_id = str(uuid.uuid4())
    path.write_text(json.dumps({"installationId": installation_id}, ensure_ascii=False), encoding="utf-8")
    return installation_id


def _set_job(store: dict[str, dict[str, Any]], job_id: str, **values: Any) -> dict[str, Any]:
    with _JOB_LOCK:
        current = dict(store.get(job_id) or {})
        current.update(values)
        store[job_id] = current
        return dict(current)


def _get_job(store: dict[str, dict[str, Any]], job_id: str) -> dict[str, Any] | None:
    with _JOB_LOCK:
        value = store.get(job_id)
        return dict(value) if value else None


def _voice_meta_path(voice_id: str) -> Path:
    return _dir("voices") / f"{voice_id}.json"


def _voice_wav_path(voice_id: str) -> Path:
    return _dir("voices") / f"{voice_id}.wav"


def _resolve_voice(voice_id: str) -> Path:
    if not VOICE_ID_RE.fullmatch(str(voice_id or "")):
        raise HTTPException(400, "Invalid BossAI voice ID.")
    path = _voice_wav_path(voice_id)
    if not path.is_file():
        raise HTTPException(404, "Authorized reference voice not found.")
    return path


def _avatar_path(avatar_id: str) -> Path:
    if not AVATAR_ID_RE.fullmatch(str(avatar_id or "")):
        raise HTTPException(400, "Invalid BossAI avatar ID.")
    matches = [p for p in _dir("avatars").glob(f"{avatar_id}.*") if p.suffix.lower() in ALLOWED_AVATAR_SUFFIXES]
    if len(matches) != 1:
        raise HTTPException(404, "Authorized avatar video not found.")
    return matches[0].resolve()


def _tts_output_path(output_id: str) -> Path:
    if not TTS_ID_RE.fullmatch(str(output_id or "")):
        raise HTTPException(400, "Invalid BossAI audio output ID.")
    path = _dir("tts") / f"{output_id}.wav"
    if not path.is_file():
        raise HTTPException(404, "BossAI audio output not found.")
    return path


def _audio_url_path(audio_url: str) -> Path:
    match = re.fullmatch(r"/api/tts/outputs/([0-9a-f]{32})/file", str(audio_url or "").strip(), re.I)
    if not match:
        raise HTTPException(400, "Digital human rendering accepts only BossAI-generated TTS outputs.")
    return _tts_output_path(match.group(1))


def _digital_human_url_path(video_url: str) -> Path:
    match = re.fullmatch(r"/api/commercial/digital-human/jobs/([0-9a-f]{32})/file", str(video_url or "").strip(), re.I)
    if not match:
        raise HTTPException(400, "Final video creation accepts only BossAI commercial digital-human outputs.")
    job = _get_job(_DH_JOBS, match.group(1))
    if not job or job.get("status") != "done":
        raise HTTPException(404, "BossAI digital human output is not ready.")
    path = Path(str(job.get("outputPath") or "")).resolve()
    root = _dir("digital-human").resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise HTTPException(403, "BossAI digital human output is outside the product data boundary.") from exc
    if not path.is_file():
        raise HTTPException(404, "BossAI digital human output file is missing.")
    return path


def _final_video_path(final_video_id: str) -> Path:
    if not FINAL_VIDEO_ID_RE.fullmatch(str(final_video_id or "")):
        raise HTTPException(400, "Invalid BossAI final video ID.")
    path = (_dir("final-videos") / f"{final_video_id}.mp4").resolve()
    if not path.is_file():
        raise HTTPException(404, "BossAI final video not found.")
    return path


def _final_video_url_path(video_url: str) -> Path:
    match = re.fullmatch(r"/api/commercial/video/final/([0-9a-f]{32})/file", str(video_url or "").strip(), re.I)
    if not match:
        raise HTTPException(400, "Publish preparation accepts only BossAI final videos.")
    return _final_video_path(match.group(1))


def _safe_project_name(value: str | None) -> str:
    text = re.sub(r"[<>:\"/\\|?*\x00-\x1f]+", "-", str(value or "").strip())
    text = re.sub(r"\s+", " ", text).strip(" .-")
    return text[:80] or "BossAI-Video"


def _public_runtime_setup() -> dict[str, Any]:
    qwen = qwen_adapter.inspect_setup()
    cosy = cosyvoice_adapter.inspect_setup()
    muse = musetalk_adapter.inspect_setup()
    return {
        "qwen": {"ready": bool(qwen.get("ready")), "missing": qwen.get("missing") or []},
        "cosyvoice2": {"ready": bool(cosy.get("ready")), "missing": cosy.get("missing") or []},
        "musetalk": {"ready": bool(muse.get("ready")), "missing": _sanitize_musetalk_missing(muse.get("missing") or [])},
    }


def _sanitize_musetalk_missing(values: list[Any]) -> list[str]:
    text = [str(v) for v in values]
    missing: list[str] = []
    if any("MUSETALK_ROOT" in v or "models/" in v.replace("\\", "/") for v in text):
        missing.append("model-runtime")
    if any("Python" in v or "python" in v for v in text):
        missing.append("python-runtime")
    if any("FFmpeg" in v or "ffmpeg" in v for v in text):
        missing.append("ffmpeg-runtime")
    if text and not missing:
        missing.append("runtime-component")
    return sorted(set(missing))


def _runtime_root() -> Path:
    explicit = os.environ.get("BOSSAI_VIDEO_RUNTIME_ROOT", "").strip().strip('"')
    if explicit:
        root = Path(explicit).expanduser().resolve()
    else:
        base = data_root()
        root = (base.parent if base.name.lower() == "data" else base) / "runtimes"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _runtime_support_root() -> Path:
    explicit = os.environ.get("BOSSAI_VIDEO_RUNTIME_SUPPORT_ROOT", "").strip().strip('"')
    if explicit:
        root = Path(explicit).expanduser().resolve()
    else:
        base = data_root()
        root = (base.parent if base.name.lower() == "data" else base) / "runtime-support"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _runtime_installers_root() -> Path:
    explicit = os.environ.get("BOSSAI_VIDEO_RESOURCES_ROOT", "").strip().strip('"')
    base = Path(explicit).expanduser().resolve() if explicit else HERE.parent
    return (base / "runtime-installers").resolve()


def _private_python310() -> Path:
    return (_runtime_support_root() / "python310" / "python.exe").resolve()


def _ffmpeg_executable() -> str:
    explicit = os.environ.get("BOSSAI_FFMPEG_BIN", "").strip().strip('"')
    if explicit and Path(explicit).is_file():
        return str(Path(explicit).resolve())
    found = shutil.which("ffmpeg.exe") or shutil.which("ffmpeg")
    return str(Path(found).resolve()) if found else ""


def _powershell_executable() -> str:
    found = shutil.which("powershell.exe") or shutil.which("powershell")
    if found:
        return str(Path(found).resolve())
    fallback = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    return str(fallback.resolve()) if fallback.is_file() else ""


def _require_local_control(token: str) -> None:
    expected = os.environ.get("BOSSAI_VIDEO_LOCAL_CONTROL_TOKEN", "").strip()
    supplied = str(token or "").strip()
    if not expected or not supplied or not secrets.compare_digest(expected, supplied):
        raise HTTPException(403, "BossAI local control authorization is required.")


def _require_loopback(request: Request) -> None:
    host = str(getattr(getattr(request, "client", None), "host", "") or "").strip().lower()
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(403, "BossAI Agent API is available only on the customer-local loopback interface.")


def _agent_connector_path() -> Path:
    return data_root() / "agent-connector.json"


def _agent_connector_token(*, rotate: bool = False) -> str:
    path = _agent_connector_path()
    if not rotate and path.is_file():
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            token = str(value.get("token") or "").strip()
            if len(token) >= 32:
                return token
        except (OSError, json.JSONDecodeError):
            pass
    token = secrets.token_urlsafe(48)
    payload = {
        "schema": "bossai.video-agent-connector-secret.v1",
        "productId": PRODUCT_ID,
        "token": token,
        "createdAt": time.time(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return token


def _require_agent_token(request: Request, token: str) -> None:
    _require_loopback(request)
    expected = _agent_connector_token()
    supplied = str(token or "").strip()
    if not supplied or not secrets.compare_digest(expected, supplied):
        raise HTTPException(403, "BossAI Agent connector token is invalid.")


def _agent_tool_manifest() -> list[dict[str, Any]]:
    read_contract = {
        "riskLevel": "L2",
        "requiresHumanApproval": False,
        "auditRequiredByBossAIOS": True,
        "externalSideEffect": False,
        "bossaiOsTool": "connector.read",
    }
    local_generate = {
        "riskLevel": "L2",
        "requiresHumanApproval": False,
        "auditRequiredByBossAIOS": True,
        "externalSideEffect": False,
        "bossaiOsTool": "media.video.request",
    }
    return [
        {
            "id": "bossai.video.product.read",
            "name": "读取视频产品状态",
            "description": "读取 BossAI Video Agent 产品、版本和本地 runtime 就绪状态。",
            "access": "read",
            "async": False,
            "inputSchema": {"type": "object", "additionalProperties": False},
            **read_contract,
        },
        {
            "id": "bossai.video.entitlement.read",
            "name": "读取商业授权状态",
            "description": "读取 Headquarters Commerce 返回的本产品商业 entitlement 投影。",
            "access": "read",
            "async": False,
            "inputSchema": {"type": "object", "additionalProperties": False},
            **read_contract,
        },
        {
            "id": "bossai.video.runtime.read",
            "name": "读取视频运行环境",
            "description": "读取 Qwen、CosyVoice2 和 MuseTalk 的就绪状态，不暴露本地绝对路径或凭据。",
            "access": "read",
            "async": False,
            "inputSchema": {"type": "object", "additionalProperties": False},
            **read_contract,
        },
        {
            "id": "bossai.video.voices.list",
            "name": "列出授权声音",
            "description": "列出客户已上传并授权使用的参考声音。",
            "access": "read",
            "async": False,
            "inputSchema": {
                "type": "object",
                "properties": {"page": {"type": "integer", "minimum": 1}, "pageSize": {"type": "integer", "minimum": 1, "maximum": 500}},
                "additionalProperties": False,
            },
            **read_contract,
        },
        {
            "id": "bossai.video.rewrite",
            "name": "生成口播文案",
            "description": "调用本地 BossAI 视频文案能力生成或改写口播稿。",
            "access": "execute",
            "async": False,
            "entitlementFeature": FEATURE_REWRITE,
            "inputSchema": RewriteBody.model_json_schema(),
            **local_generate,
        },
        {
            "id": "bossai.video.tts.generate",
            "name": "生成配音",
            "description": "使用客户已授权参考声音生成本地语音任务。",
            "access": "execute",
            "async": True,
            "entitlementFeature": FEATURE_TTS,
            "inputSchema": TtsBody.model_json_schema(),
            **local_generate,
        },
        {
            "id": "bossai.video.tts.job.read",
            "name": "读取配音任务",
            "description": "查询本产品已创建的配音任务状态和结果引用。",
            "access": "read",
            "async": False,
            "inputSchema": {"type": "object", "required": ["jobId"], "properties": {"jobId": {"type": "string", "pattern": "^[0-9a-fA-F]{32}$"}}, "additionalProperties": False},
            **read_contract,
        },
        {
            "id": "bossai.video.digital-human.setup",
            "name": "读取数字人运行环境",
            "description": "读取 MuseTalk 数字人运行环境与授权素材要求。",
            "access": "read",
            "async": False,
            "inputSchema": {"type": "object", "additionalProperties": False},
            **read_contract,
        },
        {
            "id": "bossai.video.digital-human.render",
            "name": "生成数字人口播视频",
            "description": "使用客户授权头像视频和本产品生成的音频创建本地数字人口播视频。",
            "access": "execute",
            "async": True,
            "entitlementFeature": FEATURE_DIGITAL_HUMAN,
            "inputSchema": DigitalHumanBody.model_json_schema(),
            **local_generate,
        },
        {
            "id": "bossai.video.digital-human.job.read",
            "name": "读取数字人任务",
            "description": "查询本产品数字人任务状态和结果引用。",
            "access": "read",
            "async": False,
            "inputSchema": {"type": "object", "required": ["jobId"], "properties": {"jobId": {"type": "string", "pattern": "^[0-9a-fA-F]{32}$"}}, "additionalProperties": False},
            **read_contract,
        },
    ]


def _agent_tool_by_id(tool_id: str) -> dict[str, Any] | None:
    return next((item for item in _agent_tool_manifest() if item["id"] == tool_id), None)


def _agent_cache_get(request_id: str | None) -> dict[str, Any] | None:
    if not request_id:
        return None
    with _AGENT_EXECUTION_LOCK:
        value = _AGENT_EXECUTIONS.get(request_id)
        return json.loads(json.dumps(value, ensure_ascii=False)) if value else None


def _agent_cache_set(request_id: str | None, value: dict[str, Any]) -> None:
    if not request_id:
        return
    with _AGENT_EXECUTION_LOCK:
        if len(_AGENT_EXECUTIONS) >= 256:
            _AGENT_EXECUTIONS.pop(next(iter(_AGENT_EXECUTIONS)), None)
        _AGENT_EXECUTIONS[request_id] = json.loads(json.dumps(value, ensure_ascii=False))


def _agent_request_digest(tool_id: str, input_value: dict[str, Any]) -> str:
    canonical = json.dumps({"toolId": tool_id, "input": input_value}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _agent_execute_tool(tool_id: str, input_value: dict[str, Any]) -> Any:
    if tool_id == "bossai.video.product.read":
        if input_value:
            raise HTTPException(400, "This tool does not accept input fields.")
        return commercial_product()["data"]
    if tool_id == "bossai.video.entitlement.read":
        if input_value:
            raise HTTPException(400, "This tool does not accept input fields.")
        return _entitlement_snapshot()
    if tool_id == "bossai.video.runtime.read":
        if input_value:
            raise HTTPException(400, "This tool does not accept input fields.")
        return _public_runtime_setup()
    if tool_id == "bossai.video.voices.list":
        try:
            page = int(input_value.get("page", 1))
            page_size = int(input_value.get("pageSize", 100))
        except (TypeError, ValueError) as exc:
            raise HTTPException(400, "page and pageSize must be integers.") from exc
        if page < 1 or page_size < 1 or page_size > 500 or set(input_value) - {"page", "pageSize"}:
            raise HTTPException(400, "Voice list input is invalid.")
        return list_voices(page=page, pageSize=page_size)["data"]
    if tool_id == "bossai.video.rewrite":
        return llm_rewrite(RewriteBody.model_validate(input_value))["data"]
    if tool_id == "bossai.video.tts.generate":
        return generate_tts(TtsBody.model_validate(input_value))["data"]
    if tool_id == "bossai.video.tts.job.read":
        if set(input_value) != {"jobId"}:
            raise HTTPException(400, "TTS job read requires only jobId.")
        return tts_job(str(input_value.get("jobId") or ""))["data"]
    if tool_id == "bossai.video.digital-human.setup":
        if input_value:
            raise HTTPException(400, "This tool does not accept input fields.")
        return digital_human_setup()["data"]
    if tool_id == "bossai.video.digital-human.render":
        return render_digital_human(DigitalHumanBody.model_validate(input_value))["data"]
    if tool_id == "bossai.video.digital-human.job.read":
        if set(input_value) != {"jobId"}:
            raise HTTPException(400, "Digital-human job read requires only jobId.")
        return digital_human_job(str(input_value.get("jobId") or ""))["data"]
    raise HTTPException(404, "BossAI Video Agent tool is not available.")


_RUNTIME_ENV_KEYS = {
    "BOSSAI_QWEN_MODEL",
    "BOSSAI_QWEN_PYTHON",
    "BOSSAI_COSYVOICE_ROOT",
    "BOSSAI_COSYVOICE_MODEL_DIR",
    "BOSSAI_COSYVOICE_PYTHON",
    "BOSSAI_MUSETALK_ROOT",
    "BOSSAI_MUSETALK_PYTHON",
    "BOSSAI_FFMPEG_BIN",
}


def _runtime_manifest_path(component: str) -> Path:
    if component == "python310":
        return _runtime_support_root() / "python310" / "runtime.json"
    mapping = {
        "qwen": "qwen2.5-7b-instruct",
        "cosyvoice2": "cosyvoice2-0.5b",
        "musetalk": "musetalk",
    }
    name = mapping.get(component)
    if not name:
        raise HTTPException(404, "Unknown BossAI runtime component.")
    return _runtime_root() / name / "runtime.json"


def _apply_installed_runtime_env(component: str) -> None:
    path = _runtime_manifest_path(component)
    if not path.is_file():
        return
    try:
        manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return
    values = manifest.get("env") if isinstance(manifest, dict) else None
    if not isinstance(values, dict):
        return
    for key, raw in values.items():
        if key not in _RUNTIME_ENV_KEYS:
            continue
        value = str(raw or "").strip()
        if value:
            os.environ[key] = value


def _runtime_install_center() -> dict[str, Any]:
    setup = _public_runtime_setup()
    installers = _runtime_installers_root()
    python_path = _private_python310()
    ffmpeg = _ffmpeg_executable()
    powershell = _powershell_executable()
    python_ready = python_path.is_file()
    return {
        "schema": "bossai.video-agent-runtime-install-center.v1",
        "busy": _RUNTIME_INSTALL_LOCK.locked(),
        "localControlRequired": True,
        "powershellReady": bool(powershell),
        "support": {
            "python310": {
                "ready": python_ready,
                "version": "3.10.11",
                "installerAvailable": (installers / "install-python310.ps1").is_file(),
            },
            "ffmpeg": {
                "ready": bool(ffmpeg),
                "source": "configured-or-system" if ffmpeg else "missing",
            },
        },
        "components": {
            "qwen": {
                **setup["qwen"],
                "installerAvailable": (installers / "install-qwen.ps1").is_file(),
                "installable": bool(powershell and python_ready),
                "requires": ["python310"],
            },
            "cosyvoice2": {
                **setup["cosyvoice2"],
                "installerAvailable": (installers / "install-cosyvoice2.ps1").is_file(),
                "installable": bool(powershell and python_ready),
                "requires": ["python310"],
            },
            "musetalk": {
                **setup["musetalk"],
                "installerAvailable": (installers / "install-musetalk.ps1").is_file(),
                "installable": bool(powershell and python_ready and ffmpeg),
                "requires": ["python310", "ffmpeg"],
            },
        },
    }


def _new_runtime_job(component: str) -> str:
    job_id = uuid.uuid4().hex
    with _RUNTIME_JOB_LOCK:
        _RUNTIME_JOBS[job_id] = {
            "jobId": job_id,
            "component": component,
            "status": "queued",
            "message": "等待安装",
            "progress": 0,
            "logs": [],
            "startedAt": None,
            "finishedAt": None,
        }
    return job_id


def _patch_runtime_job(job_id: str, **changes: Any) -> None:
    with _RUNTIME_JOB_LOCK:
        job = _RUNTIME_JOBS.get(job_id)
        if not job:
            return
        job.update(changes)
        logs = job.get("logs")
        if isinstance(logs, list) and len(logs) > 80:
            job["logs"] = logs[-80:]


def _append_runtime_log(job_id: str, line: str) -> None:
    clean = str(line or "").strip()
    if not clean:
        return
    with _RUNTIME_JOB_LOCK:
        job = _RUNTIME_JOBS.get(job_id)
        if not job:
            return
        logs = job.setdefault("logs", [])
        if isinstance(logs, list):
            logs.append(clean[:2000])
            if len(logs) > 80:
                del logs[:-80]
        job["message"] = clean[:500]


def _runtime_installer_command(component: str, profile: str) -> list[str]:
    powershell = _powershell_executable()
    if not powershell:
        raise HTTPException(503, "Windows PowerShell is unavailable.")
    installers = _runtime_installers_root()
    python_exe = _private_python310()
    runtime_root = _runtime_root()
    base = [powershell, "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]
    if component == "python310":
        script = installers / "install-python310.ps1"
        args = [str(script), "-TargetDir", str(_runtime_support_root() / "python310"), "-AcceptLicense"]
    elif component == "qwen":
        if not python_exe.is_file():
            raise HTTPException(409, "Install the BossAI private Python 3.10 runtime first.")
        script = installers / "install-qwen.ps1"
        flavor = "cu124" if profile == "gpu" else "cpu"
        args = [str(script), "-TargetDir", str(runtime_root / "qwen2.5-7b-instruct"), "-PythonExe", str(python_exe), "-WheelFlavor", flavor, "-AcceptLicense"]
    elif component == "cosyvoice2":
        if not python_exe.is_file():
            raise HTTPException(409, "Install the BossAI private Python 3.10 runtime first.")
        script = installers / "install-cosyvoice2.ps1"
        flavor = "cu118" if profile == "gpu" else "cpu"
        args = [str(script), "-TargetDir", str(runtime_root / "cosyvoice2-0.5b"), "-PythonExe", str(python_exe), "-TorchFlavor", flavor, "-AcceptLicense"]
    elif component == "musetalk":
        if profile != "gpu":
            raise HTTPException(400, "MuseTalk commercial runtime currently requires the GPU profile.")
        if not python_exe.is_file():
            raise HTTPException(409, "Install the BossAI private Python 3.10 runtime first.")
        ffmpeg = _ffmpeg_executable()
        if not ffmpeg:
            raise HTTPException(409, "FFmpeg is required before MuseTalk can be installed.")
        script = installers / "install-musetalk.ps1"
        args = [str(script), "-TargetDir", str(runtime_root / "musetalk"), "-PythonExe", str(python_exe), "-FfmpegExe", ffmpeg, "-AcceptLicense"]
    else:
        raise HTTPException(404, "Unknown BossAI runtime component.")
    if not script.is_file():
        raise HTTPException(503, f"BossAI runtime installer is missing: {script.name}")
    return base + args


def _run_runtime_installer(job_id: str, component: str, command: list[str]) -> None:
    started = time.time()
    _patch_runtime_job(job_id, status="running", message="正在安装", progress=5, startedAt=started)
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        process = subprocess.Popen(
            command,
            cwd=str(_runtime_installers_root()),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            creationflags=creationflags,
        )
        assert process.stdout is not None
        for line in process.stdout:
            _append_runtime_log(job_id, line)
        return_code = process.wait()
        if return_code != 0:
            raise RuntimeError(f"Runtime installer exited with code {return_code}.")
        _apply_installed_runtime_env(component)
        _patch_runtime_job(
            job_id,
            status="done",
            message="安装完成",
            progress=100,
            finishedAt=time.time(),
            runtime=_runtime_install_center(),
        )
    except Exception as exc:
        _patch_runtime_job(job_id, status="failed", message=str(exc), progress=100, finishedAt=time.time())
    finally:
        _RUNTIME_INSTALL_LOCK.release()


@app.get("/health")
def health():
    return {"success": True, "data": {"product": PRODUCT_ID, "status": "ready", "version": PRODUCT_VERSION}}


@app.post("/__bossai__/shutdown", include_in_schema=False)
def local_shutdown(x_bossai_shutdown_token: str = Header(default="")):
    expected = os.environ.get("BOSSAI_VIDEO_SHUTDOWN_TOKEN", "").strip()
    if not expected or x_bossai_shutdown_token != expected:
        raise HTTPException(403, "Shutdown token is invalid.")

    def request_exit() -> None:
        server = getattr(app.state, "uvicorn_server", None)
        if server is not None:
            server.should_exit = True

    threading.Timer(0.15, request_exit).start()
    return {"success": True, "data": {"shutdownRequested": True}}


@app.get("/api/commercial/product")
def commercial_product():
    runtime = _public_runtime_setup()
    return {
        "success": True,
        "data": {
            "schema": "bossai.video-agent-product.v1",
            "id": PRODUCT_ID,
            "name": PRODUCT_NAME,
            "version": PRODUCT_VERSION,
            "edition": "Commercial Preview",
            "installationId": _installation_id(),
            "commercialAuthority": "bossai-headquarters-commerce",
            "entitlementSchema": ENTITLEMENT_SCHEMA,
            "distributionReady": False,
            "runtime": runtime,
        },
    }


@app.get("/api/agent/v1/manifest")
def agent_manifest(request: Request):
    _require_loopback(request)
    return {
        "success": True,
        "data": {
            "schema": "bossai.video-agent-tool-manifest.v1",
            "product": {"id": PRODUCT_ID, "name": PRODUCT_NAME, "version": PRODUCT_VERSION},
            "agentPlatform": "bossai-os",
            "harness": "bossaiworkforce",
            "toolRegistryAuthority": "bossai-os",
            "executionEndpoint": "/api/agent/v1/invoke",
            "pairingEndpoint": "/api/agent/v1/pair",
            "tools": _agent_tool_manifest(),
            "guardedCapabilities": [
                {
                    "id": "bossai.video.account.bind",
                    "available": False,
                    "requiresHumanApproval": True,
                    "bossaiOsTool": "connector.write",
                    "reason": "Platform account binding is not exposed to autonomous Agent invocation.",
                },
                {
                    "id": "bossai.video.publish.external",
                    "available": False,
                    "requiresHumanApproval": True,
                    "bossaiOsTool": "connector.write",
                    "reason": "External publish remains approval-gated and is not enabled in the commercial Agent API.",
                },
                {
                    "id": "bossai.video.runtime.install",
                    "available": False,
                    "requiresHumanApproval": True,
                    "bossaiOsTool": "connector.write",
                    "reason": "Runtime installation requires local human control and license acceptance.",
                },
            ],
            "prohibited": ["arbitrary-shell", "arbitrary-filesystem", "provider-credentials", "approval-bypass", "direct-external-publish"],
        },
    }


@app.post("/api/agent/v1/pair")
def agent_pair(
    request: Request,
    body: AgentPairBody,
    x_bossai_local_control: str = Header(default=""),
):
    _require_loopback(request)
    _require_local_control(x_bossai_local_control)
    token = _agent_connector_token(rotate=body.rotate)
    return {
        "success": True,
        "data": {
            "schema": "bossai.video-agent-pairing.v1",
            "productId": PRODUCT_ID,
            "connectorId": "bossai-video-agent-local",
            "clientName": body.clientName,
            "baseUrl": "http://127.0.0.1:8765",
            "manifestPath": "/api/agent/v1/manifest",
            "invokePath": "/api/agent/v1/invoke",
            "token": token,
            "tokenHeader": "X-BossAI-Agent-Token",
            "loopbackOnly": True,
            "rotated": bool(body.rotate),
        },
    }


@app.post("/api/agent/v1/invoke")
def agent_invoke(
    request: Request,
    body: AgentInvokeBody,
    x_bossai_agent_token: str = Header(default=""),
    x_bossai_agent_id: str = Header(default=""),
):
    _require_agent_token(request, x_bossai_agent_token)
    tool = _agent_tool_by_id(body.toolId)
    if tool is None:
        raise HTTPException(404, "BossAI Video Agent tool is not declared.")
    digest = _agent_request_digest(body.toolId, body.input)
    cached = _agent_cache_get(body.requestId)
    if cached is not None:
        if cached.get("requestDigest") != digest:
            raise HTTPException(409, "requestId was already used for a different Agent tool invocation.")
        replay = dict(cached)
        replay.pop("requestDigest", None)
        replay["idempotentReplay"] = True
        return {"success": True, "data": replay}

    try:
        output = _agent_execute_tool(body.toolId, body.input)
    except ValidationError as exc:
        raise HTTPException(400, exc.errors(include_url=False)) from exc

    execution = {
        "schema": "bossai.video-agent-tool-execution.v1",
        "executionId": f"video-tool-{uuid.uuid4()}",
        "requestId": body.requestId,
        "toolId": body.toolId,
        "agentId": str(x_bossai_agent_id or "").strip()[:160] or None,
        "status": "accepted" if bool(tool.get("async")) else "completed",
        "riskLevel": tool.get("riskLevel"),
        "requiresHumanApproval": bool(tool.get("requiresHumanApproval")),
        "bossaiOsTool": tool.get("bossaiOsTool"),
        "output": output,
        "idempotentReplay": False,
        "requestDigest": digest,
    }
    _agent_cache_set(body.requestId, execution)
    public = dict(execution)
    public.pop("requestDigest", None)
    return {"success": True, "data": public}


@app.get("/api/account/session")
def account_session():
    try:
        return {"success": True, "data": bossai_os_bridge.account_session()}
    except bossai_os_bridge.BossAIOSBridgeError as exc:
        raise HTTPException(exc.status, str(exc)) from exc


@app.post("/api/account/challenges")
def account_challenge(body: AccountChallengeBody):
    try:
        return {"success": True, "data": bossai_os_bridge.create_challenge(body.model_dump(exclude_none=True))}
    except bossai_os_bridge.BossAIOSBridgeError as exc:
        raise HTTPException(exc.status, str(exc)) from exc


@app.post("/api/account/session")
def account_authenticate(body: AccountSessionBody):
    payload = body.model_dump(exclude_none=True)
    if body.mode == "register" and (not body.displayName or not body.challengeId or not body.verificationCode):
        raise HTTPException(400, "Registration requires display name, challenge ID and verification code.")
    try:
        return {"success": True, "data": bossai_os_bridge.authenticate(payload)}
    except bossai_os_bridge.BossAIOSBridgeError as exc:
        raise HTTPException(exc.status, str(exc)) from exc


@app.post("/api/account/logout")
def account_logout():
    try:
        return {"success": True, "data": bossai_os_bridge.logout()}
    except bossai_os_bridge.BossAIOSBridgeError as exc:
        raise HTTPException(exc.status, str(exc)) from exc


@app.get("/api/commercial/entitlement")
def commercial_entitlement():
    return {"success": True, "data": _entitlement_snapshot()}


@app.get("/api/commercial/runtime")
def commercial_runtime():
    return {"success": True, "data": _public_runtime_setup()}


@app.get("/api/commercial/runtime/install-center")
def commercial_runtime_install_center():
    return {"success": True, "data": _runtime_install_center()}


@app.post("/api/commercial/runtime/install/{component}")
def commercial_runtime_install(
    component: str,
    body: RuntimeInstallBody,
    x_bossai_local_control: str = Header(default=""),
):
    _require_local_control(x_bossai_local_control)
    if not body.acceptLicense:
        raise HTTPException(400, "Runtime license notices must be accepted before installation.")
    command = _runtime_installer_command(component, body.profile)
    if not _RUNTIME_INSTALL_LOCK.acquire(blocking=False):
        raise HTTPException(409, "Another BossAI runtime installation is already running.")
    job_id = _new_runtime_job(component)
    try:
        threading.Thread(
            target=_run_runtime_installer,
            args=(job_id, component, command),
            daemon=True,
            name=f"bossai-runtime-install-{component}",
        ).start()
    except Exception:
        _RUNTIME_INSTALL_LOCK.release()
        raise
    return {"success": True, "data": {"jobId": job_id, "component": component, "status": "queued"}}


@app.get("/api/commercial/runtime/install-jobs/{job_id}")
def commercial_runtime_install_job(job_id: str, x_bossai_local_control: str = Header(default="")):
    _require_local_control(x_bossai_local_control)
    if not JOB_ID_RE.fullmatch(str(job_id or "")):
        raise HTTPException(400, "Invalid BossAI runtime installation job ID.")
    with _RUNTIME_JOB_LOCK:
        value = _RUNTIME_JOBS.get(job_id)
        if value is None:
            raise HTTPException(404, "BossAI runtime installation job not found.")
        return {"success": True, "data": json.loads(json.dumps(value, ensure_ascii=False))}


@app.post("/api/llm/rewrite")
def llm_rewrite(body: RewriteBody):
    require_execution(FEATURE_REWRITE)
    try:
        rewritten = qwen_adapter.rewrite(body.sourceText, body.model_dump())
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(503, str(exc)) from exc
    return {"success": True, "data": {"rewriteText": rewritten, "engine": qwen_adapter.ENGINE_ID}}


@app.get("/api/voices/")
def list_voices(page: int = Query(default=1, ge=1), pageSize: int = Query(default=100, ge=1, le=500)):
    items: list[dict[str, Any]] = []
    for meta_path in sorted(_dir("voices").glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        voice_id = str(meta.get("id") or "")
        if VOICE_ID_RE.fullmatch(voice_id) and _voice_wav_path(voice_id).is_file():
            items.append({"id": voice_id, "displayName": str(meta.get("displayName") or "授权声音")})
    start = (page - 1) * pageSize
    return {"success": True, "data": {"items": items[start : start + pageSize], "total": len(items)}}


@app.post("/api/voices/upload")
async def upload_voice(file: UploadFile = File(...), displayName: str = ""):
    suffix = Path(file.filename or "voice.wav").suffix.lower()
    if suffix != ".wav":
        raise HTTPException(400, "Reference voice must be a WAV file.")
    voice_id = uuid.uuid4().hex
    target = _voice_wav_path(voice_id)
    size = 0
    try:
        with target.open("wb") as handle:
            while True:
                chunk = await file.read(4 * 1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_VOICE_BYTES:
                    raise HTTPException(413, "Reference voice exceeds the 128 MiB limit.")
                handle.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    if size < 1024:
        target.unlink(missing_ok=True)
        raise HTTPException(400, "Reference voice is empty or invalid.")
    meta = {"id": voice_id, "displayName": str(displayName or Path(file.filename or "voice").stem)[:100], "sizeBytes": size}
    _voice_meta_path(voice_id).write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return {"success": True, "data": meta}


@app.post("/api/tts/generate")
def generate_tts(body: TtsBody):
    require_execution(FEATURE_TTS)
    reference = _resolve_voice(body.voiceId)
    setup = cosyvoice_adapter.inspect_setup()
    if not setup.get("ready"):
        raise HTTPException(503, "CosyVoice2 commercial runtime is not ready: " + ", ".join(setup.get("missing") or []))

    job_id = uuid.uuid4().hex
    output_id = uuid.uuid4().hex
    _set_job(_TTS_JOBS, job_id, id=job_id, status="queued", progress=0, message="BossAI voice task queued")

    def worker() -> None:
        _set_job(_TTS_JOBS, job_id, status="running", progress=10, message="Generating BossAI voice")
        try:
            result = cosyvoice_adapter.render(
                text=body.text,
                reference_audio=reference,
                output_dir=_dir("tts"),
                worker_path=HERE / "cosyvoice_worker.py",
            )
            source = Path(str(result["outputPath"])).resolve()
            target = _dir("tts") / f"{output_id}.wav"
            if source != target:
                source.replace(target)
            _set_job(
                _TTS_JOBS,
                job_id,
                status="done",
                progress=100,
                message="BossAI voice completed",
                fileUrl=f"/api/tts/outputs/{output_id}/file",
                engine=cosyvoice_adapter.ENGINE_ID,
                sizeBytes=target.stat().st_size,
            )
        except Exception as exc:
            _set_job(_TTS_JOBS, job_id, status="failed", progress=100, message=str(exc))

    threading.Thread(target=worker, daemon=True, name=f"bossai-tts-{job_id[:8]}").start()
    return {"success": True, "data": {"jobId": job_id, "status": "queued", "engine": cosyvoice_adapter.ENGINE_ID}}


@app.get("/api/tts/jobs/{job_id}")
def tts_job(job_id: str):
    if not JOB_ID_RE.fullmatch(job_id):
        raise HTTPException(404, "BossAI voice job not found.")
    job = _get_job(_TTS_JOBS, job_id)
    if job is None:
        raise HTTPException(404, "BossAI voice job not found.")
    return {"success": True, "data": job}


@app.get("/api/tts/outputs/{output_id}/file")
def tts_file(output_id: str):
    path = _tts_output_path(output_id)
    return FileResponse(path, media_type="audio/wav", filename=f"bossai-voice-{output_id}.wav")


@app.post("/api/commercial/assets/avatar-video")
async def upload_avatar(file: UploadFile = File(...)):
    suffix = Path(file.filename or "avatar.mp4").suffix.lower()
    if suffix not in ALLOWED_AVATAR_SUFFIXES:
        raise HTTPException(400, "Avatar video must be MP4, MOV, WEBM or MKV.")
    avatar_id = uuid.uuid4().hex
    target = _dir("avatars") / f"{avatar_id}{suffix}"
    size = 0
    try:
        with target.open("wb") as handle:
            while True:
                chunk = await file.read(8 * 1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_AVATAR_BYTES:
                    raise HTTPException(413, "Avatar video exceeds the 2 GiB limit.")
                handle.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    if size < 1024:
        target.unlink(missing_ok=True)
        raise HTTPException(400, "Avatar video is empty or invalid.")
    return {
        "success": True,
        "data": {"schema": "bossai.video-agent-avatar.v1", "avatarId": avatar_id, "sizeBytes": size},
    }


@app.get("/api/commercial/digital-human/setup")
def digital_human_setup():
    raw = musetalk_adapter.inspect_setup()
    return {
        "success": True,
        "data": {
            "schema": "bossai.video-agent-musetalk-runtime.v1",
            "engine": "musetalk-v1.5",
            "version": str(raw.get("version") or "v15"),
            "ready": bool(raw.get("ready")),
            "missing": _sanitize_musetalk_missing(raw.get("missing") or []),
            "requiresCustomerAuthorizedAvatar": True,
            "requiresCustomerAuthorizedAudio": True,
        },
    }


@app.post("/api/commercial/digital-human/render")
def render_digital_human(body: DigitalHumanBody):
    require_execution(FEATURE_DIGITAL_HUMAN)
    avatar = _avatar_path(body.avatarId)
    audio = _audio_url_path(body.audioUrl)
    setup = musetalk_adapter.inspect_setup()
    if not setup.get("ready"):
        raise HTTPException(503, "MuseTalk commercial runtime is not ready: " + ", ".join(_sanitize_musetalk_missing(setup.get("missing") or [])))

    job_id = uuid.uuid4().hex
    _set_job(_DH_JOBS, job_id, id=job_id, status="queued", progress=0, message="BossAI digital human task queued")

    def worker() -> None:
        _set_job(_DH_JOBS, job_id, status="running", progress=10, message="Rendering BossAI digital human")
        try:
            result = musetalk_adapter.render(
                video_path=avatar,
                audio_path=audio,
                output_dir=_dir("digital-human"),
                output_filename=body.outputFileName,
            )
            path = Path(str(result["outputPath"])).resolve()
            _set_job(
                _DH_JOBS,
                job_id,
                status="done",
                progress=100,
                message="BossAI digital human completed",
                outputPath=str(path),
                fileUrl=f"/api/commercial/digital-human/jobs/{job_id}/file",
                engine="musetalk-v1.5",
                sizeBytes=path.stat().st_size,
            )
        except Exception as exc:
            _set_job(_DH_JOBS, job_id, status="failed", progress=100, message=str(exc))

    threading.Thread(target=worker, daemon=True, name=f"bossai-musetalk-{job_id[:8]}").start()
    return {"success": True, "data": {"jobId": job_id, "status": "queued", "engine": "musetalk-v1.5"}}


@app.get("/api/commercial/digital-human/jobs/{job_id}")
def digital_human_job(job_id: str):
    if not JOB_ID_RE.fullmatch(job_id):
        raise HTTPException(404, "BossAI digital human job not found.")
    job = _get_job(_DH_JOBS, job_id)
    if job is None:
        raise HTTPException(404, "BossAI digital human job not found.")
    public = {key: value for key, value in job.items() if key != "outputPath"}
    return {"success": True, "data": public}


@app.get("/api/commercial/digital-human/jobs/{job_id}/file")
def digital_human_file(job_id: str):
    if not JOB_ID_RE.fullmatch(job_id):
        raise HTTPException(404, "BossAI digital human output not found.")
    job = _get_job(_DH_JOBS, job_id)
    if not job or job.get("status") != "done":
        raise HTTPException(404, "BossAI digital human output not ready.")
    path = Path(str(job.get("outputPath") or "")).resolve()
    root = _dir("digital-human").resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise HTTPException(403, "BossAI digital human output is outside the product data boundary.") from exc
    if not path.is_file():
        raise HTTPException(404, "BossAI digital human output file is missing.")
    return FileResponse(path, media_type="video/mp4", filename=path.name)


@app.post("/api/commercial/video/finalize")
def finalize_video(body: FinalVideoBody):
    source = _digital_human_url_path(body.sourceUrl)
    final_video_id = uuid.uuid4().hex
    project_name = _safe_project_name(body.projectName)
    target = (_dir("final-videos") / f"{final_video_id}.mp4").resolve()
    shutil.copy2(source, target)
    return {
        "success": True,
        "data": {
            "schema": "bossai.video-agent-final-video.v1",
            "finalVideoId": final_video_id,
            "projectName": project_name,
            "fileUrl": f"/api/commercial/video/final/{final_video_id}/file",
            "downloadName": f"{project_name}.mp4",
            "sizeBytes": target.stat().st_size,
            "sourceType": "bossai-commercial-digital-human",
        },
    }


@app.get("/api/commercial/video/final/{final_video_id}/file")
def final_video_file(final_video_id: str):
    path = _final_video_path(final_video_id)
    return FileResponse(path, media_type="video/mp4", filename=f"bossai-video-{final_video_id}.mp4")


@app.get("/api/commercial/publish/status")
def commercial_publish_status():
    return {
        "success": True,
        "data": {
            "schema": "bossai.video-agent-publish-status.v1",
            "automatedPublishAllowed": False,
            "approvalRequired": True,
            "manualExportAllowed": True,
            "reason": "Automated external publishing remains fail-closed until BossAI approval and platform-account binding are connected.",
            "platforms": ["douyin", "channels", "xiaohongshu", "kuaishou"],
        },
    }


@app.post("/api/commercial/publish/prepare")
def prepare_commercial_publish(body: PublishPrepareBody):
    path = _final_video_url_path(body.finalVideoUrl)
    return {
        "success": True,
        "data": {
            "schema": "bossai.video-agent-publish-preparation.v1",
            "platform": body.platform,
            "status": "blocked",
            "automatedPublishAllowed": False,
            "manualExportAllowed": True,
            "approvalRequired": True,
            "sizeBytes": path.stat().st_size,
            "reason": "BossAI external publish is intentionally fail-closed in Commercial Preview. Export the final video locally; automated publishing will require governed approval and an authenticated platform account.",
        },
    }


def main() -> int:
    import uvicorn

    host = os.environ.get("BOSSAI_VIDEO_HOST", "127.0.0.1")
    port = int(os.environ.get("BOSSAI_VIDEO_PORT", "8765"))
    config = uvicorn.Config(app, host=host, port=port, log_level="info", access_log=False)
    server = uvicorn.Server(config)
    app.state.uvicorn_server = server
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
