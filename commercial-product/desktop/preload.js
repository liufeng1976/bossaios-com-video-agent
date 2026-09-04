try {
  const { contextBridge, ipcRenderer } = require('electron')
  ipcRenderer.send('bossai:preload-diagnostic', 'electron-module-ready')

  let localControlToken = ''
  try {
    localControlToken = String(ipcRenderer.sendSync('bossai:get-local-control-token') || '')
  } catch (error) {
    ipcRenderer.send('bossai:preload-diagnostic', `local-control-token-error:${error?.message || String(error)}`)
    localControlToken = ''
  }

  contextBridge.exposeInMainWorld('bossaiDesktop', Object.freeze({
    productId: 'bossai-video-agent',
    productName: 'BossAI Video Agent',
    version: '0.1.0',
    platform: 'win32',
    localControlToken,
    legalStatus: () => ipcRenderer.invoke('bossai:legal-status'),
    openUpgrade: () => ipcRenderer.invoke('bossai:open-upgrade'),
    quitApp: () => ipcRenderer.invoke('bossai:quit-app'),
    exportFinalVideo: (fileUrl, suggestedName) => ipcRenderer.invoke('bossai:export-final-video', {
      fileUrl: String(fileUrl || ''),
      suggestedName: String(suggestedName || ''),
    }),
    exportCoverImage: (fileUrl, suggestedName) => ipcRenderer.invoke('bossai:export-cover-image', {
      fileUrl: String(fileUrl || ''),
      suggestedName: String(suggestedName || ''),
    }),
    openPublishBundle: (directory) => ipcRenderer.invoke('bossai:open-publish-bundle', String(directory || '')),
    openPlatformUpload: (platform) => ipcRenderer.invoke('bossai:open-platform-upload', String(platform || '')),
    openLegalDocument: (documentId) => ipcRenderer.invoke('bossai:open-legal-document', String(documentId || '')),
  }))

  ipcRenderer.send('bossai:preload-diagnostic', 'context-bridge-exposed')
} catch (error) {
  console.error('BOSSAI_PRELOAD_FATAL', error?.stack || error?.message || String(error))
}
