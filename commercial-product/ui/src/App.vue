<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand-lockup">
        <img class="brand-mark" src="/bossai-video-mark.svg" alt="BossAI Video Agent" />
        <div>
          <strong>BossAI Video Agent</strong>
          <span>Commercial Preview · 0.1.0</span>
        </div>
      </div>

      <nav>
        <button :class="{ active: screen === 'home' }" @click="screen = 'home'">经营首页</button>
        <button :class="{ active: screen === 'studio' }" @click="screen = 'studio'">AI 口播视频</button>
        <button :class="{ active: screen === 'legal' }" @click="screen = 'legal'">关于与合规</button>
        <button disabled>多平台发布</button>
        <button disabled>团队与矩阵</button>
      </nav>

      <div class="sidebar-foot">
        <span :class="['dot', backendReady ? 'ok' : 'bad']"></span>
        <span>{{ backendReady ? '本地引擎已连接' : '本地引擎未连接' }}</span>
      </div>
    </aside>

    <main class="content">
      <header class="topbar">
        <div>
          <p class="kicker">BossAI 商业视频工作台</p>
          <h1>{{ screen === 'studio' ? 'AI 口播视频生产' : screen === 'legal' ? '关于、条款与许可' : '把内容生产变成一条清晰流水线' }}</h1>
        </div>
        <div class="top-actions">
          <span :class="['status-badge', entitlementActive ? 'success' : 'warning']">{{ entitlementLabel }}</span>
          <button class="secondary" @click="refreshStatus">刷新状态</button>
        </div>
      </header>

      <section v-if="screen === 'home'" class="home-grid">
        <article class="hero-card">
          <p class="kicker">Commercial Preview</p>
          <h2>先把文案和授权声音生产做稳定，再接入 BossAI 商业数字人。</h2>
          <p>当前商业预览只开放许可边界清晰的能力：本地文案生成、客户授权声音合成与 MuseTalk 数字人口播。人物、声音、音乐和字体必须来自 BossAI 已授权资源或客户自有授权素材。</p>
          <div class="hero-actions">
            <button class="primary" @click="screen = 'studio'">开始制作</button>
            <span v-if="previewUnlocked" class="preview-note">内部商业预览模式</span>
          </div>
        </article>

        <article class="account-card">
          <div class="panel-head">
            <div>
              <span class="step">账号</span>
              <h2>BossAI 统一账号</h2>
            </div>
            <span :class="['status-badge', accountAuthenticated ? 'success' : 'warning']">{{ accountLabel }}</span>
          </div>

          <template v-if="accountAuthenticated">
            <div class="account-summary">
              <div><span>账号</span><strong>{{ accountSession?.account?.maskedIdentifier || accountSession?.account?.displayName || '已登录' }}</strong></div>
              <div><span>当前套餐</span><strong>{{ entitlement?.planName || accountSession?.commercial?.planName || '等待授权同步' }}</strong></div>
              <div><span>可用积分</span><strong>{{ entitlement?.walletAvailable ?? accountSession?.commercial?.walletAvailable ?? 0 }}</strong></div>
            </div>
            <div class="button-row">
              <button class="secondary" :disabled="authBusy" @click="signOutAccount">退出 BossAI 账号</button>
              <button class="secondary" :disabled="authBusy" @click="refreshStatus">刷新授权</button>
            </div>
          </template>

          <template v-else>
            <p class="account-help">账号和商业授权由 BossAI OS 统一管理。本产品不保存密码、验证码或总部访问令牌。</p>
            <div class="auth-tabs">
              <button :class="{ active: authMode === 'login' }" @click="authMode = 'login'">登录</button>
              <button :class="{ active: authMode === 'register' }" @click="authMode = 'register'">注册</button>
            </div>
            <div class="grid two">
              <label>
                <span>手机号或邮箱</span>
                <input v-model.trim="accountForm.identifier" autocomplete="username" placeholder="手机号或 name@example.com" />
              </label>
              <label>
                <span>密码</span>
                <input v-model="accountForm.password" type="password" autocomplete="current-password" placeholder="至少 8 位" />
              </label>
              <label v-if="authMode === 'register'">
                <span>显示名称</span>
                <input v-model.trim="accountForm.displayName" placeholder="你的姓名或团队名称" />
              </label>
              <label v-if="authMode === 'register'">
                <span>验证码</span>
                <div class="inline-field">
                  <input v-model.trim="accountForm.verificationCode" inputmode="numeric" placeholder="验证码" />
                  <button class="secondary" :disabled="challengeBusy || !accountForm.identifier" @click="requestAccountChallenge">{{ challengeBusy ? '发送中…' : '发送验证码' }}</button>
                </div>
              </label>
            </div>
            <p v-if="authMode === 'register'" class="account-help">手机号注册建议输入国际格式；11 位中国大陆手机号会自动按 +86 发送验证码。</p>
            <button class="primary" :disabled="authBusy || !accountForm.identifier || accountForm.password.length < 8" @click="submitAccount">{{ authBusy ? '处理中…' : authMode === 'login' ? '登录 BossAI' : '创建 BossAI 账号' }}</button>
          </template>
        </article>

        <article class="runtime-card">
          <div class="panel-head">
            <div>
              <span class="step">环境</span>
              <h2>BossAI 运行环境中心</h2>
            </div>
            <span :class="['status-badge', allCoreRuntimesReady ? 'success' : 'warning']">{{ allCoreRuntimesReady ? '核心环境已就绪' : '需要安装' }}</span>
          </div>
          <p class="runtime-help">客户版不复制旧软件里的模型和运行时。所需组件从固定官方来源安装到本机 BossAI 专用目录，并保留来源、版本和许可记录。</p>
          <div class="runtime-toolbar">
            <label>
              <span>运行模式</span>
              <select v-model="runtimeInstallProfile" :disabled="runtimeInstallBusy">
                <option value="gpu">GPU（推荐）</option>
                <option value="cpu">CPU（仅文案/配音兼容模式）</option>
              </select>
            </label>
            <label class="consent-row runtime-consent">
              <input v-model="runtimeLicenseAccepted" type="checkbox" :disabled="runtimeInstallBusy" />
              <span>我已阅读并同意对应开源/第三方运行组件的许可与安装说明。</span>
            </label>
          </div>
          <div class="runtime-list">
            <div v-for="item in runtimeItems" :key="item.id" class="runtime-row">
              <div class="runtime-identity">
                <strong>{{ item.name }}</strong>
                <span>{{ item.description }}</span>
              </div>
              <span :class="['runtime-state', item.ready ? 'ready' : 'missing']">{{ item.ready ? '已就绪' : item.blockedReason || '未安装' }}</span>
              <button
                class="secondary"
                :disabled="runtimeInstallBusy || item.ready || !runtimeControlAvailable || !runtimeLicenseAccepted || !item.installable"
                @click="installRuntimeComponent(item.id)"
              >{{ runtimeInstallBusy && runtimeInstallComponentId === item.id ? '安装中…' : item.ready ? '已安装' : '安装' }}</button>
            </div>
          </div>
          <p v-if="!runtimeControlAvailable" class="runtime-note">运行环境安装只允许从 BossAI Video Agent 桌面应用发起；浏览器页面无权执行本机安装。</p>
          <p v-if="runtimeInstallMessage" class="runtime-log">{{ runtimeInstallMessage }}</p>
        </article>

        <article class="metric-card">
          <span>商业授权</span>
          <strong>{{ entitlementLabel }}</strong>
          <p>{{ entitlementReason }}</p>
        </article>

        <article class="metric-card">
          <span>当前 TTS</span>
          <strong>CosyVoice2</strong>
          <p>商业 profile 强制使用许可边界清晰的 CosyVoice2；必须选择客户已授权的参考声音。</p>
        </article>

        <article class="metric-card">
          <span>数字人引擎</span>
          <strong>MuseTalk 接入中</strong>
          <p>商业版数字人口播统一使用 MuseTalk，并要求客户提供已获得商业使用授权的人物视频。</p>
        </article>
      </section>

      <section v-else-if="screen === 'legal'" class="home-grid">
        <article class="hero-card">
          <p class="kicker">BossAI Video Agent · 0.1.0</p>
          <h2>产品身份、客户条款与第三方许可都应在客户机器上可直接查看。</h2>
          <p>正式客户法律文件只有在完成审批并进入发行包后才显示为可用。商业预览不会把草稿或内部治理文件冒充为正式条款。</p>
          <span :class="['status-badge', legalReleaseReady ? 'success' : 'warning']">{{ legalReleaseReady ? '客户法律包已批准' : '客户法律包尚未批准' }}</span>
        </article>

        <article class="account-card">
          <div class="panel-head">
            <div><span class="step">法律</span><h2>客户文件</h2></div>
            <span class="hint">仅打开发行包白名单文件</span>
          </div>
          <div class="runtime-list">
            <div v-for="item in legalDocuments" :key="item.id" class="runtime-row">
              <div class="runtime-identity">
                <strong>{{ item.name }}</strong>
                <span>{{ item.description }}</span>
              </div>
              <span :class="['runtime-state', item.available ? 'ready' : 'missing']">{{ item.available ? '可查看' : '未进入发行包' }}</span>
              <button class="secondary" :disabled="!item.available || !desktopLegalAvailable" @click="openLegal(item.id)">打开</button>
            </div>
          </div>
          <p v-if="!desktopLegalAvailable" class="runtime-note">法律文件查看入口只在 BossAI Video Agent 桌面应用中启用。</p>
        </article>

        <article class="metric-card">
          <span>商业权威</span>
          <strong>BossAI Headquarters Commerce</strong>
          <p>账号、套餐、设备、积分和商业授权统一由 BossAI 商业系统管理；本产品不创建第二套收费权威。</p>
        </article>

        <article class="metric-card">
          <span>本地数据原则</span>
          <strong>Local-first</strong>
          <p>客户声音、人物视频和生成成果默认保存在本机；商业授权快照不应包含客户业务内容或 Provider Key。</p>
        </article>
      </section>

      <section v-else class="studio-layout">
        <div v-if="!executionAllowed" class="license-blocker">
          <strong>商业执行尚未授权</strong>
          <p>{{ entitlementReason }}</p>
          <p>正式客户版不会在 entitlement 未验证时启动付费 AI 任务。</p>
        </div>

        <article class="panel">
          <div class="panel-head">
            <div><span class="step">01</span><h2>定义内容</h2></div>
            <span class="hint">先给 AI 足够的业务背景</span>
          </div>
          <label>
            <span>原始文案或素材</span>
            <textarea v-model="form.sourceText" rows="7" placeholder="粘贴已有口播、产品资料、门店介绍或你想表达的核心内容"></textarea>
          </label>
          <div class="grid two">
            <label><span>投放平台</span><select v-model="form.platform"><option value="douyin">抖音</option><option value="channels">视频号</option><option value="xiaohongshu">小红书</option><option value="kuaishou">快手</option></select></label>
            <label><span>目标字数</span><input v-model.number="form.targetChars" type="number" min="80" max="1600" /></label>
            <label><span>行业 / 人设</span><input v-model="form.industryPersona" placeholder="例如：餐饮老板、家装顾问" /></label>
            <label><span>产品 / 服务</span><input v-model="form.productBusiness" placeholder="你卖什么" /></label>
            <label><span>核心卖点</span><input v-model="form.sellingPoints" placeholder="客户为什么要选你" /></label>
            <label><span>表达风格</span><input v-model="form.toneStyle" placeholder="专业、直接、接地气……" /></label>
          </div>
          <button class="primary" :disabled="busy || !rewriteAllowed || !form.sourceText.trim()" @click="rewrite">{{ busyAction === 'rewrite' ? '正在改写…' : 'AI 改写文案' }}</button>
          <p v-if="executionAllowed && !rewriteAllowed" class="feature-lock">当前套餐未包含 AI 文案改写。</p>
          <label>
            <span>最终口播文案</span>
            <textarea v-model="form.scriptText" rows="9" placeholder="AI 改写结果会出现在这里，也可以手工调整"></textarea>
          </label>
        </article>

        <article class="panel">
          <div class="panel-head">
            <div><span class="step">02</span><h2>使用已授权声音生成配音</h2></div>
            <span class="hint">商业 profile 固定 CosyVoice2</span>
          </div>

          <div class="policy-card">
            <strong>声音权利确认</strong>
            <p>只上传你本人、公司拥有，或已经获得明确商业合成授权的参考声音。BossAI 不提供或默认启用来源不明的参考声音。</p>
          </div>

          <div class="grid two">
            <label>
              <span>声音名称</span>
              <input v-model="voiceDisplayName" placeholder="例如：品牌主理人授权音色" />
            </label>
            <label>
              <span>上传参考声音 WAV</span>
              <input type="file" accept="audio/wav,.wav" @change="selectVoiceFile" />
            </label>
          </div>

          <label class="consent-row">
            <input v-model="voiceRightsConfirmed" type="checkbox" />
            <span>我确认对本次上传声音拥有合法使用和商业语音合成授权。</span>
          </label>

          <div class="button-row">
            <button class="secondary" :disabled="busy || voiceUploading || !voiceFile || !voiceRightsConfirmed" @click="uploadAuthorizedVoice">{{ voiceUploading ? '正在上传…' : '保存授权声音' }}</button>
          </div>

          <label>
            <span>本机已授权声音</span>
            <select v-model="form.voiceId">
              <option value="">请选择已授权声音</option>
              <option v-for="voice in voices" :key="itemId(voice)" :value="itemId(voice)">{{ itemName(voice, '授权声音') }}</option>
            </select>
          </label>

          <button class="primary" :disabled="busy || !ttsAllowed || !form.scriptText.trim() || !form.voiceId || !voiceRightsConfirmed" @click="makeVoice">{{ busyAction === 'tts' ? '正在生成配音…' : '生成 CosyVoice2 配音' }}</button>
          <p v-if="executionAllowed && !ttsAllowed" class="feature-lock">当前套餐未包含授权声音配音。</p>
          <div class="result-box"><span>配音</span><code>{{ audioUrl || '尚未生成' }}</code></div>
        </article>

        <article class="panel replacement-panel">
          <div class="panel-head">
            <div><span class="step">03</span><h2>授权数字人口播</h2></div>
            <span class="hint">MuseTalk v1.5</span>
          </div>
          <div class="replacement-state">
            <div class="replacement-icon">M</div>
            <div>
              <strong>{{ digitalHumanSetup?.ready ? 'MuseTalk 商业数字人已就绪' : 'MuseTalk 商业运行环境待安装' }}</strong>
              <p v-if="digitalHumanSetup?.ready">只使用你本人、公司拥有或已取得明确商业合成授权的头像视频。BossAI 商业版不会提供来源不明的默认人物素材。</p>
              <p v-else>{{ digitalHumanMissingLabel }}</p>
            </div>
          </div>

          <template v-if="digitalHumanSetup?.ready">
            <div class="grid two">
              <label>
                <span>上传授权头像视频</span>
                <input type="file" accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm,.mkv" @change="selectAvatarFile" />
              </label>
              <label>
                <span>已登记素材</span>
                <input :value="avatarId ? '已保存到 BossAI 本机素材库' : '尚未上传'" disabled />
              </label>
            </div>
            <label class="consent-row">
              <input v-model="avatarRightsConfirmed" type="checkbox" />
              <span>我确认对该人物形象和视频拥有合法使用及商业数字人合成授权。</span>
            </label>
            <div class="button-row">
              <button class="secondary" :disabled="busy || avatarUploading || !avatarFile || !avatarRightsConfirmed" @click="uploadAuthorizedAvatar">{{ avatarUploading ? '正在保存…' : '保存授权头像视频' }}</button>
              <button class="primary" :disabled="busy || !digitalHumanAllowed || !avatarId || !audioUrl || !avatarRightsConfirmed" @click="makeDigitalHuman">{{ busyAction === 'musetalk' ? '正在生成数字人口播…' : '生成数字人口播' }}</button>
              <p v-if="executionAllowed && !digitalHumanAllowed" class="feature-lock">当前套餐未包含数字人口播。</p>
            </div>
            <div class="result-box"><span>数字人口播</span><code>{{ digitalHumanUrl || '尚未生成' }}</code></div>
            <video v-if="digitalHumanUrl" class="result-video" controls :src="apiUrl(digitalHumanUrl)"></video>
          </template>
          <button v-else class="secondary" disabled>等待安装 MuseTalk 商业运行环境</button>
        </article>

        <article class="panel">
          <div class="panel-head">
            <div><span class="step">04</span><h2>生成成片并导出</h2></div>
            <span class="hint">本地成果不因授权到期被锁定</span>
          </div>
          <div class="grid two">
            <label>
              <span>项目名称</span>
              <input v-model.trim="projectName" maxlength="120" placeholder="例如：8月30日产品口播" />
            </label>
            <label>
              <span>成片来源</span>
              <input :value="digitalHumanUrl ? 'BossAI 商业数字人口播' : '请先完成数字人口播'" disabled />
            </label>
          </div>
          <div class="button-row">
            <button class="primary" :disabled="busy || !digitalHumanUrl" @click="finalizeVideo">{{ busyAction === 'finalize' ? '正在生成成片…' : '生成最终成片' }}</button>
            <button class="secondary" :disabled="exportBusy || !finalVideoUrl || !desktopExportAvailable" @click="exportFinalVideo">{{ exportBusy ? '正在导出…' : '导出 MP4' }}</button>
          </div>
          <p v-if="!desktopExportAvailable" class="runtime-note">文件导出仅在 BossAI Video Agent 桌面应用中启用；浏览器预览不会获得本机任意文件写入权限。</p>
          <div class="result-box final"><span>最终成片</span><code>{{ finalVideoUrl || '尚未生成' }}</code></div>
          <video v-if="finalVideoUrl" class="result-video" controls :src="apiUrl(finalVideoUrl)"></video>
        </article>

        <article class="panel">
          <div class="panel-head">
            <div><span class="step">05</span><h2>发布</h2></div>
            <span class="hint">自动发布继续 fail-closed</span>
          </div>
          <div class="policy-card">
            <strong>{{ publishStatus?.automatedPublishAllowed ? '自动发布已连接' : '自动发布尚未开放' }}</strong>
            <p>{{ publishStatus?.reason || '等待读取 BossAI 发布治理状态。' }}</p>
          </div>
          <div class="grid two">
            <label>
              <span>目标平台</span>
              <select v-model="form.platform"><option value="douyin">抖音</option><option value="channels">视频号</option><option value="xiaohongshu">小红书</option><option value="kuaishou">快手</option></select>
            </label>
            <label>
              <span>当前发布模式</span>
              <input :value="publishStatus?.automatedPublishAllowed ? 'BossAI 治理发布' : '本地导出 + 人工发布'" disabled />
            </label>
          </div>
          <div class="button-row">
            <button class="secondary" :disabled="busy || !finalVideoUrl" @click="preparePublish">检查发布条件</button>
          </div>
          <div v-if="publishPreparation" class="result-box final"><span>发布状态</span><code>{{ publishPreparation.status }} · {{ publishPreparation.reason }}</code></div>
        </article>

        <p v-if="error" class="error-banner">{{ error }}</p>
        <p v-if="message" class="message-banner">{{ message }}</p>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import {
  apiUrl,
  authenticateAccount,
  getAccountSession,
  getDigitalHumanSetup,
  getEntitlement,
  getProduct,
  getRuntimeInstallCenter,
  hasLocalRuntimeControl,
  installRuntime,
  listVoices,
  logoutAccount,
  sendRegistrationChallenge,
  uploadAvatarVideo,
  uploadVoice,
} from './api.js'
import { videoCapabilities } from './capabilities/video-capability-adapter.js'

const screen = ref('home')
const product = ref(null)
const entitlement = ref(null)
const accountSession = ref(null)
const digitalHumanSetup = ref(null)
const runtimeCenter = ref(null)
const legalStatus = ref(null)
const runtimeLicenseAccepted = ref(false)
const runtimeInstallProfile = ref('gpu')
const runtimeInstallBusy = ref(false)
const runtimeInstallComponentId = ref('')
const runtimeInstallMessage = ref('')
const backendReady = ref(false)
const voices = ref([])
const busy = ref(false)
const busyAction = ref('')
const message = ref('')
const error = ref('')
const audioUrl = ref('')
const voiceFile = ref(null)
const voiceDisplayName = ref('')
const voiceRightsConfirmed = ref(false)
const voiceUploading = ref(false)
const avatarFile = ref(null)
const avatarId = ref('')
const avatarRightsConfirmed = ref(false)
const avatarUploading = ref(false)
const digitalHumanUrl = ref('')
const projectName = ref('')
const finalVideoUrl = ref('')
const finalDownloadName = ref('')
const exportBusy = ref(false)
const publishStatus = ref(null)
const publishPreparation = ref(null)
const authMode = ref('login')
const authBusy = ref(false)
const challengeBusy = ref(false)
const accountForm = reactive({
  identifier: '',
  password: '',
  displayName: '',
  challengeId: '',
  verificationCode: '',
})

const form = reactive({
  sourceText: '',
  scriptText: '',
  platform: 'douyin',
  targetChars: 300,
  industryPersona: '',
  productBusiness: '',
  sellingPoints: '',
  toneStyle: '',
  voiceId: '',
})

const previewUnlocked = import.meta.env.VITE_BOSSAI_COMMERCIAL_PREVIEW === '1'
const accountAuthenticated = computed(() => Boolean(accountSession.value?.authenticated))
const accountLabel = computed(() => {
  if (accountAuthenticated.value) return '已登录'
  if (accountSession.value?.sessionStatus === 'not_configured') return 'BossAI OS 未连接'
  if (accountSession.value?.sessionStatus === 'expired') return '登录已过期'
  return '未登录'
})
const entitlementActive = computed(() => Boolean(entitlement.value?.verified && entitlement.value?.paidExecutionAllowed))
const executionAllowed = computed(() => entitlementActive.value || previewUnlocked)
const entitledFeatures = computed(() => new Set(Array.isArray(entitlement.value?.features) ? entitlement.value.features : []))
const rewriteAllowed = computed(() => previewUnlocked || (entitlementActive.value && entitledFeatures.value.has('video.rewrite')))
const ttsAllowed = computed(() => previewUnlocked || (entitlementActive.value && entitledFeatures.value.has('video.tts')))
const digitalHumanAllowed = computed(() => previewUnlocked || (entitlementActive.value && entitledFeatures.value.has('video.digital-human')))
const entitlementLabel = computed(() => {
  if (entitlementActive.value) return '商业授权已生效'
  if (entitlement.value?.status === 'unconfigured') return '商业授权未连接'
  if (!backendReady.value) return '本地服务未连接'
  return '商业授权未验证'
})
const entitlementReason = computed(() => entitlement.value?.reason || '等待 BossAI 商业授权状态。')
const digitalHumanMissingLabel = computed(() => {
  const missing = Array.isArray(digitalHumanSetup.value?.missing) ? digitalHumanSetup.value.missing : []
  if (!missing.length) return 'MuseTalk 商业运行环境尚未完成配置。'
  const labels = {
    adapter: '数字人适配器',
    'model-runtime': 'MuseTalk 模型文件',
    'python-runtime': 'MuseTalk Python 运行环境',
    'ffmpeg-runtime': 'FFmpeg 运行环境',
    'runtime-component': 'MuseTalk 运行组件',
  }
  return `缺少：${missing.map((item) => labels[item] || item).join('、')}`
})
const runtimeControlAvailable = computed(() => hasLocalRuntimeControl())
const runtimeItems = computed(() => {
  const center = runtimeCenter.value || {}
  const support = center.support || {}
  const components = center.components || {}
  const python = support.python310 || {}
  const ffmpeg = support.ffmpeg || {}
  const qwen = components.qwen || {}
  const cosy = components.cosyvoice2 || {}
  const muse = components.musetalk || {}
  return [
    {
      id: 'python310',
      name: 'BossAI Python 3.10',
      description: '独立安装到 BossAI 本机目录，不修改系统 PATH。',
      ready: Boolean(python.ready),
      installable: Boolean(center.powershellReady && python.installerAvailable),
      blockedReason: center.powershellReady ? '' : '缺少 PowerShell',
    },
    {
      id: 'qwen',
      name: 'Qwen 本地文案引擎',
      description: '固定官方版本，用于本地文案生成与改写。',
      ready: Boolean(qwen.ready),
      installable: Boolean(qwen.installable),
      blockedReason: python.ready ? '' : '先安装 Python 3.10',
    },
    {
      id: 'cosyvoice2',
      name: 'CosyVoice2 配音引擎',
      description: '固定官方版本，只使用客户授权或 BossAI 自有声音。',
      ready: Boolean(cosy.ready),
      installable: Boolean(cosy.installable),
      blockedReason: python.ready ? '' : '先安装 Python 3.10',
    },
    {
      id: 'musetalk',
      name: 'MuseTalk 数字人引擎',
      description: '用于客户授权人物视频的数字人口播合成。',
      ready: Boolean(muse.ready),
      installable: Boolean(muse.installable),
      blockedReason: !python.ready ? '先安装 Python 3.10' : !ffmpeg.ready ? '需要 FFmpeg' : '',
    },
  ]
})
const allCoreRuntimesReady = computed(() => runtimeItems.value.every((item) => item.ready))
const desktopLegalAvailable = computed(() => Boolean(globalThis?.bossaiDesktop?.legalStatus && globalThis?.bossaiDesktop?.openLegalDocument))
const desktopExportAvailable = computed(() => Boolean(globalThis?.bossaiDesktop?.exportFinalVideo))
const legalReleaseReady = computed(() => Boolean(legalStatus.value?.approvedReleaseBundlePresent))
const legalDocuments = computed(() => {
  const available = legalStatus.value?.documents || {}
  return [
    { id: 'terms', name: '客户服务条款', description: '正式服务范围、商业授权、付款退款、第三方组件与争议条款。', available: Boolean(available.terms) },
    { id: 'privacy', name: '隐私说明', description: '本地数据、账号商业信息、云端处理和第三方服务边界。', available: Boolean(available.privacy) },
    { id: 'voiceAvatar', name: '声音与人物素材授权确认', description: '客户声音、肖像与人物视频的合法商业授权确认。', available: Boolean(available.voiceAvatar) },
    { id: 'support', name: '安装与支持说明', description: '运行环境、支持渠道、迁移、退款与售后说明。', available: Boolean(available.support) },
    { id: 'notices', name: '第三方组件说明', description: '客户发行包内第三方组件、许可证和模型使用边界。', available: Boolean(available.notices) },
  ]
})

function normalizeList(value) {
  if (Array.isArray(value)) return value
  if (Array.isArray(value?.items)) return value.items
  if (Array.isArray(value?.data)) return value.data
  return []
}
function itemId(item) { return String(item?.id || item?.voiceId || '') }
function itemName(item, fallback) { return String(item?.name || item?.title || item?.displayName || item?.fileName || item?.filename || itemId(item) || fallback) }
function isBlockedDefaultVoice(item) {
  const id = itemId(item).trim().toLowerCase()
  return !id || ['zst', '__default__', 'default'].includes(id)
}

function selectVoiceFile(event) {
  const [file] = Array.from(event?.target?.files || [])
  voiceFile.value = file || null
}

function selectAvatarFile(event) {
  const [file] = Array.from(event?.target?.files || [])
  avatarFile.value = file || null
  avatarId.value = ''
  digitalHumanUrl.value = ''
  finalVideoUrl.value = ''
  finalDownloadName.value = ''
  publishPreparation.value = null
}

async function refreshVoices() {
  const result = await listVoices()
  voices.value = normalizeList(result).filter((item) => !isBlockedDefaultVoice(item))
  if (form.voiceId && !voices.value.some((item) => itemId(item) === form.voiceId)) form.voiceId = ''
}

async function uploadAuthorizedVoice() {
  if (!voiceFile.value || !voiceRightsConfirmed.value) return
  voiceUploading.value = true
  error.value = ''
  try {
    const result = await uploadVoice(voiceFile.value, voiceDisplayName.value)
    await refreshVoices()
    const uploadedId = itemId(result)
    if (uploadedId && voices.value.some((item) => itemId(item) === uploadedId)) form.voiceId = uploadedId
    message.value = '授权声音已保存到本机。'
  } catch (e) {
    error.value = e?.message || '声音上传失败'
  } finally {
    voiceUploading.value = false
  }
}

async function refreshLegalStatus() {
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

async function openLegal(documentId) {
  if (!desktopLegalAvailable.value) return
  try {
    const result = await globalThis.bossaiDesktop.openLegalDocument(documentId)
    if (!result?.opened) error.value = '该法律文件尚未进入当前客户发行包。'
  } catch (e) {
    error.value = e?.message || '无法打开法律文件'
  }
}

async function refreshRuntimeCenter() {
  try {
    runtimeCenter.value = await getRuntimeInstallCenter()
  } catch (e) {
    runtimeCenter.value = null
    runtimeInstallMessage.value = e?.message || '无法读取 BossAI 运行环境状态。'
  }
}

async function installRuntimeComponent(component) {
  if (!runtimeLicenseAccepted.value || runtimeInstallBusy.value) return
  runtimeInstallBusy.value = true
  runtimeInstallComponentId.value = component
  runtimeInstallMessage.value = '正在准备安装…'
  error.value = ''
  try {
    await installRuntime(component, {
      profile: runtimeInstallProfile.value,
      acceptLicense: true,
      onProgress: (job) => {
        const lastLog = Array.isArray(job?.logs) && job.logs.length ? job.logs[job.logs.length - 1] : ''
        runtimeInstallMessage.value = String(lastLog || job?.message || '正在安装…')
      },
    })
    runtimeInstallMessage.value = '运行环境安装完成。'
    await refreshRuntimeCenter()
    await refreshStatus()
  } catch (e) {
    error.value = e?.message || '运行环境安装失败'
    runtimeInstallMessage.value = error.value
  } finally {
    runtimeInstallBusy.value = false
    runtimeInstallComponentId.value = ''
  }
}

async function refreshStatus() {
  error.value = ''
  try {
    const [productResult, entitlementResult, digitalHumanResult, accountResult, publishResult] = await Promise.all([
      getProduct(),
      getEntitlement(),
      getDigitalHumanSetup(),
      getAccountSession(),
      videoCapabilities.publishStatus(),
    ])
    product.value = productResult
    entitlement.value = entitlementResult
    digitalHumanSetup.value = digitalHumanResult
    accountSession.value = accountResult
    publishStatus.value = publishResult
    backendReady.value = true
    await refreshRuntimeCenter()
  } catch (e) {
    backendReady.value = false
    error.value = e?.message || '无法连接本地 BossAI Video Agent 服务。'
  }
}

function normalizedRegistrationIdentifier() {
  const value = accountForm.identifier.trim()
  if (/^1\d{10}$/.test(value)) return `+86${value}`
  return value
}

async function requestAccountChallenge() {
  challengeBusy.value = true
  error.value = ''
  message.value = ''
  try {
    const identifier = normalizedRegistrationIdentifier()
    const channel = identifier.includes('@') ? 'email' : 'phone'
    const result = await sendRegistrationChallenge({ channel, identifier, locale: 'zh-CN' })
    accountForm.challengeId = String(result?.challengeId || result?.id || '')
    if (!accountForm.challengeId) throw new Error('BossAI OS 未返回注册 challenge ID')
    message.value = '验证码已发送，请在有效期内完成注册。'
  } catch (e) {
    error.value = e?.message || '验证码发送失败'
  } finally {
    challengeBusy.value = false
  }
}

async function submitAccount() {
  authBusy.value = true
  error.value = ''
  message.value = ''
  try {
    const payload = {
      mode: authMode.value,
      identifier: authMode.value === 'register' ? normalizedRegistrationIdentifier() : accountForm.identifier.trim(),
      password: accountForm.password,
    }
    if (authMode.value === 'register') {
      payload.displayName = accountForm.displayName.trim()
      payload.challengeId = accountForm.challengeId.trim()
      payload.verificationCode = accountForm.verificationCode.trim()
    }
    accountSession.value = await authenticateAccount(payload)
    accountForm.password = ''
    accountForm.verificationCode = ''
    await refreshStatus()
    message.value = authMode.value === 'login' ? 'BossAI 账号登录成功。' : 'BossAI 账号创建并登录成功。'
  } catch (e) {
    error.value = e?.message || 'BossAI 账号操作失败'
  } finally {
    authBusy.value = false
  }
}

async function signOutAccount() {
  authBusy.value = true
  error.value = ''
  try {
    await logoutAccount()
    accountSession.value = null
    entitlement.value = null
    await refreshStatus()
    message.value = '已退出 BossAI 账号。'
  } catch (e) {
    error.value = e?.message || '退出登录失败'
  } finally {
    authBusy.value = false
  }
}

async function run(action, name) {
  busy.value = true
  busyAction.value = name
  error.value = ''
  message.value = ''
  try {
    return await action()
  } catch (e) {
    error.value = e?.message || '任务执行失败'
    throw e
  } finally {
    busy.value = false
    busyAction.value = ''
  }
}

async function rewrite() {
  await run(async () => {
    const result = await videoCapabilities.rewrite(form.sourceText, form)
    form.scriptText = String(result?.rewriteText || result || '')
    message.value = '文案已生成，可以继续调整后制作配音。'
  }, 'rewrite').catch(() => {})
}

async function makeVoice() {
  await run(async () => {
    const result = await videoCapabilities.tts({ text: form.scriptText, voiceId: form.voiceId, language: 'zh' }, (job) => {
      message.value = job?.message || '正在生成 CosyVoice2 配音…'
    })
    audioUrl.value = result?.fileUrl || ''
    digitalHumanUrl.value = ''
    finalVideoUrl.value = ''
    finalDownloadName.value = ''
    publishPreparation.value = null
    message.value = 'CosyVoice2 配音生成完成。'
  }, 'tts').catch(() => {})
}

async function uploadAuthorizedAvatar() {
  if (!avatarFile.value || !avatarRightsConfirmed.value) return
  avatarUploading.value = true
  error.value = ''
  try {
    const result = await uploadAvatarVideo(avatarFile.value)
    avatarId.value = String(result?.avatarId || '')
    digitalHumanUrl.value = ''
    message.value = '授权头像视频已保存到 BossAI 本机素材库。'
  } catch (e) {
    error.value = e?.message || '头像视频上传失败'
  } finally {
    avatarUploading.value = false
  }
}

async function makeDigitalHuman() {
  await run(async () => {
    const result = await videoCapabilities.digitalHuman({
      avatarId: avatarId.value,
      audioUrl: audioUrl.value,
    }, (job) => {
      message.value = job?.message || '正在生成 MuseTalk 数字人口播…'
    })
    digitalHumanUrl.value = String(result?.fileUrl || '')
    finalVideoUrl.value = ''
    finalDownloadName.value = ''
    publishPreparation.value = null
    message.value = 'MuseTalk 数字人口播生成完成。'
  }, 'musetalk').catch(() => {})
}

async function finalizeVideo() {
  await run(async () => {
    const result = await videoCapabilities.renderVideo({
      sourceUrl: digitalHumanUrl.value,
      projectName: projectName.value,
    })
    finalVideoUrl.value = String(result?.fileUrl || '')
    finalDownloadName.value = String(result?.downloadName || 'BossAI-Video.mp4')
    publishPreparation.value = null
    message.value = '最终成片已生成并保存在 BossAI 本机数据目录。'
  }, 'finalize').catch(() => {})
}

async function exportFinalVideo() {
  if (!desktopExportAvailable.value || !finalVideoUrl.value) return
  exportBusy.value = true
  error.value = ''
  try {
    const result = await globalThis.bossaiDesktop.exportFinalVideo(
      finalVideoUrl.value,
      finalDownloadName.value || 'BossAI-Video.mp4',
    )
    if (result?.canceled) {
      message.value = '已取消导出。'
    } else if (result?.exported) {
      message.value = `成片已导出：${result.filePath}`
    } else {
      throw new Error(result?.reason || '成片导出失败')
    }
  } catch (e) {
    error.value = e?.message || '成片导出失败'
  } finally {
    exportBusy.value = false
  }
}

async function preparePublish() {
  await run(async () => {
    publishPreparation.value = await videoCapabilities.publish({
      finalVideoUrl: finalVideoUrl.value,
      platform: form.platform,
    })
    message.value = publishPreparation.value?.automatedPublishAllowed
      ? '发布条件已满足。'
      : '自动发布继续保持关闭；成片可正常导出并由用户手工发布。'
  }, 'publish').catch(() => {})
}

onMounted(async () => {
  await refreshLegalStatus()
  await refreshStatus()
  try {
    await refreshVoices()
  } catch {
    // Commercial UI can still load even when local voice storage is unavailable.
  }
})
</script>
