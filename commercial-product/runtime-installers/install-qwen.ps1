[CmdletBinding()]
param(
  [string]$TargetDir = "",
  [string]$DownloadRoot = "",
  [ValidateSet('gpu','cpu')][string]$Profile = 'gpu',
  [string]$ModelSourceDir = "",
  [string]$LlamaZipSource = "",
  [switch]$AcceptLicense
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Set-StrictMode -Version Latest

if (-not $AcceptLicense) { throw 'Qwen and llama.cpp license notices must be reviewed and accepted before installation.' }
$lockPath = Join-Path $PSScriptRoot 'runtime-source-lock.json'
$lock = Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 | ConvertFrom-Json
$qwen = $lock.components.'qwen2.5-7b-instruct'
if (-not $qwen) { throw 'Qwen source lock is missing.' }
$llama = $qwen.inferenceRuntime
if (-not $llama) { throw 'Pinned llama.cpp inference runtime is missing from source lock.' }

if (-not $TargetDir) {
  if (-not $env:LOCALAPPDATA) { throw 'LOCALAPPDATA is unavailable; pass -TargetDir explicitly.' }
  $TargetDir = Join-Path $env:LOCALAPPDATA 'BossAI\VideoAgent\runtimes\qwen2.5-7b-instruct'
}
$TargetDir = [System.IO.Path]::GetFullPath($TargetDir)
$existingManifest = Join-Path $TargetDir 'runtime.json'
if (Test-Path -LiteralPath $existingManifest -PathType Leaf) { throw "Qwen runtime is already installed: $TargetDir" }
$InstallDir = "$TargetDir.installing-$([guid]::NewGuid().ToString('N'))"
$downloadRoot = if ($DownloadRoot) { [System.IO.Path]::GetFullPath($DownloadRoot) } elseif ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA 'BossAI\VideoAgent\downloads' } else { Join-Path ([System.IO.Path]::GetTempPath()) 'BossAI-VideoAgent-Downloads' }
New-Item -ItemType Directory -Path $downloadRoot -Force | Out-Null

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
    if (Test-Path -LiteralPath (Join-Path $FinalDir 'runtime.json') -PathType Leaf) { throw "Refusing to replace an installed Qwen runtime: $FinalDir" }
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

New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
try {
  $runtimeDir = Join-Path $InstallDir 'llama.cpp'
  $modelDir = Join-Path $InstallDir 'model'
  $licensesDir = Join-Path $InstallDir 'licenses'
  New-Item -ItemType Directory -Path $runtimeDir,$modelDir,$licensesDir -Force | Out-Null

  $zipPath = if ($LlamaZipSource) { [System.IO.Path]::GetFullPath($LlamaZipSource) } else { Join-Path $downloadRoot ([string]$llama.artifact) }
  if ($LlamaZipSource) { Verify-Hash $zipPath ([string]$llama.sha256) 'llama.cpp Vulkan runtime' }
  else { Download-Verified ([string]$llama.url) $zipPath ([string]$llama.sha256) 'llama.cpp Vulkan runtime' }
  Expand-Archive -LiteralPath $zipPath -DestinationPath $runtimeDir -Force
  $serverExe = Get-ChildItem -LiteralPath $runtimeDir -Recurse -File -Filter 'llama-server.exe' | Select-Object -First 1
  if (-not $serverExe) { throw 'Pinned llama.cpp package does not contain llama-server.exe.' }
  $previousPreference = $ErrorActionPreference
  try {
    $ErrorActionPreference = 'Continue'
    $versionText = (& $serverExe.FullName --version 2>&1 | Out-String)
    $versionExitCode = $LASTEXITCODE
  } finally { $ErrorActionPreference = $previousPreference }
  $expectedBuild = ([string]$llama.release).TrimStart('b')
  if ($versionExitCode -ne 0 -or $versionText -notmatch ("build\s+" + [regex]::Escape($expectedBuild)) -or $versionText -notmatch [regex]::Escape([string]$llama.commit)) { throw "llama.cpp release verification failed: $versionText" }

  $fileEntries = @($qwen.files)
  if ($fileEntries.Count -ne 2) { throw 'Pinned Qwen Q4_K_M split file set is invalid.' }
  foreach ($entry in $fileEntries) {
    $name = [string]$entry.name
    $sha = [string]$entry.sha256
    if (-not $name -or -not $sha) { throw 'Pinned Qwen file metadata is incomplete.' }
    $target = Join-Path $modelDir $name
    if ($ModelSourceDir) {
      $source = Join-Path ([System.IO.Path]::GetFullPath($ModelSourceDir)) $name
      Verify-Hash $source $sha "Qwen model shard $name"
      Copy-Item -LiteralPath $source -Destination $target
      Verify-Hash $target $sha "Qwen copied model shard $name"
    } else {
      $encodedName = [Uri]::EscapeDataString($name)
      $url = "https://huggingface.co/$([string]$qwen.repository)/resolve/$([string]$qwen.revision)/$encodedName?download=true"
      $cached = Join-Path $downloadRoot $name
      Download-Verified $url $cached $sha "Qwen model shard $name"
      Copy-Item -LiteralPath $cached -Destination $target
      Verify-Hash $target $sha "Qwen installed model shard $name"
    }
  }

  $modelEntry = Join-Path $modelDir ([string]$fileEntries[0].name)
  $previousPreference = $ErrorActionPreference
  try {
    $ErrorActionPreference = 'Continue'
    $probe = (& $serverExe.FullName --version 2>&1 | Out-String)
    $probeExitCode = $LASTEXITCODE
  } finally { $ErrorActionPreference = $previousPreference }
  if ($probeExitCode -ne 0 -or $probe -notmatch 'build 10516') { throw "Qwen llama.cpp probe failed: $probe" }

  $llamaLicense = Join-Path $licensesDir 'llama.cpp-LICENSE.txt'
  Invoke-WebRequest -Uri "https://raw.githubusercontent.com/ggml-org/llama.cpp/$([string]$llama.commit)/LICENSE" -OutFile $llamaLicense -UseBasicParsing
  $qwenLicense = Join-Path $licensesDir 'Qwen-LICENSE.txt'
  Invoke-WebRequest -Uri "https://huggingface.co/$([string]$qwen.repository)/resolve/$([string]$qwen.revision)/LICENSE?download=true" -OutFile $qwenLicense -UseBasicParsing
  if (-not (Test-Path -LiteralPath $llamaLicense -PathType Leaf) -or -not (Test-Path -LiteralPath $qwenLicense -PathType Leaf)) { throw 'Qwen/llama.cpp license evidence download failed.' }

  $gpuLayers = if ($Profile -eq 'gpu') { [int]$llama.defaultGpuLayers } else { 0 }
  $runtimeManifest = [ordered]@{
    schema = 'bossai.video-agent-installed-runtime.v2'
    component = 'qwen2.5-7b-instruct'
    installedAt = [DateTimeOffset]::UtcNow.ToString('o')
    source = [ordered]@{ repository=[string]$qwen.repository; revision=[string]$qwen.revision; variant=[string]$qwen.variant }
    inference = [ordered]@{ project=[string]$llama.project; release=[string]$llama.release; commit=[string]$llama.commit; backend='vulkan'; gpuLayers=$gpuLayers }
    licenseEvidence = @('licenses/Qwen-LICENSE.txt','licenses/llama.cpp-LICENSE.txt')
    files = @($fileEntries | ForEach-Object {
      $path = Join-Path $modelDir ([string]$_.name)
      [ordered]@{ name=[string]$_.name; bytes=(Get-Item -LiteralPath $path).Length; sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() }
    })
    env = [ordered]@{
      BOSSAI_QWEN_MODEL=(Join-Path $TargetDir ('model\\' + [string]$fileEntries[0].name))
      BOSSAI_QWEN_SERVER=(Join-Path $TargetDir ('llama.cpp\\' + $serverExe.Name))
      BOSSAI_QWEN_GPU_LAYERS=[string]$gpuLayers
    }
  }
  $runtimeManifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $InstallDir 'runtime.json') -Encoding UTF8
  Commit-Install $InstallDir $TargetDir
  Write-Output 'BOSSAI_DONE Qwen runtime installed from pinned Qwen + llama.cpp official sources.'
} catch {
  if (Test-Path -LiteralPath $InstallDir) { Remove-Item -LiteralPath $InstallDir -Recurse -Force -ErrorAction SilentlyContinue }
  throw
}
