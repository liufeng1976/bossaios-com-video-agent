<template>
  <section class="settings-layout">
    <nav class="settings-nav">
      <button
        v-for="section in sections"
        :key="section.id"
        :class="{ active: activeSection === section.id }"
        @click="activeSection = section.id"
      >
        <strong>{{ section.title }}</strong>
        <span :class="['runtime-state', section.ready ? 'ready' : 'missing']">{{ section.state }}</span>
      </button>
    </nav>

    <div class="settings-body">
      <article v-show="activeSection === 'account'" class="account-card">
        <div class="panel-head">
          <div><h2>{{ tr('BossAI 账号', 'BossAI Account') }}</h2></div>
          <span :class="['status-badge', accountAuthenticated ? 'success' : 'warning']">{{ accountLabel }}</span>
        </div>

        <template v-if="accountAuthenticated">
          <div class="account-summary">
            <div>
              <span>{{ tr('账号', 'Account') }}</span>
              <strong>{{ accountSession?.account?.maskedIdentifier || accountSession?.account?.displayName || tr('已登录', 'Signed in') }}</strong>
            </div>
            <div>
              <span>{{ tr('当前套餐', 'Current plan') }}</span>
              <strong>{{ tierLabel }} · {{ entitlement?.planName || tr('等待同步', 'Syncing') }}</strong>
            </div>
            <div><span>{{ tr('剩余额度', 'Remaining quota') }}</span><strong>{{ quotaDisplay }}</strong></div>
          </div>
          <div class="account-summary">
            <div><span>{{ tr('额度恢复', 'Quota reset') }}</span><strong>{{ quotaResetLabel }}</strong></div>
            <div><span>{{ tr('设备绑定', 'Device binding') }}</span><strong>{{ deviceBindingLabel }}</strong></div>
            <div>
              <span>{{ tr('商业用途', 'Commercial use') }}</span>
              <strong>{{ businessUseAllowed ? tr('已授权', 'Licensed') : tr('需要 Business', 'Business required') }}</strong>
            </div>
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
            <label>
              <span>{{ tr('手机号或邮箱', 'Phone or email') }}</span>
              <input v-model.trim="accountForm.identifier" autocomplete="username" :placeholder="tr('手机号或 name@example.com', 'Phone or name@example.com')" />
            </label>
            <label>
              <span>{{ tr('密码', 'Password') }}</span>
              <input v-model="accountForm.password" type="password" autocomplete="current-password" :placeholder="tr('至少 8 位', 'At least 8 characters')" />
            </label>
            <label v-if="authMode === 'register'">
              <span>{{ tr('显示名称', 'Display name') }}</span>
              <input v-model.trim="accountForm.displayName" :placeholder="tr('你的姓名', 'Your name')" />
            </label>
            <label v-if="authMode === 'register'">
              <span>{{ tr('验证码', 'Verification code') }}</span>
              <div class="inline-field">
                <input v-model.trim="accountForm.verificationCode" inputmode="numeric" :placeholder="tr('验证码', 'Code')" />
                <button class="secondary" :disabled="challengeBusy || !accountForm.identifier" @click="requestAccountChallenge">
                  {{ challengeBusy ? tr('发送中…', 'Sending…') : tr('发送验证码', 'Send code') }}
                </button>
              </div>
            </label>
          </div>
          <p v-if="authMode === 'register'" class="account-help">{{ tr('中国大陆 11 位手机号会自动按 +86 处理。', '11-digit mainland China mobile numbers are normalized to +86.') }}</p>
          <button class="primary" :disabled="authBusy || !accountForm.identifier || accountForm.password.length < 8" @click="submitAccount">
            {{ authBusy ? tr('处理中…', 'Working…') : authMode === 'login' ? tr('登录 BossAI', 'Sign in to BossAI') : tr('创建 BossAI 账号', 'Create BossAI account') }}
          </button>
        </template>
      </article>

      <article v-show="activeSection === 'plan'" class="account-card">
        <div class="panel-head">
          <div><h2>{{ tr('套餐、额度与许可', 'Plan, quota & license') }}</h2></div>
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

      <article v-show="activeSection === 'license'" class="account-card">
        <div class="panel-head">
          <div><h2>{{ tr('软件许可 EULA', 'Software EULA') }}</h2></div>
          <span :class="['status-badge', eulaAccepted ? 'success' : 'warning']">{{ eulaAccepted ? tr('已接受', 'Accepted') : tr('待接受', 'Required') }}</span>
        </div>
        <p class="account-help">{{ tr('当前 BossAI 自有源码适用 BossAI Community Source License：个人/非商业用途免费，商业用途需要 BossAI 授权。历史上已按 MIT 发布的 revision 权利保持不变。', 'Current BossAI-owned source uses the BossAI Community Source License: personal/non-commercial use is free and commercial use requires BossAI authorization. Historical MIT-licensed revisions keep their existing rights.') }}</p>
        <div class="button-row">
          <button class="secondary" :disabled="!desktopLegalAvailable" @click="openLegal('eula')">{{ tr('查看 EULA', 'View EULA') }}</button>
          <button v-if="!eulaAccepted" class="primary" :disabled="eulaBusy" @click="acceptCurrentEula">
            {{ eulaBusy ? tr('保存中…', 'Saving…') : tr('接受当前版本 EULA', 'Accept current EULA') }}
          </button>
        </div>
      </article>

      <article v-show="activeSection === 'runtime'" class="runtime-card">
        <div class="panel-head">
          <div><h2>{{ tr('BossAI 运行环境中心', 'BossAI Runtime Center') }}</h2></div>
          <span :class="['status-badge', allCoreRuntimesReady ? 'success' : 'warning']">
            {{ allCoreRuntimesReady ? tr('核心环境已就绪', 'Core runtimes ready') : tr('需要安装', 'Installation required') }}
          </span>
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
            <span :class="['runtime-state', item.ready ? 'ready' : 'missing']">
              {{ item.ready ? tr('已就绪', 'Ready') : item.blockedReason || tr('未安装', 'Not installed') }}
            </span>
            <button
              class="secondary"
              :disabled="runtimeInstallBusy || item.ready || !runtimeControlAvailable || !runtimeLicenseAccepted || !item.installable"
              @click="installRuntimeComponent(item.id)"
            >
              {{ runtimeInstallBusy && runtimeInstallComponentId === item.id ? tr('安装中…', 'Installing…') : item.ready ? tr('已安装', 'Installed') : tr('安装', 'Install') }}
            </button>
          </div>

          <div class="runtime-row">
            <div class="runtime-identity">
              <strong>{{ tr('成片合成（FFmpeg）', 'Final-video composition (FFmpeg)') }}</strong>
              <span>{{ tr('字幕烧录、背景音乐混音与通栏标题需要本机 FFmpeg。', 'Burned-in subtitles, background-music mixing and the banner title need local FFmpeg.') }}</span>
            </div>
            <span :class="['runtime-state', composerReady ? 'ready' : 'missing']">
              {{ composerReady ? tr('已就绪', 'Ready') : composerMissingLabel }}
            </span>
            <button class="secondary" disabled>{{ composerReady ? tr('已就绪', 'Ready') : tr('随 MuseTalk 安装', 'With MuseTalk') }}</button>
          </div>
        </div>
        <p v-if="!runtimeControlAvailable" class="runtime-note">{{ tr('运行环境安装只允许从 BossAI Video Agent 桌面应用发起；浏览器页面无权执行本机安装。', 'Runtime installation is available only in the BossAI Video Agent desktop app; browser pages cannot install local runtimes.') }}</p>
        <p v-if="runtimeInstallMessage" class="runtime-log">{{ runtimeInstallMessage }}</p>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'

import { tr } from '../i18n.js'
import {
  accountAuthenticated,
  accountForm,
  accountLabel,
  accountSession,
  acceptCurrentEula,
  allCoreRuntimesReady,
  authBusy,
  authMode,
  businessUseAllowed,
  challengeBusy,
  composerReady,
  desktopLegalAvailable,
  deviceBindingLabel,
  entitlement,
  entitlementLabel,
  eulaAccepted,
  eulaBusy,
  executionAllowed,
  installRuntimeComponent,
  openLegal,
  openUpgrade,
  quotaDisplay,
  quotaResetLabel,
  refreshStatus,
  requestAccountChallenge,
  runtimeControlAvailable,
  runtimeInstallBusy,
  runtimeInstallComponentId,
  runtimeInstallMessage,
  runtimeInstallProfile,
  runtimeItems,
  runtimeLicenseAccepted,
  signOutAccount,
  submitAccount,
  tierLabel,
  videoAssets,
} from '../stores/session.js'

const activeSection = ref('runtime')

const composerMissingLabel = computed(() => {
  const missing = videoAssets.value?.composer?.missing || []
  if (!missing.length) return tr('未就绪', 'Not ready')
  const labels = {
    'ffmpeg-runtime': 'FFmpeg',
    'ffprobe-runtime': 'FFprobe',
    'ffmpeg-drawtext-filter': tr('FFmpeg 字幕滤镜', 'FFmpeg drawtext filter'),
  }
  return tr('缺少：', 'Missing: ') + missing.map((item) => labels[item] || item).join(tr('、', ', '))
})

const sections = computed(() => [
  {
    id: 'runtime',
    title: tr('运行环境', 'Runtimes'),
    ready: allCoreRuntimesReady.value && composerReady.value,
    state: allCoreRuntimesReady.value && composerReady.value ? tr('已就绪', 'Ready') : tr('需要安装', 'Setup needed'),
  },
  {
    id: 'license',
    title: tr('软件许可', 'Licence'),
    ready: eulaAccepted.value,
    state: eulaAccepted.value ? tr('已接受', 'Accepted') : tr('待接受', 'Required'),
  },
  {
    id: 'account',
    title: tr('BossAI 账号', 'Account'),
    ready: accountAuthenticated.value,
    state: accountLabel.value,
  },
  {
    id: 'plan',
    title: tr('套餐与额度', 'Plan & quota'),
    ready: executionAllowed.value,
    state: entitlementLabel.value,
  },
])
</script>
