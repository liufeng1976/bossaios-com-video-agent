const API_BASE = import.meta.env.VITE_BOSSAI_VIDEO_API || 'http://127.0.0.1:8765'

export function apiUrl(path) {
  if (/^https?:\/\//i.test(path)) return path
  return `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`
}

export async function requestJson(path, options = {}) {
  const response = await fetch(apiUrl(path), {
    credentials: 'omit',
    ...options,
    headers: {
      Accept: 'application/json',
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(options.headers || {}),
    },
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok || payload?.success === false) {
    const detail = payload?.message || payload?.detail || response.statusText || `HTTP ${response.status}`
    throw new Error(Array.isArray(detail) ? detail.map((item) => item?.msg || String(item)).join('；') : String(detail))
  }
  return payload?.data ?? payload
}

export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

export async function pollJob(path, { timeoutMs = 3_000_000, intervalMs = 1200, onProgress, headers = {} } = {}) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const job = await requestJson(path, { headers })
    onProgress?.(job)
    if (job?.status === 'done') return job
    if (job?.status === 'failed' || job?.status === 'canceled') throw new Error(job?.message || '任务失败')
    await sleep(intervalMs)
  }
  throw new Error('任务超时，请稍后重试')
}

function localControlHeaders() {
  const token = String(globalThis?.bossaiDesktop?.localControlToken || '').trim()
  if (!token) throw new Error('请从 BossAI Video Agent 桌面应用打开运行环境安装中心。')
  return { 'x-bossai-local-control': token }
}

export function hasLocalRuntimeControl() {
  return Boolean(String(globalThis?.bossaiDesktop?.localControlToken || '').trim())
}

export async function getProduct() {
  return requestJson('/api/commercial/product')
}

export async function getRuntimeInstallCenter() {
  return requestJson('/api/commercial/runtime/install-center')
}

export async function installRuntime(component, { profile = 'gpu', acceptLicense = false, onProgress } = {}) {
  const headers = localControlHeaders()
  const first = await requestJson(`/api/commercial/runtime/install/${encodeURIComponent(component)}`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ profile, acceptLicense: Boolean(acceptLicense) }),
  })
  if (!first?.jobId) throw new Error('BossAI 运行环境安装服务未返回任务 ID')
  return pollJob(`/api/commercial/runtime/install-jobs/${encodeURIComponent(first.jobId)}`, {
    timeoutMs: 3_600_000,
    intervalMs: 1500,
    headers,
    onProgress,
  })
}

export async function getEntitlement() {
  return requestJson('/api/commercial/entitlement')
}

export async function getEulaStatus() {
  return requestJson('/api/license/eula')
}

export async function acceptEula(locale = 'zh-CN') {
  return requestJson('/api/license/eula', {
    method: 'POST',
    body: JSON.stringify({ accepted: true, locale }),
  })
}

export async function getAccountSession() {
  return requestJson('/api/account/session')
}

export async function sendRegistrationChallenge(payload) {
  return requestJson('/api/account/challenges', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function authenticateAccount(payload) {
  return requestJson('/api/account/session', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function logoutAccount() {
  return requestJson('/api/account/logout', { method: 'POST', body: JSON.stringify({}) })
}

export async function rewriteScript(sourceText, options = {}) {
  return requestJson('/api/llm/rewrite', {
    method: 'POST',
    body: JSON.stringify({
      sourceText,
      rewriteMode: 'video-learning',
      targetChars: Number(options.targetChars) || 300,
      targetLanguage: options.targetLanguage || 'zh',
      platform: options.platform || 'douyin',
      videoType: options.videoType || 'voiceover',
      personaType: 'persona',
      toneStyle: options.toneStyle || '',
      industryPersona: options.industryPersona || '',
      productBusiness: options.productBusiness || '',
      sellingPoints: options.sellingPoints || '',
      extraRequirements: options.extraRequirements || '',
    }),
  })
}

export async function listVoices() {
  return requestJson('/api/voices/?page=1&pageSize=100')
}

export async function renameVoice(voiceId, displayName) {
  return requestJson(`/api/voices/${encodeURIComponent(voiceId)}`, {
    method: 'PATCH',
    body: JSON.stringify({ displayName }),
  })
}

export async function deleteVoice(voiceId) {
  return requestJson(`/api/voices/${encodeURIComponent(voiceId)}`, { method: 'DELETE' })
}

export function voiceFileUrl(voiceId) {
  return apiUrl(`/api/voices/${encodeURIComponent(voiceId)}/file`)
}

export async function listAvatars() {
  return requestJson('/api/commercial/avatars/?page=1&pageSize=100')
}

export async function renameAvatar(avatarId, displayName) {
  return requestJson(`/api/commercial/avatars/${encodeURIComponent(avatarId)}`, {
    method: 'PATCH',
    body: JSON.stringify({ displayName }),
  })
}

export async function deleteAvatar(avatarId) {
  return requestJson(`/api/commercial/avatars/${encodeURIComponent(avatarId)}`, { method: 'DELETE' })
}

export function avatarFileUrl(avatarId) {
  return apiUrl(`/api/commercial/avatars/${encodeURIComponent(avatarId)}/file`)
}

/** Derive a publishing title and hashtags from the finished script. */
export async function generateTitle(payload) {
  return requestJson('/api/llm/generate-title', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/** Derive a short, thumbnail-readable cover line from the script. */
export async function generateCoverTitle(payload) {
  return requestJson('/api/llm/generate-cover-title', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function listMedia() {
  return requestJson('/api/commercial/media/?page=1&pageSize=100')
}

export async function uploadMedia(file, displayName = '') {
  return uploadMultipart('/api/commercial/media/upload', file, { displayName })
}

export async function renameMedia(mediaId, displayName) {
  return requestJson(`/api/commercial/media/${encodeURIComponent(mediaId)}`, {
    method: 'PATCH',
    body: JSON.stringify({ displayName }),
  })
}

export async function deleteMedia(mediaId) {
  return requestJson(`/api/commercial/media/${encodeURIComponent(mediaId)}`, { method: 'DELETE' })
}

export function mediaFileUrl(mediaId) {
  return apiUrl(`/api/commercial/media/${encodeURIComponent(mediaId)}/file`)
}

/** Build a cover image from a frame of the finished video. */
export async function createCover(payload) {
  return requestJson('/api/commercial/video/cover', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/** POST one file as multipart/form-data and unwrap the BossAI response envelope. */
export async function uploadMultipart(path, file, fields = {}) {
  const body = new FormData()
  body.append('file', file)
  for (const [key, value] of Object.entries(fields)) {
    if (String(value ?? '').trim()) body.append(key, String(value).trim())
  }
  const response = await fetch(apiUrl(path), { method: 'POST', credentials: 'omit', body })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok || payload?.success === false) {
    throw new Error(payload?.message || payload?.detail || response.statusText || `HTTP ${response.status}`)
  }
  return payload?.data ?? payload
}

export async function uploadVoice(file, displayName = '') {
  return uploadMultipart('/api/voices/upload', file, { displayName })
}

export async function getDigitalHumanSetup() {
  return requestJson('/api/commercial/digital-human/setup')
}

export async function uploadAvatarVideo(file, displayName = '') {
  return uploadMultipart('/api/commercial/assets/avatar-video', file, { displayName })
}

export async function renderCommercialDigitalHuman(payload, onProgress) {
  const first = await requestJson('/api/commercial/digital-human/render', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  if (!first?.jobId) throw new Error('MuseTalk 服务未返回任务 ID')
  return pollJob(`/api/commercial/digital-human/jobs/${encodeURIComponent(first.jobId)}`, { onProgress })
}

export async function finalizeCommercialVideo(payload) {
  return requestJson('/api/commercial/video/finalize', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function getPublishStatus() {
  return requestJson('/api/commercial/publish/status')
}

export async function prepareCommercialPublish(payload) {
  return requestJson('/api/commercial/publish/prepare', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function generateTts(payload, onProgress) {
  const first = await requestJson('/api/tts/generate', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  if (first?.fileUrl) return first
  if (!first?.jobId) throw new Error('语音服务未返回任务 ID')
  return pollJob(`/api/tts/jobs/${encodeURIComponent(first.jobId)}`, { onProgress })
}

/** Background music, installed fonts and composer readiness for the editor. */
export async function getVideoAssets() {
  return requestJson('/api/commercial/video/assets')
}

export async function uploadBgm(file) {
  return uploadMultipart('/api/commercial/video/bgm', file)
}

export async function deleteBgm(fileName) {
  return requestJson(`/api/commercial/video/bgm/${encodeURIComponent(fileName)}`, { method: 'DELETE' })
}

/** Compose the final cut; resolves once FFmpeg has finished the render. */
export async function renderCommercialFinalVideo(payload, onProgress) {
  const first = await requestJson('/api/commercial/video/render', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  if (!first?.jobId) throw new Error('成片合成服务未返回任务 ID')
  return pollJob(`/api/commercial/video/jobs/${encodeURIComponent(first.jobId)}`, { onProgress })
}
