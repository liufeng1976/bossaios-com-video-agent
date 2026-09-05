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
$versionInfo = Join-Path $backend 'windows-version-info.txt'

# Worker scripts are executed by a separately installed interpreter, so they are
# data, not imports: PyInstaller will not pick them up by following imports. The
# engine resolves them next to itself, which under --onefile means the _MEIPASS
# extraction directory, so each one must be passed as --add-data or the feature
# is simply missing from the packaged product.
#
# The list is derived from the engine source rather than hand-maintained,
# because a worker added to server.py without a matching --add-data produces a
# build that passes every source-tree test and then fails on the customer's
# machine.
$workerNames = @(
  Select-String -LiteralPath $entry -Pattern 'HERE / "([a-z0-9_]+_worker\.py)"' -AllMatches |
    ForEach-Object { $_.Matches } | ForEach-Object { $_.Groups[1].Value }
) | Sort-Object -Unique
if ($workerNames.Count -eq 0) {
  throw 'No worker scripts were discovered in server.py; the packaging check would be vacuous.'
}
$workerPaths = @($workerNames | ForEach-Object { Join-Path $backend $_ })

if (-not $OutputDirectory) {
  $OutputDirectory = Join-Path $root 'out\engine'
}
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)

foreach ($required in @($Python, $requirements, $entry, $versionInfo) + $workerPaths) {
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
    @($workerPaths | ForEach-Object { '--add-data'; "$_;." }) `
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
