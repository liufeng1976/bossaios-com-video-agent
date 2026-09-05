# BossAI Video Agent GA UAT Runbook

This runbook only closes real GA evidence. It must not be used to manufacture PASS states.

## 0. Readiness preflight (run this first)

Before collecting rights-cleared media or arranging a real Business account, find out
whether either UAT can be attempted at all:

```text
python uat-preflight.py
```

It renders nothing, authenticates nothing, writes no evidence and changes no gate. It
reports, per track, exactly what is blocking — an unresolved runtime root, a MuseTalk
installation that would fall back to upstream demo assets, a missing ffprobe (which would
make the render succeed but the UAT fail closed), an unreachable account service, or the
absence of an authenticated session. Exit 0 means every checked track is ready to attempt.

Check a single track with `--track musetalk` or `--track entitlement`.

## 1. Live BossAI Business entitlement UAT

Prerequisites:

- BossAI account service is reachable.
- A real customer test account is authenticated on the machine.
- The account/device has a real active Business entitlement for `bossai-video-agent`.

Run from `commercial-product`:

```text
python live-entitlement-uat.py --out ..\Atlas\EVIDENCE-commercial-live-entitlement-YYYYMMDD.json
```

PASS requires all of the following from the live authority response:

- evidence schema `bossai.video-agent-live-entitlement-evidence.v1`
- entitlement schema `bossai.commercial-entitlement.v1`
- authority `bossai-headquarters-commerce`
- `licenseActive=true`
- `paidExecutionAllowed=true`
- `businessUseAllowed=true`

The evidence runner never records passwords, verification codes, access/refresh tokens, provider keys, or customer content.

Do not set `bossaiLiveEntitlementUatPassed=true` until the generated evidence is reviewed and passes.

## 2. MuseTalk authorized-media commercial render UAT

Prerequisites:

- Use only media that is either customer-authorized or BossAI-owned.
- Do not use recovered/demo/unknown-rights people, voices, music, or videos.
- Installed MuseTalk runtime must already pass the installed-runtime verifier.

Example for customer-authorized media:

```text
python musetalk-live-uat.py ^
  --video "C:\path\authorized-avatar.mp4" ^
  --audio "C:\path\authorized-audio.wav" ^
  --authorization-basis customer-authorized ^
  --rights-affirmed ^
  --out ..\Atlas\EVIDENCE-commercial-musetalk-uat-YYYYMMDD.json
```

For BossAI-owned media use:

```text
--authorization-basis bossai-owned
```

The command fails before rendering unless `--rights-affirmed` is explicitly supplied. The evidence does not persist input file paths or customer content. It records input SHA-256/byte counts, runtime readiness, output SHA-256/size, and ffprobe validation.

PASS requires:

- evidence schema `bossai.video-agent-musetalk-commercial-uat.v1`
- `ready=true`
- `renderAttempted=true`
- `authorizedMediaUsed=true`
- a valid non-empty MP4 containing a video stream

Do not set `musetalkCommercialRenderUatPassed=true` until the evidence is reviewed and passes.

## 3. Windows Authenticode

GA requires the exact customer application and NSIS installer to have valid trusted Authenticode signatures and trusted timestamp evidence. Internal Pilot currently permits unsigned artifacts; GA does not.

### Producing a signed build

`build-desktop.ps1 -EnableCodeSigning` refuses to run unless the certificate is supplied,
so an unsigned artifact can never be mistaken for a signed one. Point it at the real
certificate through the environment, then build:

```text
$env:WIN_CSC_LINK = "<path to the .pfx, or its base64 form>"
$env:CSC_KEY_PASSWORD = "<certificate password>"
powershell -ExecutionPolicy Bypass -File build-desktop.ps1 -Mode dist -EnableCodeSigning
```

Never commit the certificate, its password, or its base64 form. Supply them from the
machine environment or a secret store for the duration of the build only.

The build runs `verify-windows-signing.ps1` itself and throws if Authenticode verification
fails, so a signed build cannot complete while producing an unverifiable artifact. Run the
verifier standalone when checking an artifact that was signed separately:

```text
powershell -ExecutionPolicy Bypass -File verify-windows-signing.ps1 ^
  -ApplicationExe "desktop\dist\win-unpacked\BossAI Video Agent.exe" ^
  -InstallerExe "desktop\dist\BossAI-Video-Agent-0.1.0-Setup.exe"
```

Do not mark `windowsCodeSigningValidated=true` if either artifact remains `NotSigned` or signature validation fails.

## 4. Customer legal approval

Use:

```text
python legal\legal-release-preflight.py --config legal\legal-config.json
```

Only after all required legal/business fields are completed by an authorized human reviewer and `approved=true`, generate the release bundle with `legal/generate-customer-legal.py`.

Do not invent legal entity, address, approval identity/date, governing law, venue, refund policy, support contacts, retention policy, or cloud-processing regions.

## 5. Final GA gate

After the four evidence tracks above are genuinely complete:

```text
python release-gate.py --staging-root desktop\dist\win-unpacked
```

Expected only then:

```text
passed=true
failedChecks=[]
```

Until then, `distributionReady` must remain false and the GA gate must remain fail-closed.
