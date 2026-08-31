# Third-party notices and redistribution boundary

This repository distributes no third-party model weights, model caches, packaged browser/runtime binaries, demo media, or recovered upstream artifacts. The dependency declarations and customer-side installers are source-only. Anyone downloading or packaging a component is responsible for reviewing the exact upstream version, all license texts, export/privacy obligations, and the rights for any voice, avatar, music, font, or input media.

## Components referenced by the source

| Component | Public-source treatment | Operator obligation |
| --- | --- | --- |
| Qwen2.5-7B-Instruct | No weights distributed. The installer pins an official source. | Preserve Apache-2.0 notices for any copy you distribute. |
| CosyVoice2 | No code or weights vendored. | Obtain from the official pinned source and retain the applicable Apache-2.0 notices; use only authorized reference voices. |
| MuseTalk | No code, weights, or test/demo media vendored. | Obtain from the official pinned source, retain MIT notices, and never ship upstream test people, voices, or media as production assets. |
| IndexTTS | Not included and not installed by the public release. | Treat the model and published model code as governed by the Bilibili Model Use License Agreement; do not redistribute unless all downstream, notice, threshold, and voice-right requirements are met. |
| FFmpeg, Electron/Chromium, CUDA, Python, npm/PyPI packages | Not bundled by this source release. | Determine the exact build/package license and notices before redistribution; FFmpeg and NVIDIA components require build/EULA-specific review. |

The release metadata in `commercial-product/runtime-license-inventory.json` and `commercial-product/customer-third-party-notices.json` is an implementation aid, not a substitute for the license texts that must accompany a future binary distribution.

## Non-negotiable exclusions

- No proprietary or unknown-license legacy code/binaries.
- No model checkpoint, quantization, conversion, cache, or weight without a documented grant.
- No API keys, account credentials, activation data, cookies, tokens, device identifiers, customer media, or generated outputs.
- No default voice, avatar, music, font, or other media unless it is BossAI-owned or its redistribution rights are documented.
