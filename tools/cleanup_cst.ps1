. "$PSScriptRoot\LoadCstAllowlist.ps1"
$CstForceKillAllowlist = Get-CstForceKillAllowlist

foreach ($name in $CstForceKillAllowlist) {
    Stop-Process -Name $name -Force -ErrorAction SilentlyContinue
}
Write-Output "done"
