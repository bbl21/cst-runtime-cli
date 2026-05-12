param(
    [string]$SkillName = "",
    [switch]$DryRun,
    [switch]$PruneRemoved,
    [ValidateSet("Copy", "Junction")]
    [string]$Mode = "Copy"
)

$ErrorActionPreference = "Stop"

$syncScript = Join-Path $PSScriptRoot "sync_agent_skills.ps1"
$forwardParams = @{
    Targets = @("opencode", "opencode_user")
    Mode = $Mode
}

if (-not [string]::IsNullOrWhiteSpace($SkillName)) {
    $forwardParams.SkillName = $SkillName
}

if ($DryRun) {
    $forwardParams.DryRun = $true
}

if ($PruneRemoved) {
    $forwardParams.PruneRemoved = $true
}

& $syncScript @forwardParams
