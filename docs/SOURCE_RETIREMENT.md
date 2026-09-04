# Source Retirement Plan — Superseded / 源码退役计划——已废止

> Status: **SUPERSEDED — DO NOT EXECUTE**
>
> 状态：**已废止——禁止执行旧源码退役清单**

This file records a retired transition idea that would have removed the BossAI Video Agent implementation from the public branch tip. That direction is no longer the product policy.

本文档仅保留曾经讨论过的“从公开分支移除实现源码”方案之历史语义。该方向已经废止，不再是 BossAI Video Agent 的产品政策。

## Current policy / 当前政策

BossAI Video Agent is a **public-source Freemium** Windows product:

- Current BossAI-owned source may remain publicly readable in this repository.
- Free Personal permits local personal/non-commercial use under the current BossAI source license and packaged-product terms.
- Commercial/company/client/paid/marketing use requires BossAI commercial authorization/Business entitlement.
- Historical source revisions previously published under MIT retain the MIT rights already granted for those revisions; those grants are not revoked retroactively.
- Third-party components retain their own licenses and notices.
- Model weights, credentials, runtime caches, recovered rights-unclear upstream code/assets and customer data must not be committed to the public repository.
- Customer-side runtime installers must continue using pinned official sources/revisions and exact SHA-256 verification.

BossAI Video Agent 现在采用 **公开源码（public-source）Freemium** 模式：

- BossAI 自有的当前源码可以继续公开保留在本仓库。
- Free Personal 允许在当前 BossAI 源码许可和产品条款下进行个人/非商业本地使用。
- 公司、客户项目、收费、营销及其他商业用途必须获得 BossAI 商业授权 / Business entitlement。
- 历史上已经按 MIT 发布的源码版本，其已经授予的 MIT 权利继续有效，不做追溯撤销。
- 第三方组件继续适用其各自许可证和 NOTICE。
- 模型权重、凭据、运行时缓存、权利不明确的恢复版上游代码/素材以及客户数据不得进入公开仓库。
- 客户侧 runtime installer 必须继续使用固定的官方源、固定 revision 和精确 SHA-256 校验。

## Historical retirement checklist / 历史退役清单

Any earlier checklist that instructed maintainers to remove the backend, UI, desktop shell, runtime installers, or other BossAI-owned implementation files from the future public branch tip is **void** and must not be executed.

此前任何要求从未来公开分支 tip 删除 backend、UI、desktop shell、runtime installers 或其他 BossAI 自有实现源码的清单均已**失效**，不得执行。

In particular, do not:

- delete the current implementation merely to create a documentation/download-only public repository;
- describe the current product as closed-source when discussing the repository distribution model;
- claim historical MIT grants were revoked;
- rewrite Git history, force-push, reset/clean, or remove unknown parallel-work files in order to enforce the retired policy.

特别禁止：

- 为了把公开仓库变成“仅文档/下载页”而删除当前实现源码；
- 在描述当前仓库分发模式时继续称其为闭源产品；
- 声称历史 MIT 授权已经被撤销；
- 为执行旧政策而重写 Git 历史、force-push、reset/clean，或删除未知并行现场文件。

## Authoritative repository documents / 当前权威文档

Use the current root documents as the source of truth for publication and licensing decisions:

- `LICENSE` — current source license.
- `LICENSE-HISTORICAL-MIT.md` — historical MIT notice and grant preservation.
- `PUBLIC_REPOSITORY_POLICY.md` — current public repository boundary.
- `COMMERCIAL_LICENSE.md` — commercial-use authorization summary.
- `README.md` and `INSTALL.md` — current product and installation behavior.
- `.github/workflows/source-ci.yml` and `.github/workflows/public-release.yml` — current source/release validation.

If this file conflicts with any of those current documents, the current documents above control.

如本文档与上述当前权威文档存在冲突，以这些当前文档为准。
