[CmdletBinding()]
param(
  [string]$TargetDir = "",
  [string]$PythonExe = "",
  [string]$DownloadRoot = "",
  [ValidateSet('gpu','cpu')][string]$Profile = 'gpu',
  [string]$ModelSourceDir = "",
  [switch]$AcceptLicense
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Set-StrictMode -Version Latest

if (-not $AcceptLicense) { throw 'faster-whisper and Whisper model license notices must be reviewed and accepted before installation.' }

$lockPath = Join-Path $PSScriptRoot 'runtime-source-lock.json'
$lock = Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 | ConvertFrom-Json
$whisper = $lock.components.'faster-whisper-large-v3'
if (-not $whisper) { throw 'faster-whisper source lock is missing.' }

if (-not $PythonExe) {
  if (-not $env:LOCALAPPDATA) { throw 'LOCALAPPDATA is unavailable; pass -PythonExe explicitly.' }
  $PythonExe = Join-Path $env:LOCALAPPDATA 'BossAI\VideoAgent\runtimes\python310\python.exe'
}
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) { throw "BossAI Python 3.10 runtime is required first: $PythonExe" }

if (-not $TargetDir) {
  if (-not $env:LOCALAPPDATA) { throw 'LOCALAPPDATA is unavailable; pass -TargetDir explicitly.' }
  $TargetDir = Join-Path $env:LOCALAPPDATA 'BossAI\VideoAgent\runtimes\faster-whisper-large-v3'
}
$TargetDir = [System.IO.Path]::GetFullPath($TargetDir)
$PythonExe = [System.IO.Path]::GetFullPath($PythonExe)

$existingManifest = Join-Path $TargetDir 'runtime.json'
if (Test-Path -LiteralPath $existingManifest -PathType Leaf) { throw "faster-whisper runtime is already installed: $TargetDir" }

$InstallDir = "$TargetDir.installing-$([guid]::NewGuid().ToString('N'))"
$downloadRoot = if ($DownloadRoot) { [System.IO.Path]::GetFullPath($DownloadRoot) } elseif ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA 'BossAI\VideoAgent\downloads' } else { Join-Path ([System.IO.Path]::GetTempPath()) 'BossAI-VideoAgent-Downloads' }
New-Item -ItemType Directory -Path $downloadRoot -Force | Out-Null

function Run([string]$Command, [string[]]$Arguments) {
  Write-Output "BOSSAI_STEP $Command $($Arguments -join ' ')"
  & $Command @Arguments
  if ($LASTEXITCODE -ne 0) { throw "$Command failed with exit code $LASTEXITCODE" }
}

function Verify-Hash([string]$Path, [string]$Expected, [string]$Label) {
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "$Label is missing: $Path" }
  $actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -ne ([string]$Expected).ToLowerInvariant()) { throw "$Label SHA-256 mismatch. Expected $Expected, got $actual" }
}

function Download-Verified([string]$Url, [string]$Destination, [string]$ExpectedHash, [string]$Label) {
  if (Test-Path -LiteralPath $Destination -PathType Leaf) {
    try { Verify-Hash $Destination $ExpectedHash $Label; return } catch { Remove-Item -LiteralPath $Destination -Force -ErrorAction SilentlyContinue }
  }
  Write-Output "BOSSAI_STEP Download $Label"
  $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
  if ($curl) {
    & $curl.Source -L --fail --retry 5 --retry-delay 2 --continue-at - -o $Destination $Url
    if ($LASTEXITCODE -ne 0) { throw "$Label download failed with exit code $LASTEXITCODE" }
  } else {
    Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing
  }
  Verify-Hash $Destination $ExpectedHash $Label
}

function Commit-Install([string]$StagingDir, [string]$FinalDir) {
  $parent = Split-Path -Parent $FinalDir
  if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
  $quarantine = ''
  if (Test-Path -LiteralPath $FinalDir) {
    if (Test-Path -LiteralPath (Join-Path $FinalDir 'runtime.json') -PathType Leaf) { throw "Refusing to replace an installed faster-whisper runtime: $FinalDir" }
    $quarantine = "$FinalDir.incomplete-$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())"
    Move-Item -LiteralPath $FinalDir -Destination $quarantine
  }
  try { Move-Item -LiteralPath $StagingDir -Destination $FinalDir }
  catch {
    if ($quarantine -and -not (Test-Path -LiteralPath $FinalDir) -and (Test-Path -LiteralPath $quarantine)) { Move-Item -LiteralPath $quarantine -Destination $FinalDir }
    throw
  }
  if ($quarantine) { Remove-Item -LiteralPath $quarantine -Recurse -Force -ErrorAction SilentlyContinue }
}

$installMutex = [System.Threading.Mutex]::new($false, 'BossAIVideoAgent-Whisper-Install')
$installMutexAcquired = $false
try {
  $installMutexAcquired = $installMutex.WaitOne([TimeSpan]::FromMinutes(60))
  if (-not $installMutexAcquired) { throw 'Another BossAI faster-whisper installation is already running.' }

  New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null

  $venvDir = Join-Path $InstallDir 'venv'
  $venvPython = Join-Path $venvDir 'Scripts\python.exe'
  $modelDir = Join-Path $InstallDir 'model'
  $licensesDir = Join-Path $InstallDir 'licenses'
  New-Item -ItemType Directory -Path $modelDir,$licensesDir -Force | Out-Null

  Run $PythonExe @('-m','venv',$venvDir)
  if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) { throw 'faster-whisper virtual environment creation failed.' }
  Run $venvPython @('-m','pip','install','pip==25.1.1','setuptools==80.9.0','wheel==0.45.1')

  $requirements = Join-Path $PSScriptRoot ([string]$whisper.inferenceRuntime.requirements)
  if (-not (Test-Path -LiteralPath $requirements -PathType Leaf)) { throw "Whisper requirements lock is missing: $requirements" }
  Run $venvPython @('-m','pip','install','--index-url','https://pypi.org/simple','-r',$requirements)

  # Pinned model files. The revision is fixed and every file is SHA-256 verified,
  # so inference can later run fully offline.
  foreach ($entry in @($whisper.files)) {
    $name = [string]$entry.name
    $sha = [string]$entry.sha256
    if (-not $name -or -not $sha) { throw 'Pinned Whisper file metadata is incomplete.' }
    $target = Join-Path $modelDir $name
    if ($ModelSourceDir) {
      $source = Join-Path ([System.IO.Path]::GetFullPath($ModelSourceDir)) $name
      Verify-Hash $source $sha "Whisper model file $name"
      Copy-Item -LiteralPath $source -Destination $target
    } else {
      $encoded = [Uri]::EscapeDataString($name)
      $url = "https://huggingface.co/$([string]$whisper.repository)/resolve/$([string]$whisper.revision)/$encoded" + "?download=true"
      $cached = Join-Path $downloadRoot ("faster-whisper-large-v3-" + $name)
      Download-Verified $url $cached $sha "Whisper model file $name"
      Copy-Item -LiteralPath $cached -Destination $target
    }
    Verify-Hash $target $sha "Whisper installed model file $name"
  }

  $modelLicense = Join-Path $licensesDir 'faster-whisper-large-v3-MODEL-CARD.md'
  Invoke-WebRequest -UseBasicParsing -OutFile $modelLicense `
    -Uri "https://huggingface.co/$([string]$whisper.repository)/resolve/$([string]$whisper.revision)/README.md?download=true"
  if (-not (Test-Path -LiteralPath $modelLicense -PathType Leaf)) { throw 'Whisper model license evidence download failed.' }

  $packageLicense = Join-Path $licensesDir 'faster-whisper-LICENSE.txt'
  Invoke-WebRequest -UseBasicParsing -OutFile $packageLicense `
    -Uri 'https://raw.githubusercontent.com/SYSTRAN/faster-whisper/master/LICENSE'
  if (-not (Test-Path -LiteralPath $packageLicense -PathType Leaf)) { throw 'faster-whisper package license evidence download failed.' }

  # Prove the runtime loads the pinned model locally before committing. The probe
  # always loads on CPU/int8 so it stays valid on machines without a usable GPU.
  $device = if ($Profile -eq 'gpu') { 'auto' } else { 'cpu' }
  $probe = @'
import os, sys
os.environ['HF_HUB_OFFLINE'] = '1'
from faster_whisper import WhisperModel
try:
    WhisperModel(sys.argv[1], device='cpu', compute_type='int8')
except Exception as exc:
    print('PROBE_FAILED', exc)
    raise SystemExit(1)
print('PROBE_OK')
'@
  $probeFile = Join-Path $InstallDir 'probe.py'
  Set-Content -LiteralPath $probeFile -Value $probe -Encoding UTF8
  $previousPreference = $ErrorActionPreference
  try {
    $ErrorActionPreference = 'Continue'
    $probeOutput = (& $venvPython $probeFile $modelDir 2>&1 | Out-String)
    $probeExit = $LASTEXITCODE
  } finally { $ErrorActionPreference = $previousPreference }
  if ($probeExit -ne 0 -or $probeOutput -notmatch 'PROBE_OK') { throw "faster-whisper model probe failed: $probeOutput" }
  Remove-Item -LiteralPath $probeFile -Force -ErrorAction SilentlyContinue

  $runtimeManifest = [ordered]@{
    schema = 'bossai.video-agent-installed-runtime.v2'
    component = 'faster-whisper-large-v3'
    installedAt = [DateTimeOffset]::UtcNow.ToString('o')
    source = [ordered]@{ repository=[string]$whisper.repository; revision=[string]$whisper.revision }
    inference = [ordered]@{ package='faster-whisper'; backend=[string]$whisper.inferenceRuntime.backend; device=$device }
    usagePolicy = [string]$whisper.usagePolicy
    licenseEvidence = @('licenses/faster-whisper-large-v3-MODEL-CARD.md','licenses/faster-whisper-LICENSE.txt')
    files = @($whisper.files | ForEach-Object {
      $path = Join-Path $modelDir ([string]$_.name)
      [ordered]@{ name=[string]$_.name; bytes=(Get-Item -LiteralPath $path).Length; sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() }
    })
    env = [ordered]@{
      BOSSAI_WHISPER_MODEL = (Join-Path $TargetDir 'model')
      BOSSAI_WHISPER_PYTHON = (Join-Path $TargetDir 'venv\Scripts\python.exe')
      BOSSAI_WHISPER_DEVICE = $device
    }
  }
  $runtimeManifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $InstallDir 'runtime.json') -Encoding UTF8

  Commit-Install $InstallDir $TargetDir
  Write-Output 'BOSSAI_DONE faster-whisper runtime installed from the pinned official model revision.'
} catch {
  if (Test-Path -LiteralPath $InstallDir) { Remove-Item -LiteralPath $InstallDir -Recurse -Force -ErrorAction SilentlyContinue }
  throw
} finally {
  if ($installMutexAcquired) { $installMutex.ReleaseMutex() | Out-Null }
  $installMutex.Dispose()
}
