import { ref } from 'vue'

import { tr } from '../i18n.js'

export const SCREENS = Object.freeze(['home', 'studio', 'assets', 'settings', 'legal'])

export const screen = ref('home')
export const message = ref('')
export const error = ref('')
export const busy = ref(false)
export const busyAction = ref('')

export function goTo(target) {
  screen.value = SCREENS.includes(target) ? target : 'home'
}

export function clearBanners() {
  message.value = ''
  error.value = ''
}

/**
 * Run one long task, keeping the shared busy flag and banners consistent.
 *
 * Errors are surfaced in the banner and re-thrown so callers can decide whether
 * a failure should stop a longer sequence.
 */
export async function run(action, name) {
  busy.value = true
  busyAction.value = name
  clearBanners()
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
