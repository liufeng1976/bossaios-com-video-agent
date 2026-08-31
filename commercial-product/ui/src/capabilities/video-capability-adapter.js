import {
  finalizeCommercialVideo,
  generateTts,
  getPublishStatus,
  prepareCommercialPublish,
  renderCommercialDigitalHuman,
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

  async renderVideo(payload) {
    return finalizeCommercialVideo(payload)
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
