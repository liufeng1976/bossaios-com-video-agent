[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Set-StrictMode -Version Latest

$root = $PSScriptRoot
$source = Join-Path $root 'ui'
$target = Join-Path $source 'dist'
if (-not (Test-Path -LiteralPath (Join-Path $source 'package.json'))) {
  throw "BossAI Video Agent UI package is missing: $source"
}

$temp = Join-Path ([System.IO.Path]::GetTempPath()) ("bossai-video-ui-build-" + [Guid]::NewGuid().ToString('N'))
try {
  New-Item -ItemType Directory -Path $temp -Force | Out-Null
  Copy-Item -LiteralPath (Join-Path $source 'package.json') -Destination $temp
  Copy-Item -LiteralPath (Join-Path $source 'index.html') -Destination $temp
  Copy-Item -LiteralPath (Join-Path $source 'vite.config.js') -Destination $temp
  Copy-Item -LiteralPath (Join-Path $source 'src') -Destination $temp -Recurse
  if (Test-Path -LiteralPath (Join-Path $source 'public')) {
    Copy-Item -LiteralPath (Join-Path $source 'public') -Destination $temp -Recurse
  }

  Push-Location $temp
  try {
    & npm.cmd install --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw "npm install failed with exit code $LASTEXITCODE" }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw "npm run build failed with exit code $LASTEXITCODE" }
  } finally {
    Pop-Location
  }

  $built = Join-Path $temp 'dist'
  if (-not (Test-Path -LiteralPath (Join-Path $built 'index.html'))) {
    throw 'BossAI UI build did not produce dist/index.html.'
  }
  if (Test-Path -LiteralPath $target) {
    Remove-Item -LiteralPath $target -Recurse -Force
  }
  Copy-Item -LiteralPath $built -Destination $target -Recurse
  Write-Host "RESULT: BossAI Video Agent isolated UI build passed."
  Write-Host "Output: $target"
} finally {
  Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
}
