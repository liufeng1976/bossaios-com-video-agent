[CmdletBinding()]
param(
  [ValidateSet('pack','dist')][string]$Mode = 'dist',
  [switch]$EnableCodeSigning
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Set-StrictMode -Version Latest

$root = $PSScriptRoot
$desktop = Join-Path $root 'desktop'
$uiDist = Join-Path $root 'ui\dist'
$backend = Join-Path $root 'backend'
$engine = Join-Path $backend 'BossAI Video Engine.exe'
$output = Join-Path $desktop 'dist'

foreach ($required in @(
  (Join-Path $desktop 'package.json'),
  (Join-Path $desktop 'main.cjs'),
  (Join-Path $desktop 'preload.js'),
  (Join-Path $desktop 'build\icon.svg'),
  (Join-Path $uiDist 'index.html'),
  $engine,
  (Join-Path $root 'customer-product-metadata.json'),
  (Join-Path $root 'customer-third-party-notices.json'),
  (Join-Path $root 'runtime-installers\runtime-source-lock.json'),
  (Join-Path $root 'legal\capture-python-runtime-notices.py')
)) {
  if (-not (Test-Path -LiteralPath $required)) {
    throw "Required BossAI desktop build input is missing: $required"
  }
}

$temp = Join-Path ([System.IO.Path]::GetTempPath()) ("bossai-video-desktop-build-" + [Guid]::NewGuid().ToString('N'))
$tempProduct = Join-Path $temp 'commercial-product'
$tempDesktop = Join-Path $tempProduct 'desktop'
try {
  New-Item -ItemType Directory -Path $tempDesktop -Force | Out-Null
  New-Item -ItemType Directory -Path (Join-Path $tempProduct 'ui') -Force | Out-Null
  New-Item -ItemType Directory -Path (Join-Path $tempProduct 'legal') -Force | Out-Null

  foreach ($file in @('package.json','main.cjs','preload.js')) {
    Copy-Item -LiteralPath (Join-Path $desktop $file) -Destination (Join-Path $tempDesktop $file)
  }
  Copy-Item -LiteralPath (Join-Path $desktop 'build') -Destination $tempDesktop -Recurse
  Copy-Item -LiteralPath $uiDist -Destination (Join-Path $tempProduct 'ui') -Recurse
  Copy-Item -LiteralPath $backend -Destination $tempProduct -Recurse
  Copy-Item -LiteralPath (Join-Path $root 'runtime-installers') -Destination $tempProduct -Recurse
  Copy-Item -LiteralPath (Join-Path $root 'customer-product-metadata.json') -Destination $tempProduct
  Copy-Item -LiteralPath (Join-Path $root 'customer-third-party-notices.json') -Destination $tempProduct
  Copy-Item -LiteralPath (Join-Path $root 'legal\capture-python-runtime-notices.py') -Destination (Join-Path $tempProduct 'legal')

  Push-Location $tempDesktop
  try {
    if ($EnableCodeSigning) {
      $signingLink = [string]$env:WIN_CSC_LINK
      if (-not $signingLink.Trim()) { $signingLink = [string]$env:CSC_LINK }
      if (-not $signingLink.Trim()) {
        throw 'EnableCodeSigning requires WIN_CSC_LINK or CSC_LINK to reference the real Windows code-signing certificate.'
      }
      $env:CSC_IDENTITY_AUTO_DISCOVERY = 'true'
    } else {
      $env:CSC_IDENTITY_AUTO_DISCOVERY = 'false'
    }
    & npm.cmd install --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw "desktop npm install failed with exit code $LASTEXITCODE" }
    if ($Mode -eq 'pack') {
      & npm.cmd run pack
    } else {
      & npm.cmd run dist
    }
    if ($LASTEXITCODE -ne 0) { throw "desktop electron-builder failed with exit code $LASTEXITCODE" }
  } finally {
    Pop-Location
  }

  $built = Join-Path $tempDesktop 'dist'
  if (-not (Test-Path -LiteralPath $built)) {
    throw 'electron-builder did not produce a dist directory.'
  }
  if (Test-Path -LiteralPath $output) {
    Remove-Item -LiteralPath $output -Recurse -Force
  }
  Copy-Item -LiteralPath $built -Destination $output -Recurse

  $installer = Get-ChildItem -LiteralPath $output -File -Filter 'BossAI-Video-Agent-*-Setup.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
  $unpacked = Join-Path $output 'win-unpacked'
  Write-Host 'RESULT: BossAI Video Agent isolated desktop build passed.'
  Write-Host "Mode    : $Mode"
  Write-Host "Output  : $output"
  Write-Host "Unpacked: $([bool](Test-Path -LiteralPath $unpacked))"
  if ($installer) {
    Write-Host "Installer: $($installer.FullName)"
    Write-Host "Bytes    : $($installer.Length)"
    Write-Host "SHA256   : $((Get-FileHash -LiteralPath $installer.FullName -Algorithm SHA256).Hash.ToLowerInvariant())"
  }
  if ($EnableCodeSigning) {
    if (-not $installer) { throw 'Signed dist build did not produce the expected installer.' }
    $applicationExe = Join-Path $unpacked 'BossAI Video Agent.exe'
    $verifier = Join-Path $root 'verify-windows-signing.ps1'
    & $verifier -ApplicationExe $applicationExe -InstallerExe $installer.FullName
    if ($LASTEXITCODE -ne 0) { throw "Authenticode verification failed after signed build (rc=$LASTEXITCODE)." }
    Write-Host 'CodeSign: verified Authenticode signature on application and installer.'
  } else {
    Write-Host 'CodeSign: disabled for this build; artifact is not a commercial release candidate.'
  }
} finally {
  Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
}
