<template>
  <section class="home-grid">
    <article class="hero-card">
      <p class="kicker">BossAI Video Agent · 0.1.0</p>
      <h2>{{ tr('当前源码许可、历史 MIT 事实、服务条款和隐私边界都必须可直接查看。', 'The current source license, historical MIT facts, terms and privacy boundaries must be directly viewable.') }}</h2>
      <p>{{ tr('历史 MIT 版本的既有授权不撤回；新的正式 Windows 安装版从 EULA 向前适用。未批准的客户法律文件不会被冒充为正式条款。', 'Historical MIT grants are not revoked. The EULA applies prospectively to new formal Windows builds. Unapproved customer legal files are never presented as approved terms.') }}</p>
      <span :class="['status-badge', legalReleaseReady ? 'success' : 'warning']">
        {{ legalReleaseReady ? tr('客户法律包已批准', 'Customer legal bundle approved') : tr('客户法律包尚未批准', 'Customer legal bundle not yet approved') }}
      </span>
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
          <span :class="['runtime-state', item.available ? 'ready' : 'missing']">
            {{ item.available ? tr('可查看', 'Available') : tr('未进入发行包', 'Not in release bundle') }}
          </span>
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

    <article class="metric-card">
      <span>{{ tr('素材与音乐', 'Media & music') }}</span>
      <strong>{{ tr('不随产品分发', 'Never bundled') }}</strong>
      <p>{{ tr('BossAI 不附带参考声音、人物素材、背景音乐或字体文件。剪辑只使用你自己提供的素材和本机已安装字体。', 'BossAI bundles no reference voices, avatar media, background music or font files. Editing uses only media you supply and fonts already installed on this machine.') }}</p>
    </article>
  </section>
</template>

<script setup>
import { tr } from '../i18n.js'
import { desktopLegalAvailable, legalDocuments, legalReleaseReady, openLegal } from '../stores/session.js'
</script>
