<template>
  <section class="home-layout">
    <article class="hero-card">
      <p class="kicker">Free Personal · Personal Pro · Business</p>
      <h2>{{ tr('打开就开始做视频，配置留在设置里。', 'Open the app and start producing. Configuration stays in Settings.') }}</h2>
      <p>{{ entitlementReason }}</p>
      <div class="hero-actions">
        <button class="primary" :disabled="!executionAllowed" @click="goTo('studio')">
          {{ tr('开始制作视频', 'Start creating') }}
        </button>
        <button class="secondary" @click="goTo('settings')">{{ tr('打开设置', 'Open settings') }}</button>
        <span v-if="previewUnlocked" class="preview-note">{{ tr('内部预览模式', 'Internal preview') }}</span>
      </div>
    </article>

    <article class="readiness-card">
      <div class="panel-head">
        <div>
          <span class="step">{{ tr('状态', 'Status') }}</span>
          <h2>{{ tr('准备情况', 'Readiness') }}</h2>
        </div>
        <span :class="['status-badge', readyToCreate ? 'success' : 'warning']">
          {{ readyToCreate ? tr('可以开始制作', 'Ready to create') : tr('还需完成设置', 'Setup incomplete') }}
        </span>
      </div>
      <ul class="readiness-list">
        <li v-for="item in readinessChecklist" :key="item.id">
          <span :class="['readiness-dot', item.ready ? 'ok' : item.optional ? 'optional' : 'todo']"></span>
          <div>
            <strong>{{ item.label }}</strong>
            <span>{{ item.hint }}</span>
          </div>
          <button v-if="!item.ready" class="secondary" @click="goTo('settings')">{{ tr('去设置', 'Set up') }}</button>
          <span v-else class="runtime-state ready">{{ tr('已就绪', 'Ready') }}</span>
        </li>
      </ul>
    </article>

    <h2 class="section-title">{{ tr('功能入口', 'What you can do') }}</h2>
    <div class="feature-cards">
      <article class="feature-card active">
        <div class="badge">{{ tr('核心', 'Core') }}</div>
        <h3>{{ tr('AI 口播视频工厂', 'AI Talking-Video Studio') }}</h3>
        <p>{{ tr('文案改写、授权音色配音、数字人口播、字幕与背景音乐合成、导出成片，一个流程走完。', 'Rewrite the script, generate voiceover with an authorized voice, produce the digital human, burn in subtitles and music, then export.') }}</p>
        <button class="primary" :disabled="!executionAllowed" @click="goTo('studio')">
          {{ tr('开始生产视频', 'Start producing') }}
        </button>
      </article>

      <article class="feature-card disabled">
        <div class="badge muted-badge">{{ tr('未开放', 'Planned') }}</div>
        <h3>{{ tr('标题、封面与素材库', 'Titles, covers & media library') }}</h3>
        <p>{{ tr('自动生成标题话题、封面成图，并统一管理数字人、音色与画中画素材。', 'Generate titles and hashtags, build covers, and manage avatars, voices and picture-in-picture media in one place.') }}</p>
        <button disabled>{{ tr('规划中', 'In planning') }}</button>
      </article>

      <article class="feature-card disabled">
        <div class="badge muted-badge">{{ tr('未开放', 'Planned') }}</div>
        <h3>{{ tr('多平台发布与团队矩阵', 'Multi-platform publishing & teams') }}</h3>
        <p>{{ tr('绑定抖音、视频号、小红书与快手账号，批量发布并支持团队协作。自动发布在获得授权前保持关闭。', 'Bind Douyin, Channels, Xiaohongshu and Kuaishou accounts for batch publishing and team collaboration. Automated publishing stays disabled until authorized.') }}</p>
        <button disabled>{{ tr('规划中', 'In planning') }}</button>
      </article>
    </div>
  </section>
</template>

<script setup>
import { tr } from '../i18n.js'
import {
  entitlementReason,
  executionAllowed,
  previewUnlocked,
  readinessChecklist,
  readyToCreate,
} from '../stores/session.js'
import { goTo } from '../stores/ui.js'
</script>
