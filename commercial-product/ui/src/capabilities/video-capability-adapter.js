import {
  finalizeCommercialVideo,
  generateTts,
  getPublishStatus,
  getVideoAssets,
  prepareCommercialPublish,
  renderCommercialDigitalHuman,
  renderCommercialFinalVideo,
  rewriteScript,
} from '../api.js'

function unsupported(capability, reason) {
  const error = new Error(reason)
  error.code = 'BOSSAI_CAPABILITY_UNAVAILABLE'
  error.capability = capability
  throw error
}

export class BossAIVideoCapabilityAdapter {
  async rewrite(sourceText, options = {}) {
    return rewriteScript(sourceText, options)
  }

  async tts(payload, onProgress) {
    return generateTts(payload, onProgress)
  }

  async digitalHuman(payload, onProgress) {
    return renderCommercialDigitalHuman(payload, onProgress)
  }

  /** Lossless passthrough used when no edit is enabled. */
  async finalize(payload) {
    return finalizeCommercialVideo(payload)
  }

  /** Full composition: burned-in subtitles, banner title and mixed music. */
  async renderVideo(payload, onProgress) {
    return renderCommercialFinalVideo(payload, onProgress)
  }

  async editingAssets() {
    return getVideoAssets()
  }

  async cover(_payload) {
    return unsupported(
      'cover',
      'BossAI commercial cover generation is not enabled in the independent product runtime yet.',
    )
  }

  async publishStatus() {
    return getPublishStatus()
  }

  async publish(payload) {
    return prepareCommercialPublish(payload)
  }
}

export const videoCapabilities = Object.freeze(new BossAIVideoCapabilityAdapter())
