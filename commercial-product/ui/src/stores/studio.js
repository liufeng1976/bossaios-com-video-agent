/**
 * Video production workflow state: script, voiceover, digital human, the final
 * cut and publishing checks.
 */
import { computed, reactive, ref, watch } from 'vue'

import { deleteBgm, generateTitle, uploadAvatarVideo, uploadBgm, uploadVoice } from '../api.js'
import { videoCapabilities } from '../capabilities/video-capability-adapter.js'
import { requestLanguage, tr } from '../i18n.js'
import { assetId, avatars, refreshAvatars, refreshVoices, voices } from './assets.js'
import { desktopExportAvailable, refreshVideoAssets, videoAssets } from './session.js'
import { busyAction, error, message, run } from './ui.js'

/** Content shapes the rewrite engine is tuned for, matching the backend enum. */
export const VIDEO_TYPES = Object.freeze([
  ['voiceover', '真人口播', 'Talking head'],
  ['product_seeding', '产品种草', 'Product recommendation'],
  ['knowledge', '知识科普', 'Explainer'],
  ['emotion', '情绪共鸣', 'Emotional hook'],
  ['lead_generation', '引流获客', 'Lead generation'],
  ['local_store', '门店探店', 'Local store visit'],
  ['service_intro', '服务介绍', 'Service introduction'],
  ['conversion', '成交转化', 'Conversion'],
  ['plot_twist', '剧情反转', 'Plot twist'],
  ['pain_breakdown', '痛点拆解', 'Pain-point breakdown'],
])

export const PLATFORMS = Object.freeze([
  ['douyin', '抖音', 'Douyin'],
  ['channels', '视频号', 'WeChat Channels'],
  ['xiaohongshu', '小红书', 'Xiaohongshu'],
  ['kuaishou', '快手', 'Kuaishou'],
])

export const CAPTION_POSITIONS = Object.freeze([
  ['top', '顶部', 'Top'],
  ['center', '中部', 'Middle'],
  ['bottom', '底部', 'Bottom'],
])

export const audioUrl = ref('')
export const digitalHumanUrl = ref('')
export const finalVideoUrl = ref('')
export const finalDownloadName = ref('')
export const renderSummary = ref(null)
export const renderProgress = ref(0)
export const projectName = ref('')
export const publishPreparation = ref(null)

export const voiceFile = ref(null)
export const voiceDisplayName = ref('')
export const voiceRightsConfirmed = ref(false)
export const voiceUploading = ref(false)

export const avatarFile = ref(null)
export const avatarDisplayName = ref('')
export const avatarId = ref('')
export const avatarRightsConfirmed = ref(false)
export const avatarUploading = ref(false)

/** Publishing metadata derived from the finished script. */
export const title = ref('')
export const topics = ref('')
export const titleLimit = ref(0)

export const bgmFile = ref(null)
export const bgmUploading = ref(false)
export const exportBusy = ref(false)

export const form = reactive({
  sourceText: '',
  scriptText: '',
  platform: 'douyin',
  videoType: 'voiceover',
  targetChars: 300,
  industryPersona: '',
  productBusiness: '',
  sellingPoints: '',
  toneStyle: '',
  extraRequirements: '',
  voiceId: '',
})

/** Edit settings for the final cut; every field maps to a real FFmpeg option. */
export const edit = reactive({
  subtitleEnabled: true,
  subtitleFontFile: '',
  subtitlePosition: 'bottom',
  subtitleFontSize: 56,
  subtitleColor: '#ffffff',
  subtitleStrokeColor: '#000000',
  subtitleStrokeWidth: 2,
  bgmEnabled: false,
  bgmFile: '',
  bgmVolume: 13,
  voiceMixVolume: 100,
  videoTitleEnabled: false,
  videoTitleText: '',
  videoTitlePosition: 'top',
  videoTitleFontSize: 56,
  videoTitleColor: '#ffffff',
  videoTitleStrokeColor: '#000000',
})

export const bgmLibrary = computed(() => videoAssets.value?.bgm || [])
export const fontLibrary = computed(() => videoAssets.value?.fonts || [])

/** True when the render will actually change the picture or the audio. */
export const hasEdits = computed(
  () =>
    Boolean(edit.subtitleEnabled && form.scriptText.trim()) ||
    Boolean(edit.videoTitleEnabled && edit.videoTitleText.trim()) ||
    Boolean(edit.bgmEnabled && edit.bgmFile) ||
    Number(edit.voiceMixVolume) !== 100,
)

export const renderStatusLabel = computed(() => {
  if (finalVideoUrl.value) return tr('已完成', 'Completed')
  if (busyAction.value === 'render') return tr('处理中…', 'Rendering…')
  return tr('待生成', 'Not generated')
})

/**
 * Invalidate everything produced after the given stage.
 *
 * A new voiceover or a different avatar makes the existing digital-human clip
 * stale, and any change at all makes the existing final cut stale.
 */
function invalidateFrom(stage) {
  if (stage === 'voice' || stage === 'avatar') digitalHumanUrl.value = ''
  finalVideoUrl.value = ''
  finalDownloadName.value = ''
  renderSummary.value = null
  renderProgress.value = 0
  publishPreparation.value = null
}

export function selectVoiceFile(event) {
  const [file] = Array.from(event?.target?.files || [])
  voiceFile.value = file || null
}

export function selectAvatarFile(event) {
  const [file] = Array.from(event?.target?.files || [])
  avatarFile.value = file || null
  avatarId.value = ''
  invalidateFrom('avatar')
}

// Picking a different avatar from the library invalidates the clip built from
// the previous one.
watch(avatarId, () => invalidateFrom('avatar'))

export function selectBgmFile(event) {
  const [file] = Array.from(event?.target?.files || [])
  bgmFile.value = file || null
}

/** Drop a selection that no longer exists in the library (e.g. after a delete). */
export function reconcileSelections() {
  if (form.voiceId && !voices.value.some((item) => assetId(item) === form.voiceId)) form.voiceId = ''
  if (avatarId.value && !avatars.value.some((item) => assetId(item) === avatarId.value)) avatarId.value = ''
}

export async function uploadAuthorizedVoice() {
  if (!voiceFile.value || !voiceRightsConfirmed.value) return
  voiceUploading.value = true
  error.value = ''
  try {
    const result = await uploadVoice(voiceFile.value, voiceDisplayName.value)
    await refreshVoices()
    const uploadedId = assetId(result)
    if (uploadedId && voices.value.some((item) => assetId(item) === uploadedId)) form.voiceId = uploadedId
    voiceFile.value = null
    voiceDisplayName.value = ''
    message.value = tr('授权声音已保存到本机。', 'Authorized voice saved locally.')
  } catch (e) {
    error.value = e?.message || tr('声音上传失败', 'Voice upload failed')
  } finally {
    voiceUploading.value = false
  }
}

export async function uploadAuthorizedAvatar() {
  if (!avatarFile.value || !avatarRightsConfirmed.value) return
  avatarUploading.value = true
  error.value = ''
  try {
    const result = await uploadAvatarVideo(avatarFile.value, avatarDisplayName.value)
    // Selecting the new avatar invalidates downstream output via the watcher.
    avatarId.value = String(result?.avatarId || '')
    await refreshAvatars()
    avatarFile.value = null
    avatarDisplayName.value = ''
    message.value = tr('授权头像视频已保存到 BossAI 本机素材库。', 'Authorized avatar video saved to the local BossAI asset library.')
  } catch (e) {
    error.value = e?.message || tr('头像视频上传失败', 'Avatar video upload failed')
  } finally {
    avatarUploading.value = false
  }
}

export async function uploadBackgroundMusic() {
  if (!bgmFile.value) return
  bgmUploading.value = true
  error.value = ''
  try {
    const result = await uploadBgm(bgmFile.value)
    await refreshVideoAssets()
    edit.bgmFile = String(result?.fileName || '')
    edit.bgmEnabled = true
    bgmFile.value = null
    message.value = tr('背景音乐已保存到本机素材目录。', 'Background music saved to the local asset directory.')
  } catch (e) {
    error.value = e?.message || tr('背景音乐上传失败', 'Background music upload failed')
  } finally {
    bgmUploading.value = false
  }
}

export async function removeBackgroundMusic(fileName) {
  error.value = ''
  try {
    await deleteBgm(fileName)
    if (edit.bgmFile === fileName) {
      edit.bgmFile = ''
      edit.bgmEnabled = false
    }
    await refreshVideoAssets()
    message.value = tr('背景音乐已删除。', 'Background music removed.')
  } catch (e) {
    error.value = e?.message || tr('背景音乐删除失败', 'Failed to remove background music')
  }
}

export async function rewrite() {
  await run(async () => {
    const result = await videoCapabilities.rewrite(form.sourceText, { ...form, targetLanguage: requestLanguage() })
    form.scriptText = String(result?.rewriteText || result || '')
    message.value = tr('文案已生成，可以继续调整后制作配音。', 'Script generated. You can edit it before creating voiceover.')
  }, 'rewrite').catch(() => {})
}

export async function makeTitle() {
  await run(async () => {
    const result = await generateTitle({
      scriptText: form.scriptText,
      publishPlatform: form.platform,
      topicCount: 5,
    })
    title.value = String(result?.title || '')
    topics.value = (Array.isArray(result?.topics) ? result.topics : []).join(' ')
    titleLimit.value = Number(result?.titleLimit) || 0
    // The banner title defaults to the generated title until the user edits it.
    if (!edit.videoTitleText.trim()) edit.videoTitleText = title.value
    message.value = tr('标题与话题已生成，可继续手工调整。', 'Title and hashtags generated. You can still edit them.')
  }, 'title').catch(() => {})
}

export async function makeVoice() {
  await run(async () => {
    const result = await videoCapabilities.tts(
      { text: form.scriptText, voiceId: form.voiceId, language: requestLanguage() },
      (job) => {
        message.value = job?.message || tr('正在生成 CosyVoice2 配音…', 'Generating CosyVoice2 voiceover…')
      },
    )
    audioUrl.value = result?.fileUrl || ''
    invalidateFrom('voice')
    message.value = tr('CosyVoice2 配音生成完成。', 'CosyVoice2 voiceover completed.')
  }, 'tts').catch(() => {})
}

export async function makeDigitalHuman() {
  await run(async () => {
    const result = await videoCapabilities.digitalHuman({ avatarId: avatarId.value, audioUrl: audioUrl.value }, (job) => {
      message.value = job?.message || tr('正在生成 MuseTalk 数字人口播…', 'Generating MuseTalk digital-human video…')
    })
    digitalHumanUrl.value = String(result?.fileUrl || '')
    invalidateFrom('digital-human')
    message.value = tr('MuseTalk 数字人口播生成完成。', 'MuseTalk digital-human video completed.')
  }, 'musetalk').catch(() => {})
}

/**
 * Produce the deliverable.
 *
 * With no edits enabled this is a lossless copy of the digital-human clip; with
 * edits it goes through the local FFmpeg composer and reports a progress bar.
 */
export async function renderFinalVideo() {
  await run(async () => {
    renderProgress.value = 0
    if (!hasEdits.value) {
      const result = await videoCapabilities.finalize({
        sourceUrl: digitalHumanUrl.value,
        projectName: projectName.value,
      })
      finalVideoUrl.value = String(result?.fileUrl || '')
      finalDownloadName.value = String(result?.downloadName || 'BossAI-Video.mp4')
      renderSummary.value = { subtitleBurned: false, titleBurned: false, bgmMixed: false, reEncoded: false }
      renderProgress.value = 100
      message.value = tr('成片已生成（未启用剪辑，保留原始画质）。', 'Final video created (no edits enabled, original quality preserved).')
      return
    }

    const result = await videoCapabilities.renderVideo(
      {
        sourceUrl: digitalHumanUrl.value,
        projectName: projectName.value,
        scriptText: form.scriptText,
        ...edit,
      },
      (job) => {
        renderProgress.value = Number(job?.progress) || 0
        message.value = tr(`正在合成成片… ${renderProgress.value}%`, `Composing final video… ${renderProgress.value}%`)
      },
    )
    finalVideoUrl.value = String(result?.fileUrl || '')
    finalDownloadName.value = String(result?.downloadName || 'BossAI-Video.mp4')
    renderSummary.value = result
    renderProgress.value = 100
    publishPreparation.value = null
    message.value = tr('最终成片已生成并保存在 BossAI 本机数据目录。', 'Final video generated and saved in the local BossAI data directory.')
  }, 'render').catch(() => {})
}

export async function exportFinalVideo() {
  if (!desktopExportAvailable.value || !finalVideoUrl.value) return
  exportBusy.value = true
  error.value = ''
  try {
    const result = await globalThis.bossaiDesktop.exportFinalVideo(
      finalVideoUrl.value,
      finalDownloadName.value || 'BossAI-Video.mp4',
    )
    if (result?.canceled) {
      message.value = tr('已取消导出。', 'Export canceled.')
    } else if (result?.exported) {
      message.value = tr(`成片已导出：${result.filePath}`, `Video exported: ${result.filePath}`)
    } else {
      throw new Error(result?.reason || tr('成片导出失败', 'Video export failed'))
    }
  } catch (e) {
    error.value = e?.message || tr('成片导出失败', 'Video export failed')
  } finally {
    exportBusy.value = false
  }
}

export async function preparePublish() {
  await run(async () => {
    publishPreparation.value = await videoCapabilities.publish({
      finalVideoUrl: finalVideoUrl.value,
      platform: form.platform,
    })
    message.value = publishPreparation.value?.automatedPublishAllowed
      ? tr('发布条件已满足。', 'Publishing conditions are met.')
      : tr('自动发布继续保持关闭；成片可正常导出并由用户手工发布。', 'Automated publishing stays disabled; export the video and publish manually.')
  }, 'publish').catch(() => {})
}
