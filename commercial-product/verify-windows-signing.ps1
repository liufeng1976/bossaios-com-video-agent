[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$ApplicationExe,
  [Parameter(Mandatory=$true)][string]$InstallerExe
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Verify-One([string]$Path, [string]$Role) {
  $resolved = (Resolve-Path -LiteralPath $Path).Path
  $signature = Get-AuthenticodeSignature -LiteralPath $resolved
  $certificate = $signature.SignerCertificate
  [ordered]@{
    role = $Role
    path = $resolved
    status = [string]$signature.Status
    valid = ($signature.Status -eq [System.Management.Automation.SignatureStatus]::Valid -and $null -ne $certificate)
    signerSubject = if ($certificate) { [string]$certificate.Subject } else { $null }
    signerThumbprint = if ($certificate) { [string]$certificate.Thumbprint } else { $null }
    notBefore = if ($certificate) { $certificate.NotBefore.ToString('o') } else { $null }
    notAfter = if ($certificate) { $certificate.NotAfter.ToString('o') } else { $null }
    sha256 = (Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash.ToLowerInvariant()
  }
}

$application = Verify-One $ApplicationExe 'application'
$installer = Verify-One $InstallerExe 'installer'
$passed = ($application.valid -and $installer.valid)
$result = [ordered]@{
  schema = 'bossai.video-agent-windows-signing-evidence.v1'
  productId = 'bossai-video-agent'
  passed = $passed
  application = $application
  installer = $installer
}
$result | ConvertTo-Json -Depth 8
if (-not $passed) {
  Write-Output 'RESULT: BossAI Windows signing verification FAILED CLOSED.'
  exit 2
}
Write-Output 'RESULT: BossAI Windows Authenticode signing verified.'
exit 0
