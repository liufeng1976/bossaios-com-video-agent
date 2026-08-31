[CmdletBinding()]
param(
  [string]$TargetDir = "",
  [Parameter(Mandatory = $true)][string]$PythonExe,
  [ValidateSet('cu118','cpu')][string]$TorchFlavor = 'cu118',
  [switch]$AcceptLicense
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Set-StrictMode -Version Latest

if (-not $AcceptLicense) { throw 'CosyVoice and model license notices must be reviewed and accepted before installation.' }
$lockPath = Join-Path $PSScriptRoot 'runtime-source-lock.json'
$lock = Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 | ConvertFrom-Json
$cosy = $lock.components.'cosyvoice2-0.5b'
if (-not $cosy) { throw 'CosyVoice2 source lock is missing.' }

if (-not $TargetDir) {
  if (-not $env:LOCALAPPDATA) { throw 'LOCALAPPDATA is unavailable; pass -TargetDir explicitly.' }
  $TargetDir = Join-Path $env:LOCALAPPDATA 'BossAI\VideoAgent\runtimes\cosyvoice2-0.5b'
}
$TargetDir = [System.IO.Path]::GetFullPath($TargetDir)
$PythonExe = [System.IO.Path]::GetFullPath($PythonExe)
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) { throw "Python 3.10 executable is missing: $PythonExe" }
$existingManifest = Join-Path $TargetDir 'runtime.json'
if (Test-Path -LiteralPath $existingManifest -PathType Leaf) {
  throw "CosyVoice2 runtime is already installed: $TargetDir"
}
$InstallDir = "$TargetDir.installing-$([guid]::NewGuid().ToString('N'))"
$pythonVersion = (& $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" | Select-Object -Last 1).Trim()
if ($LASTEXITCODE -ne 0 -or $pythonVersion -ne '3.10') { throw "CosyVoice2 runtime requires Python 3.10. Current: $pythonVersion" }

function Run([string]$Command, [string[]]$Arguments, [string]$WorkingDirectory = '') {
  Write-Output ("BOSSAI_RUN " + $Command + " " + ($Arguments -join ' '))
  $previous = (Get-Location).Path
  try {
    if ($WorkingDirectory) { Set-Location -LiteralPath $WorkingDirectory }
    & $Command @Arguments
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) { $exitCode = 0 }
    if ($exitCode -ne 0) { throw "Command failed with exit code $exitCode`: $Command" }
  } finally { Set-Location -LiteralPath $previous }
}

function Commit-Install([string]$StagingDir, [string]$FinalDir) {
  $parent = Split-Path -Parent $FinalDir
  if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
  $quarantine = ''
  if (Test-Path -LiteralPath $FinalDir) {
    if (Test-Path -LiteralPath (Join-Path $FinalDir 'runtime.json') -PathType Leaf) {
      throw "Refusing to replace an installed CosyVoice2 runtime: $FinalDir"
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
$repoDir = Join-Path $InstallDir 'CosyVoice'
$venvDir = Join-Path $InstallDir 'venv'
$venvPython = Join-Path $venvDir 'Scripts\python.exe'
$modelDir = Join-Path $InstallDir 'model\CosyVoice2-0.5B'
$licensesDir = Join-Path $InstallDir 'licenses'

if (-not (Test-Path -LiteralPath (Join-Path $repoDir '.git'))) {
  Run 'git.exe' @('clone','--filter=blob:none','--no-checkout',[string]$cosy.sourceRepository,$repoDir)
} else {
  $dirty = & git.exe -C $repoDir status --porcelain
  if ($LASTEXITCODE -ne 0) { throw 'Unable to inspect existing CosyVoice repository.' }
  if ($dirty) { throw 'Existing CosyVoice repository contains local modifications; refusing to overwrite it.' }
}
Run 'git.exe' @('fetch','--depth','1','origin',[string]$cosy.sourceRevision) $repoDir
Run 'git.exe' @('checkout','--detach',[string]$cosy.sourceRevision) $repoDir
Run 'git.exe' @('submodule','update','--init','--recursive') $repoDir
$installedCommit = (& git.exe -C $repoDir rev-parse HEAD).Trim()
if ($installedCommit -ne [string]$cosy.sourceRevision) { throw 'CosyVoice source revision verification failed.' }

if (-not (Test-Path -LiteralPath $venvPython)) { Run $PythonExe @('-m','venv',$venvDir) }
Run $venvPython @('-m','pip','install','pip==25.1.1','setuptools==80.9.0','wheel==0.45.1','huggingface_hub==0.30.2')
if ($TorchFlavor -eq 'cu118') {
  Run $venvPython @('-m','pip','install','torch==2.3.1','torchaudio==2.3.1','--index-url','https://download.pytorch.org/whl/cu118')
} else {
  Run $venvPython @('-m','pip','install','torch==2.3.1','torchaudio==2.3.1','--index-url','https://download.pytorch.org/whl/cpu')
}
Run $venvPython @('-m','pip','install','-r',(Join-Path $repoDir 'requirements.txt'))

$hfExe = Join-Path $venvDir 'Scripts\hf.exe'
if (-not (Test-Path -LiteralPath $hfExe)) { throw "Hugging Face CLI is missing: $hfExe" }
New-Item -ItemType Directory -Path $modelDir -Force | Out-Null
Run $hfExe @('download',[string]$cosy.modelRepository,'--revision',[string]$cosy.modelRevision,'--local-dir',$modelDir)
foreach ($required in @('cosyvoice2.yaml','flow.pt','hift.pt','llm.pt','campplus.onnx','speech_tokenizer_v2.onnx')) {
  if (-not (Test-Path -LiteralPath (Join-Path $modelDir $required) -PathType Leaf)) { throw "Pinned CosyVoice2 model file is missing: $required" }
}

$probe = @'
import pathlib, sys
repo = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(repo))
matcha = repo / 'third_party' / 'Matcha-TTS'
if matcha.is_dir(): sys.path.insert(0, str(matcha))
from cosyvoice.cli.cosyvoice import CosyVoice2
print('BOSSAI_COSYVOICE_IMPORT_OK')
'@
$probePath = Join-Path $InstallDir 'probe.py'
$probe | Set-Content -LiteralPath $probePath -Encoding UTF8
try { Run $venvPython @($probePath,$repoDir) } finally { Remove-Item -LiteralPath $probePath -Force -ErrorAction SilentlyContinue }

New-Item -ItemType Directory -Path $licensesDir -Force | Out-Null
$sourceLicense = Join-Path $repoDir 'LICENSE'
if (Test-Path -LiteralPath $sourceLicense) { Copy-Item -LiteralPath $sourceLicense -Destination (Join-Path $licensesDir 'CosyVoice-LICENSE.txt') -Force }
$modelReadme = Join-Path $modelDir 'README.md'
if (Test-Path -LiteralPath $modelReadme) { Copy-Item -LiteralPath $modelReadme -Destination (Join-Path $licensesDir 'CosyVoice2-MODEL-CARD.md') -Force }
$captureNotices = Join-Path (Split-Path -Parent $PSScriptRoot) 'legal\capture-python-runtime-notices.py'
if (-not (Test-Path -LiteralPath $captureNotices -PathType Leaf)) { throw "BossAI runtime notice capture tool is missing: $captureNotices" }
Run $venvPython @($captureNotices,'--component','cosyvoice2-0.5b','--out',$licensesDir)

$runtimeManifest = [ordered]@{
  schema = 'bossai.video-agent-installed-runtime.v1'
  component = 'cosyvoice2-0.5b'
  installedAt = [DateTimeOffset]::UtcNow.ToString('o')
  source = [ordered]@{ repository=[string]$cosy.sourceRepository; revision=[string]$cosy.sourceRevision; modelRepository=[string]$cosy.modelRepository; modelRevision=[string]$cosy.modelRevision }
  inference = [ordered]@{ torchFlavor=$TorchFlavor }
  licenseEvidence = 'licenses/python-dependency-notices.json'
  env = [ordered]@{
    BOSSAI_COSYVOICE_ROOT=(Join-Path $TargetDir 'CosyVoice')
    BOSSAI_COSYVOICE_MODEL_DIR=(Join-Path $TargetDir 'model\CosyVoice2-0.5B')
    BOSSAI_COSYVOICE_PYTHON=(Join-Path $TargetDir 'venv\Scripts\python.exe')
  }
  rights = [ordered]@{ referenceVoice='customer-authorized-or-bossai-owned-only'; upstreamExampleVoicesMayShip=$false }
}
$runtimeManifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $InstallDir 'runtime.json') -Encoding UTF8
Commit-Install $InstallDir $TargetDir
Write-Output 'BOSSAI_DONE CosyVoice2 runtime installed from pinned official sources.'
} catch {
  if (Test-Path -LiteralPath $InstallDir) { Remove-Item -LiteralPath $InstallDir -Recurse -Force -ErrorAction SilentlyContinue }
  throw
}
