<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand-lockup">
        <img class="brand-mark" src="/bossai-video-mark.svg" alt="BossAI Video Agent" />
        <div>
          <strong>BossAI Video Agent</strong>
          <span>Freemium Desktop · 0.1.0</span>
        </div>
      </div>

      <nav>
        <button :class="{ active: screen === 'home' }" @click="screen = 'home'">{{ tr('首页', 'Home') }}</button>
        <button :class="{ active: screen === 'studio' }" @click="screen = 'studio'">{{ tr('AI 口播视频', 'AI Video Studio') }}</button>
        <button :class="{ active: screen === 'legal' }" @click="screen = 'legal'">{{ tr('条款与隐私', 'Legal & Privacy') }}</button>
        <button disabled>{{ tr('多平台发布', 'Publishing') }}</button>
        <button disabled>{{ tr('团队与矩阵', 'Teams') }}</button>
      </nav>

      <div class="sidebar-foot">
        <span :class="['dot', backendReady ? 'ok' : 'bad']"></span>
        <span>{{ backendReady ? tr('本地引擎已连接', 'Local engine connected') : tr('本地引擎未连接', 'Local engine disconnected') }}</span>
      </div>
    </aside>

    <main class="content">
      <header class="topbar">
        <div>
          <p class="kicker">BossAI · bossaios.com</p>
          <h1>{{ screen === 'studio' ? tr('AI 口播视频生产', 'AI Talking Video Studio') : screen === 'legal' ? tr('条款、隐私与许可', 'Terms, Privacy & Licensing') : tr('本地 AI 视频生产工作台', 'Local AI Video Production Workspace') }}</h1>
        </div>
        <div class="top-actions">
          <button class="secondary" :class="{ active: locale === 'zh-CN' }" @click="setLocale('zh-CN')">中文</button>
          <button class="secondary" :class="{ active: locale === 'en' }" @click="setLocale('en')">English</button>
          <span :class="['status-badge', executionAllowed ? 'success' : 'warning']">{{ entitlementLabel }}</span>
          <button class="secondary" @click="refreshStatus">{{ tr('刷新', 'Refresh') }}</button>
        </div>
      </header>

      <section v-if="screen === 'home'" class="home-grid">
        <article class="hero-card">
          <p class="kicker">Free Personal · Personal Pro · Business</p>
          <h2>{{ tr('个人永久免费起步，需要更多额度再升级；商业用途必须使用 Business。', 'Start free forever for personal use, upgrade for higher limits, and use Business for commercial work.') }}</h2>
          <p>{{ tr('BossAI Video Agent 是公开源码 Freemium Windows 桌面软件。Free Personal 面向个人非商业用途免费；Personal Pro 提供个人订阅增强能力；Business 提供商业用途授权。账号、套餐、Points、Quota、设备绑定和 Entitlement 全部来自 BossAI 现有商业权威。', 'BossAI Video Agent is a public-source Freemium Windows desktop app. Free Personal is free for personal non-commercial use, Personal Pro adds enhanced personal subscription capabilities, and Business licenses commercial use. Account, plan, Points, quota, device binding and entitlement come from the existing BossAI commercial authority.') }}</p>
          <div class="hero-actions">
            <button class="primary" :disabled="!executionAllowed" @click="screen = 'studio'">{{ tr('开始制作', 'Start creating') }}</button>
            <button class="secondary" @click="openUpgrade">{{ tr('升级套餐', 'Upgrade plan') }}</button>
            <span v-if="previewUnlocked" class="preview-note">{{ tr('内部预览模式', 'Internal preview') }}</span>
          </div>
        </article>

        <article class="account-card">
          <div class="panel-head">
            <div><span class="step">01</span><h2>{{ tr('本地免费模式 / BossAI 账号', 'Local Free Mode / BossAI Account') }}</h2></div>
            <span :class="['status-badge', accountAuthenticated ? 'success' : 'warning']">{{ accountLabel }}</span>
          </div>

          <template v-if="accountAuthenticated">
            <div class="account-summary">
              <div><span>{{ tr('账号', 'Account') }}</span><strong>{{ accountSession?.account?.maskedIdentifier || accountSession?.account?.displayName || tr('已登录', 'Signed in') }}</strong></div>
              <div><span>{{ tr('当前套餐', 'Current plan') }}</span><strong>{{ tierLabel }} · {{ entitlement?.planName || tr('等待同步', 'Syncing') }}</strong></div>
              <div><span>{{ tr('剩余额度', 'Remaining quota') }}</span><strong>{{ quotaDisplay }}</strong></div>
            </div>
            <div class="account-summary">
              <div><span>{{ tr('额度恢复', 'Quota reset') }}</span><strong>{{ quotaResetLabel }}</strong></div>
              <div><span>{{ tr('设备绑定', 'Device binding') }}</span><strong>{{ deviceBindingLabel }}</strong></div>
              <div><span>{{ tr('商业用途', 'Commercial use') }}</span><strong>{{ businessUseAllowed ? tr('已授权', 'Licensed') : tr('需要 Business', 'Business required') }}</strong></div>
            </div>
            <div class="button-row">
              <button class="secondary" :disabled="authBusy" @click="signOutAccount">{{ tr('退出账号', 'Sign out') }}</button>
              <button class="secondary" :disabled="authBusy" @click="refreshStatus">{{ tr('同步套餐与额度', 'Sync plan & quota') }}</button>
              <button class="primary" @click="openUpgrade">{{ tr('升级 / 购买 Business', 'Upgrade / Buy Business') }}</button>
            </div>
          </template>

          <template v-else>
            <p class="account-help">{{ tr('Free Personal 的本地核心能力无需 BossAI 账号；登录仅用于 Personal Pro、Business、跨设备、BossAI Gateway 及其他需要总部 entitlement 的能力。Video Agent 不保存你的密码、验证码或总部访问令牌。', 'Local core features in Free Personal do not require a BossAI account. Sign-in is used only for Personal Pro, Business, cross-device access, BossAI Gateway, and other capabilities that require Headquarters entitlement. Video Agent does not store your password, verification code, or Headquarters access token.') }}</p>
            <div class="auth-tabs">
              <button :class="{ active: authMode === 'login' }" @click="authMode = 'login'">{{ tr('登录', 'Sign in') }}</button>
              <button :class="{ active: authMode === 'register' }" @click="authMode = 'register'">{{ tr('注册', 'Register') }}</button>
            </div>
            <div class="grid two">
              <label><span>{{ tr('手机号或邮箱', 'Phone or email') }}</span><input v-model.trim="accountForm.identifier" autocomplete="username" :placeholder="tr('手机号或 name@example.com', 'Phone or name@example.com')" /></label>
              <label><span>{{ tr('密码', 'Password') }}</span><input v-model="accountForm.password" type="password" autocomplete="current-password" :placeholder="tr('至少 8 位', 'At least 8 characters')" /></label>
              <label v-if="authMode === 'register'"><span>{{ tr('显示名称', 'Display name') }}</span><input v-model.trim="accountForm.displayName" :placeholder="tr('你的姓名', 'Your name')" /></label>
              <label v-if="authMode === 'register'">
                <span>{{ tr('验证码', 'Verification code') }}</span>
                <div class="inline-field">
                  <input v-model.trim="accountForm.verificationCode" inputmode="numeric" :placeholder="tr('验证码', 'Code')" />
                  <button class="secondary" :disabled="challengeBusy || !accountForm.identifier" @click="requestAccountChallenge">{{ challengeBusy ? tr('发送中…', 'Sending…') : tr('发送验证码', 'Send code') }}</button>
                </div>
              </label>
            </div>
            <p v-if="authMode === 'register'" class="account-help">{{ tr('中国大陆 11 位手机号会自动按 +86 处理。', '11-digit mainland China mobile numbers are normalized to +86.') }}</p>
            <button class="primary" :disabled="authBusy || !accountForm.identifier || accountForm.password.length < 8" @click="submitAccount">{{ authBusy ? tr('处理中…', 'Working…') : authMode === 'login' ? tr('登录 BossAI', 'Sign in to BossAI') : tr('创建 BossAI 账号', 'Create BossAI account') }}</button>
          </template>
        </article>

        <article class="account-card">
          <div class="panel-head">
            <div><span class="step">02</span><h2>{{ tr('套餐、额度与许可', 'Plan, quota & license') }}</h2></div>
            <span :class="['status-badge', executionAllowed ? 'success' : 'warning']">{{ entitlementLabel }}</span>
          </div>
          <div class="account-summary">
            <div><span>Free Personal</span><strong>{{ tr('永久免费基础额度', 'Free recurring base quota') }}</strong></div>
            <div><span>Personal Pro</span><strong>{{ tr('订阅 · 更高额度', 'Subscription · higher limits') }}</strong></div>
            <div><span>Business</span><strong>{{ tr('商业用途授权', 'Commercial-use license') }}</strong></div>
          </div>
          <p class="account-help">{{ tr('BYOK 只改变模型费用承担方式，不绕过产品 Entitlement 或产品级额度。通过 BossAI AI Gateway 的任务按总部 Points 规则扣减；本产品不创建本地积分账本。', 'BYOK changes who pays model-provider cost; it does not bypass product entitlement or product quota. Tasks routed through the BossAI AI Gateway are charged under Headquarters Points rules. This product does not create a local points ledger.') }}</p>
          <p v-if="accountAuthenticated && !businessUseAllowed" class="runtime-note">{{ tr('当前套餐仅授权个人用途。为客户交付、公司生产、收费服务或营销经营使用本软件前，请升级到 Business。', 'Your current tier is for personal use only. Upgrade to Business before client delivery, company production, paid services or commercial marketing use.') }}</p>
          <div class="button-row"><button class="primary" @click="openUpgrade">{{ tr('查看升级方案', 'View upgrade options') }}</button></div>
        </article>

        <article class="account-card">
          <div class="panel-head">
            <div><span class="step">03</span><h2>{{ tr('软件许可 EULA', 'Software EULA') }}</h2></div>
            <span :class="['status-badge', eulaAccepted ? 'success' : 'warning']">{{ eulaAccepted ? tr('已接受', 'Accepted') : tr('待接受', 'Required') }}</span>
          </div>
          <p class="account-help">{{ tr('当前 BossAI 自有源码适用 BossAI Community Source License：个人/非商业用途免费，商业用途需要 BossAI 授权。历史上已按 MIT 发布的 revision 权利保持不变。', 'Current BossAI-owned source uses the BossAI Community Source License: personal/non-commercial use is free and commercial use requires BossAI authorization. Historical MIT-licensed revisions keep their existing rights.') }}</p>
          <div class="button-row">
            <button class="secondary" :disabled="!desktopLegalAvailable" @click="openLegal('eula')">{{ tr('查看 EULA', 'View EULA') }}</button>
            <button v-if="!eulaAccepted" class="primary" :disabled="eulaBusy" @click="acceptCurrentEula">{{ eulaBusy ? tr('保存中…', 'Saving…') : tr('接受当前版本 EULA', 'Accept current EULA') }}</button>
          </div>
        </article>

        <article class="runtime-card">
          <div class="panel-head">
            <div>
              <span class="step">{{ tr('环境', 'Runtime') }}</span>
              <h2>{{ tr('BossAI 运行环境中心', 'BossAI Runtime Center') }}</h2>
            </div>
            <span :class="['status-badge', allCoreRuntimesReady ? 'success' : 'warning']">{{ allCoreRuntimesReady ? tr('核心环境已就绪', 'Core runtimes ready') : tr('需要安装', 'Installation required') }}</span>
          </div>
          <p class="runtime-help">{{ tr('BossAI 客户版不复制原项目模型和运行时。所需组件从固定官方来源安装到本机 BossAI 专用目录，并保留来源、版本和许可记录。', 'The BossAI customer build does not copy models or runtimes from the original project. Required components are installed from pinned official sources into a dedicated local BossAI directory with provenance and license records.') }}</p>
          <div class="runtime-toolbar">
            <label>
              <span>{{ tr('运行模式', 'Runtime mode') }}</span>
              <select v-model="runtimeInstallProfile" :disabled="runtimeInstallBusy">
                <option value="gpu">{{ tr('GPU（推荐）', 'GPU (recommended)') }}</option>
                <option value="cpu">{{ tr('CPU（仅文案/配音兼容模式）', 'CPU (script/TTS compatibility)') }}</option>
              </select>
            </label>
            <label class="consent-row runtime-consent">
              <input v-model="runtimeLicenseAccepted" type="checkbox" :disabled="runtimeInstallBusy" />
              <span>{{ tr('我已阅读并同意对应第三方运行组件的许可与安装说明。', 'I have reviewed and accepted the applicable third-party runtime licenses and installation notes.') }}</span>
            </label>
          </div>
          <div class="runtime-list">
            <div v-for="item in runtimeItems" :key="item.id" class="runtime-row">
              <div class="runtime-identity">
                <strong>{{ item.name }}</strong>
                <span>{{ item.description }}</span>
              </div>
              <span :class="['runtime-state', item.ready ? 'ready' : 'missing']">{{ item.ready ? tr('已就绪', 'Ready') : item.blockedReason || tr('未安装', 'Not installed') }}</span>
              <button
                class="secondary"
                :disabled="runtimeInstallBusy || item.ready || !runtimeControlAvailable || !runtimeLicenseAccepted || !item.installable"
                @click="installRuntimeComponent(item.id)"
              >{{ runtimeInstallBusy && runtimeInstallComponentId === item.id ? tr('安装中…', 'Installing…') : item.ready ? tr('已安装', 'Installed') : tr('安装', 'Install') }}</button>
            </div>
          </div>
          <p v-if="!runtimeControlAvailable" class="runtime-note">{{ tr('运行环境安装只允许从 BossAI Video Agent 桌面应用发起；浏览器页面无权执行本机安装。', 'Runtime installation is available only in the BossAI Video Agent desktop app; browser pages cannot install local runtimes.') }}</p>
          <p v-if="runtimeInstallMessage" class="runtime-log">{{ runtimeInstallMessage }}</p>
        </article>

        <article class="metric-card">
          <span>{{ tr('当前许可', 'Current license') }}</span>
          <strong>{{ entitlementLabel }}</strong>
          <p>{{ entitlementReason }}</p>
        </article>

        <article class="metric-card">
          <span>{{ tr('当前 TTS', 'Current TTS') }}</span>
          <strong>CosyVoice2</strong>
          <p>{{ tr('Free Personal、Personal Pro 与 Business 都使用许可边界清晰的 CosyVoice2；必须选择你有权使用的参考声音。', 'Free Personal, Personal Pro and Business all use CosyVoice2 under its applicable license; use only reference voices you are authorized to use.') }}</p>
        </article>

        <article class="metric-card">
          <span>{{ tr('数字人引擎', 'Digital-human engine') }}</span>
          <strong>MuseTalk</strong>
          <p>{{ tr('所有套餐都要求使用你本人、公司拥有或已取得相应授权的人物视频。', 'All tiers require avatar video that you own or are properly authorized to use.') }}</p>
        </article>
      </section>

      <section v-else-if="screen === 'legal'" class="home-grid">
        <article class="hero-card">
          <p class="kicker">BossAI Video Agent · 0.1.0</p>
          <h2>{{ tr('当前源码许可、历史 MIT 事实、服务条款和隐私边界都必须可直接查看。', 'The current source license, historical MIT facts, terms and privacy boundaries must be directly viewable.') }}</h2>
          <p>{{ tr('历史 MIT 版本的既有授权不撤回；新的正式 Windows 安装版从 EULA 向前适用。未批准的客户法律文件不会被冒充为正式条款。', 'Historical MIT grants are not revoked. The EULA applies prospectively to new formal Windows builds. Unapproved customer legal files are never presented as approved terms.') }}</p>
          <span :class="['status-badge', legalReleaseReady ? 'success' : 'warning']">{{ legalReleaseReady ? tr('客户法律包已批准', 'Customer legal bundle approved') : tr('客户法律包尚未批准', 'Customer legal bundle not yet approved') }}</span>
        </article>

        <article class="account-card">
          <div class="panel-head">
            <div><span class="step">{{ tr('法律', 'Legal') }}</span><h2>{{ tr('客户文件', 'Customer documents') }}</h2></div>
            <span class="hint">{{ tr('仅打开发行包白名单文件', 'Only allowlisted release documents') }}</span>
          </div>
          <div class="runtime-list">
            <div v-for="item in legalDocuments" :key="item.id" class="runtime-row">
              <div class="runtime-identity">
                <strong>{{ item.name }}</strong>
                <span>{{ item.description }}</span>
              </div>
              <span :class="['runtime-state', item.available ? 'ready' : 'missing']">{{ item.available ? tr('可查看', 'Available') : tr('未进入发行包', 'Not in release bundle') }}</span>
              <button class="secondary" :disabled="!item.available || !desktopLegalAvailable" @click="openLegal(item.id)">{{ tr('打开', 'Open') }}</button>
            </div>
          </div>
          <p v-if="!desktopLegalAvailable" class="runtime-note">{{ tr('法律文件查看入口只在 BossAI Video Agent 桌面应用中启用。', 'Legal documents can be opened from the BossAI Video Agent desktop app.') }}</p>
        </article>

        <article class="metric-card">
          <span>{{ tr('商业权威', 'Commercial authority') }}</span>
          <strong>BossAI Headquarters Commerce</strong>
          <p>{{ tr('账号、订阅、套餐、设备、Points、Quota 和商业授权统一由 BossAI 商业系统管理；本产品不创建第二套收费权威。', 'Account, subscription, plan, device, Points, quota and commercial licensing are managed by the BossAI commercial authority; this product creates no second billing authority.') }}</p>
        </article>

        <article class="metric-card">
          <span>{{ tr('本地数据原则', 'Local data principle') }}</span>
          <strong>Local-first</strong>
          <p>{{ tr('客户声音、人物视频和生成成果默认保存在本机；商业授权快照不包含客户业务内容或 Provider Key。', 'Customer voice, avatar media and generated results remain local by default; entitlement snapshots contain no customer business content or Provider keys.') }}</p>
        </article>
      </section>

      <section v-else class="studio-layout">
        <div v-if="!executionAllowed" class="license-blocker">
          <strong>{{ tr('当前账号/套餐/额度/EULA 尚未允许 AI 执行', 'Current account/plan/quota/EULA does not allow AI execution yet') }}</strong>
          <p>{{ entitlementReason }}</p>
          <p>{{ tr('Free Personal 本地核心能力仅要求接受当前许可条款；Personal Pro、BossAI Gateway 与所有商业用途仍需要有效 BossAI entitlement，其中商业用途必须为 Business。', 'Local core features in Free Personal require acceptance of the current license terms only. Personal Pro, BossAI Gateway, and all commercial use still require a valid BossAI entitlement, and commercial use requires Business.') }}</p>
        </div>

        <article class="panel">
          <div class="panel-head">
            <div><span class="step">01</span><h2>{{ tr('定义内容', 'Define content') }}</h2></div>
            <span class="hint">{{ tr('先给 AI 足够的业务背景', 'Give AI enough business context first') }}</span>
          </div>
          <label>
            <span>{{ tr('原始文案或素材', 'Source copy or material') }}</span>
            <textarea v-model="form.sourceText" rows="7" :placeholder="tr('粘贴已有口播、产品资料、门店介绍或你想表达的核心内容', 'Paste an existing script, product information, store introduction, or the core message you want to express')"></textarea>
          </label>
          <div class="grid two">
            <label><span>{{ tr('投放平台', 'Platform') }}</span><select v-model="form.platform"><option value="douyin">Douyin</option><option value="channels">WeChat Channels</option><option value="xiaohongshu">Xiaohongshu</option><option value="kuaishou">Kuaishou</option></select></label>
            <label><span>{{ tr('目标字数', 'Target length') }}</span><input v-model.number="form.targetChars" type="number" min="80" max="1600" /></label>
            <label><span>{{ tr('行业 / 人设', 'Industry / persona') }}</span><input v-model="form.industryPersona" :placeholder="tr('例如：餐饮老板、家装顾问', 'e.g. restaurant owner, home renovation advisor')" /></label>
            <label><span>{{ tr('产品 / 服务', 'Product / service') }}</span><input v-model="form.productBusiness" :placeholder="tr('你卖什么', 'What do you sell?')" /></label>
            <label><span>{{ tr('核心卖点', 'Key selling points') }}</span><input v-model="form.sellingPoints" :placeholder="tr('客户为什么要选你', 'Why should customers choose you?')" /></label>
            <label><span>{{ tr('表达风格', 'Tone') }}</span><input v-model="form.toneStyle" :placeholder="tr('专业、直接、接地气……', 'Professional, direct, conversational…')" /></label>
          </div>
          <button class="primary" :disabled="busy || !rewriteAllowed || !form.sourceText.trim()" @click="rewrite">{{ busyAction === 'rewrite' ? tr('正在改写…', 'Rewriting…') : tr('AI 改写文案', 'Rewrite with AI') }}</button>
          <p v-if="executionAllowed && !rewriteAllowed" class="feature-lock">{{ tr('当前套餐未包含 AI 文案改写。', 'Your current plan does not include AI rewrite.') }}</p>
          <label>
            <span>{{ tr('最终口播文案', 'Final talking script') }}</span>
            <textarea v-model="form.scriptText" rows="9" :placeholder="tr('AI 改写结果会出现在这里，也可以手工调整', 'The AI rewrite appears here and can be edited manually')"></textarea>
          </label>
        </article>

        <article class="panel">
          <div class="panel-head">
            <div><span class="step">02</span><h2>{{ tr('使用已授权声音生成配音', 'Generate voiceover with an authorized voice') }}</h2></div>
            <span class="hint">{{ tr('本地 CosyVoice2 · 仅使用授权声音', 'Local CosyVoice2 · authorized voices only') }}</span>
          </div>

          <div class="policy-card">
            <strong>{{ tr('声音权利确认', 'Voice rights confirmation') }}</strong>
            <p>{{ tr('只上传你本人、公司拥有，或已经获得明确合成授权的参考声音。BossAI 不提供或默认启用来源不明的参考声音。', 'Upload only reference voices you own or are explicitly authorized to synthesize. BossAI does not provide or enable unknown-rights default voices.') }}</p>
          </div>

          <div class="grid two">
            <label>
              <span>{{ tr('声音名称', 'Voice name') }}</span>
              <input v-model="voiceDisplayName" :placeholder="tr('例如：品牌主理人授权音色', 'e.g. Authorized brand-owner voice')" />
            </label>
            <label>
              <span>{{ tr('上传参考声音 WAV', 'Upload reference WAV') }}</span>
              <input type="file" accept="audio/wav,.wav" @change="selectVoiceFile" />
            </label>
          </div>

          <label class="consent-row">
            <input v-model="voiceRightsConfirmed" type="checkbox" />
            <span>{{ tr('我确认对本次上传声音拥有与当前用途相匹配的合法使用和语音合成授权。', 'I confirm I have lawful voice-synthesis rights matching the intended use.') }}</span>
          </label>

          <div class="button-row">
            <button class="secondary" :disabled="busy || voiceUploading || !voiceFile || !voiceRightsConfirmed" @click="uploadAuthorizedVoice">{{ voiceUploading ? tr('正在上传…', 'Uploading…') : tr('保存授权声音', 'Save authorized voice') }}</button>
          </div>

          <label>
            <span>{{ tr('本机已授权声音', 'Authorized local voices') }}</span>
            <select v-model="form.voiceId">
              <option value="">{{ tr('请选择已授权声音', 'Select an authorized voice') }}</option>
              <option v-for="voice in voices" :key="itemId(voice)" :value="itemId(voice)">{{ itemName(voice, '授权声音') }}</option>
            </select>
          </label>

          <button class="primary" :disabled="busy || !ttsAllowed || !form.scriptText.trim() || !form.voiceId || !voiceRightsConfirmed" @click="makeVoice">{{ busyAction === 'tts' ? tr('正在生成配音…', 'Generating voiceover…') : tr('生成 CosyVoice2 配音', 'Generate CosyVoice2 voiceover') }}</button>
          <p v-if="executionAllowed && !ttsAllowed" class="feature-lock">{{ tr('当前套餐未包含授权声音配音。', 'Your current plan does not include voiceover generation.') }}</p>
          <div class="result-box"><span>{{ tr('配音', 'Voiceover') }}</span><code>{{ audioUrl || tr('尚未生成', 'Not generated') }}</code></div>
        </article>

        <article class="panel replacement-panel">
          <div class="panel-head">
            <div><span class="step">03</span><h2>{{ tr('授权数字人口播', 'Authorized digital-human video') }}</h2></div>
            <span class="hint">MuseTalk v1.5</span>
          </div>
          <div class="replacement-state">
            <div class="replacement-icon">M</div>
            <div>
              <strong>{{ digitalHumanSetup?.ready ? tr('MuseTalk 数字人已就绪', 'MuseTalk is ready') : tr('MuseTalk 运行环境待安装', 'MuseTalk runtime required') }}</strong>
              <p v-if="digitalHumanSetup?.ready">{{ tr('只使用你本人、公司拥有或已取得相应数字人合成授权的头像视频。BossAI 不提供来源不明的默认人物素材。', 'Use only avatar video you own or are authorized to synthesize. BossAI does not provide unknown-rights default avatar media.') }}</p>
              <p v-else>{{ digitalHumanMissingLabel }}</p>
            </div>
          </div>

          <template v-if="digitalHumanSetup?.ready">
            <div class="grid two">
              <label>
                <span>{{ tr('上传授权头像视频', 'Upload authorized avatar video') }}</span>
                <input type="file" accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm,.mkv" @change="selectAvatarFile" />
              </label>
              <label>
                <span>{{ tr('已登记素材', 'Registered asset') }}</span>
                <input :value="avatarId ? tr('已保存到 BossAI 本机素材库', 'Saved to local BossAI asset library') : tr('尚未上传', 'Not uploaded')" disabled />
              </label>
            </div>
            <label class="consent-row">
              <input v-model="avatarRightsConfirmed" type="checkbox" />
              <span>{{ tr('我确认对该人物形象和视频拥有与当前用途相匹配的合法使用及数字人合成授权。', 'I confirm I have lawful avatar/video rights matching the intended use.') }}</span>
            </label>
            <div class="button-row">
              <button class="secondary" :disabled="busy || avatarUploading || !avatarFile || !avatarRightsConfirmed" @click="uploadAuthorizedAvatar">{{ avatarUploading ? tr('正在保存…', 'Saving…') : tr('保存授权头像视频', 'Save authorized avatar') }}</button>
              <button class="primary" :disabled="busy || !digitalHumanAllowed || !avatarId || !audioUrl || !avatarRightsConfirmed" @click="makeDigitalHuman">{{ busyAction === 'musetalk' ? tr('正在生成数字人口播…', 'Generating digital human…') : tr('生成数字人口播', 'Generate digital human') }}</button>
              <p v-if="executionAllowed && !digitalHumanAllowed" class="feature-lock">{{ tr('当前套餐未包含数字人口播。', 'Your current plan does not include digital-human generation.') }}</p>
            </div>
            <div class="result-box"><span>{{ tr('数字人口播', 'Digital-human video') }}</span><code>{{ digitalHumanUrl || tr('尚未生成', 'Not generated') }}</code></div>
            <video v-if="digitalHumanUrl" class="result-video" controls :src="apiUrl(digitalHumanUrl)"></video>
          </template>
          <button v-else class="secondary" disabled>{{ tr('等待安装 MuseTalk 运行环境', 'Waiting for MuseTalk runtime') }}</button>
        </article>

        <article class="panel">
          <div class="panel-head">
            <div><span class="step">04</span><h2>{{ tr('生成成片并导出', 'Finalize and export') }}</h2></div>
            <span class="hint">{{ tr('已生成的本地成果不因套餐变化被锁定', 'Existing local results remain accessible if the plan changes') }}</span>
          </div>
          <div class="grid two">
            <label>
              <span>{{ tr('项目名称', 'Project name') }}</span>
              <input v-model.trim="projectName" maxlength="120" :placeholder="tr('例如：8月30日产品口播', 'e.g. Aug 30 product video')" />
            </label>
            <label>
              <span>{{ tr('成片来源', 'Video source') }}</span>
              <input :value="digitalHumanUrl ? tr('BossAI 数字人口播', 'BossAI digital human') : tr('请先完成数字人口播', 'Generate digital-human video first')" disabled />
            </label>
          </div>
          <div class="button-row">
            <button class="primary" :disabled="busy || !digitalHumanUrl" @click="finalizeVideo">{{ busyAction === 'finalize' ? tr('正在生成成片…', 'Finalizing…') : tr('生成最终成片', 'Finalize video') }}</button>
            <button class="secondary" :disabled="exportBusy || !finalVideoUrl || !desktopExportAvailable" @click="exportFinalVideo">{{ exportBusy ? tr('正在导出…', 'Exporting…') : tr('导出 MP4', 'Export MP4') }}</button>
          </div>
          <p v-if="!desktopExportAvailable" class="runtime-note">{{ tr('文件导出仅在 BossAI Video Agent 桌面应用中启用；浏览器预览不会获得本机任意文件写入权限。', 'File export is enabled only in the BossAI Video Agent desktop app; browser preview has no arbitrary local file-write permission.') }}</p>
          <div class="result-box final"><span>{{ tr('最终成片', 'Final video') }}</span><code>{{ finalVideoUrl || tr('尚未生成', 'Not generated') }}</code></div>
          <video v-if="finalVideoUrl" class="result-video" controls :src="apiUrl(finalVideoUrl)"></video>
        </article>

        <article class="panel">
          <div class="panel-head">
            <div><span class="step">05</span><h2>{{ tr('发布', 'Publishing') }}</h2></div>
            <span class="hint">{{ tr('自动发布继续 fail-closed', 'Automated publishing remains fail-closed') }}</span>
          </div>
          <div class="policy-card">
            <strong>{{ publishStatus?.automatedPublishAllowed ? tr('自动发布已连接', 'Automated publishing connected') : tr('自动发布尚未开放', 'Automated publishing not enabled') }}</strong>
            <p>{{ publishStatus?.reason || tr('等待读取 BossAI 发布治理状态。', 'Waiting for BossAI publishing-governance status.') }}</p>
          </div>
          <div class="grid two">
            <label>
              <span>{{ tr('目标平台', 'Target platform') }}</span>
              <select v-model="form.platform"><option value="douyin">抖音</option><option value="channels">视频号</option><option value="xiaohongshu">小红书</option><option value="kuaishou">快手</option></select>
            </label>
            <label>
              <span>{{ tr('当前发布模式', 'Publishing mode') }}</span>
              <input :value="publishStatus?.automatedPublishAllowed ? tr('BossAI 治理发布', 'BossAI governed publishing') : tr('本地导出 + 人工发布', 'Local export + manual publishing')" disabled />
            </label>
          </div>
          <div class="button-row">
            <button class="secondary" :disabled="busy || !finalVideoUrl" @click="preparePublish">{{ tr('检查发布条件', 'Check publishing conditions') }}</button>
          </div>
          <div v-if="publishPreparation" class="result-box final"><span>{{ tr('发布状态', 'Publishing status') }}</span><code>{{ publishPreparation.status }} · {{ publishPreparation.reason }}</code></div>
        </article>

        <p v-if="error" class="error-banner">{{ error }}</p>
        <p v-if="message" class="message-banner">{{ message }}</p>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import {
  acceptEula,
  apiUrl,
  authenticateAccount,
  getAccountSession,
  getDigitalHumanSetup,
  getEntitlement,
  getEulaStatus,
  getProduct,
  getRuntimeInstallCenter,
  hasLocalRuntimeControl,
  installRuntime,
  listVoices,
  logoutAccount,
  sendRegistrationChallenge,
  uploadAvatarVideo,
  uploadVoice,
} from './api.js'
import { videoCapabilities } from './capabilities/video-capability-adapter.js'

const screen = ref('home')
const product = ref(null)
const entitlement = ref(null)
const eulaStatus = ref(null)
const accountSession = ref(null)
const digitalHumanSetup = ref(null)
const runtimeCenter = ref(null)
const legalStatus = ref(null)
const runtimeLicenseAccepted = ref(false)
const runtimeInstallProfile = ref('gpu')
const runtimeInstallBusy = ref(false)
const runtimeInstallComponentId = ref('')
const runtimeInstallMessage = ref('')
const backendReady = ref(false)
const voices = ref([])
const busy = ref(false)
const busyAction = ref('')
const message = ref('')
const error = ref('')
const audioUrl = ref('')
const voiceFile = ref(null)
const voiceDisplayName = ref('')
const voiceRightsConfirmed = ref(false)
const voiceUploading = ref(false)
const avatarFile = ref(null)
const avatarId = ref('')
const avatarRightsConfirmed = ref(false)
const avatarUploading = ref(false)
const digitalHumanUrl = ref('')
const projectName = ref('')
const finalVideoUrl = ref('')
const finalDownloadName = ref('')
const exportBusy = ref(false)
const publishStatus = ref(null)
const publishPreparation = ref(null)
const authMode = ref('login')
const authBusy = ref(false)
const challengeBusy = ref(false)
const eulaBusy = ref(false)
const locale = ref(globalThis?.localStorage?.getItem('bossai-video-locale') === 'en' ? 'en' : 'zh-CN')
const accountForm = reactive({
  identifier: '',
  password: '',
  displayName: '',
  challengeId: '',
  verificationCode: '',
})

const form = reactive({
  sourceText: '',
  scriptText: '',
  platform: 'douyin',
  targetChars: 300,
  industryPersona: '',
  productBusiness: '',
  sellingPoints: '',
  toneStyle: '',
  voiceId: '',
})

function tr(zh, en) {
  return locale.value === 'en' ? en : zh
}
function setLocale(value) {
  locale.value = value === 'en' ? 'en' : 'zh-CN'
  globalThis?.localStorage?.setItem('bossai-video-locale', locale.value)
}

const previewUnlocked = import.meta.env.VITE_BOSSAI_COMMERCIAL_PREVIEW === '1'
const accountAuthenticated = computed(() => Boolean(accountSession.value?.authenticated))
const accountLabel = computed(() => {
  if (accountAuthenticated.value) return tr('已登录', 'Signed in')
  if (['not_configured', 'unavailable'].includes(accountSession.value?.sessionStatus)) return tr('BossAI OS 未连接', 'BossAI OS disconnected')
  if (accountSession.value?.sessionStatus === 'expired') return tr('登录已过期', 'Session expired')
  return tr('未登录', 'Signed out')
})
const executionAllowed = computed(() => Boolean(previewUnlocked || entitlement.value?.executionAllowed))
const entitledFeatures = computed(() => new Set(Array.isArray(entitlement.value?.features) ? entitlement.value.features : []))
const rewriteAllowed = computed(() => Boolean(previewUnlocked || (executionAllowed.value && entitledFeatures.value.has('video.rewrite'))))
const ttsAllowed = computed(() => Boolean(previewUnlocked || (executionAllowed.value && entitledFeatures.value.has('video.tts'))))
const digitalHumanAllowed = computed(() => Boolean(previewUnlocked || (executionAllowed.value && entitledFeatures.value.has('video.digital-human'))))
const tierLabel = computed(() => {
  const tier = String(entitlement.value?.tier || '')
  if (tier === 'free-personal') return 'Free Personal'
  if (tier === 'personal-pro') return 'Personal Pro'
  if (tier === 'business') return 'Business'
  if (tier === 'developer-preview') return tr('内部预览', 'Internal Preview')
  return tr('未识别', 'Unknown')
})
const localFreeMode = computed(() => Boolean(entitlement.value?.localFreeMode))
const quotaRemaining = computed(() => Number(entitlement.value?.quotaRemaining ?? 0))
const quotaDisplay = computed(() => localFreeMode.value ? tr('本地核心能力不计 BossAI Points', 'Local core features do not consume BossAI Points') : `${quotaRemaining.value} BossAI Points`)
const quotaResetLabel = computed(() => localFreeMode.value ? tr('本地模式无需额度恢复', 'No quota reset for local mode') : String(entitlement.value?.quotaResetAt || tr('由 BossAI 权威服务下发', 'Provided by BossAI authority')))
const deviceBindingLabel = computed(() => localFreeMode.value ? tr('本地免费模式无需绑定', 'Not required for local free mode') : (entitlement.value?.deviceRegistered ? tr('已授权', 'Authorized') : tr('未授权', 'Not authorized')))
const businessUseAllowed = computed(() => Boolean(entitlement.value?.businessUseAllowed))
const eulaAccepted = computed(() => Boolean(eulaStatus.value?.accepted || entitlement.value?.eulaAccepted))
const entitlementLabel = computed(() => {
  if (previewUnlocked) return tr('内部预览', 'Internal Preview')
  if (!backendReady.value) return tr('本地服务未连接', 'Local service disconnected')
  if (entitlement.value?.status === 'local_free') return tr('Free Personal · 本地', 'Free Personal · Local')
  if (entitlement.value?.status === 'account_required') return tr('请登录 BossAI', 'Sign in to BossAI')
  if (entitlement.value?.status === 'eula_required') return tr('请接受许可协议', 'Accept license terms')
  if (entitlement.value?.status === 'unconfigured') return tr('BossAI OS 未连接', 'BossAI OS disconnected')
  if (entitlement.value?.status === 'quota_exhausted') return tr('本月额度已用完', 'Monthly quota exhausted')
  if (entitlement.value?.status === 'quota_frozen') return tr('额度已冻结', 'Quota frozen')
  if (entitlement.value?.status === 'device_required') return tr('设备未授权', 'Device not authorized')
  if (entitlement.value?.status === 'unknown_plan') return tr('套餐未识别', 'Unknown plan')
  if (executionAllowed.value) return tierLabel.value
  return tr('授权受限', 'Restricted')
})
const entitlementReason = computed(() => entitlement.value?.reason || tr('Free Personal 可在本地免费使用；需要 Pro、Gateway 或商业用途时再登录 BossAI。', 'Free Personal can be used locally for free. Sign in to BossAI only when you need Pro, Gateway, or commercial use.'))
const digitalHumanMissingLabel = computed(() => {
  const missing = Array.isArray(digitalHumanSetup.value?.missing) ? digitalHumanSetup.value.missing : []
  if (!missing.length) return 'MuseTalk 本地运行环境尚未完成配置。'
  const labels = {
    adapter: '数字人适配器',
    'model-runtime': 'MuseTalk 模型文件',
    'python-runtime': 'MuseTalk Python 运行环境',
    'ffmpeg-runtime': 'FFmpeg 运行环境',
    'runtime-component': 'MuseTalk 运行组件',
  }
  return `缺少：${missing.map((item) => labels[item] || item).join('、')}`
})
const runtimeControlAvailable = computed(() => hasLocalRuntimeControl())
const runtimeItems = computed(() => {
  const center = runtimeCenter.value || {}
  const support = center.support || {}
  const components = center.components || {}
  const python = support.python310 || {}
  const ffmpeg = support.ffmpeg || {}
  const qwen = components.qwen || {}
  const cosy = components.cosyvoice2 || {}
  const muse = components.musetalk || {}
  return [
    {
      id: 'python310',
      name: 'BossAI Python 3.10',
      description: tr('独立安装到 BossAI 本机目录，不修改系统 PATH。', 'Installed into a dedicated local BossAI directory without changing system PATH.'),
      ready: Boolean(python.ready),
      installable: Boolean(center.powershellReady && python.installerAvailable),
      blockedReason: center.powershellReady ? '' : tr('缺少 PowerShell', 'PowerShell required'),
    },
    {
      id: 'qwen',
      name: tr('Qwen 本地文案引擎', 'Qwen local writing engine'),
      description: tr('固定官方版本，用于本地文案生成与改写。', 'Pinned official runtime for local script generation and rewrite.'),
      ready: Boolean(qwen.ready),
      installable: Boolean(qwen.installable),
      blockedReason: qwen.installable ? '' : tr('需要 PowerShell', 'PowerShell required'),
    },
    {
      id: 'cosyvoice2',
      name: tr('CosyVoice2 配音引擎', 'CosyVoice2 voiceover engine'),
      description: tr('固定官方版本，只使用客户授权或 BossAI 自有声音。', 'Pinned official runtime; use only customer-authorized or BossAI-owned voices.'),
      ready: Boolean(cosy.ready),
      installable: Boolean(cosy.installable),
      blockedReason: python.ready ? '' : tr('先安装 Python 3.10', 'Install Python 3.10 first'),
    },
    {
      id: 'musetalk',
      name: tr('MuseTalk 数字人引擎', 'MuseTalk digital-human engine'),
      description: tr('用于客户授权人物视频的数字人口播合成。', 'Creates talking-avatar video from authorized customer media.'),
      ready: Boolean(muse.ready),
      installable: Boolean(muse.installable),
      blockedReason: !python.ready ? tr('先安装 Python 3.10', 'Install Python 3.10 first') : !ffmpeg.ready ? tr('需要 FFmpeg', 'FFmpeg required') : '',
    },
  ]
})
const allCoreRuntimesReady = computed(() => runtimeItems.value.every((item) => item.ready))
const desktopLegalAvailable = computed(() => Boolean(globalThis?.bossaiDesktop?.legalStatus && globalThis?.bossaiDesktop?.openLegalDocument))
const desktopExportAvailable = computed(() => Boolean(globalThis?.bossaiDesktop?.exportFinalVideo))
const legalReleaseReady = computed(() => Boolean(legalStatus.value?.approvedReleaseBundlePresent))
const legalDocuments = computed(() => {
  const available = legalStatus.value?.documents || {}
  return [
    { id: 'eula', name: tr('最终用户许可协议 EULA', 'End User License Agreement'), description: tr('当前安装版许可、套餐和使用限制。', 'Current packaged-product license, plan and usage terms.'), available: Boolean(available.eula) },
    { id: 'sourceLicense', name: tr('当前源码许可', 'Current Source License'), description: tr('个人/非商业源码使用许可及商业使用授权边界。', 'Personal/non-commercial source grant and commercial-use authorization boundary.'), available: Boolean(available.sourceLicense) },
    { id: 'historicalLicense', name: tr('历史 MIT 许可说明', 'Historical MIT License'), description: tr('保留此前已公开 MIT 版本的既有授权事实；不声明撤回。', 'Preserves the historical MIT grant for previously published versions; no revocation claim.'), available: Boolean(available.historicalLicense) },
    { id: 'commercialLicense', name: tr('Business 商业许可', 'Business Commercial License'), description: tr('商业用途、企业部署与合同授权边界。', 'Commercial-use, enterprise deployment and contractual licensing boundary.'), available: Boolean(available.commercialLicense) },
    { id: 'terms', name: tr('服务条款', 'Terms of Service'), description: tr('账号、订阅、额度、服务与退款边界。', 'Account, subscription, quota, service and refund terms.'), available: Boolean(available.terms) },
    { id: 'privacy', name: tr('隐私说明', 'Privacy Notice'), description: tr('本地数据、账号商业状态与云端处理边界。', 'Local data, account commercial state and cloud-processing boundary.'), available: Boolean(available.privacy) },
    { id: 'voiceAvatar', name: tr('声音与人物素材授权确认', 'Voice & Avatar Authorization'), description: tr('声音、肖像与人物视频合法授权确认。', 'Lawful authorization for voice, likeness and avatar media.'), available: Boolean(available.voiceAvatar) },
    { id: 'support', name: tr('安装与支持说明', 'Installation & Support'), description: tr('运行环境、安装、升级和支持说明。', 'Runtime, installation, upgrade and support information.'), available: Boolean(available.support) },
    { id: 'notices', name: tr('第三方组件说明', 'Third-party Notices'), description: tr('第三方运行时、模型和许可证边界。', 'Third-party runtime, model and license boundaries.'), available: Boolean(available.notices) },
  ]
})

function normalizeList(value) {
  if (Array.isArray(value)) return value
  if (Array.isArray(value?.items)) return value.items
  if (Array.isArray(value?.data)) return value.data
  return []
}
function itemId(item) { return String(item?.id || item?.voiceId || '') }
function itemName(item, fallback) { return String(item?.name || item?.title || item?.displayName || item?.fileName || item?.filename || itemId(item) || fallback) }
function isBlockedDefaultVoice(item) {
  const id = itemId(item).trim().toLowerCase()
  return !id || ['zst', '__default__', 'default'].includes(id)
}

function selectVoiceFile(event) {
  const [file] = Array.from(event?.target?.files || [])
  voiceFile.value = file || null
}

function selectAvatarFile(event) {
  const [file] = Array.from(event?.target?.files || [])
  avatarFile.value = file || null
  avatarId.value = ''
  digitalHumanUrl.value = ''
  finalVideoUrl.value = ''
  finalDownloadName.value = ''
  publishPreparation.value = null
}

async function refreshVoices() {
  const result = await listVoices()
  voices.value = normalizeList(result).filter((item) => !isBlockedDefaultVoice(item))
  if (form.voiceId && !voices.value.some((item) => itemId(item) === form.voiceId)) form.voiceId = ''
}

async function uploadAuthorizedVoice() {
  if (!voiceFile.value || !voiceRightsConfirmed.value) return
  voiceUploading.value = true
  error.value = ''
  try {
    const result = await uploadVoice(voiceFile.value, voiceDisplayName.value)
    await refreshVoices()
    const uploadedId = itemId(result)
    if (uploadedId && voices.value.some((item) => itemId(item) === uploadedId)) form.voiceId = uploadedId
    message.value = tr('授权声音已保存到本机。', 'Authorized voice saved locally.')
  } catch (e) {
    error.value = e?.message || tr('声音上传失败', 'Voice upload failed')
  } finally {
    voiceUploading.value = false
  }
}

async function refreshLegalStatus() {
  if (!desktopLegalAvailable.value) {
    legalStatus.value = { approvedReleaseBundlePresent: false, documents: {} }
    return
  }
  try {
    legalStatus.value = await globalThis.bossaiDesktop.legalStatus()
  } catch {
    legalStatus.value = { approvedReleaseBundlePresent: false, documents: {} }
  }
}

async function openLegal(documentId) {
  if (!desktopLegalAvailable.value) return
  try {
    const result = await globalThis.bossaiDesktop.openLegalDocument(documentId)
    if (!result?.opened) error.value = tr('该法律文件尚未进入当前客户发行包。', 'This legal document is not in the current release bundle.')
  } catch (e) {
    error.value = e?.message || tr('无法打开法律文件', 'Unable to open legal document')
  }
}

async function refreshRuntimeCenter() {
  try {
    runtimeCenter.value = await getRuntimeInstallCenter()
  } catch (e) {
    runtimeCenter.value = null
    runtimeInstallMessage.value = e?.message || tr('无法读取 BossAI 运行环境状态。', 'Unable to read BossAI runtime status.')
  }
}

async function installRuntimeComponent(component) {
  if (!runtimeLicenseAccepted.value || runtimeInstallBusy.value) return
  runtimeInstallBusy.value = true
  runtimeInstallComponentId.value = component
  runtimeInstallMessage.value = tr('正在准备安装…', 'Preparing installation…')
  error.value = ''
  try {
    await installRuntime(component, {
      profile: runtimeInstallProfile.value,
      acceptLicense: true,
      onProgress: (job) => {
        const lastLog = Array.isArray(job?.logs) && job.logs.length ? job.logs[job.logs.length - 1] : ''
        runtimeInstallMessage.value = String(lastLog || job?.message || tr('正在安装…', 'Installing…'))
      },
    })
    runtimeInstallMessage.value = tr('运行环境安装完成。', 'Runtime installation completed.')
    await refreshRuntimeCenter()
    await refreshStatus()
  } catch (e) {
    error.value = e?.message || tr('运行环境安装失败', 'Runtime installation failed')
    runtimeInstallMessage.value = error.value
  } finally {
    runtimeInstallBusy.value = false
    runtimeInstallComponentId.value = ''
  }
}

async function refreshStatus() {
  error.value = ''
  try {
    const [productResult, entitlementResult, eulaResult, digitalHumanResult, accountResult, publishResult] = await Promise.all([
      getProduct(),
      getEntitlement(),
      getEulaStatus(),
      getDigitalHumanSetup(),
      getAccountSession(),
      videoCapabilities.publishStatus(),
    ])
    product.value = productResult
    entitlement.value = entitlementResult
    eulaStatus.value = eulaResult
    digitalHumanSetup.value = digitalHumanResult
    accountSession.value = accountResult
    publishStatus.value = publishResult
    backendReady.value = true
    await refreshRuntimeCenter()
  } catch (e) {
    backendReady.value = false
    error.value = e?.message || tr('无法连接本地 BossAI Video Agent 服务。', 'Unable to connect to the local BossAI Video Agent service.')
  }
}

function normalizedRegistrationIdentifier() {
  const value = accountForm.identifier.trim()
  if (/^1\d{10}$/.test(value)) return `+86${value}`
  return value
}

async function requestAccountChallenge() {
  challengeBusy.value = true
  error.value = ''
  message.value = ''
  try {
    const identifier = normalizedRegistrationIdentifier()
    const channel = identifier.includes('@') ? 'email' : 'phone'
    const result = await sendRegistrationChallenge({ channel, identifier, locale: locale.value })
    accountForm.challengeId = String(result?.challengeId || result?.id || '')
    if (!accountForm.challengeId) throw new Error('BossAI OS 未返回注册 challenge ID')
    message.value = tr('验证码已发送，请在有效期内完成注册。', 'Verification code sent. Complete registration before it expires.')
  } catch (e) {
    error.value = e?.message || tr('验证码发送失败', 'Failed to send verification code')
  } finally {
    challengeBusy.value = false
  }
}

async function submitAccount() {
  authBusy.value = true
  error.value = ''
  message.value = ''
  try {
    const payload = {
      mode: authMode.value,
      identifier: authMode.value === 'register' ? normalizedRegistrationIdentifier() : accountForm.identifier.trim(),
      password: accountForm.password,
    }
    if (authMode.value === 'register') {
      payload.displayName = accountForm.displayName.trim()
      payload.challengeId = accountForm.challengeId.trim()
      payload.verificationCode = accountForm.verificationCode.trim()
    }
    accountSession.value = await authenticateAccount(payload)
    accountForm.password = ''
    accountForm.verificationCode = ''
    await refreshStatus()
    message.value = authMode.value === 'login' ? tr('BossAI 账号登录成功。', 'Signed in to BossAI.') : tr('BossAI 账号创建并登录成功。', 'BossAI account created and signed in.')
  } catch (e) {
    error.value = e?.message || tr('BossAI 账号操作失败', 'BossAI account operation failed')
  } finally {
    authBusy.value = false
  }
}

async function signOutAccount() {
  authBusy.value = true
  error.value = ''
  try {
    await logoutAccount()
    accountSession.value = null
    entitlement.value = null
    await refreshStatus()
    message.value = tr('已退出 BossAI 账号。', 'Signed out of BossAI.')
  } catch (e) {
    error.value = e?.message || tr('退出登录失败', 'Sign-out failed')
  } finally {
    authBusy.value = false
  }
}

async function acceptCurrentEula() {
  eulaBusy.value = true
  error.value = ''
  try {
    eulaStatus.value = await acceptEula(locale.value)
    await refreshStatus()
    message.value = tr('已接受当前版本 EULA。', 'The current-version EULA has been accepted.')
  } catch (e) {
    error.value = e?.message || tr('EULA 接受失败', 'EULA acceptance failed')
  } finally {
    eulaBusy.value = false
  }
}

async function openUpgrade() {
  error.value = ''
  try {
    const result = await globalThis?.bossaiDesktop?.openUpgrade?.()
    if (!result?.opened) throw new Error(result?.reason || tr('无法打开升级入口', 'Unable to open upgrade page'))
  } catch (e) {
    error.value = e?.message || tr('无法打开升级入口', 'Unable to open upgrade page')
  }
}

async function run(action, name) {
  busy.value = true
  busyAction.value = name
  error.value = ''
  message.value = ''
  try {
    return await action()
  } catch (e) {
    error.value = e?.message || tr('任务执行失败', 'Task failed')
    throw e
  } finally {
    busy.value = false
    busyAction.value = ''
  }
}

async function rewrite() {
  await run(async () => {
    const result = await videoCapabilities.rewrite(form.sourceText, { ...form, targetLanguage: locale.value === 'en' ? 'en' : 'zh' })
    form.scriptText = String(result?.rewriteText || result || '')
    message.value = tr('文案已生成，可以继续调整后制作配音。', 'Script generated. You can edit it before creating voiceover.')
  }, 'rewrite').catch(() => {})
}

async function makeVoice() {
  await run(async () => {
    const result = await videoCapabilities.tts({ text: form.scriptText, voiceId: form.voiceId, language: locale.value === 'en' ? 'en' : 'zh' }, (job) => {
      message.value = job?.message || tr('正在生成 CosyVoice2 配音…', 'Generating CosyVoice2 voiceover…')
    })
    audioUrl.value = result?.fileUrl || ''
    digitalHumanUrl.value = ''
    finalVideoUrl.value = ''
    finalDownloadName.value = ''
    publishPreparation.value = null
    message.value = tr('CosyVoice2 配音生成完成。', 'CosyVoice2 voiceover completed.')
  }, 'tts').catch(() => {})
}

async function uploadAuthorizedAvatar() {
  if (!avatarFile.value || !avatarRightsConfirmed.value) return
  avatarUploading.value = true
  error.value = ''
  try {
    const result = await uploadAvatarVideo(avatarFile.value)
    avatarId.value = String(result?.avatarId || '')
    digitalHumanUrl.value = ''
    message.value = tr('授权头像视频已保存到 BossAI 本机素材库。', 'Authorized avatar video saved to the local BossAI asset library.')
  } catch (e) {
    error.value = e?.message || tr('头像视频上传失败', 'Avatar video upload failed')
  } finally {
    avatarUploading.value = false
  }
}

async function makeDigitalHuman() {
  await run(async () => {
    const result = await videoCapabilities.digitalHuman({
      avatarId: avatarId.value,
      audioUrl: audioUrl.value,
    }, (job) => {
      message.value = job?.message || tr('正在生成 MuseTalk 数字人口播…', 'Generating MuseTalk digital-human video…')
    })
    digitalHumanUrl.value = String(result?.fileUrl || '')
    finalVideoUrl.value = ''
    finalDownloadName.value = ''
    publishPreparation.value = null
    message.value = tr('MuseTalk 数字人口播生成完成。', 'MuseTalk digital-human video completed.')
  }, 'musetalk').catch(() => {})
}

async function finalizeVideo() {
  await run(async () => {
    const result = await videoCapabilities.renderVideo({
      sourceUrl: digitalHumanUrl.value,
      projectName: projectName.value,
    })
    finalVideoUrl.value = String(result?.fileUrl || '')
    finalDownloadName.value = String(result?.downloadName || 'BossAI-Video.mp4')
    publishPreparation.value = null
    message.value = tr('最终成片已生成并保存在 BossAI 本机数据目录。', 'Final video generated and saved in the local BossAI data directory.')
  }, 'finalize').catch(() => {})
}

async function exportFinalVideo() {
  if (!desktopExportAvailable.value || !finalVideoUrl.value) return
  exportBusy.value = true
  error.value = ''
  try {
    const result = await globalThis.bossaiDesktop.exportFinalVideo(
      finalVideoUrl.value,
      finalDownloadName.value || 'BossAI-Video.mp4',
    )
    if (result?.canceled) {
      message.value = tr('已取消导出。', 'Export canceled.')
    } else if (result?.exported) {
      message.value = tr(`成片已导出：${result.filePath}`, `Video exported: ${result.filePath}`)
    } else {
      throw new Error(result?.reason || '成片导出失败')
    }
  } catch (e) {
    error.value = e?.message || tr('成片导出失败', 'Video export failed')
  } finally {
    exportBusy.value = false
  }
}

async function preparePublish() {
  await run(async () => {
    publishPreparation.value = await videoCapabilities.publish({
      finalVideoUrl: finalVideoUrl.value,
      platform: form.platform,
    })
    message.value = publishPreparation.value?.automatedPublishAllowed
      ? '发布条件已满足。'
      : '自动发布继续保持关闭；成片可正常导出并由用户手工发布。'
  }, 'publish').catch(() => {})
}

onMounted(async () => {
  await refreshLegalStatus()
  await refreshStatus()
  try {
    await refreshVoices()
  } catch {
    // Commercial UI can still load even when local voice storage is unavailable.
  }
})
</script>
