<template>
  <section class="assets-layout">
    <article class="hero-card">
      <p class="kicker">{{ tr('本机素材库', 'Local asset library') }}</p>
      <h2>{{ tr('管理你已授权的音色和人物视频。', 'Manage the voices and avatar clips you are authorized to use.') }}</h2>
      <p>{{ tr('BossAI 不提供任何默认音色或人物素材。这里的每一项都由你自己上传，文件保存在本机 BossAI 数据目录，删除后不可恢复。', 'BossAI provides no default voices or avatar media. Everything here was uploaded by you, stored in the local BossAI data directory, and deletion is permanent.') }}</p>
      <div class="hero-actions">
        <button class="secondary" :disabled="assetsBusy" @click="refreshAssets">{{ tr('刷新素材库', 'Refresh library') }}</button>
        <button class="secondary" @click="goTo('studio')">{{ tr('去制作视频', 'Go to studio') }}</button>
      </div>
    </article>

    <div class="assets-tabs">
      <button :class="{ active: tab === 'voice' }" @click="tab = 'voice'">
        {{ tr('音色管理', 'Voices') }} <span class="count">{{ voiceCount }}</span>
      </button>
      <button :class="{ active: tab === 'avatar' }" @click="tab = 'avatar'">
        {{ tr('数字人管理', 'Avatars') }} <span class="count">{{ avatarCount }}</span>
      </button>
      <button :class="{ active: tab === 'media' }" @click="tab = 'media'">
        {{ tr('素材库', 'Media library') }} <span class="count">{{ mediaCount }}</span>
      </button>
    </div>

    <article v-if="tab === 'voice'" class="account-card">
      <div class="panel-head">
        <div><h2>{{ tr('已授权音色', 'Authorized voices') }}</h2></div>
        <span class="hint">{{ tr('可试听、重命名、删除', 'Audition, rename or delete') }}</span>
      </div>

      <p v-if="!voices.length" class="account-help">{{ tr('还没有任何授权音色。请在「AI 口播视频」第 02 步上传你有权使用的参考声音。', 'No authorized voices yet. Upload a reference voice you are entitled to use in step 02 of the studio.') }}</p>

      <div v-else class="asset-list">
        <div v-for="item in voices" :key="assetId(item)" class="asset-row">
          <div class="asset-identity">
            <template v-if="isEditing('voice', item)">
              <input
                v-model="renameDrafts[draftKey('voice', assetId(item))]"
                maxlength="100"
                @keyup.enter="commitVoiceRename(assetId(item))"
                @keyup.escape="cancelRename('voice', assetId(item))"
              />
            </template>
            <template v-else>
              <strong>{{ assetName(item, tr('授权声音', 'Authorized voice')) }}</strong>
              <span class="mono">{{ assetId(item) }}</span>
            </template>
          </div>

          <audio class="asset-audio" controls preload="none" :src="voiceFileUrl(assetId(item))"></audio>

          <div class="asset-actions">
            <template v-if="isEditing('voice', item)">
              <button class="secondary" @click="commitVoiceRename(assetId(item))">{{ tr('保存', 'Save') }}</button>
              <button class="secondary" @click="cancelRename('voice', assetId(item))">{{ tr('取消', 'Cancel') }}</button>
            </template>
            <template v-else>
              <button class="secondary" @click="startRename('voice', item)">{{ tr('重命名', 'Rename') }}</button>
              <button class="secondary danger" @click="confirmRemove('voice', item)">{{ tr('删除', 'Delete') }}</button>
            </template>
          </div>
        </div>
      </div>
    </article>

    <article v-else-if="tab === 'avatar'" class="account-card">
      <div class="panel-head">
        <div><h2>{{ tr('已授权人物视频', 'Authorized avatar clips') }}</h2></div>
        <span class="hint">{{ tr('可预览、重命名、删除', 'Preview, rename or delete') }}</span>
      </div>

      <p v-if="!avatars.length" class="account-help">{{ tr('还没有任何授权人物视频。请在「AI 口播视频」第 03 步上传你本人、公司拥有或已获授权的头像视频。', 'No authorized avatar clips yet. Upload avatar video you own or are authorized to use in step 03 of the studio.') }}</p>

      <div v-else class="avatar-grid">
        <div v-for="item in avatars" :key="assetId(item)" class="avatar-card">
          <video class="avatar-thumb" controls preload="metadata" :src="avatarFileUrl(assetId(item))"></video>
          <div class="asset-identity">
            <template v-if="isEditing('avatar', item)">
              <input
                v-model="renameDrafts[draftKey('avatar', assetId(item))]"
                maxlength="100"
                @keyup.enter="commitAvatarRename(assetId(item))"
                @keyup.escape="cancelRename('avatar', assetId(item))"
              />
            </template>
            <template v-else>
              <strong>{{ assetName(item, tr('授权人物视频', 'Authorized avatar')) }}</strong>
              <span class="mono">{{ formatSize(item.sizeBytes) }}</span>
            </template>
          </div>
          <div class="asset-actions">
            <template v-if="isEditing('avatar', item)">
              <button class="secondary" @click="commitAvatarRename(assetId(item))">{{ tr('保存', 'Save') }}</button>
              <button class="secondary" @click="cancelRename('avatar', assetId(item))">{{ tr('取消', 'Cancel') }}</button>
            </template>
            <template v-else>
              <button class="secondary" @click="startRename('avatar', item)">{{ tr('重命名', 'Rename') }}</button>
              <button class="secondary danger" @click="confirmRemove('avatar', item)">{{ tr('删除', 'Delete') }}</button>
            </template>
          </div>
        </div>
      </div>
    </article>

    <article v-else class="account-card">
      <div class="panel-head">
        <div><h2>{{ tr('画中画素材', 'Picture-in-picture media') }}</h2></div>
        <span class="hint">{{ tr('图片与视频，用于画中画叠加', 'Images and clips used as video insets') }}</span>
      </div>

      <p v-if="!media.length" class="account-help">{{ tr('还没有任何素材。可在「AI 口播视频」第 05 步的画中画区域上传图片或视频；只上传你拥有或已获授权的素材。', 'No media yet. Upload images or clips from the picture-in-picture controls in step 05; use only media you own or are licensed to use.') }}</p>

      <div v-else class="avatar-grid">
        <div v-for="item in media" :key="assetId(item)" class="avatar-card">
          <img v-if="item.kind === 'image'" class="avatar-thumb media-thumb" :src="mediaFileUrl(assetId(item))" :alt="assetName(item, '')" />
          <video v-else class="avatar-thumb media-thumb" controls preload="metadata" :src="mediaFileUrl(assetId(item))"></video>
          <div class="asset-identity">
            <template v-if="isEditing('media', item)">
              <input
                v-model="renameDrafts[draftKey('media', assetId(item))]"
                maxlength="100"
                @keyup.enter="commitMediaRename(assetId(item))"
                @keyup.escape="cancelRename('media', assetId(item))"
              />
            </template>
            <template v-else>
              <strong>{{ assetName(item, tr('本机素材', 'Local media')) }}</strong>
              <span class="mono">{{ item.kind === 'image' ? tr('图片', 'Image') : tr('视频', 'Video') }} · {{ formatSize(item.sizeBytes) }}</span>
            </template>
          </div>
          <div class="asset-actions">
            <template v-if="isEditing('media', item)">
              <button class="secondary" @click="commitMediaRename(assetId(item))">{{ tr('保存', 'Save') }}</button>
              <button class="secondary" @click="cancelRename('media', assetId(item))">{{ tr('取消', 'Cancel') }}</button>
            </template>
            <template v-else>
              <button class="secondary" @click="startRename('media', item)">{{ tr('重命名', 'Rename') }}</button>
              <button class="secondary danger" @click="confirmRemove('media', item)">{{ tr('删除', 'Delete') }}</button>
            </template>
          </div>
        </div>
      </div>
    </article>

    <div v-if="pendingRemoval" class="confirm-bar">
      <strong>{{ tr('确认删除？', 'Delete this asset?') }}</strong>
      <span>{{ pendingRemoval.name }} · {{ tr('删除后无法恢复。', 'This cannot be undone.') }}</span>
      <button class="secondary" @click="pendingRemoval = null">{{ tr('取消', 'Cancel') }}</button>
      <button class="primary" @click="performRemove">{{ tr('确认删除', 'Delete') }}</button>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'

import { tr } from '../i18n.js'
import {
  assetId,
  assetName,
  assetsBusy,
  avatarCount,
  avatarFileUrl,
  avatars,
  cancelRename,
  commitAvatarRename,
  commitMediaRename,
  commitVoiceRename,
  draftKey,
  media,
  mediaCount,
  mediaFileUrl,
  refreshAssets,
  removeAvatar,
  removeMedia,
  removeVoice,
  renameDrafts,
  startRename,
  voiceCount,
  voiceFileUrl,
  voices,
} from '../stores/assets.js'
import { reconcileSelections } from '../stores/studio.js'
import { goTo } from '../stores/ui.js'

const tab = ref('voice')
const pendingRemoval = ref(null)

function isEditing(kind, item) {
  return draftKey(kind, assetId(item)) in renameDrafts
}

function formatSize(bytes) {
  const value = Number(bytes) || 0
  if (value >= 1024 ** 3) return `${(value / 1024 ** 3).toFixed(1)} GB`
  if (value >= 1024 ** 2) return `${(value / 1024 ** 2).toFixed(1)} MB`
  return `${Math.max(1, Math.round(value / 1024))} KB`
}

function confirmRemove(kind, item) {
  pendingRemoval.value = { kind, id: assetId(item), name: assetName(item, '') }
}

async function performRemove() {
  const target = pendingRemoval.value
  pendingRemoval.value = null
  if (!target) return
  const remove = { voice: removeVoice, avatar: removeAvatar, media: removeMedia }[target.kind]
  await remove(target.id)
  reconcileSelections()
}

onMounted(refreshAssets)
</script>
