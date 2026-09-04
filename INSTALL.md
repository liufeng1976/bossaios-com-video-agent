# BossAI Video Agent Installation / BossAI Video Agent 安装说明

## 中文

### 支持平台

当前优先支持 Windows 10/11 x64。正式 Release 以 GitHub Release 页面提供的 BossAI 官方安装包为准。

### Internal Pilot / 内部测试版

当前 `0.1.0` 已通过 Internal Pilot machine gate，但尚未通过 GA 商业发布 gate。当前 Pilot 安装包为 `BossAI-Video-Agent-0.1.0-Setup.exe`，SHA-256：`e91706f5cd3ed74ca4e7c5c0640a9d14d8b8b30daf2e3b737c86f809762ce9c2`。应用和安装包当前均为 **NotSigned**，Windows 可能显示 SmartScreen/安全警告。该版本仅用于内部 Pilot，不得宣称为已签名、已完成商业授权 UAT 或 GA 客户正式版。

### 正式安装

1. 正式 GA 后，从官方 BossAI GitHub 产品仓库的 **Releases** 下载 Windows 安装包。
2. 对照 Release 页面公布的 SHA-256 校验安装包完整性。
3. 启动安装程序并完成 Windows 安装。
4. 首次启动选择界面语言：**简体中文 / English**。
5. 查看并接受该正式版本随附且已批准的 EULA / Terms / Privacy。
6. Free Personal 的本地核心能力无需 BossAI 账号；接受当前许可条款后即可在本机使用。
7. 根据需要安装本地 Qwen、TTS、数字人运行组件。第三方运行时从固定官方 revision/source 安装，仓库和基础安装包不携带模型权重。
8. 需要 Personal Pro、BossAI Gateway、跨设备或 Business 管理时再注册/登录 BossAI 账号。
9. 商业用途必须由 BossAI Headquarters entitlement 验证通过；没有有效 Business 授权时商业能力 fail-closed。

### Runtime 下载代理

如所在网络访问 GitHub / Hugging Face / PyTorch 较慢，可在启动 BossAI Video Agent 前设置 `BOSSAI_RUNTIME_PROXY_URL` 供 git/pip 使用，并可单独设置 `BOSSAI_RUNTIME_DOWNLOAD_PROXY_URL` 供大模型与 wheel 的 curl 下载使用。两项都为空时保持直连；BossAI 不会把本机代理地址写入源码或发布包。所有代理下载仍必须通过固定 revision/source 和 SHA-256 校验后才能安装。

### Runtime / 模型存储位置

默认情况下，BossAI 把 runtime 放在当前用户的本地应用数据目录。磁盘空间紧张时，可把大模型、runtime 和下载缓存迁到其他盘。迁移脚本：`runtime-installers/migrate-runtime-storage.ps1`。例如迁到 `D:\BossAI-Models\VideoAgent` 后，桌面端会读取本机 `runtime-storage.json`，后续安装/升级继续写入 D 盘，而项目、EULA、日志等小型状态仍保留在原用户目录。也可以显式设置 `BOSSAI_VIDEO_RUNTIME_ROOT` 和 `BOSSAI_VIDEO_DOWNLOAD_ROOT`。迁移脚本在存在 `.installing-*` staging 或活动下载进程时会拒绝执行，并在删除 C 盘源目录前先做文件统计和 LICENSE/NOTICE 验证。

### 套餐说明

- **Free Personal**：个人/非商业用途永久免费；本地核心能力无需 BossAI 账号或商业 entitlement。
- **Personal Pro**：注册 + 订阅；提供更高额度和订阅功能。
- **Business**：公司生产、客户交付等商业用途需要有效商业授权。

### BYOK

BYOK 用户自行承担模型/API 成本。BYOK 不改变商业使用许可：个人/非商业本地 Free Personal 可免费使用；Personal Pro、BossAI Gateway 和商业用途仍按对应 BossAI entitlement 控制，BYOK 不能绕过商业授权。

### 数据

项目、授权声音、人物素材和生成结果默认保存在本机。仅当明确使用云能力时，才会按界面提示发生对应云端处理。

## English

### Supported platform

Windows 10/11 x64 is the primary target. Use the official BossAI installer attached to the GitHub **Releases** page.

### Internal Pilot

Version `0.1.0` currently passes the Internal Pilot machine gate but not the GA commercial-release gate. The Pilot installer is `BossAI-Video-Agent-0.1.0-Setup.exe`, SHA-256 `e91706f5cd3ed74ca4e7c5c0640a9d14d8b8b30daf2e3b737c86f809762ce9c2`. Both the application and installer are currently **NotSigned**, so Windows SmartScreen/security warnings may appear. This build is for Internal Pilot only and must not be represented as signed, Business-UAT-approved, or customer-ready GA.

### Formal install

1. After GA approval, download the Windows installer from the official BossAI public product repository Releases page.
2. Verify the installer SHA-256 against the checksum published with the release.
3. Run the installer and complete Windows setup.
4. On first launch choose **简体中文 / English**.
5. Review and accept the approved EULA / Terms / Privacy shipped with that formal release.
6. Local core features in Free Personal require no BossAI account; accept the current license terms and use them locally.
7. Install local Qwen, TTS and digital-human runtimes as needed. Third-party runtimes are installed from pinned official revisions/sources; neither the repository nor the base installer carries model weights.
8. Register/sign in only for Personal Pro, BossAI Gateway, cross-device access or Business management.
9. Commercial use requires verified BossAI Headquarters entitlement and fails closed without an active Business authorization.

### Runtime download proxy

On networks where GitHub, Hugging Face or PyTorch downloads are slow, set `BOSSAI_RUNTIME_PROXY_URL` before launching BossAI Video Agent for git/pip traffic. `BOSSAI_RUNTIME_DOWNLOAD_PROXY_URL` may be set separately for curl-based model and wheel downloads. Empty values keep direct networking. BossAI does not bake a local proxy address into source or release artifacts, and proxied downloads still must pass the pinned revision/source and SHA-256 checks before installation.

### Runtime / model storage

BossAI uses the current user's local application-data directory by default. If the system drive is tight, move large runtimes, models, and download caches to another drive with `runtime-installers/migrate-runtime-storage.ps1`. After a migration such as `D:\BossAI-Models\VideoAgent`, the desktop reads the local `runtime-storage.json` and future runtime installs/upgrades continue on that drive while small application state, EULA acceptance and logs remain under the user profile. `BOSSAI_VIDEO_RUNTIME_ROOT` and `BOSSAI_VIDEO_DOWNLOAD_ROOT` are also supported as explicit overrides. Migration refuses to run while `.installing-*` staging or an active runtime download exists, and verifies copied storage plus installed LICENSE/NOTICE evidence before source cleanup is allowed.

### Plans

- **Free Personal**: permanently free for personal/non-commercial use; local core features require no BossAI account or commercial entitlement.
- **Personal Pro**: registration + subscription, with higher quota and subscribed features.
- **Business**: valid commercial authorization required for business/company/client production covered by the Business-use policy.

### BYOK

BYOK users pay their own provider/model costs. BYOK does not change commercial-use licensing: local Free Personal remains free for personal/non-commercial use, while Personal Pro, BossAI Gateway and commercial use remain subject to the applicable BossAI entitlement. BYOK is not a commercial-authorization bypass.

### Data

Projects, authorized voices, avatar media and generated outputs are local-first. Cloud transfer occurs only when the user explicitly invokes a cloud capability and the UI indicates that data flow.
