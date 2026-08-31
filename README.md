# AIAgent Recovered — safe public source scope

This repository publishes the BossAI-owned commercial-product source layer from a local recovery workspace. It is deliberately a **source-only, safety-scoped release**, not a release of the original recovered application.

The published code provides a Windows-oriented local video-production prototype with a Vue/Electron desktop shell, FastAPI backend, BossAI OS commercial-entitlement bridge, and installers that obtain optional runtimes from their official pinned sources.

## Public scope

- `commercial-product/backend/`: source for the local API and runtime adapters.
- `commercial-product/ui/` and `commercial-product/desktop/`: editable UI and Electron shell source.
- `commercial-product/runtime-installers/`: pinned, customer-side runtime installers.
- Product contracts, release-boundary checks, and third-party metadata.

## Explicit exclusions

The local workspace retains, but this repository does **not** publish:

- recovered or original upstream application code, executables, packaged renderers, forensic notes, or compatibility baselines;
- model weights, checkpoints, caches, CUDA/Chromium/FFmpeg binaries, installers, and build output;
- activation/device data, cookies, browser profiles, API keys, tokens, customer media, generated media, or local databases;
- upstream demo voices, avatars, music, fonts, and any other asset whose redistribution right is not documented.

Those exclusions are enforced by `.gitignore` and verified before the first public commit. They are preserved locally and are not deleted or overwritten by this publication preparation.

## Licensing and model policy

`LICENSE` applies only to the BossAI-owned files included in this repository. It does not grant rights to excluded artifacts or to any third-party software, model, media, name, or trademark.

No model weights are committed. Installers download only from the pinned sources in `commercial-product/runtime-installers/runtime-source-lock.json` after the operator reviews the applicable upstream terms. `THIRD_PARTY_NOTICES.md` explains the boundaries, including the special restrictions for IndexTTS. Do not add a weight, binary, voice, avatar, music, or font without a documented redistribution review.

## Local development

Requirements: Windows, Python 3.10+ and Node.js 20+.

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r .\commercial-product\backend\requirements.txt
python .\commercial-product\backend\feature-entitlement-smoke-test.py

Push-Location .\commercial-product\ui
npm install
npm run build
Pop-Location
```

For a configured development server, set only local paths in `.env`; never commit that file. The backend defaults to refusing paid execution until it receives a valid BossAI OS entitlement. The optional model integrations also require a separately installed runtime and explicit rights to the reference voice and avatar media.

## Safety checks

```powershell
python .\commercial-product\verify-runtime-provisioning.py
python .\commercial-product\release-gate.py
python .\commercial-product\backend\feature-entitlement-smoke-test.py
```

These checks are engineering evidence only. This public source release is claimed at **completion level 1 (technical publication baseline)**; it is not a production product release or a claim of real-user validation.

## Contributing

Contributions must keep the public/recovery boundary intact. Do not submit secrets, personal data, generated content, model weights, vendored binaries, or code copied from a proprietary/unknown-license package.
