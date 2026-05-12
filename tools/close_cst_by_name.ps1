param(
    [string]$ProjectName,
    [switch]$Force
)

. "$PSScriptRoot\LoadCstAllowlist.ps1"
$CstForceKillAllowlist = Get-CstForceKillAllowlist

function Stop-AllowlistedCstProcesses {
    param([string[]]$Names)
    foreach ($name in $Names) {
        Stop-Process -Name $name -Force -ErrorAction SilentlyContinue
    }
}

if ($Force -or -not $ProjectName) {
    Stop-AllowlistedCstProcesses -Names $CstForceKillAllowlist
    Write-Output "closed all"
} else {
    Get-Process 'CST DESIGN ENVIRONMENT_AMD64' -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowTitle -like "*$ProjectName*" } |
        Stop-Process -Force -ErrorAction SilentlyContinue
    $remainingDesign = @(Get-Process 'CST DESIGN ENVIRONMENT_AMD64' -ErrorAction SilentlyContinue)
    if ($remainingDesign.Count -eq 0) {
        $remainingAllowlist = $CstForceKillAllowlist | Where-Object { $_ -ne 'CST DESIGN ENVIRONMENT_AMD64' }
        Stop-AllowlistedCstProcesses -Names $remainingAllowlist
    }
    Write-Output "closed: $ProjectName"
}
