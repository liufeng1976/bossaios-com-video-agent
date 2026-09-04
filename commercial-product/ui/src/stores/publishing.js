/**
 * Local notes for the platform accounts the customer plans to publish to.
 *
 * Automated publishing stays fail-closed until BossAI approval and a real
 * platform-account binding are connected (see the studio's step 07 and the GA
 * release gate's publishing-uat check). This store only remembers a label per
 * platform on this machine — it performs no login, no OAuth, and no upload.
 */
import { reactive } from 'vue'

import { tr } from '../i18n.js'
import { message } from './ui.js'

const STORAGE_KEY = 'bossai-video-publishing-accounts'

function loadAccounts() {
  try {
    const raw = globalThis?.localStorage?.getItem(STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : {}
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

export const accountLabels = reactive(loadAccounts())

function persist() {
  try {
    globalThis?.localStorage?.setItem(STORAGE_KEY, JSON.stringify(accountLabels))
  } catch {
    // Best-effort; local storage may be unavailable in some preview contexts.
  }
}

export function saveAccountLabel(platform, label) {
  const trimmed = String(label || '').trim().slice(0, 100)
  if (trimmed) {
    accountLabels[platform] = trimmed
  } else {
    delete accountLabels[platform]
  }
  persist()
  message.value = tr('账号备注已保存到本机。', 'Account note saved locally.')
}

export function clearAccountLabel(platform) {
  delete accountLabels[platform]
  persist()
  message.value = tr('账号备注已删除。', 'Account note removed.')
}
