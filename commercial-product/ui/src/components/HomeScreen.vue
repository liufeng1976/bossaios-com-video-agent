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
        <p>{{ tr('文案改写、标题话题、授权音色配音、数字人口播、字幕/背景音乐/画中画剪辑、封面制作，一个流程走完。', 'Rewrite the script, generate titles and hashtags, produce voiceover and the digital human, edit in subtitles, music and picture-in-picture, then build the cover — all in one flow.') }}</p>
        <button class="primary" :disabled="!executionAllowed" @click="goTo('studio')">
          {{ tr('开始生产视频', 'Start producing') }}
        </button>
      </article>

      <article class="feature-card active">
        <div class="badge">{{ tr('已开放', 'Available') }}</div>
        <h3>{{ tr('音色、数字人与素材库', 'Voices, avatars & media library') }}</h3>
        <p>{{ tr('统一管理已授权的音色、数字人头像视频与画中画素材：试听、预览、重命名、删除。', 'Manage your authorized voices, avatar clips and picture-in-picture media in one place: audition, preview, rename and delete.') }}</p>
        <button class="primary" @click="goTo('assets')">{{ tr('管理素材', 'Manage assets') }}</button>
      </article>

      <article class="feature-card active">
        <div class="badge">{{ tr('已开放', 'Available') }}</div>
        <h3>{{ tr('发布平台账号', 'Publishing accounts') }}</h3>
        <p>{{ tr('记录抖音、视频号、小红书与快手的账号备注；自动发布在获得授权前继续保持关闭，成片可随时手动导出发布。', 'Note your Douyin, Channels, Xiaohongshu and Kuaishou accounts. Automated publishing stays disabled until authorized — export and publish manually anytime.') }}</p>
        <button class="primary" @click="goTo('publishing')">{{ tr('管理发布账号', 'Manage accounts') }}</button>
      </article>

      <article class="feature-card disabled">
        <div class="badge muted-badge">{{ tr('未开放', 'Planned') }}</div>
        <h3>{{ tr('团队协作矩阵', 'Team collaboration') }}</h3>
        <p>{{ tr('多账号、多任务的团队化批量生产与协作，规划中。', 'Multi-account, multi-task team production and collaboration is in planning.') }}</p>
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
