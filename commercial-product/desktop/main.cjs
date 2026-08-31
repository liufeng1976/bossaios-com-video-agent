const { app, BrowserWindow, dialog, shell, ipcMain } = require('electron')
const { spawn } = require('child_process')
const crypto = require('crypto')
const fs = require('fs')
const http = require('http')
const path = require('path')

const PRODUCT_ID = 'bossai-video-agent'
const PRODUCT_NAME = 'BossAI Video Agent'
const API_HOST = '127.0.0.1'
const API_PORT = Number(process.env.BOSSAI_VIDEO_PORT || 8765)

let backendProcess = null
let backendOwned = false
let shutdownToken = ''
const localControlToken = crypto.randomBytes(32).toString('hex')
let quitting = false

function localStateRoot() {
  const local = String(process.env.LOCALAPPDATA || '').trim()
  return local ? path.join(local, 'BossAI', 'VideoAgent') : path.join(app.getPath('appData'), 'BossAI', 'VideoAgent')
}

function configureElectronDataRoot() {
  const root = path.join(localStateRoot(), 'desktop')
  fs.mkdirSync(root, { recursive: true })
  app.setPath('userData', root)
}

const RUNTIME_ENV_KEYS = new Set([
  'BOSSAI_QWEN_MODEL',
  'BOSSAI_QWEN_PYTHON',
  'BOSSAI_COSYVOICE_ROOT',
  'BOSSAI_COSYVOICE_MODEL_DIR',
  'BOSSAI_COSYVOICE_PYTHON',
  'BOSSAI_MUSETALK_ROOT',
  'BOSSAI_MUSETALK_PYTHON',
  'BOSSAI_FFMPEG_BIN',
])

function installedRuntimeEnvironment() {
  const runtimesRoot = path.join(localStateRoot(), 'runtimes')
  const merged = {}
  for (const component of ['qwen2.5-7b-instruct', 'cosyvoice2-0.5b', 'musetalk']) {
    const manifestPath = path.join(runtimesRoot, component, 'runtime.json')
    if (!fs.existsSync(manifestPath)) continue
    try {
      const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8').replace(/^\uFEFF/, ''))
      if (manifest?.schema !== 'bossai.video-agent-installed-runtime.v1' || manifest?.component !== component) continue
      const values = manifest?.env && typeof manifest.env === 'object' ? manifest.env : {}
      for (const [key, raw] of Object.entries(values)) {
        if (!RUNTIME_ENV_KEYS.has(key)) continue
        const value = String(raw || '').trim()
        if (value) merged[key] = value
      }
    } catch (error) {
      console.warn(`Ignoring invalid BossAI runtime manifest ${manifestPath}:`, error?.message || error)
    }
  }
  return merged
}

function resolveUiEntry() {
  const override = String(process.env.BOSSAI_VIDEO_UI_DIR || '').trim()
  if (override) return path.resolve(override, 'index.html')
  if (app.isPackaged) return path.join(process.resourcesPath, 'ui', 'index.html')
  return path.resolve(__dirname, '..', 'ui', 'dist', 'index.html')
}

function resolveBackendEngine() {
  const explicit = String(process.env.BOSSAI_VIDEO_ENGINE_EXE || '').trim()
  if (explicit) return path.resolve(explicit)
  if (app.isPackaged) {
    const packaged = path.join(process.resourcesPath, 'backend', 'BossAI Video Engine.exe')
    return fs.existsSync(packaged) ? packaged : ''
  }
  return ''
}

function resolveBackendEntry() {
  const override = String(process.env.BOSSAI_VIDEO_BACKEND_ENTRY || '').trim()
  if (override) return path.resolve(override)
  if (app.isPackaged) return path.join(process.resourcesPath, 'backend', 'server.py')
  return path.resolve(__dirname, '..', 'backend', 'server.py')
}

function resolveBackendPython() {
  const explicit = String(process.env.BOSSAI_VIDEO_BACKEND_PYTHON || '').trim()
  if (explicit) return path.resolve(explicit)
  if (app.isPackaged) {
    const packaged = path.join(process.resourcesPath, 'runtime', 'python', 'python.exe')
    return fs.existsSync(packaged) ? packaged : ''
  }
  return process.platform === 'win32' ? 'python.exe' : 'python3'
}

function httpJson(method, pathname, { headers = {}, timeoutMs = 2500 } = {}) {
  return new Promise((resolve, reject) => {
    const request = http.request({
      host: API_HOST,
      port: API_PORT,
      method,
      path: pathname,
      headers: { Accept: 'application/json', ...headers },
      timeout: timeoutMs,
    }, (response) => {
      let body = ''
      response.setEncoding('utf8')
      response.on('data', (chunk) => { body += chunk })
      response.on('end', () => {
        let payload = null
        try { payload = body ? JSON.parse(body) : null } catch {}
        resolve({ statusCode: response.statusCode || 0, payload })
      })
    })
    request.on('timeout', () => request.destroy(new Error('request timeout')))
    request.on('error', reject)
    request.end()
  })
}

function safeExportName(value) {
  const name = String(value || '').replace(/[<>:\"/\\|?*\x00-\x1f]+/g, '-').replace(/\s+/g, ' ').trim().replace(/[. ]+$/g, '')
  const stem = name.toLowerCase().endsWith('.mp4') ? name.slice(0, -4) : name
  return `${stem || 'BossAI-Video'}.mp4`
}

function downloadLocalFinalVideo(fileUrl, destination) {
  const route = String(fileUrl || '').trim()
  if (!/^\/api\/commercial\/video\/final\/[0-9a-f]{32}\/file$/i.test(route)) {
    return Promise.reject(new Error('Only BossAI final-video artifacts can be exported.'))
  }
  const target = path.resolve(destination)
  const partial = `${target}.part`
  return new Promise((resolve, reject) => {
    const output = fs.createWriteStream(partial, { flags: 'w' })
    const cleanup = (error) => {
      try { output.destroy() } catch {}
      try { fs.unlinkSync(partial) } catch {}
      reject(error)
    }
    const request = http.get({ host: API_HOST, port: API_PORT, path: route, timeout: 30_000 }, (response) => {
      if (response.statusCode !== 200) {
        response.resume()
        cleanup(new Error(`BossAI final-video export failed with HTTP ${response.statusCode || 0}.`))
        return
      }
      response.pipe(output)
      output.on('finish', () => {
        output.close(() => {
          try {
            fs.renameSync(partial, target)
            resolve(target)
          } catch (error) {
            cleanup(error)
          }
        })
      })
    })
    request.on('timeout', () => request.destroy(new Error('BossAI final-video export timed out.')))
    request.on('error', cleanup)
    output.on('error', cleanup)
  })
}

async function healthyBossAIBackend() {
  try {
    const response = await httpJson('GET', '/health', { timeoutMs: 1200 })
    return Boolean(
      response.statusCode === 200
      && response.payload?.success === true
      && response.payload?.data?.product === PRODUCT_ID,
    )
  } catch {
    return false
  }
}

async function waitForBackend(processRef) {
  const deadline = Date.now() + 45_000
  while (Date.now() < deadline) {
    if (processRef?.exitCode !== null) throw new Error(`local engine exited with code ${processRef.exitCode}`)
    if (await healthyBossAIBackend()) return
    await new Promise((resolve) => setTimeout(resolve, 450))
  }
  throw new Error(`local engine did not become ready on 127.0.0.1:${API_PORT}`)
}

async function startBackend() {
  if (await healthyBossAIBackend()) {
    backendOwned = false
    return { reused: true }
  }

  const engine = resolveBackendEngine()
  const entry = resolveBackendEntry()
  const python = resolveBackendPython()
  if (engine && !fs.existsSync(engine)) throw new Error(`BossAI Video Engine is missing: ${engine}`)
  if (!engine) {
    if (!fs.existsSync(entry)) throw new Error(`BossAI backend is missing: ${entry}`)
    if (!python) throw new Error('BossAI backend engine is not packaged and no development Python runtime is configured.')
    if (path.isAbsolute(python) && !fs.existsSync(python)) throw new Error(`BossAI Python runtime is missing: ${python}`)
  }

  const root = localStateRoot()
  const dataRoot = path.join(root, 'data')
  const logRoot = path.join(root, 'logs')
  fs.mkdirSync(dataRoot, { recursive: true })
  fs.mkdirSync(logRoot, { recursive: true })
  shutdownToken = crypto.randomBytes(32).toString('hex')

  const stdout = fs.openSync(path.join(logRoot, 'engine.stdout.log'), 'a')
  const stderr = fs.openSync(path.join(logRoot, 'engine.stderr.log'), 'a')
  const runtimeEnv = installedRuntimeEnvironment()
  const env = {
    ...process.env,
    ...runtimeEnv,
    BOSSAI_VIDEO_DATA_ROOT: dataRoot,
    BOSSAI_VIDEO_RUNTIME_ROOT: path.join(root, 'runtimes'),
    BOSSAI_VIDEO_RUNTIME_SUPPORT_ROOT: path.join(root, 'runtime-support'),
    BOSSAI_VIDEO_RESOURCES_ROOT: app.isPackaged ? process.resourcesPath : path.resolve(__dirname, '..'),
    BOSSAI_VIDEO_LOCAL_CONTROL_TOKEN: localControlToken,
    BOSSAI_VIDEO_HOST: API_HOST,
    BOSSAI_VIDEO_PORT: String(API_PORT),
    BOSSAI_VIDEO_SHUTDOWN_TOKEN: shutdownToken,
    PYTHONDONTWRITEBYTECODE: '1',
    PYTHONIOENCODING: 'utf-8',
  }

  const command = engine || python
  const args = engine ? [] : [entry]
  const cwd = engine ? path.dirname(engine) : path.dirname(entry)
  backendProcess = spawn(command, args, {
    cwd,
    env,
    windowsHide: true,
    stdio: ['ignore', stdout, stderr],
  })
  backendOwned = true
  await waitForBackend(backendProcess)
  return { reused: false, pid: backendProcess.pid, mode: engine ? 'engine-exe' : 'python-dev' }
}

async function stopBackend() {
  if (!backendOwned || !backendProcess) return
  const processRef = backendProcess
  try {
    if (processRef.exitCode === null && shutdownToken) {
      await httpJson('POST', '/__bossai__/shutdown', {
        headers: { 'x-bossai-shutdown-token': shutdownToken },
        timeoutMs: 2500,
      })
    }
  } catch {}

  const deadline = Date.now() + 7000
  while (processRef.exitCode === null && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 150))
  }
  if (processRef.exitCode === null) processRef.kill()
  backendProcess = null
  backendOwned = false
  shutdownToken = ''
}

const LEGAL_DOCUMENTS = Object.freeze({
  terms: 'CUSTOMER_TERMS.md',
  privacy: 'PRIVACY_NOTICE.md',
  voiceAvatar: 'VOICE_AVATAR_AUTHORIZATION.md',
  support: 'SUPPORT_AND_INSTALLATION.md',
  notices: 'third-party-notices.json',
})

function resolveLegalDocument(documentId) {
  const fileName = LEGAL_DOCUMENTS[String(documentId || '')]
  if (!fileName) return ''
  if (documentId === 'notices') {
    return app.isPackaged
      ? path.join(process.resourcesPath, 'legal', fileName)
      : path.resolve(__dirname, '..', 'customer-third-party-notices.json')
  }
  return app.isPackaged
    ? path.join(process.resourcesPath, 'legal', 'release', fileName)
    : path.resolve(__dirname, '..', 'legal', 'release', fileName)
}

function legalStatus() {
  const documents = {}
  for (const documentId of Object.keys(LEGAL_DOCUMENTS)) {
    const filePath = resolveLegalDocument(documentId)
    documents[documentId] = Boolean(filePath && fs.existsSync(filePath))
  }
  return {
    productId: PRODUCT_ID,
    productName: PRODUCT_NAME,
    approvedReleaseBundlePresent: Boolean(documents.terms && documents.privacy && documents.voiceAvatar && documents.support),
    documents,
  }
}

ipcMain.on('bossai:preload-diagnostic', (_event, message) => {
  console.log('BOSSAI_PRELOAD_DIAGNOSTIC', String(message || ''))
})
ipcMain.on('bossai:get-local-control-token', (event) => {
  event.returnValue = localControlToken
})
ipcMain.handle('bossai:legal-status', () => legalStatus())
ipcMain.handle('bossai:export-final-video', async (_event, payload = {}) => {
  const fileUrl = String(payload?.fileUrl || '').trim()
  const suggestedName = safeExportName(payload?.suggestedName)
  if (!/^\/api\/commercial\/video\/final\/[0-9a-f]{32}\/file$/i.test(fileUrl)) {
    return { exported: false, canceled: false, reason: 'invalid-final-video-artifact' }
  }
  const result = await dialog.showSaveDialog({
    title: '导出 BossAI 最终成片',
    defaultPath: path.join(app.getPath('videos'), suggestedName),
    buttonLabel: '导出 MP4',
    filters: [{ name: 'MP4 Video', extensions: ['mp4'] }],
  })
  if (result.canceled || !result.filePath) return { exported: false, canceled: true }
  try {
    const filePath = await downloadLocalFinalVideo(fileUrl, result.filePath)
    return { exported: true, canceled: false, filePath }
  } catch (error) {
    return { exported: false, canceled: false, reason: error?.message || String(error) }
  }
})
ipcMain.handle('bossai:open-legal-document', async (_event, documentId) => {
  const filePath = resolveLegalDocument(documentId)
  if (!filePath || !fs.existsSync(filePath)) {
    return { opened: false, reason: 'document-not-available' }
  }
  const error = await shell.openPath(filePath)
  return { opened: !error, reason: error || '' }
})

function resolvePreloadPath() {
  if (app.isPackaged) return path.join(process.resourcesPath, 'desktop', 'preload.js')
  return path.resolve(__dirname, 'preload.js')
}

function createWindow(startupError = '') {
  const uiEntry = resolveUiEntry()
  const preloadPath = resolvePreloadPath()
  if (!fs.existsSync(uiEntry)) {
    dialog.showErrorBox(PRODUCT_NAME, `BossAI UI build is missing:\n${uiEntry}`)
    app.quit()
    return
  }

  const win = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1100,
    minHeight: 720,
    show: false,
    backgroundColor: '#f5f5f7',
    title: PRODUCT_NAME,
    autoHideMenuBar: true,
    webPreferences: {
      preload: preloadPath,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    },
  })

  win.webContents.on('preload-error', (_event, failedPreloadPath, error) => {
    console.error('BOSSAI_PRELOAD_ERROR', failedPreloadPath, error?.stack || error?.message || String(error))
  })
  if (process.env.BOSSAI_VIDEO_DIAGNOSTICS === '1') {
    console.log('BOSSAI_PRELOAD_PATH', preloadPath, fs.existsSync(preloadPath))
    console.log('BOSSAI_WEB_PREFERENCES', JSON.stringify(win.webContents.getLastWebPreferences()))
  }
  win.webContents.once('did-finish-load', async () => {
    try {
      const state = await win.webContents.executeJavaScript(`(() => {
        const bridge = globalThis.bossaiDesktop
        return {
          type: typeof bridge,
          keys: bridge && typeof bridge === 'object' ? Object.keys(bridge).sort() : [],
        }
      })()`)
      if (state?.type !== 'object') {
        console.error('BOSSAI_PRELOAD_BRIDGE_MISSING', JSON.stringify(state || {}))
      }
    } catch (error) {
      console.error('BOSSAI_PRELOAD_BRIDGE_CHECK_FAILED', error?.stack || error?.message || String(error))
    }
  })

  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https:\/\//i.test(url)) shell.openExternal(url)
    return { action: 'deny' }
  })
  win.webContents.on('will-navigate', (event, url) => {
    if (url === win.webContents.getURL()) return
    if (/^https:\/\//i.test(url)) shell.openExternal(url)
    event.preventDefault()
  })
  win.once('ready-to-show', () => {
    win.show()
    if (startupError) dialog.showErrorBox(`${PRODUCT_NAME} 本地引擎`, startupError)
  })
  win.loadFile(uiEntry).catch((error) => {
    dialog.showErrorBox(PRODUCT_NAME, `BossAI UI 加载失败：\n${error.message}`)
  })
}

app.setName(PRODUCT_NAME)
process.env.BOSSAI_VIDEO_LOCAL_CONTROL_TOKEN = localControlToken
configureElectronDataRoot()

app.whenReady().then(async () => {
  let startupError = ''
  try {
    await startBackend()
  } catch (error) {
    startupError = error?.message || String(error)
  }
  createWindow(startupError)
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow(startupError)
  })
})

app.on('before-quit', (event) => {
  if (quitting || !backendOwned) return
  event.preventDefault()
  quitting = true
  stopBackend().finally(() => app.quit())
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
