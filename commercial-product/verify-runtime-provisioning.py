from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
INSTALLERS = HERE / "runtime-installers"
HEX40 = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
HEX64 = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def installer_text(name: str, failures: list[str]) -> str:
    path = INSTALLERS / name
    require(path.is_file(), f"missing installer: {name}", failures)
    return path.read_text(encoding="utf-8-sig", errors="strict") if path.is_file() else ""


def main() -> int:
    failures: list[str] = []
    lock_path = INSTALLERS / "runtime-source-lock.json"
    inventory_path = HERE / "runtime-license-inventory.json"
    notices_path = HERE / "customer-third-party-notices.json"
    capture_notices_path = HERE / "legal" / "capture-python-runtime-notices.py"
    muse_requirements_path = INSTALLERS / "musetalk-windows-requirements.txt"
    migration_script_path = INSTALLERS / "migrate-runtime-storage.ps1"

    for path in (lock_path, inventory_path, notices_path, capture_notices_path, muse_requirements_path, migration_script_path):
        require(path.is_file(), f"missing runtime governance file: {path.name}", failures)
    if failures:
        print(json.dumps({"status": "failed", "failures": failures}, ensure_ascii=False, indent=2))
        return 2

    lock = load_json(lock_path)
    inventory = load_json(inventory_path)
    notices = load_json(notices_path)

    require(lock.get("schema") == "bossai.video-agent-runtime-source-lock.v1", "invalid runtime source-lock schema", failures)
    require(inventory.get("schema") == "bossai.video-agent-runtime-license-inventory.v1", "invalid runtime license inventory schema", failures)
    require(notices.get("schema") == "bossai.video-agent-third-party-notices.v1", "invalid customer notice metadata schema", failures)

    components = lock.get("components") or {}
    for component in ("python310", "qwen2.5-7b-instruct", "cosyvoice2-0.5b", "musetalk"):
        require(isinstance(components.get(component), dict), f"source lock missing component: {component}", failures)

    py = components.get("python310") or {}
    require(bool(py.get("release")) and bool(py.get("version")) and bool(py.get("artifact")) and bool(py.get("url")), "python310 source lock is incomplete", failures)
    require(bool(HEX64.fullmatch(str(py.get("sha256") or ""))), "python310 archive SHA-256 is missing/invalid", failures)

    qwen = components.get("qwen2.5-7b-instruct") or {}
    require(bool(qwen.get("repository")), "Qwen repository is not pinned", failures)
    require(bool(HEX40.fullmatch(str(qwen.get("revision") or ""))), "Qwen revision must be an immutable 40-char commit", failures)
    qwen_files = qwen.get("files") or []
    require(len(qwen_files) == 2 and all(str((item or {}).get("name") or "").lower().endswith(".gguf") for item in qwen_files if isinstance(item, dict)), "Qwen split GGUF file set is invalid", failures)
    for item in qwen_files:
        require(isinstance(item, dict) and bool(HEX64.fullmatch(str(item.get("sha256") or ""))), "Qwen GGUF SHA-256 is missing/invalid", failures)
    qwen_runtime = qwen.get("inferenceRuntime") or {}
    require(qwen_runtime.get("project") == "ggml-org/llama.cpp", "Qwen inference runtime must be pinned llama.cpp", failures)
    require(bool(qwen_runtime.get("release")) and bool(qwen_runtime.get("artifact")) and bool(qwen_runtime.get("url")), "Qwen llama.cpp runtime source lock is incomplete", failures)
    require(bool(HEX64.fullmatch(str(qwen_runtime.get("sha256") or ""))), "Qwen llama.cpp archive SHA-256 is missing/invalid", failures)

    cosy = components.get("cosyvoice2-0.5b") or {}
    require(str(cosy.get("sourceRepository") or "").startswith("https://"), "CosyVoice source repository missing", failures)
    require(bool(HEX40.fullmatch(str(cosy.get("sourceRevision") or ""))), "CosyVoice source revision must be immutable", failures)
    require(bool(cosy.get("modelRepository")), "CosyVoice model repository missing", failures)
    require(bool(HEX40.fullmatch(str(cosy.get("modelRevision") or ""))), "CosyVoice model revision must be immutable", failures)
    cosy_hashes = cosy.get("verifiedHashes") or {}
    required_cosy_files = {
        "campplus.onnx", "cosyvoice2.yaml", "flow.pt", "hift.pt", "llm.pt", "speech_tokenizer_v2.onnx",
        "CosyVoice-BlankEN/config.json", "CosyVoice-BlankEN/generation_config.json", "CosyVoice-BlankEN/merges.txt",
        "CosyVoice-BlankEN/model.safetensors", "CosyVoice-BlankEN/tokenizer_config.json", "CosyVoice-BlankEN/vocab.json",
    }
    require(required_cosy_files.issubset(set(cosy_hashes)), "CosyVoice verified model/tokenizer hash set is incomplete", failures)
    for name, digest in cosy_hashes.items():
        require(bool(HEX64.fullmatch(str(digest))), f"CosyVoice model SHA-256 is invalid: {name}", failures)
    cosy_supplements = cosy.get("supplementalPythonLicenses") or []
    require(len(cosy_supplements) >= 4, "CosyVoice supplemental Python license lock is incomplete", failures)
    for item in cosy_supplements:
        require(isinstance(item, dict) and bool(item.get("package")) and bool(item.get("version")), "CosyVoice supplemental license package/version is missing", failures)
        require(str((item or {}).get("url") or "").startswith("https://"), f"CosyVoice supplemental license URL is not pinned: {(item or {}).get('package')}", failures)
        require(bool(HEX64.fullmatch(str((item or {}).get("sha256") or ""))), f"CosyVoice supplemental license SHA-256 is invalid: {(item or {}).get('package')}", failures)
    cosy_torch = cosy.get("torchRuntime") or {}
    require(cosy_torch.get("version") == "2.3.1" and cosy_torch.get("torchaudioVersion") == "2.3.1", "CosyVoice Torch runtime versions are not pinned", failures)
    torch_profiles = cosy_torch.get("profiles") or {}
    for profile in ("cu118", "cpu"):
        item = torch_profiles.get(profile) or {}
        require(str(item.get("torchUrl") or "").startswith("https://download-r2.pytorch.org/"), f"CosyVoice {profile} torch wheel URL is not pinned", failures)
        require(bool(HEX64.fullmatch(str(item.get("torchSha256") or ""))), f"CosyVoice {profile} torch wheel SHA-256 is invalid", failures)
        require(str(item.get("torchaudioUrl") or "").startswith("https://download-r2.pytorch.org/"), f"CosyVoice {profile} torchaudio wheel URL is not pinned", failures)
        require(bool(HEX64.fullmatch(str(item.get("torchaudioSha256") or ""))), f"CosyVoice {profile} torchaudio wheel SHA-256 is invalid", failures)

    muse = components.get("musetalk") or {}
    require(str(muse.get("sourceRepository") or "").startswith("https://"), "MuseTalk source repository missing", failures)
    require(bool(HEX40.fullmatch(str(muse.get("sourceRevision") or ""))), "MuseTalk source revision must be immutable", failures)
    require(bool(muse.get("modelRepository")), "MuseTalk model repository missing", failures)
    require(bool(HEX40.fullmatch(str(muse.get("modelRevision") or ""))), "MuseTalk model revision must be immutable", failures)
    dependency_revisions = muse.get("dependencyModelRevisions") or {}
    require(len(dependency_revisions) >= 5, "MuseTalk dependency revisions are incomplete", failures)
    for name, revision in dependency_revisions.items():
        require(bool(HEX40.fullmatch(str(revision))), f"MuseTalk dependency revision is not immutable: {name}", failures)
    verified_hashes = muse.get("verifiedHashes") or {}
    require(len(verified_hashes) >= 8, "MuseTalk verified model hash set is incomplete", failures)
    for name, digest in verified_hashes.items():
        require(bool(HEX64.fullmatch(str(digest))), f"MuseTalk model SHA-256 is invalid: {name}", failures)
    require(muse.get("sourceLicense") == "MIT", "MuseTalk source license must be recorded separately as MIT", failures)
    require(muse.get("trainedModelDeclaredLicense") == "creativeml-openrail-m", "MuseTalk trained-model license declaration must be CreativeML OpenRAIL-M", failures)
    model_license_evidence = muse.get("modelLicenseEvidence") or []
    require(len(model_license_evidence) >= 6, "MuseTalk model/dependency license evidence is incomplete", failures)
    for item in model_license_evidence:
        require(isinstance(item, dict) and bool(item.get("id")) and bool(item.get("repository")) and bool(item.get("declaredLicense")), "MuseTalk model license identity is incomplete", failures)
        require(bool(HEX40.fullmatch(str((item or {}).get("revision") or ""))), f"MuseTalk model license revision is not immutable: {(item or {}).get('id')}", failures)
        require(str((item or {}).get("url") or "").startswith("https://"), f"MuseTalk model license URL is not pinned: {(item or {}).get('id')}", failures)
        require(bool(HEX64.fullmatch(str((item or {}).get("sha256") or ""))), f"MuseTalk model license SHA-256 is invalid: {(item or {}).get('id')}", failures)
        require(bool((item or {}).get("filename")), f"MuseTalk model license output filename is missing: {(item or {}).get('id')}", failures)
    muse_requirements = muse_requirements_path.read_text(encoding="utf-8-sig").lower()
    for required_package in ("diffusers==", "numpy==", "opencv-python==", "soundfile==", "transformers==", "librosa==", "einops==", "omegaconf=="):
        require(required_package in muse_requirements, f"MuseTalk Windows inference requirements missing: {required_package}", failures)
    for forbidden_package in ("tensorflow==", "tensorboard==", "gradio==", "gdown==", "moviepy=="):
        require(forbidden_package not in muse_requirements, f"MuseTalk customer runtime must not include training/demo dependency: {forbidden_package}", failures)
    implicit_artifacts = muse.get("implicitRuntimeArtifacts") or {}
    for artifact_name in ("s3fdFaceDetector", "dwposeBackbone"):
        artifact = implicit_artifacts.get(artifact_name) or {}
        require(str(artifact.get("url") or "").startswith("https://"), f"MuseTalk hidden runtime artifact URL is not pinned: {artifact_name}", failures)
        require(bool(HEX64.fullmatch(str(artifact.get("sha256") or ""))), f"MuseTalk hidden runtime artifact SHA-256 is invalid: {artifact_name}", failures)
        require(bool(artifact.get("destination")), f"MuseTalk hidden runtime artifact destination missing: {artifact_name}", failures)
    xet_runtime = muse.get("huggingFaceXetRuntime") or {}
    require(xet_runtime.get("version") == "1.1.7", "MuseTalk Hugging Face Xet runtime version is not pinned", failures)
    require(xet_runtime.get("license") == "Apache-2.0", "MuseTalk Hugging Face Xet runtime license is not Apache-2.0", failures)
    require(str(xet_runtime.get("url") or "").startswith("https://files.pythonhosted.org/"), "MuseTalk Hugging Face Xet wheel URL is not pinned to PyPI", failures)
    require(bool(HEX64.fullmatch(str(xet_runtime.get("sha256") or ""))), "MuseTalk Hugging Face Xet wheel SHA-256 is invalid", failures)
    require(str(xet_runtime.get("filename") or "").endswith("win_amd64.whl"), "MuseTalk Hugging Face Xet wheel must target Windows x64", failures)
    openmmlab = muse.get("openMmlabRuntime") or {}
    require(openmmlab.get("mmengineVersion") == "0.10.7", "MuseTalk mmengine version is not pinned", failures)
    require(openmmlab.get("mmcvVersion") == "2.0.1", "MuseTalk mmcv version is not pinned", failures)
    require(openmmlab.get("mmdetVersion") == "3.1.0", "MuseTalk mmdet version is not pinned", failures)
    require(openmmlab.get("mmposeVersion") == "1.1.0", "MuseTalk mmpose version is not pinned", failures)
    mmcv_wheel = openmmlab.get("mmcvWheel") or {}
    require(str(mmcv_wheel.get("url") or "").startswith("https://download.openmmlab.com/"), "MuseTalk MMCV Windows wheel URL is not pinned to OpenMMLab", failures)
    require(bool(HEX64.fullmatch(str(mmcv_wheel.get("sha256") or ""))), "MuseTalk MMCV Windows wheel SHA-256 is invalid", failures)
    require(str(mmcv_wheel.get("filename") or "").endswith("win_amd64.whl"), "MuseTalk MMCV wheel must target Windows x64", failures)
    pinned_python_wheels = muse.get("pinnedPythonWheels") or {}
    for wheel_name in ("llvmlite", "scipy", "scikitLearn"):
        wheel = pinned_python_wheels.get(wheel_name) or {}
        require(bool(wheel.get("version")), f"MuseTalk pinned Python wheel version missing: {wheel_name}", failures)
        require(str(wheel.get("url") or "").startswith("https://files.pythonhosted.org/"), f"MuseTalk pinned Python wheel URL is not an immutable PyPI artifact: {wheel_name}", failures)
        require(bool(HEX64.fullmatch(str(wheel.get("sha256") or ""))), f"MuseTalk pinned Python wheel SHA-256 is invalid: {wheel_name}", failures)
        require(str(wheel.get("filename") or "").endswith("win_amd64.whl"), f"MuseTalk pinned Python wheel must target Windows x64: {wheel_name}", failures)
    muse_supplements = muse.get("supplementalPythonLicenses") or []
    expected_muse_supplements = {
        ("antlr4-python3-runtime", "4.9.3"),
        ("chumpy", "0.70"),
        ("Cython", "3.3.0"),
        ("pycocotools", "2.0.11"),
        ("tokenizers", "0.15.2"),
    }
    actual_muse_supplements = {(str(item.get("package") or ""), str(item.get("version") or "")) for item in muse_supplements if isinstance(item, dict)}
    require(expected_muse_supplements.issubset(actual_muse_supplements), "MuseTalk supplemental Python license lock is incomplete", failures)
    for item in muse_supplements:
        require(isinstance(item, dict) and bool(item.get("package")) and bool(item.get("version")), "MuseTalk supplemental license package/version is missing", failures)
        require(str((item or {}).get("url") or "").startswith("https://"), f"MuseTalk supplemental license URL is not pinned: {(item or {}).get('package')}", failures)
        require(bool(HEX64.fullmatch(str((item or {}).get("sha256") or ""))), f"MuseTalk supplemental license SHA-256 is invalid: {(item or {}).get('package')}", failures)
        if (item or {}).get("releaseArtifactUrl"):
            require(str((item or {}).get("releaseArtifactUrl") or "").startswith("https://files.pythonhosted.org/"), f"MuseTalk supplemental release artifact URL is not pinned to PyPI: {(item or {}).get('package')}", failures)
            require(bool(HEX64.fullmatch(str((item or {}).get("releaseArtifactSha256") or ""))), f"MuseTalk supplemental release artifact SHA-256 is invalid: {(item or {}).get('package')}", failures)
    muse_torch = muse.get("torchRuntime") or {}
    require(muse_torch.get("profile") == "cu118", "MuseTalk Torch profile must be pinned to cu118", failures)
    for wheel_name in ("torch", "torchvision", "torchaudio"):
        wheel = muse_torch.get(wheel_name) or {}
        require(str(wheel.get("url") or "").startswith("https://download-r2.pytorch.org/"), f"MuseTalk {wheel_name} wheel URL is not pinned", failures)
        require(bool(HEX64.fullmatch(str(wheel.get("sha256") or ""))), f"MuseTalk {wheel_name} wheel SHA-256 is invalid", failures)
    ffmpeg = muse.get("ffmpegRuntime") or {}
    require(ffmpeg.get("distributionMode") == "external-user-installed-not-bundled", "MuseTalk FFmpeg must remain an external runtime", failures)
    require(ffmpeg.get("bossaiMayBundle") is False, "BossAI must not bundle the pinned GPL FFmpeg runtime", failures)
    require(ffmpeg.get("license") == "GPL-3.0", "MuseTalk FFmpeg license profile must be explicit GPL-3.0", failures)
    require(bool(HEX64.fullmatch(str(ffmpeg.get("installerSha256") or ""))), "MuseTalk FFmpeg installer SHA-256 is invalid", failures)
    require(bool(HEX64.fullmatch(str(ffmpeg.get("expectedExecutableSha256") or ""))), "MuseTalk FFmpeg executable SHA-256 is invalid", failures)
    require(bool(HEX64.fullmatch(str(ffmpeg.get("licenseFileSha256") or ""))), "MuseTalk FFmpeg license SHA-256 is invalid", failures)

    script_requirements = {
        "install-python310.ps1": ("AcceptLicense", "Get-FileHash", "runtime.json", "BOSSAI_DONE"),
        "install-qwen.ps1": ("AcceptLicense", "runtime-source-lock.json", "Verify-Hash", "llama-server.exe", "Qwen-LICENSE.txt", "llama.cpp-LICENSE.txt", "licenseEvidence", "runtime.json", "Commit-Install", ".installing-", "BOSSAI_DONE"),
        "install-cosyvoice2.ps1": ("AcceptLicense", "runtime-source-lock.json", "sourceRevision", "modelRevision", "Download-Verified", "ResumeStagingDir", "BossAIVideoAgent-CosyVoice2-Install", "supplementalPythonLicenses", "--require-complete", "torchSha256", "torchaudioSha256", "licenses", "capture-python-runtime-notices.py", "licenseEvidence", "runtime.json", "Commit-Install", ".installing-", "BOSSAI_DONE"),
        "install-musetalk.ps1": ("AcceptLicense", "runtime-source-lock.json", "musetalk-windows-requirements.txt", "sourceRevision", "modelRevision", "modelLicenseEvidence", "supplementalPythonLicenses", "python-license-supplements.json", "--supplemental-license-manifest", "implicitRuntimeArtifacts", "TORCH_HOME", "s3fdFaceDetector", "dwposeBackbone", "sparse-checkout", "upstream demo/test/training media", "musetalk-model-cache", "DownloadVerified", "ResumeStagingDir", "BossAIVideoAgent-MuseTalk-Install", "bossaiMayBundle", "expectedExecutableSha256", "VerifyHash", "licenses", "capture-python-runtime-notices.py", "licenseEvidence", "runtime.json", "Commit-Install", ".installing-", "BOSSAI_DONE"),
    }
    migration_text = migration_script_path.read_text(encoding="utf-8-sig", errors="strict")
    for marker in ("runtime-storage.json", "RemoveSourceAfterVerify", "verify-installed-runtime-notices.py", ".installing-", "robocopy.exe"):
        require(marker in migration_text, f"runtime storage migration safety marker missing: {marker}", failures)

    scripts: dict[str, str] = {}
    for name, markers in script_requirements.items():
        text = installer_text(name, failures)
        scripts[name] = text
        for marker in markers:
            require(marker in text, f"{name} missing fail-closed provisioning marker: {marker}", failures)

    default_stack = inventory.get("commercialDefaultStack") or {}
    require(default_stack.get("llm") == "qwen2.5-7b-instruct", "commercial default LLM is not Qwen pinned stack", failures)
    require(default_stack.get("tts") == "cosyvoice2-0.5b", "commercial default TTS is not CosyVoice2 pinned stack", failures)
    require(default_stack.get("digitalHuman") == "musetalk", "commercial default digital-human stack is not MuseTalk", failures)

    notice_ids = {str(item.get("id") or "") for item in notices.get("components") or []}
    for component in ("python310", "qwen2.5-7b-instruct", "cosyvoice2-0.5b", "musetalk"):
        require(component in notice_ids, f"customer notice metadata missing component: {component}", failures)

    forbidden_literal_markers = tuple(
        "".join(chr(value) for value in codepoints)
        for codepoints in (
            (0x5CB3, 0x54E5),
            (0x41, 0x49, 0x41, 0x67, 0x65, 0x6E, 0x74),
            (0x41, 0x49, 0x667A, 0x80FD, 0x4F53),
            (0x41, 0x49, 0x2D, 0x41, 0x67, 0x65, 0x6E, 0x74, 0x2D, 0x54),
        )
    )
    for name, text in scripts.items():
        for marker in forbidden_literal_markers:
            require(marker not in text, f"{name} contains legacy identity marker", failures)

    report = {
        "schema": "bossai.video-agent-runtime-provisioning-evidence.v1",
        "productId": "bossai-video-agent",
        "strategy": "customer-side-pinned-official-download",
        "passed": not failures,
        "networkDownloadPerformed": False,
        "modelWeightsBundled": False,
        "licenseAcceptanceRequired": True,
        "pythonDependencyNoticeCaptureRequired": True,
        "sourceLockValidated": True if not failures else False,
        "installerCount": len(script_requirements),
        "requiredComponents": ["python310", "qwen2.5-7b-instruct", "cosyvoice2-0.5b", "musetalk"],
        "failures": failures,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failures:
        print("RESULT: BossAI runtime provisioning contract FAILED CLOSED.")
        return 2
    print("RESULT: BossAI runtime provisioning contract passed without bundling legacy runtimes or model weights.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
