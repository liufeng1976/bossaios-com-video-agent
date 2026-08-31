[CmdletBinding()]
param(
  [string]$TargetDir = "",
  [switch]$AcceptLicense
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Set-StrictMode -Version Latest

if (-not $AcceptLicense) {
  throw 'CPython and bundled runtime license notices must be reviewed and accepted before installation.'
}
if ($env:OS -ne 'Windows_NT') { throw 'BossAI Python runtime bootstrap currently supports Windows only.' }
if (-not $TargetDir) {
  if (-not $env:LOCALAPPDATA) { throw 'LOCALAPPDATA is unavailable; pass -TargetDir explicitly.' }
  $TargetDir = Join-Path $env:LOCALAPPDATA 'BossAI\VideoAgent\runtime-support\python310'
}
$TargetDir = [System.IO.Path]::GetFullPath($TargetDir)

$version = '3.10.20'
$release = '20260510'
$archiveName = 'cpython-3.10.20+20260510-x86_64-pc-windows-msvc-install_only_stripped.tar.gz'
$archiveUrl = "https://github.com/astral-sh/python-build-standalone/releases/download/$release/$archiveName"
$expectedSha256 = 'd1e8fb30cba04e6bb5a703e0186da77f833957de027562fa4df9fd0424ae5f7e'
$downloadRoot = Join-Path ([System.IO.Path]::GetTempPath()) 'BossAI-VideoAgent-Runtime'
$archivePath = Join-Path $downloadRoot $archiveName
$parentDir = Split-Path -Parent $TargetDir
$stageDir = "$TargetDir.installing-$PID"
New-Item -ItemType Directory -Path $downloadRoot -Force | Out-Null
New-Item -ItemType Directory -Path $parentDir -Force | Out-Null

function Verify-Archive([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Portable Python archive is missing: $Path" }
  $actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -ne $expectedSha256) { throw "Portable Python archive SHA-256 mismatch. Expected $expectedSha256, got $actual" }
}

function Test-Runtime([string]$Root) {
  $python = Join-Path $Root 'python.exe'
  if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { return $false }
  try {
    $actual = (& $python -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" | Select-Object -Last 1).Trim()
    if ($LASTEXITCODE -ne 0 -or $actual -ne $version) { return $false }
    $pip = (& $python -m pip --version | Select-Object -Last 1)
    if ($LASTEXITCODE -ne 0 -or -not $pip) { return $false }
    return $true
  } catch {
    return $false
  }
}

if (Test-Runtime $TargetDir) {
  Write-Output "BOSSAI_DONE Portable Python $version runtime is already installed and healthy."
  exit 0
}

$reuseDownload = $false
if (Test-Path -LiteralPath $archivePath -PathType Leaf) {
  try {
    Verify-Archive $archivePath
    $reuseDownload = $true
  } catch {
    Remove-Item -LiteralPath $archivePath -Force -ErrorAction SilentlyContinue
  }
}
if (-not $reuseDownload) {
  Write-Output "BOSSAI_STEP Download pinned portable CPython $version runtime"
  Invoke-WebRequest -Uri $archiveUrl -OutFile $archivePath -UseBasicParsing
  Verify-Archive $archivePath
}

$systemTarPath = if ($env:WINDIR) { Join-Path $env:WINDIR 'System32\tar.exe' } else { '' }
$tarPath = if ($systemTarPath -and (Test-Path -LiteralPath $systemTarPath -PathType Leaf)) {
  $systemTarPath
} else {
  $candidate = Get-Command tar.exe -ErrorAction SilentlyContinue
  if ($candidate) { $candidate.Source } else { '' }
}
if (-not $tarPath) { throw 'Windows tar.exe is required to extract the portable Python runtime.' }
Remove-Item -LiteralPath $stageDir -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $stageDir -Force | Out-Null

try {
  Write-Output "BOSSAI_STEP Extract portable CPython $version runtime"
  & $tarPath -xzf $archivePath -C $stageDir
  if ($LASTEXITCODE -ne 0) { throw "Portable Python archive extraction failed with exit code $LASTEXITCODE." }

  $extracted = Join-Path $stageDir 'python'
  if (-not (Test-Runtime $extracted)) { throw 'Extracted portable Python runtime failed version/pip validation.' }
  $licensePath = Join-Path $extracted 'LICENSE.txt'
  if (-not (Test-Path -LiteralPath $licensePath -PathType Leaf)) { throw "Portable Python license file is missing: $licensePath" }

  $probeVenv = Join-Path $stageDir 'venv-probe'
  & (Join-Path $extracted 'python.exe') -m venv $probeVenv
  if ($LASTEXITCODE -ne 0) { throw 'Portable Python venv probe failed.' }
  $probePython = Join-Path $probeVenv 'Scripts\python.exe'
  if (-not (Test-Path -LiteralPath $probePython -PathType Leaf)) { throw 'Portable Python venv probe did not create python.exe.' }
  & $probePython -m pip --version | Out-Null
  if ($LASTEXITCODE -ne 0) { throw 'Portable Python venv pip probe failed.' }
  Remove-Item -LiteralPath $probeVenv -Recurse -Force -ErrorAction SilentlyContinue

  if (Test-Path -LiteralPath $TargetDir) {
    Remove-Item -LiteralPath $TargetDir -Recurse -Force
  }
  Move-Item -LiteralPath $extracted -Destination $TargetDir

  $manifest = [ordered]@{
    schema = 'bossai.video-agent-installed-runtime-support.v1'
    component = 'python310'
    version = $version
    installedAt = [DateTimeOffset]::UtcNow.ToString('o')
    source = [ordered]@{
      project = 'astral-sh/python-build-standalone'
      release = $release
      url = $archiveUrl
      sha256 = $expectedSha256
      artifact = $archiveName
    }
    executable = (Join-Path $TargetDir 'python.exe')
    license = [ordered]@{
      summary = 'CPython PSF license plus bundled dependency notices preserved in LICENSE.txt'
      file = (Join-Path $TargetDir 'LICENSE.txt')
    }
    isolation = [ordered]@{
      systemRegistryModified = $false
      systemPathModified = $false
      sideBySide = $true
    }
  }
  $manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $TargetDir 'runtime.json') -Encoding UTF8

  if (-not (Test-Runtime $TargetDir)) { throw 'Installed portable Python runtime failed final validation.' }
  Write-Output "BOSSAI_DONE Portable Python $version runtime installed and verified."
} finally {
  Remove-Item -LiteralPath $stageDir -Recurse -Force -ErrorAction SilentlyContinue
}
