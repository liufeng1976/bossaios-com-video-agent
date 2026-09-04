<template>
  <div class="license-gate">
    <div class="license-card">
      <p class="kicker">BOSSAI · LICENSE</p>
      <h1>{{ tr('先接受许可协议，再开始使用', 'Accept the licence before you start') }}</h1>
      <p class="license-intro">
        {{ tr('BossAI Video Agent 个人非商业用途永久免费；请先确认以下要点。', 'BossAI Video Agent is free forever for personal, non-commercial use. Please confirm the points below first.') }}
      </p>

      <ul class="license-points">
        <li>{{ tr('个人非商业用途免费；企业、客户交付、收费服务或转售等商业用途需要 Business 授权。', 'Free for personal, non-commercial use. Business, client delivery, paid services, and resale require a Business licence.') }}</li>
        <li>{{ tr('账号、套餐、额度与设备绑定统一由 BossAI 商业系统管理，本产品不创建第二套计费权威。', 'Account, plan, quota and device binding are managed by the BossAI commercial system; this product creates no second billing authority.') }}</li>
        <li>{{ tr('只使用你本人、公司拥有或已获明确授权的声音、人物形象与素材；不提供来源不明的默认素材。', 'Use only voices, likenesses and media you own or are explicitly authorized to use. No unknown-rights default media is provided.') }}</li>
        <li>{{ tr('客户声音、人物素材与生成成果默认保存在本机；仅当你主动使用云能力时才会发生云端处理。', 'Your voices, avatar media and generated results stay local by default; cloud processing happens only when you invoke a cloud capability.') }}</li>
      </ul>

      <label class="consent-row">
        <input v-model="accepted" type="checkbox" />
        <span>{{ tr('我已阅读并同意 BossAI Video Agent 许可协议。', 'I have read and agree to the BossAI Video Agent licence.') }}</span>
      </label>

      <p v-if="error" class="license-error">{{ error }}</p>

      <div class="license-actions">
        <div class="license-actions-left">
          <button class="secondary" :disabled="!desktopLegalAvailable" @click="openLegal('eula')">
            {{ tr('查看完整 EULA', 'View full EULA') }}
          </button>
          <button v-if="desktopQuitAvailable" class="secondary" @click="quitApp">
            {{ tr('不同意，退出应用', 'Decline and quit') }}
          </button>
        </div>
        <button class="primary" :disabled="!accepted || eulaBusy" @click="accept">
          {{ eulaBusy ? tr('保存中…', 'Saving…') : tr('已阅读并同意', 'Agree and continue') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

import { tr } from '../i18n.js'
import {
  acceptCurrentEula,
  desktopLegalAvailable,
  desktopQuitAvailable,
  eulaBusy,
  openLegal,
  quitApp,
} from '../stores/session.js'
import { error } from '../stores/ui.js'

const accepted = ref(false)

async function accept() {
  if (!accepted.value) return
  await acceptCurrentEula()
}
</script>
