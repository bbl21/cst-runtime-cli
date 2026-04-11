param(
    [string]$SkillName = "",
    [string]$SourceDir = "C:\Users\z1376\Documents\CST_MCP\skills",
    [string]$TargetDir = "C:\Users\z1376\.config\opencode\skills"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $SourceDir)) {
    throw "Source skills directory not found: $SourceDir"
}

if (-not (Test-Path $TargetDir)) {
    New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
}

if ([string]::IsNullOrWhiteSpace($SkillName)) {
    $sourcePath = $SourceDir
    $targetPath = $TargetDir
    Copy-Item "$sourcePath\*" $targetPath -Recurse -Force
    Write-Output "Synced all skills: $SourceDir -> $TargetDir"
    exit 0
}

$singleSource = Join-Path $SourceDir $SkillName
$singleTarget = Join-Path $TargetDir $SkillName

if (-not (Test-Path $singleSource)) {
    throw "Skill not found: $singleSource"
}

if (Test-Path $singleTarget) {
    Remove-Item $singleTarget -Recurse -Force
}

Copy-Item $singleSource $singleTarget -Recurse -Force
Write-Output "Synced skill: $SkillName"
