const { app, BrowserWindow, dialog, shell, ipcMain } = require('electron')
const { spawn } = require('child_process')
const crypto = require('crypto')
const fs = require('fs')
const http = require('http')
const path = require('path')

const PRODUCT_ID = 'bossai-video-agent'
const PRODUCT_NAME = 'BossAI Video Agent'
// The pricing page rather than the site root, because that is the page that
// actually lists plans. There is no Chinese pricing page yet, so zh users land
// here too; `lang` is carried so the site can route them once one exists.
const UPGRADE_URL = 'https://bossaios.com/en/pricing.html'

// Where in the app the customer asked to upgrade. An allowlist, because the
// renderer must never be able to steer this link: it decides only which of
// these labels is attached, never the destination.
const UPGRADE_SOURCES = new Set(['settings-plan', 'settings-account', 'quota-exhausted'])
const UPGRADE_LANGS = new Set(['zh-CN', 'en'])
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

function runtimeStorageConfig() {
  const configPath = path.join(localStateRoot(), 'runtime-storage.json')
  try {
    if (!fs.existsSync(configPath)) return {}
    const value = JSON.parse(fs.readFileSync(configPath, 'utf8').replace(/^\uFEFF/, ''))
    return value && typeof value === 'object' ? value : {}
  } catch (error) {
    console.warn(`Ignoring invalid BossAI runtime storage config ${configPath}:`, error?.message || error)
    return {}
  }
}

function runtimeRoot() {
  const explicit = String(process.env.BOSSAI_VIDEO_RUNTIME_ROOT || '').trim()
  if (explicit) return path.resolve(explicit)
  const configured = String(runtimeStorageConfig().runtimeRoot || '').trim()
  return configured ? path.resolve(configured) : path.join(localStateRoot(), 'runtimes')
}

function runtimeDownloadRoot() {
  const explicit = String(process.env.BOSSAI_VIDEO_DOWNLOAD_ROOT || '').trim()
  if (explicit) return path.resolve(explicit)
  const configured = String(runtimeStorageConfig().downloadRoot || '').trim()
  return configured ? path.resolve(configured) : path.join(localStateRoot(), 'downloads')
}

function configureElectronDataRoot() {
  const root = path.join(localStateRoot(), 'desktop')
  fs.mkdirSync(root, { recursive: true })
  app.setPath('userData', root)
}

const RUNTIME_ENV_KEYS = new Set([
  'BOSSAI_QWEN_MODEL',
  'BOSSAI_QWEN_SERVER',
  'BOSSAI_QWEN_GPU_LAYERS',
  'BOSSAI_COSYVOICE_ROOT',
  'BOSSAI_COSYVOICE_MODEL_DIR',
  'BOSSAI_COSYVOICE_PYTHON',
  'BOSSAI_MUSETALK_ROOT',
  'BOSSAI_MUSETALK_PYTHON',
  'BOSSAI_WHISPER_MODEL',
  'BOSSAI_WHISPER_PYTHON',
  'BOSSAI_WHISPER_DEVICE',
  'BOSSAI_FFMPEG_BIN',
])

function installedRuntimeEnvironment() {
  const runtimesRoot = runtimeRoot()
  const merged = {}
  for (const component of ['qwen2.5-7b-instruct', 'cosyvoice2-0.5b', 'musetalk', 'faster-whisper-large-v3']) {
    const manifestPath = path.join(runtimesRoot, component, 'runtime.json')
    if (!fs.existsSync(manifestPath)) continue
    try {
      const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8').replace(/^\uFEFF/, ''))
      if (!['bossai.video-agent-installed-runtime.v1', 'bossai.video-agent-installed-runtime.v2'].includes(manifest?.schema) || manifest?.component !== component) continue
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

function safeExportName(value, extension = '.mp4', fallback = 'BossAI-Video') {
  const name = String(value || '').replace(/[<>:\"/\\|?*\x00-\x1f]+/g, '-').replace(/\s+/g, ' ').trim().replace(/[. ]+$/g, '')
  const stem = name.toLowerCase().endsWith(extension) ? name.slice(0, -extension.length) : name
  return `${stem || fallback}${extension}`
}

const FINAL_VIDEO_ROUTE = /^\/api\/commercial\/video\/final\/[0-9a-f]{32}\/file$/i
const COVER_ROUTE = /^\/api\/commercial\/video\/cover\/[0-9a-f]{32}\/file$/i

function downloadLocalArtifact(fileUrl, destination, allowedRoute) {
  const route = String(fileUrl || '').trim()
  if (!allowedRoute.test(route)) {
    return Promise.reject(new Error('Only BossAI generated artifacts can be exported.'))
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
        cleanup(new Error(`BossAI export failed with HTTP ${response.statusCode || 0}.`))
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
    BOSSAI_VIDEO_RUNTIME_ROOT: runtimeRoot(),
    BOSSAI_VIDEO_DOWNLOAD_ROOT: runtimeDownloadRoot(),
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
  eula: 'EULA.md',
  sourceLicense: 'SOURCE-LICENSE.txt',
  historicalLicense: 'HISTORICAL-MIT-LICENSE.md',
  commercialLicense: 'COMMERCIAL-LICENSE.md',
  terms: 'TERMS.md',
  privacy: 'PRIVACY.md',
  voiceAvatar: 'VOICE_AVATAR_AUTHORIZATION.md',
  support: 'INSTALL.md',
  notices: 'third-party-notices.json',
})

function resolveLegalDocument(documentId) {
  const fileName = LEGAL_DOCUMENTS[String(documentId || '')]
  if (!fileName) return ''
  if (documentId === 'eula' || documentId === 'sourceLicense' || documentId === 'historicalLicense' || documentId === 'commercialLicense' || documentId === 'terms' || documentId === 'privacy' || documentId === 'support') {
    const sourceName = documentId === 'historicalLicense' ? 'LICENSE-HISTORICAL-MIT.md' : documentId === 'sourceLicense' ? 'LICENSE' : fileName
    return app.isPackaged
      ? path.join(process.resourcesPath, 'legal', fileName)
      : path.resolve(__dirname, '..', '..', sourceName)
  }
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
ipcMain.handle('bossai:quit-app', () => {
  app.quit()
  return { quitting: true }
})
// Carries enough context for the site to show the right plan and to attribute
// the visit, and nothing more: no installation ID, no account, no device or
// usage detail. Everything here is either a constant or one of the fixed
// labels above.
function buildUpgradeUrl(context) {
  const url = new URL(UPGRADE_URL)
  const source = UPGRADE_SOURCES.has(context?.source) ? context.source : 'unspecified'
  const lang = UPGRADE_LANGS.has(context?.lang) ? context.lang : 'en'
  url.searchParams.set('product', PRODUCT_ID)
  url.searchParams.set('version', app.getVersion())
  url.searchParams.set('lang', lang)
  url.searchParams.set('utm_source', 'video-agent-desktop')
  url.searchParams.set('utm_medium', 'app')
  url.searchParams.set('utm_campaign', 'upgrade')
  url.searchParams.set('utm_content', source)
  return url.toString()
}

ipcMain.handle('bossai:open-upgrade', async (_event, context) => {
  const url = buildUpgradeUrl(context)
  try {
    await shell.openExternal(url)
    return { opened: true, url }
  } catch (error) {
    return { opened: false, reason: error?.message || String(error) }
  }
})
ipcMain.handle('bossai:export-final-video', async (_event, payload = {}) => {
  const fileUrl = String(payload?.fileUrl || '').trim()
  const suggestedName = safeExportName(payload?.suggestedName)
  if (!FINAL_VIDEO_ROUTE.test(fileUrl)) {
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
    const filePath = await downloadLocalArtifact(fileUrl, result.filePath, FINAL_VIDEO_ROUTE)
    return { exported: true, canceled: false, filePath }
  } catch (error) {
    return { exported: false, canceled: false, reason: error?.message || String(error) }
  }
})
ipcMain.handle('bossai:export-cover-image', async (_event, payload = {}) => {
  const fileUrl = String(payload?.fileUrl || '').trim()
  const suggestedName = safeExportName(payload?.suggestedName, '.png', 'BossAI-Video-cover')
  if (!COVER_ROUTE.test(fileUrl)) {
    return { exported: false, canceled: false, reason: 'invalid-cover-artifact' }
  }
  const result = await dialog.showSaveDialog({
    title: '导出 BossAI 封面',
    defaultPath: path.join(app.getPath('pictures'), suggestedName),
    buttonLabel: '导出 PNG',
    filters: [{ name: 'PNG Image', extensions: ['png'] }],
  })
  if (result.canceled || !result.filePath) return { exported: false, canceled: true }
  try {
    const filePath = await downloadLocalArtifact(fileUrl, result.filePath, COVER_ROUTE)
    return { exported: true, canceled: false, filePath }
  } catch (error) {
    return { exported: false, canceled: false, reason: error?.message || String(error) }
  }
})
const PLATFORM_UPLOAD_PAGES = Object.freeze({
  douyin: 'https://creator.douyin.com/creator-micro/content/upload',
  channels: 'https://channels.weixin.qq.com/platform/post/create',
  xiaohongshu: 'https://creator.xiaohongshu.com/publish/publish',
  kuaishou: 'https://cp.kuaishou.com/article/publish/video',
})

// Opens a bundle folder produced by the backend. The path is confined to the
// product's own publish-bundles directory so the renderer cannot ask the shell
// to open an arbitrary location.
ipcMain.handle('bossai:open-publish-bundle', async (_event, directory) => {
  const requested = path.resolve(String(directory || ''))
  const root = path.resolve(path.join(localStateRoot(), 'publish-bundles'))
  const relative = path.relative(root, requested)
  if (relative.startsWith('..') || path.isAbsolute(relative)) {
    return { opened: false, reason: 'outside-publish-bundle-root' }
  }
  if (!fs.existsSync(requested)) return { opened: false, reason: 'bundle-not-found' }
  const error = await shell.openPath(requested)
  return { opened: !error, reason: error || '' }
})

// Opens the platform's own creator studio in the user's browser. No credentials
// are handled and nothing is automated: the customer uploads the bundle there.
ipcMain.handle('bossai:open-platform-upload', async (_event, platform) => {
  const url = PLATFORM_UPLOAD_PAGES[String(platform || '')]
  if (!url) return { opened: false, reason: 'unknown-platform' }
  try {
    await shell.openExternal(url)
    return { opened: true, url }
  } catch (error) {
    return { opened: false, reason: error?.message || String(error) }
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
