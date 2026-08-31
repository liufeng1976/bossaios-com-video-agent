[CmdletBinding()]
param(
  [string]$Python = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
  [string]$OutputDirectory = ""
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$root = $PSScriptRoot
$backend = Join-Path $root 'backend'
$requirements = Join-Path $backend 'engine-build-requirements.txt'
$entry = Join-Path $backend 'server.py'
$qwenWorker = Join-Path $backend 'qwen_worker.py'
$cosyWorker = Join-Path $backend 'cosyvoice_worker.py'
$versionInfo = Join-Path $backend 'windows-version-info.txt'

if (-not $OutputDirectory) {
  $OutputDirectory = Join-Path $root 'out\engine'
}
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)

foreach ($required in @($Python, $requirements, $entry, $qwenWorker, $cosyWorker, $versionInfo)) {
  if (-not (Test-Path -LiteralPath $required)) {
    throw "Required BossAI Video Engine build input is missing: $required"
  }
}

$versionOk = (& $Python -c "import sys; print('1' if sys.version_info[:2] == (3, 12) else '0')" | Select-Object -Last 1).Trim()
if ($versionOk -ne '1') {
  throw 'BossAI Video Engine must be built with Python 3.12.'
}

$tempRoot = Join-Path $env:TEMP ("bossai-video-engine-build-" + [Guid]::NewGuid().ToString('N'))
$venv = Join-Path $tempRoot 'venv'
$work = Join-Path $tempRoot 'work'
$spec = Join-Path $tempRoot 'spec'
$venvPython = Join-Path $venv 'Scripts\python.exe'
$pyinstaller = Join-Path $venv 'Scripts\pyinstaller.exe'

New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

try {
  & $Python -m venv $venv
  if ($LASTEXITCODE -ne 0) { throw "Failed to create Engine build venv (rc=$LASTEXITCODE)." }

  & $venvPython -m pip install --disable-pip-version-check --no-input -r $requirements
  if ($LASTEXITCODE -ne 0) { throw "Failed to install Engine build requirements (rc=$LASTEXITCODE)." }

  & $pyinstaller `
    --noconfirm `
    --clean `
    --onefile `
    --name 'BossAI Video Engine' `
    --version-file $versionInfo `
    --distpath $OutputDirectory `
    --workpath $work `
    --specpath $spec `
    --paths $backend `
    --add-data "$qwenWorker;." `
    --add-data "$cosyWorker;." `
    $entry
  if ($LASTEXITCODE -ne 0) { throw "PyInstaller Engine build failed (rc=$LASTEXITCODE)." }

  $engine = Join-Path $OutputDirectory 'BossAI Video Engine.exe'
  if (-not (Test-Path -LiteralPath $engine)) {
    throw "Engine build completed without expected output: $engine"
  }

  $hash = (Get-FileHash -LiteralPath $engine -Algorithm SHA256).Hash.ToLowerInvariant()
  $size = (Get-Item -LiteralPath $engine).Length
  Write-Host 'RESULT: BossAI Video Engine build passed.'
  Write-Host "Engine: $engine"
  Write-Host "Bytes : $size"
  Write-Host "SHA256: $hash"
} finally {
  Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
