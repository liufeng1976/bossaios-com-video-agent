[CmdletBinding()]
param(
  [string]$TargetDir = "",
  [string]$DownloadRoot = "",
  [Parameter(Mandatory = $true)][string]$PythonExe,
  [Parameter(Mandatory = $true)][string]$FfmpegExe,
  [string]$ResumeStagingDir = "",
  [string]$ProxyUrl = "",
  [string]$DownloadProxyUrl = "",
  [string]$LocalSeedRoots = "",
  [switch]$AcceptLicense
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Set-StrictMode -Version Latest

if ($ProxyUrl) {
  $env:HTTP_PROXY = $ProxyUrl
  $env:HTTPS_PROXY = $ProxyUrl
  $env:ALL_PROXY = $ProxyUrl
  Write-Output "BOSSAI_STEP HTTP proxy enabled for git/pip: $ProxyUrl"
}
if (-not $DownloadProxyUrl) { $DownloadProxyUrl = $ProxyUrl }
if ($DownloadProxyUrl) { Write-Output "BOSSAI_STEP Download proxy enabled for curl: $DownloadProxyUrl" }
$seedRoots = @()
if ($LocalSeedRoots) {
  $seedRoots = @($LocalSeedRoots.Split(';', [System.StringSplitOptions]::RemoveEmptyEntries) | ForEach-Object { [System.IO.Path]::GetFullPath($_.Trim()) } | Where-Object { Test-Path -LiteralPath $_ -PathType Container })
  if ($seedRoots.Count -gt 0) { Write-Output "BOSSAI_STEP Local verified artifact seed roots enabled: $($seedRoots -join ';')" }
}

if (-not $AcceptLicense) {
  throw 'MuseTalk and all dependency license notices must be reviewed and accepted before installation.'
}

$installerRoot = $PSScriptRoot
$lockPath = Join-Path $installerRoot 'runtime-source-lock.json'
$constraintsPath = Join-Path $installerRoot 'musetalk-constraints.txt'
$requirementsPath = Join-Path $installerRoot 'musetalk-windows-requirements.txt'
if (-not (Test-Path -LiteralPath $lockPath)) { throw "Runtime source lock is missing: $lockPath" }
if (-not (Test-Path -LiteralPath $constraintsPath)) { throw "Pinned MuseTalk constraints are missing: $constraintsPath" }
if (-not (Test-Path -LiteralPath $requirementsPath)) { throw "Pinned MuseTalk Windows inference requirements are missing: $requirementsPath" }

$lock = Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 | ConvertFrom-Json
$muse = $lock.components.musetalk
if (-not $muse) { throw 'MuseTalk source lock is missing.' }

if (-not $TargetDir) {
  if (-not $env:LOCALAPPDATA) { throw 'LOCALAPPDATA is unavailable; pass -TargetDir explicitly.' }
  $TargetDir = Join-Path $env:LOCALAPPDATA 'BossAI\VideoAgent\runtimes\musetalk'
}
$TargetDir = [System.IO.Path]::GetFullPath($TargetDir)
$PythonExe = [System.IO.Path]::GetFullPath($PythonExe)
$FfmpegExe = [System.IO.Path]::GetFullPath($FfmpegExe)
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) { throw "Python 3.10 executable is missing: $PythonExe" }
$existingManifest = Join-Path $TargetDir 'runtime.json'
if (Test-Path -LiteralPath $existingManifest -PathType Leaf) {
  throw "MuseTalk runtime is already installed: $TargetDir"
}
if ($ResumeStagingDir) {
  $InstallDir = [System.IO.Path]::GetFullPath($ResumeStagingDir)
  $expectedPrefix = "$TargetDir.installing-"
  if (-not $InstallDir.StartsWith($expectedPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Resume staging directory must belong to the requested MuseTalk target: $InstallDir"
  }
  if (-not (Test-Path -LiteralPath $InstallDir -PathType Container)) {
    throw "Resume staging directory does not exist: $InstallDir"
  }
  Write-Output "BOSSAI_STEP Resume existing MuseTalk staging: $InstallDir"
} else {
  $InstallDir = "$TargetDir.installing-$([guid]::NewGuid().ToString('N'))"
}
if (-not (Test-Path -LiteralPath $FfmpegExe -PathType Leaf)) { throw "FFmpeg executable is missing: $FfmpegExe" }
$ffmpegLock = $muse.ffmpegRuntime
if (-not $ffmpegLock) { throw 'MuseTalk pinned external FFmpeg profile is missing from source lock.' }
if ([bool]$ffmpegLock.bossaiMayBundle) { throw 'MuseTalk FFmpeg policy must remain external and not bundled by BossAI.' }
$ffmpegHash = (Get-FileHash -LiteralPath $FfmpegExe -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ffmpegHash -ne ([string]$ffmpegLock.expectedExecutableSha256).ToLowerInvariant()) { throw "FFmpeg executable does not match the pinned BossAI external runtime profile: $FfmpegExe" }
$ffmpegVersionLine = (& $FfmpegExe -version 2>&1 | Select-Object -First 1 | Out-String).Trim()
if ($ffmpegVersionLine -notmatch [regex]::Escape([string]$ffmpegLock.version)) { throw "FFmpeg version mismatch. Expected $($ffmpegLock.version): $ffmpegVersionLine" }
$ffmpegBuildConf = (& $FfmpegExe -hide_banner -buildconf 2>&1 | Out-String)
foreach ($requiredFlag in @($ffmpegLock.requiredBuildFlags)) {
  if (-not $ffmpegBuildConf.Contains([string]$requiredFlag)) { throw "FFmpeg required build flag is missing: $requiredFlag" }
}
$ffmpegRoot = Split-Path (Split-Path $FfmpegExe -Parent) -Parent
$ffmpegLicense = Join-Path $ffmpegRoot 'LICENSE'
if (-not (Test-Path -LiteralPath $ffmpegLicense -PathType Leaf)) { throw "Pinned FFmpeg license file is missing: $ffmpegLicense" }
$ffmpegLicenseHash = (Get-FileHash -LiteralPath $ffmpegLicense -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ffmpegLicenseHash -ne ([string]$ffmpegLock.licenseFileSha256).ToLowerInvariant()) { throw "FFmpeg license file does not match the pinned BossAI external runtime profile: $ffmpegLicense" }
$downloadRoot = if ($DownloadRoot) { [System.IO.Path]::GetFullPath($DownloadRoot) } elseif ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA 'BossAI\VideoAgent\downloads' } else { Join-Path ([System.IO.Path]::GetTempPath()) 'BossAI-VideoAgent-Downloads' }
$modelCacheRoot = Join-Path $downloadRoot 'musetalk-model-cache'
New-Item -ItemType Directory -Path $downloadRoot -Force | Out-Null
New-Item -ItemType Directory -Path $modelCacheRoot -Force | Out-Null

$pythonVersion = (& $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" | Select-Object -Last 1).Trim()
if ($LASTEXITCODE -ne 0 -or $pythonVersion -ne '3.10') {
  throw "MuseTalk installer requires Python 3.10. Current interpreter reports: $pythonVersion"
}

function Step([string]$Message) {
  Write-Output ("BOSSAI_STEP " + $Message)
}

function Run([string]$Command, [string[]]$Arguments, [string]$WorkingDirectory = '') {
  Write-Output ("BOSSAI_RUN " + $Command + " " + ($Arguments -join ' '))
  $previous = (Get-Location).Path
  try {
    if ($WorkingDirectory) { Set-Location -LiteralPath $WorkingDirectory }
    & $Command @Arguments
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) { $exitCode = 0 }
    if ($exitCode -ne 0) { throw "Command failed with exit code $exitCode`: $Command" }
  } finally {
    Set-Location -LiteralPath $previous
  }
}

function VerifyHash([string]$FilePath, [string]$Expected) {
  if (-not (Test-Path -LiteralPath $FilePath -PathType Leaf)) { throw "Pinned runtime file is missing: $FilePath" }
  $actual = (Get-FileHash -LiteralPath $FilePath -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -ne $Expected.ToLowerInvariant()) { throw "Pinned runtime hash mismatch: $FilePath" }
}

function DownloadVerified([string]$Url, [string]$Destination, [string]$Expected, [string]$Label) {
  if (Test-Path -LiteralPath $Destination) {
    $destinationItem = Get-Item -LiteralPath $Destination -Force
    if (($destinationItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
      Step "Remove stale reparse-point cache entry for $Label"
      Remove-Item -LiteralPath $Destination -Force
    }
  }
  if (Test-Path -LiteralPath $Destination -PathType Leaf) {
    try { VerifyHash $Destination $Expected; Step "Reuse verified $Label"; return } catch { Step "Resume $Label" }
  } else {
    Step "Download $Label"
  }
  if ($seedRoots.Count -gt 0) {
    try {
      $uri = [System.Uri]$Url
      $seedName = [System.Uri]::UnescapeDataString(($uri.Segments | Select-Object -Last 1))
      foreach ($seedRoot in $seedRoots) {
        $directCandidate = Join-Path $seedRoot $seedName
        $candidates = @()
        if (Test-Path -LiteralPath $directCandidate -PathType Leaf) {
          $candidates += Get-Item -LiteralPath $directCandidate
        }
        if ($candidates.Count -eq 0) {
          $candidates = @(Get-ChildItem -LiteralPath $seedRoot -Recurse -File -Filter $seedName -ErrorAction SilentlyContinue)
        }
        foreach ($candidate in $candidates) {
          try {
            VerifyHash $candidate.FullName $Expected
            $destinationParent = Split-Path -Parent $Destination
            if ($destinationParent -and -not (Test-Path -LiteralPath $destinationParent)) { New-Item -ItemType Directory -Path $destinationParent -Force | Out-Null }
            Copy-Item -LiteralPath $candidate.FullName -Destination $Destination -Force
            VerifyHash $Destination $Expected
            Step "Seeded verified $Label from local artifact: $($candidate.FullName)"
            return
          } catch {}
        }
      }
    } catch {}
  }
  $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
  if (-not $curl) { throw 'curl.exe is required for resumable verified MuseTalk runtime downloads.' }
  $maxAttempts = 80
  for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
    $before = if (Test-Path -LiteralPath $Destination -PathType Leaf) { (Get-Item -LiteralPath $Destination).Length } else { 0 }
    $curlArgs = @('-L','--fail','--continue-at','-','-o',$Destination)
    if ($DownloadProxyUrl) { $curlArgs += @('--proxy',$DownloadProxyUrl) }
    $curlArgs += $Url
    & $curl.Source @curlArgs
    $curlExit = $LASTEXITCODE
    if (Test-Path -LiteralPath $Destination -PathType Leaf) {
      try {
        VerifyHash $Destination $Expected
        Step "Verified $Label after attempt $attempt"
        return
      } catch {
        $after = (Get-Item -LiteralPath $Destination).Length
        Step "Partial $Label attempt=$attempt exit=$curlExit bytes=$after"
        if ($after -le $before -and $curlExit -ne 0) { Start-Sleep -Seconds 2 }
      }
    } else {
      Step "No file produced for $Label attempt=$attempt exit=$curlExit"
      Start-Sleep -Seconds 2
    }
  }
  throw "$Label download did not reach the pinned SHA-256 after $maxAttempts resumable attempts. Partial file was preserved: $Destination"
}

function DownloadHuggingFaceVerified([string]$Repository, [string]$Revision, [string]$SourcePath, [string]$Destination, [string]$Expected, [string]$Label) {
  $sourceUrlPath = (($SourcePath.Replace('\\','/').Split('/')) | ForEach-Object { [System.Uri]::EscapeDataString($_) }) -join '/'
  $url = "https://huggingface.co/$Repository/resolve/$Revision/${sourceUrlPath}?download=true"
  Step "Use pinned Hugging Face revision with resumable HTTPS for $Label"
  DownloadVerified $url $Destination $Expected $Label
}

function Commit-Install([string]$StagingDir, [string]$FinalDir) {
  $parent = Split-Path -Parent $FinalDir
  if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
  $quarantine = ''
  if (Test-Path -LiteralPath $FinalDir) {
    if (Test-Path -LiteralPath (Join-Path $FinalDir 'runtime.json') -PathType Leaf) {
      throw "Refusing to replace an installed MuseTalk runtime: $FinalDir"
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

$installMutex = [System.Threading.Mutex]::new($false, 'BossAIVideoAgent-MuseTalk-Install')
$installMutexAcquired = $false
try {
  try { $installMutexAcquired = $installMutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $installMutexAcquired = $true }
  if (-not $installMutexAcquired) { throw 'Another BossAI MuseTalk installation is already running.' }
  New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
$repoDir = Join-Path $InstallDir 'MuseTalk'
$venvDir = Join-Path $InstallDir 'venv'
$venvPython = Join-Path $venvDir 'Scripts\python.exe'
$venvHf = Join-Path $venvDir 'Scripts\hf.exe'
$licensesDir = Join-Path $InstallDir 'licenses'
$torchHome = Join-Path $InstallDir 'torch-cache'
$env:TORCH_HOME = $torchHome

Step 'Fetch pinned official MuseTalk source'
if (-not (Test-Path -LiteralPath (Join-Path $repoDir '.git'))) {
  Run 'git.exe' @('clone', '--filter=blob:none', '--no-checkout', [string]$muse.sourceRepository, $repoDir)
} else {
  $dirty = @(& git.exe -C $repoDir status --porcelain --untracked-files=all)
  if ($LASTEXITCODE -ne 0) { throw 'Unable to inspect the existing MuseTalk repository.' }
  $unexpectedDirty = @($dirty | Where-Object {
    $_ -and
    $_ -notmatch '^\?\? models/' -and
    $_ -ne '?? musetalk/utils/face_detection/detection/sfd/s3fd.pth'
  })
  if ($unexpectedDirty.Count -gt 0) {
    throw "Existing MuseTalk repository contains source or unexpected local modifications; refusing to overwrite it: $($unexpectedDirty -join '; ')"
  }
  if ($dirty.Count -gt 0) { Step 'Reuse installer-owned untracked MuseTalk runtime artifacts while preserving source-integrity checks' }
}
Run 'git.exe' @('fetch', '--depth', '1', 'origin', [string]$muse.sourceRevision) $repoDir
Step 'Restrict MuseTalk checkout to inference source only; exclude upstream demo/test/training media'
Run 'git.exe' @('sparse-checkout', 'init', '--no-cone') $repoDir
Run 'git.exe' @('sparse-checkout', 'set', '--no-cone', '/LICENSE', '/musetalk/', '/scripts/') $repoDir
Run 'git.exe' @('checkout', '--detach', [string]$muse.sourceRevision) $repoDir
$installedCommit = (& git.exe -C $repoDir rev-parse HEAD).Trim()
if ($installedCommit -ne [string]$muse.sourceRevision) { throw 'MuseTalk source revision verification failed.' }
foreach ($forbiddenRelative in @('assets', 'data', 'app.py', 'train.py', 'train.sh')) {
  if (Test-Path -LiteralPath (Join-Path $repoDir $forbiddenRelative)) {
    throw "MuseTalk sparse checkout unexpectedly contains upstream demo/training content: $forbiddenRelative"
  }
}

Step 'Create isolated Python 3.10 environment'
if (-not (Test-Path -LiteralPath $venvPython)) { Run $PythonExe @('-m', 'venv', $venvDir) }
Run $venvPython @('-m', 'pip', 'install', 'pip==25.1.1', 'setuptools==80.9.0', 'wheel==0.45.1')
$torchRuntime = $muse.torchRuntime
if (-not $torchRuntime) { throw 'MuseTalk pinned Torch runtime is missing from source lock.' }
$torchWheel = Join-Path $downloadRoot 'torch-2.0.1+cu118-cp310-cp310-win_amd64.whl'
$torchvisionWheel = Join-Path $downloadRoot 'torchvision-0.15.2+cu118-cp310-cp310-win_amd64.whl'
$torchaudioWheel = Join-Path $downloadRoot 'torchaudio-2.0.2+cu118-cp310-cp310-win_amd64.whl'
DownloadVerified ([string]$torchRuntime.torch.url) $torchWheel ([string]$torchRuntime.torch.sha256) 'MuseTalk PyTorch cu118 wheel'
DownloadVerified ([string]$torchRuntime.torchvision.url) $torchvisionWheel ([string]$torchRuntime.torchvision.sha256) 'MuseTalk TorchVision cu118 wheel'
DownloadVerified ([string]$torchRuntime.torchaudio.url) $torchaudioWheel ([string]$torchRuntime.torchaudio.sha256) 'MuseTalk TorchAudio cu118 wheel'
& $venvPython -c "from importlib.metadata import version; import sys; expected={'torch':'2.0.1+cu118','torchvision':'0.15.2+cu118','torchaudio':'2.0.2+cu118'}; ok=True; exec('for k,v in expected.items():\n    try:\n        ok = ok and (version(k) == v)\n    except Exception:\n        ok = False'); sys.exit(0 if ok else 1)"
$torchEnvReady = ($LASTEXITCODE -eq 0)
if ($torchEnvReady) {
  Step 'Reuse exact MuseTalk Torch/TorchVision/TorchAudio environment'
} else {
  Run $venvPython @('-m', 'pip', 'install', '--force-reinstall', '--constraint', $constraintsPath, '--constraint', $requirementsPath, $torchWheel, $torchvisionWheel, $torchaudioWheel)
}

Step 'Preseed pinned heavy MuseTalk Python wheels through verified download cache'
$pinnedPythonWheels = $muse.pinnedPythonWheels
if (-not $pinnedPythonWheels) { throw 'MuseTalk pinned Python wheel lock is missing.' }
$pythonWheelCacheRoot = Join-Path $downloadRoot 'musetalk-python-wheels'
New-Item -ItemType Directory -Path $pythonWheelCacheRoot -Force | Out-Null
$heavyWheelPaths = @()
foreach ($wheelName in @('llvmlite','scipy','scikitLearn')) {
  $wheelLock = $pinnedPythonWheels.$wheelName
  if (-not $wheelLock) { throw "MuseTalk pinned Python wheel is missing: $wheelName" }
  $wheelTarget = Join-Path $pythonWheelCacheRoot ([string]$wheelLock.filename)
  DownloadVerified ([string]$wheelLock.url) $wheelTarget ([string]$wheelLock.sha256) "MuseTalk pinned Python wheel $wheelName"
  $heavyWheelPaths += $wheelTarget
}
Run $venvPython (@('-m', 'pip', 'install', '--no-deps', '--constraint', $constraintsPath) + $heavyWheelPaths)
Run $venvPython @('-m', 'pip', 'install', '--constraint', $constraintsPath, '-r', $requirementsPath)
$xetRuntime = $muse.huggingFaceXetRuntime
if (-not $xetRuntime) { throw 'MuseTalk pinned Hugging Face Xet runtime lock is missing.' }
$xetWheel = Join-Path $pythonWheelCacheRoot ([string]$xetRuntime.filename)
DownloadVerified ([string]$xetRuntime.url) $xetWheel ([string]$xetRuntime.sha256) 'MuseTalk pinned Hugging Face Xet Windows wheel'
Run $venvPython @('-m', 'pip', 'install', '--no-deps', '--constraint', $constraintsPath, $xetWheel)
$hfHome = Join-Path $downloadRoot 'huggingface'
$hfCacheRoot = Join-Path $hfHome 'hub'
$env:HF_HOME = $hfHome
$env:HF_XET_CACHE = Join-Path $hfHome 'xet'
$env:HF_XET_HIGH_PERFORMANCE = '0'
$env:HF_XET_NUM_CONCURRENT_RANGE_GETS = '4'
$env:HF_XET_CHUNK_CACHE_SIZE_BYTES = '2000000000'
New-Item -ItemType Directory -Path $hfCacheRoot -Force | Out-Null
Step "Hugging Face Xet acceleration enabled with pinned hf_xet $([string]$xetRuntime.version)"
$openMmlab = $muse.openMmlabRuntime
if (-not $openMmlab -or -not $openMmlab.mmcvWheel) { throw 'MuseTalk pinned OpenMMLab runtime lock is missing.' }
$mmcvWheel = Join-Path $pythonWheelCacheRoot ([string]$openMmlab.mmcvWheel.filename)
DownloadVerified ([string]$openMmlab.mmcvWheel.url) $mmcvWheel ([string]$openMmlab.mmcvWheel.sha256) 'MuseTalk pinned MMCV Windows wheel'
& $venvPython -c "from importlib.metadata import version; import sys; expected={'mmengine':'0.10.7','mmcv':'2.0.1','mmdet':'3.1.0','mmpose':'1.1.0'}; ok=True; exec('for k,v in expected.items():\n    try:\n        ok = ok and (version(k) == v)\n    except Exception:\n        ok = False'); sys.exit(0 if ok else 1)"
$openMmlabReady = ($LASTEXITCODE -eq 0)
if ($openMmlabReady) {
  Step 'Reuse exact MuseTalk OpenMMLab environment'
} else {
  Step 'Install pinned MuseTalk OpenMMLab runtime without openmim/opendatalab tooling'
  Run $venvPython @('-m', 'pip', 'install', '--constraint', $constraintsPath, "mmengine==$([string]$openMmlab.mmengineVersion)")
  Run $venvPython @('-m', 'pip', 'install', '--no-deps', $mmcvWheel)
  Run $venvPython @('-m', 'pip', 'install', '--constraint', $constraintsPath, "mmdet==$([string]$openMmlab.mmdetVersion)", "mmpose==$([string]$openMmlab.mmposeVersion)")
}

$modelsDir = Join-Path $repoDir 'models'
New-Item -ItemType Directory -Path $modelsDir -Force | Out-Null

Step 'Preseed pinned hidden runtime artifacts to prevent inference-time downloads'
$implicitArtifacts = $muse.implicitRuntimeArtifacts
if (-not $implicitArtifacts) { throw 'MuseTalk implicit runtime artifact lock is missing.' }
$s3fdLock = $implicitArtifacts.s3fdFaceDetector
$dwposeBackboneLock = $implicitArtifacts.dwposeBackbone
if (-not $s3fdLock -or -not $dwposeBackboneLock) { throw 'MuseTalk hidden runtime artifact lock is incomplete.' }
$s3fdCache = Join-Path $modelCacheRoot (([string]$s3fdLock.sha256).ToLowerInvariant() + '-s3fd.pth')
DownloadVerified ([string]$s3fdLock.url) $s3fdCache ([string]$s3fdLock.sha256) 'MuseTalk cached S3FD face detector weight'
$s3fdTarget = Join-Path $InstallDir ([string]$s3fdLock.destination).Replace('/','\')
$s3fdParent = Split-Path -Parent $s3fdTarget
if (-not (Test-Path -LiteralPath $s3fdParent)) { New-Item -ItemType Directory -Path $s3fdParent -Force | Out-Null }
if (-not (Test-Path -LiteralPath $s3fdTarget -PathType Leaf)) {
  try { New-Item -ItemType HardLink -Path $s3fdTarget -Target $s3fdCache -ErrorAction Stop | Out-Null } catch { Copy-Item -LiteralPath $s3fdCache -Destination $s3fdTarget -Force }
}
VerifyHash $s3fdTarget ([string]$s3fdLock.sha256)
$dwposeBackboneCache = Join-Path $modelCacheRoot (([string]$dwposeBackboneLock.sha256).ToLowerInvariant() + '-cspnext-l.pth')
DownloadVerified ([string]$dwposeBackboneLock.url) $dwposeBackboneCache ([string]$dwposeBackboneLock.sha256) 'MuseTalk cached DWPose pretrained backbone'
$dwposeBackboneTarget = Join-Path $InstallDir ([string]$dwposeBackboneLock.destination).Replace('/','\')
$dwposeBackboneParent = Split-Path -Parent $dwposeBackboneTarget
if (-not (Test-Path -LiteralPath $dwposeBackboneParent)) { New-Item -ItemType Directory -Path $dwposeBackboneParent -Force | Out-Null }
if (-not (Test-Path -LiteralPath $dwposeBackboneTarget -PathType Leaf)) {
  try { New-Item -ItemType HardLink -Path $dwposeBackboneTarget -Target $dwposeBackboneCache -ErrorAction Stop | Out-Null } catch { Copy-Item -LiteralPath $dwposeBackboneCache -Destination $dwposeBackboneTarget -Force }
}
VerifyHash $dwposeBackboneTarget ([string]$dwposeBackboneLock.sha256)

Step 'Download only pinned MuseTalk inference artifacts'
$deps = $muse.dependencyModelRevisions
$modelArtifacts = @(
  [ordered]@{ repository='TMElyralab/MuseTalk'; revision=[string]$muse.modelRevision; source='musetalkV15/musetalk.json'; destination='models/musetalkV15/musetalk.json' },
  [ordered]@{ repository='TMElyralab/MuseTalk'; revision=[string]$muse.modelRevision; source='musetalkV15/unet.pth'; destination='models/musetalkV15/unet.pth' },
  [ordered]@{ repository='stabilityai/sd-vae-ft-mse'; revision=[string]$deps.'stabilityai/sd-vae-ft-mse'; source='config.json'; destination='models/sd-vae/config.json' },
  [ordered]@{ repository='stabilityai/sd-vae-ft-mse'; revision=[string]$deps.'stabilityai/sd-vae-ft-mse'; source='diffusion_pytorch_model.bin'; destination='models/sd-vae/diffusion_pytorch_model.bin' },
  [ordered]@{ repository='openai/whisper-tiny'; revision=[string]$deps.'openai/whisper-tiny'; source='config.json'; destination='models/whisper/config.json' },
  [ordered]@{ repository='openai/whisper-tiny'; revision=[string]$deps.'openai/whisper-tiny'; source='pytorch_model.bin'; destination='models/whisper/pytorch_model.bin' },
  [ordered]@{ repository='openai/whisper-tiny'; revision=[string]$deps.'openai/whisper-tiny'; source='preprocessor_config.json'; destination='models/whisper/preprocessor_config.json' },
  [ordered]@{ repository='yzd-v/DWPose'; revision=[string]$deps.'yzd-v/DWPose'; source='dw-ll_ucoco_384.pth'; destination='models/dwpose/dw-ll_ucoco_384.pth' },
  [ordered]@{ repository='ByteDance/LatentSync'; revision=[string]$deps.'ByteDance/LatentSync'; source='latentsync_syncnet.pt'; destination='models/syncnet/latentsync_syncnet.pt' },
  [ordered]@{ repository='ManyOtherFunctions/face-parse-bisent'; revision=[string]$deps.'ManyOtherFunctions/face-parse-bisent'; source='79999_iter.pth'; destination='models/face-parse-bisent/79999_iter.pth' },
  [ordered]@{ repository='ManyOtherFunctions/face-parse-bisent'; revision=[string]$deps.'ManyOtherFunctions/face-parse-bisent'; source='resnet18-5c106cde.pth'; destination='models/face-parse-bisent/resnet18-5c106cde.pth' }
)
foreach ($artifact in $modelArtifacts) {
  $hashProperty = $muse.verifiedHashes.PSObject.Properties | Where-Object { $_.Name -eq [string]$artifact.destination } | Select-Object -First 1
  if (-not $hashProperty) { throw "MuseTalk verified hash is missing for: $($artifact.destination)" }
  $expectedHash = ([string]$hashProperty.Value).ToLowerInvariant()
  $sourcePath = ([string]$artifact.source).Replace('\\','/')
  $cacheFile = Join-Path $modelCacheRoot ($expectedHash + '-' + [System.IO.Path]::GetFileName([string]$artifact.source))
  $destination = Join-Path $repoDir ([string]$artifact.destination).Replace('/','\\')
  $destinationParent = Split-Path -Parent $destination
  if (-not (Test-Path -LiteralPath $destinationParent)) { New-Item -ItemType Directory -Path $destinationParent -Force | Out-Null }
  if (Test-Path -LiteralPath $destination -PathType Leaf) {
    try { VerifyHash $destination $expectedHash; Step "Reuse staged MuseTalk model file $($artifact.destination)"; continue } catch { Remove-Item -LiteralPath $destination -Force }
  }
  DownloadHuggingFaceVerified ([string]$artifact.repository) ([string]$artifact.revision) $sourcePath $cacheFile $expectedHash "MuseTalk cached model file $($artifact.destination)"
  try {
    New-Item -ItemType HardLink -Path $destination -Target $cacheFile -ErrorAction Stop | Out-Null
    Step "Hard-linked verified MuseTalk model file $($artifact.destination) from global cache"
  } catch {
    Copy-Item -LiteralPath $cacheFile -Destination $destination -Force
    Step "Copied verified MuseTalk model file $($artifact.destination) from global cache"
  }
  VerifyHash $destination $expectedHash
}

Step 'Verify pinned model hashes'
foreach ($property in $muse.verifiedHashes.PSObject.Properties) {
  VerifyHash (Join-Path $repoDir ([string]$property.Name).Replace('/', '\')) ([string]$property.Value)
}

Step 'Verify CUDA runtime'
Run $venvPython @('-c', "import torch; assert torch.cuda.is_available(), 'CUDA unavailable'; print(torch.cuda.get_device_name(0))")

Step 'Persist provenance and runtime manifest'
New-Item -ItemType Directory -Path $licensesDir -Force | Out-Null
$sourceLicense = Join-Path $repoDir 'LICENSE'
if (Test-Path -LiteralPath $sourceLicense) { Copy-Item -LiteralPath $sourceLicense -Destination (Join-Path $licensesDir 'MuseTalk-LICENSE.txt') -Force }
Copy-Item -LiteralPath $ffmpegLicense -Destination (Join-Path $licensesDir 'FFmpeg-GPL-3.0-LICENSE.txt') -Force

Step 'Capture pinned MuseTalk and dependency-model license texts'
$modelLicenseRecords = @()
foreach ($licenseItem in @($muse.modelLicenseEvidence)) {
  $filename = [string]$licenseItem.filename
  if (-not $filename -or [System.IO.Path]::GetFileName($filename) -ne $filename) { throw "Invalid MuseTalk model license filename: $filename" }
  $licenseTarget = Join-Path $licensesDir $filename
  DownloadVerified ([string]$licenseItem.url) $licenseTarget ([string]$licenseItem.sha256) "MuseTalk model license $($licenseItem.id)"
  $modelLicenseRecords += [ordered]@{
    id = [string]$licenseItem.id
    repository = [string]$licenseItem.repository
    revision = [string]$licenseItem.revision
    declaredLicense = [string]$licenseItem.declaredLicense
    path = "licenses/$filename"
    sha256 = [string]$licenseItem.sha256
    sourceUrl = [string]$licenseItem.url
  }
}
$modelLicenseReport = [ordered]@{
  schema = 'bossai.video-agent-model-license-evidence.v1'
  component = 'musetalk'
  complete = ($modelLicenseRecords.Count -eq @($muse.modelLicenseEvidence).Count -and $modelLicenseRecords.Count -gt 0)
  sourceLicense = [string]$muse.sourceLicense
  trainedModelDeclaredLicense = [string]$muse.trainedModelDeclaredLicense
  items = @($modelLicenseRecords)
}
if (-not $modelLicenseReport.complete) { throw 'MuseTalk model license evidence is incomplete.' }
$modelLicenseReport | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $licensesDir 'model-license-evidence.json') -Encoding UTF8

Step 'Capture pinned MuseTalk Python license supplements'
$supplementDir = Join-Path $licensesDir 'supplemental-python'
New-Item -ItemType Directory -Path $supplementDir -Force | Out-Null
$supplementEntries = @()
foreach ($supplement in @($muse.supplementalPythonLicenses)) {
  $packageName = [string]$supplement.package
  $packageVersion = [string]$supplement.version
  $safePackage = ($packageName -replace '[^A-Za-z0-9._-]+','-')
  $safeVersion = ($packageVersion -replace '[^A-Za-z0-9._-]+','-')
  $safeFile = ([string]$supplement.filename -replace '[^A-Za-z0-9._-]+','-')
  $supplementFileName = "$safePackage-$safeVersion-$safeFile"
  $supplementPath = Join-Path $supplementDir $supplementFileName
  DownloadVerified ([string]$supplement.url) $supplementPath ([string]$supplement.sha256) "Python license supplement $packageName==$packageVersion"
  $supplementEntries += [ordered]@{
    name = $packageName
    version = $packageVersion
    license = [string]$supplement.license
    path = "supplemental-python/$supplementFileName"
    sourceUrl = [string]$supplement.url
    sha256 = [string]$supplement.sha256
  }
}
$supplementManifestPath = Join-Path $licensesDir 'python-license-supplements.json'
[ordered]@{
  schema = 'bossai.video-agent-python-license-supplements.v1'
  component = 'musetalk'
  entries = $supplementEntries
} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $supplementManifestPath -Encoding UTF8

$captureNotices = Join-Path (Split-Path -Parent $PSScriptRoot) 'legal\capture-python-runtime-notices.py'
if (-not (Test-Path -LiteralPath $captureNotices -PathType Leaf)) { throw "BossAI runtime notice capture tool is missing: $captureNotices" }
Run $venvPython @($captureNotices,'--component','musetalk','--out',$licensesDir,'--supplemental-license-manifest',$supplementManifestPath,'--require-complete')

$runtimeManifest = [ordered]@{
  schema = 'bossai.video-agent-installed-runtime.v1'
  component = 'musetalk'
  installedAt = [DateTimeOffset]::UtcNow.ToString('o')
  source = [ordered]@{
    repository = [string]$muse.sourceRepository
    revision = [string]$muse.sourceRevision
    modelRepository = [string]$muse.modelRepository
    modelRevision = [string]$muse.modelRevision
    sourceLicense = [string]$muse.sourceLicense
    trainedModelDeclaredLicense = [string]$muse.trainedModelDeclaredLicense
    ffmpeg = [ordered]@{
      distributionMode = [string]$ffmpegLock.distributionMode
      packageId = [string]$ffmpegLock.packageId
      version = [string]$ffmpegLock.version
      upstreamSourceRevision = [string]$ffmpegLock.upstreamSourceRevision
      executableSha256 = $ffmpegHash
      license = [string]$ffmpegLock.license
      bundledByBossAI = $false
    }
  }
  licenseEvidence = 'licenses/python-dependency-notices.json'
  supplementalLicenseEvidence = 'licenses/python-license-supplements.json'
  modelLicenseEvidence = 'licenses/model-license-evidence.json'
  env = [ordered]@{
    BOSSAI_MUSETALK_ROOT = (Join-Path $TargetDir 'MuseTalk')
    BOSSAI_MUSETALK_PYTHON = (Join-Path $TargetDir 'venv\Scripts\python.exe')
    BOSSAI_FFMPEG_BIN = $FfmpegExe
    TORCH_HOME = (Join-Path $TargetDir 'torch-cache')
  }
  rights = [ordered]@{
    avatar = 'customer-authorized-or-bossai-owned-only'
    audio = 'customer-authorized-or-bossai-owned-only'
    upstreamTestDataMayShip = $false
  }
}
$runtimeManifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $InstallDir 'runtime.json') -Encoding UTF8
Commit-Install $InstallDir $TargetDir

Write-Output 'BOSSAI_DONE MuseTalk runtime installed from pinned official sources.'
} catch {
  if (Test-Path -LiteralPath $InstallDir) {
    Write-Output "BOSSAI_STEP Installation failed; preserving staging for diagnosis and resumable recovery: $InstallDir"
  }
  throw
} finally {
  if ($installMutexAcquired) {
    try { $installMutex.ReleaseMutex() } catch { }
  }
  $installMutex.Dispose()
}
