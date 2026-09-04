const { contextBridge, ipcRenderer } = require('electron')

let localControlToken = ''
try {
  localControlToken = String(ipcRenderer.sendSync('bossai:get-local-control-token') || '')
} catch {
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
  exportFinalVideo: (payload) => ipcRenderer.invoke('bossai:export-final-video', {
    fileUrl: String(payload?.fileUrl || ''),
    suggestedName: String(payload?.suggestedName || ''),
  }),
  exportCoverImage: (payload) => ipcRenderer.invoke('bossai:export-cover-image', {
    fileUrl: String(payload?.fileUrl || ''),
    suggestedName: String(payload?.suggestedName || ''),
  }),
  openLegalDocument: (documentId) => ipcRenderer.invoke('bossai:open-legal-document', String(documentId || '')),
}))
