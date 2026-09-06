# BossAI Video Agent

> **Free local-first Windows AI video workflow for personal and non-commercial use.**  
> **个人/非商业免费 · Windows 本地优先 AI 视频工作流。**

[![GitHub stars](https://img.shields.io/github/stars/liufeng1976/bossaios-com-video-agent?style=social)](https://github.com/liufeng1976/bossaios-com-video-agent/stargazers)
[![Windows](https://img.shields.io/badge/platform-Windows-blue)](https://github.com/liufeng1976/bossaios-com-video-agent/releases)
[![BossAI](https://img.shields.io/badge/BossAI-bossaios.com-black)](https://bossaios.com)
[![License](https://img.shields.io/badge/license-BossAI%20Community%20Source-orange)](LICENSE)

**License classification / 许可分类: Source Available, not OSI Open Source / 源码公开，不是 OSI 开源。** Personal, educational, evaluation, research and other non-commercial use is free under the BossAI Community Source License; commercial use requires BossAI authorization. Historical MIT-licensed revisions keep the rights already granted with those revisions.

**当前许可分类：Source Available / 源码公开，不是 OSI Open Source。** 个人、教育、评估、研究及其他非商业用途免费；商业用途需要 BossAI 授权。历史上已经按 MIT 发布的 revision，其既有 MIT 权利继续有效。

**Script → voice → talking avatar → subtitles / music / picture-in-picture → cover → final export, in one desktop workflow.**

**文案 → 配音 → 数字人口播 → 字幕 / 音乐 / 画中画 → 封面 → 成片导出，一条桌面工作流完成。**

## Download for Windows / Windows 免费试用

**Current public evaluation build:** `v0.1.0-pilot`

- [Download from GitHub Releases](https://github.com/liufeng1976/bossaios-com-video-agent/releases/tag/v0.1.0-pilot)
- Website: https://bossaios.com
- Verify the installer with the published SHA-256 before running it.

当前可公开下载的是 **内部 Pilot / 评估版**。请只从 GitHub Releases 下载，并在运行前核对发布页 SHA-256。

> **Pilot notice:** the current Windows installer is unsigned and is not approved for commercial production, client delivery, or paid services. Personal/non-commercial evaluation is free under the BossAI Community Source License. Commercial use requires BossAI authorization.
>
> **Pilot 提示：** 当前 Windows 安装包尚未签名，不得用于商业生产、客户交付或收费服务。个人/非商业评估免费；商业用途必须获得 BossAI 授权。

If the project is useful, please **Star** the repository. It directly helps more creators and developers discover the project.

如果它对你有帮助，欢迎点一个 **Star**，这会直接帮助更多创作者和开发者发现项目。

## What you can do / 能做什么

- **Local script generation & rewrite / 本地文案生成与改写** — Qwen
- **Local voice generation / 本地配音** — CosyVoice2
- **Local talking-avatar video / 本地数字人口播** — MuseTalk
- **Optional local transcription / 可选本地转写** — Whisper
- **Subtitles, audio mix, PIP, cover and export / 字幕、混音、画中画、封面与导出** — FFmpeg
- **Local-first by default / 默认本地优先** — core Free Personal workflow does not require a cloud model after the required runtimes are installed

BossAI Agent turns script creation, voice, digital-human video, editing, cover generation and export into one Windows workflow. This GitHub repository is the public source and release repository for BossAI-owned implementation. Personal and non-commercial use is free under the BossAI Community Source License; commercial use requires BossAI commercial authorization.

BossAI Agent 将文案、配音、数字人口播、视频剪辑、封面与导出整合为一条 Windows 工作流。本 GitHub 仓库同时承担 BossAI 自有实现的公开源码与发行职责。个人及非商业用途按 BossAI Community Source License 免费使用；商业用途必须取得 BossAI 商业授权。

## First run in 30 seconds / 30 秒开始

```text
GitHub Releases
→ download installer
→ verify SHA-256
→ install BossAI Agent
→ choose 简体中文 / English
→ enter Local Free Personal without signing in
→ install required local runtimes as needed
→ create the first video locally
```

Free Personal local core features do **not** require a BossAI account. Sign in only when you need Personal Pro, BossAI Gateway, cross-device features, or Business management.

Free Personal 本地核心能力**无需 BossAI 账号**。只有需要 Personal Pro、BossAI Gateway、跨设备能力或 Business 管理时才登录。

## Current release status / 当前发布状态

`0.1.0` is **Internal Pilot Ready**. Local Windows build, packaged first-run, real NSIS install/start/exit/uninstall, Free Personal/commercial fail-closed behavior, Qwen/CosyVoice2/MuseTalk installed runtimes, runtime SHA/NOTICE verification, D-drive runtime storage, and MuseTalk CUDA runtime checks have passed.

It is **not approved for GA/public commercial release** until live BossAI Business entitlement UAT, an authorized-media MuseTalk commercial render UAT, final customer legal approval, and trusted Authenticode signing are complete. The current installer is unsigned and must be treated as Internal Pilot only.

`0.1.0` 已达到 **Internal Pilot Ready / 内部 Pilot 可用**：本地 Windows 构建、打包首启、真实 NSIS 安装/启动/退出/卸载、Free Personal/商业 fail-closed、Qwen/CosyVoice2/MuseTalk 已安装 runtime、模型 SHA/NOTICE、D 盘 runtime 存储与 MuseTalk CUDA runtime 均已通过。

当前仍**不得作为 GA/公开商业正式版发布**，剩余门槛为真实 BossAI Business entitlement UAT、使用授权媒体的 MuseTalk 商业 render UAT、最终客户法律批准和可信 Authenticode 签名。当前安装包未签名，仅限 Internal Pilot。

## Plans / 套餐

| Plan | 中文 | English |
| --- | --- | --- |
| **Free Personal** | 个人/非商业永久免费；安装所需本地运行时后，本地核心能力无需 BossAI 账号、BossAI Points 或云端模型 | Always free for personal/non-commercial use; after required local runtimes are installed, local core features require no BossAI account, BossAI Points, or cloud model |
| **Personal Pro** | 注册 BossAI 账号并订阅；在本地核心能力之上提供更高额度、跨设备和可选云端增强 | Registered subscription adding higher allowance, cross-device use and optional cloud enhancements on top of the local core |
| **Business** | 任何企业、组织、客户交付、收费制作或其他商业用途必须取得商业授权；本地与云端能力均受商业治理 | Required for company, organization, client-delivery, paid-production or other commercial use; both local and cloud capabilities remain commercially governed |

Account, License, Subscription, BossAI Points, Quota, Device Binding and Entitlement are owned by the existing **BossAI OS + BossAI Headquarters Commerce** authority. BossAI Agent does not create a second billing or licensing ledger.

账号、License、Subscription、BossAI Points、Quota、Device Binding 与 Entitlement 统一复用现有 **BossAI OS + BossAI Headquarters Commerce** 权威；BossAI Agent 不另建第二套计费或授权账本。

## First run / 首次启动

The intended Windows journey is:

```text
GitHub Releases
→ download installer
→ install BossAI Agent
→ choose 简体中文 / English
→ review and accept the approved EULA/Terms/Privacy
→ enter Local Free Personal without signing in
→ install approved local runtimes as needed
→ create the first video locally
→ sign in only for Personal Pro / BossAI Gateway / cross-device use / Business management
```

目标 Windows 用户路径：

```text
GitHub Releases
→ 下载安装包
→ 安装 BossAI Agent
→ 选择简体中文 / English
→ 查看并接受已批准的 EULA / Terms / Privacy
→ 无需登录进入本地 Free Personal
→ 按需安装已批准的本地运行时
→ 在本地制作第一条视频
→ 需要 Personal Pro / BossAI Gateway / 跨设备 / Business 管理时再登录
```

The one-time Pairing ID / 9-digit pairing-code flow is retained only as an advanced recovery path. It is not the default Free Personal onboarding flow.

一次性 Pairing ID / 9 位配对码仅保留为高级恢复入口，不是 Free Personal 默认首启流程。

## Local-first execution / 本地优先执行

**Local execution is the default product path. Cloud models are optional enhancements, not a dependency of the Free Personal core.** After the required runtimes/models have been installed, the core workflow runs on the customer device:

- **Qwen** — local script generation and rewrite through the packaged local runtime.
- **CosyVoice2** — local voice generation using customer-authorized or BossAI-owned reference voices.
- **MuseTalk** — local talking-avatar generation using authorized avatar media.
- **Whisper** — optional local transcription.
- **FFmpeg** — local subtitles, audio mixing, cover/final-video composition and export.

Core local operations must **never silently fall back to a cloud model**. A cloud capability is used only after the user explicitly chooses BossAI Gateway or another approved cloud path. Losing access to Headquarters services must fail closed for Pro/Business/cloud entitlement while preserving eligible Free Personal local use; commercial use is never inferred from a local fallback.

**本地执行是产品默认主路径。云端模型只是可选增强层，不是 Free Personal 核心能力的依赖。** 所需 runtime / 模型完成安装后，核心工作流在客户本机执行：

- **Qwen**：本地文案生成与改写。
- **CosyVoice2**：使用客户已授权或 BossAI 自有参考声音进行本地配音。
- **MuseTalk**：使用已授权人物素材进行本地数字人口播合成。
- **Whisper**：可选的本地转写。
- **FFmpeg**：本地字幕、混音、封面/成片合成和导出。

本地核心能力**禁止静默回退到云端模型**。只有用户明确选择 BossAI Gateway 或其他已批准云能力时才进入云端路径。总部服务暂时不可达时，Pro / Business / 云端 entitlement 必须 fail-closed，但符合条件的 Free Personal 本地能力应继续可用；本地降级绝不自动产生商业使用授权。

## BYOK and BossAI Gateway / BYOK 与 BossAI Gateway

Both paths below are **explicit opt-in cloud enhancements**. Neither is required to complete the Free Personal local core workflow.

以下两条路径均为**用户主动选择的云端增强能力**，完成 Free Personal 本地核心工作流不需要它们。

- **BossAI Gateway:** usage is metered and settled through BossAI Points / plan allowance. It is never a silent fallback for a failed local runtime.  
  **BossAI Gateway：** 按 BossAI Points / 套餐额度统一计量与结算；本地 runtime 失败时不得静默切换到 Gateway。
- **BYOK:** provider/model cost is paid by the user, but BYOK still obeys Free/Pro/Business entitlement, quota, device binding and product feature gates.  
  **BYOK：** Provider/模型成本由用户承担，但仍受 Free/Pro/Business entitlement、额度、设备绑定和产品权限约束，不能绕过授权。

## Account and sign-in / 账号与登录

Free Personal local core features do not require sign-in. Sign-in is used only when the user needs Personal Pro, BossAI Gateway, cross-device features or Business management. The current `0.1.0` authentication contract uses **phone/email + password for sign-in**; registration additionally uses a verification challenge/code. Video Agent sends those credentials to the local BossAI OS account bridge for authentication and clears password/verification-code values from the UI state after submission; it does not persist the user's password or Headquarters access/refresh tokens as a Video Agent credential store.

Free Personal 本地核心能力无需登录。只有需要 Personal Pro、BossAI Gateway、跨设备能力或 Business 管理时才登录。当前 `0.1.0` 的真实认证契约为：**手机号/邮箱 + 密码登录**；注册时另外需要验证码 challenge/code。Video Agent 将凭据提交给本机 BossAI OS 账号桥完成认证，提交后清除 UI 中的密码/验证码值；Video Agent 不把用户密码或总部 access/refresh token 作为自己的凭据账本持久化。

Passwordless/verification-code sign-in may replace this flow only after BossAI OS + Headquarters Commerce expose and validate a compatible authoritative sign-in contract. Video Agent must not invent a second authentication authority.

只有当 BossAI OS + Headquarters Commerce 提供并验证兼容的权威无密码/验证码登录契约后，Video Agent 才能替换当前登录流程；Video Agent 不得自行创建第二套身份认证权威。

## Privacy and local data / 隐私与本地数据

Customer projects, authorized voice/avatar media and generated outputs are local-first unless the user explicitly invokes an approved cloud capability. Account credentials entered for the current sign-in flow are relayed to the local BossAI OS account bridge for authentication and are not persisted by Video Agent as its own password/token store. Product entitlement and quota metadata are resolved through BossAI OS / Headquarters Commerce.

客户项目、已授权声音/人物素材及生成成果默认本地优先；只有用户明确调用已批准的云能力时才发生相应云端处理。当前登录流程中输入的账号凭据会提交给本机 BossAI OS 账号桥完成认证，Video Agent 不把这些凭据作为自己的密码/token 存储持久化；套餐、额度与 entitlement 通过 BossAI OS / Headquarters Commerce 解析。

## Commercial-use rule / 商业用途规则

Free Personal is for personal, non-commercial use. Any company, organization, client-service, paid-production, resale, white-label/OEM or other commercial use requires the applicable Business authorization before use.

Free Personal 仅限个人非商业用途。企业/组织生产、客户服务、收费制作、转售、白标/OEM 或其他商业用途，必须在使用前取得适用的 Business 商业授权。

## Public repository policy / 公开仓库策略

The public repository may contain BossAI-owned backend/UI/desktop/installer source, tests, immutable runtime source locks, documentation and approved release artifacts. It must not contain recovered upstream code, legacy activation/account authority, credentials, model weights or unclear-rights media/assets.

本公开仓库可以包含 BossAI 自有 backend/UI/desktop/installer 源码、测试、固定 runtime source lock、文档和经批准的发行产物；禁止包含恢复上游代码、旧激活/账号权威、凭据、模型权重以及权利不明确的媒体/素材。

See `PUBLIC_REPOSITORY_POLICY.md`.

## Historical MIT fact / 历史 MIT 事实

This repository previously published source snapshots under the MIT License. Rights already granted with those historical snapshots remain governed by the MIT terms that accompanied them and are preserved in `LICENSE-HISTORICAL-MIT.md`.

本仓库历史上已经按 MIT License 公开过源码快照。那些历史 revision 已经产生的 MIT 权利继续有效，并通过 `LICENSE-HISTORICAL-MIT.md` 保留其历史许可文本。

Current BossAI-owned source is distributed under `BossAI Community Source License 1.0` in the root `LICENSE`: personal/non-commercial use is free, while commercial use requires BossAI commercial authorization. Third-party code and models remain governed by their own licenses.

当前 BossAI 自有源码适用根目录 `LICENSE` 中的 `BossAI Community Source License 1.0`：个人/非商业用途免费，商业用途必须取得 BossAI 商业授权；第三方代码和模型继续适用其自身许可证。

## System and runtime policy / 系统与运行时策略

- Windows desktop is the priority distribution target. / Windows 桌面版优先。
- Optional third-party runtimes/models are obtained only through approved, traceable sources and remain subject to their own licenses. / 第三方运行时/模型只使用经过批准、可追溯的来源，并继续适用其自身许可证。
- Public releases must not contain recovery/original-project code, unknown-rights binaries/assets, model weights, cookies, API keys, tokens, activation/device secrets or customer media. / 公开发行物不得包含恢复/原项目代码、权利不明二进制/素材、模型权重、Cookie、API Key、Token、激活/设备秘密或客户媒体。

## Documents / 文档

- `INSTALL.md` — Windows installation / Windows 安装
- `RELEASE_NOTES.md` — Release notes / 版本说明
- `commercial-product/legal/LEGAL_RELEASE_CHECKLIST.md` — GA legal approval checklist / GA 法律批准清单
- `commercial-product/GA_UAT_RUNBOOK.md` — real Business/MuseTalk/signing/legal GA evidence runbook / 真实 Business、MuseTalk、签名与法律 GA 证据执行手册
- `PILOT_RELEASE.md` — Internal Pilot scope, limitations and verification / 内部 Pilot 范围、限制与验收
- `PILOT_SHA256SUMS.txt` — exact Pilot artifact checksums / Pilot 精确文件校验值
- `VERIFY_PILOT.ps1` — local Pilot installer SHA/signature verifier / Pilot 安装包本机校验脚本
- `LICENSE` — current BossAI Community Source License / 当前 BossAI Community Source License
- `LICENSE-HISTORICAL-MIT.md` — historical MIT grant text / 历史 MIT 授权文本
- `EULA.md` — packaged product EULA draft/status / 安装版产品 EULA 草案/状态
- `TERMS.md` — service terms draft/status / 服务条款草案/状态
- `PRIVACY.md` — privacy notice draft/status / 隐私说明草案/状态
- `COMMERCIAL_LICENSE.md` — Free / Pro / Business licensing / 商业授权
- `PUBLIC_REPOSITORY_POLICY.md` — public repository boundary / 公开仓库边界
- `THIRD_PARTY_NOTICES.md` — third-party boundary / 第三方许可边界

## Security / 安全

Never post passwords, API keys, provider secrets, cookies, device credentials, customer media or private logs in Issues. Use only official BossAI support channels once published.

请勿在 Issues 中提交密码、API Key、Provider 密钥、Cookie、设备凭据、客户媒体或私有日志；正式支持渠道公布后仅通过官方 BossAI 渠道提交敏感支持信息。