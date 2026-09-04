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
        <button
          v-for="item in navItems"
          :key="item.id"
          :class="{ active: screen === item.id }"
          @click="goTo(item.id)"
        >{{ item.label }}</button>
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
          <h1>{{ screenTitle }}</h1>
        </div>
        <div class="top-actions">
          <button class="secondary" :class="{ active: locale === 'zh-CN' }" @click="setLocale('zh-CN')">中文</button>
          <button class="secondary" :class="{ active: locale === 'en' }" @click="setLocale('en')">English</button>
          <span :class="['status-badge', executionAllowed ? 'success' : 'warning']">{{ entitlementLabel }}</span>
          <button class="secondary" @click="refreshStatus">{{ tr('刷新', 'Refresh') }}</button>
        </div>
      </header>

      <HomeScreen v-if="screen === 'home'" />
      <AssetsScreen v-else-if="screen === 'assets'" />
      <SettingsScreen v-else-if="screen === 'settings'" />
      <LegalScreen v-else-if="screen === 'legal'" />
      <StudioScreen v-else />

      <p v-if="error" class="error-banner">{{ error }}</p>
      <p v-if="message" class="message-banner">{{ message }}</p>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'

import AssetsScreen from './components/AssetsScreen.vue'
import HomeScreen from './components/HomeScreen.vue'
import LegalScreen from './components/LegalScreen.vue'
import SettingsScreen from './components/SettingsScreen.vue'
import StudioScreen from './components/StudioScreen.vue'
import { locale, setLocale, tr } from './i18n.js'
import {
  backendReady,
  entitlementLabel,
  executionAllowed,
  refreshLegalStatus,
  refreshStatus,
} from './stores/session.js'
import { refreshAssets } from './stores/assets.js'
import { error, goTo, message, screen } from './stores/ui.js'

const navItems = computed(() => [
  { id: 'home', label: tr('首页', 'Home') },
  { id: 'studio', label: tr('AI 口播视频', 'AI Video Studio') },
  { id: 'assets', label: tr('素材管理', 'Assets') },
  { id: 'settings', label: tr('设置', 'Settings') },
  { id: 'legal', label: tr('条款与隐私', 'Legal & Privacy') },
])

const screenTitle = computed(() => {
  const titles = {
    home: tr('本地 AI 视频生产工作台', 'Local AI Video Production Workspace'),
    studio: tr('AI 口播视频生产', 'AI Talking Video Studio'),
    assets: tr('音色与数字人素材库', 'Voice & Avatar Library'),
    settings: tr('设置', 'Settings'),
    legal: tr('条款、隐私与许可', 'Terms, Privacy & Licensing'),
  }
  return titles[screen.value] || titles.home
})

onMounted(async () => {
  await refreshLegalStatus()
  await refreshStatus()
  try {
    await refreshAssets()
  } catch {
    // The commercial UI still loads when local asset storage is unavailable.
  }
})
</script>
