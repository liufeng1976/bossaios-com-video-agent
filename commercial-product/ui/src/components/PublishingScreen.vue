<template>
  <section class="publishing-layout">
    <article class="hero-card">
      <p class="kicker">{{ tr('发布平台', 'Publishing platforms') }}</p>
      <h2>{{ tr('自动发布尚未开放，这里先记录你计划使用的账号。', 'Automated publishing is not enabled yet — use this page to note the accounts you plan to use.') }}</h2>
      <p>{{ publishReasonLabel }}</p>
      <span :class="['status-badge', publishStatus?.automatedPublishAllowed ? 'success' : 'warning']">
        {{ publishStatus?.automatedPublishAllowed ? tr('自动发布已连接', 'Automated publishing connected') : tr('自动发布尚未开放', 'Automated publishing not enabled') }}
      </span>
    </article>

    <div class="publishing-grid">
      <article v-for="[value, zh, en] in PLATFORMS" :key="value" class="account-card publishing-card">
        <div class="panel-head">
          <div><h2>{{ tr(zh, en) }}</h2></div>
          <span :class="['status-badge', accountLabels[value] ? 'success' : 'warning']">
            {{ accountLabels[value] ? tr('本地备注', 'Local note') : tr('未记录', 'Not noted') }}
          </span>
        </div>
        <label>
          <span>{{ tr('账号备注名称', 'Account note') }}</span>
          <input v-model="drafts[value]" maxlength="100" :placeholder="tr('例如：门店官方账号', 'e.g. Official store account')" />
        </label>
        <div class="button-row">
          <button class="secondary" @click="save(value)">{{ tr('保存备注', 'Save note') }}</button>
          <button class="secondary danger" :disabled="!accountLabels[value]" @click="clear(value)">{{ tr('删除', 'Remove') }}</button>
        </div>
        <p class="hint">{{ tr('这只是本机记录，不会登录或绑定真实平台账号；自动发布开放后将改为真实账号授权。', 'This is a local note only — it does not sign in to or bind a real platform account. Automated publishing will use real account authorization once enabled.') }}</p>
      </article>
    </div>
  </section>
</template>

<script setup>
import { reactive, watch } from 'vue'

import { tr } from '../i18n.js'
import { publishReasonLabel, publishStatus } from '../stores/session.js'
import { PLATFORMS } from '../stores/studio.js'
import { accountLabels, clearAccountLabel, saveAccountLabel } from '../stores/publishing.js'

const drafts = reactive({ ...accountLabels })
watch(accountLabels, (value) => Object.assign(drafts, value), { deep: true })

function save(platform) {
  saveAccountLabel(platform, drafts[platform])
}

function clear(platform) {
  drafts[platform] = ''
  clearAccountLabel(platform)
}
</script>
