<template>
  <section class="studio-layout">
    <div v-if="!executionAllowed" class="license-blocker">
      <strong>{{ tr('当前账号/套餐/额度/EULA 尚未允许 AI 执行', 'Current account/plan/quota/EULA does not allow AI execution yet') }}</strong>
      <p>{{ entitlementReason }}</p>
      <p>{{ tr('Free Personal 本地核心能力仅要求接受当前许可条款；Personal Pro、BossAI Gateway 与所有商业用途仍需要有效 BossAI entitlement，其中商业用途必须为 Business。', 'Local core features in Free Personal require acceptance of the current license terms only. Personal Pro, BossAI Gateway, and all commercial use still require a valid BossAI entitlement, and commercial use requires Business.') }}</p>
      <div class="button-row"><button class="secondary" @click="goTo('settings')">{{ tr('前往设置', 'Open settings') }}</button></div>
    </div>

    <article class="panel">
      <div class="panel-head">
        <div><span class="step">01</span><h2>{{ tr('文案仿写', 'Script') }}</h2></div>
        <span class="hint">{{ tr('先给 AI 足够的业务背景', 'Give AI enough business context first') }}</span>
      </div>
      <label>
        <span>{{ tr('原始文案或素材', 'Source copy or material') }}</span>
        <textarea v-model="form.sourceText" rows="7" :placeholder="tr('粘贴已有口播、产品资料、门店介绍或你想表达的核心内容', 'Paste an existing script, product information, store introduction, or the core message you want to express')"></textarea>
      </label>
      <div class="grid two">
        <label>
          <span>{{ tr('视频类型', 'Video type') }}</span>
          <select v-model="form.videoType">
            <option v-for="[value, zh, en] in VIDEO_TYPES" :key="value" :value="value">{{ tr(zh, en) }}</option>
          </select>
        </label>
        <label>
          <span>{{ tr('投放平台', 'Platform') }}</span>
          <select v-model="form.platform">
            <option v-for="[value, zh, en] in PLATFORMS" :key="value" :value="value">{{ tr(zh, en) }}</option>
          </select>
        </label>
        <label><span>{{ tr('目标字数', 'Target length') }}</span><input v-model.number="form.targetChars" type="number" min="80" max="1600" /></label>
        <label><span>{{ tr('行业 / 人设', 'Industry / persona') }}</span><input v-model="form.industryPersona" :placeholder="tr('例如：餐饮老板、家装顾问', 'e.g. restaurant owner, home renovation advisor')" /></label>
        <label><span>{{ tr('产品 / 服务', 'Product / service') }}</span><input v-model="form.productBusiness" :placeholder="tr('你卖什么', 'What do you sell?')" /></label>
        <label><span>{{ tr('核心卖点', 'Key selling points') }}</span><input v-model="form.sellingPoints" :placeholder="tr('客户为什么要选你', 'Why should customers choose you?')" /></label>
        <label><span>{{ tr('表达风格', 'Tone') }}</span><input v-model="form.toneStyle" :placeholder="tr('专业、直接、接地气……', 'Professional, direct, conversational…')" /></label>
        <label><span>{{ tr('补充要求', 'Extra requirements') }}</span><input v-model="form.extraRequirements" :placeholder="tr('必须提到的信息、禁止出现的说法…', 'Must-mention details, phrases to avoid…')" /></label>
      </div>
      <button class="primary" :disabled="busy || !rewriteAllowed || !form.sourceText.trim()" @click="rewrite">
        {{ busyAction === 'rewrite' ? tr('正在改写…', 'Rewriting…') : tr('AI 改写文案', 'Rewrite with AI') }}
      </button>
      <p v-if="executionAllowed && !rewriteAllowed" class="feature-lock">{{ tr('当前套餐未包含 AI 文案改写。', 'Your current plan does not include AI rewrite.') }}</p>
      <label>
        <span>{{ tr('最终口播文案', 'Final talking script') }}</span>
        <textarea v-model="form.scriptText" rows="9" :placeholder="tr('AI 改写结果会出现在这里，也可以手工调整', 'The AI rewrite appears here and can be edited manually')"></textarea>
      </label>
    </article>

    <article class="panel">
      <div class="panel-head">
        <div><span class="step">02</span><h2>{{ tr('标题话题', 'Title & hashtags') }}</h2></div>
        <span class="hint">{{ tr('根据口播文案生成发布信息', 'Publishing metadata from the script') }}</span>
      </div>
      <div class="button-row">
        <button class="primary" :disabled="busy || !rewriteAllowed || !form.scriptText.trim()" @click="makeTitle">
          {{ busyAction === 'title' ? tr('生成中…', 'Generating…') : tr('生成标题和话题', 'Generate title & hashtags') }}
        </button>
      </div>
      <div class="grid two">
        <label>
          <span>{{ tr('标题', 'Title') }}<em v-if="titleLimit"> · {{ tr(`不超过 ${titleLimit} 字`, `max ${titleLimit} chars`) }}</em></span>
          <textarea v-model="title" rows="3" :placeholder="tr('生成后可继续编辑', 'Editable after generation')"></textarea>
        </label>
        <label>
          <span>{{ tr('话题标签', 'Hashtags') }}</span>
          <textarea v-model="topics" rows="3" placeholder="#话题1 #话题2"></textarea>
        </label>
      </div>
      <p class="hint">{{ tr('标题与话题只依据你的口播文案提炼，不会编造价格、资质或效果承诺。各平台发布时仍会应用自己的格式限制。', 'Titles and hashtags are derived only from your script; no prices, credentials or outcome claims are invented. Each platform still applies its own formatting limits at publish time.') }}</p>
    </article>

    <article class="panel">
      <div class="panel-head">
        <div><span class="step">03</span><h2>{{ tr('使用已授权声音生成配音', 'Generate voiceover with an authorized voice') }}</h2></div>
        <span class="hint">{{ tr('本地 CosyVoice2 · 仅使用授权声音', 'Local CosyVoice2 · authorized voices only') }}</span>
      </div>

      <div class="policy-card">
        <strong>{{ tr('声音权利确认', 'Voice rights confirmation') }}</strong>
        <p>{{ tr('只上传你本人、公司拥有，或已经获得明确合成授权的参考声音。BossAI 不提供或默认启用来源不明的参考声音。', 'Upload only reference voices you own or are explicitly authorized to synthesize. BossAI does not provide or enable unknown-rights default voices.') }}</p>
      </div>

      <div class="grid two">
        <label><span>{{ tr('声音名称', 'Voice name') }}</span><input v-model="voiceDisplayName" :placeholder="tr('例如：品牌主理人授权音色', 'e.g. Authorized brand-owner voice')" /></label>
        <label><span>{{ tr('上传参考声音 WAV', 'Upload reference WAV') }}</span><input type="file" accept="audio/wav,.wav" @change="selectVoiceFile" /></label>
      </div>

      <label class="consent-row">
        <input v-model="voiceRightsConfirmed" type="checkbox" />
        <span>{{ tr('我确认对本次上传声音拥有与当前用途相匹配的合法使用和语音合成授权。', 'I confirm I have lawful voice-synthesis rights matching the intended use.') }}</span>
      </label>

      <div class="button-row">
        <button class="secondary" :disabled="busy || voiceUploading || !voiceFile || !voiceRightsConfirmed" @click="uploadAuthorizedVoice">
          {{ voiceUploading ? tr('正在上传…', 'Uploading…') : tr('保存授权声音', 'Save authorized voice') }}
        </button>
        <button class="secondary" @click="goTo('assets')">{{ tr('管理音色', 'Manage voices') }}</button>
      </div>

      <label>
        <span>{{ tr('本机已授权声音', 'Authorized local voices') }}</span>
        <select v-model="form.voiceId">
          <option value="">{{ tr('请选择已授权声音', 'Select an authorized voice') }}</option>
          <option v-for="voice in voices" :key="assetId(voice)" :value="assetId(voice)">{{ assetName(voice, tr('授权声音', 'Authorized voice')) }}</option>
        </select>
      </label>

      <button class="primary" :disabled="busy || !ttsAllowed || !form.scriptText.trim() || !form.voiceId || !voiceRightsConfirmed" @click="makeVoice">
        {{ busyAction === 'tts' ? tr('正在生成配音…', 'Generating voiceover…') : tr('生成 CosyVoice2 配音', 'Generate CosyVoice2 voiceover') }}
      </button>
      <p v-if="executionAllowed && !ttsAllowed" class="feature-lock">{{ tr('当前套餐未包含授权声音配音。', 'Your current plan does not include voiceover generation.') }}</p>
      <div class="result-box"><span>{{ tr('配音', 'Voiceover') }}</span><code>{{ audioUrl || tr('尚未生成', 'Not generated') }}</code></div>
    </article>

    <article class="panel replacement-panel">
      <div class="panel-head">
        <div><span class="step">04</span><h2>{{ tr('授权数字人口播', 'Authorized digital-human video') }}</h2></div>
        <span class="hint">MuseTalk v1.5</span>
      </div>
      <div class="replacement-state">
        <div class="replacement-icon">M</div>
        <div>
          <strong>{{ digitalHumanSetup?.ready ? tr('MuseTalk 数字人已就绪', 'MuseTalk is ready') : tr('MuseTalk 运行环境待安装', 'MuseTalk runtime required') }}</strong>
          <p v-if="digitalHumanSetup?.ready">{{ tr('只使用你本人、公司拥有或已取得相应数字人合成授权的头像视频。BossAI 不提供来源不明的默认人物素材。', 'Use only avatar video you own or are authorized to synthesize. BossAI does not provide unknown-rights default avatar media.') }}</p>
          <p v-else>{{ digitalHumanMissingLabel }}</p>
        </div>
      </div>

      <template v-if="digitalHumanSetup?.ready">
        <div class="grid two">
          <label><span>{{ tr('人物名称', 'Avatar name') }}</span><input v-model="avatarDisplayName" :placeholder="tr('例如：公司代言人', 'e.g. Company spokesperson')" /></label>
          <label>
            <span>{{ tr('上传授权头像视频', 'Upload authorized avatar video') }}</span>
            <input type="file" accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm,.mkv" @change="selectAvatarFile" />
          </label>
        </div>
        <label class="consent-row">
          <input v-model="avatarRightsConfirmed" type="checkbox" />
          <span>{{ tr('我确认对该人物形象和视频拥有与当前用途相匹配的合法使用及数字人合成授权。', 'I confirm I have lawful avatar/video rights matching the intended use.') }}</span>
        </label>
        <div class="button-row">
          <button class="secondary" :disabled="busy || avatarUploading || !avatarFile || !avatarRightsConfirmed" @click="uploadAuthorizedAvatar">
            {{ avatarUploading ? tr('正在保存…', 'Saving…') : tr('保存授权头像视频', 'Save authorized avatar') }}
          </button>
          <button class="secondary" @click="goTo('assets')">{{ tr('管理数字人', 'Manage avatars') }}</button>
        </div>
        <label>
          <span>{{ tr('本机已授权人物视频', 'Authorized local avatars') }}</span>
          <select v-model="avatarId">
            <option value="">{{ tr('请选择已授权人物视频', 'Select an authorized avatar') }}</option>
            <option v-for="item in avatars" :key="assetId(item)" :value="assetId(item)">{{ assetName(item, tr('授权人物视频', 'Authorized avatar')) }}</option>
          </select>
        </label>
        <button class="primary" :disabled="busy || !digitalHumanAllowed || !avatarId || !audioUrl || !avatarRightsConfirmed" @click="makeDigitalHuman">
          {{ busyAction === 'musetalk' ? tr('正在生成数字人口播…', 'Generating digital human…') : tr('生成数字人口播', 'Generate digital human') }}
        </button>
        <p v-if="executionAllowed && !digitalHumanAllowed" class="feature-lock">{{ tr('当前套餐未包含数字人口播。', 'Your current plan does not include digital-human generation.') }}</p>
        <div class="result-box"><span>{{ tr('数字人口播', 'Digital-human video') }}</span><code>{{ digitalHumanUrl || tr('尚未生成', 'Not generated') }}</code></div>
        <video v-if="digitalHumanUrl" class="result-video" controls :src="apiUrl(digitalHumanUrl)"></video>
      </template>
      <button v-else class="secondary" @click="goTo('settings')">{{ tr('前往设置安装 MuseTalk', 'Install MuseTalk in Settings') }}</button>
    </article>

    <article class="panel">
      <div class="panel-head">
        <div><span class="step">05</span><h2>{{ tr('视频剪辑与成片', 'Editing & final cut') }}</h2></div>
        <span :class="['runtime-state', finalVideoUrl ? 'ready' : 'missing']">{{ renderStatusLabel }}</span>
      </div>

      <p v-if="!composerReady" class="runtime-note">{{ tr('本机成片合成组件尚未就绪，剪辑选项不可用。可先直接生成未剪辑成片。', 'Local composition runtime is not ready, so editing options are unavailable. You can still produce an unedited final video.') }}</p>

      <VideoEditPanel />

      <div class="grid two">
        <label>
          <span>{{ tr('项目名称', 'Project name') }}</span>
          <input v-model.trim="projectName" maxlength="120" :placeholder="tr('例如：8月30日产品口播', 'e.g. Aug 30 product video')" />
        </label>
        <label>
          <span>{{ tr('成片来源', 'Video source') }}</span>
          <input :value="digitalHumanUrl ? tr('BossAI 数字人口播', 'BossAI digital human') : tr('请先完成数字人口播', 'Generate digital-human video first')" disabled />
        </label>
      </div>
      <div class="button-row">
        <button class="primary" :disabled="busy || !digitalHumanUrl" @click="renderFinalVideo">
          {{ busyAction === 'render' ? tr('正在生成成片…', 'Rendering…') : hasEdits ? tr('合成最终成片', 'Compose final video') : tr('生成成片（无剪辑）', 'Create final video (no edits)') }}
        </button>
        <button class="secondary" :disabled="exportBusy || !finalVideoUrl || !desktopExportAvailable" @click="exportFinalVideo">
          {{ exportBusy ? tr('正在导出…', 'Exporting…') : tr('导出 MP4', 'Export MP4') }}
        </button>
      </div>
      <div v-if="busyAction === 'render'" class="progress"><span :style="{ width: `${renderProgress}%` }"></span></div>
      <p v-if="renderSummary" class="render-summary">
        {{ tr('本次合成：', 'This render: ') }}
        <span :class="renderSummary.subtitleBurned ? 'on' : 'off'">{{ tr('字幕', 'Subtitles') }}{{ renderSummary.subtitleBurned ? ` · ${renderSummary.subtitleSegments}` : '' }}</span>
        <span :class="renderSummary.titleBurned ? 'on' : 'off'">{{ tr('通栏标题', 'Banner title') }}</span>
        <span :class="renderSummary.bgmMixed ? 'on' : 'off'">{{ tr('背景音乐', 'Music') }}</span>
      </p>
      <p v-if="!desktopExportAvailable" class="runtime-note">{{ tr('文件导出仅在 BossAI Video Agent 桌面应用中启用；浏览器预览不会获得本机任意文件写入权限。', 'File export is enabled only in the BossAI Video Agent desktop app; browser preview has no arbitrary local file-write permission.') }}</p>
      <div class="result-box final"><span>{{ tr('最终成片', 'Final video') }}</span><code>{{ finalVideoUrl || tr('尚未生成', 'Not generated') }}</code></div>
      <video v-if="finalVideoUrl" class="result-video" controls :src="apiUrl(finalVideoUrl)"></video>
    </article>

    <article class="panel">
      <div class="panel-head">
        <div><span class="step">06</span><h2>{{ tr('发布平台', 'Publishing') }}</h2></div>
        <span class="hint">{{ tr('自动发布继续 fail-closed', 'Automated publishing remains fail-closed') }}</span>
      </div>
      <div class="policy-card">
        <strong>{{ publishStatus?.automatedPublishAllowed ? tr('自动发布已连接', 'Automated publishing connected') : tr('自动发布尚未开放', 'Automated publishing not enabled') }}</strong>
        <p>{{ publishStatus?.reason || tr('等待读取 BossAI 发布治理状态。', 'Waiting for BossAI publishing-governance status.') }}</p>
      </div>
      <div class="grid two">
        <label>
          <span>{{ tr('目标平台', 'Target platform') }}</span>
          <select v-model="form.platform">
            <option v-for="[value, zh, en] in PLATFORMS" :key="value" :value="value">{{ tr(zh, en) }}</option>
          </select>
        </label>
        <label>
          <span>{{ tr('当前发布模式', 'Publishing mode') }}</span>
          <input :value="publishStatus?.automatedPublishAllowed ? tr('BossAI 治理发布', 'BossAI governed publishing') : tr('本地导出 + 人工发布', 'Local export + manual publishing')" disabled />
        </label>
      </div>
      <div v-if="title" class="result-box"><span>{{ tr('待发布标题', 'Title') }}</span><code>{{ title }}</code></div>
      <div v-if="topics" class="result-box"><span>{{ tr('话题标签', 'Hashtags') }}</span><code>{{ topics }}</code></div>
      <div class="button-row">
        <button class="secondary" :disabled="busy || !finalVideoUrl" @click="preparePublish">{{ tr('检查发布条件', 'Check publishing conditions') }}</button>
      </div>
      <div v-if="publishPreparation" class="result-box final">
        <span>{{ tr('发布状态', 'Publishing status') }}</span>
        <code>{{ publishPreparation.status }} · {{ publishPreparation.reason }}</code>
      </div>
    </article>
  </section>
</template>

<script setup>
import { apiUrl } from '../api.js'
import { tr } from '../i18n.js'
import { assetId, assetName, avatars, voices } from '../stores/assets.js'
import {
  composerReady,
  desktopExportAvailable,
  digitalHumanAllowed,
  digitalHumanMissingLabel,
  digitalHumanSetup,
  entitlementReason,
  executionAllowed,
  publishStatus,
  rewriteAllowed,
  ttsAllowed,
} from '../stores/session.js'
import {
  PLATFORMS,
  VIDEO_TYPES,
  audioUrl,
  avatarDisplayName,
  avatarFile,
  avatarId,
  avatarRightsConfirmed,
  avatarUploading,
  digitalHumanUrl,
  exportBusy,
  exportFinalVideo,
  finalVideoUrl,
  form,
  hasEdits,
  makeDigitalHuman,
  makeTitle,
  makeVoice,
  preparePublish,
  projectName,
  publishPreparation,
  renderFinalVideo,
  renderProgress,
  renderStatusLabel,
  renderSummary,
  rewrite,
  selectAvatarFile,
  selectVoiceFile,
  title,
  titleLimit,
  topics,
  uploadAuthorizedAvatar,
  uploadAuthorizedVoice,
  voiceDisplayName,
  voiceFile,
  voiceRightsConfirmed,
  voiceUploading,
} from '../stores/studio.js'
import { busy, busyAction, goTo } from '../stores/ui.js'
import VideoEditPanel from './VideoEditPanel.vue'
</script>
