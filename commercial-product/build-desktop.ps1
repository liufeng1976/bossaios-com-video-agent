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

# Repository-root documents that package.json declares under extraResources as
# '../../<name>'. They must all be staged at the temp build root, or
# electron-builder silently warns "file source doesn't exist" and ships an
# installer whose in-app Legal screen shows the documents as unavailable.
$repoRoot = Split-Path -Parent $root
$rootLegalDocuments = @(
  'LICENSE',
  'COMMERCIAL_LICENSE.md',
  'EULA.md',
  'LICENSE-HISTORICAL-MIT.md',
  'TERMS.md',
  'PRIVACY.md',
  'INSTALL.md'
)

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
) + ($rootLegalDocuments | ForEach-Object { Join-Path $repoRoot $_ })) {
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
  Copy-Item -LiteralPath (Join-Path $root 'first-party-assets') -Destination $tempProduct -Recurse
  Copy-Item -LiteralPath (Join-Path $root 'customer-product-metadata.json') -Destination $tempProduct
  Copy-Item -LiteralPath (Join-Path $root 'customer-third-party-notices.json') -Destination $tempProduct
  foreach ($document in $rootLegalDocuments) {
    Copy-Item -LiteralPath (Join-Path $repoRoot $document) -Destination $temp
  }
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

  # electron-builder only warns when an extraResources source is missing, so the
  # customer legal bundle is asserted here instead of trusting a clean exit code.
  $unpackedLegal = Join-Path $built 'win-unpacked\resources\legal'
  $requiredLegalArtifacts = @(
    'EULA.md',
    'SOURCE-LICENSE.txt',
    'HISTORICAL-MIT-LICENSE.md',
    'COMMERCIAL-LICENSE.md',
    'TERMS.md',
    'PRIVACY.md',
    'INSTALL.md',
    'third-party-notices.json'
  )
  $missingLegal = @($requiredLegalArtifacts | Where-Object {
    -not (Test-Path -LiteralPath (Join-Path $unpackedLegal $_))
  })
  if ($missingLegal.Count -gt 0) {
    throw "Packaged customer legal bundle is incomplete: $($missingLegal -join ', ')"
  }

  # Every runtime the install centre offers must ship its installer, or the
  # component is simply uninstallable in the delivered product.
  $unpackedInstallers = Join-Path $built 'win-unpacked\resources\runtime-installers'
  $requiredInstallers = @(
    'install-python310.ps1','install-qwen.ps1','install-cosyvoice2.ps1',
    'install-musetalk.ps1','install-whisper.ps1',
    'runtime-source-lock.json','whisper-windows-requirements.txt'
  )
  $missingInstallers = @($requiredInstallers | Where-Object {
    -not (Test-Path -LiteralPath (Join-Path $unpackedInstallers $_))
  })
  if ($missingInstallers.Count -gt 0) {
    throw "Packaged runtime installers are incomplete: $($missingInstallers -join ', ')"
  }

  # server.py is also the fallback entry point when the engine exe is absent, so
  # the shipped backend directory has to be importable on its own. Derive what it
  # needs from the source instead of trusting the extraResources filter: a module
  # added to server.py without a matching filter entry breaks only the packaged
  # build, which every source-tree test still passes.
  $unpackedBackend = Join-Path $built 'win-unpackedesourcesackend'
  $serverSource = Get-Content -LiteralPath (Join-Path $backend 'server.py') -Raw
  $backendNames = New-Object System.Collections.Generic.HashSet[string]
  foreach ($match in [regex]::Matches($serverSource, '(?m)^import\s+([a-z0-9_]+)\s*$')) {
    $candidate = $match.Groups[1].Value
    if (Test-Path -LiteralPath (Join-Path $backend "$candidate.py")) {
      [void]$backendNames.Add("$candidate.py")
    }
  }
  foreach ($match in [regex]::Matches($serverSource, 'HERE / "([a-z0-9_]+_worker\.py)"')) {
    [void]$backendNames.Add($match.Groups[1].Value)
  }
  if ($backendNames.Count -eq 0) {
    throw 'No backend dependencies were discovered in server.py; the packaging check would be vacuous.'
  }
  $missingBackend = @($backendNames | Where-Object {
    -not (Test-Path -LiteralPath (Join-Path $unpackedBackend $_))
  } | Sort-Object)
  if ($missingBackend.Count -gt 0) {
    throw "Packaged backend is missing files server.py depends on: $($missingBackend -join ', ')"
  }

  # The manifest ships so the product can read the bundle. The developer
  # documentation deliberately does not: it names the legacy product and the
  # recovery package, which the customer distribution boundary scan forbids.
  $unpackedAssets = Join-Path $built 'win-unpacked\resources\first-party-assets\manifest.json'
  if (-not (Test-Path -LiteralPath $unpackedAssets)) {
    throw 'Packaged first-party asset manifest is missing.'
  }
  if (Test-Path -LiteralPath (Join-Path $built 'win-unpacked\resources\first-party-assets\README.md')) {
    throw 'First-party asset developer documentation must not ship in the customer build.'
  }
  if (Test-Path -LiteralPath $output) {
    Remove-Item -LiteralPath $output -Recurse -Force
  }
  Copy-Item -LiteralPath $built -Destination $output -Recurse

  $installer = Get-ChildItem -LiteralPath $output -File -Filter 'BossAI-Video-Community-*-Setup.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
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
