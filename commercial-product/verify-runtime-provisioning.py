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

    for path in (lock_path, inventory_path, notices_path, capture_notices_path):
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
    require(len(qwen_files) == 2 and all(str(item).lower().endswith(".gguf") for item in qwen_files), "Qwen split GGUF file set is invalid", failures)

    cosy = components.get("cosyvoice2-0.5b") or {}
    require(str(cosy.get("sourceRepository") or "").startswith("https://"), "CosyVoice source repository missing", failures)
    require(bool(HEX40.fullmatch(str(cosy.get("sourceRevision") or ""))), "CosyVoice source revision must be immutable", failures)
    require(bool(cosy.get("modelRepository")), "CosyVoice model repository missing", failures)
    require(bool(HEX40.fullmatch(str(cosy.get("modelRevision") or ""))), "CosyVoice model revision must be immutable", failures)

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

    script_requirements = {
        "install-python310.ps1": ("AcceptLicense", "Get-FileHash", "runtime.json", "BOSSAI_DONE"),
        "install-qwen.ps1": ("AcceptLicense", "runtime-source-lock.json", "--revision", "LICENSE", "capture-python-runtime-notices.py", "licenseEvidence", "runtime.json", "Commit-Install", ".installing-", "BOSSAI_DONE"),
        "install-cosyvoice2.ps1": ("AcceptLicense", "runtime-source-lock.json", "sourceRevision", "modelRevision", "licenses", "capture-python-runtime-notices.py", "licenseEvidence", "runtime.json", "Commit-Install", ".installing-", "BOSSAI_DONE"),
        "install-musetalk.ps1": ("AcceptLicense", "runtime-source-lock.json", "sourceRevision", "modelRevision", "VerifyHash", "licenses", "capture-python-runtime-notices.py", "licenseEvidence", "runtime.json", "Commit-Install", ".installing-", "BOSSAI_DONE"),
    }
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
