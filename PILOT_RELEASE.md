# BossAI Video Agent 0.1.0 Internal Pilot

Status: **INTERNAL PILOT READY — NOT GA / NOT PUBLIC COMMERCIAL RELEASE**

## Pilot artifact

- Installer: `BossAI-Video-Agent-0.1.0-Setup.exe`
- SHA-256: `9ee207a7c3a7cfe71354f09f5aad26010187897477f3e796a2adcf45c72c2b36`
- Authenticode: `NotSigned`
- Expected Windows behavior: SmartScreen or other security warnings may appear because the Pilot build is unsigned.

## Validated for Pilot

- Real NSIS install → launch → shutdown → uninstall smoke passed.
- Free Personal local mode works without BossAI sign-in after license acceptance.
- Personal Pro / Business / Gateway commercial paths remain fail-closed without verified BossAI authority.
- Qwen, CosyVoice2 and MuseTalk runtimes are installed from pinned sources/revisions/hashes.
- Runtime model hashes and LICENSE/NOTICE coverage pass exact-machine verification.
- MuseTalk CUDA runtime passes on the validated NVIDIA RTX 4060 Laptop GPU machine.
- Large runtime/model/download storage is persisted under `D:\BossAI-Models\VideoAgent` on the validated machine.
- Customer package boundary scan reports zero forbidden legacy/model-weight/credential violations.
- Real publishing remains disabled.

## Pilot limitations

This build must not be described as a GA, signed, or fully commercial-authorized release. The following GA gates remain fail-closed:

1. Live BossAI Business entitlement UAT on a real authenticated customer account/device.
2. End-to-end MuseTalk commercial render UAT using customer-authorized or BossAI-owned media.
3. Trusted Windows Authenticode signing for both application and installer.
4. Final approved customer legal release bundle.

## Verification

Run `VERIFY_PILOT.ps1` next to the installer, or compare the installer SHA-256 with `PILOT_SHA256SUMS.txt` before installation.

For development/release engineering, run:

```text
python commercial-product/pilot-release-gate.py
```

A passing Internal Pilot gate is intentionally separate from `commercial-product/release-gate.py`; the latter must remain fail-closed until all GA requirements are satisfied.
