[CmdletBinding()]
param(
  [string]$TargetDir = "",
  [Parameter(Mandatory = $true)][string]$PythonExe,
  [ValidateSet('cpu','cu118','cu124')][string]$WheelFlavor = 'cpu',
  [switch]$AcceptLicense
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Set-StrictMode -Version Latest

if (-not $AcceptLicense) { throw 'Qwen and llama-cpp-python license notices must be reviewed and accepted before installation.' }
$lockPath = Join-Path $PSScriptRoot 'runtime-source-lock.json'
$lock = Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 | ConvertFrom-Json
$qwen = $lock.components.'qwen2.5-7b-instruct'
if (-not $qwen) { throw 'Qwen source lock is missing.' }

if (-not $TargetDir) {
  if (-not $env:LOCALAPPDATA) { throw 'LOCALAPPDATA is unavailable; pass -TargetDir explicitly.' }
  $TargetDir = Join-Path $env:LOCALAPPDATA 'BossAI\VideoAgent\runtimes\qwen2.5-7b-instruct'
}
$TargetDir = [System.IO.Path]::GetFullPath($TargetDir)
$PythonExe = [System.IO.Path]::GetFullPath($PythonExe)
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) { throw "Python executable is missing: $PythonExe" }
$existingManifest = Join-Path $TargetDir 'runtime.json'
if (Test-Path -LiteralPath $existingManifest -PathType Leaf) {
  throw "Qwen runtime is already installed: $TargetDir"
}
$InstallDir = "$TargetDir.installing-$([guid]::NewGuid().ToString('N'))"
$pythonVersion = (& $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" | Select-Object -Last 1).Trim()
if ($LASTEXITCODE -ne 0 -or $pythonVersion -notin @('3.10','3.11','3.12')) { throw "Qwen runtime requires Python 3.10-3.12. Current: $pythonVersion" }

function Run([string]$Command, [string[]]$Arguments) {
  Write-Output ("BOSSAI_RUN " + $Command + " " + ($Arguments -join ' '))
  & $Command @Arguments
  if ($LASTEXITCODE -ne 0) { throw "Command failed with exit code $LASTEXITCODE`: $Command" }
}

function Commit-Install([string]$StagingDir, [string]$FinalDir) {
  $parent = Split-Path -Parent $FinalDir
  if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
  $quarantine = ''
  if (Test-Path -LiteralPath $FinalDir) {
    if (Test-Path -LiteralPath (Join-Path $FinalDir 'runtime.json') -PathType Leaf) {
      throw "Refusing to replace an installed Qwen runtime: $FinalDir"
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
$venvDir = Join-Path $InstallDir 'venv'
$venvPython = Join-Path $venvDir 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) { Run $PythonExe @('-m','venv',$venvDir) }
Run $venvPython @('-m','pip','install','pip==25.1.1','setuptools==80.9.0','wheel==0.45.1','huggingface_hub==0.30.2')

$wheelIndex = switch ($WheelFlavor) {
  'cu118' { 'https://abetlen.github.io/llama-cpp-python/whl/cu118' }
  'cu124' { 'https://abetlen.github.io/llama-cpp-python/whl/cu124' }
  default { 'https://abetlen.github.io/llama-cpp-python/whl/cpu' }
}
Run $venvPython @('-m','pip','install','llama-cpp-python==0.3.34','--extra-index-url',$wheelIndex)

$hfExe = Join-Path $venvDir 'Scripts\hf.exe'
if (-not (Test-Path -LiteralPath $hfExe)) { throw "Hugging Face CLI is missing: $hfExe" }
$modelDir = Join-Path $InstallDir 'model'
New-Item -ItemType Directory -Path $modelDir -Force | Out-Null
$fileNames = @($qwen.files | ForEach-Object { [string]$_ })
if ($fileNames.Count -ne 2) { throw 'Pinned Qwen Q4_K_M split file list is invalid.' }
Run $hfExe @('download',[string]$qwen.repository,'--revision',[string]$qwen.revision,'--local-dir',$modelDir,'--include',$fileNames[0],$fileNames[1],'README.md','LICENSE')
foreach ($name in $fileNames) {
  $path = Join-Path $modelDir $name
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Pinned Qwen model shard is missing: $path" }
}

# llama.cpp split GGUF loading starts from shard 1 and resolves the sibling shard automatically.
$modelEntry = Join-Path $modelDir $fileNames[0]
$probe = @'
from llama_cpp import Llama
import sys
m = Llama(model_path=sys.argv[1], n_ctx=256, n_gpu_layers=0, verbose=False)
print('BOSSAI_QWEN_MODEL_OK')
'@
$probePath = Join-Path $InstallDir 'probe.py'
$probe | Set-Content -LiteralPath $probePath -Encoding UTF8
try { Run $venvPython @($probePath,$modelEntry) } finally { Remove-Item -LiteralPath $probePath -Force -ErrorAction SilentlyContinue }

$licensesDir = Join-Path $InstallDir 'licenses'
New-Item -ItemType Directory -Path $licensesDir -Force | Out-Null
$modelLicense = Join-Path $modelDir 'LICENSE'
if (Test-Path -LiteralPath $modelLicense) { Copy-Item -LiteralPath $modelLicense -Destination (Join-Path $licensesDir 'Qwen-LICENSE.txt') -Force }
$captureNotices = Join-Path (Split-Path -Parent $PSScriptRoot) 'legal\capture-python-runtime-notices.py'
if (-not (Test-Path -LiteralPath $captureNotices -PathType Leaf)) { throw "BossAI runtime notice capture tool is missing: $captureNotices" }
Run $venvPython @($captureNotices,'--component','qwen2.5-7b-instruct','--out',$licensesDir)

$runtimeManifest = [ordered]@{
  schema = 'bossai.video-agent-installed-runtime.v1'
  component = 'qwen2.5-7b-instruct'
  installedAt = [DateTimeOffset]::UtcNow.ToString('o')
  source = [ordered]@{ repository=[string]$qwen.repository; revision=[string]$qwen.revision; variant=[string]$qwen.variant }
  inference = [ordered]@{ package='llama-cpp-python'; version='0.3.34'; wheelFlavor=$WheelFlavor }
  licenseEvidence = 'licenses/python-dependency-notices.json'
  files = @($fileNames | ForEach-Object {
    $path = Join-Path $modelDir $_
    [ordered]@{ name=$_; bytes=(Get-Item -LiteralPath $path).Length; sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() }
  })
  env = [ordered]@{
    BOSSAI_QWEN_MODEL=(Join-Path $TargetDir ('model\\' + $fileNames[0]))
    BOSSAI_QWEN_PYTHON=(Join-Path $TargetDir 'venv\\Scripts\\python.exe')
  }
}
$runtimeManifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $InstallDir 'runtime.json') -Encoding UTF8
Commit-Install $InstallDir $TargetDir
Write-Output 'BOSSAI_DONE Qwen runtime installed from pinned official sources.'
} catch {
  if (Test-Path -LiteralPath $InstallDir) { Remove-Item -LiteralPath $InstallDir -Recurse -Force -ErrorAction SilentlyContinue }
  throw
}
