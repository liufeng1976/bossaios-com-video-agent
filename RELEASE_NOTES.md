# BossAI Video Agent Release Notes / BossAI Video Agent 版本说明

## 0.1.0 public-source Freemium candidate / 0.1.0 公开源码 Freemium 候选版

Status / 状态: **Internal Pilot Ready — GA/commercial release still fail-closed / 内部 Pilot 已可用，GA/商业正式发布仍保持 fail-closed**

### 中文

本版本建立 BossAI 自有的 BossAI Video Agent 产品基线：

- Windows 优先的公开源码 Freemium 桌面软件。
- 当前公开源码按 BossAI Community Source License 提供：个人及非商业使用免费；商业、公司生产、客户交付、收费服务、转售、白标/OEM 等用途必须取得 BossAI Business 商业授权。
- 历史上已经按 MIT License 公开的旧源码快照继续保留当时已经授予的 MIT 权利，不追溯撤回。
- Free Personal 本地模式无需 BossAI 登录即可使用已安装的本地核心能力；BossAI Gateway、Personal Pro 与 Business 商业能力继续由 BossAI Headquarters entitlement 管理并 fail-closed。
- 已真实验证本地 Qwen2.5-7B + llama.cpp 文案改写，不使用 mock 结果。
- 第三方运行时和模型不进入源码仓库或基础安装包；只允许通过固定官方 source/revision/hash 安装，并保留第三方 LICENSE/NOTICE。
- 已完成 BossAI 品牌 Electron shell、backend、双语 UI、Source License/历史 MIT/商业许可展示、最终成片导出与发布前 fail-closed 边界。
- 已真实完成 NSIS 构建、静默安装、已安装程序首启 smoke、正常退出和静默卸载。
- GitHub 仓库同时作为 BossAI 自有实现的公开源码仓库与 Release 仓库；禁止提交恢复/原项目代码、权利不明二进制/资产、模型权重、Cookie、Token、API Key、激活秘密或客户数据。
- Qwen、CosyVoice2、MuseTalk 三套本地 runtime 已完成固定 revision/hash、运行验证和完整 LICENSE/NOTICE；MuseTalk CUDA 已在 RTX 4060 Laptop GPU 上通过。
- 大模型/runtime/download cache 已迁移到 `D:\\BossAI-Models\\VideoAgent`，删除 C 盘模型源后再次完成 runtime/import/CUDA 验证。
- 最新 0.1.0 NSIS 安装包已完成真实安装→启动→卸载 smoke，Internal Pilot machine gate 已通过。
- 当前仍未达到 GA/商业正式发行：真实 Business entitlement UAT、使用客户授权或 BossAI 自有媒体的 MuseTalk 商业 render UAT、最终客户法律批准和可信 Authenticode 签名仍需闭环。

### English

This version establishes the BossAI-owned BossAI Video Agent baseline:

- Windows-first public-source Freemium desktop software.
- Current source is distributed under the BossAI Community Source License: personal and non-commercial use is free; business/company production, client delivery, paid services, resale, white-label/OEM and other commercial use require BossAI Business authorization.
- Historical source snapshots already released under the MIT License retain the MIT rights previously granted with those snapshots; no retroactive revocation is claimed.
- Free Personal local mode can use installed local core capabilities without BossAI sign-in. BossAI Gateway, Personal Pro and Business commercial capabilities remain governed by BossAI Headquarters entitlement and fail closed when authorization is unavailable.
- A real local Qwen2.5-7B + llama.cpp rewrite has been validated without mock output.
- Third-party runtimes and model weights are not committed to the source repository or bundled in the base installer. They must be installed from pinned official source/revision/hash records with their own LICENSE/NOTICE evidence.
- The BossAI Electron shell, backend, bilingual UI, current Source License/historical MIT/commercial-license display, final-video export and pre-publication fail-closed boundary are implemented.
- Real NSIS build, silent install, installed-app first-run smoke, clean exit and silent uninstall have passed.
- GitHub is both the public source repository for BossAI-owned implementation and the Release repository. Recovered/original-project code, unknown-rights binaries/assets, model weights, cookies, tokens, API keys, activation secrets and customer data are forbidden.
- Qwen, CosyVoice2 and MuseTalk local runtimes now have pinned revision/hash validation, runtime validation and complete LICENSE/NOTICE coverage; MuseTalk CUDA passed on an RTX 4060 Laptop GPU.
- Large runtimes/models/download caches were migrated to `D:\\BossAI-Models\\VideoAgent`; the C-drive model source was removed and the D-drive runtimes were revalidated afterwards.
- The current 0.1.0 NSIS installer passed a real install → launch → uninstall smoke, and the Internal Pilot machine gate passes.
- GA/commercial release is still blocked on live Business entitlement UAT, an authorized-media MuseTalk commercial render UAT, final customer legal approval and trusted Authenticode signing.
