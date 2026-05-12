param(
    [switch]$DryRun
)

. "$PSScriptRoot\LoadCstAllowlist.ps1"
$CstForceKillAllowlist = Get-CstForceKillAllowlist

$attempts = @()
foreach ($name in $CstForceKillAllowlist) {
    $processes = @(Get-Process -Name $name -ErrorAction SilentlyContinue)
    foreach ($process in $processes) {
        if ($DryRun) {
            $attempts += "dry_run:$($process.Id):$($process.ProcessName)"
            continue
        }
        try {
            Stop-Process -Id $process.Id -Force -ErrorAction Stop
            $attempts += "killed:$($process.Id):$($process.ProcessName)"
        } catch {
            $attempts += "failed:$($process.Id):$($process.ProcessName):$($_.Exception.Message)"
        }
    }
}

Write-Output "CST force-kill allowlist: $($CstForceKillAllowlist -join ', ')"
if ($attempts.Count -eq 0) {
    Write-Output "No allowlisted CST processes found"
} else {
    $attempts | ForEach-Object { Write-Output $_ }
}
