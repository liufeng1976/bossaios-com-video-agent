[CmdletBinding()]
param(
  [string]$TargetDir = "",
  [string]$DownloadRoot = "",
  [Parameter(Mandatory = $true)][string]$PythonExe,
  [ValidateSet('cu121','cu118','cpu')][string]$TorchFlavor = 'cu121',
  [string]$ModelSourceDir = "",
  [string]$ResumeStagingDir = "",
  [string]$ProxyUrl = "",
  [string]$DownloadProxyUrl = "",
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

if (-not $AcceptLicense) { throw 'CosyVoice and model license notices must be reviewed and accepted before installation.' }
$lockPath = Join-Path $PSScriptRoot 'runtime-source-lock.json'
$lock = Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 | ConvertFrom-Json
$cosy = $lock.components.'cosyvoice2-0.5b'
if (-not $cosy) { throw 'CosyVoice2 source lock is missing.' }

if (-not $TargetDir) {
  if (-not $env:LOCALAPPDATA) { throw 'LOCALAPPDATA is unavailable; pass -TargetDir explicitly.' }
  $TargetDir = Join-Path $env:LOCALAPPDATA 'BossAI\VideoAgent\runtimes\cosyvoice2-0.5b'
}
$TargetDir = [System.IO.Path]::GetFullPath($TargetDir)
$PythonExe = [System.IO.Path]::GetFullPath($PythonExe)
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) { throw "Python 3.10 executable is missing: $PythonExe" }
$existingManifest = Join-Path $TargetDir 'runtime.json'
if (Test-Path -LiteralPath $existingManifest -PathType Leaf) {
  throw "CosyVoice2 runtime is already installed: $TargetDir"
}
if ($ResumeStagingDir) {
  $InstallDir = [System.IO.Path]::GetFullPath($ResumeStagingDir)
  $expectedPrefix = "$TargetDir.installing-"
  if (-not $InstallDir.StartsWith($expectedPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Resume staging directory is outside the expected CosyVoice2 install prefix: $InstallDir"
  }
  if (-not (Test-Path -LiteralPath $InstallDir -PathType Container)) {
    throw "Resume staging directory does not exist: $InstallDir"
  }
  if (Test-Path -LiteralPath (Join-Path $InstallDir 'runtime.json') -PathType Leaf) {
    throw "Resume staging directory already contains runtime.json; refusing ambiguous promotion: $InstallDir"
  }
  Write-Output "BOSSAI_STEP Resume staging $InstallDir"
} else {
  $InstallDir = "$TargetDir.installing-$([guid]::NewGuid().ToString('N'))"
}
$downloadRoot = if ($DownloadRoot) { [System.IO.Path]::GetFullPath($DownloadRoot) } elseif ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA 'BossAI\VideoAgent\downloads' } else { Join-Path ([System.IO.Path]::GetTempPath()) 'BossAI-VideoAgent-Downloads' }
New-Item -ItemType Directory -Path $downloadRoot -Force | Out-Null
$pythonVersion = (& $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" | Select-Object -Last 1).Trim()
if ($LASTEXITCODE -ne 0 -or $pythonVersion -ne '3.10') { throw "CosyVoice2 runtime requires Python 3.10. Current: $pythonVersion" }

function Run([string]$Command, [string[]]$Arguments, [string]$WorkingDirectory = '') {
  Write-Output ("BOSSAI_RUN " + $Command + " " + ($Arguments -join ' '))
  $previous = (Get-Location).Path
  try {
    if ($WorkingDirectory) { Set-Location -LiteralPath $WorkingDirectory }
    & $Command @Arguments
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) { $exitCode = 0 }
    if ($exitCode -ne 0) { throw "Command failed with exit code $exitCode`: $Command" }
  } finally { Set-Location -LiteralPath $previous }
}

function Verify-Hash([string]$Path, [string]$Expected, [string]$Label) {
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "$Label is missing: $Path" }
  $actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -ne ([string]$Expected).ToLowerInvariant()) { throw "$Label SHA-256 mismatch. Expected $Expected, got $actual" }
}

function Download-Verified([string]$Url, [string]$Destination, [string]$ExpectedHash, [string]$Label) {
  if (Test-Path -LiteralPath $Destination -PathType Leaf) {
    try { Verify-Hash $Destination $ExpectedHash $Label; Write-Output "BOSSAI_STEP Reuse verified $Label"; return } catch { Write-Output "BOSSAI_STEP Resume $Label" }
  } else {
    Write-Output "BOSSAI_STEP Download $Label"
  }
  $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
  if (-not $curl) {
    Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing
    Verify-Hash $Destination $ExpectedHash $Label
    return
  }

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
        Verify-Hash $Destination $ExpectedHash $Label
        Write-Output "BOSSAI_STEP Verified $Label after attempt $attempt"
        return
      } catch {
        $after = (Get-Item -LiteralPath $Destination).Length
        Write-Output "BOSSAI_STEP Partial $Label attempt=$attempt exit=$curlExit bytes=$after"
        if ($after -le $before -and $curlExit -ne 0) { Start-Sleep -Seconds 2 }
      }
    } else {
      Write-Output "BOSSAI_STEP No file produced for $Label attempt=$attempt exit=$curlExit"
      Start-Sleep -Seconds 2
    }
  }
  throw "$Label download did not reach the pinned SHA-256 after $maxAttempts resumable attempts. Partial file was preserved: $Destination"
}

function Expand-SingleRootArchive([string]$ArchivePath, [string]$Destination) {
  $temp = "$Destination.extract-$([guid]::NewGuid().ToString('N'))"
  New-Item -ItemType Directory -Path $temp -Force | Out-Null
  try {
    Expand-Archive -LiteralPath $ArchivePath -DestinationPath $temp -Force
    $roots = @(Get-ChildItem -LiteralPath $temp -Directory)
    if ($roots.Count -ne 1) { throw "Expected one root directory in archive: $ArchivePath" }
    if (Test-Path -LiteralPath $Destination) { Remove-Item -LiteralPath $Destination -Recurse -Force }
    Move-Item -LiteralPath $roots[0].FullName -Destination $Destination
  } finally { Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue }
}

function Apply-BossAIInferencePatches([string]$RepoDir, [string]$MatchaDir) {
  $cosyEntry = Join-Path $RepoDir 'cosyvoice\cli\cosyvoice.py'
  $cosyText = Get-Content -LiteralPath $cosyEntry -Raw -Encoding UTF8
  $modelscopeImport = 'from modelscope import snapshot_download'
  $modelscopePatch = @'
def snapshot_download(*args, **kwargs):
    raise RuntimeError('BossAI Video Agent requires installer-provisioned local CosyVoice model files; inference-time model downloading is disabled.')
'@
  if ($cosyText.Contains($modelscopeImport)) {
    $cosyText = $cosyText.Replace($modelscopeImport, $modelscopePatch.TrimEnd())
    Set-Content -LiteralPath $cosyEntry -Value $cosyText -Encoding UTF8
    Write-Output 'BOSSAI_STEP Applied local-model-only CosyVoice inference patch'
  } elseif (-not $cosyText.Contains('inference-time model downloading is disabled')) {
    throw 'CosyVoice local-model-only patch precondition failed.'
  }

  $pylogger = Join-Path $MatchaDir 'matcha\utils\pylogger.py'
  $pyloggerText = Get-Content -LiteralPath $pylogger -Raw -Encoding UTF8
  $lightningImport = 'from lightning.pytorch.utilities import rank_zero_only'
  $lightningPatch = @'
def rank_zero_only(function):
    return function
'@
  if ($pyloggerText.Contains($lightningImport)) {
    $pyloggerText = $pyloggerText.Replace($lightningImport, $lightningPatch.TrimEnd())
    Set-Content -LiteralPath $pylogger -Value $pyloggerText -Encoding UTF8
    Write-Output 'BOSSAI_STEP Applied inference-only Matcha logger patch'
  } elseif (-not $pyloggerText.Contains('def rank_zero_only(function):')) {
    throw 'Matcha inference logger patch precondition failed.'
  }
}

function Commit-Install([string]$StagingDir, [string]$FinalDir) {
  $parent = Split-Path -Parent $FinalDir
  if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
  $quarantine = ''
  if (Test-Path -LiteralPath $FinalDir) {
    if (Test-Path -LiteralPath (Join-Path $FinalDir 'runtime.json') -PathType Leaf) {
      throw "Refusing to replace an installed CosyVoice2 runtime: $FinalDir"
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

$installMutex = [System.Threading.Mutex]::new($false, 'BossAIVideoAgent-CosyVoice2-Install')
$installMutexAcquired = $false
try {
  try { $installMutexAcquired = $installMutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $installMutexAcquired = $true }
  if (-not $installMutexAcquired) { throw 'Another BossAI CosyVoice2 installation is already running.' }
  New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
$repoDir = Join-Path $InstallDir 'CosyVoice'
$venvDir = Join-Path $InstallDir 'venv'
$venvPython = Join-Path $venvDir 'Scripts\python.exe'
$modelDir = Join-Path $InstallDir 'model\CosyVoice2-0.5B'
$licensesDir = Join-Path $InstallDir 'licenses'

$sourceArchive = $cosy.sourceArtifact
if (-not $sourceArchive) { throw 'CosyVoice pinned source artifact is missing.' }
$sourceZip = Join-Path $downloadRoot ("CosyVoice-" + [string]$cosy.sourceRevision + ".zip")
Download-Verified ([string]$sourceArchive.url) $sourceZip ([string]$sourceArchive.sha256) 'CosyVoice source archive'
if (-not (Test-Path -LiteralPath (Join-Path $repoDir 'cosyvoice\cli\cosyvoice.py') -PathType Leaf)) {
  Expand-SingleRootArchive $sourceZip $repoDir
} else {
  Write-Output 'BOSSAI_STEP Resume existing CosyVoice source tree'
}

$matcha = $cosy.submodules.'third_party/Matcha-TTS'
if (-not $matcha) { throw 'CosyVoice Matcha-TTS submodule lock is missing.' }
$matchaZip = Join-Path $downloadRoot ("Matcha-TTS-" + [string]$matcha.revision + ".zip")
Download-Verified ([string]$matcha.archiveUrl) $matchaZip ([string]$matcha.sha256) 'Matcha-TTS source archive'
$matchaDir = Join-Path $repoDir 'third_party\Matcha-TTS'
if (-not (Test-Path -LiteralPath (Join-Path $matchaDir 'matcha') -PathType Container)) {
  Expand-SingleRootArchive $matchaZip $matchaDir
} else {
  Write-Output 'BOSSAI_STEP Resume existing Matcha-TTS source tree'
}

if (-not (Test-Path -LiteralPath (Join-Path $repoDir 'cosyvoice\cli\cosyvoice.py') -PathType Leaf)) { throw 'CosyVoice source archive layout verification failed.' }
if (-not (Test-Path -LiteralPath (Join-Path $matchaDir 'matcha') -PathType Container)) { throw 'Matcha-TTS source archive layout verification failed.' }
Apply-BossAIInferencePatches $repoDir $matchaDir

if (-not (Test-Path -LiteralPath $venvPython)) { Run $PythonExe @('-m','venv',$venvDir) }
Run $venvPython @('-m','pip','install','pip==25.1.1','setuptools==80.9.0','wheel==0.45.1','huggingface_hub==0.30.2')
$torchProfile = $cosy.torchRuntime.profiles.$TorchFlavor
if (-not $torchProfile) { throw "CosyVoice2 Torch profile is not pinned: $TorchFlavor" }
$torchWheelName = switch ($TorchFlavor) {
  'cu121' { 'torch-2.3.1+cu121-cp310-cp310-win_amd64.whl' }
  'cu118' { 'torch-2.3.1+cu118-cp310-cp310-win_amd64.whl' }
  default { 'torch-2.3.1+cpu-cp310-cp310-win_amd64.whl' }
}
$torchaudioWheelName = switch ($TorchFlavor) {
  'cu121' { 'torchaudio-2.3.1+cu121-cp310-cp310-win_amd64.whl' }
  'cu118' { 'torchaudio-2.3.1+cu118-cp310-cp310-win_amd64.whl' }
  default { 'torchaudio-2.3.1+cpu-cp310-cp310-win_amd64.whl' }
}
$torchWheel = Join-Path $downloadRoot $torchWheelName
$torchaudioWheel = Join-Path $downloadRoot $torchaudioWheelName
Download-Verified ([string]$torchProfile.torchUrl) $torchWheel ([string]$torchProfile.torchSha256) "PyTorch $TorchFlavor wheel"
Download-Verified ([string]$torchProfile.torchaudioUrl) $torchaudioWheel ([string]$torchProfile.torchaudioSha256) "TorchAudio $TorchFlavor wheel"
Run $venvPython @('-m','pip','install',$torchWheel,$torchaudioWheel)
$windowsRequirements = Join-Path $PSScriptRoot 'cosyvoice-windows-requirements.txt'
if (-not (Test-Path -LiteralPath $windowsRequirements -PathType Leaf)) { throw "BossAI CosyVoice Windows dependency lock is missing: $windowsRequirements" }
Run $venvPython @('-m','pip','install','--index-url','https://pypi.org/simple','-r',$windowsRequirements)

New-Item -ItemType Directory -Path $modelDir -Force | Out-Null
$requiredModelFiles = @(
  'cosyvoice2.yaml',
  'flow.pt',
  'hift.pt',
  'llm.pt',
  'campplus.onnx',
  'speech_tokenizer_v2.onnx',
  'CosyVoice-BlankEN/config.json',
  'CosyVoice-BlankEN/generation_config.json',
  'CosyVoice-BlankEN/merges.txt',
  'CosyVoice-BlankEN/model.safetensors',
  'CosyVoice-BlankEN/tokenizer_config.json',
  'CosyVoice-BlankEN/vocab.json'
)
if ($ModelSourceDir) {
  $sourceModelDir = [System.IO.Path]::GetFullPath($ModelSourceDir)
  foreach ($required in $requiredModelFiles) {
    $source = Join-Path $sourceModelDir $required
    $expected = [string]$cosy.verifiedHashes.$required
    if (-not $expected) { throw "CosyVoice2 verified hash is missing for: $required" }
    Verify-Hash $source $expected "CosyVoice2 source model file $required"
    $destination = Join-Path $modelDir $required
    $destinationParent = Split-Path -Parent $destination
    if (-not (Test-Path -LiteralPath $destinationParent)) { New-Item -ItemType Directory -Path $destinationParent -Force | Out-Null }
    Copy-Item -LiteralPath $source -Destination $destination -Force
  }
} else {
  foreach ($required in $requiredModelFiles) {
    $expected = [string]$cosy.verifiedHashes.$required
    if (-not $expected) { throw "CosyVoice2 verified hash is missing for: $required" }
    $destination = Join-Path $modelDir $required
    $destinationParent = Split-Path -Parent $destination
    if (-not (Test-Path -LiteralPath $destinationParent)) { New-Item -ItemType Directory -Path $destinationParent -Force | Out-Null }
    $relativeUrl = ($required -replace '\\','/')
    $url = "https://huggingface.co/$([string]$cosy.modelRepository)/resolve/$([string]$cosy.modelRevision)/${relativeUrl}?download=true"
    Download-Verified $url $destination $expected "Pinned CosyVoice2 model file $required"
  }
}
foreach ($required in $requiredModelFiles) {
  $path = Join-Path $modelDir $required
  $expected = [string]$cosy.verifiedHashes.$required
  if (-not $expected) { throw "CosyVoice2 verified hash is missing for: $required" }
  Verify-Hash $path $expected "Pinned CosyVoice2 model file $required"
}

$probe = @'
import pathlib, sys
repo = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(repo))
matcha = repo / 'third_party' / 'Matcha-TTS'
if matcha.is_dir(): sys.path.insert(0, str(matcha))
from cosyvoice.cli.cosyvoice import CosyVoice2
print('BOSSAI_COSYVOICE_IMPORT_OK')
'@
$probePath = Join-Path $InstallDir 'probe.py'
$probe | Set-Content -LiteralPath $probePath -Encoding UTF8
try { Run $venvPython @($probePath,$repoDir) } finally { Remove-Item -LiteralPath $probePath -Force -ErrorAction SilentlyContinue }

New-Item -ItemType Directory -Path $licensesDir -Force | Out-Null
$sourceLicense = Join-Path $repoDir 'LICENSE'
if (Test-Path -LiteralPath $sourceLicense) { Copy-Item -LiteralPath $sourceLicense -Destination (Join-Path $licensesDir 'CosyVoice-LICENSE.txt') -Force }
$modelReadme = Join-Path $modelDir 'README.md'
if (Test-Path -LiteralPath $modelReadme) { Copy-Item -LiteralPath $modelReadme -Destination (Join-Path $licensesDir 'CosyVoice2-MODEL-CARD.md') -Force }

$supplementDir = Join-Path $licensesDir 'supplemental-python'
New-Item -ItemType Directory -Path $supplementDir -Force | Out-Null
$supplementEntries = @()
foreach ($supplement in @($cosy.supplementalPythonLicenses)) {
  $packageName = [string]$supplement.package
  $packageVersion = [string]$supplement.version
  $safePackage = ($packageName -replace '[^A-Za-z0-9._-]+','-')
  $safeVersion = ($packageVersion -replace '[^A-Za-z0-9._-]+','-')
  $safeFile = ([string]$supplement.filename -replace '[^A-Za-z0-9._-]+','-')
  $supplementFileName = "$safePackage-$safeVersion-$safeFile"
  $supplementPath = Join-Path $supplementDir $supplementFileName
  Download-Verified ([string]$supplement.url) $supplementPath ([string]$supplement.sha256) "Python license supplement $packageName==$packageVersion"
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
  component = 'cosyvoice2-0.5b'
  entries = $supplementEntries
} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $supplementManifestPath -Encoding UTF8

$captureNotices = Join-Path (Split-Path -Parent $PSScriptRoot) 'legal\capture-python-runtime-notices.py'
if (-not (Test-Path -LiteralPath $captureNotices -PathType Leaf)) { throw "BossAI runtime notice capture tool is missing: $captureNotices" }
Run $venvPython @($captureNotices,'--component','cosyvoice2-0.5b','--out',$licensesDir,'--supplemental-license-manifest',$supplementManifestPath,'--require-complete')

$runtimeManifest = [ordered]@{
  schema = 'bossai.video-agent-installed-runtime.v1'
  component = 'cosyvoice2-0.5b'
  installedAt = [DateTimeOffset]::UtcNow.ToString('o')
  source = [ordered]@{
    repository=[string]$cosy.sourceRepository
    revision=[string]$cosy.sourceRevision
    modelRepository=[string]$cosy.modelRepository
    modelRevision=[string]$cosy.modelRevision
    bossaiInferencePatches=@('local-model-only-no-runtime-download','matcha-inference-logger-no-lightning')
  }
  inference = [ordered]@{ torchFlavor=$TorchFlavor }
  licenseEvidence = 'licenses/python-dependency-notices.json'
  supplementalLicenseEvidence = 'licenses/python-license-supplements.json'
  files = @($requiredModelFiles | ForEach-Object {
    $path = Join-Path $modelDir $_
    [ordered]@{ name=$_; bytes=(Get-Item -LiteralPath $path).Length; sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() }
  })
  env = [ordered]@{
    BOSSAI_COSYVOICE_ROOT=(Join-Path $TargetDir 'CosyVoice')
    BOSSAI_COSYVOICE_MODEL_DIR=(Join-Path $TargetDir 'model\CosyVoice2-0.5B')
    BOSSAI_COSYVOICE_PYTHON=(Join-Path $TargetDir 'venv\Scripts\python.exe')
  }
  rights = [ordered]@{ referenceVoice='customer-authorized-or-bossai-owned-only'; upstreamExampleVoicesMayShip=$false }
}
$runtimeManifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $InstallDir 'runtime.json') -Encoding UTF8
Commit-Install $InstallDir $TargetDir
Write-Output 'BOSSAI_DONE CosyVoice2 runtime installed from pinned official sources.'
} catch {
  if ($ResumeStagingDir) {
    Write-Output "BOSSAI_STEP Resume failed; preserving staging for diagnosis: $InstallDir"
  } elseif (Test-Path -LiteralPath $InstallDir) {
    Remove-Item -LiteralPath $InstallDir -Recurse -Force -ErrorAction SilentlyContinue
  }
  throw
} finally {
  if ($installMutexAcquired) {
    try { $installMutex.ReleaseMutex() } catch { }
  }
  $installMutex.Dispose()
}
