[CmdletBinding(SupportsShouldProcess = $true)]
param(
  [string]$DestinationRoot = 'D:\BossAI-Models\VideoAgent',
  [string]$SourceRoot = '',
  [string]$RecoveryMuseTalkStagingDir = '',
  [switch]$RemoveSourceAfterVerify
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Set-StrictMode -Version Latest

if (-not $SourceRoot) {
  if (-not $env:LOCALAPPDATA) { throw 'LOCALAPPDATA is unavailable; pass -SourceRoot explicitly.' }
  $SourceRoot = Join-Path $env:LOCALAPPDATA 'BossAI\VideoAgent'
}
$SourceRoot = [System.IO.Path]::GetFullPath($SourceRoot)
$DestinationRoot = [System.IO.Path]::GetFullPath($DestinationRoot)
$sourceRuntimes = Join-Path $SourceRoot 'runtimes'
$sourceDownloads = Join-Path $SourceRoot 'downloads'
$destinationRuntimes = Join-Path $DestinationRoot 'runtimes'
$destinationDownloads = Join-Path $DestinationRoot 'downloads'
$configPath = Join-Path $SourceRoot 'runtime-storage.json'

if ($SourceRoot.TrimEnd('\') -eq $DestinationRoot.TrimEnd('\')) { throw 'Source and destination storage roots must be different.' }
if (-not (Test-Path -LiteralPath $sourceRuntimes -PathType Container)) { throw "BossAI runtime source directory is missing: $sourceRuntimes" }

$activeInstallers = @(Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -and $_.CommandLine -match 'install-(qwen|cosyvoice2|musetalk)\.ps1|hf_hub_download'
})
if ($activeInstallers.Count -gt 0) {
  $details = $activeInstallers | ForEach-Object { "$($_.ProcessId):$($_.Name)" }
  throw "Refusing runtime migration while an installer/download process is active: $($details -join ', ')"
}

$staging = @(Get-ChildItem -LiteralPath $sourceRuntimes -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '\.installing-' })
$recoveryStaging = ''
if ($RecoveryMuseTalkStagingDir) {
  $recoveryStaging = [System.IO.Path]::GetFullPath($RecoveryMuseTalkStagingDir)
  $expectedPrefix = (Join-Path $sourceRuntimes 'musetalk.installing-')
  if (-not $recoveryStaging.StartsWith($expectedPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "MuseTalk recovery staging must belong to the source runtime root: $recoveryStaging"
  }
  if (-not (Test-Path -LiteralPath $recoveryStaging -PathType Container)) {
    throw "MuseTalk recovery staging directory is missing: $recoveryStaging"
  }
  $unexpectedStaging = @($staging | Where-Object { $_.FullName -ne $recoveryStaging })
  if ($unexpectedStaging.Count -gt 0) {
    throw "Refusing runtime migration because unrelated install staging exists: $($unexpectedStaging.FullName -join '; ')"
  }
  Write-Output "BOSSAI_STEP Explicit MuseTalk partial-promote recovery enabled: $recoveryStaging"
} elseif ($staging.Count -gt 0) {
  throw "Refusing runtime migration while install staging exists: $($staging.FullName -join '; ')"
}

function Get-TreeStats([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
    return [ordered]@{ files = 0L; bytes = 0L }
  }
  $files = @(Get-ChildItem -LiteralPath $Path -Recurse -File -Force -ErrorAction Stop)
  $sum = ($files | Measure-Object -Property Length -Sum).Sum
  if ($null -eq $sum) { $sum = 0 }
  return [ordered]@{ files = [long]$files.Count; bytes = [long]$sum }
}

function Copy-VerifiedTree([string]$Source, [string]$Destination, [string]$Label) {
  if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
    Write-Output "BOSSAI_STEP Skip missing $Label source: $Source"
    return
  }
  New-Item -ItemType Directory -Path $Destination -Force | Out-Null
  $before = Get-TreeStats $Source
  Write-Output "BOSSAI_STEP Copy $Label files=$($before.files) bytes=$($before.bytes) -> $Destination"
  & robocopy.exe $Source $Destination /E /COPY:DAT /DCOPY:DAT /R:2 /W:2 /XJ /NFL /NDL /NP /NJH /NJS
  $code = $LASTEXITCODE
  if ($code -gt 7) { throw "robocopy failed for $Label with exit code $code" }
  $after = Get-TreeStats $Destination
  if ($after.files -lt $before.files -or $after.bytes -lt $before.bytes) {
    throw "$Label verification failed after copy. sourceFiles=$($before.files) sourceBytes=$($before.bytes) destinationFiles=$($after.files) destinationBytes=$($after.bytes)"
  }
  Write-Output "BOSSAI_STEP Verified copied $Label files=$($after.files) bytes=$($after.bytes)"
}

function Rewrite-StorageValue($Value, [string]$OldRuntimeRoot, [string]$NewRuntimeRoot, [string]$OldDownloadRoot, [string]$NewDownloadRoot) {
  if ($Value -is [string]) {
    if ($Value.StartsWith($OldRuntimeRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
      return $NewRuntimeRoot + $Value.Substring($OldRuntimeRoot.Length)
    }
    if ($Value.StartsWith($OldDownloadRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
      return $NewDownloadRoot + $Value.Substring($OldDownloadRoot.Length)
    }
    return $Value
  }
  if ($Value -is [System.Collections.IDictionary]) {
    $mapped = [ordered]@{}
    foreach ($key in $Value.Keys) { $mapped[$key] = Rewrite-StorageValue $Value[$key] $OldRuntimeRoot $NewRuntimeRoot $OldDownloadRoot $NewDownloadRoot }
    return $mapped
  }
  if ($Value -is [pscustomobject]) {
    $mapped = [ordered]@{}
    foreach ($property in $Value.PSObject.Properties) { $mapped[$property.Name] = Rewrite-StorageValue $property.Value $OldRuntimeRoot $NewRuntimeRoot $OldDownloadRoot $NewDownloadRoot }
    return $mapped
  }
  if ($Value -is [System.Collections.IEnumerable] -and -not ($Value -is [string])) {
    return @($Value | ForEach-Object { Rewrite-StorageValue $_ $OldRuntimeRoot $NewRuntimeRoot $OldDownloadRoot $NewDownloadRoot })
  }
  return $Value
}

function Rewrite-RuntimeManifests() {
  foreach ($manifest in @(Get-ChildItem -LiteralPath $destinationRuntimes -Recurse -File -Filter 'runtime.json' -ErrorAction Stop)) {
    $value = Get-Content -LiteralPath $manifest.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
    $rewritten = Rewrite-StorageValue $value $sourceRuntimes $destinationRuntimes $sourceDownloads $destinationDownloads
    $rewritten | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $manifest.FullName -Encoding UTF8
    Write-Output "BOSSAI_STEP Rewrote runtime storage paths: $($manifest.FullName)"
  }
}

function Verify-InstalledRuntimeNotices() {
  $commercialRoot = Split-Path -Parent $PSScriptRoot
  $verifier = Join-Path $commercialRoot 'verify-installed-runtime-notices.py'
  if (-not (Test-Path -LiteralPath $verifier -PathType Leaf)) { throw "Installed runtime verifier is missing: $verifier" }
  $privatePython = Join-Path $SourceRoot 'runtime-support\python310\python.exe'
  $python = if (Test-Path -LiteralPath $privatePython -PathType Leaf) { $privatePython } else { (Get-Command python.exe -ErrorAction Stop).Source }
  & $python $verifier --runtimes-root $destinationRuntimes
  if ($LASTEXITCODE -ne 0) { throw 'Installed runtime LICENSE/NOTICE verification failed after storage migration.' }
}

if ($PSCmdlet.ShouldProcess($DestinationRoot, 'Migrate BossAI Video Agent runtimes and downloads')) {
  New-Item -ItemType Directory -Path $DestinationRoot -Force | Out-Null
  New-Item -ItemType Directory -Path $destinationRuntimes -Force | Out-Null
  foreach ($component in @('qwen2.5-7b-instruct','cosyvoice2-0.5b','musetalk')) {
    $componentSource = Join-Path $sourceRuntimes $component
    $componentDestination = Join-Path $destinationRuntimes $component
    Copy-VerifiedTree $componentSource $componentDestination "runtime component $component"
  }
  if ($recoveryStaging) {
    $museDestination = Join-Path $destinationRuntimes 'musetalk'
    Copy-VerifiedTree $recoveryStaging $museDestination 'MuseTalk partial-promote recovery staging'
    $gitMetadata = Join-Path $museDestination 'MuseTalk\.git'
    if (Test-Path -LiteralPath $gitMetadata) {
      try {
        Remove-Item -LiteralPath $gitMetadata -Recurse -Force
        Write-Output 'BOSSAI_STEP Removed non-runtime MuseTalk Git metadata from D-drive recovery target.'
      } catch {
        Write-Output "BOSSAI_STEP Non-runtime MuseTalk Git metadata could not be removed; continuing because runtime integrity is verified independently: $($_.Exception.Message)"
      }
    }
  }
  Copy-VerifiedTree $sourceDownloads $destinationDownloads 'download/model cache'
  Rewrite-RuntimeManifests
  Verify-InstalledRuntimeNotices

  $storageConfig = [ordered]@{
    schema = 'bossai.video-agent-runtime-storage.v1'
    runtimeRoot = $destinationRuntimes
    downloadRoot = $destinationDownloads
    migratedAt = [DateTimeOffset]::UtcNow.ToString('o')
    sourceRoot = $SourceRoot
  }
  $storageConfig | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $configPath -Encoding UTF8
  Write-Output "BOSSAI_STEP Persisted runtime storage config: $configPath"

  if ($RemoveSourceAfterVerify) {
    Remove-Item -LiteralPath $sourceRuntimes -Recurse -Force
    if (Test-Path -LiteralPath $sourceDownloads -PathType Container) { Remove-Item -LiteralPath $sourceDownloads -Recurse -Force }
    Write-Output 'BOSSAI_STEP Removed verified C-drive runtime/download source trees after migration.'
  } else {
    Write-Output 'BOSSAI_STEP Source trees retained. Re-run with -RemoveSourceAfterVerify after confirming the D-drive runtime works.'
  }
  Write-Output "BOSSAI_DONE Runtime storage migrated to $DestinationRoot"
}
