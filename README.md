# BossAI Video Agent

> **bossaios.com · Windows-first bilingual Freemium desktop software**
> **bossaios.com · Windows 优先的中英文双语 Freemium 桌面软件**

BossAI Agent turns script creation, voice, digital-human video, editing, cover generation and export into one Windows workflow. This GitHub repository is the public source and release repository for BossAI-owned implementation. Personal and non-commercial use is free under the BossAI Community Source License; commercial use requires BossAI commercial authorization.

BossAI Agent 将文案、配音、数字人口播、视频剪辑、封面与导出整合为一条 Windows 工作流。本 GitHub 仓库同时承担 BossAI 自有实现的公开源码与发行职责。个人及非商业用途按 BossAI Community Source License 免费使用；商业用途必须取得 BossAI 商业授权。

## Download / 下载

Use **GitHub Releases** for official Windows installers, release notes and SHA-256 checksums. Do not trust installers from unofficial mirrors.

请仅通过 **GitHub Releases** 获取官方 Windows 安装包、版本说明和 SHA-256 校验值，不要使用非官方镜像。

**Current release status / 当前发布状态:** `0.1.0` is **Internal Pilot Ready**. Local Windows build, packaged first-run, real NSIS install/start/exit/uninstall, Free Personal/commercial fail-closed behavior, Qwen/CosyVoice2/MuseTalk installed runtimes, runtime SHA/NOTICE verification, D-drive runtime storage, and MuseTalk CUDA runtime checks have passed. It is **not approved for GA/public commercial release** until live BossAI Business entitlement UAT, an authorized-media MuseTalk commercial render UAT, final customer legal approval, and trusted Authenticode signing are complete. The current installer is unsigned and must be treated as Internal Pilot only.

`0.1.0` 已达到 **Internal Pilot Ready / 内部 Pilot 可用**：本地 Windows 构建、打包首启、真实 NSIS 安装/启动/退出/卸载、Free Personal/商业 fail-closed、Qwen/CosyVoice2/MuseTalk 已安装 runtime、模型 SHA/NOTICE、D 盘 runtime 存储与 MuseTalk CUDA runtime 均已通过。当前仍**不得作为 GA/公开商业正式版发布**，剩余门槛为真实 BossAI Business entitlement UAT、使用授权媒体的 MuseTalk 商业 render UAT、最终客户法律批准和可信 Authenticode 签名。当前安装包未签名，仅限 Internal Pilot。

## Plans / 套餐

| Plan | 中文 | English |
| --- | --- | --- |
| **Free Personal** | 个人/非商业永久免费；本地核心能力无需 BossAI 账号或商业授权 | Always free for personal/non-commercial use; local core features require no BossAI account or commercial entitlement |
| **Personal Pro** | 注册 BossAI 账号并订阅；长期更高额度、跨设备和高级能力 | Registered subscription with sustained higher allowance, cross-device use and advanced capabilities |
| **Business** | 任何企业、组织、客户交付、收费制作或其他商业用途必须取得商业授权 | Required for company, organization, client-delivery, paid-production or other commercial use |

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

## BYOK and BossAI Gateway / BYOK 与 BossAI Gateway

- **BossAI Gateway:** usage is metered and settled through BossAI Points / plan allowance.
  **BossAI Gateway：** 按 BossAI Points / 套餐额度统一计量与结算。
- **BYOK:** provider/model cost is paid by the user, but BYOK still obeys Free/Pro/Business entitlement, quota, device binding and product feature gates.
  **BYOK：** Provider/模型成本由用户承担，但仍受 Free/Pro/Business entitlement、额度、设备绑定和产品权限约束，不能绕过授权。

## Privacy and local data / 隐私与本地数据

Customer projects, authorized voice/avatar media and generated outputs are local-first unless the user explicitly invokes an approved cloud capability. BossAI Agent never asks for or stores the user's BossAI account password. Product entitlement and quota metadata are resolved through BossAI OS / Headquarters Commerce.

客户项目、已授权声音/人物素材及生成成果默认本地优先；只有用户明确调用已批准的云能力时才发生相应云端处理。BossAI Agent 不要求或保存 BossAI 账号密码；套餐、额度与 entitlement 通过 BossAI OS / Headquarters Commerce 解析。

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
