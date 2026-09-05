# BossAI Video Agent Installation / BossAI Video Agent 安装说明

## 中文

### 支持平台

当前优先支持 Windows 10/11 x64。正式 Release 以 GitHub Release 页面提供的 BossAI 官方安装包为准。

### Internal Pilot / 内部测试版

当前 `0.1.0` 已通过 Internal Pilot machine gate，但尚未通过 GA 商业发布 gate。Pilot 安装包为 `BossAI-Video-Agent-0.1.0-Setup.exe`；其 SHA-256 以 GitHub Release 页面公布的值为准，可用仓库内的 `VERIFY_PILOT.ps1` 自动核对。（本文件随安装包一起分发，因此不能在此写出该安装包自身的哈希——那个值只有在文件定稿之后才产生。）应用和安装包当前均为 **NotSigned**，Windows 可能显示 SmartScreen/安全警告。该版本仅用于内部 Pilot，不得宣称为已签名、已完成商业授权 UAT 或 GA 客户正式版。

### 正式安装

1. 正式 GA 后，从官方 BossAI GitHub 产品仓库的 **Releases** 下载 Windows 安装包。
2. 对照 Release 页面公布的 SHA-256 校验安装包完整性。
3. 启动安装程序并完成 Windows 安装。
4. 首次启动选择界面语言：**简体中文 / English**。
5. 查看并接受该正式版本随附且已批准的 EULA / Terms / Privacy。
6. Free Personal 的本地核心能力无需 BossAI 账号、BossAI Points 或云端模型；接受当前许可条款后即可进入本地模式。
7. 根据需要安装本地 Qwen、CosyVoice2、MuseTalk、可选 Whisper 与 FFmpeg 运行组件。第三方运行时从固定官方 revision/source 安装，仓库和基础安装包不携带模型权重。
8. 本地运行时安装完成后，文案、配音、数字人口播、可选转写、字幕/混音/成片合成可按对应本地能力执行；本地失败时不得静默切换到云端模型。
9. 需要 Personal Pro、BossAI Gateway、跨设备或 Business 管理时再注册/登录 BossAI 账号并主动选择相应能力。
10. 商业用途必须由 BossAI Headquarters entitlement 验证通过；没有有效 Business 授权时商业能力 fail-closed，但不得因此把符合条件的个人非商业本地核心能力变成云端依赖。

### 本地优先与云端增强

BossAI Video Agent 的默认执行策略是 **local-first**：

- Qwen：本地文案生成/改写。
- CosyVoice2：本地配音。
- MuseTalk：本地数字人口播。
- Whisper：可选本地转写。
- FFmpeg：本地字幕、混音、封面/成片合成与导出。

BossAI Gateway 和 BYOK 都属于用户主动选择的增强路径，不是 Free Personal 本地核心工作流的依赖。云端能力必须显式启用；不得因为本地 runtime 缺失、失败或总部服务状态变化而静默回退到云端模型。

总部账号/entitlement 服务不可达时，Pro、Business、BossAI Gateway 与其他需总部授权的能力必须 fail-closed。Free Personal 的个人非商业本地核心能力在 EULA 已接受且本地 runtime 已就绪时应保持可用；这种本地降级不授予任何商业使用权。

### 当前账号登录契约

Free Personal 本地核心能力不要求登录。当前 `0.1.0` 的真实账号契约为：

- 登录：手机号或邮箱 + 密码。
- 注册：手机号或邮箱 + 密码 + 显示名称 + 验证码 challenge/code。
- 中国大陆 11 位手机号会按 `+86` 规范化。

Video Agent 将登录凭据提交给本机 BossAI OS 账号桥完成认证，提交后清除 UI 中的密码/验证码值；Video Agent 不把用户密码或总部 access/refresh token 建成自己的持久化凭据账本。未来只有在 BossAI OS + Headquarters Commerce 提供并验证权威的无密码/验证码登录契约后，才切换登录方式；Video Agent 不自建第二套身份系统。

### Runtime 下载代理

如所在网络访问 GitHub / Hugging Face / PyTorch 较慢，可在启动 BossAI Video Agent 前设置 `BOSSAI_RUNTIME_PROXY_URL` 供 git/pip 使用，并可单独设置 `BOSSAI_RUNTIME_DOWNLOAD_PROXY_URL` 供大模型与 wheel 的 curl 下载使用。两项都为空时保持直连；BossAI 不会把本机代理地址写入源码或发布包。所有代理下载仍必须通过固定 revision/source 和 SHA-256 校验后才能安装。

### Runtime / 模型存储位置

默认情况下，BossAI 把 runtime 放在当前用户的本地应用数据目录。磁盘空间紧张时，可把大模型、runtime 和下载缓存迁到其他盘。迁移脚本：`runtime-installers/migrate-runtime-storage.ps1`。例如迁到 `D:\BossAI-Models\VideoAgent` 后，桌面端会读取本机 `runtime-storage.json`，后续安装/升级继续写入 D 盘，而项目、EULA、日志等小型状态仍保留在原用户目录。也可以显式设置 `BOSSAI_VIDEO_RUNTIME_ROOT` 和 `BOSSAI_VIDEO_DOWNLOAD_ROOT`。迁移脚本在存在 `.installing-*` staging 或活动下载进程时会拒绝执行，并在删除 C 盘源目录前先做文件统计和 LICENSE/NOTICE 验证。

### 套餐说明

- **Free Personal**：个人/非商业用途永久免费；本地核心能力无需 BossAI 账号、BossAI Points 或云端模型。
- **Personal Pro**：注册 + 订阅；在本地核心能力之上提供更高额度、跨设备及可选云端增强。
- **Business**：公司生产、客户交付等商业用途需要有效商业授权；本地与云端能力均受商业治理。

### BYOK

BYOK 是可选云端增强路径，用户自行承担模型/API 成本。BYOK 不改变商业使用许可：个人/非商业本地 Free Personal 可免费使用；Personal Pro、BossAI Gateway 和商业用途仍按对应 BossAI entitlement 控制，BYOK 不能绕过商业授权，也不能作为本地 runtime 失败时的静默回退。

### 数据

项目、授权声音、人物素材和生成结果默认保存在本机。仅当用户明确选择并调用云能力时，才会按界面提示发生对应云端处理。

## English

### Supported platform

Windows 10/11 x64 is the primary target. Use the official BossAI installer attached to the GitHub **Releases** page.

### Internal Pilot

Version `0.1.0` currently passes the Internal Pilot machine gate but not the GA commercial-release gate. The Pilot installer is `BossAI-Video-Agent-0.1.0-Setup.exe`. Its SHA-256 is the value published on the GitHub Release page; `VERIFY_PILOT.ps1` in the repository checks it for you. This file ships inside that installer, so it cannot state the installer's own hash: that value only exists once this file is final. Both the application and installer are currently **NotSigned**, so Windows SmartScreen/security warnings may appear. This build is for Internal Pilot only and must not be represented as signed, Business-UAT-approved, or customer-ready GA.

### Formal install

1. After GA approval, download the Windows installer from the official BossAI public product repository Releases page.
2. Verify the installer SHA-256 against the checksum published with the release.
3. Run the installer and complete Windows setup.
4. On first launch choose **简体中文 / English**.
5. Review and accept the approved EULA / Terms / Privacy shipped with that formal release.
6. Free Personal local core features require no BossAI account, BossAI Points or cloud model; after accepting the current licence terms, enter local mode directly.
7. Install local Qwen, CosyVoice2, MuseTalk, optional Whisper and FFmpeg runtimes as needed. Third-party runtimes are installed from pinned official revisions/sources; neither the repository nor the base installer carries model weights.
8. Once those runtimes are ready, script generation/rewrite, voiceover, talking-avatar generation, optional transcription, subtitles/mixing/final composition can use their local execution paths. A local failure must never silently fall back to a cloud model.
9. Register/sign in only for Personal Pro, BossAI Gateway, cross-device access or Business management, and explicitly choose the relevant enhanced capability.
10. Commercial use requires verified BossAI Headquarters entitlement and fails closed without active Business authorization; this must not turn eligible personal/non-commercial local core use into a cloud dependency.

### Local-first and cloud enhancement

BossAI Video Agent defaults to **local-first** execution:

- Qwen: local script generation/rewrite.
- CosyVoice2: local voice generation.
- MuseTalk: local talking-avatar generation.
- Whisper: optional local transcription.
- FFmpeg: local subtitles, mixing, cover/final-video composition and export.

BossAI Gateway and BYOK are explicit opt-in enhancements rather than dependencies of the Free Personal local core. Cloud capabilities must be selected explicitly; a missing/failed local runtime or changing Headquarters-service status must never cause a silent cloud fallback.

If Headquarters account/entitlement services are unavailable, Pro, Business, BossAI Gateway and other Headquarters-gated capabilities must fail closed. Eligible Free Personal personal/non-commercial local core use should remain available once the EULA is accepted and local runtimes are ready; that fallback grants no commercial-use rights.

### Current account sign-in contract

Free Personal local core features do not require sign-in. The real `0.1.0` account contract is:

- Sign-in: phone or email + password.
- Registration: phone or email + password + display name + verification challenge/code.
- 11-digit mainland China mobile numbers are normalized to `+86`.

Video Agent relays sign-in credentials to the local BossAI OS account bridge for authentication and clears password/verification-code values from UI state after submission. It does not create its own persisted password or Headquarters access/refresh-token ledger. Passwordless/verification-code sign-in should replace this flow only after BossAI OS + Headquarters Commerce expose and validate an authoritative compatible contract; Video Agent must not create a second identity authority.

### Runtime download proxy

On networks where GitHub, Hugging Face or PyTorch downloads are slow, set `BOSSAI_RUNTIME_PROXY_URL` before launching BossAI Video Agent for git/pip traffic. `BOSSAI_RUNTIME_DOWNLOAD_PROXY_URL` may be set separately for curl-based model and wheel downloads. Empty values keep direct networking. BossAI does not bake a local proxy address into source or release artifacts, and proxied downloads still must pass the pinned revision/source and SHA-256 checks before installation.

### Runtime / model storage

BossAI uses the current user's local application-data directory by default. If the system drive is tight, move large runtimes, models, and download caches to another drive with `runtime-installers/migrate-runtime-storage.ps1`. After a migration such as `D:\BossAI-Models\VideoAgent`, the desktop reads the local `runtime-storage.json` and future runtime installs/upgrades continue on that drive while small application state, EULA acceptance and logs remain under the user profile. `BOSSAI_VIDEO_RUNTIME_ROOT` and `BOSSAI_VIDEO_DOWNLOAD_ROOT` are also supported as explicit overrides. Migration refuses to run while `.installing-*` staging or an active runtime download exists, and verifies copied storage plus installed LICENSE/NOTICE evidence before source cleanup is allowed.

### Plans

- **Free Personal**: permanently free for personal/non-commercial use; local core features require no BossAI account, BossAI Points or cloud model.
- **Personal Pro**: registration + subscription, adding higher allowance, cross-device use and optional cloud enhancements on top of the local core.
- **Business**: valid commercial authorization required for business/company/client production; local and cloud capabilities remain commercially governed.

### BYOK

BYOK is an optional cloud enhancement path whose provider/model cost is paid by the user. BYOK does not change commercial-use licensing: local Free Personal remains free for personal/non-commercial use, while Personal Pro, BossAI Gateway and commercial use remain subject to the applicable BossAI entitlement. BYOK is not a commercial-authorization bypass and must not be used as a silent fallback for failed local runtimes.

### Data

Projects, authorized voices, avatar media and generated outputs are local-first. Cloud transfer occurs only when the user explicitly selects and invokes a cloud capability and the UI indicates that data flow.
