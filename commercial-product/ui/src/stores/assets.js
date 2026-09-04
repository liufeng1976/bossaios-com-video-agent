/**
 * The local authorized-asset library: reference voices and avatar clips.
 *
 * Everything here is customer-supplied. The product creates no default voice or
 * avatar of its own, so an empty library is the correct initial state.
 */
import { computed, reactive, ref } from 'vue'

import {
  avatarFileUrl,
  deleteAvatar,
  deleteVoice,
  listAvatars,
  listVoices,
  renameAvatar,
  renameVoice,
  voiceFileUrl,
} from '../api.js'
import { tr } from '../i18n.js'
import { error, message } from './ui.js'

export const voices = ref([])
export const avatars = ref([])
export const assetsBusy = ref(false)

/** Pending rename text, keyed by `${kind}:${id}`; absent means "not editing". */
export const renameDrafts = reactive({})

function normalizeList(value) {
  if (Array.isArray(value)) return value
  if (Array.isArray(value?.items)) return value.items
  if (Array.isArray(value?.data)) return value.data
  return []
}

export function assetId(item) {
  return String(item?.id || item?.voiceId || item?.avatarId || '')
}

export function assetName(item, fallback) {
  return String(item?.displayName || item?.name || assetId(item) || fallback)
}

/**
 * Voices with no provenance are never offered as usable.
 *
 * Legacy upstream builds shipped an unnamed default reference voice; this
 * product must not surface one.
 */
function isBlockedDefaultVoice(item) {
  const id = assetId(item).trim().toLowerCase()
  return !id || ['zst', '__default__', 'default'].includes(id)
}

export const voiceCount = computed(() => voices.value.length)
export const avatarCount = computed(() => avatars.value.length)

export function draftKey(kind, id) {
  return `${kind}:${id}`
}

export function startRename(kind, item) {
  renameDrafts[draftKey(kind, assetId(item))] = assetName(item, '')
}

export function cancelRename(kind, id) {
  delete renameDrafts[draftKey(kind, id)]
}

export async function refreshVoices() {
  voices.value = normalizeList(await listVoices()).filter((item) => !isBlockedDefaultVoice(item))
}

export async function refreshAvatars() {
  avatars.value = normalizeList(await listAvatars())
}

export async function refreshAssets() {
  assetsBusy.value = true
  try {
    const [voiceResult, avatarResult] = await Promise.allSettled([refreshVoices(), refreshAvatars()])
    if (voiceResult.status === 'rejected' && avatarResult.status === 'rejected') {
      error.value = tr('无法读取本机素材库。', 'Unable to read the local asset library.')
    }
  } finally {
    assetsBusy.value = false
  }
}

async function applyRename(kind, id, request, refresh) {
  const key = draftKey(kind, id)
  const displayName = String(renameDrafts[key] || '').trim()
  if (!displayName) return
  error.value = ''
  try {
    await request(id, displayName)
    delete renameDrafts[key]
    await refresh()
    message.value = tr('名称已更新。', 'Name updated.')
  } catch (e) {
    error.value = e?.message || tr('重命名失败', 'Rename failed')
  }
}

export function commitVoiceRename(id) {
  return applyRename('voice', id, renameVoice, refreshVoices)
}

export function commitAvatarRename(id) {
  return applyRename('avatar', id, renameAvatar, refreshAvatars)
}

async function removeAsset(id, request, refresh, successText) {
  error.value = ''
  try {
    await request(id)
    await refresh()
    message.value = successText
  } catch (e) {
    error.value = e?.message || tr('删除失败', 'Delete failed')
  }
}

export function removeVoice(id) {
  return removeAsset(id, deleteVoice, refreshVoices, tr('授权声音已删除。', 'Authorized voice deleted.'))
}

export function removeAvatar(id) {
  return removeAsset(id, deleteAvatar, refreshAvatars, tr('授权人物视频已删除。', 'Authorized avatar deleted.'))
}

export { avatarFileUrl, voiceFileUrl }
