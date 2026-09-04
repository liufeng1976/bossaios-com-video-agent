<template>
  <div class="edit-grid">
    <section class="edit-block">
      <h3>{{ tr('字幕', 'Subtitles') }}</h3>
      <label class="consent-row">
        <input v-model="edit.subtitleEnabled" type="checkbox" :disabled="!composerReady" />
        <span>{{ tr('根据口播文案自动生成并烧录字幕', 'Generate and burn in captions from the script') }}</span>
      </label>
      <div class="grid two">
        <label>
          <span>{{ tr('字体', 'Font') }}</span>
          <select v-model="edit.subtitleFontFile" :disabled="subtitleLocked">
            <option value="">{{ tr('自动选择', 'Automatic') }}</option>
            <option v-for="font in fontLibrary" :key="font.fileName" :value="font.fileName">{{ font.displayName || font.fileName }}</option>
          </select>
        </label>
        <label>
          <span>{{ tr('位置', 'Position') }}</span>
          <select v-model="edit.subtitlePosition" :disabled="subtitleLocked">
            <option v-for="[value, zh, en] in CAPTION_POSITIONS" :key="value" :value="value">{{ tr(zh, en) }}</option>
          </select>
        </label>
        <label><span>{{ tr('字号', 'Size') }}</span><input v-model.number="edit.subtitleFontSize" type="number" min="24" max="120" :disabled="subtitleLocked" /></label>
        <label><span>{{ tr('描边宽度', 'Stroke width') }}</span><input v-model.number="edit.subtitleStrokeWidth" type="number" min="0" max="8" step="0.5" :disabled="subtitleLocked" /></label>
        <label><span>{{ tr('文字颜色', 'Text color') }}</span><input v-model="edit.subtitleColor" type="color" :disabled="subtitleLocked" /></label>
        <label><span>{{ tr('描边颜色', 'Stroke color') }}</span><input v-model="edit.subtitleStrokeColor" type="color" :disabled="subtitleLocked" /></label>
      </div>
      <p class="hint">{{ tr('字幕时间按配音时长与文案长度自动分配；本产品不含语音识别运行时。', 'Caption timing is distributed across the measured voiceover duration; the product ships no speech-recognition runtime.') }}</p>
    </section>

    <section class="edit-block">
      <h3>{{ tr('背景音乐', 'Background music') }}</h3>
      <label class="consent-row">
        <input v-model="edit.bgmEnabled" type="checkbox" :disabled="!composerReady || !bgmLibrary.length" />
        <span>{{ tr('混入背景音乐', 'Mix in background music') }}</span>
      </label>
      <label>
        <span>{{ tr('曲目', 'Track') }}</span>
        <select v-model="edit.bgmFile" :disabled="!edit.bgmEnabled || !composerReady">
          <option value="">{{ tr('无配乐', 'No music') }}</option>
          <option v-for="item in bgmLibrary" :key="item.fileName" :value="item.fileName">{{ item.displayName || item.fileName }}</option>
        </select>
      </label>
      <label><span>{{ tr('音乐音量', 'Music volume') }} {{ edit.bgmVolume }}%</span><input v-model.number="edit.bgmVolume" type="range" min="0" max="100" :disabled="!edit.bgmEnabled || !composerReady" /></label>
      <label><span>{{ tr('人声音量', 'Voice volume') }} {{ edit.voiceMixVolume }}%</span><input v-model.number="edit.voiceMixVolume" type="range" min="0" max="150" :disabled="!composerReady" /></label>

      <div class="policy-card">
        <strong>{{ tr('音乐权利确认', 'Music rights confirmation') }}</strong>
        <p>{{ tr('BossAI 不附带任何背景音乐。请只上传你拥有或已获授权的曲目；文件保存在本机素材目录。', 'BossAI ships no background music. Upload only tracks you own or are licensed to use; files stay in your local asset directory.') }}</p>
      </div>
      <div class="grid two">
        <label><span>{{ tr('上传音乐', 'Upload music') }}</span><input type="file" accept="audio/*,.mp3,.wav,.m4a,.aac,.flac,.ogg" @change="selectBgmFile" /></label>
        <label>
          <span>{{ tr('操作', 'Actions') }}</span>
          <div class="inline-field">
            <button class="secondary" :disabled="!bgmFile || bgmUploading" @click="uploadBackgroundMusic">
              {{ bgmUploading ? tr('上传中…', 'Uploading…') : tr('保存音乐', 'Save music') }}
            </button>
            <button class="secondary danger" :disabled="!edit.bgmFile" @click="removeBackgroundMusic(edit.bgmFile)">{{ tr('删除所选', 'Delete') }}</button>
          </div>
        </label>
      </div>
    </section>

    <section class="edit-block">
      <h3>{{ tr('画中画', 'Picture-in-picture') }}</h3>
      <label class="consent-row">
        <input v-model="edit.pipEnabled" type="checkbox" :disabled="!composerReady || !mediaLibrary.length" />
        <span>{{ tr('在画面上叠加图片或视频素材', 'Overlay an image or clip on the video') }}</span>
      </label>
      <label>
        <span>{{ tr('素材', 'Media') }}</span>
        <select v-model="edit.pipMediaId" :disabled="!edit.pipEnabled || !composerReady">
          <option value="">{{ tr('请选择素材', 'Select media') }}</option>
          <option v-for="item in mediaLibrary" :key="assetId(item)" :value="assetId(item)">
            {{ assetName(item, tr('本机素材', 'Local media')) }} · {{ item.kind === 'image' ? tr('图片', 'Image') : tr('视频', 'Video') }}
          </option>
        </select>
      </label>
      <div class="grid two">
        <label>
          <span>{{ tr('位置', 'Corner') }}</span>
          <select v-model="edit.pipCorner" :disabled="pipLocked">
            <option v-for="[value, zh, en] in PIP_CORNERS" :key="value" :value="value">{{ tr(zh, en) }}</option>
          </select>
        </label>
        <label><span>{{ tr('边距', 'Margin') }} {{ edit.pipMarginPercent }}%</span><input v-model.number="edit.pipMarginPercent" type="range" min="0" max="40" :disabled="pipLocked" /></label>
      </div>
      <label><span>{{ tr('画面占比', 'Size') }} {{ edit.pipScalePercent }}%</span><input v-model.number="edit.pipScalePercent" type="range" min="5" max="100" :disabled="pipLocked" /></label>
      <label><span>{{ tr('不透明度', 'Opacity') }} {{ edit.pipOpacity }}%</span><input v-model.number="edit.pipOpacity" type="range" min="10" max="100" :disabled="pipLocked" /></label>
      <div class="grid two">
        <label><span>{{ tr('开始秒', 'Start (s)') }}</span><input v-model.number="edit.pipStartSeconds" type="number" min="0" step="0.5" :disabled="pipLocked" /></label>
        <label><span>{{ tr('结束秒', 'End (s)') }}</span><input v-model.number="edit.pipEndSeconds" type="number" min="0" step="0.5" :disabled="pipLocked" :placeholder="tr('0 = 到片尾', '0 = to the end')" /></label>
      </div>
      <p class="hint">{{ tr('占比按成片画面计算，与素材原始分辨率无关。', 'Size is measured against the output frame, not the source asset resolution.') }}</p>
      <div class="grid two">
        <label><span>{{ tr('上传素材', 'Upload media') }}</span><input type="file" accept="image/*,video/*" @change="selectMediaFile" /></label>
        <label>
          <span>{{ tr('操作', 'Actions') }}</span>
          <div class="inline-field">
            <button class="secondary" :disabled="!mediaFile || mediaUploading" @click="uploadPictureInPictureMedia">
              {{ mediaUploading ? tr('上传中…', 'Uploading…') : tr('保存素材', 'Save media') }}
            </button>
            <button class="secondary" @click="goTo('assets')">{{ tr('管理素材', 'Manage') }}</button>
          </div>
        </label>
      </div>
    </section>

    <section class="edit-block">
      <h3>{{ tr('通栏标题', 'Banner title') }}</h3>
      <label class="consent-row">
        <input v-model="edit.videoTitleEnabled" type="checkbox" :disabled="!composerReady" />
        <span>{{ tr('在视频画面烧录标题', 'Burn a title into the frame') }}</span>
      </label>
      <label>
        <span>{{ tr('标题内容', 'Title text') }}</span>
        <input v-model="edit.videoTitleText" maxlength="200" :disabled="!edit.videoTitleEnabled || !composerReady" :placeholder="tr('例如：限时活动', 'e.g. Limited-time offer')" />
      </label>
      <div class="grid two">
        <label>
          <span>{{ tr('位置', 'Position') }}</span>
          <select v-model="edit.videoTitlePosition" :disabled="!edit.videoTitleEnabled || !composerReady">
            <option v-for="[value, zh, en] in CAPTION_POSITIONS" :key="value" :value="value">{{ tr(zh, en) }}</option>
          </select>
        </label>
        <label><span>{{ tr('字号', 'Size') }}</span><input v-model.number="edit.videoTitleFontSize" type="number" min="24" max="120" :disabled="!edit.videoTitleEnabled || !composerReady" /></label>
        <label><span>{{ tr('文字颜色', 'Text color') }}</span><input v-model="edit.videoTitleColor" type="color" :disabled="!edit.videoTitleEnabled || !composerReady" /></label>
        <label><span>{{ tr('描边颜色', 'Stroke color') }}</span><input v-model="edit.videoTitleStrokeColor" type="color" :disabled="!edit.videoTitleEnabled || !composerReady" /></label>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'

import { tr } from '../i18n.js'
import { assetId, assetName } from '../stores/assets.js'
import { composerReady } from '../stores/session.js'
import {
  CAPTION_POSITIONS,
  PIP_CORNERS,
  bgmFile,
  bgmLibrary,
  bgmUploading,
  edit,
  fontLibrary,
  mediaFile,
  mediaLibrary,
  mediaUploading,
  removeBackgroundMusic,
  selectBgmFile,
  selectMediaFile,
  uploadBackgroundMusic,
  uploadPictureInPictureMedia,
} from '../stores/studio.js'
import { goTo } from '../stores/ui.js'

const subtitleLocked = computed(() => !edit.subtitleEnabled || !composerReady.value)
const pipLocked = computed(() => !edit.pipEnabled || !composerReady.value)
</script>
