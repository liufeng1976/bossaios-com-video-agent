/**
 * Account, entitlement, licence and runtime state.
 *
 * These are configuration concerns: the Settings screen owns them, and the Home
 * screen only reads the derived readiness flags.
 */
import { computed, reactive, ref } from 'vue'

import {
  acceptEula,
  authenticateAccount,
  getAccountSession,
  getDigitalHumanSetup,
  getEntitlement,
  getEulaStatus,
  getProduct,
  getRuntimeInstallCenter,
  getTranscriptionSetup,
  getVideoAssets,
  hasLocalRuntimeControl,
  installRuntime,
  logoutAccount,
  sendRegistrationChallenge,
} from '../api.js'
import { videoCapabilities } from '../capabilities/video-capability-adapter.js'
import { locale, tr } from '../i18n.js'
import { error, message } from './ui.js'

export const previewUnlocked = import.meta.env.VITE_BOSSAI_COMMERCIAL_PREVIEW === '1'

export const product = ref(null)
export const entitlement = ref(null)
export const eulaStatus = ref(null)
export const accountSession = ref(null)
export const digitalHumanSetup = ref(null)
export const runtimeCenter = ref(null)
export const legalStatus = ref(null)
export const publishStatus = ref(null)
export const videoAssets = ref(null)
export const transcriptionSetup = ref(null)
export const backendReady = ref(false)

export const authMode = ref('login')
export const authBusy = ref(false)
export const challengeBusy = ref(false)
export const eulaBusy = ref(false)
export const runtimeLicenseAccepted = ref(false)
export const runtimeInstallProfile = ref('gpu')
export const runtimeInstallBusy = ref(false)
export const runtimeInstallComponentId = ref('')
export const runtimeInstallMessage = ref('')

export const accountForm = reactive({
  identifier: '',
  password: '',
  displayName: '',
  challengeId: '',
  verificationCode: '',
})

export const accountAuthenticated = computed(() => Boolean(accountSession.value?.authenticated))
export const accountLabel = computed(() => {
  if (accountAuthenticated.value) return tr('已登录', 'Signed in')
  if (['not_configured', 'unavailable'].includes(accountSession.value?.sessionStatus)) {
    return tr('BossAI OS 未连接', 'BossAI OS disconnected')
  }
  if (accountSession.value?.sessionStatus === 'expired') return tr('登录已过期', 'Session expired')
  return tr('未登录', 'Signed out')
})

export const executionAllowed = computed(() => Boolean(previewUnlocked || entitlement.value?.executionAllowed))
const entitledFeatures = computed(() => new Set(Array.isArray(entitlement.value?.features) ? entitlement.value.features : []))
const featureAllowed = (feature) =>
  computed(() => Boolean(previewUnlocked || (executionAllowed.value && entitledFeatures.value.has(feature))))

export const rewriteAllowed = featureAllowed('video.rewrite')
export const ttsAllowed = featureAllowed('video.tts')
export const digitalHumanAllowed = featureAllowed('video.digital-human')

export const tierLabel = computed(() => {
  const tier = String(entitlement.value?.tier || '')
  if (tier === 'free-personal') return 'Free Personal'
  if (tier === 'personal-pro') return 'Personal Pro'
  if (tier === 'business') return 'Business'
  if (tier === 'developer-preview') return tr('内部预览', 'Internal Preview')
  return tr('未识别', 'Unknown')
})

export const localFreeMode = computed(() => Boolean(entitlement.value?.localFreeMode))
export const quotaRemaining = computed(() => Number(entitlement.value?.quotaRemaining ?? 0))
export const localFreeQuota = computed(() => entitlement.value?.localFreeQuota ?? null)

// Metering is off unless an operator turns it on, so every quota label has to
// read correctly in the unmetered case too -- that is the shipping default.
export const localQuotaEnabled = computed(() => Boolean(localFreeMode.value && localFreeQuota.value?.enabled))

export const quotaDisplay = computed(() => {
  if (!localFreeMode.value) return `${quotaRemaining.value} BossAI Points`
  if (!localQuotaEnabled.value) {
    return tr('本地核心能力不计 BossAI Points', 'Local core features do not consume BossAI Points')
  }
  const daily = Number(localFreeQuota.value?.dailyUnits ?? 0)
  return tr(
    `今日剩余 ${quotaRemaining.value} / ${daily} 本地额度`,
    `${quotaRemaining.value} of ${daily} local units left today`,
  )
})

// The per-deliverable prices come from the backend rather than being restated
// here, so changing the allowance never leaves the Settings screen quoting
// costs the engine no longer charges.
export const quotaCostsLabel = computed(() => {
  const costs = localFreeQuota.value?.operationUnits
  if (!localQuotaEnabled.value || !costs) return ''
  const zh = { rewrite: '改写', tts: '配音', 'digital-human': '数字人' }
  const en = { rewrite: 'rewrite', tts: 'voiceover', 'digital-human': 'digital human' }
  return Object.entries(costs)
    .map(([key, units]) => `${tr(zh[key] ?? key, en[key] ?? key)} ${units}`)
    .join(tr('，', ' · '))
})

const formatResetAt = (value) => {
  const at = new Date(String(value || ''))
  if (Number.isNaN(at.getTime())) return String(value || '')
  return at.toLocaleString(locale.value === 'en' ? 'en-US' : 'zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export const quotaResetLabel = computed(() => {
  if (localFreeMode.value) {
    if (!localQuotaEnabled.value) return tr('本地模式无需额度恢复', 'No quota reset for local mode')
    const at = localFreeQuota.value?.resetAt
    return at
      ? tr(`${formatResetAt(at)} 重置`, `Resets ${formatResetAt(at)}`)
      : tr('每日重置', 'Resets daily')
  }
  return String(entitlement.value?.quotaResetAt || tr('由 BossAI 权威服务下发', 'Provided by BossAI authority'))
})
export const deviceBindingLabel = computed(() =>
  localFreeMode.value
    ? tr('本地免费模式无需绑定', 'Not required for local free mode')
    : entitlement.value?.deviceRegistered
      ? tr('已授权', 'Authorized')
      : tr('未授权', 'Not authorized'),
)
export const businessUseAllowed = computed(() => Boolean(entitlement.value?.businessUseAllowed))
export const eulaAccepted = computed(() => Boolean(eulaStatus.value?.accepted || entitlement.value?.eulaAccepted))

// Status values the backend actually returns (see server.py _entitlement_snapshot):
// preview, local_free, eula_required, active, restricted, unknown_plan,
// device_required, quota_frozen, quota_exhausted, unavailable.
export const entitlementLabel = computed(() => {
  if (previewUnlocked) return tr('内部预览', 'Internal Preview')
  if (!backendReady.value) return tr('本地服务未连接', 'Local service disconnected')
  const byStatus = {
    local_free: tr('Free Personal · 本地', 'Free Personal · Local'),
    eula_required: tr('请接受许可协议', 'Accept license terms'),
    quota_exhausted: tr('本月额度已用完', 'Monthly quota exhausted'),
    quota_frozen: tr('额度已冻结', 'Quota frozen'),
    device_required: tr('设备未授权', 'Device not authorized'),
    unknown_plan: tr('套餐未识别', 'Unknown plan'),
    restricted: tr('授权受限', 'Restricted'),
    unavailable: tr('BossAI 服务暂不可用', 'BossAI service unavailable'),
  }
  return byStatus[entitlement.value?.status] || (executionAllowed.value ? tierLabel.value : tr('授权受限', 'Restricted'))
})

/**
 * The backend's `reason` field is a fixed English string meant for logs, not
 * end users — it must never be shown as-is. This maps the entitlement status
 * to a localized explanation instead, falling back to a generic message (not
 * the raw backend string) for anything unmapped.
 */
export const entitlementReason = computed(() => {
  const status = entitlement.value?.status
  const byStatus = {
    preview: tr('内部预览模式，不代表真实的客户订阅、额度或授权。', 'Internal preview mode. This does not represent a real customer subscription, quota, or entitlement.'),
    local_free: tr('Free Personal 已在本地激活，个人非商业用途永久免费；商业用途需要登录 BossAI 并升级 Business。', 'Free Personal is active locally and free forever for personal, non-commercial use. Commercial use requires signing in to BossAI and upgrading to Business.'),
    eula_required: tr('请先在设置中接受软件许可协议，才能使用本地 AI 能力。', 'Accept the software licence in Settings before using local AI features.'),
    active: tr('当前 BossAI 授权有效。', 'The current BossAI entitlement is active.'),
    restricted: tr('当前 BossAI 套餐或授权不满足执行条件，请在设置中检查账号与套餐状态。', 'The current BossAI plan or entitlement does not authorize execution. Check your account and plan in Settings.'),
    unknown_plan: tr('BossAI 返回了本产品版本无法识别的套餐，请更新应用或联系支持。', 'BossAI returned a plan this product version does not recognize. Update the app or contact support.'),
    device_required: tr('当前设备尚未在 BossAI 账号下完成授权注册。', 'This device is not yet registered under your BossAI account.'),
    quota_frozen: tr('BossAI 额度账户已被冻结，请前往 BossAI 官方渠道处理。', 'The BossAI quota wallet is frozen. Resolve this through official BossAI channels.'),
    quota_exhausted: tr('本月 BossAI 额度已用完，额度恢复以 BossAI 权威记录为准。', 'This month’s BossAI quota is exhausted. It resets according to the authoritative BossAI record.'),
    unavailable: tr('无法连接 BossAI 商业服务，个人本地免费功能不受影响。', 'Unable to reach BossAI commercial services; local Free Personal features are unaffected.'),
  }
  return (
    byStatus[status] ||
    tr(
      'Free Personal 可在本地免费使用；需要 Pro、Gateway 或商业用途时再登录 BossAI。',
      'Free Personal can be used locally for free. Sign in to BossAI only when you need Pro, Gateway, or commercial use.',
    )
  )
})

export const digitalHumanMissingLabel = computed(() => {
  const missing = Array.isArray(digitalHumanSetup.value?.missing) ? digitalHumanSetup.value.missing : []
  if (!missing.length) return tr('MuseTalk 本地运行环境尚未完成配置。', 'The MuseTalk local runtime is not configured yet.')
  const labels = {
    adapter: tr('数字人适配器', 'digital-human adapter'),
    'model-runtime': tr('MuseTalk 模型文件', 'MuseTalk model files'),
    'python-runtime': tr('MuseTalk Python 运行环境', 'MuseTalk Python runtime'),
    'ffmpeg-runtime': tr('FFmpeg 运行环境', 'FFmpeg runtime'),
    'runtime-component': tr('MuseTalk 运行组件', 'MuseTalk runtime component'),
  }
  const names = missing.map((item) => labels[item] || item).join(tr('、', ', '))
  return tr(`缺少：${names}`, `Missing: ${names}`)
})

/**
 * The publish-status `reason` field is a fixed English string for logs, same
 * as the entitlement reason — never render it directly.
 */
export const publishReasonLabel = computed(() => {
  if (!publishStatus.value) return tr('等待读取 BossAI 发布治理状态。', 'Waiting for BossAI publishing-governance status.')
  return publishStatus.value.automatedPublishAllowed
    ? tr('自动发布已获授权并接入平台账号。', 'Automated publishing is authorized and connected to a platform account.')
    : tr('自动发布在获得 BossAI 审批与平台账号绑定前继续保持关闭；成片可随时手动导出发布。', 'Automated publishing stays disabled until BossAI approval and platform-account binding are connected; export and publish the video manually anytime.')
})

export const composerReady = computed(() => Boolean(videoAssets.value?.composer?.ready))
export const transcriptionReady = computed(() => Boolean(transcriptionSetup.value?.ready))
export const runtimeControlAvailable = computed(() => hasLocalRuntimeControl())

export const runtimeItems = computed(() => {
  const center = runtimeCenter.value || {}
  const support = center.support || {}
  const components = center.components || {}
  const python = support.python310 || {}
  const ffmpeg = support.ffmpeg || {}
  return [
    {
      id: 'python310',
      name: 'BossAI Python 3.10',
      description: tr('独立安装到 BossAI 本机目录，不修改系统 PATH。', 'Installed into a dedicated local BossAI directory without changing system PATH.'),
      ready: Boolean(python.ready),
      installable: Boolean(center.powershellReady && python.installerAvailable),
      blockedReason: center.powershellReady ? '' : tr('缺少 PowerShell', 'PowerShell required'),
    },
    {
      id: 'qwen',
      name: tr('Qwen 本地文案引擎', 'Qwen local writing engine'),
      description: tr('固定官方版本，用于本地文案生成与改写。', 'Pinned official runtime for local script generation and rewrite.'),
      ready: Boolean((components.qwen || {}).ready),
      installable: Boolean((components.qwen || {}).installable),
      blockedReason: (components.qwen || {}).installable ? '' : tr('需要 PowerShell', 'PowerShell required'),
    },
    {
      id: 'cosyvoice2',
      name: tr('CosyVoice2 配音引擎', 'CosyVoice2 voiceover engine'),
      description: tr('固定官方版本，只使用客户授权或 BossAI 自有声音。', 'Pinned official runtime; use only customer-authorized or BossAI-owned voices.'),
      ready: Boolean((components.cosyvoice2 || {}).ready),
      installable: Boolean((components.cosyvoice2 || {}).installable),
      blockedReason: python.ready ? '' : tr('先安装 Python 3.10', 'Install Python 3.10 first'),
    },
    {
      id: 'whisper',
      name: tr('本地转写引擎（可选）', 'Local transcription engine (optional)'),
      description: tr('从你自有的视频提取文案，并让字幕时间轴对齐真实语音。', 'Extracts a script from video you own and aligns subtitles to the real speech.'),
      ready: Boolean((components.whisper || {}).ready),
      installable: Boolean((components.whisper || {}).installable),
      blockedReason: python.ready ? '' : tr('先安装 Python 3.10', 'Install Python 3.10 first'),
      optional: true,
    },
    {
      id: 'musetalk',
      name: tr('MuseTalk 数字人引擎', 'MuseTalk digital-human engine'),
      description: tr('用于客户授权人物视频的数字人口播合成。', 'Creates talking-avatar video from authorized customer media.'),
      ready: Boolean((components.musetalk || {}).ready),
      installable: Boolean((components.musetalk || {}).installable),
      blockedReason: !python.ready
        ? tr('先安装 Python 3.10', 'Install Python 3.10 first')
        : !ffmpeg.ready
          ? tr('需要 FFmpeg', 'FFmpeg required')
          : '',
    },
  ]
})

export const allCoreRuntimesReady = computed(() =>
  runtimeItems.value.filter((item) => !item.optional).every((item) => item.ready),
)
export const desktopLegalAvailable = computed(() =>
  Boolean(globalThis?.bossaiDesktop?.legalStatus && globalThis?.bossaiDesktop?.openLegalDocument),
)
export const desktopExportAvailable = computed(() => Boolean(globalThis?.bossaiDesktop?.exportFinalVideo))
export const legalReleaseReady = computed(() => Boolean(legalStatus.value?.approvedReleaseBundlePresent))

export const legalDocuments = computed(() => {
  const available = legalStatus.value?.documents || {}
  const definitions = [
    ['eula', tr('最终用户许可协议 EULA', 'End User License Agreement'), tr('当前安装版许可、套餐和使用限制。', 'Current packaged-product license, plan and usage terms.')],
    ['sourceLicense', tr('当前源码许可', 'Current Source License'), tr('个人/非商业源码使用许可及商业使用授权边界。', 'Personal/non-commercial source grant and commercial-use authorization boundary.')],
    ['historicalLicense', tr('历史 MIT 许可说明', 'Historical MIT License'), tr('保留此前已公开 MIT 版本的既有授权事实；不声明撤回。', 'Preserves the historical MIT grant for previously published versions; no revocation claim.')],
    ['commercialLicense', tr('Business 商业许可', 'Business Commercial License'), tr('商业用途、企业部署与合同授权边界。', 'Commercial-use, enterprise deployment and contractual licensing boundary.')],
    ['terms', tr('服务条款', 'Terms of Service'), tr('账号、订阅、额度、服务与退款边界。', 'Account, subscription, quota, service and refund terms.')],
    ['privacy', tr('隐私说明', 'Privacy Notice'), tr('本地数据、账号商业状态与云端处理边界。', 'Local data, account commercial state and cloud-processing boundary.')],
    ['voiceAvatar', tr('声音与人物素材授权确认', 'Voice & Avatar Authorization'), tr('声音、肖像与人物视频合法授权确认。', 'Lawful authorization for voice, likeness and avatar media.')],
    ['support', tr('安装与支持说明', 'Installation & Support'), tr('运行环境、安装、升级和支持说明。', 'Runtime, installation, upgrade and support information.')],
    ['notices', tr('第三方组件说明', 'Third-party Notices'), tr('第三方运行时、模型和许可证边界。', 'Third-party runtime, model and license boundaries.')],
  ]
  return definitions.map(([id, name, description]) => ({ id, name, description, available: Boolean(available[id]) }))
})

/** Everything the user must clear before the studio can produce a video. */
export const readinessChecklist = computed(() => [
  {
    id: 'eula',
    label: tr('接受软件许可', 'Accept the software licence'),
    ready: eulaAccepted.value,
    hint: tr('Free Personal 只需接受许可即可开始使用。', 'Free Personal only requires accepting the licence.'),
  },
  {
    id: 'runtime',
    label: tr('安装本地运行环境', 'Install the local runtimes'),
    ready: allCoreRuntimesReady.value,
    hint: tr('Qwen、CosyVoice2 与 MuseTalk 从官方来源安装到本机。', 'Qwen, CosyVoice2 and MuseTalk install locally from pinned official sources.'),
  },
  {
    id: 'composer',
    label: tr('成片合成组件', 'Final-video composition'),
    ready: composerReady.value,
    hint: tr('字幕、背景音乐与通栏标题需要本机 FFmpeg。', 'Subtitles, background music and the banner title need local FFmpeg.'),
  },
  {
    id: 'account',
    label: tr('登录 BossAI（商业用途必需）', 'Sign in to BossAI (required for commercial use)'),
    ready: accountAuthenticated.value,
    hint: tr('个人本地使用无需登录；商业用途需要 Business。', 'Local personal use needs no sign-in; commercial use requires Business.'),
    optional: true,
  },
])

export const readyToCreate = computed(() =>
  readinessChecklist.value.filter((item) => !item.optional).every((item) => item.ready),
)

export async function refreshRuntimeCenter() {
  try {
    runtimeCenter.value = await getRuntimeInstallCenter()
  } catch (e) {
    runtimeCenter.value = null
    runtimeInstallMessage.value = e?.message || tr('无法读取 BossAI 运行环境状态。', 'Unable to read BossAI runtime status.')
  }
}

export async function refreshTranscriptionSetup() {
  try {
    transcriptionSetup.value = await getTranscriptionSetup()
  } catch {
    // Transcription is optional; the studio degrades to manual script entry.
    transcriptionSetup.value = null
  }
}

export async function refreshVideoAssets() {
  try {
    videoAssets.value = await getVideoAssets()
  } catch {
    // Editing assets are optional; the studio degrades to no-edit rendering.
    videoAssets.value = null
  }
}

export async function refreshLegalStatus() {
  if (!desktopLegalAvailable.value) {
    legalStatus.value = { approvedReleaseBundlePresent: false, documents: {} }
    return
  }
  try {
    legalStatus.value = await globalThis.bossaiDesktop.legalStatus()
  } catch {
    legalStatus.value = { approvedReleaseBundlePresent: false, documents: {} }
  }
}

export async function refreshStatus() {
  error.value = ''
  try {
    const [productResult, entitlementResult, eulaResult, digitalHumanResult, accountResult, publishResult] =
      await Promise.all([
        getProduct(),
        getEntitlement(),
        getEulaStatus(),
        getDigitalHumanSetup(),
        getAccountSession(),
        videoCapabilities.publishStatus(),
      ])
    product.value = productResult
    entitlement.value = entitlementResult
    eulaStatus.value = eulaResult
    digitalHumanSetup.value = digitalHumanResult
    accountSession.value = accountResult
    publishStatus.value = publishResult
    backendReady.value = true
    await Promise.all([refreshRuntimeCenter(), refreshVideoAssets(), refreshTranscriptionSetup()])
  } catch (e) {
    backendReady.value = false
    error.value = e?.message || tr('无法连接本地 BossAI Video Agent 服务。', 'Unable to connect to the local BossAI Video Agent service.')
  }
}

function normalizedRegistrationIdentifier() {
  const value = accountForm.identifier.trim()
  return /^1\d{10}$/.test(value) ? `+86${value}` : value
}

export async function requestAccountChallenge() {
  challengeBusy.value = true
  error.value = ''
  message.value = ''
  try {
    const identifier = normalizedRegistrationIdentifier()
    const result = await sendRegistrationChallenge({
      channel: identifier.includes('@') ? 'email' : 'phone',
      identifier,
      locale: locale.value,
    })
    accountForm.challengeId = String(result?.challengeId || result?.id || '')
    if (!accountForm.challengeId) throw new Error('BossAI OS 未返回注册 challenge ID')
    message.value = tr('验证码已发送，请在有效期内完成注册。', 'Verification code sent. Complete registration before it expires.')
  } catch (e) {
    error.value = e?.message || tr('验证码发送失败', 'Failed to send verification code')
  } finally {
    challengeBusy.value = false
  }
}

export async function submitAccount() {
  authBusy.value = true
  error.value = ''
  message.value = ''
  try {
    const register = authMode.value === 'register'
    const payload = {
      mode: authMode.value,
      identifier: register ? normalizedRegistrationIdentifier() : accountForm.identifier.trim(),
      password: accountForm.password,
    }
    if (register) {
      payload.displayName = accountForm.displayName.trim()
      payload.challengeId = accountForm.challengeId.trim()
      payload.verificationCode = accountForm.verificationCode.trim()
    }
    accountSession.value = await authenticateAccount(payload)
    accountForm.password = ''
    accountForm.verificationCode = ''
    await refreshStatus()
    message.value = register
      ? tr('BossAI 账号创建并登录成功。', 'BossAI account created and signed in.')
      : tr('BossAI 账号登录成功。', 'Signed in to BossAI.')
  } catch (e) {
    error.value = e?.message || tr('BossAI 账号操作失败', 'BossAI account operation failed')
  } finally {
    authBusy.value = false
  }
}

export async function signOutAccount() {
  authBusy.value = true
  error.value = ''
  try {
    await logoutAccount()
    accountSession.value = null
    entitlement.value = null
    await refreshStatus()
    message.value = tr('已退出 BossAI 账号。', 'Signed out of BossAI.')
  } catch (e) {
    error.value = e?.message || tr('退出登录失败', 'Sign-out failed')
  } finally {
    authBusy.value = false
  }
}

export async function acceptCurrentEula() {
  eulaBusy.value = true
  error.value = ''
  try {
    eulaStatus.value = await acceptEula(locale.value)
    await refreshStatus()
    message.value = tr('已接受当前版本 EULA。', 'The current-version EULA has been accepted.')
  } catch (e) {
    error.value = e?.message || tr('EULA 接受失败', 'EULA acceptance failed')
  } finally {
    eulaBusy.value = false
  }
}

export async function installRuntimeComponent(component) {
  if (!runtimeLicenseAccepted.value || runtimeInstallBusy.value) return
  runtimeInstallBusy.value = true
  runtimeInstallComponentId.value = component
  runtimeInstallMessage.value = tr('正在准备安装…', 'Preparing installation…')
  error.value = ''
  try {
    await installRuntime(component, {
      profile: runtimeInstallProfile.value,
      acceptLicense: true,
      onProgress: (job) => {
        const logs = Array.isArray(job?.logs) ? job.logs : []
        runtimeInstallMessage.value = String(logs[logs.length - 1] || job?.message || tr('正在安装…', 'Installing…'))
      },
    })
    runtimeInstallMessage.value = tr('运行环境安装完成。', 'Runtime installation completed.')
    await refreshRuntimeCenter()
    await refreshStatus()
  } catch (e) {
    error.value = e?.message || tr('运行环境安装失败', 'Runtime installation failed')
    runtimeInstallMessage.value = error.value
  } finally {
    runtimeInstallBusy.value = false
    runtimeInstallComponentId.value = ''
  }
}

export async function openLegal(documentId) {
  if (!desktopLegalAvailable.value) return
  try {
    const result = await globalThis.bossaiDesktop.openLegalDocument(documentId)
    if (!result?.opened) {
      error.value = tr('该法律文件尚未进入当前客户发行包。', 'This legal document is not in the current release bundle.')
    }
  } catch (e) {
    error.value = e?.message || tr('无法打开法律文件', 'Unable to open legal document')
  }
}

export const desktopQuitAvailable = computed(() => Boolean(globalThis?.bossaiDesktop?.quitApp))

export async function quitApp() {
  try {
    await globalThis?.bossaiDesktop?.quitApp?.()
  } catch {
    // Best-effort; there is nothing meaningful to recover from here.
  }
}

export async function openUpgrade() {
  error.value = ''
  try {
    const result = await globalThis?.bossaiDesktop?.openUpgrade?.()
    if (!result?.opened) throw new Error(result?.reason || tr('无法打开升级入口', 'Unable to open upgrade page'))
  } catch (e) {
    error.value = e?.message || tr('无法打开升级入口', 'Unable to open upgrade page')
  }
}
