import { ref } from 'vue'

const STORAGE_KEY = 'bossai-video-locale'

function storedLocale() {
  return globalThis?.localStorage?.getItem(STORAGE_KEY) === 'en' ? 'en' : 'zh-CN'
}

export const locale = ref(storedLocale())

/** Pick the Chinese or English string for the active locale. */
export function tr(zh, en) {
  return locale.value === 'en' ? en : zh
}

export function setLocale(value) {
  locale.value = value === 'en' ? 'en' : 'zh-CN'
  globalThis?.localStorage?.setItem(STORAGE_KEY, locale.value)
}

/** Short language tag the backend expects for generation requests. */
export function requestLanguage() {
  return locale.value === 'en' ? 'en' : 'zh'
}
