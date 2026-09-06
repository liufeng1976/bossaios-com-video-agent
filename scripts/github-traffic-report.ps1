param(
  [string]$SavePath = ''
)

$ErrorActionPreference = 'Stop'
$Repo = 'liufeng1976/bossaios-com-video-agent'
$ReleaseTag = 'v0.1.0-pilot'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

$gh = Get-Command gh -ErrorAction Stop
& $gh.Source auth status *> $null
if ($LASTEXITCODE -ne 0) {
  throw 'GitHub CLI authentication is not available for the current Windows user.'
}

function Gh-Json([string[]]$Args) {
  $raw = & $gh.Source @Args
  if ($LASTEXITCODE -ne 0) { throw "gh command failed: gh $($Args -join ' ')" }
  return $raw | ConvertFrom-Json
}

$views = Gh-Json @('api', "repos/$Repo/traffic/views")
$clones = Gh-Json @('api', "repos/$Repo/traffic/clones")
$referrers = Gh-Json @('api', "repos/$Repo/traffic/popular/referrers")
$paths = Gh-Json @('api', "repos/$Repo/traffic/popular/paths")
$community = Gh-Json @('repo', 'view', $Repo, '--json', 'stargazerCount,forkCount,issues')
$release = Gh-Json @('release', 'view', $ReleaseTag, '--repo', $Repo, '--json', 'tagName,isPrerelease,assets')

$installer = $release.assets | Where-Object { $_.name -eq 'BossAI-Video-Agent-0.1.0-Setup.exe' } | Select-Object -First 1

$report = [ordered]@{
  schemaVersion = 1
  project = 'bossaios-com-video-agent'
  capturedAt = (Get-Date).ToUniversalTime().ToString('o')
  semantics = [ordered]@{
    traffic = 'GitHub rolling 14-day views/clones window; not cumulative acquisition.'
    community = 'Point-in-time cumulative Stars/Forks/Open Issues.'
    releaseDownloads = 'GitHub release asset download_count; do not assume every download is external or successful use.'
  }
  traffic = [ordered]@{
    views = $views.count
    uniqueVisitors = $views.uniques
    clones = $clones.count
    uniqueCloners = $clones.uniques
  }
  community = [ordered]@{
    stars = $community.stargazerCount
    forks = $community.forkCount
    openIssues = $community.issues.totalCount
  }
  pilot = [ordered]@{
    tag = $release.tagName
    prerelease = $release.isPrerelease
    installer = if ($installer) { $installer.name } else { $null }
    downloadCount = if ($installer) { $installer.downloadCount } else { $null }
  }
  topReferrers = $referrers
  popularPaths = $paths
}

$json = $report | ConvertTo-Json -Depth 8
Write-Output $json

if ($SavePath) {
  $absolute = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $SavePath))
  $rootFull = [System.IO.Path]::GetFullPath($repoRoot)
  if (-not $absolute.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'SavePath must stay inside the repository.'
  }
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $absolute) | Out-Null
  [System.IO.File]::WriteAllText($absolute, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
  Write-Host "Saved GitHub traffic snapshot: $SavePath" -ForegroundColor Green
}
