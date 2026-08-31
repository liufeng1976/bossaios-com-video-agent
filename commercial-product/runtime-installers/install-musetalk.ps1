[CmdletBinding()]
param(
  [string]$TargetDir = "",
  [Parameter(Mandatory = $true)][string]$PythonExe,
  [Parameter(Mandatory = $true)][string]$FfmpegExe,
  [switch]$AcceptLicense
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Set-StrictMode -Version Latest

if (-not $AcceptLicense) {
  throw 'MuseTalk and all dependency license notices must be reviewed and accepted before installation.'
}

$installerRoot = $PSScriptRoot
$lockPath = Join-Path $installerRoot 'runtime-source-lock.json'
$constraintsPath = Join-Path $installerRoot 'musetalk-constraints.txt'
if (-not (Test-Path -LiteralPath $lockPath)) { throw "Runtime source lock is missing: $lockPath" }
if (-not (Test-Path -LiteralPath $constraintsPath)) { throw "Pinned MuseTalk constraints are missing: $constraintsPath" }

$lock = Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 | ConvertFrom-Json
$muse = $lock.components.musetalk
if (-not $muse) { throw 'MuseTalk source lock is missing.' }

if (-not $TargetDir) {
  if (-not $env:LOCALAPPDATA) { throw 'LOCALAPPDATA is unavailable; pass -TargetDir explicitly.' }
  $TargetDir = Join-Path $env:LOCALAPPDATA 'BossAI\VideoAgent\runtimes\musetalk'
}
$TargetDir = [System.IO.Path]::GetFullPath($TargetDir)
$PythonExe = [System.IO.Path]::GetFullPath($PythonExe)
$FfmpegExe = [System.IO.Path]::GetFullPath($FfmpegExe)
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) { throw "Python 3.10 executable is missing: $PythonExe" }
$existingManifest = Join-Path $TargetDir 'runtime.json'
if (Test-Path -LiteralPath $existingManifest -PathType Leaf) {
  throw "MuseTalk runtime is already installed: $TargetDir"
}
$InstallDir = "$TargetDir.installing-$([guid]::NewGuid().ToString('N'))"
if (-not (Test-Path -LiteralPath $FfmpegExe -PathType Leaf)) { throw "FFmpeg executable is missing: $FfmpegExe" }

$pythonVersion = (& $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" | Select-Object -Last 1).Trim()
if ($LASTEXITCODE -ne 0 -or $pythonVersion -ne '3.10') {
  throw "MuseTalk installer requires Python 3.10. Current interpreter reports: $pythonVersion"
}

function Step([string]$Message) {
  Write-Output ("BOSSAI_STEP " + $Message)
}

function Run([string]$Command, [string[]]$Arguments, [string]$WorkingDirectory = '') {
  Write-Output ("BOSSAI_RUN " + $Command + " " + ($Arguments -join ' '))
  $previous = (Get-Location).Path
  try {
    if ($WorkingDirectory) { Set-Location -LiteralPath $WorkingDirectory }
    & $Command @Arguments
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) { $exitCode = 0 }
    if ($exitCode -ne 0) { throw "Command failed with exit code $exitCode`: $Command" }
  } finally {
    Set-Location -LiteralPath $previous
  }
}

function VerifyHash([string]$FilePath, [string]$Expected) {
  if (-not (Test-Path -LiteralPath $FilePath -PathType Leaf)) { throw "Pinned runtime file is missing: $FilePath" }
  $actual = (Get-FileHash -LiteralPath $FilePath -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -ne $Expected.ToLowerInvariant()) { throw "Pinned runtime hash mismatch: $FilePath" }
}

function Commit-Install([string]$StagingDir, [string]$FinalDir) {
  $parent = Split-Path -Parent $FinalDir
  if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
  $quarantine = ''
  if (Test-Path -LiteralPath $FinalDir) {
    if (Test-Path -LiteralPath (Join-Path $FinalDir 'runtime.json') -PathType Leaf) {
      throw "Refusing to replace an installed MuseTalk runtime: $FinalDir"
    }
    $quarantine = "$FinalDir.incomplete-$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())"
    Move-Item -LiteralPath $FinalDir -Destination $quarantine
  }
  try {
    Move-Item -LiteralPath $StagingDir -Destination $FinalDir
  } catch {
    if ($quarantine -and -not (Test-Path -LiteralPath $FinalDir) -and (Test-Path -LiteralPath $quarantine)) {
      Move-Item -LiteralPath $quarantine -Destination $FinalDir
    }
    throw
  }
  if ($quarantine) { Remove-Item -LiteralPath $quarantine -Recurse -Force -ErrorAction SilentlyContinue }
}

New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
try {
$repoDir = Join-Path $InstallDir 'MuseTalk'
$venvDir = Join-Path $InstallDir 'venv'
$venvPython = Join-Path $venvDir 'Scripts\python.exe'
$venvHf = Join-Path $venvDir 'Scripts\hf.exe'
$licensesDir = Join-Path $InstallDir 'licenses'

Step 'Fetch pinned official MuseTalk source'
if (-not (Test-Path -LiteralPath (Join-Path $repoDir '.git'))) {
  Run 'git.exe' @('clone', '--filter=blob:none', '--no-checkout', [string]$muse.sourceRepository, $repoDir)
} else {
  $dirty = & git.exe -C $repoDir status --porcelain
  if ($LASTEXITCODE -ne 0) { throw 'Unable to inspect the existing MuseTalk repository.' }
  if ($dirty) { throw 'Existing MuseTalk repository contains local modifications; refusing to overwrite it.' }
}
Run 'git.exe' @('fetch', '--depth', '1', 'origin', [string]$muse.sourceRevision) $repoDir
Run 'git.exe' @('checkout', '--detach', [string]$muse.sourceRevision) $repoDir
$installedCommit = (& git.exe -C $repoDir rev-parse HEAD).Trim()
if ($installedCommit -ne [string]$muse.sourceRevision) { throw 'MuseTalk source revision verification failed.' }

Step 'Create isolated Python 3.10 environment'
if (-not (Test-Path -LiteralPath $venvPython)) { Run $PythonExe @('-m', 'venv', $venvDir) }
Run $venvPython @('-m', 'pip', 'install', 'pip==25.1.1', 'setuptools==80.9.0', 'wheel==0.45.1')
Run $venvPython @('-m', 'pip', 'install', 'torch==2.0.1', 'torchvision==0.15.2', 'torchaudio==2.0.2', '--index-url', 'https://download.pytorch.org/whl/cu118')
Run $venvPython @('-m', 'pip', 'install', '--constraint', $constraintsPath, '-r', (Join-Path $repoDir 'requirements.txt'))
Run $venvPython @('-m', 'pip', 'install', '--constraint', $constraintsPath, 'openmim==0.3.9', 'huggingface_hub==0.30.2', 'hf_xet==1.1.7')
$mimExe = Join-Path $venvDir 'Scripts\mim.exe'
Run $mimExe @('install', 'mmengine')
Run $mimExe @('install', 'mmcv==2.0.1')
Run $mimExe @('install', 'mmdet==3.1.0')
Run $mimExe @('install', 'mmpose==1.1.0')

if (-not (Test-Path -LiteralPath $venvHf)) { throw "Hugging Face CLI was not installed: $venvHf" }
$modelsDir = Join-Path $repoDir 'models'
New-Item -ItemType Directory -Path $modelsDir -Force | Out-Null

Step 'Download pinned official MuseTalk model artifacts'
Run $venvHf @('download', 'TMElyralab/MuseTalk', '--revision', [string]$muse.modelRevision, '--local-dir', $modelsDir)
$deps = $muse.dependencyModelRevisions
Run $venvHf @('download', 'stabilityai/sd-vae-ft-mse', '--revision', [string]$deps.'stabilityai/sd-vae-ft-mse', '--local-dir', (Join-Path $modelsDir 'sd-vae'), '--include', 'config.json', 'diffusion_pytorch_model.bin')
Run $venvHf @('download', 'openai/whisper-tiny', '--revision', [string]$deps.'openai/whisper-tiny', '--local-dir', (Join-Path $modelsDir 'whisper'), '--include', 'config.json', 'pytorch_model.bin', 'preprocessor_config.json')
Run $venvHf @('download', 'yzd-v/DWPose', '--revision', [string]$deps.'yzd-v/DWPose', '--local-dir', (Join-Path $modelsDir 'dwpose'), '--include', 'dw-ll_ucoco_384.pth')
Run $venvHf @('download', 'ByteDance/LatentSync', '--revision', [string]$deps.'ByteDance/LatentSync', '--local-dir', (Join-Path $modelsDir 'syncnet'), '--include', 'latentsync_syncnet.pt')
Run $venvHf @('download', 'ManyOtherFunctions/face-parse-bisent', '--revision', [string]$deps.'ManyOtherFunctions/face-parse-bisent', '--local-dir', (Join-Path $modelsDir 'face-parse-bisent'), '--include', '79999_iter.pth', 'resnet18-5c106cde.pth')

Step 'Verify pinned model hashes'
foreach ($property in $muse.verifiedHashes.PSObject.Properties) {
  VerifyHash (Join-Path $repoDir ([string]$property.Name).Replace('/', '\')) ([string]$property.Value)
}

Step 'Verify CUDA runtime'
Run $venvPython @('-c', "import torch; assert torch.cuda.is_available(), 'CUDA unavailable'; print(torch.cuda.get_device_name(0))")

Step 'Persist provenance and runtime manifest'
New-Item -ItemType Directory -Path $licensesDir -Force | Out-Null
$sourceLicense = Join-Path $repoDir 'LICENSE'
if (Test-Path -LiteralPath $sourceLicense) { Copy-Item -LiteralPath $sourceLicense -Destination (Join-Path $licensesDir 'MuseTalk-LICENSE.txt') -Force }
$captureNotices = Join-Path (Split-Path -Parent $PSScriptRoot) 'legal\capture-python-runtime-notices.py'
if (-not (Test-Path -LiteralPath $captureNotices -PathType Leaf)) { throw "BossAI runtime notice capture tool is missing: $captureNotices" }
Run $venvPython @($captureNotices,'--component','musetalk','--out',$licensesDir)

$runtimeManifest = [ordered]@{
  schema = 'bossai.video-agent-installed-runtime.v1'
  component = 'musetalk'
  installedAt = [DateTimeOffset]::UtcNow.ToString('o')
  source = [ordered]@{
    repository = [string]$muse.sourceRepository
    revision = [string]$muse.sourceRevision
    modelRepository = [string]$muse.modelRepository
    modelRevision = [string]$muse.modelRevision
  }
  licenseEvidence = 'licenses/python-dependency-notices.json'
  env = [ordered]@{
    BOSSAI_MUSETALK_ROOT = (Join-Path $TargetDir 'MuseTalk')
    BOSSAI_MUSETALK_PYTHON = (Join-Path $TargetDir 'venv\Scripts\python.exe')
    BOSSAI_FFMPEG_BIN = $FfmpegExe
  }
  rights = [ordered]@{
    avatar = 'customer-authorized-or-bossai-owned-only'
    audio = 'customer-authorized-or-bossai-owned-only'
    upstreamTestDataMayShip = $false
  }
}
$runtimeManifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $InstallDir 'runtime.json') -Encoding UTF8
Commit-Install $InstallDir $TargetDir

Write-Output 'BOSSAI_DONE MuseTalk runtime installed from pinned official sources.'
} catch {
  if (Test-Path -LiteralPath $InstallDir) { Remove-Item -LiteralPath $InstallDir -Recurse -Force -ErrorAction SilentlyContinue }
  throw
}
