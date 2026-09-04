[CmdletBinding()]
param(
  [string]$InstallerPath = '.\BossAI-Video-Agent-0.1.0-Setup.exe'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$expectedSha256 = '525e22848dd08443eecd828975522bb20143b390fa03ee5e260b968632273ee7'
$resolved = (Resolve-Path -LiteralPath $InstallerPath).Path
$actualSha256 = (Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash.ToLowerInvariant()
$signature = Get-AuthenticodeSignature -LiteralPath $resolved

$result = [ordered]@{
  schema = 'bossai.video-agent-pilot-package-verification.v1'
  productId = 'bossai-video-agent'
  version = '0.1.0'
  channel = 'internal-pilot'
  installer = $resolved
  sha256Expected = $expectedSha256
  sha256Actual = $actualSha256
  sha256Valid = ($actualSha256 -eq $expectedSha256)
  authenticodeStatus = [string]$signature.Status
  signed = ($signature.Status -eq [System.Management.Automation.SignatureStatus]::Valid)
  gaApproved = $false
}

$result | ConvertTo-Json -Depth 4
if ($actualSha256 -ne $expectedSha256) {
  Write-Output 'RESULT: Pilot installer verification FAILED. SHA-256 mismatch.'
  exit 2
}

if ($signature.Status -ne [System.Management.Automation.SignatureStatus]::Valid) {
  Write-Output 'WARNING: This exact installer is unsigned. Internal Pilot only; Windows SmartScreen/security warnings may appear.'
}
Write-Output 'RESULT: Exact BossAI Video Agent 0.1.0 Internal Pilot installer SHA-256 verified.'
exit 0
