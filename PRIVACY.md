# BossAI Agent Privacy Notice / BossAI Agent 隐私说明

> Pre-release privacy draft; production release requires formal approval.
> 预发布隐私草案；正式发行前需要完成正式批准。

## Local-first processing / 本地优先处理

**English.** BossAI Agent is designed to keep local projects, uploaded reference voices, avatar media and generated outputs on the user's device by default. A cloud transfer should occur only when the user invokes a capability that explicitly requires a BossAI or third-party cloud service.

**中文。** BossAI Agent 默认将本地项目、上传的参考声音、人物素材及生成结果保存在用户设备上。只有当用户明确调用需要 BossAI 或第三方云服务的能力时，才应发生对应云端传输。

## Account and entitlement data / 账号与授权数据

**English.** The official application may exchange the minimum data required for account authentication, subscription, License, Points, quota, device binding and entitlement with BossAI's existing commercial infrastructure. The product must not create a second independent identity, billing or quota authority.

**中文。** 官方应用可与 BossAI 现有商业基础设施交换账号认证、订阅、License、Points、Quota、Device Binding 和 Entitlement 所需的最小数据。产品不得另建第二套独立身份、计费或额度权威。

## Credentials / 凭据

**English.** Passwords and one-time verification codes should be submitted only to the authorized BossAI account service and must not be persisted by the BossAI Agent product. Provider/API keys used in BYOK mode must remain under the applicable BossAI key-management policy and must not be copied into entitlement records.

**中文。** 密码和一次性验证码只应提交给授权的 BossAI 账号服务，BossAI Agent 产品不得持久化保存。BYOK 使用的 Provider/API Key 必须遵循 BossAI 适用 Key 管理策略，不得写入 entitlement 记录。

## BYOK / 自带 Key

**English.** When BYOK is enabled, task content may be sent directly or through BossAI-approved routing to the selected provider according to the configuration shown to the user. BYOK affects model cost responsibility; it does not bypass product entitlement or quota controls.

**中文。** 启用 BYOK 后，任务内容可能按照界面明确显示的配置直接发送给所选 Provider，或通过 BossAI 批准的路由发送。BYOK 只改变模型成本承担方式，不绕过产品 entitlement 或额度控制。

## Device information / 设备信息

**English.** Non-secret installation/device identifiers, product version, plan status and other minimum diagnostics may be used to enforce device eligibility, prevent abuse and support entitlement synchronization. Customer media and project content must not be included in entitlement snapshots.

**中文。** 非秘密的安装/设备标识、产品版本、套餐状态及必要诊断信息可用于设备资格校验、防滥用和 entitlement 同步。客户媒体和项目内容不得进入 entitlement 快照。

## Third-party services / 第三方服务

**English.** Third-party models, platforms or providers may have separate privacy policies. Their data processing applies only when the corresponding capability is actually used.

**中文。** 第三方模型、平台或 Provider 可能适用独立隐私政策；只有实际使用对应能力时，才会发生相应的数据处理。

## Historical versions / 历史版本

**English.** This notice describes the proprietary Freemium product direction for future formal releases. It does not alter the license or data behavior statements that accompanied historical MIT-licensed versions.

**中文。** 本说明描述未来正式闭源 Freemium 版本的隐私方向，不改变历史 MIT 许可版本随附的许可或数据行为说明。
