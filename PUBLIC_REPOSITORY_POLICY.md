# BossAI Video Agent Public Repository Policy / BossAI Video Agent 公开仓库策略

## 中文

本仓库 `github.com/liufeng1976/bossaios-com-video-agent` 是 **BossAI Video Agent 的公开源码与发行仓库**。

当前源码许可采用 `BossAI Community Source License 1.0`：

- 个人、学习、研究、评估及其他非商业用途可免费使用、修改、构建和再分发；
- 公司生产、客户交付、收费制作、SaaS/托管、转售、白标/OEM 或其他商业用途必须取得 BossAI Commercial License / Headquarters entitlement；
- 任何本地 patch、环境变量、构建参数或自签 token 都不能构成商业授权；商业模式必须通过 BossAI Headquarters entitlement contract 验证并 fail-closed；
- 历史上已经按 MIT License 公开的 revision，其既有 MIT 权利继续有效，不撤回、不缩小。历史 MIT 文本保存在 `LICENSE-HISTORICAL-MIT.md`。

允许公开并应持续维护的内容：

- BossAI 自有 backend / desktop / UI / installer 源码；
- Runtime installer 与固定 upstream source/revision/hash 清单；
- README、安装说明、Release Notes、EULA、Terms、Privacy、Commercial License；
- GitHub Actions、Issue 模板、测试与 smoke；
- Windows 安装包和 SHA-256（正式 Release 时）。

禁止提交或发布：

- 恢复/取证上游代码、原版 Electron bundle、原激活/账号实现；
- HeyVideo key、cookies、tokens、API keys、设备秘密、客户数据；
- 权利不明确的模型权重、声音、人物、音乐、字体、图片或其他资产；
- 未经许可允许再分发的第三方二进制/模型；
- BossAI OS Runtime、第二套 License Server、第二套账户/积分/审批/审计权威。

### Runtime 原则

仓库不携带模型权重。Qwen、CosyVoice2、MuseTalk 等运行组件必须由客户侧 installer 从固定官方 source/revision 下载，并进行 hash、license/notice 和 runtime manifest 验证。

### 发布纪律

公开源码不等于商业授权。正式 Release 必须同时通过：

1. source/public-tree buildability；
2. backend start；
3. UI/Desktop start；
4. Free Personal 真实本地能力 smoke；
5. Commercial/Business entitlement fail-closed；
6. runtime installer/source-lock/license verification；
7. 品牌、凭据、第三方分发边界扫描；
8. 客户法律文件状态检查；
9. Windows 安装包 smoke；
10. 生产发行要求的 Windows 签名策略。

## English

`github.com/liufeng1976/bossaios-com-video-agent` is the **public source and distribution repository** for BossAI Video Agent.

Current BossAI-owned source is licensed under the `BossAI Community Source License 1.0`:

- personal, educational, research, evaluation and other non-commercial use is free, including source modification and local builds;
- company production, client delivery, paid production, hosted/SaaS use, resale, white-label/OEM and other commercial use requires a BossAI Commercial License / Headquarters entitlement;
- local patches, environment variables, build flags or self-issued tokens never create commercial authorization; commercial mode must verify the BossAI Headquarters entitlement contract and fail closed otherwise;
- rights already granted to historical revisions published under MIT remain valid. The historical MIT text is preserved in `LICENSE-HISTORICAL-MIT.md`.

Public content may include BossAI-owned backend/desktop/UI/installer source, tests, runtime installers, immutable upstream source locks, documentation, legal texts, GitHub Actions and approved release binaries/checksums.

The repository must not contain recovery/original upstream code or Electron bundles, legacy activation/account authority, HeyVideo keys, credentials, customer data, unclear-rights models/assets, or duplicated BossAI OS / Headquarters authorities.

Model weights are not stored in the repository. Optional runtimes such as Qwen, CosyVoice2 and MuseTalk are installed client-side from pinned official sources and must pass source hash, license/notice and runtime-manifest verification.

Public source does not itself grant commercial-use authorization. Formal releases must pass public-tree buildability, backend/UI/Desktop smoke, real Free Personal local-feature smoke, commercial fail-closed checks, runtime provisioning/license verification, distribution-boundary scans, legal status checks and the applicable Windows signing policy.
